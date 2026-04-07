from __future__ import annotations

import ast
import importlib
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from code2skill.version import __version__ as CODE2SKILL_VERSION
from .json_utils import parse_json_object
from .llm_backend import LLMBackend
from .models import (
    ConfigSummary,
    FileDiffPatch,
    RuleSummary,
    SkillBlueprint,
    SkillPlan,
    SkillPlanEntry,
    SkillRecommendation,
    SourceFileSummary,
    StateSnapshot,
)
from .skill_markdown import (
    ParsedSkillDocument,
    apply_section_updates,
    finalize_generated_skill,
    parse_skill_document,
)


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
            generation_prompt_builder or _build_default_generation_prompt
        )
        self.incremental_system_prompt = (
            incremental_system_prompt or DEFAULT_INCREMENTAL_SYSTEM_PROMPT
        )
        self.incremental_prompt_builder = (
            incremental_prompt_builder or _build_default_incremental_prompt
        )
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
        return finalize_generated_skill(
            raw_markdown=raw,
            context_files=context_files,
        )

    def _update_skill(
        self,
        blueprint: SkillBlueprint,
        skill: SkillPlanEntry,
        existing_skill_md: str,
        changed_diffs: list[FileDiffPatch],
        previous_state: StateSnapshot | None,
    ) -> str:
        existing_document = parse_skill_document(existing_skill_md)
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
        return apply_section_updates(
            existing_document=existing_document,
            updated_sections=updated_sections,
        )

    def _load_file_context(self, relative_path: str) -> dict[str, str] | None:
        return importlib.import_module(
            ".skill_context_builder", __package__
        ).load_file_context(
            repo_path=self.repo_path,
            relative_path=relative_path,
            max_inline_chars=self.max_inline_chars,
        )

    def _build_skeleton_from_content(self, relative_path: str, content: str) -> str:
        return importlib.import_module(
            ".skill_context_builder", __package__
        ).build_skeleton_from_content(
            repo_path=self.repo_path,
            relative_path=relative_path,
            content=content,
        )[: self.max_inline_chars]


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


def _build_default_generation_prompt(
    blueprint: SkillBlueprint,
    skill: SkillPlanEntry,
    context_files: list[dict[str, str]],
    relevant_rules: list[RuleSummary],
) -> str:
    return importlib.import_module(
        ".skill_prompts", __package__
    ).build_default_generation_prompt(blueprint, skill, context_files, relevant_rules)


def _build_default_incremental_prompt(
    blueprint: SkillBlueprint,
    skill: SkillPlanEntry,
    existing_skill_md: str,
    changed_diffs: list[FileDiffPatch],
    previous_state: StateSnapshot | None,
    existing_document: ParsedSkillDocument,
) -> str:
    return importlib.import_module(
        ".skill_prompts", __package__
    ).build_default_incremental_prompt(
        blueprint,
        skill,
        existing_skill_md,
        changed_diffs,
        previous_state,
        existing_document,
    )


def _load_current_context(
    previous_state: StateSnapshot | None,
    blueprint: SkillBlueprint,
    relative_path: str,
) -> str | None:
    return importlib.import_module(
        ".skill_incremental_context", __package__
    ).load_current_context(previous_state, blueprint, relative_path)


def _load_previous_context(
    relative_path: str,
    previous_state: StateSnapshot | None,
) -> str:
    return importlib.import_module(
        ".skill_incremental_context", __package__
    ).load_previous_context(relative_path, previous_state)


def _render_config_summary(summary: ConfigSummary) -> str:
    return importlib.import_module(
        ".skill_incremental_context", __package__
    ).render_config_summary(summary)


def _render_source_summary(summary: SourceFileSummary) -> str:
    return importlib.import_module(
        ".skill_incremental_context", __package__
    ).render_source_summary(summary)


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-zA-Z0-9_/.-]+", text.lower())
        if token
    }
