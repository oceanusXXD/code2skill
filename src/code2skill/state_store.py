from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import STATE_DIRNAME, STATE_FILENAME
from .models import (
    CachedFileRecord,
    ClassInfo,
    ConfigSummary,
    ExportInfo,
    FunctionInfo,
    ImportInfo,
    RouteSummary,
    SkillImpactIndexEntry,
    SourceFileSummary,
    StateSnapshot,
)


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
            snapshot = StateSnapshot(
                version=int(data["version"]),
                generated_at=str(data["generated_at"]),
                repo_root=str(data["repo_root"]),
                head_commit=data.get("head_commit"),
                selected_paths=list(data.get("selected_paths", [])),
                directory_counts={
                    str(key): int(value)
                    for key, value in data.get("directory_counts", {}).items()
                },
                gitignore_patterns=list(data.get("gitignore_patterns", [])),
                discovery_method=str(data.get("discovery_method", "filesystem")),
                candidate_count=int(data.get("candidate_count", 0)),
                total_chars=int(data.get("total_chars", 0)),
                bytes_read=int(data.get("bytes_read", 0)),
                files={
                    path: _cached_file_from_dict(path, payload)
                    for path, payload in data.get("files", {}).items()
                },
                reverse_dependencies={
                    str(key): list(value)
                    for key, value in data.get("reverse_dependencies", {}).items()
                },
                skill_index={
                    name: SkillImpactIndexEntry(**payload)
                    for name, payload in data.get("skill_index", {}).items()
                },
            )
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
        payload = {
            "version": snapshot.version,
            "generated_at": snapshot.generated_at,
            "repo_root": snapshot.repo_root,
            "head_commit": snapshot.head_commit,
            "selected_paths": snapshot.selected_paths,
            "directory_counts": snapshot.directory_counts,
            "gitignore_patterns": snapshot.gitignore_patterns,
            "discovery_method": snapshot.discovery_method,
            "candidate_count": snapshot.candidate_count,
            "total_chars": snapshot.total_chars,
            "bytes_read": snapshot.bytes_read,
            "files": {
                path: _cached_file_to_dict(record)
                for path, record in snapshot.files.items()
            },
            "reverse_dependencies": snapshot.reverse_dependencies,
            "skill_index": {
                name: asdict(entry)
                for name, entry in snapshot.skill_index.items()
            },
        }
        # 先写临时文件，再替换正式文件，减少中断时留下半写入状态的概率。
        tmp_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(self.state_path)


def _cached_file_to_dict(record: CachedFileRecord) -> dict[str, Any]:
    return {
        "path": record.path,
        "sha256": record.sha256,
        "size_bytes": record.size_bytes,
        "char_count": record.char_count,
        "language": record.language,
        "inferred_role": record.inferred_role,
        "priority": record.priority,
        "priority_reasons": record.priority_reasons,
        "gitignored": record.gitignored,
        "selected": record.selected,
        "config_summary": asdict(record.config_summary)
        if record.config_summary
        else None,
        "source_summary": asdict(record.source_summary)
        if record.source_summary
        else None,
    }


def _cached_file_from_dict(path: str, data: dict[str, Any]) -> CachedFileRecord:
    config_summary_data = data.get("config_summary")
    source_summary_data = data.get("source_summary")
    return CachedFileRecord(
        path=path,
        sha256=str(data["sha256"]),
        size_bytes=int(data["size_bytes"]),
        char_count=int(data["char_count"]),
        language=data.get("language"),
        inferred_role=str(data["inferred_role"]),
        priority=int(data["priority"]),
        priority_reasons=list(data.get("priority_reasons", [])),
        gitignored=bool(data.get("gitignored", False)),
        selected=bool(data.get("selected", False)),
        config_summary=_config_summary_from_dict(config_summary_data)
        if config_summary_data
        else None,
        source_summary=_source_summary_from_dict(source_summary_data)
        if source_summary_data
        else None,
    )


def _config_summary_from_dict(data: dict[str, Any]) -> ConfigSummary:
    return ConfigSummary(
        path=str(data["path"]),
        kind=str(data["kind"]),
        summary=str(data["summary"]),
        framework_signals=list(data.get("framework_signals", [])),
        entrypoints=list(data.get("entrypoints", [])),
        details=dict(data.get("details", {})),
    )


def _source_summary_from_dict(data: dict[str, Any]) -> SourceFileSummary:
    return SourceFileSummary(
        path=str(data["path"]),
        inferred_role=str(data["inferred_role"]),
        language=data.get("language"),
        imports=list(data.get("imports", [])),
        exports=list(data.get("exports", [])),
        import_details=[
            ImportInfo(**item)
            for item in data.get("import_details", [])
        ],
        export_details=[
            ExportInfo(**item)
            for item in data.get("export_details", [])
        ],
        top_level_symbols=list(data.get("top_level_symbols", [])),
        classes=list(data.get("classes", [])),
        functions=list(data.get("functions", [])),
        function_details=[
            FunctionInfo(**item)
            for item in data.get("function_details", [])
        ],
        class_details=[
            ClassInfo(**item)
            for item in data.get("class_details", [])
        ],
        methods=list(data.get("methods", [])),
        decorators=list(data.get("decorators", [])),
        routes=[
            RouteSummary(**route)
            for route in data.get("routes", [])
        ],
        models_or_schemas=list(data.get("models_or_schemas", [])),
        state_signals=list(data.get("state_signals", [])),
        export_styles=list(data.get("export_styles", [])),
        file_structure=list(data.get("file_structure", [])),
        internal_dependencies=list(data.get("internal_dependencies", [])),
        short_doc_summary=str(data.get("short_doc_summary", "")),
        notes=list(data.get("notes", [])),
        confidence=float(data.get("confidence", 0.0)),
    )
