# Skill-Final Artifact Model Design

## Goal

Align `code2skill`'s product surface with one clear rule: the final product is Skill output.
Everything else inside `.code2skill/` remains important, but it is treated as an intermediate artifact that supports generation, review, reporting, and incremental CI refresh.

## Decision

`code2skill` should separate artifact roles in both code and docs:

- **final products**: `skills/index.md`, `skills/*.md`, and the target-facing instruction files produced by `adapt`
- **intermediate artifacts**: `project-summary.md`, `skill-blueprint.json`, `skill-plan.json`, `references/*.md`, `report.json`, and `state/analysis-state.json`

## Why This Is The Right Shape

The repository already behaves like a compiler pipeline:

1. analyze repository structure
2. plan a Skill set
3. generate Skill documents
4. adapt them into downstream tool formats

In that pipeline, blueprint, plan, report, and state are not independent products. They are support artifacts for producing and maintaining Skills.

Making that boundary explicit improves product clarity, report clarity, and CLI clarity.

## Code-Level Changes

The implementation should make this role split explicit in four places:

1. `ArtifactLayout` partitions bundle paths into final Skill products versus intermediate artifacts.
2. `ExecutionReport` exposes `final_product_files` and `intermediate_artifact_files`.
3. `CommandRunSummary` and CLI rendering surface final Skill products first.
4. `adapt` treats its written target files as final published Skill outputs.

## Non-Goals

- changing the underlying `scan` / `estimate` / `ci` / `adapt` pipeline shape
- introducing graph-style outputs or graph terminology
- removing intermediate artifacts from the bundle
- collapsing planning, reporting, or state into the Skill documents themselves

## Success Criteria

This design is successful when:

- bundle classification distinguishes Skill products from intermediate artifacts
- `report.json` exposes that distinction explicitly
- CLI summaries highlight final Skill products first
- docs consistently describe Skills as the final product layer
