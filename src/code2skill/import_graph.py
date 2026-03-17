from __future__ import annotations

from collections import deque
from pathlib import Path

from .models import SourceFileSummary
from .python_imports import build_python_module_index, resolve_python_imports


class ImportGraph:
    """全仓 import 依赖图。"""

    def __init__(self) -> None:
        self._nodes: set[str] = set()
        self._edges: dict[str, set[str]] = {}
        self._reverse_edges: dict[str, set[str]] = {}

    def build(self, file_skeletons: dict[str, SourceFileSummary]) -> None:
        self._nodes = set(file_skeletons)
        self._edges = {path: set() for path in self._nodes}
        self._reverse_edges = {path: set() for path in self._nodes}
        module_index = build_python_module_index(self._nodes)

        for path, skeleton in file_skeletons.items():
            for dependency in resolve_python_imports(
                source_path=Path(path),
                imports=skeleton.imports,
                known_paths=self._nodes,
                module_index=module_index,
            ):
                self._edges[path].add(dependency)
                self._reverse_edges.setdefault(dependency, set()).add(path)

    def get_in_degree(self, filepath: str) -> int:
        return len(self._reverse_edges.get(filepath, set()))

    def get_out_degree(self, filepath: str) -> int:
        return len(self._edges.get(filepath, set()))

    def get_hub_files(self, top_n: int = 20) -> list[str]:
        ranked = sorted(
            self._nodes,
            key=lambda path: (-self.get_in_degree(path), -self.get_out_degree(path), path),
        )
        return ranked[:top_n]

    def get_leaf_files(self) -> list[str]:
        return sorted(
            path
            for path in self._nodes
            if self.get_in_degree(path) == 0
        )

    def get_entry_points(self) -> list[str]:
        return sorted(
            path
            for path in self._nodes
            if self.get_in_degree(path) == 0 and self.get_out_degree(path) > 0
        )

    def get_clusters(self) -> list[list[str]]:
        undirected: dict[str, set[str]] = {path: set() for path in self._nodes}
        for source, targets in self._edges.items():
            for target in targets:
                undirected[source].add(target)
                undirected[target].add(source)

        visited: set[str] = set()
        clusters: list[list[str]] = []
        for node in sorted(self._nodes):
            if node in visited:
                continue
            queue = deque([node])
            component: list[str] = []
            visited.add(node)
            while queue:
                current = queue.popleft()
                component.append(current)
                for neighbor in sorted(undirected[current]):
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    queue.append(neighbor)
            clusters.append(sorted(component))
        clusters.sort(key=lambda cluster: (-len(cluster), cluster[0] if cluster else ""))
        return clusters

    def get_pagerank(
        self,
        damping: float = 0.85,
        iterations: int = 20,
    ) -> dict[str, float]:
        if not self._nodes:
            return {}
        node_count = len(self._nodes)
        base_score = (1.0 - damping) / node_count
        scores = {node: 1.0 / node_count for node in self._nodes}

        for _ in range(iterations):
            next_scores = {node: base_score for node in self._nodes}
            sink_total = sum(
                scores[node]
                for node in self._nodes
                if not self._edges.get(node)
            )
            sink_share = damping * sink_total / node_count

            for node in self._nodes:
                next_scores[node] += sink_share

            for source, targets in self._edges.items():
                if not targets:
                    continue
                distributed = damping * scores[source] / len(targets)
                for target in targets:
                    next_scores[target] += distributed
            scores = next_scores
        return scores

    def internal_dependencies_for(self, filepath: str) -> list[str]:
        return sorted(self._edges.get(filepath, set()))

    def reverse_dependencies(self) -> dict[str, list[str]]:
        return {
            path: sorted(importers)
            for path, importers in self._reverse_edges.items()
            if importers
        }

    def total_internal_edges(self) -> int:
        return sum(len(targets) for targets in self._edges.values())
