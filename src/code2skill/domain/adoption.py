from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AdoptionCheck:
    name: str
    status: str
    message: str
    path: Path | None = None


@dataclass(frozen=True)
class AdoptionReadiness:
    repo_path: Path
    output_dir: Path
    target: str | None
    ready: bool
    score: int
    checks: list[AdoptionCheck] = field(default_factory=list)
    missing_paths: list[Path] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
