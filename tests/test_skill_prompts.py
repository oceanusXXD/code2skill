from __future__ import annotations

from code2skill.models import (
    FileDiffPatch,
    ProjectProfile,
    SkillBlueprint,
    SkillPlanEntry,
    SkillRecommendation,
    StateSnapshot,
)
from code2skill.skill_markdown import ParsedSkillDocument, SkillDocumentSection
from code2skill.skill_prompts import build_default_generation_prompt, build_default_incremental_prompt


def test_generation_prompt_includes_hard_requirements_and_context() -> None:
    prompt = build_default_generation_prompt(
        SkillBlueprint(
            project_profile=ProjectProfile(
                name="demo",
                repo_type="backend",
                languages=["python"],
                framework_signals=[],
                package_topology="flat",
                entrypoints=["src/app.py"],
            ),
            tech_stack={"language": ["python"]},
            domains=[],
            directory_summary=[],
            key_configs=[],
            core_modules=[],
            important_apis=[],
            abstract_rules=[],
            concrete_workflows=[],
            recommended_skills=[],
        ),
        SkillPlanEntry(
            name="scanner-flow",
            title="Scanner Flow",
            scope="CLI entrypoint",
            why="The CLI starts the workflow.",
            read_files=["src/app.py"],
            read_reason="Entrypoint context",
        ),
        [{"path": "src/app.py", "content": "def main():\n    run()\n"}],
        [],
    )

    assert "Hard requirements:" in prompt
    assert "Output exactly the 5 sections listed below and nothing else." in prompt
    assert "--- src/app.py ---" in prompt


def test_incremental_prompt_includes_change_sections_and_existing_headings() -> None:
    prompt = build_default_incremental_prompt(
        SkillBlueprint(
            project_profile=ProjectProfile(
                name="demo",
                repo_type="backend",
                languages=["python"],
                framework_signals=[],
                package_topology="flat",
                entrypoints=["src/app.py"],
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
                    name="scanner-flow",
                    purpose="entrypoint",
                    scope="CLI",
                    source_evidence=["src/app.py"],
                    why_split="Entry path",
                    likely_inputs=[],
                    likely_outputs=[],
                )
            ],
        ),
        SkillPlanEntry(
            name="scanner-flow",
            title="Scanner Flow",
            scope="CLI entrypoint",
            why="The CLI starts the workflow.",
            read_files=["src/app.py"],
            read_reason="Entrypoint context",
        ),
        "# Scanner Flow\n\n## Overview\nKeep.\n",
        [
            FileDiffPatch(
                path="src/app.py",
                change_type="modify",
                patch="@@ -1 +1,2 @@\n-def main():\n+def main():\n+    run()\n",
            )
        ],
        StateSnapshot(
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
            files={},
            reverse_dependencies={},
            skill_index={},
        ),
        ParsedSkillDocument(
            title="# Scanner Flow",
            preamble="",
            sections=[SkillDocumentSection("Overview", "## Overview\nKeep.")],
        ),
    )

    assert "Existing section headings that may be updated:" in prompt
    assert "- Overview" in prompt
    assert "Changed files and supporting context:" in prompt
    assert "Unified diff:" in prompt
