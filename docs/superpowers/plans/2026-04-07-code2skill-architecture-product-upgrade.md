# code2skill Architecture Product Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `code2skill` around workflow-oriented product interfaces and layered internals while preserving the current artifact contract and the existing `scan`, `estimate`, `ci`, and `adapt` entrypoints during migration.

**Architecture:** Introduce `domain`, `workflows`, `product`, and `capabilities/adapt` packages first, then route API and CLI through those workflows before shrinking legacy orchestration. Preserve the public entrypoints and default `.code2skill` artifact layout while moving path resolution, run summaries, and adapter behavior into focused modules.

**Tech Stack:** Python 3.10+, setuptools, pytest, argparse, pathlib, dataclasses

---

## File Structure

- Create: `src/code2skill/domain/__init__.py`
- Create: `src/code2skill/domain/artifacts.py`
- Create: `src/code2skill/domain/results.py`
- Create: `src/code2skill/workflows/__init__.py`
- Create: `src/code2skill/workflows/requests.py`
- Create: `src/code2skill/workflows/runners.py`
- Create: `src/code2skill/product/__init__.py`
- Create: `src/code2skill/product/cli_summary.py`
- Create: `src/code2skill/capabilities/adapt/__init__.py`
- Create: `src/code2skill/capabilities/adapt/targets.py`
- Create: `tests/test_workflow_requests.py`
- Create: `tests/test_cli_summary.py`
- Modify: `src/code2skill/api.py`
- Modify: `src/code2skill/cli.py`
- Modify: `src/code2skill/adapt.py`
- Modify: `src/code2skill/__init__.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_cli.py`
- Modify: `docs/cli.md`
- Modify: `docs/python-api.md`
- Modify: `docs/output-layout.md`

### Task 1: Introduce workflow request and result contracts

**Files:**
- Create: `src/code2skill/domain/artifacts.py`
- Create: `src/code2skill/domain/results.py`
- Create: `src/code2skill/workflows/requests.py`
- Create: `tests/test_workflow_requests.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from code2skill.domain.artifacts import ArtifactLayout
from code2skill.domain.results import CommandRunSummary
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

    request = WorkflowRequest.for_command(
        command="scan",
        repo_path=repo_path,
        output_dir=".generated",
    )

    assert request.repo_path == repo_path.resolve()
    assert request.output_dir == (repo_path / ".generated").resolve()


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


def test_command_run_summary_keeps_writes_in_order() -> None:
    summary = CommandRunSummary(
        command="scan",
        mode="full",
        repo_path=Path("/repo"),
        output_dir=Path("/repo/.code2skill"),
        written_paths=[Path("/repo/.code2skill/report.json"), Path("/repo/.code2skill/skills/index.md")],
    )

    assert summary.written_paths[0].name == "report.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workflow_requests.py -v`
Expected: FAIL with `ModuleNotFoundError` for `code2skill.domain` or missing symbols.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/code2skill/domain/artifacts.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactLayout:
    root: Path
    skills_dir: Path
    report_path: Path
    skill_plan_path: Path
    blueprint_path: Path
    state_path: Path

    @classmethod
    def from_repo_root(cls, repo_root: Path, output_dir: Path | str = ".code2skill") -> "ArtifactLayout":
        resolved_root = repo_root.resolve()
        artifact_root = (resolved_root / output_dir).resolve() if not Path(output_dir).is_absolute() else Path(output_dir).resolve()
        return cls(
            root=artifact_root,
            skills_dir=artifact_root / "skills",
            report_path=artifact_root / "report.json",
            skill_plan_path=artifact_root / "skill-plan.json",
            blueprint_path=artifact_root / "skill-blueprint.json",
            state_path=artifact_root / "state" / "analysis-state.json",
        )
```

```python
# src/code2skill/domain/results.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CommandRunSummary:
    command: str
    mode: str
    repo_path: Path
    output_dir: Path
    written_paths: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
```

```python
# src/code2skill/workflows/requests.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _resolve_repo_path(repo_path: Path | str) -> Path:
    return Path(repo_path).resolve()


def _resolve_repo_relative(repo_root: Path, value: Path | str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


@dataclass(frozen=True)
class WorkflowRequest:
    command: str
    repo_path: Path
    output_dir: Path

    @classmethod
    def for_command(
        cls,
        *,
        command: str,
        repo_path: Path | str,
        output_dir: Path | str = ".code2skill",
    ) -> "WorkflowRequest":
        resolved_repo = _resolve_repo_path(repo_path)
        return cls(
            command=command,
            repo_path=resolved_repo,
            output_dir=_resolve_repo_relative(resolved_repo, output_dir),
        )


@dataclass(frozen=True)
class AdaptRequest:
    repo_path: Path
    target: str
    source_dir: Path
    destination_root: Path

    @classmethod
    def create(
        cls,
        *,
        repo_path: Path | str,
        target: str,
        source_dir: Path | str = ".code2skill/skills",
    ) -> "AdaptRequest":
        resolved_repo = _resolve_repo_path(repo_path)
        return cls(
            repo_path=resolved_repo,
            target=target,
            source_dir=_resolve_repo_relative(resolved_repo, source_dir),
            destination_root=resolved_repo,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workflow_requests.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflow_requests.py src/code2skill/domain/artifacts.py src/code2skill/domain/results.py src/code2skill/workflows/requests.py
git commit -m "feat: add workflow request contracts"
```

### Task 2: Add workflow runners that wrap existing orchestration

**Files:**
- Create: `src/code2skill/workflows/runners.py`
- Modify: `src/code2skill/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from code2skill.api import adapt_repository
from code2skill.workflows.runners import adapt_with_request


def test_adapt_repository_resolves_source_dir_from_repo_root(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    def fake_adapt(target: str, source_dir, destination_root):
        captured["target"] = target
        captured["source_dir"] = source_dir
        captured["destination_root"] = destination_root
        return []

    monkeypatch.setattr("code2skill.workflows.runners.adapt_skills", fake_adapt)

    adapt_repository(repo_path=repo_path, target="codex", source_dir="generated-skills")

    assert captured["source_dir"] == (repo_path / "generated-skills").resolve()


def test_adapt_with_request_returns_written_paths(monkeypatch, tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    monkeypatch.setattr(
        "code2skill.workflows.runners.adapt_skills",
        lambda target, source_dir, destination_root: [destination_root / "AGENTS.md"],
    )

    written = adapt_with_request(repo_path=repo_path, target="codex")

    assert written == [(repo_path / "AGENTS.md").resolve()]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_adapt_repository_resolves_source_dir_from_repo_root tests/test_api.py::test_adapt_with_request_returns_written_paths -v`
Expected: FAIL because `workflows.runners` does not exist or `adapt_repository` still bypasses repo-relative request handling.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/code2skill/workflows/runners.py
from __future__ import annotations

from pathlib import Path

from code2skill.adapt import adapt_skills
from code2skill.workflows.requests import AdaptRequest


def adapt_with_request(
    *,
    repo_path: Path | str,
    target: str,
    source_dir: Path | str = ".code2skill/skills",
) -> list[Path]:
    request = AdaptRequest.create(repo_path=repo_path, target=target, source_dir=source_dir)
    return adapt_skills(
        target=request.target,
        source_dir=request.source_dir,
        destination_root=request.destination_root,
    )
```

```python
# src/code2skill/api.py
from code2skill.workflows.runners import adapt_with_request


def adapt_repository(...):
    return adapt_with_request(repo_path=repo_path, target=target, source_dir=source_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py::test_adapt_repository_resolves_source_dir_from_repo_root tests/test_api.py::test_adapt_with_request_returns_written_paths -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/code2skill/workflows/runners.py src/code2skill/api.py tests/test_api.py
git commit -m "fix: route adapt api through workflow request"
```

### Task 3: Move CLI summaries into a product module

**Files:**
- Create: `src/code2skill/product/cli_summary.py`
- Modify: `src/code2skill/cli.py`
- Create: `tests/test_cli_summary.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from code2skill.domain.results import CommandRunSummary
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
        "repo: /repo",
        "output_dir: /repo/.code2skill",
        "wrote: /repo/.code2skill/report.json",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_summary.py -v`
Expected: FAIL with `ModuleNotFoundError` for `code2skill.product.cli_summary`.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/code2skill/product/cli_summary.py
from __future__ import annotations

from code2skill.domain.results import CommandRunSummary


def render_summary_lines(summary: CommandRunSummary) -> list[str]:
    lines = [
        f"command: {summary.command}",
        f"mode: {summary.mode}",
        f"repo: {summary.repo_path}",
        f"output_dir: {summary.output_dir}",
    ]
    lines.extend(f"wrote: {path}" for path in summary.written_paths)
    return lines
```

```python
# src/code2skill/cli.py
from code2skill.domain.results import CommandRunSummary
from code2skill.product.cli_summary import render_summary_lines


def _print_summary(summary: CommandRunSummary) -> None:
    for line in render_summary_lines(summary):
        print(line)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_summary.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/code2skill/product/cli_summary.py src/code2skill/cli.py tests/test_cli_summary.py tests/test_cli.py
git commit -m "refactor: isolate cli run summary formatting"
```

### Task 4: Introduce target metadata for adaptation

**Files:**
- Create: `src/code2skill/capabilities/adapt/targets.py`
- Modify: `src/code2skill/adapt.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
from code2skill.capabilities.adapt.targets import get_target_definition


def test_get_target_definition_for_codex_has_agents_output() -> None:
    target = get_target_definition("codex")

    assert target.name == "codex"
    assert target.output_paths == ["AGENTS.md"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_get_target_definition_for_codex_has_agents_output -v`
Expected: FAIL because target metadata module does not exist.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/code2skill/capabilities/adapt/targets.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetDefinition:
    name: str
    output_paths: list[str]


_TARGETS = {
    "codex": TargetDefinition(name="codex", output_paths=["AGENTS.md"]),
    "claude": TargetDefinition(name="claude", output_paths=["CLAUDE.md"]),
    "copilot": TargetDefinition(name="copilot", output_paths=[".github/copilot-instructions.md"]),
    "windsurf": TargetDefinition(name="windsurf", output_paths=[".windsurfrules"]),
}


def get_target_definition(name: str) -> TargetDefinition:
    return _TARGETS[name]
```

```python
# src/code2skill/adapt.py
from code2skill.capabilities.adapt.targets import get_target_definition


def adapt_skills(...):
    target_definition = get_target_definition(target)
    # keep existing rendering logic, but route output path selection through target_definition
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py::test_get_target_definition_for_codex_has_agents_output -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/code2skill/capabilities/adapt/targets.py src/code2skill/adapt.py tests/test_api.py
git commit -m "refactor: add target metadata for adaptation"
```

### Task 5: Route API helpers through workflow requests

**Files:**
- Modify: `src/code2skill/api.py`
- Modify: `src/code2skill/__init__.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from code2skill.api import create_scan_config


def test_create_scan_config_uses_workflow_request_output_resolution(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    config = create_scan_config(repo_path=repo_path, command="scan", output_dir=".generated")

    assert config.output_dir == (repo_path / ".generated").resolve()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_create_scan_config_uses_workflow_request_output_resolution -v`
Expected: FAIL after introducing workflow requests until `api.py` is updated to use one shared resolver.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/code2skill/api.py
from code2skill.workflows.requests import WorkflowRequest


def create_scan_config(...):
    request = WorkflowRequest.for_command(
        command=command,
        repo_path=repo_path,
        output_dir=output_dir,
    )
    resolved_repo_path = request.repo_path
    resolved_output_dir = request.output_dir
    # keep existing run option construction, but reuse resolved paths from WorkflowRequest
```

```python
# src/code2skill/__init__.py
from .domain.artifacts import ArtifactLayout
from .domain.results import CommandRunSummary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/code2skill/api.py src/code2skill/__init__.py tests/test_api.py
git commit -m "refactor: share api path resolution through workflow requests"
```

### Task 6: Route CLI command execution through workflow-aware summaries

**Files:**
- Modify: `src/code2skill/cli.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from code2skill.domain.results import CommandRunSummary


def test_cli_uses_summary_renderer_for_success_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "code2skill.cli._run_command",
        lambda parser, args: CommandRunSummary(
            command="scan",
            mode="full",
            repo_path=Path("/repo"),
            output_dir=Path("/repo/.code2skill"),
            written_paths=[Path("/repo/.code2skill/report.json")],
        ),
    )

    exit_code = __import__("code2skill.cli", fromlist=["main"]).main(["scan"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "command: scan" in captured.out
    assert "wrote: /repo/.code2skill/report.json" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_cli_uses_summary_renderer_for_success_output -v`
Expected: FAIL because `main()` currently assumes raw command results, not `CommandRunSummary` objects.

- [ ] **Step 3: Write the minimal implementation**

```python
# src/code2skill/cli.py
from code2skill.domain.results import CommandRunSummary


def main(argv: list[str] | None = None) -> int:
    ...
    result = _run_command(parser, args)
    if isinstance(result, CommandRunSummary):
        _print_summary(result)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/code2skill/cli.py tests/test_cli.py
git commit -m "refactor: support workflow summaries in cli main"
```

### Task 7: Update docs to match the upgraded public contract

**Files:**
- Modify: `docs/cli.md`
- Modify: `docs/python-api.md`
- Modify: `docs/output-layout.md`

- [ ] **Step 1: Write the failing doc assertions**

```python
from pathlib import Path


def test_docs_refer_to_workflow_oriented_product_terms() -> None:
    cli_doc = Path("docs/cli.md").read_text(encoding="utf-8")
    api_doc = Path("docs/python-api.md").read_text(encoding="utf-8")
    layout_doc = Path("docs/output-layout.md").read_text(encoding="utf-8")

    assert "workflow" in cli_doc.lower()
    assert "repo_path" in api_doc
    assert "analysis-state.json" in layout_doc
```
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::test_docs_refer_to_workflow_oriented_product_terms -v`
Expected: FAIL until the docs are updated and the assertion is moved to a doc-focused test file if needed.

- [ ] **Step 3: Write the minimal implementation**

```md
# docs/cli.md
Add a short section explaining that the commands represent one repository knowledge workflow and that path resolution is repo-relative by default.
```

```md
# docs/python-api.md
Clarify that the high-level helpers align with workflow-oriented operations and that `adapt_repository(...)` resolves relative `source_dir` values from `repo_path`.
```

```md
# docs/output-layout.md
Add language that describes `.code2skill/` as the artifact bundle root for analysis, planning, generation, reports, and state.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/cli.md docs/python-api.md docs/output-layout.md tests/test_api.py
git commit -m "docs: align public contract with workflow architecture"
```

### Task 8: Full verification pass

**Files:**
- Modify: any file changed above as needed during verification
- Test: `tests/test_api.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_workflow_requests.py`
- Test: `tests/test_cli_summary.py`

- [ ] **Step 1: Run focused tests**

Run: `pytest tests/test_workflow_requests.py tests/test_cli_summary.py tests/test_api.py tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 3: Inspect package diagnostics**

Run: `python -m compileall src`
Expected: `Listing 'src'...` followed by successful compilation without errors.

- [ ] **Step 4: Commit the verified migration slice**

```bash
git add src docs tests
git commit -m "refactor: add workflow-oriented product foundation"
```

## Self-Review

- Spec coverage: this plan covers the first delivery slice of the approved design by introducing workflow/domain/product boundaries, fixing the known `adapt_repository` contract debt, normalizing target metadata, and preparing CLI/API output around workflow summaries.
- Placeholder scan: no `TODO`, `TBD`, or deferred implementation markers remain in the plan steps.
- Type consistency: the same `ArtifactLayout`, `CommandRunSummary`, `WorkflowRequest`, `AdaptRequest`, and `adapt_with_request(...)` names are used consistently across tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-code2skill-architecture-product-upgrade.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

For this session, the user has already authorized autonomous continuation, so proceed with **Inline Execution** unless a later step reveals a hard blocker.
