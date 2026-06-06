from __future__ import annotations

from code2skill.models import (
    DirectorySummary,
    EvidenceCoverage,
    ProjectProfile,
    SkillRecommendation,
    SkillBlueprint,
    SourceFileSummary,
)
from code2skill.renderers.markdown_renderer import render_adoption_guide, render_project_summary


def test_project_summary_includes_directory_section_when_entrypoints_exist() -> None:
    blueprint = _sample_blueprint()

    rendered = render_project_summary(blueprint)

    assert "## Entrypoints" in rendered
    assert "## Evidence Coverage" in rendered
    assert "high_signal_files: 1/1" in rendered
    assert "internal_dependencies=2" in rendered
    assert "## Directory Summary" in rendered
    assert "- src: 2 files;" in rendered


def test_adoption_guide_explains_repository_workflow_and_readiness_check() -> None:
    rendered = render_adoption_guide(_sample_blueprint())

    assert "# Adoption Guide" in rendered
    assert "## Repository Scenario" in rendered
    assert "Run `code2skill estimate .`" in rendered
    assert "Run `code2skill doctor . --target codex`" in rendered
    assert "`backend`" in rendered


def _sample_blueprint() -> SkillBlueprint:
    return SkillBlueprint(
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
        recommended_skills=[
            SkillRecommendation(
                name="backend",
                purpose="Explain backend boundaries",
                scope="src",
                source_evidence=["src/app.py"],
                why_split="backend is the main area",
                likely_inputs=["src/app.py"],
                likely_outputs=["skills/backend.md"],
            )
        ],
        evidence_coverage=EvidenceCoverage(
            source_file_count=1,
            high_signal_file_count=1,
            class_count=0,
            function_count=1,
            route_count=0,
            call_target_count=2,
            type_reference_count=0,
            data_flow_edge_count=0,
            dynamic_import_count=0,
            raised_exception_count=0,
            model_or_schema_count=0,
            internal_dependency_count=2,
        ),
    )
