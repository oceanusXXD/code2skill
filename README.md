# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

Chinese documentation: [README.zh-CN.md](https://github.com/oceanusXXD/code2skill/blob/main/README.zh-CN.md).

`code2skill` compiles a Python repository into reviewable AI working instructions.

It reads real source-code evidence, builds a repository blueprint, asks an LLM to plan and write focused Skills, and can publish the same knowledge to Codex, Claude Code, Cursor, GitHub Copilot, and Windsurf. The result is a committed, testable instruction layer instead of stale chat context or scattered hand-written rules.

Use it when a Python project needs AI coding assistants to understand current module boundaries, workflows, contracts, and maintenance rules from the code that actually exists.

## What It Solves

- Turns repository structure and source evidence into AI-ready Skills.
- Keeps generated knowledge reviewable in Git and refreshable in CI.
- Publishes one Skill layer to several AI coding tools.
- Preserves hand-written target-file content through managed blocks.
- Validates generated bundles and adapted tool files with `doctor`.
- Supports OpenAI Responses API, OpenAI-compatible Responses endpoints, Claude, and Qwen.

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

- [Getting Started](https://github.com/oceanusXXD/code2skill/blob/main/docs/getting-started.md)
- [Use Cases](https://github.com/oceanusXXD/code2skill/blob/main/docs/use-cases.md)
- [CLI Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/cli.md)
- [CI Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/ci.md)
- [Python API](https://github.com/oceanusXXD/code2skill/blob/main/docs/python-api.md)
- [Output Layout](https://github.com/oceanusXXD/code2skill/blob/main/docs/output-layout.md)
- [Release Guide](https://github.com/oceanusXXD/code2skill/blob/main/docs/release.md)
- [Changelog](https://github.com/oceanusXXD/code2skill/blob/main/CHANGELOG.md)

## Guarantees

- Python-first analysis using `ast`, import graph analysis, file-role inference, and pattern detection.
- Evidence-first prompts that require source references and keep uncertainty explicit.
- Durable outputs written to disk instead of kept in chat history.
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
