# Output Layout

By default, `code2skill` writes workflow artifacts under `.code2skill/` inside the target repository.

This bundle separates generated Skill files from intermediate artifacts used for diagnostics, cost reporting, and incremental CI refresh.

```text
.code2skill/
  adoption-guide.md
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

### Final Product Artifacts

- `skills/index.md`: the generated Skill inventory.
- `skills/*.md`: Skill documents generated from repository evidence.
- target files written by `adapt`, such as `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/*`, `.github/copilot-instructions.md`, and `.windsurfrules`.

### Review And Diagnostic Artifacts

- `adoption-guide.md`: repository-specific adoption checklist and recommended next workflow.
- `project-summary.md`: human-readable repository overview.
- `skill-blueprint.json`: structural analysis output from Phase 1.
- `skill-plan.json`: planned Skill inventory.
- `references/*.md`: supporting architecture, style, workflow, and API references.
- `report.json`: execution metrics, mode decisions, cost estimates, affected files, affected Skills, and artifact lists.
- `state/analysis-state.json`: incremental execution cache.

## Artifacts By Command

| Command | Writes `.code2skill/` | Writes Skills | Writes state | Writes target files | Typical use |
|---|---:|---:|---:|---:|---|
| `scan --structure-only` | Yes | No | Yes | No | No-LLM structural smoke check |
| `scan` | Yes | Yes | Yes | No | Full local generation |
| `estimate` | `report.json` only | No | No | No | Cost and impact preview |
| `ci --structure-only` | Yes | No | Yes | No | No-LLM CI sanity check |
| `ci` | Yes | Yes, when full or affected | Yes | No | Automated refresh |
| `adapt` | No | No | No | Yes | Publish generated Skills to target tool files |
| `doctor` | No | No | No | No | Validate readiness |

## What To Commit

For a team adopting `code2skill`, usually commit:

- `.code2skill/adoption-guide.md`
- `.code2skill/skills/index.md`
- `.code2skill/skills/*.md`
- adapted target files used by the team, such as `AGENTS.md`

Depending on your review policy, you may also commit:

- `.code2skill/project-summary.md`
- `.code2skill/references/*.md`
- `.code2skill/report.json`
- `.code2skill/skill-plan.json`

Treat `.code2skill/state/analysis-state.json` as a cache. Commit it only if you want deterministic incremental reuse from a shared baseline; otherwise cache it in CI.

## Adapted Outputs

`adapt` writes target-specific files under the repository root, not inside `.code2skill/`.

| Target | Output | Mode |
|---|---|---|
| `codex` | `AGENTS.md` | managed block merge |
| `claude` | `CLAUDE.md` | managed block merge |
| `cursor` | `.cursor/rules/*.md` and `.cursor/rules/.code2skill-manifest.json` | manifest-tracked file copy |
| `copilot` | `.github/copilot-instructions.md` | managed block merge |
| `windsurf` | `.windsurfrules` | managed block merge |
| `all` | all of the above | mixed |

Merge targets preserve hand-written content outside the generated block:

```text
<!-- code2skill:start -->
generated Skill content
<!-- code2skill:end -->
```

Copy targets use `.code2skill-manifest.json` to track files written by `code2skill`. Later `adapt` runs update current generated Skills and remove stale manifest-tracked Markdown files without deleting unmanaged team rules.

## Readiness Validation

Run:

```bash
code2skill doctor . --target codex
```

`doctor` verifies that:

- bundle files are present
- `report.json` is valid and referenced artifacts exist
- `skill-plan.json` maps to generated Skill files
- `skills/index.md` links resolve
- state belongs to the same repository root
- the requested adapted target file exists and contains the managed block or copied Skills
