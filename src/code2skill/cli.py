from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from . import __version__


USER_FACING_EXCEPTIONS = (
    FileNotFoundError,
    RuntimeError,
    ValueError,
)


class HelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code2skill",
        description=(
            "Generate repository-aware Skills, structured project knowledge, "
            "and AI rule files from real Python codebases."
        ),
        epilog=(
            "Examples:\n"
            "  code2skill scan /path/to/repo --llm qwen --model qwen-plus-latest\n"
            "  code2skill ci /path/to/repo --mode auto --base-ref origin/main --llm qwen\n"
            "  code2skill adapt /path/to/repo --target codex"
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
        help="Run a full repository scan and generate Skills.",
        description="Scan a repository and write the full code2skill artifact set.",
        formatter_class=HelpFormatter,
    )
    _add_common_arguments(scan_parser)
    _add_skill_arguments(scan_parser, include_structure_only=True)
    scan_parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="Execution mode for the scan command.",
    )

    estimate_parser = subparsers.add_parser(
        "estimate",
        help="Preview impact and cost without generating Skills.",
        description="Estimate scan impact and cost, then write report.json only.",
        formatter_class=HelpFormatter,
    )
    _add_common_arguments(estimate_parser)
    _add_runtime_arguments(estimate_parser, default_mode="auto")

    ci_parser = subparsers.add_parser(
        "ci",
        help="Run the automation-friendly full or incremental pipeline.",
        description=(
            "Use repository state and diffs to choose full or incremental mode "
            "for CI/CD workflows."
        ),
        formatter_class=HelpFormatter,
    )
    _add_common_arguments(ci_parser)
    _add_skill_arguments(ci_parser, include_structure_only=True)
    _add_runtime_arguments(ci_parser, default_mode="auto")

    adapt_parser = subparsers.add_parser(
        "adapt",
        help="Adapt generated Skills into target AI tool instruction files.",
        description=(
            "Copy or merge generated Skills into target-specific files under "
            "the repository root."
        ),
        formatter_class=HelpFormatter,
    )
    adapt_parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Repository root where adapted files should be written.",
    )
    adapt_parser.add_argument(
        "--target",
        choices=("cursor", "claude", "codex", "copilot", "windsurf", "all"),
        required=True,
        help="Target IDE or instruction-file format.",
    )
    adapt_parser.add_argument(
        "--source-dir",
        default=_env_str("CODE2SKILL_SOURCE_DIR", ".code2skill/skills"),
        help="Generated skills directory. Relative paths are resolved from repo_path.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        return _run_command(parser, args)
    except KeyboardInterrupt:
        _print_stderr("code2skill: interrupted\n")
        return 130
    except USER_FACING_EXCEPTIONS as exc:
        _print_stderr(f"code2skill: error: {exc}\n")
        return 1


def _run_command(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> int:
    if args.command == "adapt":
        from .adapt import adapt_skills

        repo_path = Path(args.repo_path).expanduser().resolve()
        source_dir = _resolve_repo_relative_path(repo_path, args.source_dir)
        written_files = adapt_skills(
            target=args.target,
            source_dir=source_dir,
            destination_root=repo_path,
        )
        print(f"code2skill {__version__}")
        print("command: adapt")
        print(f"repo: {repo_path}")
        print(f"target: {args.target}")
        print(f"source_dir: {source_dir}")
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
    if result.generated_skills:
        print(f"generated_skills: {', '.join(result.generated_skills)}")
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
        help="Repository path to analyze.",
    )
    parser.add_argument(
        "--output-dir",
        default=_env_str("CODE2SKILL_OUTPUT_DIR", ".code2skill"),
        help="Output directory for generated artifacts.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=_env_int("CODE2SKILL_MAX_FILES", 40),
        help="Maximum number of high-value files to retain in the working set.",
    )
    parser.add_argument(
        "--max-file-size-kb",
        type=int,
        default=_env_int("CODE2SKILL_MAX_FILE_SIZE_KB", 256),
        help="Maximum inline size for a single text file.",
    )
    parser.add_argument(
        "--max-total-chars",
        type=int,
        default=_env_int("CODE2SKILL_MAX_TOTAL_CHARS", 120000),
        help="Total retained character budget for one run.",
    )


def _add_runtime_arguments(
    parser: argparse.ArgumentParser,
    default_mode: str,
) -> None:
    parser.add_argument(
        "--mode",
        choices=("auto", "full", "incremental"),
        default=_env_choice(
            "CODE2SKILL_MODE",
            default_mode,
            ("auto", "full", "incremental"),
        ),
        help="Execution mode for report-only or CI workflows.",
    )
    parser.add_argument(
        "--base-ref",
        default=_env_optional("CODE2SKILL_BASE_REF"),
        help="Base Git ref used for diffing, such as origin/main.",
    )
    parser.add_argument(
        "--head-ref",
        default=_env_str("CODE2SKILL_HEAD_REF", "HEAD"),
        help="Head Git ref used for diffing.",
    )
    parser.add_argument(
        "--diff-file",
        default=_env_optional("CODE2SKILL_DIFF_FILE"),
        help="Optional unified diff file. When provided, it is used before Git refs.",
    )
    parser.add_argument(
        "--report-json",
        default=_env_optional("CODE2SKILL_REPORT_JSON"),
        help="Optional report path. Defaults to output-dir/report.json.",
    )
    parser.add_argument(
        "--pricing-file",
        default=_env_optional("CODE2SKILL_PRICING_FILE"),
        help="Optional pricing JSON used for cost estimation.",
    )
    parser.add_argument(
        "--max-incremental-changed-files",
        type=int,
        default=_env_int("CODE2SKILL_MAX_INCREMENTAL_CHANGED_FILES", 64),
        help="Fallback to full mode when the changed file count exceeds this limit.",
    )


def _add_skill_arguments(
    parser: argparse.ArgumentParser,
    include_structure_only: bool,
) -> None:
    if include_structure_only:
        parser.add_argument(
            "--structure-only",
            action="store_true",
            help="Run Phase 1 structure analysis only.",
        )
    parser.add_argument(
        "--llm",
        choices=("openai", "claude", "qwen"),
        default=_env_choice("CODE2SKILL_LLM", "openai", ("openai", "claude", "qwen")),
        help="LLM provider used for planning and Skill generation.",
    )
    parser.add_argument(
        "--model",
        default=_env_optional("CODE2SKILL_MODEL"),
        help="Optional model name for the selected provider.",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        default=_env_int("CODE2SKILL_MAX_SKILLS", 8),
        help="Maximum number of generated Skills.",
    )


def _build_config(args):
    from .api import create_scan_config

    return create_scan_config(
        repo_path=args.repo_path,
        command=args.command,
        output_dir=args.output_dir,
        mode=args.mode,
        base_ref=getattr(args, "base_ref", None),
        head_ref=getattr(args, "head_ref", "HEAD"),
        diff_file=getattr(args, "diff_file", None),
        report_path=getattr(args, "report_json", None),
        pricing_file=getattr(args, "pricing_file", None),
        structure_only=getattr(args, "structure_only", False),
        llm_provider=getattr(args, "llm", "openai"),
        llm_model=getattr(args, "model", None),
        max_skills=getattr(args, "max_skills", 8),
        max_files=args.max_files,
        max_file_size_kb=args.max_file_size_kb,
        max_total_chars=args.max_total_chars,
        max_incremental_changed_files=getattr(
            args,
            "max_incremental_changed_files",
            64,
        ),
    )


def _resolve_repo_relative_path(repo_path: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (repo_path / path).resolve()


def _print_stderr(message: str) -> None:
    print(message, file=sys.stderr, end="")


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
