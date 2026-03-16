from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


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
        "from code2skill import scan_repository, estimate_repository, run_ci_repository; "
        "print(json.dumps({"
        "'scan': callable(scan_repository), "
        "'estimate': callable(estimate_repository), "
        "'ci': callable(run_ci_repository)"
        "}))"
    )
    assert data == {
        "scan": True,
        "estimate": True,
        "ci": True,
    }
