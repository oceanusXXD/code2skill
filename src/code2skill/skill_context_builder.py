from __future__ import annotations

import hashlib
from pathlib import Path

from .config import infer_language
from .extractors.config_extractor import ConfigExtractor
from .extractors.python_extractor import PythonExtractor
from .models import FileCandidate
from .scanner.prioritizer import FilePrioritizer
from .skill_incremental_context import render_config_summary, render_source_summary


def load_file_context(
    *,
    repo_path: Path,
    relative_path: str,
    max_inline_chars: int,
) -> dict[str, str] | None:
    absolute_path = repo_path / Path(relative_path)
    if not absolute_path.exists() or not absolute_path.is_file():
        return None
    content = absolute_path.read_text(encoding="utf-8", errors="ignore")
    if len(content) <= max_inline_chars:
        return {"path": relative_path, "content": content}
    return {
        "path": relative_path,
        "content": build_skeleton_from_content(
            repo_path=repo_path,
            relative_path=relative_path,
            content=content,
        ),
    }


def build_skeleton_from_content(
    *,
    repo_path: Path,
    relative_path: str,
    content: str,
) -> str:
    relative = Path(relative_path)
    language = infer_language(relative)
    _, reasons, role = FilePrioritizer().score(relative, language)
    candidate = FileCandidate(
        absolute_path=repo_path / relative,
        relative_path=relative,
        size_bytes=len(content.encode("utf-8")),
        char_count=len(content),
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        language=language,
        inferred_role=role,
        priority=0,
        priority_reasons=reasons,
        content=content,
        gitignored=False,
    )

    config_summary = ConfigExtractor().extract(candidate)
    if config_summary is not None:
        return render_config_summary(config_summary)
    if language == "python":
        return render_source_summary(PythonExtractor().extract(candidate))
    return content
