from __future__ import annotations

import json
from pathlib import Path

from code2skill.models import StateSnapshot
from code2skill.state_store import StateStore


def test_state_store_load_returns_none_for_invalid_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    state_dir = output_dir / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "analysis-state.json").write_text("{invalid", encoding="utf-8")

    assert StateStore(output_dir, repo_path=tmp_path / "repo").load() is None


def test_state_store_load_returns_none_for_missing_required_keys(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    state_dir = output_dir / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "analysis-state.json").write_text(
        json.dumps({"generated_at": "2026-04-05T00:00:00+00:00"}),
        encoding="utf-8",
    )

    assert StateStore(output_dir, repo_path=tmp_path / "repo").load() is None


def test_state_store_load_returns_none_for_repo_mismatch(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    snapshot = _build_snapshot(repo_root=str(tmp_path / "other-repo"))
    StateStore(output_dir).save(snapshot)

    loaded = StateStore(output_dir, repo_path=tmp_path / "repo").load()

    assert loaded is None


def test_state_store_load_without_repo_guard_allows_foreign_repo_root(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    snapshot = _build_snapshot(repo_root=str(tmp_path / "other-repo"))
    StateStore(output_dir).save(snapshot)

    loaded = StateStore(output_dir).load()

    assert loaded == snapshot


def test_state_store_round_trips_when_repo_matches(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    output_dir = tmp_path / "out"
    snapshot = _build_snapshot(repo_root=str(repo_path.resolve()))

    store = StateStore(output_dir, repo_path=repo_path)
    store.save(snapshot)
    loaded = store.load()

    assert loaded == snapshot


def test_state_store_load_allows_repo_match_after_path_resolution(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    output_dir = tmp_path / "out"
    snapshot = _build_snapshot(repo_root=str(repo_path / "."))

    StateStore(output_dir).save(snapshot)
    loaded = StateStore(output_dir, repo_path=repo_path).load()

    assert loaded is not None
    assert Path(loaded.repo_root).resolve() == repo_path.resolve()


def test_state_store_save_replaces_file_without_leaving_tmp(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    output_dir = tmp_path / "out"
    store = StateStore(output_dir, repo_path=repo_path)

    store.save(_build_snapshot(repo_root=str(repo_path.resolve())))

    assert store.state_path.exists()
    assert not store.state_path.with_suffix(f"{store.state_path.suffix}.tmp").exists()


def _build_snapshot(repo_root: str) -> StateSnapshot:
    return StateSnapshot(
        version=1,
        generated_at="2026-04-05T00:00:00+00:00",
        repo_root=repo_root,
        head_commit="deadbeef",
        selected_paths=[],
        directory_counts={},
        gitignore_patterns=[],
        discovery_method="git",
        candidate_count=0,
        total_chars=0,
        bytes_read=0,
        files={},
        reverse_dependencies={},
        skill_index={},
    )
