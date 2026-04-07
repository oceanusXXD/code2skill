from __future__ import annotations

from pathlib import Path
from typing import Literal

from .config import PricingConfig, RunOptions, ScanConfig, ScanLimits
from .workflows.requests import (
    WorkflowRequest,
    resolve_repo_relative_optional_path,
)


CommandName = Literal["scan", "estimate", "ci"]
ModeName = Literal["auto", "full", "incremental"]
LLMProvider = Literal["openai", "claude", "qwen"]


def create_scan_config(
    repo_path: Path | str = ".",
    *,
    command: CommandName = "scan",
    output_dir: Path | str = ".code2skill",
    mode: ModeName | None = None,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    diff_file: Path | str | None = None,
    report_path: Path | str | None = None,
    pricing_file: Path | str | None = None,
    structure_only: bool = False,
    llm_provider: LLMProvider = "openai",
    llm_model: str | None = None,
    max_skills: int = 8,
    max_files: int = 40,
    max_file_size_kb: int = 256,
    max_total_chars: int = 120000,
    write_outputs: bool | None = None,
    write_state: bool | None = None,
    max_incremental_changed_files: int = 64,
    force_full_on_config_change: bool = True,
) -> ScanConfig:
    request = WorkflowRequest.create(
        command=command,
        repo_path=repo_path,
        output_dir=output_dir,
    )
    repo_root = request.repo_path
    output_root = request.output_dir
    effective_mode = mode or ("full" if command == "scan" else "auto")
    effective_report_path = resolve_repo_relative_optional_path(repo_root, report_path)
    if effective_report_path is None:
        effective_report_path = request.artifact_layout.report_path

    return ScanConfig(
        repo_path=repo_root,
        output_dir=output_root,
        limits=ScanLimits(
            max_files=max_files,
            max_file_size_kb=max_file_size_kb,
            max_total_chars=max_total_chars,
        ),
        run=RunOptions(
            command=command,
            mode=effective_mode,
            base_ref=base_ref,
            head_ref=head_ref,
            diff_file=resolve_repo_relative_optional_path(repo_root, diff_file),
            report_path=effective_report_path,
            pricing=PricingConfig.from_file(
                resolve_repo_relative_optional_path(repo_root, pricing_file)
            ),
            structure_only=structure_only,
            llm_provider=llm_provider,
            llm_model=llm_model,
            max_skills=max_skills,
            write_outputs=command != "estimate" if write_outputs is None else write_outputs,
            write_state=command != "estimate" if write_state is None else write_state,
            max_incremental_changed_files=max_incremental_changed_files,
            force_full_on_config_change=force_full_on_config_change,
        ),
    )


def scan(
    repo_path: Path | str = ".",
    *,
    output_dir: Path | str = ".code2skill",
    mode: Literal["full", "incremental"] = "full",
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    diff_file: Path | str | None = None,
    report_path: Path | str | None = None,
    pricing_file: Path | str | None = None,
    structure_only: bool = False,
    llm_provider: LLMProvider = "openai",
    llm_model: str | None = None,
    max_skills: int = 8,
    max_files: int = 40,
    max_file_size_kb: int = 256,
    max_total_chars: int = 120000,
    max_incremental_changed_files: int = 64,
):
    from .application import run_scan

    return run_scan(
        create_scan_config(
            repo_path=repo_path,
            command="scan",
            output_dir=output_dir,
            mode=mode,
            base_ref=base_ref,
            head_ref=head_ref,
            diff_file=diff_file,
            report_path=report_path,
            pricing_file=pricing_file,
            structure_only=structure_only,
            llm_provider=llm_provider,
            llm_model=llm_model,
            max_skills=max_skills,
            max_files=max_files,
            max_file_size_kb=max_file_size_kb,
            max_total_chars=max_total_chars,
            max_incremental_changed_files=max_incremental_changed_files,
        )
    )


def estimate(
    repo_path: Path | str = ".",
    *,
    output_dir: Path | str = ".code2skill",
    mode: ModeName = "auto",
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    diff_file: Path | str | None = None,
    report_path: Path | str | None = None,
    pricing_file: Path | str | None = None,
    max_files: int = 40,
    max_file_size_kb: int = 256,
    max_total_chars: int = 120000,
    max_incremental_changed_files: int = 64,
):
    from .application import run_estimate

    return run_estimate(
        create_scan_config(
            repo_path=repo_path,
            command="estimate",
            output_dir=output_dir,
            mode=mode,
            base_ref=base_ref,
            head_ref=head_ref,
            diff_file=diff_file,
            report_path=report_path,
            pricing_file=pricing_file,
            max_files=max_files,
            max_file_size_kb=max_file_size_kb,
            max_total_chars=max_total_chars,
            max_incremental_changed_files=max_incremental_changed_files,
        )
    )


def run_ci(
    repo_path: Path | str = ".",
    *,
    output_dir: Path | str = ".code2skill",
    mode: ModeName = "auto",
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    diff_file: Path | str | None = None,
    report_path: Path | str | None = None,
    pricing_file: Path | str | None = None,
    structure_only: bool = False,
    llm_provider: LLMProvider = "openai",
    llm_model: str | None = None,
    max_skills: int = 8,
    max_files: int = 40,
    max_file_size_kb: int = 256,
    max_total_chars: int = 120000,
    max_incremental_changed_files: int = 64,
):
    from .application import run_ci as run_ci_application

    return run_ci_application(
        create_scan_config(
            repo_path=repo_path,
            command="ci",
            output_dir=output_dir,
            mode=mode,
            base_ref=base_ref,
            head_ref=head_ref,
            diff_file=diff_file,
            report_path=report_path,
            pricing_file=pricing_file,
            structure_only=structure_only,
            llm_provider=llm_provider,
            llm_model=llm_model,
            max_skills=max_skills,
            max_files=max_files,
            max_file_size_kb=max_file_size_kb,
            max_total_chars=max_total_chars,
            max_incremental_changed_files=max_incremental_changed_files,
        )
    )


def adapt_repository(
    repo_path: Path | str = ".",
    *,
    target: str,
    source_dir: Path | str = ".code2skill/skills",
) -> list[Path]:
    from .application import run_adapt

    written_paths, _ = run_adapt(
        repo_path=repo_path,
        target=target,
        source_dir=source_dir,
    )
    return written_paths
