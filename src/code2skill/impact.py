from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from pathlib import Path

from .models import (
    CachedFileRecord,
    SkillBlueprint,
    SkillImpactIndexEntry,
    SourceFileSummary,
)
from .python_imports import build_python_module_index, resolve_python_imports


class ImpactAnalyzer:
    def enrich_internal_dependencies(
        self,
        records: dict[str, CachedFileRecord],
    ) -> dict[str, CachedFileRecord]:
        known_paths = set(records)
        module_index = build_python_module_index(known_paths)
        enriched: dict[str, CachedFileRecord] = {}
        for path, record in records.items():
            summary = record.source_summary
            if summary is None:
                enriched[path] = record
                continue
            if record.language != "python":
                enriched[path] = record
                continue
            internal_dependencies = resolve_python_imports(
                source_path=Path(path),
                imports=summary.imports,
                known_paths=known_paths,
                module_index=module_index,
            )
            enriched[path] = replace(
                record,
                source_summary=replace(
                    summary,
                    internal_dependencies=internal_dependencies,
                ),
            )
        return enriched

    def build_reverse_dependencies(
        self,
        records: dict[str, CachedFileRecord],
    ) -> dict[str, list[str]]:
        reverse_map: dict[str, set[str]] = defaultdict(set)
        for path, record in records.items():
            summary = record.source_summary
            if summary is None:
                continue
            for dependency in summary.internal_dependencies:
                reverse_map[dependency].add(path)
        return {
            path: sorted(importers)
            for path, importers in reverse_map.items()
        }

    def expand_affected_files(
        self,
        changed_files: list[str],
        reverse_dependencies: dict[str, list[str]],
    ) -> list[str]:
        queue = deque(changed_files)
        visited = set(changed_files)
        while queue:
            current = queue.popleft()
            for importer in reverse_dependencies.get(current, []):
                if importer in visited:
                    continue
                visited.add(importer)
                queue.append(importer)
        return sorted(visited)

    def build_skill_index(
        self,
        blueprint: SkillBlueprint,
    ) -> dict[str, SkillImpactIndexEntry]:
        index: dict[str, SkillImpactIndexEntry] = {}
        for skill in blueprint.recommended_skills:
            related_paths = set(skill.source_evidence)
            for module in blueprint.core_modules:
                if module.path in related_paths:
                    related_paths.add(module.path)
            index[skill.name] = SkillImpactIndexEntry(
                name=skill.name,
                purpose=skill.purpose,
                source_evidence=sorted(set(skill.source_evidence)),
                related_paths=sorted(related_paths),
            )
        return index

    def match_affected_skills(
        self,
        affected_files: list[str],
        skill_index: dict[str, SkillImpactIndexEntry],
    ) -> list[str]:
        affected = set(affected_files)
        matched = [
            name
            for name, entry in skill_index.items()
            if affected & set(entry.related_paths)
        ]
        return sorted(matched)
