# Use Cases

`code2skill` is built for maintainers who want AI coding assistants to work from the same repository knowledge that humans can review in Git.

## Primary Personas

| Persona | Repository pain | Desired outcome |
|---|---|---|
| Python maintainer | AI tools miss local boundaries, style, and workflow contracts | Generated Skills describe how to modify the current codebase |
| DevEx or platform owner | Each team writes different AI rules, often by hand | One repeatable workflow standardizes assistant context across services |
| Open-source maintainer | Contributors bring different tools and private chat context | Public, committed AI instructions make project expectations auditable |
| AI tooling evaluator | A repository needs to compare Codex, Cursor, Claude Code, Copilot, and Windsurf | One Skill layer can be adapted into every supported target |

## Scenario 1: First Repository Knowledge Layer

### Trigger

A Python repository is adopting an AI coding assistant and needs a durable project entry point.

### Workflow

```bash
code2skill scan . --structure-only
code2skill estimate .
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target codex
code2skill doctor . --target codex
```

### Outputs

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- `AGENTS.md` or another target instruction file

### Success Signal

`doctor` reports `ready: true`, generated Skills are reviewable, and the target instruction file can be committed.

## Scenario 2: Pull Request And CI Refresh

### Trigger

Code changes may invalidate existing AI-facing project knowledge.

### Workflow

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
code2skill adapt . --target codex
code2skill doctor . --target codex
```

### Outputs

- refreshed Skill files when affected
- refreshed target instruction files
- `.code2skill/report.json` with execution mode, changed files, affected files, affected Skills, and written artifacts
- `.code2skill/state/analysis-state.json` for later incremental reuse

### Success Signal

The PR shows exactly which AI-facing artifacts changed and why.

## Scenario 3: One Knowledge Source For Multiple AI Tools

### Trigger

A team uses more than one AI coding assistant and wants consistent project context across tools.

### Workflow

```bash
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target all
code2skill doctor . --target all
```

### Outputs

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

### Success Signal

All supported target files are generated from the same Skill layer, and `doctor --target all` reports readiness.

## Scenario 4: Platform Or DevEx Automation

### Trigger

A platform team needs to run the same repository-knowledge workflow across multiple Python services.

### Workflow

```python
from code2skill import adapt_repository, doctor, run_ci

for repo in repositories:
    result = run_ci(repo, mode="auto", base_ref="origin/main")
    adapt_repository(repo, target="codex")
    readiness = doctor(repo, target="codex")
    if not readiness.ready:
        raise RuntimeError((repo, readiness.next_steps))
```

### Success Signal

Automation can make a binary decision from structured readiness data instead of scraping free-form command output.

## Scenario 5: Open-Source Contributor Onboarding

### Trigger

An open-source project wants new contributors and AI assistants to share the same implementation rules before a change is proposed.

### Workflow

```bash
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target codex
code2skill doctor . --target codex
```

Then link the generated target file and `.code2skill/skills/index.md` from contributor documentation.

### Success Signal

Contributors can inspect the same AI-facing project guidance that maintainers review and commit.

## Selection Guide

| Scenario | Start with | Then run | Validate with |
|---|---|---|---|
| First adoption | `scan --structure-only` | `estimate`, `scan`, `adapt` | `doctor --target <tool>` |
| PR refresh | `ci --mode auto` | `adapt` | `doctor` |
| Multi-tool publishing | `scan` | `adapt --target all` | `doctor --target all` |
| Platform automation | Python API | `run_ci`, `adapt_repository` | `doctor` |
| Open-source onboarding | `scan` | docs link plus `adapt` | `doctor` |
