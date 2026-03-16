from __future__ import annotations

from code2skill.models import ClassInfo, SourceFileSummary
from code2skill.pattern_detector import PatternDetector


def _service_summary(path: str, service_name: str) -> SourceFileSummary:
    return SourceFileSummary(
        path=path,
        inferred_role="service",
        language="python",
        imports=["app.db", "app.logging"],
        class_details=[
            ClassInfo(
                name=service_name,
                bases=["BaseService"],
                methods=[
                    f"{service_name}.create",
                    f"{service_name}.get",
                    f"{service_name}.update",
                ],
            )
        ],
        methods=[
            f"{service_name}.create",
            f"{service_name}.get",
            f"{service_name}.update",
        ],
        export_styles=["named"],
        file_structure=["imports", "classes", "exports"],
    )


def test_pattern_detector_finds_common_patterns_and_naming() -> None:
    detector = PatternDetector()
    skeletons = [
        _service_summary("services/UserService.py", "UserService"),
        _service_summary("services/OrderService.py", "OrderService"),
        _service_summary("services/BillingService.py", "BillingService"),
    ]

    patterns = detector.detect_patterns("service", skeletons)
    pattern_types = {pattern.pattern_type for pattern in patterns}
    descriptions = [pattern.description for pattern in patterns]

    assert "common_base_class" in pattern_types
    assert "common_method" in pattern_types
    assert "common_import" in pattern_types
    assert "file_structure" in pattern_types
    assert any("BaseService" in description for description in descriptions)
    assert any("create" in description for description in descriptions)

    naming = detector.detect_naming_conventions(
        role="service",
        file_paths=[summary.path for summary in skeletons],
    )

    assert naming is not None
    assert naming.pattern == "{name}Service.py"
    assert naming.case_style == "PascalCase"
    assert naming.coverage == 1.0

