from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence

from . import __version__


class HelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code2skill",
        description=(
            "把 Python 仓库编译为可供 AI 编程助手消费的结构化项目知识与 Skill 文档。"
        ),
        epilog=(
            "示例:\n"
            "  code2skill scan --llm qwen --model qwen-plus\n"
            "  code2skill ci --mode auto --base-ref origin/main --llm qwen\n"
            "  code2skill adapt --target codex"
        ),
        formatter_class=HelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="全量生成项目蓝图、Skill 规划和 Skill 文档。",
        description="执行完整扫描流程，默认从当前目录读取仓库。",
        formatter_class=HelpFormatter,
    )
    _add_common_arguments(scan_parser)
    _add_skill_arguments(scan_parser, include_structure_only=True)
    scan_parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="scan 命令默认走 full，也允许显式测试 incremental。",
    )

    estimate_parser = subparsers.add_parser(
        "estimate",
        help="只计算影响范围和成本，不写出中间产物。",
        description="用于在 CI 或本地预估扫描成本，不触发写盘。",
        formatter_class=HelpFormatter,
    )
    _add_common_arguments(estimate_parser)
    _add_runtime_arguments(estimate_parser, default_mode="auto")

    ci_parser = subparsers.add_parser(
        "ci",
        help="CI/CD 统一入口，支持 auto/full/incremental。",
        description="优先用于自动化场景，会根据历史状态和 diff 自动选择模式。",
        formatter_class=HelpFormatter,
    )
    _add_common_arguments(ci_parser)
    _add_skill_arguments(ci_parser, include_structure_only=True)
    _add_runtime_arguments(ci_parser, default_mode="auto")

    adapt_parser = subparsers.add_parser(
        "adapt",
        help="把生成后的 Skill 适配到 Cursor、Codex、Claude 等目标位置。",
        description="纯文件操作，不调用 LLM。",
        formatter_class=HelpFormatter,
    )
    adapt_parser.add_argument(
        "--target",
        choices=("cursor", "claude", "codex", "copilot", "windsurf", "all"),
        required=True,
        help="目标 IDE 或规则文件格式。",
    )
    adapt_parser.add_argument(
        "--source-dir",
        default=_env_str("CODE2SKILL_SOURCE_DIR", ".code2skill/skills"),
        help="Skill 目录，支持通过 CODE2SKILL_SOURCE_DIR 预设。",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "adapt":
        from .adapt import adapt_skills

        written_files = adapt_skills(
            target=args.target,
            source_dir=args.source_dir,
        )
        print(f"code2skill {__version__}")
        print("command: adapt")
        print(f"target: {args.target}")
        for artifact in written_files:
            print(f"wrote: {artifact}")
        return 0

    config = _build_config(args)

    if args.command == "scan":
        from .core import scan_repository

        result = scan_repository(config)
    elif args.command == "estimate":
        from .core import estimate_repository

        result = estimate_repository(config)
    elif args.command == "ci":
        from .core import run_ci_repository

        result = run_ci_repository(config)
    else:
        parser.error(f"Unsupported command: {args.command}")
        return 2

    print(f"code2skill {__version__}")
    print(f"command: {args.command}")
    print(f"mode: {result.run_mode}")
    print(f"repo: {result.repo_path}")
    print(f"repo_type: {result.blueprint.project_profile.repo_type}")
    print(f"selected_files: {result.selected_count}/{result.candidate_count}")
    print(f"total_chars: {result.total_chars}")
    if result.changed_files:
        print(f"changed_files: {len(result.changed_files)}")
    if result.affected_skills:
        print(f"affected_skills: {', '.join(result.affected_skills)}")
    print(f"output_dir: {result.output_dir}")
    if result.report_path is not None:
        print(f"report: {result.report_path}")
    for artifact in result.output_files:
        print(f"wrote: {artifact}")
    return 0


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="要分析的仓库路径，默认当前目录。",
    )
    parser.add_argument(
        "--output-dir",
        default=_env_str("CODE2SKILL_OUTPUT_DIR", ".code2skill"),
        help="输出目录，可通过 CODE2SKILL_OUTPUT_DIR 预设。",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=_env_int("CODE2SKILL_MAX_FILES", 40),
        help="预算内最多保留多少个高价值文件。",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        default=_env_int("CODE2SKILL_MAX_FILE_SIZE_KB", 256),
        help="单个文本文件允许内联读取的最大体积。",
    )
    parser.add_argument(
        "--max-total-chars",
        type=int,
        default=_env_int("CODE2SKILL_MAX_TOTAL_CHARS", 120000),
        help="整个扫描流程允许保留的总字符预算。",
    )


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    default_mode: str,
) -> None:
    parser.add_argument(
        "--mode",
        choices=("auto", "full", "incremental"),
        default=_env_choice("CODE2SKILL_MODE", default_mode, ("auto", "full", "incremental")),
        help="运行模式，可通过 CODE2SKILL_MODE 预设。",
    )
    parser.add_argument(
        "--base-ref",
        default=_env_optional("CODE2SKILL_BASE_REF"),
        help="CI diff 使用的基线引用，例如 origin/main。",
    )
    parser.add_argument(
        "--head-ref",
        default=_env_str("CODE2SKILL_HEAD_REF", "HEAD"),
        help="CI diff 使用的目标引用。",
    )
    parser.add_argument(
        "--diff-file",
        default=_env_optional("CODE2SKILL_DIFF_FILE"),
        help="可选的 unified diff 文件路径，提供后优先读取。",
    )
    parser.add_argument(
        "--report-json",
        default=_env_optional("CODE2SKILL_REPORT_JSON"),
        help="报告输出路径，默认为 output-dir/report.json。",
    )
    parser.add_argument(
        "--pricing-file",
        default=_env_optional("CODE2SKILL_PRICING_FILE"),
        help="可选的价格配置 JSON，用于估算模型成本。",
    )
    parser.add_argument(
        "--max-incremental-changed-files",
        type=int,
        default=_env_int("CODE2SKILL_MAX_INCREMENTAL_CHANGED_FILES", 64),
        help="超过这个阈值时，auto 模式自动回退为 full。",
    )


def _add_skill_arguments(
    parser: argparse.ArgumentParser,
    include_structure_only: bool,
) -> None:
    if include_structure_only:
        parser.add_argument(
            "--structure-only",
            action="store_true",
            help="只运行 Phase 1 结构扫描。",
        )
    parser.add_argument(
        "--llm",
        choices=("openai", "claude", "qwen"),
        default=_env_choice("CODE2SKILL_LLM", "openai", ("openai", "claude", "qwen")),
        help="LLM 后端，可通过 CODE2SKILL_LLM 预设。",
    )
    parser.add_argument(
        "--model",
        default=_env_optional("CODE2SKILL_MODEL"),
        help="可选的模型名，可通过 CODE2SKILL_MODEL 预设。",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=_env_int("CODE2SKILL_MAX_SKILLS", 8),
        help="最多生成多少个 Skill，可通过 CODE2SKILL_MAX_SKILLS 预设。",
    )


def _build_config(args):
    from .config import PricingConfig, RunOptions, ScanConfig, ScanLimits

    repo_path = Path(args.repo_path).expanduser().resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_path / output_dir

    pricing_path = (
        Path(args.pricing_file).expanduser().resolve()
        if getattr(args, "pricing_file", None)
        else None
    )
    report_path = (
        Path(args.report_json).expanduser().resolve()
        if getattr(args, "report_json", None)
        else output_dir / "report.json"
    )
    diff_path = (
        Path(args.diff_file).expanduser().resolve()
        if getattr(args, "diff_file", None)
        else None
    )

    return ScanConfig(
        repo_path=repo_path,
        output_dir=output_dir,
        limits=ScanLimits(
            max_files=args.max_files,
            max_file_size_kb=args.max_file_size_kb,
            max_total_chars=args.max_total_chars,
        ),
        run=RunOptions(
            command=args.command,
            mode=args.mode,
            base_ref=getattr(args, "base_ref", None),
            head_ref=getattr(args, "head_ref", "HEAD"),
            diff_file=diff_path,
            report_path=report_path,
            pricing=PricingConfig.from_file(pricing_path),
            structure_only=getattr(args, "structure_only", False),
            llm_provider=getattr(args, "llm", "openai"),
            llm_model=getattr(args, "model", None),
            max_skills=getattr(args, "max_skills", 8),
            write_outputs=args.command != "estimate",
            write_state=args.command != "estimate",
            max_incremental_changed_files=getattr(
                args,
                "max_incremental_changed_files",
                64,
            ),
        ),
    )


def _env_choice(name: str, default: str, choices: tuple[str, ...]) -> str:
    value = os.getenv(name, "").strip().lower()
    if value in choices:
        return value
    return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default
