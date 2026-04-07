from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.artifacts import ArtifactLayout

"""Workflow request helpers for repo-root-aware path resolution.

These request objects normalize repository-relative paths before they reach the
application and orchestration layers. The intent is to keep CLI/API semantics aligned
without duplicating path rules in multiple entrypoints.
"""


def resolve_repo_path(repo_path: Path | str) -> Path:
    return Path(repo_path).expanduser().resolve()


def resolve_repo_relative_path(repo_path: Path | str, value: Path | str) -> Path:
    root = resolve_repo_path(repo_path)
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def resolve_repo_relative_optional_path(
    repo_path: Path | str,
    value: Path | str | None,
) -> Path | None:
    if value is None:
        return None
    return resolve_repo_relative_path(repo_path, value)


@dataclass(frozen=True)
class WorkflowRequest:
    command: str
    repo_path: Path
    artifact_layout: ArtifactLayout

    @property
    def output_dir(self) -> Path:
        return self.artifact_layout.root

    @classmethod
    def create(
        cls,
        *,
        command: str,
        repo_path: Path | str,
        output_dir: Path | str = ".code2skill",
    ) -> "WorkflowRequest":
        resolved_repo_path = resolve_repo_path(repo_path)
        artifact_layout = ArtifactLayout.from_repo_root(
            resolved_repo_path,
            output_dir=output_dir,
        )
        return cls(
            command=command,
            repo_path=resolved_repo_path,
            artifact_layout=artifact_layout,
        )


@dataclass(frozen=True)
class AdaptRequest:
    repo_path: Path
    target: str
    source_dir: Path
    destination_root: Path

    @classmethod
    def create(
        cls,
        *,
        repo_path: Path | str,
        target: str,
        source_dir: Path | str = ".code2skill/skills",
    ) -> "AdaptRequest":
        resolved_repo_path = resolve_repo_path(repo_path)
        return cls(
            repo_path=resolved_repo_path,
            target=target,
            source_dir=resolve_repo_relative_path(resolved_repo_path, source_dir),
            destination_root=resolved_repo_path,
        )
