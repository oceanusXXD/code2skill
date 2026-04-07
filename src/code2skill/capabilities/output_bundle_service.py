from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from code2skill.models import FileCandidate


def write_outputs(
    output_dir: Path,
    rendered_artifacts: dict[str, str],
) -> tuple[list[Path], list[Path]]:
    written_files: list[Path] = []
    updated_files: list[Path] = []
    for relative_path, content in rendered_artifacts.items():
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        written_files.append(path)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        updated_files.append(path)
    return written_files, updated_files


def prune_stale_skill_files(
    output_dir: Path,
    planned_skill_names: list[str],
) -> list[Path]:
    skills_dir = output_dir / "skills"
    if not skills_dir.exists():
        return []

    keep = {f"{name}.md" for name in planned_skill_names}
    keep.add("index.md")
    removed: list[Path] = []
    for path in skills_dir.glob("*.md"):
        if path.name in keep:
            continue
        path.unlink(missing_ok=True)
        removed.append(path)
    return removed


def selected_path_strings(selected_candidates: Sequence[FileCandidate]) -> list[str]:
    return [candidate.relative_path.as_posix() for candidate in selected_candidates]
