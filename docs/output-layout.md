# Output Layout

By default, `code2skill` writes artifacts under `.code2skill/` inside the target repository.

This directory is the default artifact bundle root for the repository workflow. It groups the structural analysis outputs, planning outputs, generated Skills, diagnostics, and incremental state under one predictable location.

Within this bundle, `code2skill` treats generated Skills as the final product layer. The other files remain important, but they are intermediate artifacts that support generation, review, reporting, and incremental CI refresh.

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

### Final product artifacts

- `skills/index.md` and `skills/*.md`: grounded AI-consumable Skill documents

### Intermediate artifacts

- `project-summary.md`: human-readable project overview
- `skill-blueprint.json`: structural analysis output from Phase 1
- `skill-plan.json`: LLM-planned Skill inventory
- `report.json`: execution metrics, cost estimates, and impact summaries
- `references/*.md`: supporting architectural and workflow references
- `state/analysis-state.json`: incremental execution cache

When `write_state` is enabled, both `report.json` accounting and `ScanExecution.output_files` include `state/analysis-state.json` in this intermediate layer.

In product terms, `.code2skill/` is the workspace-local artifact bundle. The final repository-local product is the generated Skill set, while `adapt` publishes that Skill layer into the repository locations where each AI tool expects to read it.

## Adapted Outputs

The `adapt` command writes target-specific files under the repository root:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules/*`
- `.github/copilot-instructions.md`
- `.windsurfrules`

These files are not written into `.code2skill/`; they are written where the target tool expects to read them.
