from __future__ import annotations

from code2skill.import_graph import ImportGraph
from code2skill.models import ImportInfo, SourceFileSummary


def _summary(path: str, language: str, imports: list[str]) -> SourceFileSummary:
    return SourceFileSummary(
        path=path,
        inferred_role="source",
        language=language,
        imports=imports,
    )


def test_import_graph_metrics_and_clusters() -> None:
    graph = ImportGraph()
    graph.build(
        {
            "src/main.py": _summary(
                "src/main.py",
                "python",
                [
                    "src.routes.users",
                    "src.routes.admin",
                    "src.services.user_service",
                ],
            ),
            "src/routes/users.py": _summary(
                "src/routes/users.py",
                "python",
                [
                    "..services.user_service",
                    "..models.user",
                ],
            ),
            "src/routes/admin.py": _summary(
                "src/routes/admin.py",
                "python",
                ["..services.user_service"],
            ),
            "src/services/user_service.py": _summary(
                "src/services/user_service.py",
                "python",
                [],
            ),
            "src/models/user.py": _summary(
                "src/models/user.py",
                "python",
                [],
            ),
            "src/utils/helpers.py": _summary(
                "src/utils/helpers.py",
                "python",
                [],
            ),
            "scripts/once.py": _summary(
                "scripts/once.py",
                "python",
                [],
            ),
        }
    )

    assert graph.total_internal_edges() == 6
    assert graph.get_in_degree("src/services/user_service.py") == 3
    assert graph.get_out_degree("src/main.py") == 3
    assert graph.get_hub_files(top_n=1) == ["src/services/user_service.py"]
    assert graph.get_entry_points() == ["src/main.py"]
    assert "scripts/once.py" in graph.get_leaf_files()
    assert any(
        cluster
        == [
            "src/main.py",
            "src/models/user.py",
            "src/routes/admin.py",
            "src/routes/users.py",
            "src/services/user_service.py",
        ]
        for cluster in graph.get_clusters()
    )
    assert any(cluster == ["src/utils/helpers.py"] for cluster in graph.get_clusters())
    assert any(cluster == ["scripts/once.py"] for cluster in graph.get_clusters())

    pagerank = graph.get_pagerank()
    assert max(pagerank, key=pagerank.get) == "src/services/user_service.py"


def test_import_graph_resolves_python_src_layout_imports() -> None:
    graph = ImportGraph()
    graph.build(
        {
            "src/demo_user_service/api/users.py": _summary(
                "src/demo_user_service/api/users.py",
                "python",
                [
                    "demo_user_service.models",
                    "demo_user_service.services.user_service",
                ],
            ),
            "src/demo_user_service/models.py": _summary(
                "src/demo_user_service/models.py",
                "python",
                [],
            ),
            "src/demo_user_service/services/user_service.py": _summary(
                "src/demo_user_service/services/user_service.py",
                "python",
                ["demo_user_service.models"],
            ),
        }
    )

    assert graph.total_internal_edges() == 3
    assert graph.internal_dependencies_for("src/demo_user_service/api/users.py") == [
        "src/demo_user_service/models.py",
        "src/demo_user_service/services/user_service.py",
    ]
    assert graph.get_in_degree("src/demo_user_service/models.py") == 2


def test_import_graph_resolves_from_imported_submodules_and_dynamic_imports() -> None:
    graph = ImportGraph()
    graph.build(
        {
            "src/app/handlers.py": SourceFileSummary(
                path="src/app/handlers.py",
                inferred_role="source",
                language="python",
                imports=[".", "app.plugins.audit"],
                import_details=[
                    ImportInfo(
                        module=".",
                        kind="from",
                        is_relative=True,
                        names=["services"],
                        aliases=["services"],
                    ),
                    ImportInfo(
                        module="app.plugins.audit",
                        kind="dynamic",
                        is_dynamic=True,
                    ),
                ],
            ),
            "src/app/services.py": _summary(
                "src/app/services.py",
                "python",
                [],
            ),
            "src/app/plugins/audit.py": _summary(
                "src/app/plugins/audit.py",
                "python",
                [],
            ),
        }
    )

    assert graph.internal_dependencies_for("src/app/handlers.py") == [
        "src/app/plugins/audit.py",
        "src/app/services.py",
    ]


def test_import_graph_resolves_reexported_symbol_references() -> None:
    graph = ImportGraph()
    graph.build(
        {
            "src/shop/__init__.py": SourceFileSummary(
                path="src/shop/__init__.py",
                inferred_role="source",
                language="python",
                imports=["shop.core.ops"],
                import_details=[
                    ImportInfo(
                        module="shop.core.ops",
                        kind="from",
                        names=["UserService"],
                        aliases=["UserService"],
                    )
                ],
            ),
            "src/shop/api/users.py": SourceFileSummary(
                path="src/shop/api/users.py",
                inferred_role="route",
                language="python",
                imports=["shop"],
                import_details=[
                    ImportInfo(
                        module="shop",
                        kind="from",
                        names=["UserService"],
                        aliases=["UserService"],
                    )
                ],
                call_targets=["UserService", "UserService.create"],
            ),
            "src/shop/core/ops.py": SourceFileSummary(
                path="src/shop/core/ops.py",
                inferred_role="service",
                language="python",
                top_level_symbols=["UserService"],
                classes=["UserService"],
            ),
        }
    )

    assert graph.internal_dependencies_for("src/shop/api/users.py") == [
        "src/shop/__init__.py",
        "src/shop/core/ops.py",
    ]
    assert graph.get_in_degree("src/shop/core/ops.py") == 2


def test_import_graph_leaves_ambiguous_plain_symbol_references_unresolved() -> None:
    graph = ImportGraph()
    graph.build(
        {
            "src/app/handler.py": SourceFileSummary(
                path="src/app/handler.py",
                inferred_role="source",
                language="python",
                call_targets=["UserService"],
            ),
            "src/app/a.py": SourceFileSummary(
                path="src/app/a.py",
                inferred_role="service",
                language="python",
                top_level_symbols=["UserService"],
                classes=["UserService"],
            ),
            "src/app/b.py": SourceFileSummary(
                path="src/app/b.py",
                inferred_role="service",
                language="python",
                top_level_symbols=["UserService"],
                classes=["UserService"],
            ),
        }
    )

    assert graph.internal_dependencies_for("src/app/handler.py") == []
