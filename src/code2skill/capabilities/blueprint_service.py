from __future__ import annotations

from pathlib import Path

from code2skill.analyzers.project_classifier import ProjectClassifier
from code2skill.analyzers.rules_analyzer import RulesAnalyzer
from code2skill.analyzers.skill_blueprint_builder import SkillBlueprintBuilder
from code2skill.analyzers.workflow_analyzer import WorkflowAnalyzer
from code2skill.models import CachedFileRecord, FileCandidate, ImportGraphStats, SkillBlueprint


def build_blueprint(
    *,
    repo_path: Path,
    inventory,
    selected_paths: list[str],
    records: dict[str, CachedFileRecord],
    import_graph_stats: ImportGraphStats | None = None,
) -> SkillBlueprint:
    config_summaries = [
        record.config_summary
        for record in records.values()
        if record.config_summary is not None
    ]
    source_summaries = [
        record.source_summary
        for path, record in records.items()
        if path in selected_paths and record.source_summary is not None
    ]

    classifier = ProjectClassifier()
    inventory_candidates = [
        record_to_candidate(repo_path, path, record)
        for path, record in records.items()
    ]
    project_profile = classifier.classify(
        repo_path=repo_path,
        inventory_files=inventory_candidates,
        config_summaries=config_summaries,
        source_summaries=source_summaries,
    )
    domains = classifier.summarize_domains(source_summaries)
    tech_stack = classifier.build_tech_stack(project_profile, config_summaries)
    abstract_rules = RulesAnalyzer().analyze(source_summaries, config_summaries)
    concrete_workflows = WorkflowAnalyzer().analyze(source_summaries)
    return SkillBlueprintBuilder().build(
        profile=project_profile,
        tech_stack=tech_stack,
        domains=domains,
        directory_counts=inventory.directory_counts,
        config_summaries=config_summaries,
        source_summaries=source_summaries,
        abstract_rules=abstract_rules,
        concrete_workflows=concrete_workflows,
        import_graph_stats=import_graph_stats,
    )


def record_to_candidate(
    repo_path: Path,
    path: str,
    record: CachedFileRecord,
) -> FileCandidate:
    relative_path = Path(path)
    return FileCandidate(
        absolute_path=repo_path / relative_path,
        relative_path=relative_path,
        size_bytes=record.size_bytes,
        char_count=record.char_count,
        sha256=record.sha256,
        language=record.language,
        inferred_role=record.inferred_role,
        priority=record.priority,
        priority_reasons=record.priority_reasons,
        content=None,
        gitignored=record.gitignored,
    )
