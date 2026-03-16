from __future__ import annotations

from pathlib import Path

import pytest

from code2skill.models import ClassInfo, FunctionInfo, RouteSummary, SourceFileSummary
from code2skill.scanner.prioritizer import FilePrioritizer


@pytest.mark.parametrize(
    ("current_role", "summary", "expected_role"),
    [
        (
            "source",
            SourceFileSummary(
                path="src/features/module.py",
                inferred_role="source",
                language="python",
                routes=[
                    RouteSummary(
                        method="GET",
                        path="/users",
                        handler="list_users",
                        framework="fastapi",
                    )
                ],
            ),
            "route",
        ),
        (
            "source",
            SourceFileSummary(
                path="src/services/users.py",
                inferred_role="source",
                language="python",
                class_details=[
                    ClassInfo(
                        name="UserService",
                        methods=["create", "get", "update"],
                    )
                ],
                function_details=[
                    FunctionInfo(name="create"),
                    FunctionInfo(name="get"),
                    FunctionInfo(name="update"),
                ],
            ),
            "service",
        ),
        (
            "source",
            SourceFileSummary(
                path="src/models/user.py",
                inferred_role="source",
                language="python",
                models_or_schemas=["UserModel"],
            ),
            "model",
        ),
    ],
)
def test_refine_uses_content_signals_to_fix_roles(
    current_role: str,
    summary: SourceFileSummary,
    expected_role: str,
) -> None:
    score, reasons, refined_role = FilePrioritizer().refine(
        relative_path=Path(summary.path),
        language=summary.language,
        current_score=20,
        current_role=current_role,
        current_reasons=["general source"],
        summary=summary,
        in_degree=0,
        out_degree=1,
        pagerank_score=0.0,
        is_entry_point=False,
        is_hub=False,
    )

    assert refined_role == expected_role
    assert score == 20
    assert any(reason.startswith("content signal:") for reason in reasons)
