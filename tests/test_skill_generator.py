from __future__ import annotations

from pathlib import Path

from code2skill.models import (
    CachedFileRecord,
    FileDiffPatch,
    ProjectProfile,
    SkillBlueprint,
    SkillPlan,
    SkillPlanEntry,
    SkillRecommendation,
    SourceFileSummary,
    StateSnapshot,
)
from code2skill.skill_generator import SkillGenerator


class FakeBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self.response


def test_generate_incremental_uses_diff_and_updates_only_changed_sections(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "services").mkdir()
    (repo_path / "services" / "user_service.py").write_text(
        "def ping():\n    return 'pong-v2'\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    skill_dir = output_dir / "skills"
    skill_dir.mkdir(parents=True)
    (skill_dir / "backend-architecture.md").write_text(
        "# Backend Architecture\n\n"
        "## Overview\n"
        "Keep this section unchanged.\n\n"
        "## Core Rules\n"
        "- Old rule\n\n"
        "## Common Flows\n"
        "- Old flow\n",
        encoding="utf-8",
    )

    backend = FakeBackend(
        '{"updated_sections":[{"heading":"Core Rules","content":"## Core Rules\\n- Services return stable string payloads. Source: services/user_service.py:ping"}]}'
    )
    generator = SkillGenerator(
        backend=backend,
        repo_path=repo_path,
        output_dir=output_dir,
        max_inline_chars=4096,
    )
    plan = SkillPlan(
        skills=[
            SkillPlanEntry(
                name="backend-architecture",
                title="Backend Architecture",
                scope="Service layer",
                why="Service implementations define architecture rules.",
                read_files=["app.py"],
                read_reason="Entrypoint file.",
            )
        ]
    )
    blueprint = SkillBlueprint(
        project_profile=ProjectProfile(
            name="demo",
            repo_type="backend",
            languages=["python"],
            framework_signals=[],
            package_topology="flat",
            entrypoints=["app.py"],
        ),
        tech_stack={"language": ["python"]},
        domains=[],
        directory_summary=[],
        key_configs=[],
        core_modules=[],
        important_apis=[],
        abstract_rules=[],
        concrete_workflows=[],
        recommended_skills=[
            SkillRecommendation(
                name="backend-architecture",
                purpose="Service rules",
                scope="Service layer",
                source_evidence=["services/user_service.py"],
                why_split="The service layer is a major change point.",
                likely_inputs=[],
                likely_outputs=[],
            )
        ],
    )
    previous_state = StateSnapshot(
        version=1,
        generated_at="2026-03-16T00:00:00+00:00",
        repo_root=str(repo_path),
        head_commit="deadbeef",
        selected_paths=["services/user_service.py"],
        directory_counts={},
        gitignore_patterns=[],
        discovery_method="git",
        candidate_count=1,
        total_chars=0,
        bytes_read=0,
        files={
            "services/user_service.py": CachedFileRecord(
                path="services/user_service.py",
                sha256="old",
                size_bytes=24,
                char_count=24,
                language="python",
                inferred_role="service",
                priority=1,
                priority_reasons=["service"],
                gitignored=False,
                source_summary=SourceFileSummary(
                    path="services/user_service.py",
                    inferred_role="service",
                    language="python",
                    functions=["ping"],
                    short_doc_summary="Old ping implementation.",
                ),
            )
        },
        reverse_dependencies={},
        skill_index={},
    )
    changed_diff = FileDiffPatch(
        path="services/user_service.py",
        change_type="modify",
        patch=(
            "diff --git a/services/user_service.py b/services/user_service.py\n"
            "--- a/services/user_service.py\n"
            "+++ b/services/user_service.py\n"
            "@@ -1 +1,2 @@\n"
            "-def ping():\n"
            "+def ping():\n"
            "+    return 'pong-v2'\n"
        ),
    )

    artifacts = generator.generate_incremental(
        blueprint=blueprint,
        plan=plan,
        affected_skill_names=["backend-architecture"],
        changed_files=["services/user_service.py"],
        changed_diffs=[changed_diff],
        previous_state=previous_state,
    )

    updated = artifacts["skills/backend-architecture.md"]
    prompt = backend.calls[0][0]

    assert "services/user_service.py" in prompt
    assert "@@ -1 +1,2 @@" in prompt
    assert "## Overview\nKeep this section unchanged." in updated
    assert (
        "## Core Rules\n<!-- UPDATED -->\n- Services return stable string payloads. Source: services/user_service.py:ping"
        in updated
    )
    assert "- Old rule" not in updated
