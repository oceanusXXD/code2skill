from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

from ..config import (
    CONFIG_FILE_GLOBS,
    HIGH_VALUE_BASENAMES,
    HIGH_VALUE_GLOBS,
    ScanConfig,
    matches_any_glob,
)
from ..git_client import GitClient
from ..models import CachedFileRecord, FileCandidate, RepositoryInventory
from .detector import detect_language
from .filters import FileFilter, GitIgnoreMatcher
from .prioritizer import FilePrioritizer


# 仓库扫描器负责两件事：
# 1. 发现候选文件。
# 2. 生成预算排序所需的轻量元数据。
#
# 它故意不做抽取和分析，避免把扫描层变成“巨型总控函数”。
class RepositoryScanner:
    def __init__(
        self,
        config: ScanConfig,
        previous_files: dict[str, CachedFileRecord] | None = None,
        changed_paths: set[str] | None = None,
    ) -> None:
        self.config = config
        self.previous_files = previous_files or {}
        self.changed_paths = changed_paths
        self.gitignore_matcher = GitIgnoreMatcher.from_repo(config.repo_path)
        self.file_filter = FileFilter(
            max_file_size_kb=config.limits.max_file_size_kb,
            gitignore_matcher=self.gitignore_matcher,
        )
        self.prioritizer = FilePrioritizer()
        self.git_client = GitClient(config.repo_path)

    def scan(self) -> RepositoryInventory:
        repo_path = self.config.repo_path
        if not repo_path.exists() or not repo_path.is_dir():
            raise FileNotFoundError(f"Repository path does not exist: {repo_path}")

        discovered_paths, discovery_method = self._discover_paths()
        candidates: list[FileCandidate] = []
        directory_counts: Counter[str] = Counter()
        bytes_read = 0

        for relative_path in discovered_paths:
            absolute_path = repo_path / relative_path
            if not absolute_path.exists() or absolute_path.is_dir():
                continue

            size_bytes = absolute_path.stat().st_size
            path_decision = self.file_filter.should_include_path(
                relative_path,
                size_bytes,
            )
            if not path_decision.include:
                continue

            cached = self.previous_files.get(relative_path.as_posix())
            if self._can_reuse_cache(relative_path, cached):
                candidates.append(
                    self._candidate_from_cache(
                        absolute_path=absolute_path,
                        relative_path=relative_path,
                        cached=cached,
                    )
                )
                directory_counts[self._top_level_key(relative_path)] += 1
                continue

            data = absolute_path.read_bytes()
            bytes_read += len(data)
            if self.file_filter.looks_binary_blob(data):
                continue

            content = data.decode("utf-8", errors="ignore")
            content_decision = self.file_filter.should_include_content(
                relative_path,
                content,
            )
            if not content_decision.include:
                continue

            language = detect_language(relative_path)
            if language is None and not self._is_supported_non_source_file(relative_path):
                continue
            priority, reasons, inferred_role = self.prioritizer.score(
                relative_path,
                language,
            )
            candidates.append(
                FileCandidate(
                    absolute_path=absolute_path,
                    relative_path=relative_path,
                    size_bytes=size_bytes,
                    char_count=len(content),
                    sha256=hashlib.sha256(data).hexdigest(),
                    language=language,
                    inferred_role=inferred_role,
                    priority=priority,
                    priority_reasons=reasons,
                    content=content,
                    gitignored=path_decision.gitignored,
                )
            )
            directory_counts[self._top_level_key(relative_path)] += 1

        candidates.sort(
            key=lambda candidate: (
                -candidate.priority,
                candidate.char_count,
                candidate.relative_path.as_posix(),
            )
        )
        return RepositoryInventory(
            repo_path=repo_path,
            candidates=candidates,
            directory_counts=dict(sorted(directory_counts.items())),
            gitignore_patterns=self.gitignore_matcher.patterns(),
            discovery_method=discovery_method,
            bytes_read=bytes_read,
        )

    def _discover_paths(self) -> tuple[list[Path], str]:
        if self.git_client.is_repository():
            git_paths = {
                path
                for path in self.git_client.list_candidate_paths()
                if path.parts
            }
            git_paths.update(self._supplement_high_value_paths())
            return sorted(git_paths, key=lambda path: path.as_posix()), "git"

        filesystem_paths = [
            path.relative_to(self.config.repo_path)
            for path in sorted(self.config.repo_path.rglob("*"))
            if path.is_file()
        ]
        return filesystem_paths, "filesystem"

    def _supplement_high_value_paths(self) -> set[Path]:
        # git 不会返回被忽略的未跟踪文件。
        # 这里只补充少量高价值配置文件，避免为此退回全量递归遍历。
        supplemental: set[Path] = set()
        for absolute_path in self.config.repo_path.iterdir():
            if not absolute_path.is_file():
                continue
            relative_path = absolute_path.relative_to(self.config.repo_path)
            if relative_path.name in HIGH_VALUE_BASENAMES:
                supplemental.add(relative_path)
                continue
            if matches_any_glob(relative_path, HIGH_VALUE_GLOBS):
                supplemental.add(relative_path)
                continue
            if matches_any_glob(relative_path, CONFIG_FILE_GLOBS):
                supplemental.add(relative_path)
        return supplemental

    def _can_reuse_cache(
        self,
        relative_path: Path,
        cached: CachedFileRecord | None,
    ) -> bool:
        if cached is None:
            return False
        if self.changed_paths is None:
            return False
        return relative_path.as_posix() not in self.changed_paths

    def _candidate_from_cache(
        self,
        absolute_path: Path,
        relative_path: Path,
        cached: CachedFileRecord,
    ) -> FileCandidate:
        return FileCandidate(
            absolute_path=absolute_path,
            relative_path=relative_path,
            size_bytes=cached.size_bytes,
            char_count=cached.char_count,
            sha256=cached.sha256,
            language=cached.language,
            inferred_role=cached.inferred_role,
            priority=cached.priority,
            priority_reasons=cached.priority_reasons,
            content=None,
            gitignored=cached.gitignored,
        )

    def _top_level_key(self, relative_path: Path) -> str:
        parent = relative_path.parent.as_posix()
        return "." if parent in {"", "."} else parent

    def _is_supported_non_source_file(self, relative_path: Path) -> bool:
        if relative_path.name in HIGH_VALUE_BASENAMES:
            return True
        if relative_path.name.lower().startswith("readme"):
            return True
        if relative_path.name.startswith("Dockerfile"):
            return True
        if matches_any_glob(relative_path, HIGH_VALUE_GLOBS):
            return True
        return matches_any_glob(relative_path, CONFIG_FILE_GLOBS)
