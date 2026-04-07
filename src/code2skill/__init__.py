"""code2skill package."""

from __future__ import annotations

import importlib
from typing import Any

from code2skill.version import __version__

__all__ = [
    "adapt_repository",
    "adapt_skills",
    "ArtifactLayout",
    "CommandRunSummary",
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

_LAZY_EXPORTS = {
    "adapt_repository": (".api", "adapt_repository"),
    "adapt_skills": (".adapt", "adapt_skills"),
    "ArtifactLayout": (".domain", "ArtifactLayout"),
    "CommandRunSummary": (".domain", "CommandRunSummary"),
    "create_scan_config": (".api", "create_scan_config"),
    "estimate": (".api", "estimate"),
    "ExecutionReport": (".models", "ExecutionReport"),
    "PricingConfig": (".config", "PricingConfig"),
    "RunOptions": (".config", "RunOptions"),
    "ScanConfig": (".config", "ScanConfig"),
    "ScanExecution": (".models", "ScanExecution"),
    "ScanLimits": (".config", "ScanLimits"),
    "run_ci": (".api", "run_ci"),
    "scan": (".api", "scan"),
    "scan_repository": (".core", "scan_repository"),
    "estimate_repository": (".core", "estimate_repository"),
    "run_ci_repository": (".core", "run_ci_repository"),
}

def __getattr__(name: str) -> Any:
    if name == "__version__":
        return __version__
    if name in _LAZY_EXPORTS:
        module_name, attribute_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_name, __name__)
        value = getattr(module, attribute_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
