from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .domain.results import (
    CommandRunSummary,
    summarize_adapt_result,
    summarize_scan_execution,
)
from .workflows.requests import AdaptRequest

if TYPE_CHECKING:
    from .config import ScanConfig
    from .models import ScanExecution


"""Application-level workflow facade.

This module keeps the public command/API entrypoints thin while routing work into the
existing orchestration pipeline. It is intentionally small: the goal of this layer is
to establish stable application seams before deeper pipeline extraction happens.
"""


def run_scan(config: "ScanConfig") -> "ScanExecution":
    from .core import scan_repository

    return scan_repository(config)


def run_estimate(config: "ScanConfig") -> "ScanExecution":
    from .core import estimate_repository

    return estimate_repository(config)


def run_ci(config: "ScanConfig") -> "ScanExecution":
    from .core import run_ci_repository

    return run_ci_repository(config)


def run_adapt(
    repo_path: Path | str = ".",
    *,
    target: str,
    source_dir: Path | str = ".code2skill/skills",
) -> tuple[list[Path], CommandRunSummary]:
    from .adapt import adapt_skills

    request = AdaptRequest.create(
        repo_path=repo_path,
        target=target,
        source_dir=source_dir,
    )
    written_paths = adapt_skills(
        target=request.target,
        source_dir=request.source_dir,
        destination_root=request.destination_root,
    )
    return written_paths, summarize_adapt_result(request, written_paths)


def summarize_execution(command: str, result) -> CommandRunSummary:
    return summarize_scan_execution(command, result)
