from __future__ import annotations

from code2skill.models import (
    DirectorySummary,
    ProjectProfile,
    SkillBlueprint,
    SourceFileSummary,
)
from code2skill.renderers.markdown_renderer import render_project_summary


def test_project_summary_includes_directory_section_when_entrypoints_exist() -> None:
    blueprint = SkillBlueprint(
        project_profile=ProjectProfile(
            name="demo",
            repo_type="backend",
            languages=["python"],
            framework_signals=[],
            package_topology="flat",
            entrypoints=["src/app.py"],
        ),
        tech_stack={"languages": ["python"]},
        domains=[],
        directory_summary=[
            DirectorySummary(
                path="src",
                file_count=2,
                dominant_roles=["entrypoint", "service"],
                sample_files=["src/app.py", "src/service.py"],
            )
        ],
        key_configs=[],
        core_modules=[
            SourceFileSummary(
                path="src/app.py",
                inferred_role="entrypoint",
                language="python",
                functions=["main"],
                short_doc_summary="Main entrypoint",
            )
        ],
        important_apis=[],
        abstract_rules=[],
        concrete_workflows=[],
        recommended_skills=[],
    )

    rendered = render_project_summary(blueprint)

    assert "## Entrypoints" in rendered
    assert "## Directory Summary" in rendered
    assert "- src: 2 files;" in rendered
