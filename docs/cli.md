# CLI Guide

`code2skill` exposes four CLI commands.

They form one repository-knowledge workflow:

- `scan`: build the full analysis, planning, and generation artifact set
- `estimate`: preview impact and cost without writing Skills or state
- `ci`: run the automation-oriented workflow that can choose full or incremental execution
- `adapt`: publish generated Skill artifacts into target tool instruction files

This workflow model is intentional: the CLI now treats repository analysis, artifact generation, and target adaptation as linked stages of one product surface rather than unrelated commands.

## Entry Points

```bash
code2skill --help
python -m code2skill --help
```

## Repository Path Model

Every command accepts an explicit `repo_path`.

- Relative `repo_path` values are resolved from the current shell location.
- Relative `--output-dir`, `--report-json`, `--diff-file`, and `--pricing-file` values are resolved from `repo_path`.
- For `adapt`, relative `--source-dir` values are also resolved from `repo_path`.

This means callers can run the CLI from outside the target repository without changing path semantics.

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

## Exit Behavior

- Success returns exit code `0`.
- User-facing runtime errors return exit code `1` and print a concise `code2skill: error: ...` message to stderr.
- `Ctrl+C` returns exit code `130`.

## Output Summary

Successful `scan`, `estimate`, and `ci` commands print a compact summary including:

- the command name
- the effective mode
- repository path
- repository type
- selected file counts
- retained character volume
- output directory
- report path when available
- generated artifact paths

`adapt` prints the repository root, target, source directory, and written files.
