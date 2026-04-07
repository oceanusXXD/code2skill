from __future__ import annotations

import importlib
import json
from pathlib import Path

from .config import STATE_DIRNAME, STATE_FILENAME
from .models import StateSnapshot


class StateStore:
    """负责 `.code2skill/state` 下状态文件的读写。"""

    def __init__(self, output_dir: Path, repo_path: Path | None = None) -> None:
        self.output_dir = output_dir
        self.repo_path = repo_path.resolve() if repo_path is not None else None
        self.state_dir = output_dir / STATE_DIRNAME
        self.state_path = self.state_dir / STATE_FILENAME

    def load(self) -> StateSnapshot | None:
        """读取历史状态；不存在、损坏或仓库不匹配时返回 `None`。"""

        if not self.state_path.exists():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            snapshot = _snapshot_from_dict(data)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

        # 增量缓存只能在同一个仓库根目录下复用，避免跨仓库误判。
        if self.repo_path is not None:
            snapshot_repo_root = Path(snapshot.repo_root).resolve()
            if snapshot_repo_root != self.repo_path:
                return None
        return snapshot

    def save(self, snapshot: StateSnapshot) -> None:
        """把新的状态快照写回磁盘，并尽量通过临时文件替换降低写坏风险。"""

        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = _snapshot_to_dict(snapshot)
        # 先写临时文件，再替换正式文件，减少中断时留下半写入状态的概率。
        tmp_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(self.state_path)


def _snapshot_from_dict(data: dict[str, object]) -> StateSnapshot:
    return importlib.import_module(
        ".state_codec", __package__
    ).snapshot_from_dict(data)


def _snapshot_to_dict(snapshot: StateSnapshot) -> dict[str, object]:
    return importlib.import_module(
        ".state_codec", __package__
    ).snapshot_to_dict(snapshot)
