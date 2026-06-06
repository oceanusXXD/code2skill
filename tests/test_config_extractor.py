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


def test_config_extractor_accepts_utf8_bom_pyproject() -> None:
    extractor = ConfigExtractor()
    candidate = FileCandidate(
        absolute_path=Path("/repo/pyproject.toml"),
        relative_path=Path("pyproject.toml"),
        size_bytes=120,
        char_count=120,
        sha256="deadbeef",
        language=None,
        inferred_role="configuration",
        priority=1,
        priority_reasons=["config"],
        content=(
            "\ufeff[project]\n"
            'name = "demo"\n'
            'dependencies = ["fastapi>=0.100", "pytest"]\n'
            "\n"
            "[project.scripts]\n"
            'demo = "demo.cli:main"\n'
        ),
    )

    summary = extractor.extract(candidate)

    assert summary is not None
    assert summary.kind == "pyproject"
    assert "fastapi" in summary.framework_signals
    assert summary.entrypoints == ["demo.cli:main"]
    assert summary.details["name"] == "demo"
