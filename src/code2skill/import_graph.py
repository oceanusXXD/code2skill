from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from .models import ImportInfo, SourceFileSummary
from .python_imports import (
    build_python_module_index,
    resolve_python_import_detail,
    resolve_python_imports,
)


class ImportGraph:
    """Repository-level import and symbol-reference dependency graph."""

    def __init__(self) -> None:
        self._nodes: set[str] = set()
        self._edges: dict[str, set[str]] = {}
        self._reverse_edges: dict[str, set[str]] = {}

    def build(self, file_skeletons: dict[str, SourceFileSummary]) -> None:
        self._nodes = set(file_skeletons)
        self._edges = {path: set() for path in self._nodes}
        self._reverse_edges = {path: set() for path in self._nodes}
        module_index = build_python_module_index(self._nodes)
        symbol_index = _build_symbol_index(
            file_skeletons=file_skeletons,
            module_index=module_index,
            known_paths=self._nodes,
        )

        for path, skeleton in file_skeletons.items():
            for dependency in resolve_python_imports(
                source_path=Path(path),
                imports=skeleton.imports,
                known_paths=self._nodes,
                module_index=module_index,
                import_details=skeleton.import_details,
            ):
                self._add_edge(path, dependency)

            for dependency in _resolve_semantic_dependencies(
                source_path=path,
                summary=skeleton,
                module_index=module_index,
                symbol_index=symbol_index,
            ):
                self._add_edge(path, dependency)

    def _add_edge(self, source: str, target: str) -> None:
        if target not in self._nodes or source == target:
            return
        self._edges.setdefault(source, set()).add(target)
        self._reverse_edges.setdefault(target, set()).add(source)

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


@dataclass(frozen=True)
class _SymbolIndex:
    by_full_name: dict[str, set[str]]
    by_plain_name: dict[str, set[str]]


def _build_symbol_index(
    *,
    file_skeletons: dict[str, SourceFileSummary],
    module_index: dict[str, set[str]],
    known_paths: set[str],
) -> _SymbolIndex:
    modules_by_path: dict[str, set[str]] = defaultdict(set)
    for module_name, paths in module_index.items():
        for path in paths:
            modules_by_path[path].add(module_name)

    by_full_name: dict[str, set[str]] = defaultdict(set)
    by_plain_name: dict[str, set[str]] = defaultdict(set)
    for path, summary in file_skeletons.items():
        for symbol in _declared_symbols(summary):
            by_plain_name[symbol].add(path)
            for module_name in modules_by_path.get(path, set()):
                by_full_name[f"{module_name}.{symbol}"].add(path)

    for path, summary in file_skeletons.items():
        for module_name in modules_by_path.get(path, set()):
            for detail in summary.import_details:
                if detail.kind != "from":
                    continue
                for imported_name, alias in _imported_symbol_names(detail):
                    dependency_paths = resolve_python_import_detail(
                        source_path=Path(path),
                        detail=ImportInfo(
                            module=detail.module,
                            kind="from",
                            is_relative=detail.is_relative,
                            names=[imported_name],
                            aliases=[alias],
                        ),
                        known_paths=known_paths,
                        module_index=module_index,
                    )
                    for dependency_path in dependency_paths:
                        by_full_name[f"{module_name}.{alias}"].add(dependency_path)

    return _SymbolIndex(
        by_full_name=dict(by_full_name),
        by_plain_name=dict(by_plain_name),
    )


def _resolve_semantic_dependencies(
    *,
    source_path: str,
    summary: SourceFileSummary,
    module_index: dict[str, set[str]],
    symbol_index: _SymbolIndex,
) -> list[str]:
    aliases = _import_alias_targets(summary)
    dependencies: set[str] = set()
    for reference in _semantic_references(summary):
        for candidate in _reference_candidates(reference, aliases):
            dependencies.update(
                _paths_for_candidate(
                    candidate,
                    module_index=module_index,
                    symbol_index=symbol_index,
                )
            )
    dependencies.discard(source_path)
    return sorted(dependencies)


def _declared_symbols(summary: SourceFileSummary) -> list[str]:
    return _dedupe(
        [
            *summary.top_level_symbols,
            *summary.exports,
            *summary.classes,
            *summary.functions,
        ]
    )


def _semantic_references(summary: SourceFileSummary) -> list[str]:
    return _dedupe(
        [
            *summary.call_targets,
            *summary.instantiated_classes,
            *summary.type_references,
            *summary.raised_exceptions,
            *summary.decorators,
        ]
    )


def _import_alias_targets(summary: SourceFileSummary) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    for detail in summary.import_details:
        if detail.kind == "from":
            for imported_name, alias in _imported_symbol_names(detail):
                aliases[alias].add(_join_import_name(detail.module, imported_name))
            continue

        import_aliases = detail.aliases or [detail.module.rsplit(".", 1)[-1]]
        for alias in import_aliases:
            aliases[alias].add(detail.module)
        if detail.module:
            root = detail.module.split(".", 1)[0]
            aliases[root].add(root)
    return dict(aliases)


def _imported_symbol_names(detail: ImportInfo) -> list[tuple[str, str]]:
    names: list[tuple[str, str]] = []
    for imported_name, alias in zip_longest(detail.names, detail.aliases, fillvalue=""):
        imported_name = imported_name or ""
        alias = alias or imported_name
        if not imported_name or imported_name == "*" or not alias:
            continue
        names.append((imported_name, alias))
    return names


def _reference_candidates(
    reference: str,
    aliases: dict[str, set[str]],
) -> list[str]:
    if not reference:
        return []

    parts = reference.split(".")
    candidates = [reference]
    for end in range(len(parts) - 1, 0, -1):
        candidates.append(".".join(parts[:end]))

    base = parts[0]
    tail = ".".join(parts[1:])
    for target in aliases.get(base, set()):
        candidates.append(target)
        if tail:
            candidates.append(f"{target}.{tail}")
    return _dedupe(candidates)


def _paths_for_candidate(
    candidate: str,
    *,
    module_index: dict[str, set[str]],
    symbol_index: _SymbolIndex,
) -> set[str]:
    paths: set[str] = set()
    parts = candidate.split(".")
    for end in range(len(parts), 0, -1):
        name = ".".join(parts[:end])
        paths.update(module_index.get(name, set()))
        paths.update(symbol_index.by_full_name.get(name, set()))
        if "." not in name:
            plain_paths = symbol_index.by_plain_name.get(name, set())
            if len(plain_paths) == 1:
                paths.update(plain_paths)
    return paths


def _join_import_name(module: str, name: str) -> str:
    if module.startswith("."):
        separator = "" if module.endswith(".") else "."
        return f"{module}{separator}{name}"
    if module:
        return f"{module}.{name}"
    return name


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
