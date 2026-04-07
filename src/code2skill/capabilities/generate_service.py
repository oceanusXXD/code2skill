from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..config import ScanConfig
from ..llm_backend import LLMBackend
from ..models import FileDiffPatch, SkillBlueprint, StateSnapshot
from ..skill_generator import SkillGenerator, match_planned_skills
from ..skill_planner import SkillPlanner, load_skill_plan, render_skill_plan

"""Skill generation orchestration extracted from core.

This service owns the planner/generator coordination, fallback rules, and the switch
between full and incremental generation. Keeping it here reduces pressure on
`core.execute_repository(...)` without changing the underlying generation behavior.
"""


BackendFactory = Callable[[str, str | None], LLMBackend]


class SkillPipelineService:
    def __init__(self, backend_factory: BackendFactory) -> None:
        self._backend_factory = backend_factory

    def build_artifacts(
        self,
        *,
        config: ScanConfig,
        effective_mode: str,
        repo_path: Path,
        output_dir: Path,
        blueprint: SkillBlueprint,
        previous_state: StateSnapshot | None,
        changed_files: list[str],
        changed_diffs: list[FileDiffPatch],
        affected_files: list[str],
        affected_skill_names: list[str],
    ) -> tuple[dict[str, str], list[str], list[str]]:
        backend = self._backend_factory(
            config.run.llm_provider,
            config.run.llm_model,
        )
        planner = SkillPlanner(
            backend=backend,
            max_skills=config.run.max_skills,
        )
        generator = SkillGenerator(
            backend=backend,
            repo_path=repo_path,
            output_dir=output_dir,
            max_inline_chars=config.limits.max_file_size_kb * 1024,
        )
        plan_path = output_dir / "skill-plan.json"
        needs_full_generation = (
            config.run.command == "scan"
            or effective_mode == "full"
            or not plan_path.exists()
        )

        if needs_full_generation:
            return self._generate_full(
                planner=planner,
                generator=generator,
                blueprint=blueprint,
                repo_path=repo_path,
            )

        try:
            plan = load_skill_plan(plan_path)
        except Exception:
            return self._generate_full(
                planner=planner,
                generator=generator,
                blueprint=blueprint,
                repo_path=repo_path,
            )

        return self._generate_incremental(
            planner=planner,
            generator=generator,
            blueprint=blueprint,
            repo_path=repo_path,
            plan=plan,
            previous_state=previous_state,
            changed_files=changed_files,
            changed_diffs=changed_diffs,
            affected_files=affected_files,
            affected_skill_names=affected_skill_names,
        )

    @staticmethod
    def _generate_full(
        *,
        planner: SkillPlanner,
        generator: SkillGenerator,
        blueprint: SkillBlueprint,
        repo_path: Path,
    ) -> tuple[dict[str, str], list[str], list[str]]:
        plan = planner.plan(blueprint=blueprint, repo_path=repo_path)
        artifacts = {
            "skill-plan.json": render_skill_plan(plan),
        }
        artifacts.update(generator.generate_all(blueprint=blueprint, plan=plan))
        planned_names = [skill.name for skill in plan.skills]
        return artifacts, planned_names, planned_names

    @staticmethod
    def _generate_incremental(
        *,
        planner: SkillPlanner,
        generator: SkillGenerator,
        blueprint: SkillBlueprint,
        repo_path: Path,
        plan,
        previous_state: StateSnapshot | None,
        changed_files: list[str],
        changed_diffs: list[FileDiffPatch],
        affected_files: list[str],
        affected_skill_names: list[str],
    ) -> tuple[dict[str, str], list[str], list[str]]:
        artifacts: dict[str, str] = {}
        plan_skill_names = {skill.name for skill in plan.skills}
        planned_names = [skill.name for skill in plan.skills]
        present_skills = [
            name for name in affected_skill_names if name in plan_skill_names
        ]
        missing_skills = [
            name for name in affected_skill_names if name not in plan_skill_names
        ]
        if present_skills:
            affected_skill_names = present_skills
        elif missing_skills:
            plan = planner.plan(blueprint=blueprint, repo_path=repo_path)
            artifacts["skill-plan.json"] = render_skill_plan(plan)
            planned_names = [skill.name for skill in plan.skills]
            affected_skill_names = match_planned_skills(affected_files, plan)
            artifacts.update(generator.generate_all(blueprint=blueprint, plan=plan))
            return artifacts, planned_names, planned_names

        if not affected_skill_names:
            return artifacts, [], planned_names

        artifacts.update(
            generator.generate_incremental(
                blueprint=blueprint,
                plan=plan,
                affected_skill_names=affected_skill_names,
                changed_files=changed_files,
                changed_diffs=changed_diffs,
                previous_state=previous_state,
            )
        )
        return artifacts, affected_skill_names, planned_names
