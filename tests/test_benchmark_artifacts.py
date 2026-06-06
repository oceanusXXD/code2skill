from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_structural_evidence_benchmark_script_generates_report_and_svg(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "benchmark.json"
    svg_path = tmp_path / "benchmark.svg"

    completed = subprocess.run(
        [
            sys.executable,
            "benchmarks/evaluate_structural_evidence.py",
            "--report-json",
            str(report_path),
            "--svg",
            str(svg_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "code2skill-semantic: gold_recall=1.000" in completed.stdout
    report = json.loads(report_path.read_text(encoding="utf-8"))
    recalls = {
        item["method"]: item["recall"]
        for item in report["results"]
    }
    assert recalls["path-only"] < recalls["ast-symbols"]
    assert recalls["ast-symbols"] < recalls["code2skill-semantic"]
    assert recalls["code2skill-semantic"] == 1.0
    assert "Structural Evidence Extraction" in svg_path.read_text(encoding="utf-8")
