from __future__ import annotations

from collections import deque
from pathlib import Path

from .models import SourceFileSummary


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

        for path, skeleton in file_skeletons.items():
            for dependency in self._resolve_dependencies(
                source_path=Path(path),
                language=skeleton.language,
                imports=skeleton.imports,
                known_paths=self._nodes,
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

    def _resolve_dependencies(
        self,
        source_path: Path,
        language: str | None,
        imports: list[str],
        known_paths: set[str],
    ) -> list[str]:
        if language != "python":
            return []

        resolved: set[str] = set()
        for import_name in imports:
            resolved.update(
                self._resolve_python_import(
                    source_path=source_path,
                    import_name=import_name,
                    known_paths=known_paths,
                )
            )
        return sorted(resolved)

    def _resolve_python_import(
        self,
        source_path: Path,
        import_name: str,
        known_paths: set[str],
    ) -> list[str]:
        if not import_name:
            return []
        if import_name.startswith("."):
            level = len(import_name) - len(import_name.lstrip("."))
            module_name = import_name[level:]
            base_dir = source_path.parent
            for _ in range(max(level - 1, 0)):
                base_dir = base_dir.parent
            target = base_dir
            if module_name:
                target = target.joinpath(*module_name.split("."))
            return self._expand_python_candidates(target, known_paths)

        module_path = Path(*import_name.split("."))
        return self._expand_python_candidates(module_path, known_paths)

    def _expand_python_candidates(
        self,
        target: Path,
        known_paths: set[str],
    ) -> list[str]:
        candidates = [
            target.with_suffix(".py").as_posix(),
            (target / "__init__.py").as_posix(),
        ]
        return [candidate for candidate in candidates if candidate in known_paths]
