from __future__ import annotations

from pathlib import Path
from typing import Literal

from .adapt import adapt_skills
from .config import PricingConfig, RunOptions, ScanConfig, ScanLimits


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
    repo_root = Path(repo_path).expanduser().resolve()
    output_root = _resolve_repo_relative_path(repo_root, output_dir)
    effective_mode = mode or ("full" if command == "scan" else "auto")
    effective_report_path = _resolve_repo_relative_optional_path(repo_root, report_path)
    if effective_report_path is None:
        effective_report_path = output_root / "report.json"

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
            diff_file=_resolve_repo_relative_optional_path(repo_root, diff_file),
            report_path=effective_report_path,
            pricing=PricingConfig.from_file(
                _resolve_repo_relative_optional_path(repo_root, pricing_file)
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
    from .core import scan_repository

    return scan_repository(
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
    from .core import estimate_repository

    return estimate_repository(
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
    from .core import run_ci_repository

    return run_ci_repository(
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
    repo_root = Path(repo_path).expanduser().resolve()
    return adapt_skills(
        target=target,
        source_dir=source_dir,
        destination_root=repo_root,
    )


def _resolve_repo_relative_path(repo_path: Path, value: Path | str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (repo_path / path).resolve()


def _resolve_repo_relative_optional_path(
    repo_path: Path,
    value: Path | str | None,
) -> Path | None:
    if value is None:
        return None
    return _resolve_repo_relative_path(repo_path, value)
