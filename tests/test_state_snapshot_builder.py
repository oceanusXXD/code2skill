from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from code2skill.capabilities.state_snapshot_service import build_state_snapshot
from code2skill.config import RunOptions, ScanConfig
from code2skill.models import CachedFileRecord, FileCandidate, SkillImpactIndexEntry, StateSnapshot


def test_build_state_snapshot_keeps_selected_paths_and_metadata(tmp_path: Path) -> None:
    config = ScanConfig(repo_path=tmp_path, output_dir=tmp_path / ".code2skill", run=RunOptions())
    inventory = SimpleNamespace(
        directory_counts={"src": 1},
        gitignore_patterns=[".venv"],
        discovery_method="git",
        candidates=[object()],
    )
    budget = SimpleNamespace(
        selected=[
            FileCandidate(
                absolute_path=tmp_path / "src" / "app.py",
                relative_path=Path("src/app.py"),
                size_bytes=12,
                char_count=12,
                sha256="abc",
                language="python",
                inferred_role="entrypoint",
                priority=1,
                priority_reasons=["entrypoint"],
            )
        ],
        total_chars=12,
    )
    records = {
        "src/app.py": CachedFileRecord(
            path="src/app.py",
            sha256="abc",
            size_bytes=12,
            char_count=12,
            language="python",
            inferred_role="entrypoint",
            priority=1,
            priority_reasons=["entrypoint"],
            gitignored=False,
        )
    }

    snapshot = build_state_snapshot(
        config=config,
        inventory=inventory,
        budget=budget,
        records=records,
        reverse_dependencies={"src/app.py": []},
        skill_index={
            "backend": SkillImpactIndexEntry(
                name="backend",
                purpose="backend rules",
                source_evidence=["src/app.py"],
                related_paths=["src/app.py"],
            )
        },
        bytes_read=64,
        head_commit="deadbeef",
        generated_at="2026-04-07T00:00:00+00:00",
    )

    assert isinstance(snapshot, StateSnapshot)
    assert snapshot.selected_paths == ["src/app.py"]
    assert snapshot.directory_counts == {"src": 1}
    assert snapshot.bytes_read == 64
    assert snapshot.head_commit == "deadbeef"
