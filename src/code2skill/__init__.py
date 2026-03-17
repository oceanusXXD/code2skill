"""code2skill package."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__version__ = "0.1.1"

__all__ = [
    "ScanExecution",
    "scan_repository",
    "estimate_repository",
    "run_ci_repository",
    "__version__",
]

if TYPE_CHECKING:
    from .core import estimate_repository, run_ci_repository, scan_repository
    from .models import ScanExecution


def __getattr__(name: str) -> Any:
    if name == "ScanExecution":
        from .models import ScanExecution

        return ScanExecution
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
