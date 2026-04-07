from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..config import CONFIG_FILE_GLOBS, HIGH_VALUE_BASENAMES, ScanConfig, matches_any_glob


class GitRepositoryProbe(Protocol):
    def is_repository(self) -> bool: ...


def choose_effective_mode(
    config: ScanConfig,
    previous_state: object | None,
    git_client: GitRepositoryProbe,
    changed_files: list[str],
) -> tuple[str, list[str]]:
    notes: list[str] = []
    requested_mode = config.run.mode
    if requested_mode == "full":
        return "full", notes
    if config.run.diff_file is None and not git_client.is_repository():
        notes.append("当前目录不是 git 仓库，自动回退到全量模式。")
        return "full", notes
    if previous_state is None:
        notes.append("未发现历史状态缓存，自动执行首次全量构建。")
        return "full", notes
    if requested_mode == "incremental" and not changed_files:
        notes.append("未检测到代码变化，将复用缓存并快速重建产物。")
        return "incremental", notes
    if requested_mode in {"incremental", "auto"}:
        if (
            config.run.force_full_on_config_change
            and any(is_full_rebuild_trigger(path) for path in changed_files)
        ):
            notes.append("检测到核心配置变化，自动回退到全量模式。")
            return "full", notes
        if len(changed_files) > config.run.max_incremental_changed_files:
            notes.append("变更文件过多，自动回退到全量模式。")
            return "full", notes
        return "incremental", notes
    return "full", notes


def is_full_rebuild_trigger(path: str) -> bool:
    relative_path = Path(path)
    if relative_path.name in {"pyproject.toml", "requirements.txt", "Dockerfile"}:
        return True
    if matches_any_glob(relative_path, CONFIG_FILE_GLOBS):
        return True
    return relative_path.name in HIGH_VALUE_BASENAMES and len(relative_path.parts) == 1
