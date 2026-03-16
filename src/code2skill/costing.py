from __future__ import annotations

import json
import math
from dataclasses import asdict

from .config import PricingConfig
from .models import (
    CostEstimateSummary,
    SkillBlueprint,
    SkillCostBreakdown,
)


# 这里的 cost 不是精确账单，而是稳定、可解释、可在 CI 中复现的工程估算。
# 目的不是替代真实计费，而是让流水线在执行前先知道“量级大概是多少”。
class CostEstimator:
    def __init__(self, pricing: PricingConfig) -> None:
        self.pricing = pricing

    def estimate_first_generation(
        self,
        blueprint: SkillBlueprint,
        rendered_artifacts: dict[str, str],
    ) -> CostEstimateSummary:
        shared_chars = sum(len(content) for content in rendered_artifacts.values())
        per_skill = [
            self._estimate_skill_call(
                skill_name=skill.name,
                skill_payload=self._build_skill_payload(
                    blueprint=blueprint,
                    skill_name=skill.name,
                    shared_chars=shared_chars,
                ),
                output_chars=self._estimate_output_chars(
                    skill.name,
                    len(skill.source_evidence),
                ),
            )
            for skill in blueprint.recommended_skills
        ]
        return self._combine(
            strategy="first_generation",
            per_skill=per_skill,
            assumptions=[
                "假设每个推荐 skill 会单独调用一次下游 skill-creator。",
                "假设每次调用都会携带共享中间产物，因此这是偏保守的上界估算。",
            ],
        )

    def estimate_incremental_rewrite(
        self,
        blueprint: SkillBlueprint,
        rendered_artifacts: dict[str, str],
        affected_skills: list[str],
        changed_files: list[str],
        affected_files: list[str],
    ) -> CostEstimateSummary:
        if not affected_skills:
            return self._empty(strategy="incremental_rewrite")

        shared_chars = sum(
            len(content)
            for path, content in rendered_artifacts.items()
            if not path.endswith("project-summary.md")
        )
        diff_chars = self._estimate_diff_chars(changed_files, affected_files)
        per_skill = [
            self._estimate_skill_call(
                skill_name=skill_name,
                skill_payload=self._build_skill_payload(
                    blueprint=blueprint,
                    skill_name=skill_name,
                    shared_chars=shared_chars + diff_chars,
                ),
                output_chars=self._estimate_output_chars(skill_name, 3),
            )
            for skill_name in affected_skills
        ]
        return self._combine(
            strategy="incremental_rewrite",
            per_skill=per_skill,
            assumptions=[
                "假设增量更新会完整重写受影响的 skill，而不是只做局部补丁。",
                "共享上下文只包含 references 与蓝图，不再重复完整仓库摘要。",
            ],
        )

    def estimate_incremental_patch(
        self,
        rewrite_cost: CostEstimateSummary,
    ) -> CostEstimateSummary:
        if rewrite_cost.skill_count == 0:
            return self._empty(strategy="incremental_patch")

        per_skill = [
            SkillCostBreakdown(
                name=item.name,
                input_chars=math.ceil(item.input_chars * 0.45),
                input_tokens=math.ceil(item.input_tokens * 0.45),
                output_chars=math.ceil(item.output_chars * 0.35),
                output_tokens=math.ceil(item.output_tokens * 0.35),
                estimated_usd=round(item.estimated_usd * 0.40, 6),
            )
            for item in rewrite_cost.per_skill
        ]
        return self._combine(
            strategy="incremental_patch",
            per_skill=per_skill,
            assumptions=[
                "假设下游系统支持仅更新受影响 skill 的局部 section。",
                "patch 模式按 rewrite 模式的 40% 成本进行启发式估算。",
            ],
        )

    def pricing_dict(self) -> dict[str, float | str]:
        return {
            "model": self.pricing.model,
            "input_per_1m": self.pricing.input_per_1m,
            "output_per_1m": self.pricing.output_per_1m,
            "chars_per_token": self.pricing.chars_per_token,
        }

    def _estimate_skill_call(
        self,
        skill_name: str,
        skill_payload: dict[str, object],
        output_chars: int,
    ) -> SkillCostBreakdown:
        input_chars = len(
            json.dumps(skill_payload, ensure_ascii=False, indent=2)
        )
        input_tokens = self._chars_to_tokens(input_chars)
        output_tokens = self._chars_to_tokens(output_chars)
        return SkillCostBreakdown(
            name=skill_name,
            input_chars=input_chars,
            input_tokens=input_tokens,
            output_chars=output_chars,
            output_tokens=output_tokens,
            estimated_usd=self._estimate_usd(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )

    def _build_skill_payload(
        self,
        blueprint: SkillBlueprint,
        skill_name: str,
        shared_chars: int,
    ) -> dict[str, object]:
        recommendation = next(
            skill
            for skill in blueprint.recommended_skills
            if skill.name == skill_name
        )
        evidence = set(recommendation.source_evidence)
        modules = [
            asdict(module)
            for module in blueprint.core_modules
            if module.path in evidence
        ]
        rules = [
            asdict(rule)
            for rule in blueprint.abstract_rules
            if evidence & set(rule.evidence)
        ]
        workflows = [
            asdict(workflow)
            for workflow in blueprint.concrete_workflows
            if evidence & set(workflow.evidence)
        ]
        apis = [
            asdict(api)
            for api in blueprint.important_apis
            if api.source in evidence
        ]
        return {
            "skill": asdict(recommendation),
            "project_profile": asdict(blueprint.project_profile),
            "tech_stack": blueprint.tech_stack,
            "shared_context_chars": shared_chars,
            "modules": modules,
            "rules": rules,
            "workflows": workflows,
            "apis": apis,
        }

    def _estimate_output_chars(
        self,
        skill_name: str,
        evidence_count: int,
    ) -> int:
        base = 1800
        if "overview" in skill_name:
            base += 800
        if "architecture" in skill_name:
            base += 600
        if skill_name.endswith("-flow") or "flow" in skill_name:
            base += 400
        return base + evidence_count * 160

    def _estimate_diff_chars(
        self,
        changed_files: list[str],
        affected_files: list[str],
    ) -> int:
        changed_chars = sum(len(path) for path in changed_files) * 3
        affected_chars = sum(len(path) for path in affected_files)
        return 600 + changed_chars + affected_chars

    def _combine(
        self,
        strategy: str,
        per_skill: list[SkillCostBreakdown],
        assumptions: list[str],
    ) -> CostEstimateSummary:
        return CostEstimateSummary(
            strategy=strategy,
            skill_count=len(per_skill),
            input_chars=sum(item.input_chars for item in per_skill),
            input_tokens=sum(item.input_tokens for item in per_skill),
            output_chars=sum(item.output_chars for item in per_skill),
            output_tokens=sum(item.output_tokens for item in per_skill),
            estimated_usd=round(
                sum(item.estimated_usd for item in per_skill),
                6,
            ),
            assumptions=assumptions,
            per_skill=per_skill,
        )

    def _empty(self, strategy: str) -> CostEstimateSummary:
        return CostEstimateSummary(
            strategy=strategy,
            skill_count=0,
            input_chars=0,
            input_tokens=0,
            output_chars=0,
            output_tokens=0,
            estimated_usd=0.0,
            assumptions=["当前没有受影响的 skill，因此增量成本为 0。"],
            per_skill=[],
        )

    def _chars_to_tokens(self, chars: int) -> int:
        return int(math.ceil(chars / self.pricing.chars_per_token))

    def _estimate_usd(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        input_cost = (input_tokens / 1_000_000) * self.pricing.input_per_1m
        output_cost = (
            output_tokens / 1_000_000
        ) * self.pricing.output_per_1m
        return round(input_cost + output_cost, 6)
