# CI Guide

`code2skill ci --mode auto` is the automation-oriented entrypoint.

## What Auto Mode Uses

Auto mode decides between full and incremental execution from:

- the current repository root
- the presence or absence of `.code2skill/state/analysis-state.json`
- the presence or absence of `skill-plan.json`
- changed files discovered from Git refs or an explicit diff file
- fallback triggers such as changed core config files or too many modified files

## GitHub Actions

This repository includes checked-in workflows under `.github/workflows/`:

- `ci.yml`: test matrix, build, metadata check, and install smoke test
- `release.yml`: version validation, build, metadata check, and GitHub Release creation on version tags

The README includes a sample consumer workflow for running `code2skill` inside another repository.

## Required Inputs

Common CI arguments:

```bash
code2skill ci /path/to/repo --mode auto --base-ref origin/main --head-ref HEAD
```

Optional diff-file workflow:

```bash
code2skill ci /path/to/repo --mode auto --diff-file path/to/changes.diff
```

## Incremental Reuse Requirements

Incremental reuse depends on:

- a previous `.code2skill/state/analysis-state.json`
- a previous `skill-plan.json`
- the saved state belonging to the same resolved repository root

If any of these conditions are missing or invalid, `code2skill` safely falls back to a full rebuild.

## Common Full-Rebuild Triggers

- first run with no saved state
- non-Git directory and no explicit diff file
- `pyproject.toml`, `requirements.txt`, or another core config trigger changed
- too many changed files for safe incremental execution
- cached state from a different repository root

## No-LLM CI Sanity Check

If you want an artifact and structure sanity check without planning or generation, use:

```bash
code2skill ci /path/to/repo --mode auto --structure-only
```
