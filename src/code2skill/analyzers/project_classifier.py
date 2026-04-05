from __future__ import annotations

from pathlib import Path

from ..config import BACKEND_FRAMEWORKS
from ..models import (
    ConfigSummary,
    DomainSummary,
    FileCandidate,
    ProjectProfile,
    SourceFileSummary,
)
from ..scanner.detector import infer_role_domain


class ProjectClassifier:
    """根据候选文件和抽取结果识别仓库类型、领域和技术栈。"""

    def classify(
        self,
        repo_path: Path,
        inventory_files: list[FileCandidate],
        config_summaries: list[ConfigSummary],
        source_summaries: list[SourceFileSummary],
    ) -> ProjectProfile:
        """输出顶层项目画像，供后续蓝图构建阶段使用。"""

        languages = sorted({candidate.language for candidate in inventory_files if candidate.language})
        framework_signals = sorted(
            {
                signal
                for summary in config_summaries
                for signal in summary.framework_signals
            }
        )
        entrypoints = sorted(
            {
                summary.path
                for summary in source_summaries
                if summary.inferred_role == "entrypoint"
            }
            | {
                entrypoint
                for config in config_summaries
                for entrypoint in config.entrypoints
            }
        )

        top_level_names = {
            candidate.relative_path.parts[0]
            for candidate in inventory_files
            if candidate.relative_path.parts
        }
        monorepo = bool(top_level_names & {"apps", "packages", "services"})

        backend_score = self._score_backend(framework_signals, source_summaries, top_level_names)

        if monorepo:
            repo_type = "monorepo"
        elif backend_score > 0:
            repo_type = "backend"
        else:
            repo_type = "infra_lib"

        package_topology = "workspace" if monorepo else "single-package"
        evidence = sorted(
            {
                *entrypoints,
                *(summary.path for summary in config_summaries[:4]),
            }
        )
        return ProjectProfile(
            name=repo_path.name,
            repo_type=repo_type,
            languages=languages,
            framework_signals=framework_signals,
            package_topology=package_topology,
            entrypoints=entrypoints,
            evidence=evidence,
        )

    def summarize_domains(self, source_summaries: list[SourceFileSummary]) -> list[DomainSummary]:
        """按照推断角色，把源码骨架归纳为若干业务领域。"""

        evidence_by_domain: dict[str, list[str]] = {}
        for summary in source_summaries:
            domain = infer_role_domain(summary.inferred_role)
            evidence_by_domain.setdefault(domain, []).append(summary.path)

        domains: list[DomainSummary] = []
        for domain_name, evidence in sorted(evidence_by_domain.items()):
            if domain_name == "backend":
                summary = "Routes, services, persistence, or validation layers."
            elif domain_name == "quality":
                summary = "Tests and verification scaffolding."
            else:
                summary = "Shared entrypoints, configuration, or cross-cutting helpers."
            domains.append(
                DomainSummary(
                    name=domain_name,
                    summary=summary,
                    evidence=sorted(set(evidence))[:8],
                )
            )
        return domains

    def build_tech_stack(
        self,
        profile: ProjectProfile,
        config_summaries: list[ConfigSummary],
    ) -> dict[str, object]:
        """从配置摘要中提取语言、框架、工具和包管理器信息。"""

        package_managers: list[str] = []
        tools: list[str] = []
        for summary in config_summaries:
            if summary.kind in {"pyproject", "requirements"}:
                package_managers.append("python")
            tools.extend(summary.framework_signals)

        return {
            "languages": profile.languages,
            "frameworks": profile.framework_signals,
            "package_managers": sorted(set(package_managers)),
            "tools": sorted(set(tools)),
        }

    @staticmethod
    def _score_backend(
        framework_signals: list[str],
        source_summaries: list[SourceFileSummary],
        top_level_names: set[str],
    ) -> int:
        """后端倾向打分，分数越高越像 backend。"""

        score = sum(2 for signal in framework_signals if signal in BACKEND_FRAMEWORKS)
        score += sum(
            1
            for summary in source_summaries
            if summary.inferred_role in {"route", "service", "model"}
        )
        if top_level_names & {"api", "backend", "server"}:
            score += 2
        return score
