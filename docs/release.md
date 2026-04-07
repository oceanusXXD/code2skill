# Release Guide

This repository ships both a CLI and a Python package.

This guide is safe to use as a local release rehearsal for a test version. It does not assume that tagging, GitHub Release creation, or PyPI publishing must happen in the current working tree.

## Pre-Release Checks

Run the local validation gates before tagging a release:

```bash
python -m pytest -q
python -m build
python -m twine check dist/*
```

## Test-Version Rehearsal

If you are only validating a test build locally:

1. keep the repository on an unreleased working branch
2. run the validation gates
3. inspect the generated files in `dist/`
4. install the wheel in an isolated environment
5. do not tag or upload anything yet

When doing repeated rehearsals, remove old `dist/` contents first so you do not accidentally validate or upload stale artifacts from another version.

Optional clean-install smoke check:

```bash
python -m venv .venv-smoke
. .venv-smoke/bin/activate
pip install dist/code2skill-*.whl
code2skill --help
python -m code2skill --version
```

## Version Update

When cutting a new release:

1. Update `version` in `pyproject.toml`
2. Update `__version__` in `src/code2skill/version.py`
3. Add a new note in `docs/releases/`
4. Update `CHANGELOG.md`

For a test-version rehearsal, you can skip this section and keep the current version unchanged.

## GitHub Actions

This repository includes:

- `.github/workflows/ci.yml`: unit tests plus package build and install smoke check
- `.github/workflows/release.yml`: version validation, build, `twine check`, and GitHub Release creation on version tags
- `.github/workflows/publish-pypi.yml`: manual PyPI publishing from a selected ref

The checked-in release workflow is intentionally repository-focused. It does not publish to PyPI automatically.
PyPI publishing is handled separately through the manual `publish-pypi.yml` workflow.

## Manual PyPI Publish

Use `.github/workflows/publish-pypi.yml` only when you explicitly want to publish a built version to PyPI.

Recommended flow:

1. prepare and push the final release commit
2. make sure `src/code2skill/version.py` has the final version and `pyproject.toml` still points to the dynamic version source
3. run the `Release` workflow via a version tag so GitHub Release creation succeeds
4. manually run `Publish PyPI` from the same ref and provide the exact version string

This keeps repository release automation and package publication separate.

## Manual Release Safety Notes

- do not use `twine upload dist/*` if `dist/` contains artifacts from multiple versions
- upload only the exact wheel and sdist for the intended version
- tag and publish only from a clean `git status`
