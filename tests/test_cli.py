from __future__ import annotations

from pathlib import Path

from code2skill.cli import _build_config, build_parser


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
    monkeypatch.setenv("CODE2SKILL_MODEL", "qwen-plus")
    monkeypatch.setenv("CODE2SKILL_MAX_SKILLS", "5")
    monkeypatch.setenv("CODE2SKILL_BASE_REF", "origin/main")
    monkeypatch.setenv("CODE2SKILL_HEAD_REF", "HEAD~1")

    parser = build_parser()
    args = parser.parse_args(["ci"])
    config = _build_config(args)

    assert config.repo_path == tmp_path.resolve()
    assert config.output_dir == tmp_path / ".code2skill-release"
    assert config.run.llm_provider == "qwen"
    assert config.run.llm_model == "qwen-plus"
    assert config.run.max_skills == 5
    assert config.run.base_ref == "origin/main"
    assert config.run.head_ref == "HEAD~1"


def test_invalid_environment_choice_falls_back_to_safe_default(monkeypatch) -> None:
    monkeypatch.setenv("CODE2SKILL_LLM", "unsupported-provider")

    parser = build_parser()
    args = parser.parse_args(["scan"])

    assert args.llm == "openai"
