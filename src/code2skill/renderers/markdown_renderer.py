from __future__ import annotations

from ..models import SkillBlueprint


def render_adoption_guide(blueprint: SkillBlueprint) -> str:
    profile = blueprint.project_profile
    lines = [
        "# Adoption Guide",
        "",
        "## Repository Scenario",
        (
            f"This repository is classified as a `{profile.repo_type}` Python project. "
            "Use the generated Skill layer as the project instruction source for "
            "local coding assistants, IDE rules, and CI checks."
        ),
        "",
        "## Intended Users",
        "- Repository maintainers who want assistants to follow current project boundaries.",
        "- DevEx or platform owners standardizing coding-tool instructions across a team.",
        "- Teams that want project instructions stored as files instead of chat context.",
        "",
        "## First Adoption Workflow",
        "1. Run `code2skill estimate .` to preview selected files, impact, and generation cost.",
        "2. Run `code2skill scan . --llm <provider> --model <model>` to generate Skills.",
        "3. Review `.code2skill/skills/index.md` and `.code2skill/skills/*.md`.",
        "4. Run `code2skill adapt . --target codex` or `--target all` to publish tool-specific files.",
        "5. Run `code2skill doctor . --target codex` to confirm the bundle is ready to use.",
        "",
        "## What To Review",
        "- `.code2skill/adoption-guide.md`: this adoption checklist.",
        "- `.code2skill/project-summary.md`: human-readable repository summary.",
        "- `.code2skill/skills/index.md` and `.code2skill/skills/*.md`: generated Skill files.",
        "- `.code2skill/report.json`: selected files, mode decisions, costs, and affected Skills.",
        "- Adapted target files such as `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, `.github/copilot-instructions.md`, and `.windsurfrules`.",
        "",
        "## Repository Signals",
        f"- name: {profile.name}",
        f"- repo_type: {profile.repo_type}",
        f"- package_topology: {profile.package_topology}",
        f"- languages: {', '.join(profile.languages) or 'unknown'}",
        f"- entrypoints: {', '.join(profile.entrypoints[:8]) or 'none detected'}",
        "",
        "## Recommended Skill Products",
    ]
    if blueprint.recommended_skills:
        for skill in blueprint.recommended_skills:
            lines.append(f"- `{skill.name}`: {skill.purpose}")
    else:
        lines.append("- No recommended Skills were inferred during structural analysis.")
    lines.extend(
        [
            "",
            "## CI Maintenance",
            "Use `code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD` after the first committed bundle. Cache `.code2skill/` so later CI runs can reuse `state/analysis-state.json` and regenerate only affected Skills.",
            "",
            "## Readiness Check",
            "Run `code2skill doctor . --target codex` before committing or from CI to verify that the artifact bundle, generated Skills, incremental state, and adapted target file are present.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_project_summary(blueprint: SkillBlueprint) -> str:
    profile = blueprint.project_profile
    lines = [
        "# Project Summary",
        "",
        "## Repo Profile",
        f"- name: {profile.name}",
        f"- repo_type: {profile.repo_type}",
        f"- package_topology: {profile.package_topology}",
        f"- languages: {', '.join(profile.languages) or 'unknown'}",
        f"- framework_signals: {', '.join(profile.framework_signals) or 'none'}",
        "",
        "## Entrypoints",
    ]
    entrypoints = profile.entrypoints[:10]
    if entrypoints:
        lines.extend(f"- {entrypoint}" for entrypoint in entrypoints)
    else:
        lines.append("- none detected")
    lines.extend(
        [
            "",
            "## Directory Summary",
        ]
    )
    for item in blueprint.directory_summary:
        sample_files = ", ".join(item.sample_files) or "n/a"
        lines.append(
            f"- {item.path}: {item.file_count} files; dominant roles = {', '.join(item.dominant_roles) or 'n/a'}; "
            f"samples = {sample_files}"
        )
    lines.extend(
        [
            "",
            "## Core Modules",
        ]
    )
    lines.extend(
        (
            f"- {module.path}: {module.inferred_role}; {module.short_doc_summary}; "
            f"calls={', '.join(module.call_targets[:5]) or '-'}; "
            f"types={', '.join(module.type_references[:5]) or '-'}"
        )
        for module in blueprint.core_modules
    )
    lines.extend(
        [
            "",
            "## Import Graph",
        ]
    )
    if blueprint.import_graph_stats is not None:
        lines.extend(
            [
                f"- total_internal_edges: {blueprint.import_graph_stats.total_internal_edges}",
                f"- hub_files: {', '.join(blueprint.import_graph_stats.hub_files) or 'none'}",
                f"- entry_points: {', '.join(blueprint.import_graph_stats.entry_points) or 'none'}",
                f"- cluster_count: {blueprint.import_graph_stats.cluster_count}",
            ]
        )
        for cluster in blueprint.import_graph_stats.clusters[:6]:
            lines.append(
                f"- cluster {cluster.name}: {', '.join(cluster.files[:4])}"
            )
    else:
        lines.append("- not available")
    lines.extend(
        [
            "",
            "## Architecture Observations",
        ]
    )
    if blueprint.abstract_rules:
        for rule in blueprint.abstract_rules:
            lines.append(
                f"- {_confidence_badge(rule.confidence)} {rule.rule} "
                f"(source={rule.source}, confidence={rule.confidence:.0%})"
            )
    else:
        lines.append("- No stable architecture rules were inferred.")
    lines.extend(
        [
            "",
            "## Workflow Observations",
        ]
    )
    if blueprint.concrete_workflows:
        lines.extend(f"- {workflow.summary}" for workflow in blueprint.concrete_workflows)
    else:
        lines.append("- No concrete workflows were inferred.")
    return "\n".join(lines) + "\n"


def render_architecture_reference(blueprint: SkillBlueprint) -> str:
    lines = [
        "# Architecture Reference",
        "",
        "## Abstract Rules",
    ]
    for rule in blueprint.abstract_rules:
        lines.append(f"### {rule.name}")
        lines.append(f"{_confidence_badge(rule.confidence)} {rule.rule}")
        lines.append("")
        lines.append(f"Source: {rule.source}")
        lines.append(f"Confidence: {rule.confidence:.0%}")
        lines.append(f"Rationale: {rule.rationale}")
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {evidence}" for evidence in rule.evidence)
        if rule.example_snippet:
            lines.append("")
            lines.append("Example:")
            lines.append("```text")
            lines.append(rule.example_snippet)
            lines.append("```")
        lines.append("")
    if len(lines) == 3:
        lines.append("No architecture rules were inferred.")
    return "\n".join(lines).rstrip() + "\n"


def render_code_style_reference(blueprint: SkillBlueprint) -> str:
    lines = [
        "# Code Style Reference",
        "",
        "## Style and Naming Signals",
    ]
    for rule in blueprint.abstract_rules:
        if "naming" in rule.name or "config" in rule.name or "testing" in rule.name:
            lines.append(
                f"- {_confidence_badge(rule.confidence)} {rule.rule} "
                f"(source={rule.source}, confidence={rule.confidence:.0%}) "
                f"Evidence: {', '.join(rule.evidence) or 'none'}"
            )
    if len(lines) == 3:
        lines.append("- No strong style signals were detected.")
    return "\n".join(lines) + "\n"


def render_workflows_reference(blueprint: SkillBlueprint) -> str:
    lines = [
        "# Workflow Reference",
        "",
    ]
    for workflow in blueprint.concrete_workflows:
        lines.append(f"## {workflow.name}")
        lines.append(workflow.summary)
        lines.append("")
        lines.append("Steps:")
        lines.extend(f"- {step}" for step in workflow.steps)
        lines.append("")
        lines.append("Evidence:")
        lines.extend(f"- {item}" for item in workflow.evidence)
        lines.append("")
    if not blueprint.concrete_workflows:
        lines.append("No concrete workflows were detected.")
    return "\n".join(lines).rstrip() + "\n"


def render_api_usage_reference(blueprint: SkillBlueprint) -> str:
    lines = [
        "# API Usage Reference",
        "",
        "## Important APIs and Entry Points",
    ]
    for api in blueprint.important_apis:
        detail = f" ({api.details})" if api.details else ""
        lines.append(f"- {api.kind}: {api.name} in {api.source}{detail}")
    if len(lines) == 3:
        lines.append("- No API-style entry points were detected.")
    return "\n".join(lines) + "\n"


def _confidence_badge(confidence: float) -> str:
    if confidence >= 0.75:
        return "[high]"
    if confidence >= 0.5:
        return "[medium]"
    return "[low]"
