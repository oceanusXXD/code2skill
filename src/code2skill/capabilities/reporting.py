from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..config import DEFAULT_REPORT_FILENAME, ScanConfig
from ..models import ExecutionReport, ImpactSummary


class PricingReporter(Protocol):
    def pricing_dict(self) -> dict[str, float | str]: ...


def resolve_report_path(config: ScanConfig) -> Path:
    if config.run.report_path is not None:
        return config.run.report_path
    return config.output_dir / DEFAULT_REPORT_FILENAME


def build_execution_report(
    *,
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
    cost_estimator: PricingReporter,
    first_generation_cost,
    rewrite_cost,
    patch_cost,
    notes: list[str],
    generated_at: str,
) -> ExecutionReport:
    return ExecutionReport(
        generated_at=generated_at,
        command=config.run.command,
        requested_mode=config.run.mode,
        effective_mode=effective_mode,
        structure_only=config.run.structure_only,
        llm_provider=config.run.llm_provider,
        llm_model=config.run.llm_model,
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
