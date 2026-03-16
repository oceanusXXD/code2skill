from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__ as CODE2SKILL_VERSION
from .config import infer_language
from .extractors.config_extractor import ConfigExtractor
from .extractors.python_extractor import PythonExtractor
from .json_utils import parse_json_object
from .llm_backend import LLMBackend
from .models import (
    ConfigSummary,
    FileCandidate,
    FileDiffPatch,
    RuleSummary,
    SkillBlueprint,
    SkillPlan,
    SkillPlanEntry,
    SkillRecommendation,
    SourceFileSummary,
    StateSnapshot,
)
from .scanner.prioritizer import FilePrioritizer


GenerationPromptBuilder = Callable[
    [SkillBlueprint, SkillPlanEntry, list[dict[str, str]], list[RuleSummary]],
    str,
]
IncrementalPromptBuilder = Callable[
    [
        SkillBlueprint,
        SkillPlanEntry,
        str,
        list[FileDiffPatch],
        StateSnapshot | None,
        "ParsedSkillDocument",
    ],
    str,
]


DEFAULT_SKILL_SYSTEM_PROMPT = (
    "You are a strict repository standards analyst. "
    "Generate skill documents only from the provided code, skeleton summaries, "
    "and repository rules. Do not invent modules, frameworks, workflows, future "
    "plans, or best practices that are not grounded in the input. Do not use emoji."
)
DEFAULT_INCREMENTAL_SYSTEM_PROMPT = (
    "You are a strict repository standards analyst. "
    "Revise the existing skill document only where the supplied code changes justify it. "
    "Remove invalidated rules instead of preserving stale guidance. Do not use emoji."
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\uFE0F"
    "]",
    flags=re.UNICODE,
)
_LOW_VALUE_RULE_PATTERNS = [
    re.compile(r"from __future__ import annotations", flags=re.IGNORECASE),
    re.compile(r"\bimport(?:s|ing)?\s+path\b", flags=re.IGNORECASE),
    re.compile(r"\bpath\b.*\bimport", flags=re.IGNORECASE),
    re.compile(r"\bimport\s+order\b", flags=re.IGNORECASE),
    re.compile(r"\bempty\s+__init__\.py\b", flags=re.IGNORECASE),
]


@dataclass
class SkillDocumentSection:
    heading: str
    content: str


@dataclass
class ParsedSkillDocument:
    title: str
    preamble: str
    sections: list[SkillDocumentSection]


class SkillGenerator:
    def __init__(
        self,
        backend: LLMBackend,
        repo_path: Path,
        output_dir: Path,
        max_inline_chars: int,
        system_prompt: str | None = None,
        generation_prompt_builder: GenerationPromptBuilder | None = None,
        incremental_system_prompt: str | None = None,
        incremental_prompt_builder: IncrementalPromptBuilder | None = None,
    ) -> None:
        self.backend = backend
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.max_inline_chars = max_inline_chars
        self.system_prompt = system_prompt or DEFAULT_SKILL_SYSTEM_PROMPT
        self.generation_prompt_builder = (
            generation_prompt_builder or build_default_generation_prompt
        )
        self.incremental_system_prompt = (
            incremental_system_prompt or DEFAULT_INCREMENTAL_SYSTEM_PROMPT
        )
        self.incremental_prompt_builder = (
            incremental_prompt_builder or build_default_incremental_prompt
        )
        self.config_extractor = ConfigExtractor()
        self.python_extractor = PythonExtractor()
        self.prioritizer = FilePrioritizer()

    def generate_all(
        self,
        blueprint: SkillBlueprint,
        plan: SkillPlan,
    ) -> dict[str, str]:
        artifacts: dict[str, str] = {}
        for skill in plan.skills:
            artifacts[f"skills/{skill.name}.md"] = self._generate_skill(
                blueprint=blueprint,
                skill=skill,
            )
        artifacts["skills/index.md"] = render_skill_index(plan)
        return artifacts

    def generate_incremental(
        self,
        blueprint: SkillBlueprint,
        plan: SkillPlan,
        affected_skill_names: list[str],
        changed_files: list[str],
        changed_diffs: list[FileDiffPatch],
        previous_state: StateSnapshot | None,
    ) -> dict[str, str]:
        affected = set(affected_skill_names)
        changed = set(changed_files)
        changed_by_path = {item.path: item for item in changed_diffs}
        recommendations = {
            item.name: item
            for item in blueprint.recommended_skills
        }
        artifacts: dict[str, str] = {}

        for skill in plan.skills:
            if skill.name not in affected:
                continue
            skill_path = self.output_dir / "skills" / f"{skill.name}.md"
            relevant_diffs = self._collect_relevant_diffs(
                skill=skill,
                recommendation=recommendations.get(skill.name),
                changed_files=changed,
                changed_by_path=changed_by_path,
            )
            if skill_path.exists() and relevant_diffs:
                artifacts[f"skills/{skill.name}.md"] = self._update_skill(
                    blueprint=blueprint,
                    skill=skill,
                    existing_skill_md=skill_path.read_text(encoding="utf-8"),
                    changed_diffs=relevant_diffs,
                    previous_state=previous_state,
                )
                continue
            artifacts[f"skills/{skill.name}.md"] = self._generate_skill(
                blueprint=blueprint,
                skill=skill,
            )

        if artifacts:
            artifacts["skills/index.md"] = render_skill_index(plan)
        return artifacts

    def _collect_relevant_diffs(
        self,
        skill: SkillPlanEntry,
        recommendation: SkillRecommendation | None,
        changed_files: set[str],
        changed_by_path: dict[str, FileDiffPatch],
    ) -> list[FileDiffPatch]:
        relevant_paths: list[str] = []
        seen: set[str] = set()
        candidate_paths = [
            *skill.read_files,
            *(recommendation.source_evidence if recommendation else []),
        ]
        for path in candidate_paths:
            if path not in changed_files or path in seen:
                continue
            diff_entry = changed_by_path.get(path)
            if diff_entry is None:
                continue
            relevant_paths.append(path)
            seen.add(path)

        if relevant_paths:
            return [changed_by_path[path] for path in relevant_paths]

        return [
            changed_by_path[path]
            for path in sorted(changed_files)
            if path in changed_by_path
        ]

    def _generate_skill(
        self,
        blueprint: SkillBlueprint,
        skill: SkillPlanEntry,
    ) -> str:
        context_files = [
            entry
            for path in skill.read_files
            if (entry := self._load_file_context(path)) is not None
        ]
        relevant_rules = filter_rules_by_skill(blueprint.abstract_rules, skill)
        prompt = self.generation_prompt_builder(
            blueprint,
            skill,
            context_files,
            relevant_rules,
        )
        raw = self.backend.complete(prompt=prompt, system=self.system_prompt)
        return _sanitize_markdown(raw)

    def _update_skill(
        self,
        blueprint: SkillBlueprint,
        skill: SkillPlanEntry,
        existing_skill_md: str,
        changed_diffs: list[FileDiffPatch],
        previous_state: StateSnapshot | None,
    ) -> str:
        existing_document = _parse_skill_document(existing_skill_md)
        prompt = self.incremental_prompt_builder(
            blueprint,
            skill,
            existing_skill_md,
            changed_diffs,
            previous_state,
            existing_document,
        )
        raw = self.backend.complete(
            prompt=prompt,
            system=self.incremental_system_prompt,
        )
        payload = parse_json_object(
            raw,
            error_context="Incremental skill update response was not valid JSON",
            backend=self.backend,
            expected_top_level_key="updated_sections",
            repair_hint=(
                "The output must be a JSON object with an 'updated_sections' array. "
                "Each item must include heading and content."
            ),
        )
        updated_sections = payload.get("updated_sections", [])
        if not isinstance(updated_sections, list):
            raise RuntimeError("Incremental skill update payload must contain a list.")
        return _apply_section_updates(
            existing_document=existing_document,
            updated_sections=updated_sections,
        )

    def _load_file_context(self, relative_path: str) -> dict[str, str] | None:
        absolute_path = self.repo_path / Path(relative_path)
        if not absolute_path.exists() or not absolute_path.is_file():
            return None
        content = absolute_path.read_text(encoding="utf-8", errors="ignore")
        if len(content) <= self.max_inline_chars:
            return {"path": relative_path, "content": content}
        return {
            "path": relative_path,
            "content": self._build_skeleton_from_content(relative_path, content),
        }

    def _build_skeleton_from_content(self, relative_path: str, content: str) -> str:
        relative = Path(relative_path)
        language = infer_language(relative)
        _, reasons, role = self.prioritizer.score(relative, language)
        candidate = FileCandidate(
            absolute_path=self.repo_path / relative,
            relative_path=relative,
            size_bytes=len(content.encode("utf-8")),
            char_count=len(content),
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            language=language,
            inferred_role=role,
            priority=0,
            priority_reasons=reasons,
            content=content,
            gitignored=False,
        )

        config_summary = self.config_extractor.extract(candidate)
        if config_summary is not None:
            return _render_config_summary(config_summary)
        if language == "python":
            return _render_source_summary(self.python_extractor.extract(candidate))
        return content[: self.max_inline_chars]


def build_default_generation_prompt(
    blueprint: SkillBlueprint,
    skill: SkillPlanEntry,
    context_files: list[dict[str, str]],
    relevant_rules: list[RuleSummary],
) -> str:
    rendered_rules = "\n".join(
        [
            (
                f"- {rule.name}: {rule.rule} "
                f"(confidence={rule.confidence:.0%}; source={rule.source}; "
                f"evidence={', '.join(rule.evidence) or '[none]'})"
            )
            for rule in relevant_rules
        ]
    ) or "[no explicit repository rules matched]"
    rendered_files = "\n\n".join(
        [
            f"--- {item['path']} ---\n{item['content']}"
            for item in context_files
        ]
    ) or "[no readable file context available]"

    return f"""
You are a repository standards analyst. Generate one Skill document for an AI coding assistant using only the evidence below.

Project type: {blueprint.project_profile.repo_type}
Tech stack: {json.dumps(blueprint.tech_stack, ensure_ascii=False)}
Skill name: {skill.name}
Skill title: {skill.title}
Skill scope: {skill.scope}
Why this skill exists: {skill.why}
Read-plan rationale: {skill.read_reason}

Known repository rules:
{rendered_rules}

Relevant code and skeleton context:

{rendered_files}

Hard requirements:
1. Infer only from the provided rules and file context.
2. Do not invent missing modules, frameworks, workflows, directories, design goals, or future plans.
3. Write the final Skill document in English.
4. Do not use emoji, decorative symbols, or extra headings.
5. Output exactly the 5 sections listed below and nothing else.
6. Every bullet under "Core Rules" must include a source path in the same bullet.
7. Use strong wording such as "must", "never", or "always" only when the code clearly supports it.
8. If the evidence only shows a common pattern instead of a hard rule, say so explicitly.
9. Mark uncertainty as [Needs confirmation].
10. Prefer behavior constraints, call order, module boundaries, data contracts, and extension points over style trivia.
11. Do not turn `from __future__ import annotations`, routine typing, import ordering, empty `__init__.py`, or a shared `Path` import into a rule unless it materially affects behavior.
12. Keep "Core Rules" to 4-6 high-value bullets.

Return Markdown with exactly this structure:

# {skill.title}

## Overview
Write 1-2 sentences describing the role and importance of this area in the repository.

## Core Rules
- Use a single-level bullet list.
- Each bullet must be concrete, actionable, and include "Source: path[:symbol]".
- If a rule is only partially supported, describe the scope or mark it [Needs confirmation].
- Do not turn syntax trivia or accidental similarity into a rule.

## Typical Patterns
Show 1-3 short code snippets. Explain the source file before each snippet.

## Avoid
List only anti-patterns that can be inferred from the current code. If evidence is insufficient, write one bullet: "[Needs confirmation] The current context is not sufficient to derive a stable anti-pattern."

## Common Flows
If this area has a stable operational flow, write it step by step. Otherwise write one bullet: "[Needs confirmation] The current context does not show a stable flow."
""".strip()


def build_default_incremental_prompt(
    blueprint: SkillBlueprint,
    skill: SkillPlanEntry,
    existing_skill_md: str,
    changed_diffs: list[FileDiffPatch],
    previous_state: StateSnapshot | None,
    existing_document: ParsedSkillDocument,
) -> str:
    change_sections: list[str] = []
    for diff_entry in changed_diffs:
        before_path = diff_entry.previous_path or diff_entry.path
        before = (
            "[new file]"
            if diff_entry.change_type == "add"
            else _load_previous_context(before_path, previous_state)
        )
        if diff_entry.change_type == "delete":
            after = "[file deleted]"
        else:
            after = (
                _load_current_context(previous_state, blueprint, diff_entry.path)
                or "[current version unavailable]"
            )
        metadata = [
            f"--- {diff_entry.path} ---",
            f"change_type: {diff_entry.change_type}",
        ]
        if diff_entry.previous_path is not None:
            metadata.append(f"previous_path: {diff_entry.previous_path}")
        change_sections.append(
            "\n".join(
                [
                    *metadata,
                    "Unified diff:",
                    diff_entry.patch.strip() or "[empty patch]",
                    "",
                    "Before:",
                    before,
                    "",
                    "After:",
                    after,
                ]
            )
        )

    return f"""
Here is the current Skill document:
{existing_skill_md}

Skill metadata:
- Name: {skill.name}
- Title: {skill.title}
- Scope: {skill.scope}
- Why it exists: {skill.why}

Existing section headings that may be updated:
{chr(10).join(f"- {section.heading}" for section in existing_document.sections) or "[none]"}

Changed files and supporting context:

{chr(10).join(change_sections)}

Repository context:
- Project type: {blueprint.project_profile.repo_type}
- Tech stack: {json.dumps(blueprint.tech_stack, ensure_ascii=False)}

Revision requirements:
1. Update only the parts justified by the supplied file changes.
2. Preserve still-valid content and remove rules that are no longer supported.
3. Do not rewrite the whole document into a new style.
4. Keep the final content in English.
5. Use [Needs confirmation] where the change makes a previous rule uncertain.
6. Use strong wording only when the changed code clearly supports it.
7. Do not add new sections or use emoji.
8. Return only the affected sections, not the full document.
9. Each section heading must come from the existing section list.

Return strict JSON:
{{
  "updated_sections": [
    {{
      "heading": "section heading",
      "content": "full section markdown that starts with ## {{heading}}"
    }}
  ]
}}
""".strip()


def match_planned_skills(affected_files: list[str], plan: SkillPlan) -> list[str]:
    affected = set(affected_files)
    return [
        skill.name
        for skill in plan.skills
        if affected & set(skill.read_files)
    ]


def filter_rules_by_skill(
    abstract_rules: list[RuleSummary],
    skill: SkillPlanEntry,
) -> list[RuleSummary]:
    tokens = _tokenize(
        " ".join(
            [
                skill.name,
                skill.title,
                skill.scope,
                skill.why,
                " ".join(skill.read_files),
            ]
        )
    )
    scored: list[tuple[int, RuleSummary]] = []
    for rule in abstract_rules:
        score = 0
        evidence = set(rule.evidence)
        if evidence & set(skill.read_files):
            score += 5
        rule_tokens = _tokenize(" ".join([rule.name, rule.rule, rule.rationale]))
        score += len(tokens & rule_tokens)
        score += int(rule.confidence * 3)
        if score > 0:
            scored.append((score, rule))

    if not scored:
        return abstract_rules[:5]
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1].confidence,
            item[1].name,
        )
    )
    return [rule for _, rule in scored[:8]]


def render_skill_index(plan: SkillPlan) -> str:
    rows = "\n".join(
        [
            f"| {skill.title} | {skill.scope or '-'} | [{skill.name}.md](./{skill.name}.md) |"
            for skill in plan.skills
        ]
    )
    return f"""# Project Skill Index

| Skill | Scope | File |
|---|---|---|
{rows}

Generated at: {datetime.now(timezone.utc).isoformat()}
Generated by: code2skill v{CODE2SKILL_VERSION}
""".strip() + "\n"


def _load_current_context(
    previous_state: StateSnapshot | None,
    blueprint: SkillBlueprint,
    relative_path: str,
) -> str | None:
    repo_root = None
    if previous_state is not None:
        repo_root = Path(previous_state.repo_root)
    elif blueprint.project_profile.entrypoints:
        repo_root = Path.cwd()

    if repo_root is None:
        return None

    absolute_path = repo_root / Path(relative_path)
    if not absolute_path.exists() or not absolute_path.is_file():
        return None
    return absolute_path.read_text(encoding="utf-8", errors="ignore")


def _load_previous_context(
    relative_path: str,
    previous_state: StateSnapshot | None,
) -> str:
    if previous_state is None:
        return "[previous version unavailable]"
    record = previous_state.files.get(relative_path)
    if record is None:
        return "[previous version unavailable]"
    if record.config_summary is not None:
        return _render_config_summary(record.config_summary)
    if record.source_summary is not None:
        return _render_source_summary(record.source_summary)
    return "[previous version unavailable]"


def _parse_skill_document(markdown: str) -> ParsedSkillDocument:
    stripped = markdown.strip()
    if not stripped:
        raise RuntimeError("Existing skill document is empty.")

    lines = stripped.splitlines()
    title = lines[0].strip()
    if not title.startswith("# "):
        raise RuntimeError("Existing skill document must start with a level-1 heading.")

    preamble_lines: list[str] = []
    sections: list[SkillDocumentSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines[1:]:
        if line.startswith("## "):
            if current_heading is not None:
                sections.append(
                    SkillDocumentSection(
                        heading=current_heading,
                        content="\n".join(current_lines).strip(),
                    )
                )
            current_heading = line[3:].strip()
            current_lines = [line]
            continue

        if current_heading is None:
            preamble_lines.append(line)
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append(
            SkillDocumentSection(
                heading=current_heading,
                content="\n".join(current_lines).strip(),
            )
        )

    if not sections:
        body = "\n".join(lines[1:]).strip()
        sections.append(
            SkillDocumentSection(
                heading="Body",
                content=f"## Body\n{body}".strip(),
            )
        )

    return ParsedSkillDocument(
        title=title,
        preamble="\n".join(preamble_lines).strip(),
        sections=sections,
    )


def _apply_section_updates(
    existing_document: ParsedSkillDocument,
    updated_sections: list[object],
) -> str:
    sections = [
        SkillDocumentSection(
            heading=section.heading,
            content=section.content,
        )
        for section in existing_document.sections
    ]
    section_index = {
        section.heading: index
        for index, section in enumerate(sections)
    }

    for item in updated_sections:
        if not isinstance(item, dict):
            raise RuntimeError("Each updated section must be an object.")
        heading = str(item.get("heading", "")).strip()
        content = str(item.get("content", "")).strip()
        if not heading or heading not in section_index:
            raise RuntimeError(f"Unknown section heading in incremental update: {heading}")
        sections[section_index[heading]] = SkillDocumentSection(
            heading=heading,
            content=_normalize_updated_section_content(
                heading=heading,
                content=content,
            ),
        )

    parts = [existing_document.title]
    if existing_document.preamble:
        parts.append(existing_document.preamble)
    parts.extend(section.content for section in sections if section.content)
    return _sanitize_markdown(
        "\n\n".join(part.strip() for part in parts if part.strip())
    )


def _normalize_updated_section_content(heading: str, content: str) -> str:
    normalized = content.strip()
    expected_heading = f"## {heading}"
    if not normalized.startswith(expected_heading):
        raise RuntimeError(
            f"Updated section content must start with '{expected_heading}'."
        )
    lines = normalized.splitlines()
    if "<!-- UPDATED -->" not in normalized:
        lines.insert(1, "<!-- UPDATED -->")
    return "\n".join(lines).strip()


def _render_config_summary(summary: ConfigSummary) -> str:
    details = json.dumps(summary.details, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            f"[CONFIG SKELETON] {summary.path}",
            f"kind: {summary.kind}",
            f"summary: {summary.summary}",
            f"framework_signals: {', '.join(summary.framework_signals) or '-'}",
            f"entrypoints: {', '.join(summary.entrypoints) or '-'}",
            "details:",
            details,
        ]
    )


def _render_source_summary(summary: SourceFileSummary) -> str:
    route_lines = [
        f"- {route.method} {route.path} -> {route.handler} ({route.framework})"
        for route in summary.routes
    ]
    return "\n".join(
        [
            f"[SOURCE SKELETON] {summary.path}",
            f"role: {summary.inferred_role}",
            f"language: {summary.language or '-'}",
            f"summary: {summary.short_doc_summary}",
            f"imports: {', '.join(summary.imports) or '-'}",
            f"exports: {', '.join(summary.exports) or '-'}",
            f"classes: {', '.join(summary.classes) or '-'}",
            f"functions: {', '.join(summary.functions) or '-'}",
            f"methods: {', '.join(summary.methods) or '-'}",
            f"models_or_schemas: {', '.join(summary.models_or_schemas) or '-'}",
            f"state_signals: {', '.join(summary.state_signals) or '-'}",
            "routes:",
        ]
        + (route_lines or ["-"])
        + [f"notes: {', '.join(summary.notes) or '-'}"]
    )


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-zA-Z0-9_/.-]+", text.lower())
        if token
    }


def _sanitize_markdown(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").strip()
    cleaned = _EMOJI_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return _remove_low_value_core_rules(cleaned)


def _remove_low_value_core_rules(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines: list[str] = []
    in_core_rules = False
    kept_rule_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_core_rules and kept_rule_count == 0:
                cleaned_lines.append(
                    "- [Needs confirmation] The current context is not sufficient to derive high-value rules."
                )
            in_core_rules = stripped == "## Core Rules"
            if in_core_rules:
                kept_rule_count = 0
            cleaned_lines.append(line)
            continue

        if in_core_rules and stripped.startswith("- "):
            if _is_low_value_rule(stripped):
                continue
            kept_rule_count += 1

        cleaned_lines.append(line)

    if in_core_rules and kept_rule_count == 0:
        cleaned_lines.append(
            "- [Needs confirmation] The current context is not sufficient to derive high-value rules."
        )

    return "\n".join(cleaned_lines).strip() + "\n"


def _is_low_value_rule(line: str) -> bool:
    return any(pattern.search(line) for pattern in _LOW_VALUE_RULE_PATTERNS)
