from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from code2skill.capabilities.reporting import build_execution_report, resolve_report_path
from code2skill.config import RunOptions, ScanConfig
from code2skill.models import CostEstimateSummary


class FakeCostEstimator:
    def pricing_dict(self) -> dict[str, object]:
        return {"model": "heuristic"}


def _zero_cost() -> CostEstimateSummary:
    return CostEstimateSummary(
        strategy="heuristic",
        skill_count=0,
        input_chars=0,
        input_tokens=0,
        output_chars=0,
        output_tokens=0,
        estimated_usd=0.0,
        assumptions=[],
    )


def test_resolve_report_path_uses_configured_report_path(tmp_path: Path) -> None:
    config = ScanConfig(
        repo_path=tmp_path,
        output_dir=tmp_path / ".code2skill",
        run=RunOptions(report_path=tmp_path / "reports" / "custom.json"),
    )

    assert resolve_report_path(config) == (tmp_path / "reports" / "custom.json")


def test_build_execution_report_includes_run_metadata(tmp_path: Path) -> None:
    config = ScanConfig(
        repo_path=tmp_path,
        output_dir=tmp_path / ".code2skill",
        run=RunOptions(
            command="ci",
            mode="auto",
            structure_only=True,
            llm_provider="qwen",
            llm_model="qwen-plus-latest",
        ),
    )
    inventory = SimpleNamespace(discovery_method="git", candidates=[object(), object()])
    budget = SimpleNamespace(selected=[object()], total_chars=120)

    report = build_execution_report(
        config=config,
        effective_mode="incremental",
        repo_path=tmp_path,
        output_dir=tmp_path / ".code2skill",
        report_path=tmp_path / ".code2skill" / "report.json",
        inventory=inventory,
        budget=budget,
        changed_files=["app.py"],
        affected_files=["app.py"],
        affected_skills=["backend"],
        generated_skills=["backend"],
        written_files=[tmp_path / ".code2skill" / "report.json"],
        updated_files=[tmp_path / ".code2skill" / "skills" / "backend.md"],
        head_commit="deadbeef",
        bytes_read=512,
        cost_estimator=FakeCostEstimator(),
        first_generation_cost=_zero_cost(),
        rewrite_cost=_zero_cost(),
        patch_cost=_zero_cost(),
        notes=["reused incremental state"],
        generated_at="2026-04-07T00:00:00+00:00",
    )

    assert report.structure_only is True
    assert report.llm_provider == "qwen"
    assert report.llm_model == "qwen-plus-latest"
    assert report.updated_files == [str(tmp_path / ".code2skill" / "skills" / "backend.md")]
    assert report.notes == ["reused incremental state"]


def test_build_execution_report_partitions_final_products_from_intermediates(tmp_path: Path) -> None:
    output_dir = tmp_path / ".code2skill"
    skill_path = output_dir / "skills" / "backend.md"
    plan_path = output_dir / "skill-plan.json"
    report_path = output_dir / "report.json"
    state_path = output_dir / "state" / "analysis-state.json"
    config = ScanConfig(repo_path=tmp_path, output_dir=output_dir)
    inventory = SimpleNamespace(discovery_method="git", candidates=[object()])
    budget = SimpleNamespace(selected=[object()], total_chars=42)

    report = build_execution_report(
        config=config,
        effective_mode="full",
        repo_path=tmp_path,
        output_dir=output_dir,
        report_path=report_path,
        inventory=inventory,
        budget=budget,
        changed_files=[],
        affected_files=[],
        affected_skills=[],
        generated_skills=["backend"],
        written_files=[plan_path, skill_path],
        updated_files=[skill_path],
        head_commit="deadbeef",
        bytes_read=128,
        cost_estimator=FakeCostEstimator(),
        first_generation_cost=_zero_cost(),
        rewrite_cost=_zero_cost(),
        patch_cost=_zero_cost(),
        notes=[],
        generated_at="2026-04-07T00:00:00+00:00",
    )

    assert report.final_product_files == [str(skill_path)]
    assert report.intermediate_artifact_files == [
        str(plan_path),
        str(report_path),
        str(state_path),
    ]
