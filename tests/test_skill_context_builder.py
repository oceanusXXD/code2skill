from __future__ import annotations

from pathlib import Path

from code2skill.skill_context_builder import build_skeleton_from_content, load_file_context


def test_load_file_context_inlines_small_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("def main():\n    return 1\n", encoding="utf-8")

    context = load_file_context(
        repo_path=repo,
        relative_path="src/app.py",
        max_inline_chars=4096,
    )

    assert context == {"path": "src/app.py", "content": "def main():\n    return 1\n"}


def test_build_skeleton_from_content_uses_source_summary_for_python(tmp_path: Path) -> None:
    skeleton = build_skeleton_from_content(
        repo_path=tmp_path,
        relative_path="src/app.py",
        content="def main():\n    return 1\n",
    )

    assert "[SOURCE SKELETON] src/app.py" in skeleton
    assert "functions: main" in skeleton


def test_build_skeleton_from_content_includes_semantic_lines(tmp_path: Path) -> None:
    skeleton = build_skeleton_from_content(
        repo_path=tmp_path,
        relative_path="src/app.py",
        content=(
            "from pathlib import Path\n\n"
            "def main(root: str) -> Path:\n"
            "    path = Path(root)\n"
            "    return path\n"
        ),
    )

    assert "call_targets: Path" in skeleton
    assert "instantiated_classes: Path" in skeleton
    assert "type_references: Path" in skeleton
    assert "data_flow_edges: main:path<-Path" in skeleton
