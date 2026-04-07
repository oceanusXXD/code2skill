from __future__ import annotations

from pathlib import Path

from code2skill.domain.results import CommandRunSummary, summarize_scan_execution
from code2skill.models import CostEstimateSummary, ExecutionReport, ImpactSummary, ScanExecution
from code2skill.models import ImportGraphStats, ProjectProfile, SkillBlueprint
from code2skill.product.cli_summary import render_summary_lines


def test_render_summary_lines_prints_command_mode_repo_and_writes() -> None:
    summary = CommandRunSummary(
        command="scan",
        mode="full",
        repo_path=Path("/repo"),
        output_dir=Path("/repo/.code2skill"),
        written_paths=[Path("/repo/.code2skill/report.json")],
    )

    lines = render_summary_lines(summary)

    assert lines == [
        "command: scan",
        "mode: full",
        f"repo: {Path('/repo')}",
        f"output_dir: {Path('/repo/.code2skill')}",
        f"wrote: {Path('/repo/.code2skill/report.json')}",
    ]


def test_render_summary_lines_includes_report_metadata_and_notes() -> None:
    summary = CommandRunSummary(
        command="ci",
        mode="incremental",
        repo_path=Path("/repo"),
        output_dir=Path("/repo/.code2skill"),
        structure_only=True,
        llm_provider="qwen",
        llm_model="qwen-plus-latest",
        notes=["reused incremental state", "report-only preview"],
        updated_paths=[Path("/repo/.code2skill/skills/backend.md")],
        written_paths=[Path("/repo/.code2skill/report.json")],
    )

    lines = render_summary_lines(summary)

    assert "structure_only: true" in lines
    assert "llm_provider: qwen" in lines
    assert "llm_model: qwen-plus-latest" in lines
    assert "note: reused incremental state" in lines
    assert "note: report-only preview" in lines
    assert f"updated: {Path('/repo/.code2skill/skills/backend.md')}" in lines


def test_summarize_scan_execution_includes_report_metadata() -> None:
    blueprint = SkillBlueprint(
        project_profile=ProjectProfile(
            name="repo",
            repo_type="library",
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
        import_graph_stats=ImportGraphStats(
            total_internal_edges=0,
            hub_files=[],
            entry_points=[],
            cluster_count=0,
        ),
    )
    zero_cost = CostEstimateSummary(
        strategy="heuristic",
        skill_count=0,
        input_chars=0,
        input_tokens=0,
        output_chars=0,
        output_tokens=0,
        estimated_usd=0.0,
        assumptions=[],
    )
    report = ExecutionReport(
        generated_at="2026-04-07T00:00:00+00:00",
        command="ci",
        requested_mode="auto",
        effective_mode="incremental",
        repo_path="/repo",
        output_dir="/repo/.code2skill",
        base_ref="origin/main",
        head_ref="HEAD",
        head_commit="deadbeef",
        discovery_method="git",
        candidate_count=10,
        selected_count=3,
        total_chars=120,
        bytes_read=512,
        written_files=["/repo/.code2skill/report.json"],
        updated_files=["/repo/.code2skill/skills/backend.md"],
        impact=ImpactSummary(changed_files=["a.py"], affected_files=["a.py"], affected_skills=["backend"]),
        first_generation_cost=zero_cost,
        incremental_rewrite_cost=zero_cost,
        incremental_patch_cost=zero_cost,
        pricing={},
        structure_only=True,
        llm_provider="qwen",
        llm_model="qwen-plus-latest",
        notes=["reused incremental state"],
    )
    execution = ScanExecution(
        repo_path=Path("/repo"),
        output_dir=Path("/repo/.code2skill"),
        output_files=[Path("/repo/.code2skill/report.json")],
        candidate_count=10,
        selected_count=3,
        total_chars=120,
        blueprint=blueprint,
        run_mode="incremental",
        changed_files=["a.py"],
        affected_skills=["backend"],
        generated_skills=["backend"],
        report_path=Path("/repo/.code2skill/report.json"),
        report=report,
    )

    summary = summarize_scan_execution("ci", execution)

    assert summary.structure_only is True
    assert summary.llm_provider == "qwen"
    assert summary.llm_model == "qwen-plus-latest"
    assert summary.notes == ["reused incremental state"]
    assert summary.updated_paths == [Path("/repo/.code2skill/skills/backend.md")]
