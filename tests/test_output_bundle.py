from __future__ import annotations

from pathlib import Path

from code2skill.capabilities.output_bundle_service import prune_stale_skill_files, selected_path_strings, write_outputs
from code2skill.models import FileCandidate


def test_write_outputs_tracks_written_and_updated_files(tmp_path: Path) -> None:
    output_dir = tmp_path / ".code2skill"
    output_dir.mkdir()
    existing = output_dir / "report.json"
    existing.write_text("same", encoding="utf-8")

    written, updated = write_outputs(
        output_dir,
        {
            "report.json": "same",
            "skills/backend.md": "# Backend\n",
        },
    )

    assert written == [output_dir / "report.json", output_dir / "skills" / "backend.md"]
    assert updated == [output_dir / "skills" / "backend.md"]


def test_prune_stale_skill_files_removes_only_unplanned_markdown(tmp_path: Path) -> None:
    skills_dir = tmp_path / ".code2skill" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "index.md").write_text("# Index\n", encoding="utf-8")
    kept = skills_dir / "backend.md"
    kept.write_text("# Backend\n", encoding="utf-8")
    stale = skills_dir / "old.md"
    stale.write_text("# Old\n", encoding="utf-8")

    removed = prune_stale_skill_files(tmp_path / ".code2skill", ["backend"])

    assert removed == [stale]
    assert kept.exists()
    assert not stale.exists()


def test_selected_path_strings_are_stable_and_repo_relative() -> None:
    selected = [
        FileCandidate(
            absolute_path=Path("/repo/src/app.py"),
            relative_path=Path("src/app.py"),
            size_bytes=10,
            char_count=10,
            sha256="a",
            language="python",
            inferred_role="entrypoint",
            priority=1,
            priority_reasons=["entrypoint"],
        )
    ]

    assert selected_path_strings(selected) == ["src/app.py"]
