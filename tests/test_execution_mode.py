from __future__ import annotations

from pathlib import Path

from code2skill.capabilities.execution_mode import choose_effective_mode, is_full_rebuild_trigger
from code2skill.config import RunOptions, ScanConfig


class FakeGitClient:
    def __init__(self, is_repository: bool) -> None:
        self._is_repository = is_repository

    def is_repository(self) -> bool:
        return self._is_repository


def test_choose_effective_mode_falls_back_to_full_without_previous_state(tmp_path: Path) -> None:
    config = ScanConfig(
        repo_path=tmp_path,
        output_dir=tmp_path / ".code2skill",
        run=RunOptions(command="ci", mode="auto"),
    )

    effective_mode, notes = choose_effective_mode(
        config=config,
        previous_state=None,
        git_client=FakeGitClient(is_repository=True),
        changed_files=["app.py"],
    )

    assert effective_mode == "full"
    assert notes == ["未发现历史状态缓存，自动执行首次全量构建。"]


def test_choose_effective_mode_keeps_incremental_without_changed_files(tmp_path: Path) -> None:
    config = ScanConfig(
        repo_path=tmp_path,
        output_dir=tmp_path / ".code2skill",
        run=RunOptions(command="ci", mode="incremental"),
    )

    effective_mode, notes = choose_effective_mode(
        config=config,
        previous_state=object(),
        git_client=FakeGitClient(is_repository=True),
        changed_files=[],
    )

    assert effective_mode == "incremental"
    assert notes == ["未检测到代码变化，将复用缓存并快速重建产物。"]


def test_is_full_rebuild_trigger_matches_project_root_config_files() -> None:
    assert is_full_rebuild_trigger("pyproject.toml") is True
    assert is_full_rebuild_trigger("docker-compose.yml") is True
    assert is_full_rebuild_trigger("src/app.py") is False
