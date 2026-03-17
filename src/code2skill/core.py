from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .analyzers.project_classifier import ProjectClassifier
from .analyzers.rules_analyzer import RulesAnalyzer
from .analyzers.skill_blueprint_builder import SkillBlueprintBuilder
from .analyzers.workflow_analyzer import WorkflowAnalyzer
from .config import (
    CONFIG_FILE_GLOBS,
    DEFAULT_REPORT_FILENAME,
    HIGH_VALUE_BASENAMES,
    ScanConfig,
    matches_any_glob,
)
from .costing import CostEstimator
from .extractors.config_extractor import ConfigExtractor
from .extractors.python_extractor import PythonExtractor
from .git_client import GitClient, parse_unified_diff
from .impact import ImpactAnalyzer
from .import_graph import ImportGraph
from .models import (
    CachedFileRecord,
    ConfigSummary,
    FileDiffPatch,
    ExecutionReport,
    FileCandidate,
    ImpactSummary,
    ImportGraphCluster,
    ImportGraphStats,
    ScanExecution,
    SkillBlueprint,
    SkillImpactIndexEntry,
    SourceFileSummary,
    StateSnapshot,
)
from .renderers.json_renderer import render_skill_blueprint
from .renderers.markdown_renderer import (
    render_api_usage_reference,
    render_architecture_reference,
    render_code_style_reference,
    render_project_summary,
    render_workflows_reference,
)
from .scanner.budget import BudgetManager
from .scanner.prioritizer import FilePrioritizer
from .scanner.repository import RepositoryScanner
from .state_store import StateStore


# 这是统一入口：
# - `scan` 走全量或显式模式
# - `estimate` 只产生成本与影响报告
# - `ci` 会根据状态和 diff 自动选择 full / incremental
#
# 好处是后续如果再接 skill-creator，不需要重新发明另一套编排。
def execute_repository(config: ScanConfig) -> ScanExecution:
    """执行统一知识编译流水线，并返回完整运行结果。"""

    repo_path = config.repo_path
    output_dir = config.output_dir
    git_client = GitClient(repo_path)
    state_store = StateStore(output_dir)
    previous_state = state_store.load()
    changed_diffs = _detect_changed_diffs(config, previous_state, git_client)
    changed_files = _changed_paths_from_diffs(
        changed_diffs=changed_diffs,
        repo_path=repo_path,
        output_dir=output_dir,
    )
    effective_mode, notes = _choose_effective_mode(
        config=config,
        previous_state=previous_state,
        git_client=git_client,
        changed_files=changed_files,
    )

    inventory = RepositoryScanner(
        config=config,
        previous_files=previous_state.files if previous_state else None,
        changed_paths=set(changed_files) if effective_mode == "incremental" else None,
    ).scan()
    budget_manager = BudgetManager(config.limits)
    coarse_budget = budget_manager.select(inventory.candidates)
    coarse_selected_paths = set(_selected_path_strings(coarse_budget.selected))

    records, extra_bytes_read = _collect_records(
        all_candidates=inventory.candidates,
        selected_paths=coarse_selected_paths,
        previous_state=previous_state,
        changed_files=set(changed_files),
    )
    refined_candidates, records, import_graph, import_graph_stats = _refine_candidates(
        candidates=inventory.candidates,
        records=records,
    )
    budget = budget_manager.select(refined_candidates)
    selected_paths = _selected_path_strings(budget.selected)
    records = _update_selected_flags(records, set(selected_paths))

    impact_analyzer = ImpactAnalyzer()
    reverse_dependencies = import_graph.reverse_dependencies()
    combined_reverse_dependencies = _merge_reverse_dependencies(
        current_map=reverse_dependencies,
        previous_map=previous_state.reverse_dependencies if previous_state else {},
    )

    blueprint = _build_blueprint(
        repo_path=repo_path,
        inventory=inventory,
        selected_paths=selected_paths,
        records=records,
        import_graph_stats=import_graph_stats,
    )
    current_skill_index = impact_analyzer.build_skill_index(blueprint)
    merged_skill_index = _merge_skill_index(
        current_index=current_skill_index,
        previous_index=previous_state.skill_index if previous_state else {},
    )

    affected_files = _resolve_affected_files(
        effective_mode=effective_mode,
        selected_paths=selected_paths,
        changed_files=changed_files,
        reverse_dependencies=combined_reverse_dependencies,
        impact_analyzer=impact_analyzer,
    )
    affected_skills = _resolve_affected_skills(
        effective_mode=effective_mode,
        blueprint=blueprint,
        affected_files=affected_files,
        current_skill_index=current_skill_index,
        merged_skill_index=merged_skill_index,
        impact_analyzer=impact_analyzer,
    )

    phase1_artifacts = _render_outputs(blueprint)
    cost_estimator = CostEstimator(config.run.pricing)
    first_generation_cost = cost_estimator.estimate_first_generation(
        blueprint=blueprint,
        rendered_artifacts=phase1_artifacts,
    )
    rewrite_cost = cost_estimator.estimate_incremental_rewrite(
        blueprint=blueprint,
        rendered_artifacts=phase1_artifacts,
        affected_skills=[
            name
            for name in affected_skills
            if name in current_skill_index
        ],
        changed_files=changed_files,
        affected_files=affected_files,
    )
    patch_cost = cost_estimator.estimate_incremental_patch(rewrite_cost)

    skill_artifacts: dict[str, str] = {}
    generated_skill_names: list[str] = []
    planned_skill_names: list[str] = []
    if _should_run_skill_pipeline(config):
        (
            skill_artifacts,
            generated_skill_names,
            planned_skill_names,
        ) = _build_skill_artifacts(
            config=config,
            effective_mode=effective_mode,
            repo_path=repo_path,
            output_dir=output_dir,
            blueprint=blueprint,
            previous_state=previous_state,
            changed_files=changed_files,
            changed_diffs=changed_diffs,
            affected_files=affected_files,
            affected_skill_names=affected_skills,
        )
    rendered_artifacts = {**phase1_artifacts, **skill_artifacts}

    written_files: list[Path] = []
    updated_files: list[Path] = []
    if config.run.write_outputs:
        written_files, updated_files = _write_outputs(
            output_dir=output_dir,
            rendered_artifacts=rendered_artifacts,
        )
        if planned_skill_names:
            updated_files.extend(
                _prune_stale_skill_files(
                    output_dir=output_dir,
                    planned_skill_names=planned_skill_names,
                )
            )

    report = _build_report(
        config=config,
        effective_mode=effective_mode,
        repo_path=repo_path,
        output_dir=output_dir,
        inventory=inventory,
        budget=budget,
        changed_files=changed_files,
        affected_files=affected_files,
        affected_skills=affected_skills,
        generated_skills=generated_skill_names,
        written_files=written_files,
        updated_files=updated_files,
        head_commit=git_client.current_head() if git_client.is_repository() else None,
        bytes_read=inventory.bytes_read + extra_bytes_read,
        cost_estimator=cost_estimator,
        first_generation_cost=first_generation_cost,
        rewrite_cost=rewrite_cost,
        patch_cost=patch_cost,
        notes=notes,
    )

    report_path = _resolve_report_path(config)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if config.run.write_state:
        state_store.save(
            _build_state_snapshot(
                config=config,
                inventory=inventory,
                budget=budget,
                records=records,
                reverse_dependencies=reverse_dependencies,
                skill_index=current_skill_index,
                bytes_read=inventory.bytes_read + extra_bytes_read,
                head_commit=report.head_commit,
            )
        )

    return ScanExecution(
        repo_path=repo_path,
        output_dir=output_dir,
        output_files=sorted({*written_files, report_path}),
        candidate_count=len(inventory.candidates),
        selected_count=len(budget.selected),
        total_chars=budget.total_chars,
        blueprint=blueprint,
        run_mode=effective_mode,
        changed_files=changed_files,
        affected_files=affected_files,
        affected_skills=affected_skills,
        generated_skills=generated_skill_names,
        report_path=report_path,
        report=report,
    )


def scan_repository(config: ScanConfig) -> ScanExecution:
    """显式执行扫描命令，并确保写出产物与状态。"""

    scan_config = replace(
        config,
        run=replace(
            config.run,
            command="scan",
            mode=config.run.mode if config.run.mode != "auto" else "full",
            write_outputs=True,
            write_state=True,
        ),
    )
    return execute_repository(scan_config)


def estimate_repository(config: ScanConfig) -> ScanExecution:
    """只生成影响与成本报告，不写知识产物与状态缓存。"""

    estimate_config = replace(
        config,
        run=replace(
            config.run,
            command="estimate",
            write_outputs=False,
            write_state=False,
        ),
    )
    return execute_repository(estimate_config)


def run_ci_repository(config: ScanConfig) -> ScanExecution:
    """提供给 CI/CD 使用的统一入口。"""

    ci_config = replace(
        config,
        run=replace(
            config.run,
            command="ci",
            mode=config.run.mode or "auto",
            write_outputs=True,
            write_state=True,
        ),
    )
    return execute_repository(ci_config)


def _collect_records(
    all_candidates: Sequence[FileCandidate],
    selected_paths: set[str],
    previous_state: StateSnapshot | None,
    changed_files: set[str],
) -> tuple[dict[str, CachedFileRecord], int]:
    """为当前候选文件构建缓存记录，并尽量复用历史抽取结果。"""

    previous_files = previous_state.files if previous_state else {}
    records: dict[str, CachedFileRecord] = {}
    extra_bytes_read = 0

    config_extractor = ConfigExtractor()
    python_extractor = PythonExtractor()

    for candidate in all_candidates:
        path_key = candidate.relative_path.as_posix()
        cached = previous_files.get(path_key)
        selected = path_key in selected_paths
        if _can_reuse_record(
            candidate=candidate,
            cached=cached,
            changed_files=changed_files,
        ):
            records[path_key] = replace(cached, selected=selected)
            continue

        hydrated_candidate, bytes_read = _hydrate_candidate(candidate)
        extra_bytes_read += bytes_read
        config_summary, source_summary = _extract_candidate_summaries(
            candidate=hydrated_candidate,
            config_extractor=config_extractor,
            python_extractor=python_extractor,
        )
        records[path_key] = _record_from_candidate(
            candidate=hydrated_candidate,
            selected=selected,
            config_summary=config_summary,
            source_summary=source_summary,
        )

    return records, extra_bytes_read


def _extract_candidate_summaries(
    candidate: FileCandidate,
    config_extractor: ConfigExtractor,
    python_extractor: PythonExtractor,
) -> tuple[ConfigSummary | None, SourceFileSummary | None]:
    """按语言分派抽取器，返回配置摘要与源码骨架摘要。"""

    config_summary = config_extractor.extract(candidate)
    if candidate.language == "python":
        return config_summary, python_extractor.extract(candidate)
    return config_summary, None


def _build_blueprint(
    repo_path: Path,
    inventory,
    selected_paths: list[str],
    records: dict[str, CachedFileRecord],
    import_graph_stats: ImportGraphStats | None = None,
) -> SkillBlueprint:
    """把缓存记录重组成最终的 skill blueprint。"""

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
    source_summaries = [item for item in source_summaries if item is not None]
    config_summaries = [item for item in config_summaries if item is not None]

    classifier = ProjectClassifier()
    inventory_candidates = [
        _record_to_candidate(repo_path=repo_path, path=path, record=record)
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


def _record_to_candidate(
    repo_path: Path,
    path: str,
    record: CachedFileRecord,
) -> FileCandidate:
    """把缓存记录恢复成轻量候选对象，供分类阶段复用。"""

    from .models import FileCandidate

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


def _record_from_candidate(
    candidate: FileCandidate,
    selected: bool,
    config_summary: ConfigSummary | None,
    source_summary: SourceFileSummary | None,
) -> CachedFileRecord:
    """把候选文件与抽取结果压缩成可持久化的缓存记录。"""

    return CachedFileRecord(
        path=candidate.relative_path.as_posix(),
        sha256=candidate.sha256,
        size_bytes=candidate.size_bytes,
        char_count=candidate.char_count,
        language=candidate.language,
        inferred_role=candidate.inferred_role,
        priority=candidate.priority,
        priority_reasons=candidate.priority_reasons,
        gitignored=candidate.gitignored,
        selected=selected,
        config_summary=config_summary,
        source_summary=source_summary,
    )


def _refine_candidates(
    candidates: Sequence[FileCandidate],
    records: dict[str, CachedFileRecord],
) -> tuple[list[FileCandidate], dict[str, CachedFileRecord], ImportGraph, ImportGraphStats]:
    import_graph = _build_import_graph(records)
    pagerank = import_graph.get_pagerank()
    hub_files = set(import_graph.get_hub_files(top_n=20))
    entry_points = set(import_graph.get_entry_points())
    prioritizer = FilePrioritizer()

    refined_candidates: list[FileCandidate] = []
    refined_records: dict[str, CachedFileRecord] = {}
    for candidate in candidates:
        path_key = candidate.relative_path.as_posix()
        record = records[path_key]
        summary = record.source_summary
        refined_score, refined_reasons, refined_role = prioritizer.refine(
            relative_path=candidate.relative_path,
            language=candidate.language,
            current_score=candidate.priority,
            current_role=candidate.inferred_role,
            current_reasons=candidate.priority_reasons,
            summary=summary,
            in_degree=import_graph.get_in_degree(path_key),
            out_degree=import_graph.get_out_degree(path_key),
            pagerank_score=pagerank.get(path_key, 0.0),
            is_entry_point=path_key in entry_points,
            is_hub=path_key in hub_files,
        )
        refined_summary = summary
        if summary is not None:
            refined_summary = replace(
                summary,
                inferred_role=refined_role,
                internal_dependencies=import_graph.internal_dependencies_for(path_key),
            )
        refined_candidates.append(
            replace(
                candidate,
                inferred_role=refined_role,
                priority=refined_score,
                priority_reasons=refined_reasons,
            )
        )
        refined_records[path_key] = replace(
            record,
            inferred_role=refined_role,
            priority=refined_score,
            priority_reasons=refined_reasons,
            source_summary=refined_summary,
        )

    return refined_candidates, refined_records, import_graph, _build_import_graph_stats(import_graph)


def _build_import_graph(records: dict[str, CachedFileRecord]) -> ImportGraph:
    import_graph = ImportGraph()
    import_graph.build(
        {
            path: record.source_summary
            for path, record in records.items()
            if record.source_summary is not None
        }
    )
    return import_graph


def _build_import_graph_stats(import_graph: ImportGraph) -> ImportGraphStats:
    clusters = [
        ImportGraphCluster(
            name=_derive_cluster_name(files, index),
            files=files,
        )
        for index, files in enumerate(import_graph.get_clusters(), start=1)
    ]
    return ImportGraphStats(
        total_internal_edges=import_graph.total_internal_edges(),
        hub_files=import_graph.get_hub_files(top_n=20),
        entry_points=import_graph.get_entry_points(),
        cluster_count=len(clusters),
        clusters=clusters,
    )


def _derive_cluster_name(files: list[str], index: int) -> str:
    if not files:
        return f"cluster-{index}"

    split_parents = [path.split("/")[:-1] for path in files]
    common_parts: list[str] = []
    for parts in zip(*split_parents):
        if len(set(parts)) != 1:
            break
        common_parts.append(parts[0])
    if common_parts:
        return "/".join(common_parts)

    parent_counts = Counter(
        "/".join(path.split("/")[:-1]) or "."
        for path in files
    )
    top_parent, _ = parent_counts.most_common(1)[0]
    if top_parent != ".":
        return top_parent
    return f"cluster-{index}"


def _update_selected_flags(
    records: dict[str, CachedFileRecord],
    selected_paths: set[str],
) -> dict[str, CachedFileRecord]:
    return {
        path: replace(record, selected=path in selected_paths)
        for path, record in records.items()
    }


def _can_reuse_record(
    candidate: FileCandidate,
    cached: CachedFileRecord | None,
    changed_files: set[str],
) -> bool:
    """判断入选文件是否可以直接复用历史抽取结果。"""

    if cached is None:
        return False
    path_key = candidate.relative_path.as_posix()
    if path_key in changed_files:
        return False
    return cached.config_summary is not None or cached.source_summary is not None


def _hydrate_candidate(candidate: FileCandidate) -> tuple[FileCandidate, int]:
    """在需要时补读文件正文，避免无意义的重复 IO。"""

    if candidate.content is not None:
        return candidate, 0
    data = candidate.absolute_path.read_bytes()
    return replace(
        candidate,
        content=data.decode("utf-8", errors="ignore"),
        size_bytes=len(data),
    ), len(data)


def _detect_changed_diffs(
    config: ScanConfig,
    previous_state: StateSnapshot | None,
    git_client: GitClient,
) -> list[FileDiffPatch]:
    """根据 diff 文件、base ref 或上次状态，找出本次运行的变化补丁。"""

    if config.run.diff_file is not None:
        raw = config.run.diff_file.read_text(encoding="utf-8")
        parsed = parse_unified_diff(raw)
        if raw.strip() and not parsed:
            raise RuntimeError(
                f"Could not parse any file patches from diff file: {config.run.diff_file}"
            )
        return parsed
    if not git_client.is_repository():
        return []
    if config.run.base_ref:
        return git_client.diff_patches(
            base_ref=config.run.base_ref,
            head_ref=config.run.head_ref,
            merge_base=True,
        )
    if previous_state and previous_state.head_commit:
        return git_client.changed_patches_from_worktree(
            previous_state.head_commit,
        )
    return []


def _changed_paths_from_diffs(
    changed_diffs: list[FileDiffPatch],
    repo_path: Path,
    output_dir: Path,
) -> list[str]:
    return sorted(
        {
            item.path
            for item in changed_diffs
            if item.path
            and not _is_generated_artifact_path(
                path=item.path,
                repo_path=repo_path,
                output_dir=output_dir,
            )
        }
    )


def _is_generated_artifact_path(
    path: str,
    repo_path: Path,
    output_dir: Path,
) -> bool:
    normalized = Path(path).as_posix()
    first_part = normalized.split("/", 1)[0]
    if first_part.startswith(".code2skill"):
        return True
    if normalized in {"AGENTS.md", "CLAUDE.md", ".windsurfrules"}:
        return True
    if normalized == ".github/copilot-instructions.md":
        return True
    if normalized == ".cursor/rules" or normalized.startswith(".cursor/rules/"):
        return True

    try:
        relative_output_dir = output_dir.relative_to(repo_path).as_posix()
    except ValueError:
        return False

    return (
        normalized == relative_output_dir
        or normalized.startswith(f"{relative_output_dir}/")
    )


def _choose_effective_mode(
    config: ScanConfig,
    previous_state: StateSnapshot | None,
    git_client: GitClient,
    changed_files: list[str],
) -> tuple[str, list[str]]:
    """根据运行参数、git 状态和历史缓存选择 full 或 incremental。"""

    notes: list[str] = []
    requested_mode = config.run.mode
    if requested_mode == "full":
        return "full", notes
    if config.run.diff_file is None and not git_client.is_repository():
        notes.append("当前目录不是 git 仓库，自动回退到全量模式。")
        return "full", notes
    if previous_state is None:
        notes.append("未发现历史状态缓存，自动执行首次全量构建。")
        return "full", notes
    if requested_mode == "incremental" and not changed_files:
        notes.append("未检测到代码变化，将复用缓存并快速重建产物。")
        return "incremental", notes
    if requested_mode in {"incremental", "auto"}:
        if (
            config.run.force_full_on_config_change
            and any(_is_full_rebuild_trigger(path) for path in changed_files)
        ):
            notes.append("检测到核心配置变化，自动回退到全量模式。")
            return "full", notes
        if len(changed_files) > config.run.max_incremental_changed_files:
            notes.append("变更文件过多，自动回退到全量模式。")
            return "full", notes
        return "incremental", notes
    return "full", notes


def _is_full_rebuild_trigger(path: str) -> bool:
    """判断某个变更是否足以触发整仓重编译。"""

    relative_path = Path(path)
    if relative_path.name in {
        "pyproject.toml",
        "requirements.txt",
        "Dockerfile",
    }:
        return True
    if matches_any_glob(relative_path, CONFIG_FILE_GLOBS):
        return True
    return relative_path.name in HIGH_VALUE_BASENAMES and len(relative_path.parts) == 1


def _resolve_affected_files(
    effective_mode: str,
    selected_paths: list[str],
    changed_files: list[str],
    reverse_dependencies: dict[str, list[str]],
    impact_analyzer: ImpactAnalyzer,
) -> list[str]:
    """把直接改动扩展成需要重新评估的文件集合。"""

    if effective_mode == "full":
        return sorted(selected_paths)
    return impact_analyzer.expand_affected_files(
        changed_files=changed_files,
        reverse_dependencies=reverse_dependencies,
    )


def _resolve_affected_skills(
    effective_mode: str,
    blueprint: SkillBlueprint,
    affected_files: list[str],
    current_skill_index: dict[str, SkillImpactIndexEntry],
    merged_skill_index: dict[str, SkillImpactIndexEntry],
    impact_analyzer: ImpactAnalyzer,
) -> list[str]:
    """把受影响文件映射到需要重算的推荐 skill。"""

    if effective_mode == "full":
        return [skill.name for skill in blueprint.recommended_skills]
    return impact_analyzer.match_affected_skills(
        affected_files=affected_files,
        skill_index=merged_skill_index,
    )


def _merge_reverse_dependencies(
    current_map: dict[str, list[str]],
    previous_map: dict[str, list[str]],
) -> dict[str, list[str]]:
    """合并新旧反向依赖图，保留删除文件的历史影响信息。"""

    merged: dict[str, set[str]] = {}
    for path, importers in previous_map.items():
        merged.setdefault(path, set()).update(importers)
    for path, importers in current_map.items():
        merged.setdefault(path, set()).update(importers)
    return {
        path: sorted(importers)
        for path, importers in merged.items()
    }


def _merge_skill_index(
    current_index: dict[str, SkillImpactIndexEntry],
    previous_index: dict[str, SkillImpactIndexEntry],
) -> dict[str, SkillImpactIndexEntry]:
    """合并新旧 skill 索引，保证删除文件时仍能定位旧 skill。"""

    merged = dict(previous_index)
    merged.update(current_index)
    return merged


def _render_outputs(blueprint: SkillBlueprint) -> dict[str, str]:
    """渲染所有对人和对机器可消费的中间产物。"""

    return {
        "project-summary.md": render_project_summary(blueprint),
        "skill-blueprint.json": render_skill_blueprint(blueprint),
        "references/architecture.md": render_architecture_reference(blueprint),
        "references/code-style.md": render_code_style_reference(blueprint),
        "references/workflows.md": render_workflows_reference(blueprint),
        "references/api-usage.md": render_api_usage_reference(blueprint),
    }


def _should_run_skill_pipeline(config: ScanConfig) -> bool:
    return (
        config.run.write_outputs
        and config.run.command in {"scan", "ci"}
        and not config.run.structure_only
    )


def _build_skill_artifacts(
    config: ScanConfig,
    effective_mode: str,
    repo_path: Path,
    output_dir: Path,
    blueprint: SkillBlueprint,
    previous_state: StateSnapshot | None,
    changed_files: list[str],
    changed_diffs: list[FileDiffPatch],
    affected_files: list[str],
    affected_skill_names: list[str],
) -> tuple[dict[str, str], list[str], list[str]]:
    from .skill_generator import SkillGenerator, match_planned_skills
    from .skill_planner import SkillPlanner, load_skill_plan, render_skill_plan

    backend = build_llm_backend(
        provider=config.run.llm_provider,
        model=config.run.llm_model,
    )
    planner = SkillPlanner(
        backend=backend,
        max_skills=config.run.max_skills,
    )
    generator = SkillGenerator(
        backend=backend,
        repo_path=repo_path,
        output_dir=output_dir,
        max_inline_chars=config.limits.max_file_size_kb * 1024,
    )
    plan_path = output_dir / "skill-plan.json"
    needs_full_generation = (
        config.run.command == "scan"
        or effective_mode == "full"
        or not plan_path.exists()
    )

    if needs_full_generation:
        plan = planner.plan(blueprint=blueprint, repo_path=repo_path)
        artifacts = {
            "skill-plan.json": render_skill_plan(plan),
        }
        artifacts.update(generator.generate_all(blueprint=blueprint, plan=plan))
        planned_names = [skill.name for skill in plan.skills]
        return artifacts, planned_names, planned_names

    try:
        plan = load_skill_plan(plan_path)
    except Exception:
        plan = planner.plan(blueprint=blueprint, repo_path=repo_path)
        artifacts = {
            "skill-plan.json": render_skill_plan(plan),
        }
        artifacts.update(generator.generate_all(blueprint=blueprint, plan=plan))
        planned_names = [skill.name for skill in plan.skills]
        return artifacts, planned_names, planned_names

    artifacts: dict[str, str] = {}
    plan_skill_names = {skill.name for skill in plan.skills}
    planned_names = [skill.name for skill in plan.skills]
    present_skills = [
        name for name in affected_skill_names
        if name in plan_skill_names
    ]
    missing_skills = [
        name for name in affected_skill_names
        if name not in plan_skill_names
    ]
    if present_skills:
        affected_skill_names = present_skills
    elif missing_skills:
        plan = planner.plan(blueprint=blueprint, repo_path=repo_path)
        artifacts["skill-plan.json"] = render_skill_plan(plan)
        plan_skill_names = {skill.name for skill in plan.skills}
        planned_names = [skill.name for skill in plan.skills]
        affected_skill_names = match_planned_skills(affected_files, plan)
        artifacts.update(generator.generate_all(blueprint=blueprint, plan=plan))
        return artifacts, planned_names, planned_names

    if not affected_skill_names:
        return artifacts, [], planned_names

    artifacts.update(
        generator.generate_incremental(
            blueprint=blueprint,
            plan=plan,
            affected_skill_names=affected_skill_names,
            changed_files=changed_files,
            changed_diffs=changed_diffs,
            previous_state=previous_state,
        )
    )
    return artifacts, affected_skill_names, planned_names


def build_llm_backend(provider: str, model: str | None = None):
    from .llm_backend import build_llm_backend as _build_llm_backend

    return _build_llm_backend(provider=provider, model=model)


def _write_outputs(
    output_dir: Path,
    rendered_artifacts: dict[str, str],
) -> tuple[list[Path], list[Path]]:
    """把渲染结果写到磁盘，并区分“存在”和“实际更新”的文件。"""

    written_files: list[Path] = []
    updated_files: list[Path] = []
    for relative_path, content in rendered_artifacts.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        written_files.append(path)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        updated_files.append(path)
    return written_files, updated_files


def _prune_stale_skill_files(
    output_dir: Path,
    planned_skill_names: list[str],
) -> list[Path]:
    skills_dir = output_dir / "skills"
    if not skills_dir.exists():
        return []

    keep = {f"{name}.md" for name in planned_skill_names}
    keep.add("index.md")
    removed: list[Path] = []
    for path in skills_dir.glob("*.md"):
        if path.name in keep:
            continue
        path.unlink(missing_ok=True)
        removed.append(path)
    return removed


def _build_report(
    config: ScanConfig,
    effective_mode: str,
    repo_path: Path,
    output_dir: Path,
    inventory,
    budget,
    changed_files: list[str],
    affected_files: list[str],
    affected_skills: list[str],
    generated_skills: list[str],
    written_files: list[Path],
    updated_files: list[Path],
    head_commit: str | None,
    bytes_read: int,
    cost_estimator: CostEstimator,
    first_generation_cost,
    rewrite_cost,
    patch_cost,
    notes: list[str],
) -> ExecutionReport:
    """把本次执行压缩成机器可读的报告对象。"""

    return ExecutionReport(
        generated_at=_now_iso(),
        command=config.run.command,
        requested_mode=config.run.mode,
        effective_mode=effective_mode,
        repo_path=str(repo_path),
        output_dir=str(output_dir),
        base_ref=config.run.base_ref,
        head_ref=config.run.head_ref,
        head_commit=head_commit,
        discovery_method=inventory.discovery_method,
        candidate_count=len(inventory.candidates),
        selected_count=len(budget.selected),
        total_chars=budget.total_chars,
        bytes_read=bytes_read,
        written_files=[str(path) for path in written_files],
        updated_files=[str(path) for path in updated_files],
        impact=ImpactSummary(
            changed_files=changed_files,
            affected_files=affected_files,
            affected_skills=affected_skills,
            generated_skills=generated_skills,
        ),
        first_generation_cost=first_generation_cost,
        incremental_rewrite_cost=rewrite_cost,
        incremental_patch_cost=patch_cost,
        pricing=cost_estimator.pricing_dict(),
        notes=notes,
    )


def _build_state_snapshot(
    config: ScanConfig,
    inventory,
    budget,
    records: dict[str, CachedFileRecord],
    reverse_dependencies: dict[str, list[str]],
    skill_index: dict[str, SkillImpactIndexEntry],
    bytes_read: int,
    head_commit: str | None,
) -> StateSnapshot:
    """构建增量运行所需的状态快照。"""

    return StateSnapshot(
        version=1,
        generated_at=_now_iso(),
        repo_root=str(config.repo_path),
        head_commit=head_commit,
        selected_paths=[
            candidate.relative_path.as_posix()
            for candidate in budget.selected
        ],
        directory_counts=inventory.directory_counts,
        gitignore_patterns=inventory.gitignore_patterns,
        discovery_method=inventory.discovery_method,
        candidate_count=len(inventory.candidates),
        total_chars=budget.total_chars,
        bytes_read=bytes_read,
        files=records,
        reverse_dependencies=reverse_dependencies,
        skill_index=skill_index,
    )


def _resolve_report_path(config: ScanConfig) -> Path:
    """统一解析报告输出路径。"""

    if config.run.report_path is not None:
        return config.run.report_path
    return config.output_dir / DEFAULT_REPORT_FILENAME


def _selected_path_strings(selected_candidates: Sequence[FileCandidate]) -> list[str]:
    """把入选候选文件转换成稳定的相对路径字符串。"""

    return [
        candidate.relative_path.as_posix()
        for candidate in selected_candidates
    ]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
