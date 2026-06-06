from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .capabilities.adapt.targets import get_target_definitions

MANAGED_BLOCK_START = "<!-- code2skill:start -->"
MANAGED_BLOCK_END = "<!-- code2skill:end -->"
COPY_MANIFEST_NAME = ".code2skill-manifest.json"


def adapt_skills(
    target: str,
    source_dir: Path | str = ".code2skill/skills",
    destination_root: Path | str = ".",
) -> list[Path]:
    destination_root_path = Path(destination_root).expanduser().resolve()
    source_path = _resolve_path(destination_root_path, source_dir)
    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError(f"Skill directory does not exist: {source_path}")
    _validate_skill_source(source_path)

    written: list[Path] = []
    for target_definition in get_target_definitions(target):
        destination = (destination_root_path / target_definition.destination).resolve()
        if target_definition.mode == "copy":
            written.extend(_copy_skills(source_path, destination))
            continue
        written.append(_merge_skills(source_path, destination))
    return written


def _resolve_path(root: Path, candidate: Path | str) -> Path:
    path = Path(candidate).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _validate_skill_source(source_dir: Path) -> None:
    index_path = source_dir / "index.md"
    skill_files = [
        path
        for path in source_dir.glob("*.md")
        if path.name != "index.md"
    ]
    if not index_path.is_file() or not skill_files:
        raise ValueError(
            "Generated skills directory is incomplete: expected index.md and at least "
            "one Skill .md file. Run `code2skill scan .` without `--structure-only` first."
        )


def _copy_skills(source_dir: Path, destination_dir: Path) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    skill_files = sorted(source_dir.glob("*.md"))
    current_names = {skill_file.name for skill_file in skill_files}
    manifest_path = destination_dir / COPY_MANIFEST_NAME
    previous_names = _read_copy_manifest(manifest_path)
    for stale_name in sorted(previous_names - current_names):
        if not _is_direct_markdown_filename(stale_name):
            continue
        stale_path = destination_dir / stale_name
        if stale_path.is_file():
            stale_path.unlink()

    written: list[Path] = []
    for skill_file in skill_files:
        destination = destination_dir / skill_file.name
        shutil.copyfile(skill_file, destination)
        written.append(destination)
    _write_copy_manifest(manifest_path, current_names)
    written.append(manifest_path)
    return written


def _read_copy_manifest(manifest_path: Path) -> set[str]:
    if not manifest_path.is_file():
        return set()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Copy manifest is not valid JSON: {manifest_path}") from exc
    raw_files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(raw_files, list) or not all(isinstance(name, str) for name in raw_files):
        raise ValueError(f"Copy manifest does not match the expected schema: {manifest_path}")
    invalid_names = [name for name in raw_files if not _is_direct_markdown_filename(name)]
    if invalid_names:
        raise ValueError(f"Copy manifest contains invalid filenames: {', '.join(invalid_names[:3])}")
    return set(raw_files)


def _write_copy_manifest(manifest_path: Path, filenames: set[str]) -> None:
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "files": sorted(filenames),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _is_direct_markdown_filename(filename: str) -> bool:
    return Path(filename).name == filename and filename.endswith(".md")


def _merge_skills(source_dir: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    managed_content = _render_managed_block(_render_merged_skills(source_dir))
    if destination.exists():
        existing = destination.read_text(encoding="utf-8")
        destination.write_text(
            _replace_or_append_managed_block(existing, managed_content),
            encoding="utf-8",
        )
        return destination
    destination.write_text(f"{managed_content}\n", encoding="utf-8")
    return destination


def _render_merged_skills(source_dir: Path) -> str:
    parts: list[str] = []
    index_path = source_dir / "index.md"
    if index_path.exists():
        parts.append(index_path.read_text(encoding="utf-8").strip())
    for skill_file in _ordered_skill_files(source_dir):
        parts.append(skill_file.read_text(encoding="utf-8").strip())
    return "\n\n---\n\n".join(part for part in parts if part).strip()


def _render_managed_block(content: str) -> str:
    return "\n".join(
        [
            MANAGED_BLOCK_START,
            content.strip(),
            MANAGED_BLOCK_END,
        ]
    ).strip()


def _replace_or_append_managed_block(existing: str, managed_content: str) -> str:
    if MANAGED_BLOCK_START in existing and MANAGED_BLOCK_END in existing:
        pattern = re.compile(
            f"{re.escape(MANAGED_BLOCK_START)}.*?{re.escape(MANAGED_BLOCK_END)}",
            flags=re.DOTALL,
        )
        return pattern.sub(managed_content, existing, count=1).rstrip() + "\n"
    prefix = existing.rstrip()
    if not prefix:
        return f"{managed_content}\n"
    return f"{prefix}\n\n{managed_content}\n"


def _ordered_skill_files(source_dir: Path) -> list[Path]:
    skill_files = {
        path.name: path
        for path in source_dir.glob("*.md")
        if path.name != "index.md"
    }
    ordered: list[Path] = []
    seen: set[str] = set()

    index_path = source_dir / "index.md"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        for filename in re.findall(r"\]\(\./([^)]+\.md)\)", index_content):
            if filename in skill_files and filename not in seen:
                seen.add(filename)
                ordered.append(skill_files[filename])

    for name in sorted(skill_files):
        if name in seen:
            continue
        ordered.append(skill_files[name])
    return ordered
