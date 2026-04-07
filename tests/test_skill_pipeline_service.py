from __future__ import annotations

import importlib
from pathlib import Path

from code2skill.config import RunOptions, ScanConfig, ScanLimits
from code2skill.models import ProjectProfile, SkillBlueprint


class FakeBackend:
    def complete(self, prompt: str, system: str | None = None) -> str:
        return "{}"


class FakePlanner:
    def __init__(self, backend, max_skills: int) -> None:
        self.backend = backend
        self.max_skills = max_skills

    def plan(self, blueprint, repo_path):
        from code2skill.models import SkillPlan, SkillPlanEntry

        return SkillPlan(
            skills=[
                SkillPlanEntry(
                    name="backend-architecture",
                    title="Backend Architecture",
                    scope="service layer",
                    why="service files define the architecture",
                    read_files=["services/user_service.py"],
                    read_reason="service implementation",
                )
            ]
        )


class FakeGenerator:
    def __init__(self, backend, repo_path: Path, output_dir: Path, max_inline_chars: int) -> None:
        self.backend = backend
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.max_inline_chars = max_inline_chars

    def generate_all(self, blueprint, plan):
        return {"skills/backend-architecture.md": "# Backend Architecture\n"}


def test_skill_pipeline_service_runs_full_generation_when_plan_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service_module = importlib.import_module("code2skill.capabilities.generate_service")
    SkillPipelineService = service_module.SkillPipelineService

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    output_dir = tmp_path / ".code2skill"
    output_dir.mkdir()

    monkeypatch.setattr(service_module, "SkillPlanner", FakePlanner)
    monkeypatch.setattr(service_module, "SkillGenerator", FakeGenerator)

    service = SkillPipelineService(backend_factory=lambda provider, model: FakeBackend())
    blueprint = SkillBlueprint(
        project_profile=ProjectProfile(
            name="demo",
            repo_type="backend",
            languages=["python"],
            framework_signals=[],
            package_topology="flat",
            entrypoints=["app.py"],
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
    )

    artifacts, generated_skills, planned_skills = service.build_artifacts(
        config=ScanConfig(
            repo_path=repo_path,
            output_dir=output_dir,
            limits=ScanLimits(max_file_size_kb=4),
            run=RunOptions(command="ci", mode="auto", max_skills=4),
        ),
        effective_mode="incremental",
        repo_path=repo_path,
        output_dir=output_dir,
        blueprint=blueprint,
        previous_state=None,
        changed_files=[],
        changed_diffs=[],
        affected_files=[],
        affected_skill_names=[],
    )

    assert artifacts["skill-plan.json"]
    assert artifacts["skills/backend-architecture.md"] == "# Backend Architecture\n"
    assert generated_skills == ["backend-architecture"]
    assert planned_skills == ["backend-architecture"]
