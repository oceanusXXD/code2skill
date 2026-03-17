# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

English README. For Chinese documentation, see [README.zh-CN.md](./README.zh-CN.md).

`code2skill` turns a real Python repository into structured project knowledge, reusable AI skill documents, and IDE-ready rule files for tools such as Cursor, Claude Code, Codex, GitHub Copilot, and Windsurf.

Instead of relying on one long prompt, it builds durable repository artifacts that can be committed, reviewed, reused, and incrementally regenerated in CI.

## What It Generates

From one Python repository, `code2skill` can generate:

- `project-summary.md` for a human-readable overview
- `skill-blueprint.json` for the structured Phase 1 repository blueprint
- `skill-plan.json` for LLM-generated skill planning
- `skills/index.md` and `skills/*.md` for grounded AI-consumable skill documents
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, and other target-specific outputs via `adapt`

## Why It Exists

Most AI coding workflows still depend on ad-hoc prompts, chat history, or manually curated notes. That does not scale well for real repositories.

`code2skill` is designed to:

- extract repository structure before asking an LLM to synthesize rules
- preserve repository knowledge as files rather than transient conversations
- make AI context reproducible in local workflows and CI
- keep generated guidance grounded in code, imports, patterns, and selected evidence

## Current Scope

- Python repositories only
- Python source analysis uses `ast`
- Phase 1 does not require an LLM
- Supports `scan`, `estimate`, `ci`, and `adapt`
- Supports `openai`, `claude`, and `qwen`
- Default generated prompts and skill documents are in English

## Installation

Published package:

```bash
pip install code2skill
```

Development install:

```bash
pip install -e .[dev]
```

CLI entrypoints:

```bash
code2skill --help
python -m code2skill --help
```

## Quick Start

Bash:

```bash
export QWEN_API_KEY=...
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest

cd /path/to/repo
code2skill scan
```

PowerShell:

```powershell
$env:QWEN_API_KEY="..."
$env:CODE2SKILL_LLM="qwen"
$env:CODE2SKILL_MODEL="qwen-plus-latest"

Set-Location D:\path\to\repo
code2skill scan
```

If you only want Phase 1 structural analysis:

```bash
code2skill scan --structure-only
```

If you already have previous state and want automatic incremental regeneration:

```bash
code2skill ci --mode auto
```

## Core Commands

Full scan and skill generation:

```bash
code2skill scan --llm qwen --model qwen-plus-latest
```

Structure-only scan:

```bash
code2skill scan --structure-only
```

Cost and impact estimation only:

```bash
code2skill estimate
```

Automatic incremental mode for CI:

```bash
code2skill ci --mode auto --base-ref origin/main
```

Adapt generated skills into Codex format:

```bash
code2skill adapt --target codex --source-dir .code2skill/skills
```

Adapt to all supported targets:

```bash
code2skill adapt --target all --source-dir .code2skill/skills
```

## How The Pipeline Works

### Phase 1: Structural Scan

Input:

- repository path

Output:

- `project-summary.md`
- `skill-blueprint.json`
- `references/architecture.md`
- `references/code-style.md`
- `references/workflows.md`
- `references/api-usage.md`
- `report.json`
- `state/analysis-state.json`

Main steps:

1. discover and filter files
2. apply coarse scoring and budget selection
3. extract Python structure with AST
4. build the internal import graph
5. refine file priority and inferred role
6. detect patterns and abstract rules
7. assemble the final `SkillBlueprint`

### Phase 2: Skill Planning

Input:

- `skill-blueprint.json`

Output:

- `skill-plan.json`

Main steps:

1. compress repository profile, directory summary, clusters, core modules, rules, and workflows
2. make one LLM call
3. decide which skills should exist
4. choose the most valuable files to read for each skill

### Phase 3: Skill Generation

Input:

- `skill-plan.json`
- selected files or extracted skeletons

Output:

- `skills/index.md`
- `skills/*.md`

Main steps:

1. gather exact file context for each planned skill
2. inline smaller files and use structural summaries for larger files
3. filter repository rules relevant to that skill
4. generate grounded skill markdown
5. sanitize and validate the final skill output

### Adapt Phase

Input:

- generated `skills/*.md`

Output:

- Cursor rules
- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.windsurfrules`

## Output Layout

Typical output:

```text
.code2skill/
  project-summary.md
  skill-blueprint.json
  skill-plan.json
  report.json
  references/
    architecture.md
    code-style.md
    workflows.md
    api-usage.md
  skills/
    index.md
    *.md
  state/
    analysis-state.json
```

## LLM Backends

Supported providers:

- `openai`
- `claude`
- `qwen`

Environment variables:

Bash:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
$env:ANTHROPIC_API_KEY="..."
$env:QWEN_API_KEY="..."
```

Common CLI defaults:

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

Notes:

- `qwen` uses the DashScope international compatible endpoint by default
- `qwen` reads `QWEN_API_KEY` and also accepts `DASHSCOPE_API_KEY`
- missing credentials fail fast rather than silently degrading

## Incremental CI

`code2skill ci --mode auto` is intended for automation scenarios.

It can:

- detect changed files from git state or an explicit diff file
- expand impact through internal reverse dependencies
- select affected skills
- regenerate only the necessary outputs
- clean up stale skill files when the planned set changes

Common reasons to fall back to a full rebuild:

- no previous state exists
- critical config changed
- too many files changed
- repository metadata changed enough that incremental confidence is low

## Why The Output Is Useful For AI Tools

The generated skill documents are meant to be consumed directly by coding assistants, not just read by humans.

They focus on:

- module boundaries
- call flows
- stable repository rules
- evidence-backed patterns
- target-specific rule packaging

That makes them more reusable than one-off prompts and easier to keep aligned with repository changes.

## Typical Use Cases

- generate Codex `AGENTS.md` from an existing Python backend repository
- produce Cursor rules from real source code instead of manually written docs
- give Claude Code a repository-specific skill set before large refactors
- keep AI-facing repository guidance updated in CI after code changes

## Limitations

- currently optimized for Python codebases
- JavaScript or TypeScript structural analysis is not a first-class target
- quality still depends on repository clarity and the chosen model
- this is an alpha release line, so output quality will continue to evolve

## License

Apache-2.0. See [LICENSE](./LICENSE).
