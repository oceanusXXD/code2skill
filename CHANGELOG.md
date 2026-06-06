# Changelog

This file tracks repository-level release history for `code2skill`.
Detailed notes for each tagged release live under [`docs/releases/`](./docs/releases/).

## Unreleased

- Added `doctor` readiness checks for generated bundles, Skill plans, state snapshots, and adapted target files.
- Added repository-specific `adoption-guide.md` output and updated README/docs around first adoption, CI refresh, and multi-tool publishing workflows.
- Changed merge-style adapters to preserve hand-written content through a managed code2skill block.
- Added Cursor copy-target manifest cleanup so stale generated rules are removed while unmanaged team rules are preserved.
- Added OpenAI-compatible Responses endpoint configuration through `CODE2SKILL_OPENAI_BASE_URL`.
- Improved Skill planning and writing prompts to avoid documentation/packaging-only pseudo-skills and produce more maintainer-oriented guidance.
- Improved PyPI-facing README content, package metadata, and sdist documentation inclusion.
- Added explicit user personas and business scenarios to README/use-case documentation.
- Hardened `adapt` to reject incomplete generated Skill directories before writing target files.
- Hardened `doctor --target cursor` to require the copy manifest used for stale generated-rule cleanup.
- Hardened CLI environment variable parsing to report invalid values instead of silently falling back to defaults.
- Restricted sdist docs inclusion to public docs and release notes, excluding internal planning docs.
- Fixed cost-estimate assumption text that rendered as mojibake in CLI/report output.
- Fixed LLM invalid-JSON responses to produce a clear runtime error.
- Fixed incremental generation to replan when affected Skills are missing from the existing plan.

## v0.1.7

- Release notes: [docs/releases/v0.1.7.md](./docs/releases/v0.1.7.md)

## v0.1.6

- Release notes: [docs/releases/v0.1.6.md](./docs/releases/v0.1.6.md)

## v0.1.5

- Release notes: [docs/releases/v0.1.5.md](./docs/releases/v0.1.5.md)

## v0.1.4

- Added checked-in GitHub Actions workflows for CI and tagged releases.
- Added dedicated CLI, Python API, output layout, and release guide documents.
- Added package typing metadata via `py.typed`.
- Split package extras into `test`, `release`, and `dev`.
- Release notes: [docs/releases/v0.1.4.md](./docs/releases/v0.1.4.md)

## v0.1.3

- Release notes: [docs/releases/v0.1.3.md](./docs/releases/v0.1.3.md)

## v0.1.2

- Release notes: [docs/releases/v0.1.2.md](./docs/releases/v0.1.2.md)

## v0.1.1

- Release notes: [docs/releases/v0.1.1.md](./docs/releases/v0.1.1.md)

## v0.1.0

- Release notes: [docs/releases/v0.1.0.md](./docs/releases/v0.1.0.md)
