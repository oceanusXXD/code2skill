from __future__ import annotations

from code2skill.config import PricingConfig
from code2skill.costing import CostEstimator
from code2skill.models import ProjectProfile, SkillBlueprint, SkillRecommendation


def test_cost_assumptions_are_ascii_and_user_readable() -> None:
    estimator = CostEstimator(PricingConfig())
    blueprint = SkillBlueprint(
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
        recommended_skills=[
            SkillRecommendation(
                name="backend-flow",
                purpose="backend flow",
                scope="backend",
                source_evidence=[],
                why_split="backend evidence",
                likely_inputs=[],
                likely_outputs=[],
            )
        ],
    )

    first = estimator.estimate_first_generation(blueprint, {"project-summary.md": "# Summary"})
    rewrite = estimator.estimate_incremental_rewrite(
        blueprint,
        {"references/architecture.md": "# Architecture"},
        affected_skills=["backend-flow"],
        changed_files=["src/app.py"],
        affected_files=["src/app.py"],
    )
    patch = estimator.estimate_incremental_patch(rewrite)
    empty = estimator.estimate_incremental_patch(
        estimator.estimate_incremental_rewrite(
            blueprint,
            {},
            affected_skills=[],
            changed_files=[],
            affected_files=[],
        )
    )

    assumptions = [
        *first.assumptions,
        *rewrite.assumptions,
        *patch.assumptions,
        *empty.assumptions,
    ]
    assert assumptions
    assert all(text.isascii() for text in assumptions)
    assert all(text.strip() for text in assumptions)
    assert not any("?" in text for text in assumptions)
