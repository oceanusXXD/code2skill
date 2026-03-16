from __future__ import annotations

from ..models import SkillBlueprint


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
        f"- {module.path}: {module.inferred_role}; {module.short_doc_summary}"
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
