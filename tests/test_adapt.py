from __future__ import annotations

from pathlib import Path

from code2skill.adapt import (
    COPY_MANIFEST_NAME,
    MANAGED_BLOCK_END,
    MANAGED_BLOCK_START,
    adapt_skills,
)


def test_adapt_merge_preserves_existing_user_content(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = _write_skills(repo_path)
    agents_path = repo_path / "AGENTS.md"
    agents_path.write_text("# Team Notes\n\nKeep this text.\n", encoding="utf-8")

    written = adapt_skills(
        target="codex",
        source_dir=skills_dir,
        destination_root=repo_path,
    )

    content = agents_path.read_text(encoding="utf-8")
    assert written == [agents_path.resolve()]
    assert "# Team Notes" in content
    assert "Keep this text." in content
    assert MANAGED_BLOCK_START in content
    assert MANAGED_BLOCK_END in content
    assert "# Backend" in content


def test_adapt_merge_replaces_existing_managed_block_idempotently(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = _write_skills(repo_path)
    agents_path = repo_path / "AGENTS.md"
    agents_path.write_text(
        "\n".join(
            [
                "# Team Notes",
                "",
                MANAGED_BLOCK_START,
                "# Old",
                MANAGED_BLOCK_END,
                "",
            ]
        ),
        encoding="utf-8",
    )

    adapt_skills(target="codex", source_dir=skills_dir, destination_root=repo_path)
    first = agents_path.read_text(encoding="utf-8")
    adapt_skills(target="codex", source_dir=skills_dir, destination_root=repo_path)
    second = agents_path.read_text(encoding="utf-8")

    assert first == second
    assert "# Old" not in second
    assert second.count(MANAGED_BLOCK_START) == 1
    assert second.count(MANAGED_BLOCK_END) == 1
    assert "# Backend" in second


def test_adapt_all_writes_each_target(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = _write_skills(repo_path)

    written = adapt_skills(
        target="all",
        source_dir=skills_dir,
        destination_root=repo_path,
    )

    assert {path.relative_to(repo_path.resolve()).as_posix() for path in written} == {
        ".cursor/rules/backend.md",
        ".cursor/rules/index.md",
        f".cursor/rules/{COPY_MANIFEST_NAME}",
        ".github/copilot-instructions.md",
        ".windsurfrules",
        "AGENTS.md",
        "CLAUDE.md",
    }


def test_adapt_cursor_copy_removes_manifest_tracked_stale_skills(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = _write_skills(repo_path)

    adapt_skills(target="cursor", source_dir=skills_dir, destination_root=repo_path)
    (skills_dir / "backend.md").unlink()
    (skills_dir / "index.md").write_text("# Index\n\n[api.md](./api.md)\n", encoding="utf-8")
    (skills_dir / "api.md").write_text("# Api\n", encoding="utf-8")

    adapt_skills(target="cursor", source_dir=skills_dir, destination_root=repo_path)

    cursor_rules = repo_path / ".cursor" / "rules"
    assert not (cursor_rules / "backend.md").exists()
    assert (cursor_rules / "api.md").read_text(encoding="utf-8") == "# Api\n"
    assert COPY_MANIFEST_NAME in {path.name for path in cursor_rules.iterdir()}


def test_adapt_cursor_copy_preserves_unmanaged_markdown_rules(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = _write_skills(repo_path)
    cursor_rules = repo_path / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "team-rule.md").write_text("# Team Rule\n", encoding="utf-8")

    adapt_skills(target="cursor", source_dir=skills_dir, destination_root=repo_path)

    assert (cursor_rules / "team-rule.md").read_text(encoding="utf-8") == "# Team Rule\n"


def test_adapt_rejects_empty_skill_directory(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = repo_path / ".code2skill" / "skills"
    skills_dir.mkdir(parents=True)

    try:
        adapt_skills(target="codex", source_dir=skills_dir, destination_root=repo_path)
    except ValueError as exc:
        assert "expected index.md and at least one Skill .md file" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("adapt_skills should reject an empty generated skills directory")


def test_adapt_rejects_index_without_skill_files(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = repo_path / ".code2skill" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "index.md").write_text("# Index\n", encoding="utf-8")

    try:
        adapt_skills(target="codex", source_dir=skills_dir, destination_root=repo_path)
    except ValueError as exc:
        assert "Run `code2skill scan .` without `--structure-only` first" in str(exc)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("adapt_skills should reject a source with no Skill files")


def _write_skills(repo_path: Path) -> Path:
    skills_dir = repo_path / ".code2skill" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "index.md").write_text(
        "# Index\n\n[backend.md](./backend.md)\n",
        encoding="utf-8",
    )
    (skills_dir / "backend.md").write_text("# Backend\n", encoding="utf-8")
    return skills_dir
