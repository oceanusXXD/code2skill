from __future__ import annotations

from ..models import SourceFileSummary, WorkflowSummary


class WorkflowAnalyzer:
    """从源码骨架中提取具体、可执行的开发流程。"""

    def analyze(self, source_summaries: list[SourceFileSummary]) -> list[WorkflowSummary]:
        """输出 concrete_workflows，对应高频操作路径。"""

        workflows: list[WorkflowSummary] = []
        roles = {summary.inferred_role for summary in source_summaries}

        if {"route", "service", "model"} <= roles:
            workflows.append(
                WorkflowSummary(
                    name="api-flow",
                    summary="Backend request handling likely flows from route/controller files into service files and then into models or schemas.",
                    steps=[
                        "Start from the route or controller module that exposes the handler.",
                        "Trace the invoked service or repository helper for business logic.",
                        "Follow model or schema definitions for validation and persistence concerns.",
                    ],
                    evidence=_workflow_evidence(source_summaries, {"route", "service", "model"}),
                )
            )

        if {"route", "service"} <= roles:
            workflows.append(
                WorkflowSummary(
                    name="feature-adding-flow",
                    summary="Adding a feature usually requires touching the request entrypoint plus one or two adjacent backend layers.",
                    steps=[
                        "Pick the user-facing entrypoint such as a route, CLI command, or job module.",
                        "Add or update the service or repository layer that carries the feature logic.",
                        "Update validation, contracts, and tests near the touched layers.",
                    ],
                    evidence=[summary.path for summary in source_summaries[:8]],
                )
            )

        return workflows


def _workflow_evidence(source_summaries: list[SourceFileSummary], roles: set[str]) -> list[str]:
    """收集单个 workflow 用到的代表性路径。"""

    return [summary.path for summary in source_summaries if summary.inferred_role in roles][:8]
