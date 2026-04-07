# code2skill Architecture and Product Upgrade Design

## Goal

Upgrade `code2skill` from a command-oriented repository analysis tool into a Python-first, artifact-centered product with a clearer workflow model, stronger diagnostics, and an internal architecture that separates product interfaces, workflows, domain logic, capabilities, and infrastructure.

The primary product goal is to improve the quality, predictability, and maintainability of generated Skill and rule outputs. The architectural goal is to remove the current concentration of responsibilities in orchestration-heavy modules and replace it with stable boundaries that can support future expansion without forcing a full platform rewrite now.

## Product Positioning

`code2skill` remains Python-first. It does not become a fully generic multi-language platform in this phase. Instead, it adopts a product shape that is optimized for two core usage modes:

1. local developer workflows that need fast repository analysis and high-quality AI-consumable outputs
2. CI-driven team workflows that need stable incremental updates, diagnostics, and reproducible generated artifacts

The product center remains generated Skills and downstream rule files. Internal abstractions should support future expansion, but this phase should avoid overbuilding a generic platform before product value is improved for current users.

## Current-State Problems

The existing codebase already contains the core product value, but the architecture is held back by several concentration points:

- `src/code2skill/core.py` acts as a large orchestration center across scanning, refinement, diff handling, generation control, writing, and reporting.
- `src/code2skill/skill_generator.py` mixes context loading, prompt construction, generation strategy, incremental patching, markdown parsing, and snippet extraction.
- `src/code2skill/models.py` mixes multiple domain concerns into one large model hub.
- CLI, API, CI, adaptation, and generation flows share concepts but not one consistently expressed workflow model.
- path resolution, state reuse, and repeated extractor/prioritizer construction appear in multiple places.
- current architecture is optimized around implementation flow, but less around product workflow clarity and diagnostics.

These issues make the system harder to extend, harder to test in focused layers, and harder to present as a mature product.

## Product Outcome

The upgraded product should feel like a coherent workflow rather than a bag of commands. The public user journey should map to a repository knowledge lifecycle:

1. initialize project configuration and output strategy
2. analyze the repository and produce structured understanding
3. plan the skill and artifact set
4. build generated artifacts
5. preview impact, changes, and diagnostics
6. apply or publish outputs to selected targets
7. synchronize incrementally in CI or repeated local runs

This should improve clarity for both local and automated use while preserving the existing value of full scans, incremental runs, and target adaptation.

## Core Usage Scenarios

### Scenario A: Local developer workflow

A developer points the tool at a Python repository, reviews repository analysis, generates Skills and rule files, inspects the result, and adapts outputs for a target AI tool. The upgraded product should provide clearer progress, clearer diagnostics, and clearer output expectations at every step.

### Scenario B: CI-driven team workflow

A team runs the tool inside CI with a persisted prior state. The system determines whether to perform an incremental or full rebuild, explains that decision, regenerates only impacted outputs when safe, and emits diagnostics and reports that make automation behavior understandable and auditable.

These two scenarios must share the same internal workflow model so the codebase does not fork into separate local and CI architectures.

## Architecture Overview

The upgraded system should use five layers.

### 1. Product Interface Layer

This layer handles CLI commands, Python API entrypoints, interactive output formatting, and CI-facing invocation semantics. It is responsible for input parsing, user-facing defaults, and presentation of results. It must not own repository analysis, generation logic, or file adaptation rules.

### 2. Application Workflow Layer

This layer expresses top-level use cases such as repository analysis, skill planning, artifact building, adaptation, preview, estimation, and incremental synchronization. It coordinates capabilities and produces structured results. This layer replaces the current orchestration concentration in `core.py`.

### 3. Domain Layer

This layer defines the core concepts of the product: repository profile, analysis snapshot, skill plan, artifact bundle, target output, diagnostics, impact set, and run result types. The domain layer should encode stable contracts and business language, not transport or infrastructure concerns.

### 4. Capability Layer

This layer contains the operational building blocks used by workflows. The expected groups are:

- repository discovery and filtering
- Python analysis and structure extraction
- import graph and impact calculation
- planning and prompt assembly
- skill generation and patch/update strategy
- artifact adaptation
- state loading and reuse
- pricing and report calculation

Each capability should have a clear boundary and should be testable independently.

### 5. Infrastructure Layer

This layer handles filesystem access, git operations, LLM provider calls, serialization, state storage, and report writing. It should isolate side effects from workflow and domain logic.

## Proposed Module Structure

The target structure should converge toward the following modules or package groups:

- `src/code2skill/product/`
- `src/code2skill/workflows/`
- `src/code2skill/domain/`
- `src/code2skill/capabilities/analyze/`
- `src/code2skill/capabilities/plan/`
- `src/code2skill/capabilities/generate/`
- `src/code2skill/capabilities/adapt/`
- `src/code2skill/capabilities/incremental/`
- `src/code2skill/infra/git/`
- `src/code2skill/infra/llm/`
- `src/code2skill/infra/storage/`
- `src/code2skill/infra/reporting/`

This design does not require moving every file at once. The migration should begin by introducing the new boundaries and routing new workflows through them while legacy code is gradually reduced.

## Public Product Model

The product should evolve toward a clearer workflow-driven command model. The exact command names may shift during implementation, but the product surface should express these concepts directly:

- initialization and configuration
- repository analysis
- planning and estimation
- artifact building
- preview and diagnostics
- adaptation/application to target tools
- CI and incremental synchronization

The Python API should align with the same workflow model instead of acting as a thin convenience layer over orchestration internals.

## Configuration Design

The upgraded product should define one primary configuration contract. The preferred default is a dedicated `pyproject.toml` section, such as `[tool.code2skill]`, with room for a standalone config file later if needed.

The configuration should cover:

- output directory strategy
- default targets
- ignore rules
- CI base reference
- generation depth or scope controls
- pricing or provider defaults when applicable
- automation behavior such as whether adaptation is write-through or staged

This change reduces dependency on loosely coordinated CLI flags and environment variables for core product behavior.

## Artifact Contract

Artifacts should be treated as explicit bundles rather than incidental file writes. The system should standardize categories such as:

- analysis artifacts
- planning artifacts
- generated skill artifacts
- adapted target artifacts
- diagnostics and report artifacts
- incremental state artifacts

The output layout documentation should become the human-readable expression of this code-level contract rather than the only place where the contract exists.

## Diagnostics and Preview

Diagnostics should become a first-class product feature. A run should explain:

- what was analyzed
- what changed
- which skills or artifacts are affected
- whether a full or incremental path was selected
- which assumptions remain uncertain
- what outputs will be produced or updated

This is required for both local usability and CI trustworthiness.

## Target Adapter Model

The adaptation layer should become a normalized adapter model. Each target such as Codex, Claude, Cursor, Copilot, or Windsurf should define:

- target metadata
- supported artifact types
- output mapping rules
- merge or overwrite strategy
- validation constraints

This keeps target-specific behavior out of the workflow core and makes future adapters easier to add without expanding orchestration complexity.

## Data Flow

The upgraded workflow should standardize data flow as:

`RepositoryInput -> AnalysisSnapshot -> SkillPlan -> GenerationContext -> ArtifactBundle -> TargetOutputs -> RunReport`

Each step should persist or expose a meaningful intermediate representation where appropriate. This improves debuggability, testing, incremental reuse, and CI visibility.

## Error Handling

The upgraded system should move from mostly execution-driven failure signaling to structured result and diagnostics handling. It should distinguish among:

- user input or configuration errors
- unsupported repository conditions
- git or state resolution failures
- LLM provider failures
- generation contract failures
- adaptation or write failures

CLI presentation may stay concise, but reports and machine-readable outputs should preserve detailed diagnostics.

## Testing Strategy

Testing should align with the new architecture:

- domain tests for model and rule logic
- capability tests for analysis, planning, generation, adaptation, and incremental logic
- workflow tests for analyze/build/preview/sync use cases
- integration tests for CLI, API, and CI-facing runs
- golden artifact tests for generated Skills, adapted outputs, and diagnostics bundles

The purpose is to reduce reliance on large end-to-end confidence only and make architectural changes safer.

## Migration Strategy

Migration should happen in staged slices rather than as a single rewrite.

### Phase 1: Introduce new architecture skeleton

Create the new package groups and stable workflow/domain entrypoints without removing existing behavior immediately.

### Phase 2: Migrate analysis and estimation

Move repository analysis, impact calculation, and estimation into the new workflow/capability model. Reduce `core.py` responsibility first.

### Phase 3: Migrate generation and adaptation

Split `skill_generator.py` into focused generation capabilities and introduce normalized target adapters.

### Phase 4: Redesign CLI and Python API

Rebuild public interfaces around the new workflows and diagnostics model.

### Phase 5: Consolidate CI and state reuse

Unify incremental state handling, fallback decisions, and report production under the new workflows.

### Phase 6: Product polish

Finalize preview, diagnostics, configuration ergonomics, and updated documentation.

## Constraints

- Keep this phase Python-first.
- Do not overbuild a language-agnostic platform before product value is improved.
- Prioritize better output quality, workflow clarity, and diagnosability.
- Prefer stable workflow and artifact contracts over preserving current internal shapes.
- Break external APIs only when the redesign meaningfully improves product coherence.

## Success Criteria

The upgrade is successful when:

- orchestration-heavy modules are materially decomposed into workflow and capability boundaries
- product interfaces expose a clearer repository knowledge workflow
- generated artifacts and adapted outputs remain central and higher quality
- incremental behavior is more explainable and testable
- diagnostics and preview capabilities become first-class
- the codebase becomes easier to extend without routing every new feature through one central orchestrator

## Implementation Direction

Implementation should favor a pragmatic architecture uplift:

- product-centered first
- layered internals second
- future-proofing only where it directly supports this product upgrade

This keeps the redesign ambitious enough to raise the architecture level while avoiding a premature leap into full platform abstraction.
