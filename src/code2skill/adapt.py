from __future__ import annotations

import re
import shutil
from pathlib import Path


TARGETS = {
    "cursor": {
        "mode": "copy",
        "dest": ".cursor/rules/",
    },
    "claude": {
        "mode": "merge",
        "dest": "CLAUDE.md",
    },
    "codex": {
        "mode": "merge",
        "dest": "AGENTS.md",
    },
    "copilot": {
        "mode": "merge",
        "dest": ".github/copilot-instructions.md",
    },
    "windsurf": {
        "mode": "merge",
        "dest": ".windsurfrules",
    },
}


def adapt_skills(target: str, source_dir: Path | str = ".code2skill/skills") -> list[Path]:
    source_path = Path(source_dir).expanduser().resolve()
    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError(f"Skill directory does not exist: {source_path}")

    targets = list(TARGETS) if target == "all" else [target]
    written: list[Path] = []
    for target_name in targets:
        if target_name not in TARGETS:
            raise ValueError(f"Unsupported target: {target_name}")
        target_config = TARGETS[target_name]
        destination = (Path.cwd() / target_config["dest"]).resolve()
        if target_config["mode"] == "copy":
            written.extend(_copy_skills(source_path, destination))
            continue
        written.append(_merge_skills(source_path, destination))
    return written


def _copy_skills(source_dir: Path, destination_dir: Path) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for skill_file in sorted(source_dir.glob("*.md")):
        destination = destination_dir / skill_file.name
        shutil.copyfile(skill_file, destination)
        written.append(destination)
    return written


def _merge_skills(source_dir: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    index_path = source_dir / "index.md"
    if index_path.exists():
        parts.append(index_path.read_text(encoding="utf-8").strip())
    for skill_file in _ordered_skill_files(source_dir):
        parts.append(skill_file.read_text(encoding="utf-8").strip())
    destination.write_text("\n\n---\n\n".join(part for part in parts if part) + "\n", encoding="utf-8")
    return destination


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
