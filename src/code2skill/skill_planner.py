from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from .json_utils import parse_json_object
from .llm_backend import LLMBackend
from .models import SkillBlueprint, SkillPlan, SkillPlanEntry


PlannerPromptBuilder = Callable[[SkillBlueprint, int], str]

DEFAULT_PLANNER_SYSTEM_PROMPT = (
    "You are a strict repository analyst. "
    "Plan skills only from the provided structural evidence. "
    "Do not invent modules, frameworks, languages, workflows, or future plans "
    "that are not supported by the input."
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


class SkillPlanner:
    def __init__(
        self,
        backend: LLMBackend,
        max_skills: int = 8,
        system_prompt: str | None = None,
        prompt_builder: PlannerPromptBuilder | None = None,
    ) -> None:
        self.backend = backend
        self.max_skills = max_skills
        self.system_prompt = system_prompt or DEFAULT_PLANNER_SYSTEM_PROMPT
        self.prompt_builder = prompt_builder or build_default_planner_prompt

    def plan(self, blueprint: SkillBlueprint, repo_path: Path) -> SkillPlan:
        prompt = self.prompt_builder(blueprint, self.max_skills)
        raw = self.backend.complete(prompt=prompt, system=self.system_prompt)
        payload = parse_json_object(
            raw,
            error_context="Skill planner response was not valid JSON",
            backend=self.backend,
            expected_top_level_key="skills",
            repair_hint=(
                "The output must be a JSON object with a top-level 'skills' key. "
                "Each skill must include name, title, scope, why, read_files, and read_reason."
            ),
        )

        normalized: list[SkillPlanEntry] = []
        for item in payload.get("skills", [])[: self.max_skills]:
            if not isinstance(item, dict):
                continue
            read_files = _normalize_read_files(
                item.get("read_files", []),
                repo_path=repo_path,
                limit=10,
            )
            normalized.append(
                SkillPlanEntry(
                    name=_to_kebab_case(str(item.get("name", "unnamed-skill"))),
                    title=_sanitize_plain_text(str(item.get("title", ""))) or "Untitled Skill",
                    scope=_sanitize_plain_text(str(item.get("scope", ""))),
                    why=_sanitize_plain_text(str(item.get("why", ""))),
                    read_files=read_files,
                    read_reason=_sanitize_plain_text(str(item.get("read_reason", ""))),
                )
            )

        deduped: list[SkillPlanEntry] = []
        seen: set[str] = set()
        for item in normalized:
            if not item.name or item.name in seen:
                continue
            seen.add(item.name)
            deduped.append(item)

        if not deduped:
            raise RuntimeError("Skill planner did not return any valid skills.")

        return SkillPlan(skills=deduped)


def build_default_planner_prompt(
    blueprint: SkillBlueprint,
    max_skills: int,
) -> str:
    project_profile_text = "\n".join(
        [
            f"- name: {blueprint.project_profile.name}",
            f"- repo_type: {blueprint.project_profile.repo_type}",
            f"- languages: {', '.join(blueprint.project_profile.languages) or '[not detected]'}",
            f"- framework_signals: {', '.join(blueprint.project_profile.framework_signals) or '[not detected]'}",
            f"- package_topology: {blueprint.project_profile.package_topology}",
            f"- entrypoints: {', '.join(blueprint.project_profile.entrypoints) or '[not detected]'}",
        ]
    )
    tech_stack_text = _render_tech_stack(blueprint.tech_stack)
    domains_text = "\n".join(
        [
            f"- {domain.name}: {domain.summary} | evidence={', '.join(domain.evidence[:4]) or '[none]'}"
            for domain in blueprint.domains[:8]
        ]
    ) or "[no domain summary detected]"
    directory_summary_text = "\n".join(
        [
            (
                f"- {item.path}: {item.file_count} files; "
                f"roles={', '.join(item.dominant_roles) or '[unknown]'}; "
                f"samples={', '.join(item.sample_files) or '[none]'}"
            )
            for item in blueprint.directory_summary[:16]
        ]
    ) or "[no directory summary detected]"
    key_configs_text = "\n".join(
        [
            (
                f"- {item.path} [{item.kind}] summary={item.summary}; "
                f"frameworks={', '.join(item.framework_signals[:4]) or '-'}; "
                f"entrypoints={', '.join(item.entrypoints[:4]) or '-'}"
            )
            for item in blueprint.key_configs[:10]
        ]
    ) or "[no key configuration detected]"
    core_modules_text = "\n".join(
        [
            (
                f"- {module.path} [{module.inferred_role}] "
                f"deps={', '.join(module.internal_dependencies[:4]) or '-'}; "
                f"symbols={', '.join((module.classes + module.functions)[:6]) or '-'}; "
                f"summary={module.short_doc_summary or '[none]'}"
            )
            for module in blueprint.core_modules[:16]
        ]
    ) or "[no core modules detected]"
    abstract_rules_text = "\n".join(
        [
            (
                f"- {rule.name}: {rule.rule} "
                f"(confidence={rule.confidence:.0%}; source={rule.source}; "
                f"evidence={', '.join(rule.evidence[:3]) or '[none]'})"
            )
            for rule in blueprint.abstract_rules[:12]
        ]
    ) or "[no stable rules detected]"
    workflow_text = "\n".join(
        [
            (
                f"- {workflow.name}: {workflow.summary} | "
                f"steps={'; '.join(workflow.steps[:4]) or '[none]'} | "
                f"evidence={', '.join(workflow.evidence[:4]) or '[none]'}"
            )
            for workflow in blueprint.concrete_workflows[:8]
        ]
    ) or "[no stable workflow detected]"
    import_graph_text = _render_import_graph(blueprint)
    recommended_skills_text = "\n".join(
        [
            f"- {skill.name}: {skill.scope} | evidence={', '.join(skill.source_evidence[:4]) or '[none]'}"
            for skill in blueprint.recommended_skills[:8]
        ]
    ) or "[no heuristic recommendation]"

    return f"""
You are a project analyzer. Based on the repository summary below, decide which Skill files should be generated.

Project profile:
{project_profile_text}

Tech stack:
{tech_stack_text}

Domain summary:
{domains_text}

Directory structure with file counts and role labels:
{directory_summary_text}

Key configuration:
{key_configs_text}

Dependency summary:
{import_graph_text}

High-value files:
{core_modules_text}

Detected structural patterns:
{abstract_rules_text}

Detected stable workflows:
{workflow_text}

Heuristic recommendations (low-priority reference, do not follow blindly):
{recommended_skills_text}

Hard constraints:
1. Plan skills only from evidence present in the input.
2. Do not invent missing modules, frameworks, languages, architectural layers, or future directions.
3. If evidence is weak, generate fewer skills instead of forcing coverage.
4. The skill count is usually 2-6 and must not exceed {max_skills}.
5. Each skill must focus on one clear area, not a vague broad topic.
6. Choose at most 10 read_files per skill.
7. Prefer package boundaries, directory boundaries, dependency clusters, and stable workflows over generic labels.
8. Prefer entrypoints, core models, config files, and representative service or orchestration files.
9. For similar files, choose only 1-2 representative examples instead of all of them.
10. If multiple candidate skills depend on heavily overlapping files, merge them.
11. Avoid generic skills such as "general architecture" unless the evidence clearly shows a standalone subsystem.
12. Skill names must use kebab-case.
13. scope, why, and read_reason must stay evidence-based and concrete.
14. Testing-related skills should be secondary unless the test layer is itself a major subsystem.
15. Write the output values in English.
16. Do not use emoji.

Return strict JSON:
{{
  "skills": [
    {{
      "name": "string, kebab-case filename",
      "title": "string, concise title",
      "scope": "string, scope description",
      "why": "string, why this skill is needed",
      "read_files": ["string, file path"],
      "read_reason": "string, why these files were selected"
    }}
  ]
}}
""".strip()


def load_skill_plan(path: Path) -> SkillPlan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    skills = [
        SkillPlanEntry(
            name=str(item["name"]),
            title=str(item["title"]),
            scope=str(item.get("scope", "")),
            why=str(item.get("why", "")),
            read_files=list(item.get("read_files", [])),
            read_reason=str(item.get("read_reason", "")),
        )
        for item in payload.get("skills", [])
    ]
    return SkillPlan(skills=skills)


def render_skill_plan(plan: SkillPlan) -> str:
    return json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)


def _render_tech_stack(tech_stack: dict[str, object]) -> str:
    parts: list[str] = []
    for key, value in tech_stack.items():
        if isinstance(value, list):
            display = ", ".join(str(item) for item in value) or "[empty]"
        elif isinstance(value, dict):
            display = ", ".join(
                f"{nested_key}={nested_value}"
                for nested_key, nested_value in value.items()
            ) or "[empty]"
        else:
            display = str(value)
        parts.append(f"{key}: {display}")
    return "; ".join(parts) or "[not detected]"


def _normalize_read_files(
    raw_paths: object,
    repo_path: Path,
    limit: int,
) -> list[str]:
    if not isinstance(raw_paths, list):
        return []
    normalized: list[str] = []
    for item in raw_paths:
        value = str(item).strip().replace("\\", "/").removeprefix("./")
        if not value:
            continue
        candidate = repo_path / Path(value)
        if not candidate.exists() or not candidate.is_file():
            continue
        normalized.append(Path(value).as_posix())

    deduped: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:limit]


def _to_kebab_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "unnamed-skill"


def _sanitize_plain_text(value: str) -> str:
    value = _EMOJI_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _render_import_graph(blueprint: SkillBlueprint) -> str:
    stats = blueprint.import_graph_stats
    if stats is None:
        return "[no internal dependency graph detected]"

    cluster_lines = [
        f"  - {cluster.name}: {len(cluster.files)} files; examples={', '.join(cluster.files[:4])}"
        for cluster in stats.clusters[:6]
    ]
    lines = [
        f"- hub_files: {', '.join(stats.hub_files[:8]) or '[none]'}",
        f"- entry_points: {', '.join(stats.entry_points[:8]) or '[none]'}",
        f"- total_internal_edges: {stats.total_internal_edges}",
        "- clusters:",
        *(cluster_lines or ["  - [none]"]),
    ]
    return "\n".join(lines)
