# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

Language: English | [简体中文](https://github.com/oceanusXXD/code2skill/blob/main/README.zh-CN.md)

`code2skill` turns a Python repository into instruction files for coding assistants.

It scans source code and configuration, writes a `.code2skill/` bundle, generates focused Skill documents, and publishes them to Codex, Claude Code, Cursor, GitHub Copilot, or Windsurf. The files stay in the repository, so maintainers can review them, run them in CI, and update them when code changes.

Use it when a Python project needs coding assistants to follow the current module boundaries, workflows, API contracts, and maintenance rules.

## What This Repository Can Do

- Analyze a Python repository with AST semantic extraction, import graph checks, call/type/data-flow evidence, config extraction, and file-role inference.
- Write a `.code2skill/` bundle with a project summary, references, a Skill plan, generated Skills, a report, and incremental state.
- Estimate model cost and affected Skills before generation.
- Generate Skill Markdown from repository evidence using OpenAI Responses API, OpenAI-compatible Responses endpoints, Claude, or Qwen.
- Publish generated Skills into `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, `.github/copilot-instructions.md`, and `.windsurfrules`.
- Refresh outputs in CI with full or incremental mode.
- Validate the bundle and target files with `doctor`.

## Who It Is For

| User | Need | What code2skill provides |
|---|---|---|
| Python maintainers | Assistants should follow local architecture and naming patterns | Source-based Skill files and readiness checks |
| DevEx and platform teams | Several services need the same assistant setup process | CLI, Python API, CI refresh, and shared output layout |
| Open-source maintainers | Contributors need public project instructions instead of untracked notes | Committed files that can be reviewed with the rest of the repo |
| Tooling evaluators | One repository needs to work with several coding assistants | One generated Skill layer adapted into multiple target formats |

## Common Scenarios

| Scenario | When to use it | Expected result |
|---|---|---|
| First assistant setup | A repo starts using Codex, Cursor, Claude Code, Copilot, or Windsurf | `scan`, `adapt`, and `doctor` produce a ready target file |
| Pull request refresh | Code changes may make previous instructions stale | `ci --mode auto` reports changed files, affected files, and affected Skills |
| Multi-tool setup | A team uses more than one coding assistant | `adapt --target all` writes consistent target files |
| Platform automation | A DevEx team runs the workflow across many Python services | Python API returns structured results and readiness status |
| Contributor onboarding | New contributors need project-specific implementation rules | Generated Skills and docs describe the repo's working contracts |

## Install

Requires Python 3.10 or newer.

```bash
python -m pip install code2skill
code2skill --version
code2skill --help
```

The expected CLI commands are `scan`, `estimate`, `ci`, `adapt`, and `doctor`.

If the console script is not on `PATH`, use the module entry point:

```bash
python -m code2skill --help
```

## First Run

Run a no-LLM structural check first. This verifies that the package can read the repository and write the local artifact bundle.

```bash
code2skill scan . --structure-only
```

Preview model cost and incremental impact:

```bash
code2skill estimate .
```

Generate Skills with a model provider:

```bash
export QWEN_API_KEY=...
code2skill scan . --llm qwen --model qwen-plus-latest
```

Publish the generated Skill layer to an AI tool:

```bash
code2skill adapt . --target codex
```

Check that the bundle and target file are ready to use:

```bash
code2skill doctor . --target codex
```

Review and commit the files that matter for your workflow:

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- adapted target files such as `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, `.github/copilot-instructions.md`, or `.windsurfrules`

Use `.code2skill/report.json` to inspect selected files, execution mode, changed files, affected Skills, cost estimates, and generated outputs.

## Model Configuration

Common environment variables:

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

Provider keys:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

OpenAI Responses API:

```bash
export CODE2SKILL_LLM=openai
export CODE2SKILL_MODEL=gpt-4o-mini
export CODE2SKILL_OPENAI_API_KEY=...
code2skill scan .
```

OpenAI-compatible Responses endpoint:

```bash
export CODE2SKILL_LLM=openai
export CODE2SKILL_MODEL=<responses-compatible-model>
export CODE2SKILL_OPENAI_API_KEY=...
export CODE2SKILL_OPENAI_BASE_URL=https://example.com/v1
code2skill scan .
```

`CODE2SKILL_OPENAI_BASE_URL` may point either to a `/v1` base URL or directly to a `/responses` endpoint.

## Commands

| Command | Calls LLM | Writes files | Primary purpose |
|---|---:|---:|---|
| `scan` | Yes, unless `--structure-only` | Yes | Full local analysis and Skill generation |
| `estimate` | No | `report.json` only | Cost and impact preview |
| `ci` | Yes, unless `--structure-only` | Yes | Automation-friendly full or incremental refresh |
| `adapt` | No | Yes | Publish generated Skills to target AI tool files |
| `doctor` | No | No | Validate bundle, Skill plan, state, target files, and readiness |

## Output Layout

The default artifact directory is `.code2skill/`.

| Path | Purpose |
|---|---|
| `adoption-guide.md` | Repository-specific adoption checklist and next workflow |
| `project-summary.md` | Human-readable repository summary |
| `skill-blueprint.json` | Structural repository blueprint |
| `skill-plan.json` | LLM-planned Skill inventory |
| `references/*.md` | Architecture, style, workflow, and API references |
| `skills/index.md` | Generated Skill index |
| `skills/*.md` | Generated AI working instructions |
| `report.json` | Execution metrics, cost estimates, changed files, affected Skills, and artifact lists |
| `state/analysis-state.json` | Incremental CI cache |

## Target Tools

| Target | Command | Output |
|---|---|---|
| Codex | `code2skill adapt . --target codex` | `AGENTS.md` |
| Claude Code | `code2skill adapt . --target claude` | `CLAUDE.md` |
| Cursor | `code2skill adapt . --target cursor` | `.cursor/rules/*.md` plus `.cursor/rules/.code2skill-manifest.json` |
| GitHub Copilot | `code2skill adapt . --target copilot` | `.github/copilot-instructions.md` |
| Windsurf | `code2skill adapt . --target windsurf` | `.windsurfrules` |
| All targets | `code2skill adapt . --target all` | all of the above |

Merge-style targets use a managed block:

```text
<!-- code2skill:start -->
...
<!-- code2skill:end -->
```

Content outside the managed block is preserved. Cursor uses copied Skill files and a manifest so later runs can remove stale generated files while keeping unmanaged team rules.

## CI Refresh

After the first bundle exists, use `ci --mode auto` to reuse state and regenerate only affected Skill outputs when code changes.

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
code2skill adapt . --target codex
code2skill doctor . --target codex
```

The first CI run usually falls back to `full` because no state exists yet. Later runs can use `.code2skill/state/analysis-state.json` and `skill-plan.json` to decide whether incremental refresh is safe.

## Python API

The package root exports the supported high-level API:

```python
from pathlib import Path

from code2skill import adapt_repository, doctor, estimate, scan

repo = Path(".")

preview = estimate(repo)
result = scan(
    repo,
    llm_provider="qwen",
    llm_model="qwen-plus-latest",
    max_skills=6,
)
written = adapt_repository(repo, target="codex")
readiness = doctor(repo, target="codex")

print(preview.report_path)
print(result.generated_skills)
print(written)
print(readiness.ready, readiness.score)
```

For lower-level automation, use `create_scan_config(...)` with `scan_repository(...)`, `estimate_repository(...)`, or `run_ci_repository(...)`.

## Documentation

- English README: [README.md](https://github.com/oceanusXXD/code2skill/blob/main/README.md)
- Chinese README: [README.zh-CN.md](https://github.com/oceanusXXD/code2skill/blob/main/README.zh-CN.md)
- [Getting Started](https://github.com/oceanusXXD/code2skill/blob/main/docs/getting-started.md)
- [Use Cases](https://github.com/oceanusXXD/code2skill/blob/main/docs/use-cases.md)
- [CLI Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/cli.md)
- [CI Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/ci.md)
- [Python API](https://github.com/oceanusXXD/code2skill/blob/main/docs/python-api.md)
- [Output Layout](https://github.com/oceanusXXD/code2skill/blob/main/docs/output-layout.md)
- [Algorithm Notes](https://github.com/oceanusXXD/code2skill/blob/main/docs/algorithm-notes.md)
- [Release Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/release.md)
- [Changelog](https://github.com/oceanusXXD/code2skill/blob/main/CHANGELOG.md)

## Guarantees

- Python-first analysis using `ast`, import graph analysis, file-role inference, and pattern detection.
- Evidence-first prompts that require source references and keep uncertainty explicit.
- Outputs written to files instead of kept in chat history.
- Measurable runs through `report.json`.
- Incremental operation through state reuse, diff impact, and affected Skill mapping.
- Readiness validation through `doctor`.

## Limitations

- Optimized for Python repositories.
- Non-Python code is scanned only as supporting context, not as a first-class analysis target.
- Output quality still depends on repository clarity and the selected model.
- The package is in the `0.1.x` stage and public behavior may continue to evolve.

## License

Apache-2.0. See [LICENSE](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE).
