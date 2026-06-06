# CLI Guide

`code2skill` exposes five CLI commands that form one repository-knowledge workflow:

- `scan`: build repository analysis and, unless structure-only, generate Skills
- `estimate`: preview cost and impact without generating Skills or state
- `ci`: run automation-friendly full or incremental refresh
- `adapt`: publish generated Skills to target tool instruction files
- `doctor`: verify that the bundle and optional target output are ready to use

`repo_path` is optional for every command and defaults to `.`. Relative paths are resolved from the target repository root, so you can run the CLI from inside or outside the repository.

## Entry Points

```bash
code2skill --help
python -m code2skill --help
```

## First Workflow

```bash
code2skill scan . --structure-only
code2skill estimate .
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target codex
code2skill doctor . --target codex
```

The first command is a no-LLM smoke check. The second command writes a cost and impact report. The third command generates Skills. The fourth command publishes them into `AGENTS.md`. The fifth command validates that the bundle, plan, state, Skills, and target file are present and internally consistent.

## Command Reference

| Command | Default repo | Default mode | Calls LLM | Writes state | Main output | Key flags |
|---|---|---|---:|---:|---|---|
| `scan` | `.` | `full` | Yes, unless `--structure-only` | Yes | `.code2skill/` bundle and Skills | `--structure-only`, `--llm`, `--model`, `--max-skills` |
| `estimate` | `.` | `auto` | No | No | `report.json` | `--mode`, `--base-ref`, `--diff-file`, `--pricing-file` |
| `ci` | `.` | `auto` | Yes, unless `--structure-only` | Yes | refreshed `.code2skill/` bundle | `--mode`, `--base-ref`, `--head-ref`, `--diff-file` |
| `adapt` | `.` | n/a | No | No | target instruction files | `--target`, `--source-dir` |
| `doctor` | `.` | n/a | No | No | readiness diagnostics | `--target`, `--output-dir`, `--no-fail` |

## Repository Path Model

- Relative `repo_path` values are resolved from the current shell location.
- Relative `--output-dir`, `--report-json`, `--diff-file`, and `--pricing-file` values are resolved from `repo_path`.
- For `adapt`, relative `--source-dir` values are resolved from `repo_path`.
- For `doctor`, relative `--output-dir` values are resolved from `repo_path`.

This keeps path behavior stable in local shells, CI jobs, and automation scripts.

## Common Examples

Full generation:

```bash
code2skill scan /path/to/repo --llm qwen --model qwen-plus-latest
```

Structure-only scan:

```bash
code2skill scan /path/to/repo --structure-only
```

Cost preview:

```bash
code2skill estimate /path/to/repo --pricing-file pricing.json
```

Incremental CI run:

```bash
code2skill ci /path/to/repo --mode auto --base-ref origin/main --head-ref HEAD
```

Adapt generated Skills into Codex format:

```bash
code2skill adapt /path/to/repo --target codex
```

For Cursor, `adapt` copies Skills into `.cursor/rules/` and writes `.cursor/rules/.code2skill-manifest.json` so stale generated Markdown can be removed on later runs without deleting unmanaged team rules.

Verify readiness without writing files:

```bash
code2skill doctor /path/to/repo --target codex
```

Run diagnostics without failing the shell:

```bash
code2skill doctor /path/to/repo --target codex --no-fail
```

## `doctor` Readiness Checks

`doctor` checks:

- `.code2skill/` exists
- `project-summary.md`, `adoption-guide.md`, and `report.json` exist
- `report.json` is valid JSON and referenced artifacts exist
- `skills/index.md` and at least one generated Skill exist
- index links point to existing Skill files
- `skill-plan.json` is valid and maps each planned Skill to a generated file
- `state/analysis-state.json` is valid and belongs to the same repository root
- optional target output exists, such as `AGENTS.md` for `--target codex`

By default, `doctor` exits `1` when readiness fails. Use `--no-fail` when you only want a local diagnostic report.

## Environment Defaults

```bash
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
export CODE2SKILL_HEAD_REF=HEAD
export CODE2SKILL_SOURCE_DIR=.code2skill/skills
export CODE2SKILL_TARGET=codex
```

Provider keys:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

OpenAI-compatible Responses endpoints are supported with:

```bash
export CODE2SKILL_LLM=openai
export CODE2SKILL_MODEL=<responses-compatible-model>
export CODE2SKILL_OPENAI_API_KEY=...
export CODE2SKILL_OPENAI_BASE_URL=https://example.com/v1
```

## Output Summary

Successful `scan`, `estimate`, and `ci` commands print:

- command name
- effective mode
- repository path
- repository type
- selected file counts
- retained character volume
- output directory
- report path
- final products and intermediate artifact counts
- updated and written files

`adapt` prints the repository root, target, source directory, and written target files.

`doctor` prints readiness status, score, per-check messages, missing paths, and next-step commands.

## Exit Behavior

- Success returns exit code `0`.
- `doctor` returns exit code `1` when readiness fails unless `--no-fail` is used.
- User-facing runtime errors return exit code `1` and print `code2skill: error: ...` to stderr.
- `Ctrl+C` returns exit code `130`.
