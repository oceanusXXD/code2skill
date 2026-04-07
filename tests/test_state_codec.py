from __future__ import annotations

from code2skill.models import CachedFileRecord, StateSnapshot
from code2skill.state_codec import snapshot_from_dict, snapshot_to_dict


def test_state_codec_round_trips_snapshot_dict() -> None:
    snapshot = StateSnapshot(
        version=1,
        generated_at="2026-04-07T00:00:00+00:00",
        repo_root="/repo",
        head_commit="deadbeef",
        selected_paths=["src/app.py"],
        directory_counts={"src": 1},
        gitignore_patterns=[".venv"],
        discovery_method="git",
        candidate_count=1,
        total_chars=12,
        bytes_read=64,
        files={
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
        },
        reverse_dependencies={"src/app.py": []},
        skill_index={},
    )

    payload = snapshot_to_dict(snapshot)
    restored = snapshot_from_dict(payload)

    assert restored == snapshot
