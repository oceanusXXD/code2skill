"""code2skill package."""

from .core import (
    ScanExecution,
    estimate_repository,
    run_ci_repository,
    scan_repository,
)

__all__ = [
    "ScanExecution",
    "scan_repository",
    "estimate_repository",
    "run_ci_repository",
    "__version__",
]

__version__ = "0.3.0"
