from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import ScanExecution
    from ..workflows.requests import AdaptRequest


@dataclass(frozen=True)
class CommandRunSummary:
    command: str
    repo_path: Path
    output_dir: Path | None = None
    mode: str | None = None
    structure_only: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    target: str | None = None
    source_dir: Path | None = None
    repo_type: str | None = None
    selected_count: int | None = None
    candidate_count: int | None = None
    total_chars: int | None = None
    changed_files: list[str] = field(default_factory=list)
    affected_skills: list[str] = field(default_factory=list)
    generated_skills: list[str] = field(default_factory=list)
    report_path: Path | None = None
    notes: list[str] = field(default_factory=list)
    updated_paths: list[Path] = field(default_factory=list)
    written_paths: list[Path] = field(default_factory=list)


def summarize_scan_execution(command: str, result: "ScanExecution") -> CommandRunSummary:
    report = result.report
    return CommandRunSummary(
        command=command,
        repo_path=result.repo_path,
        output_dir=result.output_dir,
        mode=result.run_mode,
        structure_only=report.structure_only if report is not None else None,
        llm_provider=report.llm_provider if report is not None else None,
        llm_model=report.llm_model if report is not None else None,
        repo_type=result.blueprint.project_profile.repo_type,
        selected_count=result.selected_count,
        candidate_count=result.candidate_count,
        total_chars=result.total_chars,
        changed_files=list(result.changed_files),
        affected_skills=list(result.affected_skills),
        generated_skills=list(result.generated_skills),
        report_path=result.report_path,
        notes=list(report.notes) if report is not None else [],
        updated_paths=[Path(path) for path in report.updated_files] if report is not None else [],
        written_paths=list(result.output_files),
    )


def summarize_adapt_result(
    request: "AdaptRequest",
    written_paths: list[Path],
) -> CommandRunSummary:
    return CommandRunSummary(
        command="adapt",
        repo_path=request.repo_path,
        target=request.target,
        source_dir=request.source_dir,
        written_paths=list(written_paths),
    )
