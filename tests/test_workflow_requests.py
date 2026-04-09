from __future__ import annotations

from pathlib import Path

from code2skill.domain.artifacts import ArtifactLayout
from code2skill.workflows.requests import AdaptRequest, WorkflowRequest


def test_artifact_layout_builds_default_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    layout = ArtifactLayout.from_repo_root(repo_path)

    assert layout.root == repo_path / ".code2skill"
    assert layout.skills_dir == repo_path / ".code2skill" / "skills"
    assert layout.report_path == repo_path / ".code2skill" / "report.json"


def test_workflow_request_uses_repo_relative_output_dir(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    request = WorkflowRequest.create(
        command="scan",
        repo_path=repo_path,
        output_dir=".generated",
    )

    assert request.repo_path == repo_path.resolve()
    assert request.output_dir == (repo_path / ".generated").resolve()
    assert request.artifact_layout.skills_dir == (repo_path / ".generated" / "skills").resolve()


def test_adapt_request_resolves_source_dir_from_repo_root(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    request = AdaptRequest.create(
        repo_path=repo_path,
        target="codex",
        source_dir="generated-skills",
    )

    assert request.source_dir == (repo_path / "generated-skills").resolve()
    assert request.destination_root == repo_path.resolve()


def test_artifact_layout_partitions_final_skill_products_from_intermediates(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    layout = ArtifactLayout.from_repo_root(repo_path)

    final_products, intermediates = layout.partition_bundle_paths(
        [
            "project-summary.md",
            "skill-plan.json",
            "skills/index.md",
            "skills/backend.md",
            "state/analysis-state.json",
        ]
    )

    assert final_products == [
        layout.skills_dir / "index.md",
        layout.skills_dir / "backend.md",
    ]
    assert intermediates == [
        layout.project_summary_path,
        layout.skill_plan_path,
        layout.state_path,
    ]
