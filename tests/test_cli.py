from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from code2skill.cli import _build_config, build_parser, main


def test_scan_parser_defaults_repo_path_to_current_directory() -> None:
    parser = build_parser()
    args = parser.parse_args(["scan"])

    assert args.repo_path == "."


def test_build_config_uses_environment_defaults(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODE2SKILL_OUTPUT_DIR", ".code2skill-release")
    monkeypatch.setenv("CODE2SKILL_LLM", "qwen")
    monkeypatch.setenv("CODE2SKILL_MODEL", "qwen-plus-latest")
    monkeypatch.setenv("CODE2SKILL_MAX_SKILLS", "5")
    monkeypatch.setenv("CODE2SKILL_BASE_REF", "origin/main")
    monkeypatch.setenv("CODE2SKILL_HEAD_REF", "HEAD~1")

    parser = build_parser()
    args = parser.parse_args(["ci"])
    config = _build_config(args)

    assert config.repo_path == tmp_path.resolve()
    assert config.output_dir == tmp_path / ".code2skill-release"
    assert config.run.llm_provider == "qwen"
    assert config.run.llm_model == "qwen-plus-latest"
    assert config.run.max_skills == 5
    assert config.run.base_ref == "origin/main"
    assert config.run.head_ref == "HEAD~1"


def test_build_config_resolves_paths_relative_to_repo_path(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text(json.dumps({}), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "ci",
            str(repo_path),
            "--output-dir",
            ".code2skill-release",
            "--report-json",
            str(tmp_path / "report.json"),
            "--diff-file",
            str(tmp_path / "changes.diff"),
            "--pricing-file",
            str(pricing_path),
        ]
    )
    config = _build_config(args)

    assert config.repo_path == repo_path.resolve()
    assert config.output_dir == (repo_path / ".code2skill-release").resolve()
    assert config.run.report_path == (tmp_path / "report.json").resolve()
    assert config.run.diff_file == (tmp_path / "changes.diff").resolve()
    assert config.run.pricing is not None


def test_build_config_resolves_relative_aux_paths_from_repo_path(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    pricing_path = repo_path / "config" / "pricing.json"
    pricing_path.parent.mkdir(parents=True)
    pricing_path.write_text(json.dumps({}), encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "ci",
            str(repo_path),
            "--report-json",
            "reports/run.json",
            "--diff-file",
            "diffs/current.diff",
            "--pricing-file",
            "config/pricing.json",
        ]
    )
    config = _build_config(args)

    assert config.run.report_path == (repo_path / "reports" / "run.json").resolve()
    assert config.run.diff_file == (repo_path / "diffs" / "current.diff").resolve()
    assert config.run.pricing is not None


def test_invalid_environment_choice_falls_back_to_safe_default(monkeypatch) -> None:
    monkeypatch.setenv("CODE2SKILL_LLM", "unsupported-provider")

    parser = build_parser()
    args = parser.parse_args(["scan"])

    assert args.llm == "openai"


def test_adapt_command_resolves_repo_relative_source_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    def fake_adapt_skills(
        target: str,
        source_dir: Path | str = ".code2skill/skills",
        destination_root: Path | str = ".",
    ) -> list[Path]:
        captured["target"] = target
        captured["source_dir"] = source_dir
        captured["destination_root"] = destination_root
        return []

    adapt_module = importlib.import_module("code2skill.adapt")
    monkeypatch.setattr(adapt_module, "adapt_skills", fake_adapt_skills)

    exit_code = main(["adapt", str(repo_path), "--target", "codex"])

    assert exit_code == 0
    assert captured == {
        "target": "codex",
        "source_dir": (repo_path / ".code2skill" / "skills").resolve(),
        "destination_root": repo_path.resolve(),
    }


def test_main_reports_user_facing_runtime_errors_cleanly(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "code2skill.cli._run_command",
        lambda parser, args: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    exit_code = main(["scan"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "code2skill: error:" in captured.err
    assert "boom" in captured.err


def test_main_reports_user_facing_value_errors_cleanly(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "code2skill.cli._run_command",
        lambda parser, args: (_ for _ in ()).throw(ValueError("bad input")),
    )

    exit_code = main(["scan"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "code2skill: error:" in captured.err
    assert "bad input" in captured.err


def test_main_exits_130_on_keyboard_interrupt(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        "code2skill.cli._run_command",
        lambda parser, args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    exit_code = main(["scan"])
    captured = capsys.readouterr()

    assert exit_code == 130
    assert captured.err == "code2skill: interrupted\n"
