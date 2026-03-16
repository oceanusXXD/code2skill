from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ..models import (
    ApiSummary,
    ConfigSummary,
    DirectorySummary,
    DomainSummary,
    ImportGraphStats,
    ProjectProfile,
    RuleSummary,
    SkillBlueprint,
    SkillRecommendation,
    SourceFileSummary,
    WorkflowSummary,
)


class SkillBlueprintBuilder:
    """把分类、规则、流程等结果装配成统一 blueprint。"""

    def build(
        self,
        profile: ProjectProfile,
        tech_stack: dict[str, object],
        domains: list[DomainSummary],
        directory_counts: dict[str, int],
        config_summaries: list[ConfigSummary],
        source_summaries: list[SourceFileSummary],
        abstract_rules: list[RuleSummary],
        concrete_workflows: list[WorkflowSummary],
        import_graph_stats: ImportGraphStats | None = None,
    ) -> SkillBlueprint:
        """构建 skill-blueprint.json 对应的数据对象。"""

        directory_summary = self._build_directory_summary(
            directory_counts,
            config_summaries,
            source_summaries,
        )
        core_modules = self._build_core_modules(
            profile=profile,
            source_summaries=source_summaries,
            concrete_workflows=concrete_workflows,
            import_graph_stats=import_graph_stats,
        )
        important_apis = self._build_important_apis(source_summaries)
        recommended_skills = self._recommend_skills(
            profile,
            domains,
            concrete_workflows,
            source_summaries,
        )

        return SkillBlueprint(
            project_profile=profile,
            tech_stack=tech_stack,
            domains=domains,
            directory_summary=directory_summary,
            key_configs=config_summaries[:12],
            core_modules=core_modules,
            important_apis=important_apis,
            abstract_rules=abstract_rules,
            concrete_workflows=concrete_workflows,
            recommended_skills=recommended_skills,
            import_graph_stats=import_graph_stats,
        )

    def _build_directory_summary(
        self,
        directory_counts: dict[str, int],
        config_summaries: list[ConfigSummary],
        source_summaries: list[SourceFileSummary],
    ) -> list[DirectorySummary]:
        """生成目录级摘要，用于概览仓库骨架。"""

        roles_by_directory: dict[str, Counter[str]] = defaultdict(Counter)
        sample_files_by_directory: dict[str, list[str]] = defaultdict(list)
        for summary in source_summaries:
            directory = _directory_key(summary.path)
            roles_by_directory[directory][summary.inferred_role] += 1
            _append_sample(sample_files_by_directory[directory], summary.path)

        for summary in config_summaries:
            directory = _directory_key(summary.path)
            roles_by_directory[directory]["config"] += 1
            _append_sample(sample_files_by_directory[directory], summary.path)

        result: list[DirectorySummary] = []
        for directory, file_count in sorted(
            directory_counts.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            dominant_roles = [
                role
                for role, _ in roles_by_directory.get(
                    directory,
                    Counter(),
                ).most_common(3)
            ]
            result.append(
                DirectorySummary(
                    path=directory,
                    file_count=file_count,
                    dominant_roles=dominant_roles,
                    sample_files=sample_files_by_directory.get(directory, [])[:3],
                )
            )
        return result[:16]

    def _build_core_modules(
        self,
        profile: ProjectProfile,
        source_summaries: list[SourceFileSummary],
        concrete_workflows: list[WorkflowSummary],
        import_graph_stats: ImportGraphStats | None,
    ) -> list[SourceFileSummary]:
        summary_by_path = {
            summary.path: summary
            for summary in source_summaries
        }
        selected: list[SourceFileSummary] = []
        seen: set[str] = set()

        def add(path: str) -> None:
            summary = summary_by_path.get(path)
            if summary is None or path in seen:
                return
            seen.add(path)
            selected.append(summary)

        for path in profile.entrypoints:
            add(path)

        if import_graph_stats is not None:
            for path in import_graph_stats.hub_files[:8]:
                add(path)
            for cluster in import_graph_stats.clusters[:6]:
                representative = self._select_cluster_representative(
                    cluster.files,
                    summary_by_path,
                )
                if representative is not None:
                    add(representative)

        for workflow in concrete_workflows[:6]:
            for path in workflow.evidence[:3]:
                add(path)

        roles = ("entrypoint", "route", "service", "model", "source", "utility")
        for role in roles:
            role_matches = sorted(
                (
                    summary
                    for summary in source_summaries
                    if summary.inferred_role == role
                ),
                key=_core_module_sort_key,
            )
            for summary in role_matches[:2]:
                add(summary.path)

        fallback = sorted(source_summaries, key=_core_module_sort_key)
        for summary in fallback:
            add(summary.path)

        return selected[:16]

    def _select_cluster_representative(
        self,
        cluster_files: list[str],
        summary_by_path: dict[str, SourceFileSummary],
    ) -> str | None:
        candidates = [
            summary_by_path[path]
            for path in cluster_files
            if path in summary_by_path
        ]
        if not candidates:
            return None
        candidates.sort(key=_core_module_sort_key)
        return candidates[0].path

    def _build_important_apis(
        self,
        source_summaries: list[SourceFileSummary],
    ) -> list[ApiSummary]:
        """从路由和服务模块中抽取 API 级摘要。"""

        apis: list[ApiSummary] = []
        for summary in source_summaries:
            for route in summary.routes:
                apis.append(
                    ApiSummary(
                        kind="route",
                        name=f"{route.method} {route.path}",
                        source=summary.path,
                        details=route.handler,
                    )
                )
            if summary.inferred_role == "service":
                for function_name in summary.functions[:3]:
                    apis.append(
                        ApiSummary(
                            kind=summary.inferred_role,
                            name=function_name,
                            source=summary.path,
                            details=summary.short_doc_summary,
                        )
                    )
        return apis[:16]

    def _recommend_skills(
        self,
        profile: ProjectProfile,
        domains: list[DomainSummary],
        workflows: list[WorkflowSummary],
        source_summaries: list[SourceFileSummary],
    ) -> list[SkillRecommendation]:
        """根据领域与流程，为后续 skill-creator 提供拆分建议。"""

        recommendations: list[SkillRecommendation] = [
            SkillRecommendation(
                name="project-overview",
                purpose="Capture the repository topology, stack, and stable architectural boundaries.",
                scope="Cross-cutting orientation for the full project.",
                source_evidence=profile.evidence[:6],
                why_split="This stable context is reusable across every narrower skill.",
                likely_inputs=["architecture questions", "new contributor onboarding", "feature scoping"],
                likely_outputs=["module selection guidance", "touch-point hints", "boundary reminders"],
            )
        ]

        domain_names = {domain.name for domain in domains}
        if "backend" in domain_names:
            recommendations.append(
                SkillRecommendation(
                    name="backend-architecture",
                    purpose="Explain how routes, services, models, and validation layers fit together.",
                    scope="Server-side request handling and data boundaries.",
                    source_evidence=_evidence_for_roles(
                        source_summaries,
                        {"route", "service", "model"},
                    ),
                    why_split="Backend behavior has its own layering, contracts, and testing patterns.",
                    likely_inputs=["API changes", "service logic changes", "model updates"],
                    likely_outputs=["route-to-service traces", "required backend file edits", "data-layer guidance"],
                )
            )

        for workflow in workflows:
            recommendations.append(
                SkillRecommendation(
                    name=workflow.name,
                    purpose=f"Operationalize the observed {workflow.name} workflow.",
                    scope=workflow.summary,
                    source_evidence=workflow.evidence[:6],
                    why_split="Concrete workflows are easier to execute when stored separately from abstract architecture rules.",
                    likely_inputs=[workflow.name, "task-specific implementation questions"],
                    likely_outputs=["ordered file touch suggestions", "workflow checkpoints", "validation reminders"],
                )
            )

        deduped: list[SkillRecommendation] = []
        seen: set[str] = set()
        for recommendation in recommendations:
            if recommendation.name in seen:
                continue
            seen.add(recommendation.name)
            deduped.append(recommendation)
        return deduped[:8]


def _evidence_for_roles(source_summaries: list[SourceFileSummary], roles: set[str]) -> list[str]:
    """为角色型 skill 收集核心证据路径。"""

    return [summary.path for summary in source_summaries if summary.inferred_role in roles][:8]


def _directory_key(path: str) -> str:
    parent = Path(path).parent.as_posix()
    return "." if parent in {"", "."} else parent


def _append_sample(samples: list[str], path: str) -> None:
    if path in samples or len(samples) >= 3:
        return
    samples.append(path)


def _core_module_sort_key(summary: SourceFileSummary) -> tuple[int, float, int, int, str]:
    role_priority = {
        "entrypoint": 0,
        "route": 1,
        "service": 2,
        "model": 3,
        "source": 4,
        "utility": 5,
    }.get(summary.inferred_role, 6)
    symbol_count = (
        len(summary.functions)
        + len(summary.classes)
        + len(summary.methods)
        + len(summary.routes) * 2
        + len(summary.internal_dependencies)
    )
    return (
        role_priority,
        -summary.confidence,
        -symbol_count,
        summary.path.count("/"),
        summary.path,
    )
