# code2skill

[![PyPI version](https://img.shields.io/pypi/v/code2skill)](https://pypi.org/project/code2skill/)
[![Python versions](https://img.shields.io/pypi/pyversions/code2skill)](https://pypi.org/project/code2skill/)
[![License](https://img.shields.io/pypi/l/code2skill)](https://github.com/oceanusXXD/code2skill/blob/main/LICENSE)

English README. For Chinese documentation, see [README.zh-CN.md](./README.zh-CN.md).

`code2skill` is a CLI for real Python repositories. It turns source code into structured project knowledge, Skill documents that AI coding assistants can consume directly, and rule files adapted for tools such as Cursor, Claude Code, Codex, GitHub Copilot, and Windsurf.

It provides a full chain from repository scanning and structural analysis to Skill generation and rule adaptation, with incremental updates based on diffs and historical state. The generated outputs are written to disk so they can be reviewed, committed, reused, and continuously integrated into local development and CI workflows.

## Why Skills Matter

In traditional software development, the `README` is the standard entry document for a project. It is written for human developers and usually covers project introduction, installation, usage, development setup, and examples.

In the AI IDE era, AI tools also read READMEs, documentation, and source code to understand a project. At that point, a repository needs a form of knowledge that is better suited for direct AI consumption. READMEs still matter, but they often mix user guidance, developer guidance, background context, historical notes, sample snippets, and presentation-oriented material. That structure is natural for human readers. For AI systems, however, project conventions, important patterns, and execution boundaries are more useful when they are presented in a more unified and structured form.

A Skill is that AI-oriented project document form.

In practice, a Skill can be treated as an engineering-grade README for AI. It organizes implementation-relevant knowledge into stable, clear, and maintainable documents so that AI can read consistent project context across different tools, sessions, and stages of work.

Skills let a repository express information such as:

- the core structure of the project and the responsibility boundaries of modules
- the important roles, call relationships, and behavioral constraints in the code
- existing patterns, conventions, and preferred extension paths
- the implementation path and modification style expected for specific tasks
- a unified source for downstream tool-specific rule files

Once that information is materialized as Skills, it can be consumed directly by AI IDEs, agents, and automation workflows. Developers can also iterate on collaboration practices around those Skills and turn "how this repository should be worked on" into an auditable, commit-friendly, evolvable engineering asset.

## What code2skill Provides

`code2skill` builds project knowledge from real Python repositories and generates a set of outputs that can be written to disk, tracked over time, and integrated into normal engineering workflows.

It covers the full chain from repository scanning, structural analysis, Skill planning, and document generation to tool-specific rule adaptation. It also supports incremental regeneration so Skills can stay aligned as the repository evolves.

For one-off local analysis, `code2skill` can scan an entire repository and generate the full result set.
For ongoing development workflows, it can combine historical state and code diffs to rebuild only the affected Skills, reducing repeated generation cost and making CI-based updates practical.

## What It Guarantees

- Python-first analysis with `ast`, import graph analysis, file-role inference, and pattern detection
- Evidence-first prompts: built-in prompts are in English, ban emoji, and avoid unsupported claims
- Durable outputs: repository knowledge is written to files instead of chat history
- Measurable runs: every `scan`, `estimate`, or `ci` execution writes a `report.json`
- Incremental operation: CI can reuse prior state and only regenerate impacted skills

## Command Model

| Command | Uses LLM | Writes outputs | Primary purpose |
|---|---|---|---|
| `scan` | Yes, unless `--structure-only` | Yes | Full local generation |
| `estimate` | No | `report.json` only | Cost and impact preview |
| `ci` | Yes, unless `--structure-only` | Yes | Automated full or incremental execution |
| `adapt` | No | Yes | Copy or merge generated skills into tool-specific targets |

## What It Generates

From one Python repository, `code2skill` can produce:

- `project-summary.md` for a human-readable repository overview
- `skill-blueprint.json` for the Phase 1 structural blueprint
- `skill-plan.json` for the LLM-planned skill set
- `skills/index.md` and `skills/*.md` for grounded AI-consumable skill documents
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, `.github/copilot-instructions.md`, and `.windsurfrules` via `adapt`
- `report.json` for execution metrics, token estimates, and impact summaries
- `state/analysis-state.json` for incremental CI reuse

## The Role Of Skills In A Repository

Skills are the standardized AI-facing expression layer of repository knowledge.

They connect repository structure, implementation details, team conventions, and tool rules so an AI system can enter the project with one consistent context source instead of repeatedly reconstructing it from README files, scattered docs, previous implementations, and chat history.

In engineering practice, that creates direct value:

- it gives AI IDEs a unified, stable, low-noise project entry point
- it lets developers turn recurring implementation patterns into reusable guidance
- it helps future changes follow the same boundaries and extension paths already present in the repository
- it gives rule-file generation a single consistent source of truth
- it keeps repository knowledge incrementally maintained as code changes, instead of periodically rewritten by hand

That is why `code2skill` is really about organizing, transmitting, and updating repository knowledge for AI collaboration.

## Incremental Updates And Ongoing Maintenance

Repository knowledge needs to evolve with the code.

`code2skill` supports incremental regeneration based on historical analysis state and the current change scope. After code changes, it can identify the affected areas, rebuild the relevant Skills, and preserve outputs that are still valid. That makes it suitable for local development loops, pull request checks, and continuous CI automation.

This workflow has several practical benefits:

- it reduces the cost of repeated full regeneration on larger repositories
- it keeps Skills synchronized with the current code state
- it moves project-knowledge maintenance into the normal development process
- it makes generated outputs reviewable, comparable, and commit-friendly

Skills therefore become a long-lived engineering asset rather than a temporary prompt artifact.

## Adapting To Multiple AI Tools

Different AI coding tools use different rule file formats, but they all need high-quality project context.

`code2skill` first generates a unified Skill-centered knowledge layer, then uses `adapt` to copy or merge that layer into target-specific formats, including:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

That approach lets a repository maintain one core knowledge representation and distribute consistent context and constraints to multiple AI tools without duplicating maintenance effort.

## When To Use code2skill

`code2skill` is a good fit for:

- Python repositories that want a stable project context for AI IDEs
- teams that want repository knowledge committed as files instead of kept in chat threads
- engineering workflows that need CI-based updates for AI rule files
- projects that want diff-aware control over regeneration scope and cost
- repositories that need one knowledge source adapted to multiple AI coding tools

## Pipeline

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

1. Discover and filter files.
2. Apply coarse scoring and budget selection.
3. Extract Python structure with `ast`.
4. Build the internal import graph.
5. Refine file priority and inferred roles.
6. Detect patterns and abstract rules.
7. Assemble the final `SkillBlueprint`.

### Phase 2: Skill Planning

Input:

- `skill-blueprint.json`

Output:

- `skill-plan.json`

Main steps:

1. Compress the project profile, directories, clusters, modules, rules, and workflows.
2. Make one LLM call.
3. Decide which skills should exist.
4. Pick the most representative files for each skill.

### Phase 3: Skill Generation

Input:

- `skill-plan.json`
- selected source files or extracted structural summaries

Output:

- `skills/index.md`
- `skills/*.md`

Main steps:

1. Gather the exact context for each skill.
2. Inline small files and structural summaries for large files.
3. Filter repository rules relevant to that skill.
4. Generate one grounded Skill document per skill.
5. Sanitize the final Markdown and keep uncertainty explicit as `[Needs confirmation]`.

### Adapt Phase

Input:

- generated `skills/*.md`

Output:

- Cursor rules
- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.windsurfrules`

## Prompt Policy

The built-in prompts are intentionally opinionated:

- Planner output must be in English, use kebab-case names, stay evidence-based, and avoid emoji.
- Skill generation must stay grounded in provided files and rules only.
- Generated skills must use a fixed five-section structure.
- When evidence is incomplete, the output must say `[Needs confirmation]` instead of inventing certainty.

This keeps the generated documents more stable for downstream AI tools and easier to review in Git.

## Measured On This Repository

The numbers below were collected on `2026-03-17` from this repository at commit `3714510`, on Windows with Python `3.10.6`, using the current default limits and heuristic pricing.

| Metric | Result |
|---|---|
| `scan --structure-only` wall-clock time | `1.33s` |
| `estimate` wall-clock time | `1.30s` |
| Candidate files / selected files | `51 / 31` |
| Bytes read in full structure-only scan | `314,585` |
| Retained context size | `119,984 chars` |
| Heuristic recommended skills | `2` |
| First-generation estimate | `6,138` input tokens, `1,610` output tokens |
| Per-skill estimate | `project-overview: 450 in / 850 out`, `backend-architecture: 5,688 in / 760 out` |
| Second `ci --mode auto` run on reused state | `incremental` |
| Incremental no-diff bytes read | `20,939` |
| Incremental no-diff affected skills | `0` |

Important notes:

- The default pricing mode is heuristic. It estimates chars and tokens, but leaves USD at `0.0` until you provide real model pricing.
- `estimate` does not call an LLM. It predicts likely first-generation, incremental rewrite, and incremental patch costs from the scanned repository structure.
- `ci --mode auto` really does switch modes based on repository state. On this repo, the first run was `full` because no prior state existed; the second run was `incremental`.

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

Structure-only scan:

```bash
code2skill scan --structure-only
```

Cost and impact preview:

```bash
code2skill estimate
```

Automatic incremental mode:

```bash
code2skill ci --mode auto --base-ref origin/main
```

Adapt generated skills into Codex format:

```bash
code2skill adapt --target codex --source-dir .code2skill/skills
```

## LLM Backends

Supported providers:

- `openai`
- `claude`
- `qwen`

Environment variables:

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export QWEN_API_KEY=...
```

Common defaults:

```bash
export CODE2SKILL_LLM=qwen
export CODE2SKILL_MODEL=qwen-plus-latest
export CODE2SKILL_OUTPUT_DIR=.code2skill
export CODE2SKILL_MAX_SKILLS=6
export CODE2SKILL_BASE_REF=origin/main
```

Notes:

- `qwen` uses the DashScope international compatible endpoint by default.
- `qwen` reads `QWEN_API_KEY` and also accepts `DASHSCOPE_API_KEY`.
- Missing credentials fail fast instead of silently degrading.

## Cost Estimation And `report.json`

`estimate` is intended for preflight checks and CI planning. It does not write the full artifact set. It only writes `report.json`.

The report includes:

- selected file counts and retained character volume
- full-scan bytes read
- changed files, affected files, and affected skills
- `first_generation_cost`
- `incremental_rewrite_cost`
- `incremental_patch_cost`
- pricing metadata and execution notes

If you want real USD output instead of token-only estimates, pass a pricing file:

```bash
code2skill estimate --pricing-file pricing.json
```

`pricing.json` must contain:

```json
{
  "model": "qwen-plus-latest",
  "input_per_1m": 0.0,
  "output_per_1m": 0.0,
  "chars_per_token": 4.0
}
```

Replace `0.0` with your current provider prices before using it for budgeting.

## CI/CD Integration

`code2skill ci --mode auto` is the main automation entrypoint.

It can:

- detect changed files from git history or an explicit diff file
- expand impact through reverse dependencies
- map changed files to affected skills
- regenerate only the required Skill outputs
- prune stale skill files when the skill set changes

Common reasons to fall back to a full rebuild:

- no previous `.code2skill/state/analysis-state.json`
- no previous `skill-plan.json`
- important config changed, such as `pyproject.toml`
- too many changed files for a safe incremental run

Recommended GitHub Actions workflow:

```yaml
name: code2skill

on:
  pull_request:
  push:
    branches:
      - main

jobs:
  build-skills:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Restore code2skill cache
        uses: actions/cache@v4
        with:
          path: .code2skill
          key: code2skill-${{ runner.os }}-${{ github.ref_name }}-${{ github.sha }}
          restore-keys: |
            code2skill-${{ runner.os }}-${{ github.ref_name }}-
            code2skill-${{ runner.os }}-

      - name: Install
        run: pip install code2skill

      - name: Run code2skill
        env:
          QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
          CODE2SKILL_LLM: qwen
          CODE2SKILL_MODEL: qwen-plus-latest
        run: |
          code2skill ci \
            --mode auto \
            --base-ref origin/${{ github.base_ref || 'main' }} \
            --head-ref HEAD

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: code2skill-output
          path: .code2skill
```

Notes:

- `fetch-depth: 0` matters, otherwise the base ref may not exist locally.
- Caching `.code2skill` is what enables fast incremental reuse.
- The first CI run on a branch usually behaves like a full build because there is no prior state.
- If you want a no-LLM CI sanity check, use `code2skill ci --mode auto --structure-only`.

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

## Typical Use Cases

- generate Codex `AGENTS.md` from an existing Python backend repository
- generate Cursor rules from real source code instead of manually maintained notes
- give Claude Code a repository-specific skill set before a large refactor
- keep AI-facing repository guidance current in CI after changes land

## Limitations

- optimized for Python repositories
- non-Python code is not a first-class analysis target
- output quality still depends on repository clarity and the chosen model
- the package is still in the `0.1.x` stage and will continue to evolve

## License

Apache-2.0. See [LICENSE](./LICENSE).
