from __future__ import annotations

from pathlib import Path

import pytest

from code2skill.adapt import COPY_MANIFEST_NAME, MANAGED_BLOCK_END, MANAGED_BLOCK_START
from code2skill.capabilities.adoption_service import inspect_adoption_readiness
from code2skill.skill_planner import render_skill_plan
from code2skill.models import SkillPlan, SkillPlanEntry


def test_adoption_readiness_reports_missing_bundle_with_next_steps(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    readiness = inspect_adoption_readiness(repo_path, target="codex")

    assert readiness.ready is False
    assert readiness.score < 100
    assert repo_path / ".code2skill" in readiness.missing_paths
    assert any("code2skill scan . --structure-only" in step for step in readiness.next_steps)
    assert any(check.name == "target_codex" for check in readiness.checks)


def test_adoption_readiness_passes_when_bundle_and_target_are_present(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    output_dir = repo_path / ".code2skill"
    skills_dir = output_dir / "skills"
    state_dir = output_dir / "state"
    skills_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    (output_dir / "project-summary.md").write_text("# Summary\n", encoding="utf-8")
    (output_dir / "adoption-guide.md").write_text("# Adoption\n", encoding="utf-8")
    (output_dir / "report.json").write_text("{}", encoding="utf-8")
    (output_dir / "skill-plan.json").write_text(
        _render_plan("backend"),
        encoding="utf-8",
    )
    (skills_dir / "index.md").write_text(
        "# Index\n\n[backend.md](./backend.md)\n",
        encoding="utf-8",
    )
    (skills_dir / "backend.md").write_text("# Backend\n", encoding="utf-8")
    (state_dir / "analysis-state.json").write_text(
        _render_state(repo_path),
        encoding="utf-8",
    )
    (repo_path / "AGENTS.md").write_text(
        f"{MANAGED_BLOCK_START}\n# Agents\n{MANAGED_BLOCK_END}\n",
        encoding="utf-8",
    )

    readiness = inspect_adoption_readiness(repo_path, target="codex")

    assert readiness.ready is True
    assert readiness.score == 100
    assert readiness.missing_paths == []
    assert readiness.next_steps == []


def test_adoption_readiness_validates_cursor_copy_target(tmp_path: Path) -> None:
    repo_path, output_dir, skills_dir = _write_minimal_bundle(tmp_path)
    cursor_rules = repo_path / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "index.md").write_text(
        (skills_dir / "index.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (cursor_rules / "backend.md").write_text("# Backend\n", encoding="utf-8")
    (cursor_rules / COPY_MANIFEST_NAME).write_text(
        '{"version": 1, "files": ["backend.md", "index.md"]}\n',
        encoding="utf-8",
    )

    readiness = inspect_adoption_readiness(repo_path, target="cursor")

    target_check = next(check for check in readiness.checks if check.name == "target_cursor")
    assert target_check.status == "ok"


def test_adoption_readiness_detects_stale_cursor_copy_target(tmp_path: Path) -> None:
    repo_path, _, skills_dir = _write_minimal_bundle(tmp_path)
    cursor_rules = repo_path / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "index.md").write_text(
        (skills_dir / "index.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (cursor_rules / "backend.md").write_text("# Old Backend\n", encoding="utf-8")

    readiness = inspect_adoption_readiness(repo_path, target="cursor")

    target_check = next(check for check in readiness.checks if check.name == "target_cursor")
    assert target_check.status == "invalid"
    assert "out of date" in target_check.message


def test_adoption_readiness_detects_cursor_manifest_mismatch(tmp_path: Path) -> None:
    repo_path, _, skills_dir = _write_minimal_bundle(tmp_path)
    cursor_rules = repo_path / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "index.md").write_text(
        (skills_dir / "index.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (cursor_rules / "backend.md").write_text("# Backend\n", encoding="utf-8")
    (cursor_rules / COPY_MANIFEST_NAME).write_text(
        '{"version": 1, "files": ["backend.md", "index.md", "old.md"]}\n',
        encoding="utf-8",
    )

    readiness = inspect_adoption_readiness(repo_path, target="cursor")

    target_check = next(check for check in readiness.checks if check.name == "target_cursor")
    assert target_check.status == "invalid"
    assert "manifest" in target_check.message


def test_adoption_readiness_requires_cursor_manifest(tmp_path: Path) -> None:
    repo_path, _, skills_dir = _write_minimal_bundle(tmp_path)
    cursor_rules = repo_path / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)
    (cursor_rules / "index.md").write_text(
        (skills_dir / "index.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (cursor_rules / "backend.md").write_text("# Backend\n", encoding="utf-8")

    readiness = inspect_adoption_readiness(repo_path, target="cursor")

    target_check = next(check for check in readiness.checks if check.name == "target_cursor")
    assert target_check.status == "missing"
    assert "manifest is missing" in target_check.message


def test_adoption_readiness_rejects_unknown_target(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    with pytest.raises(ValueError, match="Unsupported target"):
        inspect_adoption_readiness(repo_path, target="unknown")


def test_adoption_readiness_detects_broken_skill_index_link(tmp_path: Path) -> None:
    repo_path, output_dir, skills_dir = _write_minimal_bundle(tmp_path)
    (skills_dir / "index.md").write_text(
        "# Index\n\n[missing.md](./missing.md)\n",
        encoding="utf-8",
    )

    readiness = inspect_adoption_readiness(repo_path)

    skill_check = next(check for check in readiness.checks if check.name == "skill_products")
    assert skill_check.status == "invalid"
    assert "missing.md" in skill_check.message


def test_adoption_readiness_detects_plan_without_skill_file(tmp_path: Path) -> None:
    repo_path, output_dir, skills_dir = _write_minimal_bundle(tmp_path)
    (output_dir / "skill-plan.json").write_text(
        _render_plan("missing"),
        encoding="utf-8",
    )

    readiness = inspect_adoption_readiness(repo_path)

    plan_check = next(check for check in readiness.checks if check.name == "skill_plan")
    assert plan_check.status == "invalid"
    assert "missing.md" in plan_check.message


def test_adoption_readiness_detects_target_without_managed_block(tmp_path: Path) -> None:
    repo_path, _, _ = _write_minimal_bundle(tmp_path)
    (repo_path / "AGENTS.md").write_text("# Hand Written\n", encoding="utf-8")

    readiness = inspect_adoption_readiness(repo_path, target="codex")

    target_check = next(check for check in readiness.checks if check.name == "target_codex")
    assert target_check.status == "missing"


def _write_minimal_bundle(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_path = tmp_path / "repo"
    output_dir = repo_path / ".code2skill"
    skills_dir = output_dir / "skills"
    state_dir = output_dir / "state"
    skills_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    (output_dir / "project-summary.md").write_text("# Summary\n", encoding="utf-8")
    (output_dir / "adoption-guide.md").write_text("# Adoption\n", encoding="utf-8")
    (output_dir / "report.json").write_text("{}", encoding="utf-8")
    (output_dir / "skill-plan.json").write_text(
        _render_plan("backend"),
        encoding="utf-8",
    )
    (skills_dir / "index.md").write_text(
        "# Index\n\n[backend.md](./backend.md)\n",
        encoding="utf-8",
    )
    (skills_dir / "backend.md").write_text("# Backend\n", encoding="utf-8")
    (state_dir / "analysis-state.json").write_text(
        _render_state(repo_path),
        encoding="utf-8",
    )
    return repo_path, output_dir, skills_dir


def _render_plan(name: str) -> str:
    return render_skill_plan(
        SkillPlan(
            skills=[
                SkillPlanEntry(
                    name=name,
                    title=name.title(),
                    scope="backend",
                    why="backend evidence",
                    read_files=["src/app.py"],
                    read_reason="backend evidence",
                )
            ]
        )
    )


def _render_state(repo_path: Path) -> str:
    return """{
  "version": 1,
  "generated_at": "2026-04-07T00:00:00+00:00",
  "repo_root": "%s",
  "head_commit": null,
  "selected_paths": [],
  "directory_counts": {},
  "gitignore_patterns": [],
  "discovery_method": "filesystem",
  "candidate_count": 0,
  "total_chars": 0,
  "bytes_read": 0,
  "files": {},
  "reverse_dependencies": {},
  "skill_index": {}
}
""" % repo_path.resolve().as_posix()
