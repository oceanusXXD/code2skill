# Output Layout

By default, `code2skill` writes artifacts under `.code2skill/` inside the target repository.

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

## Artifact Roles

- `project-summary.md`: human-readable project overview
- `skill-blueprint.json`: structural analysis output from Phase 1
- `skill-plan.json`: LLM-planned Skill inventory
- `skills/index.md` and `skills/*.md`: grounded AI-consumable Skill documents
- `report.json`: execution metrics, cost estimates, and impact summaries
- `state/analysis-state.json`: incremental execution cache

## Adapted Outputs

The `adapt` command writes target-specific files under the repository root:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

These files are not written into `.code2skill/`; they are written where the target tool expects to read them.
