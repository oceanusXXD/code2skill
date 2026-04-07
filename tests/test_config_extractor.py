from __future__ import annotations

from pathlib import Path

from code2skill.extractors.config_extractor import ConfigExtractor
from code2skill.models import FileCandidate


def test_config_extractor_ignores_readme_documents() -> None:
    extractor = ConfigExtractor()
    candidate = FileCandidate(
        absolute_path=Path("/repo/README.md"),
        relative_path=Path("README.md"),
        size_bytes=24,
        char_count=24,
        sha256="deadbeef",
        language=None,
        inferred_role="documentation",
        priority=1,
        priority_reasons=["high-value-doc"],
        content="# Project Title\n\nRepository guide.\n",
    )

    summary = extractor.extract(candidate)

    assert summary is None
