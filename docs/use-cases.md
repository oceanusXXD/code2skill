# Use Cases

`code2skill` is for Python repositories that want coding assistants to use project rules from files in the repo, not from one-off prompts or untracked notes.

## Maintainer Profiles

| Maintainer | Problem | Useful output |
|---|---|---|
| Python package or service maintainer | Assistants miss local module boundaries and extension points | Skill files generated from source and config evidence |
| DevEx or platform owner | Several teams need the same assistant setup process | One CLI/API workflow that can run across repositories |
| Open-source maintainer | Contributors use different assistants and bring inconsistent project context | Public instruction files that can be reviewed in pull requests |
| Tooling evaluator | The same repo needs to work with Codex, Cursor, Claude Code, Copilot, and Windsurf | One Skill layer adapted into multiple target files |

## 1. First Assistant Setup

Use this when a repository is starting to use Codex, Cursor, Claude Code, GitHub Copilot, or Windsurf.

```bash
code2skill scan . --structure-only
code2skill estimate .
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target codex
code2skill doctor . --target codex
```

Review these files first:

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- `AGENTS.md` or another target instruction file

The run is ready when `doctor` reports `ready: true` and the target file matches the assistant your team uses.

## 2. Pull Request Refresh

Use this when code changes may make previous instruction files stale.

```bash
code2skill ci . --mode auto --base-ref origin/main --head-ref HEAD
code2skill adapt . --target codex
code2skill doctor . --target codex
```

Review `.code2skill/report.json` to see:

- whether the run used `full` or `incremental`
- which files changed
- which files were affected
- which Skills were regenerated
- which artifacts were written

This makes generated instruction changes reviewable in the same PR as the code change.

## 3. One Skill Layer For Several Tools

Use this when a team uses more than one coding assistant.

```bash
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target all
code2skill doctor . --target all
```

This writes:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

The source remains `.code2skill/skills/`; target files are only adapters.

## 4. Platform Automation

Use this when a DevEx or platform team wants the same workflow across several Python services.

```python
from code2skill import adapt_repository, doctor, run_ci

for repo in repositories:
    result = run_ci(repo, mode="auto", base_ref="origin/main")
    adapt_repository(repo, target="codex")
    readiness = doctor(repo, target="codex")
    if not readiness.ready:
        raise RuntimeError((repo, readiness.next_steps))
```

The Python API returns structured results, so automation can act on `ready`, `score`, `checks`, and `next_steps` without parsing CLI output.

## 5. Open-Source Contributor Onboarding

Use this when new contributors need project-specific implementation rules before opening a PR.

```bash
code2skill scan . --llm qwen --model qwen-plus-latest
code2skill adapt . --target codex
code2skill doctor . --target codex
```

Then link the generated target file and `.code2skill/skills/index.md` from contributor documentation.

This gives contributors the same project instructions that maintainers can review and update.

## Selection Guide

| Goal | Start with | Then run | Check with |
|---|---|---|---|
| First setup | `scan --structure-only` | `estimate`, `scan`, `adapt` | `doctor --target <tool>` |
| PR refresh | `ci --mode auto` | `adapt` | `doctor` |
| Multi-tool output | `scan` | `adapt --target all` | `doctor --target all` |
| Platform automation | Python API | `run_ci`, `adapt_repository` | `doctor` |
| Contributor onboarding | `scan` | docs link plus `adapt` | `doctor` |
