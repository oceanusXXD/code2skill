# Getting Started

This guide takes a Python repository from no generated AI context to a checked, reviewable Skill layer.

## 1. Install

Requires Python 3.10 or newer.

```bash
pip install code2skill
```

For local development from this repository:

```bash
pip install -e .[dev]
```

## 2. Run A No-LLM Smoke Check

Start with structural analysis. This checks repository discovery, path handling, reporting, and state writing without using a model.

```bash
code2skill scan . --structure-only
```

Expected files include:

- `.code2skill/adoption-guide.md`
- `.code2skill/project-summary.md`
- `.code2skill/skill-blueprint.json`
- `.code2skill/report.json`
- `.code2skill/state/analysis-state.json`

## 3. Preview Cost And Impact

```bash
code2skill estimate .
```

Open `.code2skill/report.json` and review:

- selected file counts
- retained character volume
- first-generation estimate
- incremental rewrite estimate
- changed files and affected Skills, when applicable

## 4. Generate Skills

Set your provider credentials, then run `scan` without `--structure-only`.

```bash
export QWEN_API_KEY=...
code2skill scan . --llm qwen --model qwen-plus-latest
```

Review:

- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- `.code2skill/skill-plan.json`

Generated Skills should be grounded in the files shown in the plan and should keep uncertainty explicit when evidence is weak.

## 5. Publish To An AI Tool

For Codex:

```bash
code2skill adapt . --target codex
```

This writes or updates `AGENTS.md`. Generated content is placed inside:

```text
<!-- code2skill:start -->
...
<!-- code2skill:end -->
```

Hand-written content outside that block is preserved.

For every supported target:

```bash
code2skill adapt . --target all
```

## 6. Validate Readiness

```bash
code2skill doctor . --target codex
```

`doctor` exits with code `1` if readiness fails. It checks the artifact bundle, JSON reports, state snapshot, Skill plan, Skill index links, generated Skill files, and optional target output.

For local diagnostics without a failing exit code:

```bash
code2skill doctor . --target codex --no-fail
```

## 7. Decide What To Commit

Recommended for most teams:

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- target files your team uses, such as `AGENTS.md`

Optional review artifacts:

- `.code2skill/project-summary.md`
- `.code2skill/references/*.md`
- `.code2skill/skill-plan.json`
- `.code2skill/report.json`

Treat `.code2skill/state/analysis-state.json` as a cache. Commit it only when you want a shared incremental baseline; otherwise cache `.code2skill/` in CI.

## 8. Add CI

After the first bundle exists:

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
code2skill adapt . --target codex
code2skill doctor . --target codex
```

See [CI Guide](./ci.md) for a complete GitHub Actions workflow.
