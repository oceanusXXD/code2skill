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


class ImpactAnalyzer:
    def enrich_internal_dependencies(
        self,
        records: dict[str, CachedFileRecord],
    ) -> dict[str, CachedFileRecord]:
        known_paths = set(records)
        enriched: dict[str, CachedFileRecord] = {}
        for path, record in records.items():
            summary = record.source_summary
            if summary is None:
                enriched[path] = record
                continue
            internal_dependencies = self._resolve_dependencies(
                source_path=Path(path),
                language=record.language,
                imports=summary.imports,
                known_paths=known_paths,
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
