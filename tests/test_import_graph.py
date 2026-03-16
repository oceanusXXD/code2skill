from __future__ import annotations

from code2skill.import_graph import ImportGraph
from code2skill.models import SourceFileSummary


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

