from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .adapt import adapt_skills
from .config import PricingConfig, RunOptions, ScanConfig, ScanLimits
from .core import estimate_repository, run_ci_repository, scan_repository


# CLI 只负责参数解释和命令分发。
# 真正的扫描 / 增量 / 成本逻辑全部留在核心流水线里，
# 这样测试和后续集成都会更干净。
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code2skill",
        description="Compile repository knowledge into CI-friendly skill inputs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser(
        "scan",
        help="执行全量或显式模式的仓库知识编译。",
    )
    _add_common_arguments(scan_parser)
    _add_skill_arguments(scan_parser, include_structure_only=True)
    scan_parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="scan 默认走 full，也允许显式测试 incremental。",
    )

    estimate_parser = subparsers.add_parser(
        "estimate",
        help="只计算影响范围和预计成本，不写中间产物。",
    )
    _add_common_arguments(estimate_parser)
    _add_runtime_arguments(estimate_parser, default_mode="auto")

    ci_parser = subparsers.add_parser(
        "ci",
        help="面向 CI/CD 的统一入口，支持 auto/full/incremental。",
    )
    _add_common_arguments(ci_parser)
    _add_skill_arguments(ci_parser, include_structure_only=True)
    _add_runtime_arguments(ci_parser, default_mode="auto")

    adapt_parser = subparsers.add_parser("adapt", help="Adapt generated skills.")
    adapt_parser.add_argument(
        "--target",
        choices=("cursor", "claude", "codex", "copilot", "windsurf", "all"),
        required=True,
    )
    adapt_parser.add_argument(
        "--source-dir",
        default=".code2skill/skills",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "adapt":
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
        result = scan_repository(config)
    elif args.command == "estimate":
        result = estimate_repository(config)
    elif args.command == "ci":
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
    parser.add_argument("repo_path", help="要扫描的仓库路径。")
    parser.add_argument(
        "--output-dir",
        default=".code2skill",
        help="输出目录；相对路径会解析到目标仓库内部。",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=40,
        help="预算内最多保留多少个高价值文件。",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        default=256,
        help="单个文本文件的最大扫描体积。",
    )
    parser.add_argument(
        "--max-total-chars",
        type=int,
        default=120000,
        help="所有保留文件的总字符预算。",
    )


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    default_mode: str,
) -> None:
    parser.add_argument(
        "--mode",
        choices=("auto", "full", "incremental"),
        default=default_mode,
        help="运行模式选择。",
    )
    parser.add_argument(
        "--base-ref",
        default=None,
        help="用于 CI diff 的基线引用，例如 origin/main。",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="用于 CI diff 的目标引用，默认是 HEAD。",
    )
    parser.add_argument(
        "--diff-file",
        default=None,
        help="可选的 unified diff 文件路径；提供后优先读取该 diff。",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help="报告输出路径，默认写到输出目录下的 report.json。",
    )
    parser.add_argument(
        "--pricing-file",
        default=None,
        help="可选的价格配置 JSON，用于估算下游模型成本。",
    )
    parser.add_argument(
        "--max-incremental-changed-files",
        type=int,
        default=64,
        help="超过这个阈值时，auto 模式自动回退到 full。",
    )


def _add_skill_arguments(
    parser: argparse.ArgumentParser,
    include_structure_only: bool,
) -> None:
    if include_structure_only:
        parser.add_argument(
            "--structure-only",
            action="store_true",
            help="Only run Phase 1 structure scan.",
        )
    parser.add_argument(
        "--llm",
        choices=("openai", "claude", "qwen"),
        default="openai",
        help="LLM backend provider.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional provider-specific model override.",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=8,
        help="Maximum number of generated skills.",
    )


def _build_config(args) -> ScanConfig:
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
