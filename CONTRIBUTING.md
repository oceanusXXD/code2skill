# Contributing

Thanks for contributing to `code2skill`.

## Local Setup

```bash
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Validation

Run these before opening a pull request:

```bash
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Repository Areas

- `src/code2skill/`: production package code
- `tests/`: unit and integration tests
- `docs/`: user-facing guides and release notes
- `.github/`: workflows and GitHub community-health files

## Pull Request Expectations

- keep changes scoped and reviewable
- add or update tests for behavior changes
- update docs when command behavior, API shape, or release process changes
- update `CHANGELOG.md` and add `docs/releases/vX.Y.Z.md` when preparing a release

## Release Update Steps

For release preparation, follow the canonical checklist in [`docs/release.md`](./docs/release.md).
