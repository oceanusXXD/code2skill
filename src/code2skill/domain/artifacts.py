from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

"""Artifact layout contracts for one repository run.

`ArtifactLayout` is the stable description of the `.code2skill/` bundle. Using this
object keeps output-path decisions explicit instead of reconstructing them ad hoc in
CLI, API, and workflow code.
"""


@dataclass(frozen=True)
class ArtifactLayout:
    root: Path
    project_summary_path: Path
    blueprint_path: Path
    skill_plan_path: Path
    report_path: Path
    references_dir: Path
    skills_dir: Path
    state_dir: Path
    state_path: Path

    @classmethod
    def from_repo_root(
        cls,
        repo_root: Path | str,
        output_dir: Path | str = ".code2skill",
    ) -> "ArtifactLayout":
        resolved_repo_root = Path(repo_root).expanduser().resolve()
        output_path = Path(output_dir).expanduser()
        artifact_root = (
            output_path.resolve()
            if output_path.is_absolute()
            else (resolved_repo_root / output_path).resolve()
        )
        references_dir = artifact_root / "references"
        state_dir = artifact_root / "state"
        return cls(
            root=artifact_root,
            project_summary_path=artifact_root / "project-summary.md",
            blueprint_path=artifact_root / "skill-blueprint.json",
            skill_plan_path=artifact_root / "skill-plan.json",
            report_path=artifact_root / "report.json",
            references_dir=references_dir,
            skills_dir=artifact_root / "skills",
            state_dir=state_dir,
            state_path=state_dir / "analysis-state.json",
        )

    def partition_bundle_paths(
        self,
        paths: Sequence[Path | str],
    ) -> tuple[list[Path], list[Path]]:
        final_products: list[Path] = []
        intermediates: list[Path] = []
        for path in paths:
            resolved = self._resolve_bundle_path(path)
            if self._is_final_product_path(resolved):
                final_products.append(resolved)
                continue
            intermediates.append(resolved)
        return final_products, intermediates

    def _resolve_bundle_path(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser()
        if candidate.is_absolute():
            return candidate.resolve()
        return (self.root / candidate).resolve()

    def _is_final_product_path(self, path: Path) -> bool:
        return path.suffix == ".md" and path.parent == self.skills_dir.resolve()
