"""code2skill package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .adapt import adapt_skills
from .api import adapt_repository, create_scan_config, estimate, run_ci, scan
from .config import PricingConfig, RunOptions, ScanConfig, ScanLimits
from .models import ExecutionReport, ScanExecution

__version__ = "0.1.5"

__all__ = [
    "adapt_repository",
    "adapt_skills",
    "create_scan_config",
    "estimate",
    "ExecutionReport",
    "PricingConfig",
    "RunOptions",
    "ScanConfig",
    "ScanExecution",
    "ScanLimits",
    "run_ci",
    "scan_repository",
    "scan",
    "estimate_repository",
    "run_ci_repository",
    "__version__",
]

if TYPE_CHECKING:
    from .core import estimate_repository, run_ci_repository, scan_repository


def __getattr__(name: str) -> Any:
    if name in {"scan_repository", "estimate_repository", "run_ci_repository"}:
        from .core import estimate_repository, run_ci_repository, scan_repository

        return {
            "scan_repository": scan_repository,
            "estimate_repository": estimate_repository,
            "run_ci_repository": run_ci_repository,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
