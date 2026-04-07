from __future__ import annotations

from pathlib import Path

from code2skill.models import CachedFileRecord, ConfigSummary, ProjectProfile, SkillBlueprint, SourceFileSummary, StateSnapshot
from code2skill.skill_incremental_context import load_current_context, load_previous_context


def test_load_current_context_reads_from_previous_state_repo_root(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    target = repo_root / "services" / "user_service.py"
    target.parent.mkdir(parents=True)
    target.write_text("def ping():\n    return 'pong'\n", encoding="utf-8")

    current = load_current_context(
        previous_state=StateSnapshot(
            version=1,
            generated_at="2026-04-07T00:00:00+00:00",
            repo_root=str(repo_root),
            head_commit=None,
            selected_paths=[],
            directory_counts={},
            gitignore_patterns=[],
            discovery_method="git",
            candidate_count=0,
            total_chars=0,
            bytes_read=0,
            files={},
            reverse_dependencies={},
            skill_index={},
        ),
        blueprint=SkillBlueprint(
            project_profile=ProjectProfile(
                name="demo",
                repo_type="backend",
                languages=["python"],
                framework_signals=[],
                package_topology="flat",
                entrypoints=[],
            ),
            tech_stack={},
            domains=[],
            directory_summary=[],
            key_configs=[],
            core_modules=[],
            important_apis=[],
            abstract_rules=[],
            concrete_workflows=[],
            recommended_skills=[],
        ),
        relative_path="services/user_service.py",
    )

    assert current == "def ping():\n    return 'pong'\n"


def test_load_previous_context_renders_cached_summaries() -> None:
    previous = StateSnapshot(
        version=1,
        generated_at="2026-04-07T00:00:00+00:00",
        repo_root="/repo",
        head_commit=None,
        selected_paths=[],
        directory_counts={},
        gitignore_patterns=[],
        discovery_method="git",
        candidate_count=0,
        total_chars=0,
        bytes_read=0,
        files={
            "pyproject.toml": CachedFileRecord(
                path="pyproject.toml",
                sha256="a",
                size_bytes=10,
                char_count=10,
                language=None,
                inferred_role="config",
                priority=1,
                priority_reasons=["config"],
                gitignored=False,
                config_summary=ConfigSummary(
                    path="pyproject.toml",
                    kind="pyproject",
                    summary="python project",
                    details={"name": "demo"},
                ),
            ),
            "src/app.py": CachedFileRecord(
                path="src/app.py",
                sha256="b",
                size_bytes=10,
                char_count=10,
                language="python",
                inferred_role="entrypoint",
                priority=1,
                priority_reasons=["entrypoint"],
                gitignored=False,
                source_summary=SourceFileSummary(
                    path="src/app.py",
                    inferred_role="entrypoint",
                    language="python",
                    functions=["main"],
                    short_doc_summary="app entrypoint",
                ),
            ),
        },
        reverse_dependencies={},
        skill_index={},
    )

    config_rendered = load_previous_context("pyproject.toml", previous)
    source_rendered = load_previous_context("src/app.py", previous)

    assert "[CONFIG SKELETON] pyproject.toml" in config_rendered
    assert "[SOURCE SKELETON] src/app.py" in source_rendered
