from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from code2skill.capabilities.adapt.targets import get_target_definition
from code2skill.api import (
    _create_scan_config_from_namespace,
    _run_with_scan_config,
    adapt_repository,
    create_scan_config,
    estimate,
    run_ci,
    scan,
)


def test_create_scan_config_builds_repo_relative_defaults(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    config = create_scan_config(
        repo_path=repo_path,
        command="ci",
        output_dir=".code2skill-release",
        mode="auto",
        llm_provider="qwen",
        llm_model="qwen-plus-latest",
        max_skills=5,
    )

    assert config.repo_path == repo_path.resolve()
    assert config.output_dir == repo_path / ".code2skill-release"
    assert config.run.command == "ci"
    assert config.run.mode == "auto"
    assert config.run.llm_provider == "qwen"
    assert config.run.llm_model == "qwen-plus-latest"
    assert config.run.max_skills == 5


def test_create_scan_config_defaults_by_command(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    scan_config = create_scan_config(repo_path=repo_path, command="scan")
    estimate_config = create_scan_config(repo_path=repo_path, command="estimate")
    ci_config = create_scan_config(repo_path=repo_path, command="ci")

    assert scan_config.run.mode == "full"
    assert scan_config.run.write_outputs is True
    assert scan_config.run.write_state is True
    assert estimate_config.run.mode == "auto"
    assert estimate_config.run.write_outputs is False
    assert estimate_config.run.write_state is False
    assert ci_config.run.mode == "auto"
    assert ci_config.run.write_outputs is True
    assert ci_config.run.write_state is True


def test_create_scan_config_resolves_explicit_paths(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    report_path = tmp_path / "report.json"
    diff_path = tmp_path / "changes.diff"
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text(json.dumps({}), encoding="utf-8")

    config = create_scan_config(
        repo_path=repo_path,
        command="ci",
        output_dir=".out",
        report_path=report_path,
        diff_file=diff_path,
        pricing_file=pricing_path,
    )

    assert config.output_dir == (repo_path / ".out").resolve()
    assert config.run.report_path == report_path.resolve()
    assert config.run.diff_file == diff_path.resolve()
    assert config.run.pricing is not None


def test_create_scan_config_resolves_relative_optional_paths_from_repo_root(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    pricing_path = repo_path / "pricing" / "pricing.json"
    pricing_path.parent.mkdir(parents=True)
    pricing_path.write_text(json.dumps({}), encoding="utf-8")

    config = create_scan_config(
        repo_path=repo_path,
        command="ci",
        report_path="reports/report.json",
        diff_file="changes/current.diff",
        pricing_file="pricing/pricing.json",
    )

    assert config.run.report_path == (repo_path / "reports" / "report.json").resolve()
    assert config.run.diff_file == (repo_path / "changes" / "current.diff").resolve()
    assert config.run.pricing is not None


def test_create_scan_config_from_namespace_reads_cli_shape(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    args = SimpleNamespace(
        repo_path=str(repo_path),
        command="ci",
        output_dir=".generated",
        mode="auto",
        base_ref="origin/main",
        head_ref="HEAD~1",
        diff_file="changes.diff",
        report_json="reports/report.json",
        pricing_file=None,
        structure_only=True,
        llm="qwen",
        model="qwen-plus-latest",
        max_skills=3,
        max_files=20,
        max_file_size_kb=128,
        max_total_chars=5000,
        max_incremental_changed_files=10,
    )

    config = _create_scan_config_from_namespace(args)

    assert config.repo_path == repo_path.resolve()
    assert config.output_dir == (repo_path / ".generated").resolve()
    assert config.run.base_ref == "origin/main"
    assert config.run.head_ref == "HEAD~1"
    assert config.run.diff_file == (repo_path / "changes.diff").resolve()
    assert config.run.report_path == (repo_path / "reports" / "report.json").resolve()
    assert config.run.structure_only is True
    assert config.run.llm_provider == "qwen"


def test_run_with_scan_config_builds_config_once(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_runner(config):
        captured["config"] = config
        return sentinel

    result = _run_with_scan_config(
        runner=fake_runner,
        repo_path=repo_path,
        command="scan",
        output_dir=".generated",
        llm_provider="qwen",
        llm_model="qwen-plus-latest",
        max_skills=2,
    )

    assert result is sentinel
    config = captured["config"]
    assert config.run.command == "scan"
    assert config.run.llm_provider == "qwen"
    assert config.run.max_skills == 2


def test_scan_shortcut_delegates_to_core_with_built_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_scan_repository(config):
        captured["config"] = config
        return sentinel

    monkeypatch.setattr("code2skill.core.scan_repository", fake_scan_repository)

    result = scan(
        repo_path=repo_path,
        output_dir=".generated",
        llm_provider="qwen",
        llm_model="qwen-plus-latest",
        max_skills=3,
    )

    config = captured["config"]

    assert result is sentinel
    assert config.repo_path == repo_path.resolve()
    assert config.output_dir == repo_path / ".generated"
    assert config.run.llm_provider == "qwen"
    assert config.run.llm_model == "qwen-plus-latest"
    assert config.run.max_skills == 3


def test_estimate_shortcut_delegates_to_core_with_built_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_estimate_repository(config):
        captured["config"] = config
        return sentinel

    monkeypatch.setattr("code2skill.core.estimate_repository", fake_estimate_repository)

    result = estimate(repo_path=repo_path, output_dir=".generated", mode="incremental")

    config = captured["config"]

    assert result is sentinel
    assert config.repo_path == repo_path.resolve()
    assert config.output_dir == repo_path / ".generated"
    assert config.run.command == "estimate"
    assert config.run.mode == "incremental"
    assert config.run.write_outputs is False
    assert config.run.write_state is False


def test_run_ci_shortcut_delegates_to_core_with_built_config(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_run_ci_repository(config):
        captured["config"] = config
        return sentinel

    monkeypatch.setattr("code2skill.core.run_ci_repository", fake_run_ci_repository)

    result = run_ci(
        repo_path=repo_path,
        output_dir=".generated",
        llm_provider="qwen",
        llm_model="qwen-plus-latest",
        max_skills=2,
    )

    config = captured["config"]

    assert result is sentinel
    assert config.repo_path == repo_path.resolve()
    assert config.output_dir == repo_path / ".generated"
    assert config.run.command == "ci"
    assert config.run.mode == "auto"
    assert config.run.llm_provider == "qwen"
    assert config.run.llm_model == "qwen-plus-latest"
    assert config.run.max_skills == 2


def test_adapt_shortcut_writes_relative_to_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    skills_dir = repo_path / ".code2skill" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "index.md").write_text("# Skills Index\n", encoding="utf-8")
    (skills_dir / "backend.md").write_text("# Backend\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    written = adapt_repository(repo_path=repo_path, target="codex")

    assert written == [(repo_path / "AGENTS.md").resolve()]
    assert (repo_path / "AGENTS.md").exists()
    assert not (tmp_path / "AGENTS.md").exists()


def test_adapt_shortcut_resolves_relative_source_dir_from_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    source_dir = repo_path / "generated-skills"
    source_dir.mkdir(parents=True)
    (source_dir / "index.md").write_text("# Skills Index\n", encoding="utf-8")
    (source_dir / "backend.md").write_text("# Backend\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    written = adapt_repository(
        repo_path=repo_path,
        target="codex",
        source_dir="generated-skills",
    )

    assert written == [(repo_path / "AGENTS.md").resolve()]
    assert (repo_path / "AGENTS.md").exists()
    assert not (tmp_path / "AGENTS.md").exists()


def test_get_target_definition_for_codex_has_agents_output() -> None:
    target = get_target_definition("codex")

    assert target.name == "codex"
    assert target.destination == "AGENTS.md"
