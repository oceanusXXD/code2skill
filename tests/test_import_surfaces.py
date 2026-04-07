from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from code2skill import __version__

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _run_python(script: str) -> dict[str, bool]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout)


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "code2skill", *args],
        check=True,
        capture_output=True,
        cwd=ROOT,
        text=True,
        env=env,
    )


def test_package_import_does_not_eagerly_load_core() -> None:
    data = _run_python(
        "import json, sys; "
        "import code2skill; "
        "print(json.dumps({'core_loaded': 'code2skill.core' in sys.modules}))"
    )
    assert data["core_loaded"] is False


def test_cli_import_does_not_eagerly_load_core() -> None:
    data = _run_python(
        "import json, sys; "
        "import code2skill.cli; "
        "print(json.dumps({'core_loaded': 'code2skill.core' in sys.modules}))"
    )
    assert data["core_loaded"] is False


def test_package_public_api_still_resolves() -> None:
    data = _run_python(
        "import json; "
        "from code2skill import ("
        "adapt_repository, adapt_skills, create_scan_config, estimate, estimate_repository, "
        "run_ci, run_ci_repository, scan, scan_repository"
        "); "
        "print(json.dumps({"
        "'adapt_repository': callable(adapt_repository), "
        "'adapt_skills': callable(adapt_skills), "
        "'create_scan_config': callable(create_scan_config), "
        "'estimate_shortcut': callable(estimate), "
        "'scan': callable(scan_repository), "
        "'estimate': callable(estimate_repository), "
        "'scan_shortcut': callable(scan), "
        "'ci': callable(run_ci_repository), "
        "'ci_shortcut': callable(run_ci)"
        "}))"
    )
    assert data == {
        "adapt_repository": True,
        "adapt_skills": True,
        "create_scan_config": True,
        "estimate_shortcut": True,
        "scan": True,
        "estimate": True,
        "scan_shortcut": True,
        "ci": True,
        "ci_shortcut": True,
    }


def test_module_entrypoint_help_and_version_work() -> None:
    help_output = _run_module("--help")
    version_output = _run_module("--version")

    assert "Generate repository-aware Skills" in help_output.stdout
    assert "adapt" in help_output.stdout
    assert version_output.stdout.strip() == f"code2skill {__version__}"


def test_package_includes_py_typed_marker() -> None:
    assert (SRC / "code2skill" / "py.typed").exists()


def test_runtime_version_matches_pyproject_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["dynamic"] == ["version"]
    assert (
        pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"]
        == "code2skill.version.__version__"
    )
    assert __version__ == "0.1.7"
