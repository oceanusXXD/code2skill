# code2skill Positioning as a CI-Native Repo-Knowledge Compiler

## Goal

Sharpen the product direction of `code2skill` so future work converges on a clear lane: a CLI-first, Python-first compiler that turns repository evidence into durable AI-consumable artifacts for local development and CI/CD workflows.

This document does not replace `docs/superpowers/specs/2026-04-07-code2skill-architecture-product-upgrade-design.md`. It narrows the product boundary that the architecture work should serve.

## Decision Summary

`code2skill` should position itself as a **CI-native repo-knowledge compiler and adapter**, not as a generic agent platform and not as a knowledge-graph product.

The core user promise is:

1. read a real Python repository
2. compile repository evidence into a durable artifact bundle
3. keep that bundle incrementally fresh in CI
4. adapt the same knowledge base into multiple assistant-specific instruction targets

In this model, the main product output is not chat behavior, runtime orchestration, or an interactive graph. The main output is a reviewed, commit-friendly artifact set written to disk.

## Why This Position Fits the Existing Product

The current public surface already points in this direction.

- `README.md` describes one workflow-oriented chain: `scan`, `estimate`, `ci`, and `adapt`
- `docs/cli.md` explicitly says those commands are one repository-knowledge workflow rather than unrelated utilities
- `docs/ci.md` makes `ci --mode auto` the automation-oriented entrypoint
- the generated outputs already emphasize durable files, incremental state reuse, and target-specific instruction artifacts

That means the strongest direction is not to invent a new identity. It is to tighten the identity the repository already has.

## Direct Answer to the Graphify Question

`graphify` does **not** make this work redundant.

It becomes a problem only if `code2skill` tries to compete on `graphify`'s axis.

`graphify` is best understood as a **multimodal knowledge-graph builder plus assistant-side skill and hook layer**. Its center of gravity is graph creation, graph querying, assistant installation, and graph-first navigation across code, docs, PDFs, and images.

`code2skill` is strongest when it focuses on a different center of gravity: **repository evidence -> artifact bundle -> CI refresh -> multi-target rule emission**.

Those are adjacent spaces, not the same product.

## Comparison: code2skill vs graphify

| Dimension | code2skill | graphify |
|---|---|---|
| Primary user moment | maintainer workflow, repository setup, CI refresh | assistant-side exploration and graph-guided understanding |
| Primary input | real Python repository | mixed corpus: code, docs, PDFs, images, notes |
| Core artifact | Skills, blueprints, plans, reports, adapted rule files | `graph.json`, `graph.html`, `GRAPH_REPORT.md`, wiki/Obsidian/Neo4j exports |
| Product center | compile and maintain AI-facing repository knowledge | build and query a graph of relationships |
| Automation story | incremental CI and durable artifact refresh | local graph refresh, query, watch, and assistant hooks |
| Defensible promise | one evidence base, many assistant targets, CI-safe refresh | structure discovery, graph traversal, multimodal context compression |

## What code2skill Should Explicitly Be

### 1. A compiler, not a chat runtime

The product should take repository inputs and produce structured outputs with predictable phases, machine-readable reports, and stable file contracts.

The right mental model is closer to:

`repo -> analysis snapshot -> skill plan -> generated skills -> adapted targets -> run report`

than to:

`assistant plugin -> runtime memory -> interactive exploration surface`

### 2. CI-native, not assistant-runtime-native

The highest-leverage use case is not “help an assistant browse this repo right now.”

It is:

- make repository knowledge maintainable as code changes
- regenerate only what is affected
- keep AI-facing instruction files aligned with the current repository state
- make the refresh path auditable in pull requests and CI logs

### 3. Python-first in this phase

The current analyzer value comes from being opinionated and grounded in real Python repository structure. The product should deepen that advantage before expanding into a generic multi-language ingestion platform.

### 4. One knowledge source, many instruction targets

The strongest downstream story is that one repository knowledge base can emit consistent outputs for:

- `AGENTS.md`
- `CLAUDE.md`
- Cursor rules
- GitHub Copilot instructions
- Windsurf rules

That is a clear operational value proposition for teams standardizing AI collaboration across tools.

## What code2skill Should Not Become

The following directions should be de-emphasized or explicitly cut in this phase:

### 1. General knowledge-graph platform

Do not compete on graph visualization, graph traversal UX, graph query commands, graph databases, or graph export ecosystems.

### 2. Multimodal ingestion platform

Do not expand into PDFs, screenshots, whiteboards, or general document corpus ingestion as a primary product story.

### 3. Always-on assistant hook installer

Do not center the product around assistant-specific runtime hooks, slash-command installation flows, or “always read this first” hook behavior.

### 4. Generic agent platform

Do not reposition the repo as a general-purpose agent operating system, agent marketplace, or assistant runtime layer.

Those paths would blur the product, duplicate adjacent tools, and weaken the current CI/compiler identity.

## Recommended Product Surface

The existing public command model is already close to the right shape.

### `scan`

Full local compile of repository knowledge into the artifact bundle.

### `estimate`

Dry-run preview for cost, scope, impact, and likely output changes.

### `ci`

Automation-first compile path that selects full or incremental execution and explains why.

### `adapt`

Artifact publication layer that maps generated repository knowledge into target-specific instruction files.

The command model should keep feeling like one workflow with four phases, not four mini-products.

## Recommended Artifact Model

The primary artifact bundle should stay explicit and file-based.

At minimum, the product should keep treating these as first-class outputs:

- analysis artifacts
- planning artifacts
- generated Skill artifacts
- adapted target artifacts
- diagnostics and reports
- incremental state artifacts

The artifact bundle is the product boundary. CI should be able to reason about it, review it, cache it, diff it, and publish from it.

## Recommended Architecture Implications

The architecture-upgrade direction from `2026-04-07` still holds, but this positioning sharpens what those layers are for.

### Product interface layer

Should present one compiler-like workflow across CLI, Python API, and CI invocation.

### Workflow layer

Should coordinate explicit phases such as analyze, plan, generate, adapt, and report.

### Domain layer

Should define stable contracts for the artifact bundle and run summaries, not assistant runtime behavior.

### Capability layer

Should focus on repository analysis, planning, generation, adaptation, state reuse, and diagnostics.

### Infrastructure layer

Should isolate filesystem, git, serialization, and LLM-provider concerns without becoming the product center.

In short: the architecture should optimize for **trustworthy compilation and refresh of repository knowledge artifacts**, not for interactive graph exploration.

## Recommended Near-Term Priorities

### Priority 1: Tighten product copy around the compiler lane

Every public description should reinforce that `code2skill` is for compiling repository knowledge into durable AI-facing artifacts and keeping them fresh in CI.

### Priority 2: Make diagnostics and incremental decisions more legible

The strongest differentiator is trustworthy CI behavior. Users should understand:

- why a run was full or incremental
- what changed
- which artifacts were affected
- what was written
- what still needs confirmation

### Priority 3: Treat the artifact bundle as a stable contract

The output layout should feel like an intentional product interface, not just a side effect of command execution.

### Priority 4: Strengthen target adapters

The more reliable and consistent the downstream adapters are, the stronger the “one evidence base, many assistant targets” story becomes.

### Priority 5: Improve packaging and smoke-tested install paths

The compiler story becomes more credible when the package can be installed, invoked, and embedded in CI without local-environment ambiguity.

## Non-Goals for This Phase

- interactive graph explorer
- graph query language or path traversal surface
- wiki/obsidian/neo4j export ecosystem
- multimodal document understanding productization
- assistant marketplace or plugin platform strategy
- generalized non-Python repository support as the main positioning change

## Success Criteria

This positioning is working when:

- users can explain `code2skill` in one sentence as a CI-native repo-knowledge compiler
- the command model feels like one end-to-end workflow
- generated artifacts are reviewed and reused as durable assets
- CI runs can incrementally refresh those artifacts with clear diagnostics
- adapter outputs become a trusted bridge from one repository knowledge source to many AI tools
- future work is evaluated against the question: “does this strengthen the compiler-and-adapter lane?”

## Relationship to Existing Architecture Work

The existing architecture-upgrade design should remain active.

This document changes the frame around it:

- the purpose of decomposition is not generic platformization
- the purpose is to make the compiler workflow clearer, more testable, and more trustworthy in CI
- feature selection should prefer improvements to artifact quality, diagnostics, incremental behavior, and adapter reliability

## Final Recommendation

The winning move is not to chase graphify.

The winning move is to become the best tool for **compiling repository evidence into durable, incrementally maintained, assistant-specific knowledge artifacts for Python repositories**.

That is narrower than a generic agent platform, but stronger, clearer, and more defensible.
