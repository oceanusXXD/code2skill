# CI Guide

`code2skill ci --mode auto` is the automation-oriented entrypoint for keeping AI-facing repository knowledge current as code changes.

Auto mode uses the previous `.code2skill/state/analysis-state.json`, the previous `skill-plan.json`, and the current diff to choose between a full rebuild and an incremental refresh.

## Consumer GitHub Actions Workflow

Use this in a repository that wants generated Skills and target instruction files refreshed in CI.

```yaml
name: code2skill

on:
  pull_request:
  workflow_dispatch:

jobs:
  code2skill:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - uses: actions/cache@v4
        with:
          path: .code2skill
          key: code2skill-${{ runner.os }}-${{ github.ref_name }}
          restore-keys: |
            code2skill-${{ runner.os }}-

      - name: Install code2skill
        run: python -m pip install code2skill

      - name: Refresh repository Skills
        env:
          QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
          CODE2SKILL_LLM: qwen
          CODE2SKILL_MODEL: qwen-plus-latest
        run: |
          code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
          code2skill adapt . --target codex
          code2skill doctor . --target codex
```

`doctor` fails the job if the bundle, generated Skills, state, plan, or adapted target file are missing or inconsistent.

## No-LLM CI Sanity Check

For a cheap PR check that validates scanning and reporting without calling a model:

```yaml
name: code2skill-structure

on:
  pull_request:

jobs:
  structure:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install code2skill
        run: python -m pip install code2skill

      - name: Structure-only refresh
        run: |
          code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD --structure-only
```

This writes structural artifacts and `report.json`, but it does not generate Skills.

## What Auto Mode Uses

Auto mode decides from:

- the resolved repository root
- `.code2skill/state/analysis-state.json`
- `.code2skill/skill-plan.json`
- changed files discovered from Git refs or an explicit diff file
- config-change triggers such as `pyproject.toml` or `requirements.txt`
- the configured maximum incremental changed-file count

## Required Inputs

Common CI invocation:

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
```

Diff-file invocation:

```bash
code2skill ci . --mode auto --diff-file path/to/changes.diff
```

## Incremental Reuse Requirements

Incremental reuse depends on:

- a previous `.code2skill/state/analysis-state.json`
- a previous `.code2skill/skill-plan.json`
- the saved state belonging to the same resolved repository root
- a changed-file set that is small enough for configured incremental limits

If these conditions are missing or invalid, `code2skill` falls back to a full rebuild.

## Common Full-Rebuild Triggers

- first run with no saved state
- non-Git directory and no explicit diff file
- `pyproject.toml`, `requirements.txt`, Docker files, or other high-value root config changes
- too many changed files for safe incremental execution
- cached state from a different repository root
- affected Skills no longer matching the current `skill-plan.json`

## PR Review Strategy

Review these files when a PR changes generated repository knowledge:

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- adapted target files, such as `AGENTS.md`
- `.code2skill/report.json`

`report.json` tells reviewers whether the run used `full` or `incremental`, which files changed, which Skills were affected, and which artifacts were written.

## Current Repository Workflows

This repository also includes maintainer workflows under `.github/workflows/`:

- `ci.yml`: test matrix, build, metadata check, and install smoke test
- `release.yml`: version validation, build, metadata check, and GitHub Release creation on version tags
- `publish-pypi.yml`: manual PyPI publication workflow
