from __future__ import annotations

import json
from pathlib import Path

from .models import ConfigSummary, SkillBlueprint, SourceFileSummary, StateSnapshot


def load_current_context(
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


def load_previous_context(
    relative_path: str,
    previous_state: StateSnapshot | None,
) -> str:
    if previous_state is None:
        return "[previous version unavailable]"
    record = previous_state.files.get(relative_path)
    if record is None:
        return "[previous version unavailable]"
    if record.config_summary is not None:
        return render_config_summary(record.config_summary)
    if record.source_summary is not None:
        return render_source_summary(record.source_summary)
    return "[previous version unavailable]"


def render_config_summary(summary: ConfigSummary) -> str:
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


def render_source_summary(summary: SourceFileSummary) -> str:
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
