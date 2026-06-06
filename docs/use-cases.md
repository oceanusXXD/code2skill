# Use Cases

`code2skill` is designed around three practical adoption scenarios for Python repositories.

## 1. First Repository Knowledge Layer

### Problem

AI coding assistants enter a repository with incomplete context. They read README files, scattered docs, previous code, and chat history, but those sources are not structured as stable implementation guidance.

### Workflow

```bash
code2skill scan . --structure-only
code2skill estimate .
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target codex
code2skill doctor . --target codex
```

### Output

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- `AGENTS.md` or another target instruction file

### Business Value

The team gets a reviewable AI-facing project entry point that can be committed and maintained like normal repository documentation.

## 2. Pull Request And CI Refresh

### Problem

AI-facing project knowledge becomes stale when code changes. Manually updating tool-specific rules is easy to skip, and full regeneration on every PR can be wasteful.

### Workflow

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
code2skill adapt . --target codex
code2skill doctor . --target codex
```

### Output

- refreshed Skill files when affected
- refreshed target instruction files
- `.code2skill/report.json` showing mode, changed files, affected files, affected Skills, and written artifacts
- `.code2skill/state/analysis-state.json` for later incremental reuse

### Business Value

Teams can make AI knowledge maintenance part of the normal PR loop, with clear evidence for what changed and why.

## 3. One Knowledge Source For Multiple AI Tools

### Problem

Codex, Claude Code, Cursor, GitHub Copilot, and Windsurf all expect different instruction-file locations or formats. Maintaining each by hand creates drift.

### Workflow

```bash
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target all
code2skill doctor . --target all
```

### Output

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

### Business Value

The repository owns one generated Skill layer and publishes consistent context to every supported assistant.

## 4. Platform Or DevEx Automation

### Problem

Platform teams may need to run the same repository-knowledge workflow across multiple Python services without shelling out manually.

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

### Business Value

The same workflow can be embedded into internal automation while preserving the same artifact layout and readiness checks as the CLI.

## Selection Guide

| Scenario | Start with | Then run | Validate with |
|---|---|---|---|
| First adoption | `scan --structure-only` | `estimate`, `scan`, `adapt` | `doctor --target <tool>` |
| PR refresh | `ci --mode auto` | `adapt` | `doctor` |
| Multi-tool publishing | `scan` | `adapt --target all` | `doctor --target all` |
| Platform automation | Python API | `run_ci`, `adapt_repository` | `doctor` |
