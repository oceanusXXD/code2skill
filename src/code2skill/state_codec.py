from __future__ import annotations

from dataclasses import asdict
from typing import Any

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


def snapshot_to_dict(snapshot: StateSnapshot) -> dict[str, Any]:
    return {
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
        "files": {path: cached_file_to_dict(record) for path, record in snapshot.files.items()},
        "reverse_dependencies": snapshot.reverse_dependencies,
        "skill_index": {name: asdict(entry) for name, entry in snapshot.skill_index.items()},
    }


def snapshot_from_dict(data: dict[str, Any]) -> StateSnapshot:
    return StateSnapshot(
        version=int(data["version"]),
        generated_at=str(data["generated_at"]),
        repo_root=str(data["repo_root"]),
        head_commit=data.get("head_commit"),
        selected_paths=list(data.get("selected_paths", [])),
        directory_counts={str(key): int(value) for key, value in data.get("directory_counts", {}).items()},
        gitignore_patterns=list(data.get("gitignore_patterns", [])),
        discovery_method=str(data.get("discovery_method", "filesystem")),
        candidate_count=int(data.get("candidate_count", 0)),
        total_chars=int(data.get("total_chars", 0)),
        bytes_read=int(data.get("bytes_read", 0)),
        files={path: cached_file_from_dict(path, payload) for path, payload in data.get("files", {}).items()},
        reverse_dependencies={str(key): list(value) for key, value in data.get("reverse_dependencies", {}).items()},
        skill_index={name: SkillImpactIndexEntry(**payload) for name, payload in data.get("skill_index", {}).items()},
    )


def cached_file_to_dict(record: CachedFileRecord) -> dict[str, Any]:
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
        "config_summary": asdict(record.config_summary) if record.config_summary else None,
        "source_summary": asdict(record.source_summary) if record.source_summary else None,
    }


def cached_file_from_dict(path: str, data: dict[str, Any]) -> CachedFileRecord:
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
        config_summary=config_summary_from_dict(config_summary_data) if config_summary_data else None,
        source_summary=source_summary_from_dict(source_summary_data) if source_summary_data else None,
    )


def config_summary_from_dict(data: dict[str, Any]) -> ConfigSummary:
    return ConfigSummary(
        path=str(data["path"]),
        kind=str(data["kind"]),
        summary=str(data["summary"]),
        framework_signals=list(data.get("framework_signals", [])),
        entrypoints=list(data.get("entrypoints", [])),
        details=dict(data.get("details", {})),
    )


def source_summary_from_dict(data: dict[str, Any]) -> SourceFileSummary:
    return SourceFileSummary(
        path=str(data["path"]),
        inferred_role=str(data["inferred_role"]),
        language=data.get("language"),
        imports=list(data.get("imports", [])),
        exports=list(data.get("exports", [])),
        import_details=[ImportInfo(**item) for item in data.get("import_details", [])],
        export_details=[ExportInfo(**item) for item in data.get("export_details", [])],
        top_level_symbols=list(data.get("top_level_symbols", [])),
        classes=list(data.get("classes", [])),
        functions=list(data.get("functions", [])),
        function_details=[FunctionInfo(**item) for item in data.get("function_details", [])],
        class_details=[ClassInfo(**item) for item in data.get("class_details", [])],
        methods=list(data.get("methods", [])),
        decorators=list(data.get("decorators", [])),
        routes=[RouteSummary(**route) for route in data.get("routes", [])],
        models_or_schemas=list(data.get("models_or_schemas", [])),
        state_signals=list(data.get("state_signals", [])),
        export_styles=list(data.get("export_styles", [])),
        file_structure=list(data.get("file_structure", [])),
        internal_dependencies=list(data.get("internal_dependencies", [])),
        short_doc_summary=str(data.get("short_doc_summary", "")),
        notes=list(data.get("notes", [])),
        confidence=float(data.get("confidence", 0.0)),
    )
