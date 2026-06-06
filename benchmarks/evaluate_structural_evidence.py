from __future__ import annotations

import argparse
import ast
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2skill.extractors.python_extractor import PythonExtractor
from code2skill.import_graph import ImportGraph
from code2skill.models import FileCandidate
from code2skill.scanner.prioritizer import FilePrioritizer


@dataclass(frozen=True)
class MethodResult:
    method: str
    facts_found: int
    gold_hits: int
    gold_total: int
    recall: float
    hit_facts: list[str]
    missed_facts: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate structural evidence extraction for Skill generation."
    )
    parser.add_argument(
        "--report-json",
        default="benchmarks/results/structural-evidence-benchmark.json",
    )
    parser.add_argument(
        "--svg",
        default="docs/assets/structural-evidence-benchmark.svg",
    )
    args = parser.parse_args()

    report = run_benchmark()
    report_path = resolve_output(args.report_json)
    svg_path = resolve_output(args.svg)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    svg_path.write_text(render_svg(report), encoding="utf-8")

    for result in report["results"]:
        print(
            f"{result['method']}: "
            f"gold_recall={result['recall']:.3f} "
            f"({result['gold_hits']}/{result['gold_total']})"
        )
    print(f"wrote {display_path(report_path)}")
    print(f"wrote {display_path(svg_path)}")
    return 0


def run_benchmark() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="code2skill-structural-evidence-") as root:
        repo_path = Path(root) / "repo"
        write_fixture_repo(repo_path)
        gold = set(gold_facts())
        results = [
            evaluate("path-only", path_only_facts(repo_path), gold),
            evaluate("ast-symbols", ast_symbol_facts(repo_path), gold),
            evaluate("code2skill-semantic", code2skill_facts(repo_path), gold),
        ]

    return {
        "name": "structural-evidence-extraction",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold_total": len(gold_facts()),
        "results": [asdict(result) for result in results],
        "baselines": [
            "path-only: file path and suffix role inference",
            "ast-symbols: standard AST imports, classes, functions, and methods",
            "code2skill-semantic: AST symbols plus routes, calls, type references, data-flow edges, dynamic imports, raised exceptions, re-exported symbols, and internal dependency resolution",
        ],
        "scope": (
            "This benchmark measures repository evidence extraction before any LLM call. "
            "It does not claim end-to-end SWE-bench issue resolution."
        ),
    }


def evaluate(method: str, facts: set[str], gold: set[str]) -> MethodResult:
    hits = sorted(facts & gold)
    missed = sorted(gold - facts)
    return MethodResult(
        method=method,
        facts_found=len(facts),
        gold_hits=len(hits),
        gold_total=len(gold),
        recall=len(hits) / len(gold),
        hit_facts=hits,
        missed_facts=missed,
    )


def path_only_facts(repo_path: Path) -> set[str]:
    prioritizer = FilePrioritizer()
    facts: set[str] = set()
    for path in python_files(repo_path):
        relative = path.relative_to(repo_path)
        _, _, role = prioritizer.score(relative, "python")
        facts.add(f"role:{relative.as_posix()}:{role}")
    return facts


def ast_symbol_facts(repo_path: Path) -> set[str]:
    facts: set[str] = set()
    for path in python_files(repo_path):
        relative = path.relative_to(repo_path).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    facts.add(f"import:{relative}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                facts.add(f"import:{relative}:{module}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                facts.add(f"function:{relative}:{node.name}")
            elif isinstance(node, ast.ClassDef):
                facts.add(f"class:{relative}:{node.name}")
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        facts.add(f"method:{relative}:{node.name}.{child.name}")
    return facts


def code2skill_facts(repo_path: Path) -> set[str]:
    prioritizer = FilePrioritizer()
    summaries = {}
    facts: set[str] = set()
    for path in python_files(repo_path):
        relative_path = path.relative_to(repo_path)
        relative = relative_path.as_posix()
        content = path.read_text(encoding="utf-8")
        priority, reasons, role = prioritizer.score(relative_path, "python")
        candidate = FileCandidate(
            absolute_path=path,
            relative_path=relative_path,
            size_bytes=len(content.encode("utf-8")),
            char_count=len(content),
            sha256="benchmark",
            language="python",
            inferred_role=role,
            priority=priority,
            priority_reasons=reasons,
            content=content,
        )
        summary = PythonExtractor().extract(candidate)
        summaries[relative] = summary

        facts.add(f"role:{relative}:{role}")
        facts.update(f"import:{relative}:{module}" for module in summary.imports)
        facts.update(f"class:{relative}:{name}" for name in summary.classes)
        facts.update(f"function:{relative}:{name}" for name in summary.functions)
        facts.update(f"method:{relative}:{name}" for name in summary.methods)
        facts.update(
            f"route:{relative}:{route.method} {route.path}->{route.handler}"
            for route in summary.routes
        )
        facts.update(f"call:{relative}:{target}" for target in summary.call_targets)
        facts.update(f"type:{relative}:{target}" for target in summary.type_references)
        facts.update(f"model:{relative}:{target}" for target in summary.models_or_schemas)
        facts.update(f"dynamic_import:{relative}:{target}" for target in summary.dynamic_imports)
        facts.update(f"raise:{relative}:{target}" for target in summary.raised_exceptions)
        facts.update(f"data_flow:{relative}:{edge}" for edge in summary.data_flow_edges)
        if "has_main_guard" in summary.notes:
            facts.add(f"main_guard:{relative}")

    graph = ImportGraph()
    graph.build(summaries)
    for source, summary in summaries.items():
        for dependency in graph.internal_dependencies_for(source):
            facts.add(f"dependency:{source}->{dependency}")
    return facts


def render_svg(report: dict[str, object]) -> str:
    results = report["results"]
    width = 880
    height = 330
    left = 210
    top = 88
    chart_width = 610
    bar_height = 34
    gap = 52
    colors = {
        "path-only": "#8a8f98",
        "ast-symbols": "#3f6d8f",
        "code2skill-semantic": "#198754",
    }
    labels = {
        "path-only": "Path-only baseline",
        "ast-symbols": "AST symbols baseline",
        "code2skill-semantic": "code2skill semantic",
    }
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="880" height="330" viewBox="0 0 880 330" role="img" aria-labelledby="title desc">',
        '<title id="title">Structural evidence extraction benchmark</title>',
        '<desc id="desc">Gold evidence recall for path-only, AST-symbols, and code2skill-semantic extraction.</desc>',
        '<rect width="880" height="330" fill="#ffffff"/>',
        '<text x="36" y="38" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#111827">Structural Evidence Extraction</text>',
        '<text x="36" y="62" font-family="Arial, sans-serif" font-size="13" fill="#4b5563">Gold evidence recall before any LLM call. Higher is better.</text>',
    ]
    for tick in range(0, 6):
        x = left + tick * chart_width / 5
        lines.append(f'<line x1="{x:.1f}" y1="78" x2="{x:.1f}" y2="252" stroke="#eef0f3"/>')
        lines.append(
            f'<text x="{x - 8:.1f}" y="276" font-family="Arial, sans-serif" font-size="11" fill="#6b7280">{tick / 5:.1f}</text>'
        )
    for index, result in enumerate(results):
        method = result["method"]
        y = top + index * gap
        value = result["recall"]
        bar_width = value * chart_width
        lines.append(
            f'<text x="36" y="{y + 23}" font-family="Arial, sans-serif" font-size="14" font-weight="700" fill="#111827">{labels[method]}</text>'
        )
        lines.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" rx="4" fill="{colors[method]}"/>'
        )
        lines.append(
            f'<text x="{left + bar_width + 10:.1f}" y="{y + 23}" font-family="Arial, sans-serif" font-size="13" fill="#111827">{value:.3f} ({result["gold_hits"]}/{result["gold_total"]})</text>'
        )
    lines.append(
        '<text x="36" y="314" font-family="Arial, sans-serif" font-size="12" fill="#6b7280">code2skill captures routes, calls, type references, data-flow, dynamic imports, re-exported symbols, exceptions, and dependency edges.</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines)


def gold_facts() -> list[str]:
    return [
        "role:src/shop/main.py:entrypoint",
        "role:src/shop/api/users.py:route",
        "import:src/shop/__init__.py:shop.core.ops",
        "import:src/shop/api/users.py:shop",
        "class:src/shop/core/ops.py:UserService",
        "class:src/shop/domain/accounts.py:AccountCreate",
        "class:src/shop/domain/accounts.py:AccountRecord",
        "method:src/shop/core/ops.py:UserService.create",
        "function:src/shop/api/users.py:create_user",
        "route:src/shop/api/users.py:POST /users->create_user",
        "call:src/shop/api/users.py:UserService",
        "call:src/shop/api/users.py:UserService.create",
        "type:src/shop/api/users.py:AccountCreate",
        "type:src/shop/core/ops.py:AccountRecord",
        "model:src/shop/domain/accounts.py:AccountCreate",
        "model:src/shop/domain/accounts.py:AccountRecord",
        "dependency:src/shop/__init__.py->src/shop/core/ops.py",
        "dependency:src/shop/api/users.py->src/shop/__init__.py",
        "dependency:src/shop/api/users.py->src/shop/core/ops.py",
        "dependency:src/shop/api/users.py->src/shop/domain/accounts.py",
        "dependency:src/shop/core/ops.py->src/shop/domain/accounts.py",
        "import:src/app/runtime/loader.py:importlib",
        "function:src/app/bootstrap.py:boot",
        "function:src/app/runtime/loader.py:load_plugin",
        "class:src/app/plugins/audit.py:AuditPlugin",
        "method:src/app/plugins/audit.py:AuditPlugin.record",
        "call:src/app/bootstrap.py:load_plugin",
        "call:src/app/runtime/loader.py:importlib.import_module",
        "call:src/app/runtime/loader.py:module.AuditPlugin",
        "dynamic_import:src/app/runtime/loader.py:app.plugins.audit",
        "data_flow:src/app/runtime/loader.py:load_plugin:module<-importlib.import_module",
        "dependency:src/app/bootstrap.py->src/app/runtime/loader.py",
        "dependency:src/app/runtime/loader.py->src/app/plugins/audit.py",
        "function:src/tool/runner.py:run",
        "class:src/tool/actions.py:ReleaseService",
        "method:src/tool/actions.py:ReleaseService.publish",
        "function:src/tool/state_store.py:load_state",
        "main_guard:src/tool/runner.py",
        "call:src/tool/runner.py:ReleaseService",
        "call:src/tool/runner.py:ReleaseService.publish",
        "call:src/tool/runner.py:load_state",
        "raise:src/tool/actions.py:ValueError",
        "data_flow:src/tool/runner.py:run:state<-load_state",
        "dependency:src/tool/runner.py->src/tool/actions.py",
        "dependency:src/tool/runner.py->src/tool/state_store.py",
    ]


def write_fixture_repo(repo_path: Path) -> None:
    files = {
        "src/shop/__init__.py": """
            from shop.core.ops import UserService
        """,
        "src/shop/main.py": """
            from fastapi import FastAPI
            from shop.api.users import router

            app = FastAPI()
            app.include_router(router)
        """,
        "src/shop/api/users.py": """
            from fastapi import APIRouter
            from shop import UserService
            from shop.domain.accounts import AccountCreate

            router = APIRouter()

            @router.post("/users")
            def create_user(payload: AccountCreate):
                return UserService().create(payload)
        """,
        "src/shop/core/ops.py": """
            from shop.domain.accounts import AccountCreate, AccountRecord

            class UserService:
                def create(self, payload: AccountCreate) -> AccountRecord:
                    return AccountRecord(id="new", email=payload.email)

                def list(self) -> list[AccountRecord]:
                    return []
        """,
        "src/shop/domain/accounts.py": """
            from pydantic import BaseModel

            class AccountCreate(BaseModel):
                email: str

            class AccountRecord(BaseModel):
                id: str
                email: str
        """,
        "src/app/bootstrap.py": """
            from app.runtime.loader import load_plugin

            def boot() -> object:
                return load_plugin("app.plugins.audit")
        """,
        "src/app/runtime/loader.py": """
            import importlib

            def load_plugin(path: str) -> object:
                module = importlib.import_module("app.plugins.audit")
                return module.AuditPlugin()
        """,
        "src/app/plugins/audit.py": """
            class AuditPlugin:
                def record(self, event: str) -> dict[str, str]:
                    return {"event": event}
        """,
        "src/tool/runner.py": """
            from tool.actions import ReleaseService
            from tool.state_store import load_state

            def run() -> None:
                state = load_state()
                ReleaseService().publish(state)

            if __name__ == "__main__":
                run()
        """,
        "src/tool/actions.py": """
            class ReleaseService:
                def publish(self, state: dict[str, str]) -> None:
                    if "version" not in state:
                        raise ValueError("missing version")
        """,
        "src/tool/state_store.py": """
            STATE_CACHE: dict[str, str] = {"version": "0.1.0"}

            def load_state() -> dict[str, str]:
                return STATE_CACHE
        """,
    }
    for relative_path, content in files.items():
        path = repo_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(trim_margin(content), encoding="utf-8")


def python_files(repo_path: Path) -> list[Path]:
    return sorted(path for path in repo_path.rglob("*.py") if path.is_file())


def trim_margin(text: str) -> str:
    lines = text.strip("\n").splitlines()
    indent = min(
        (len(line) - len(line.lstrip(" ")) for line in lines if line.strip()),
        default=0,
    )
    return "\n".join(line[indent:] for line in lines) + "\n"


def resolve_output(path: str) -> Path:
    output = Path(path)
    if output.is_absolute():
        return output
    return REPO_ROOT / output


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
