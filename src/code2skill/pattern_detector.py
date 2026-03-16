from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import SourceFileSummary


@dataclass(frozen=True)
class DetectedPattern:
    pattern_type: str
    description: str
    evidence_files: list[str]
    coverage: float
    example_snippet: str


@dataclass(frozen=True)
class NamingConvention:
    role: str
    pattern: str
    case_style: str
    examples: list[str]
    coverage: float


class PatternDetector:
    """同角色文件的模式比较器。"""

    def detect_patterns(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
    ) -> list[DetectedPattern]:
        if not skeletons:
            return []

        threshold = max(1, int(len(skeletons) * 0.6 + 0.9999))
        patterns: list[DetectedPattern] = []

        patterns.extend(
            self._detect_common_base_classes(role, skeletons, threshold)
        )
        patterns.extend(
            self._detect_common_imports(role, skeletons, threshold)
        )
        patterns.extend(
            self._detect_common_methods(role, skeletons, threshold)
        )
        patterns.extend(
            self._detect_common_decorators(role, skeletons, threshold)
        )
        patterns.extend(
            self._detect_common_exports(role, skeletons, threshold)
        )
        structure_pattern = self._detect_file_structure(role, skeletons, threshold)
        if structure_pattern is not None:
            patterns.append(structure_pattern)

        patterns.sort(key=lambda item: (-item.coverage, item.pattern_type, item.description))
        return patterns

    def detect_naming_conventions(
        self,
        role: str,
        file_paths: list[str],
    ) -> NamingConvention | None:
        if len(file_paths) < 2:
            return None

        stems = [Path(path).stem for path in file_paths]
        case_styles = Counter(_classify_name_style(stem) for stem in stems)
        case_styles.pop(None, None)
        if not case_styles:
            return None
        dominant_case, case_count = case_styles.most_common(1)[0]
        coverage = case_count / len(stems)

        suffix_pattern = _common_affix(stems, suffix=True)
        prefix_pattern = _common_affix(stems, suffix=False)
        if suffix_pattern:
            pattern = f"{{name}}{suffix_pattern}{Path(file_paths[0]).suffix}"
        elif prefix_pattern:
            pattern = f"{prefix_pattern}{{name}}{Path(file_paths[0]).suffix}"
        else:
            pattern = f"{{name}}{Path(file_paths[0]).suffix}"

        if coverage < 0.6:
            return None
        return NamingConvention(
            role=role,
            pattern=pattern,
            case_style=dominant_case,
            examples=sorted(file_paths)[:4],
            coverage=coverage,
        )

    def _detect_common_base_classes(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
        threshold: int,
    ) -> list[DetectedPattern]:
        coverage_by_base: dict[str, list[str]] = defaultdict(list)
        for skeleton in skeletons:
            bases = {
                base
                for class_info in skeleton.class_details
                for base in class_info.bases
            }
            for base in bases:
                coverage_by_base[base].append(skeleton.path)

        patterns: list[DetectedPattern] = []
        for base, evidence in coverage_by_base.items():
            if len(evidence) < threshold:
                continue
            coverage = len(evidence) / len(skeletons)
            patterns.append(
                DetectedPattern(
                    pattern_type="common_base_class",
                    description=f"Most {role} files inherit from {base}.",
                    evidence_files=sorted(evidence),
                    coverage=coverage,
                    example_snippet=f"class Example{role.title()}({base}):\n    ...",
                )
            )
        return patterns

    def _detect_common_imports(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
        threshold: int,
    ) -> list[DetectedPattern]:
        import_to_files: dict[str, list[str]] = defaultdict(list)
        for skeleton in skeletons:
            for imported in set(skeleton.imports):
                import_to_files[imported].append(skeleton.path)

        patterns: list[DetectedPattern] = []
        for imported, evidence in import_to_files.items():
            if len(evidence) < threshold:
                continue
            coverage = len(evidence) / len(skeletons)
            patterns.append(
                DetectedPattern(
                    pattern_type="common_import",
                    description=f"Most {role} files import {imported}.",
                    evidence_files=sorted(evidence),
                    coverage=coverage,
                    example_snippet=f"import {imported}",
                )
            )
        return patterns

    def _detect_common_methods(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
        threshold: int,
    ) -> list[DetectedPattern]:
        method_to_files: dict[str, list[str]] = defaultdict(list)
        for skeleton in skeletons:
            names = {
                function.name
                for function in skeleton.function_details
            }
            names.update(
                method.split(".", 1)[-1]
                for method in skeleton.methods
            )
            for name in names:
                method_to_files[name].append(skeleton.path)

        patterns: list[DetectedPattern] = []
        for method_name, evidence in method_to_files.items():
            if len(evidence) < threshold:
                continue
            coverage = len(evidence) / len(skeletons)
            patterns.append(
                DetectedPattern(
                    pattern_type="common_method",
                    description=f"Most {role} files expose a {method_name} method or function.",
                    evidence_files=sorted(evidence),
                    coverage=coverage,
                    example_snippet=f"def {method_name}(...):\n    ...",
                )
            )
        return patterns

    def _detect_common_decorators(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
        threshold: int,
    ) -> list[DetectedPattern]:
        decorator_to_files: dict[str, list[str]] = defaultdict(list)
        for skeleton in skeletons:
            for decorator in set(skeleton.decorators):
                decorator_to_files[decorator].append(skeleton.path)

        patterns: list[DetectedPattern] = []
        for decorator, evidence in decorator_to_files.items():
            if len(evidence) < threshold:
                continue
            coverage = len(evidence) / len(skeletons)
            patterns.append(
                DetectedPattern(
                    pattern_type="common_decorator",
                    description=f"Most {role} files use the @{decorator} decorator.",
                    evidence_files=sorted(evidence),
                    coverage=coverage,
                    example_snippet=f"@{decorator}\n...",
                )
            )
        return patterns

    def _detect_common_exports(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
        threshold: int,
    ) -> list[DetectedPattern]:
        export_to_files: dict[str, list[str]] = defaultdict(list)
        for skeleton in skeletons:
            for export_style in set(skeleton.export_styles):
                export_to_files[export_style].append(skeleton.path)

        patterns: list[DetectedPattern] = []
        for export_style, evidence in export_to_files.items():
            if len(evidence) < threshold:
                continue
            coverage = len(evidence) / len(skeletons)
            patterns.append(
                DetectedPattern(
                    pattern_type="common_export",
                    description=f"Most {role} files use {export_style} exports.",
                    evidence_files=sorted(evidence),
                    coverage=coverage,
                    example_snippet=f"export {export_style} ...",
                )
            )
        return patterns

    def _detect_file_structure(
        self,
        role: str,
        skeletons: list[SourceFileSummary],
        threshold: int,
    ) -> DetectedPattern | None:
        structures: Counter[tuple[str, ...]] = Counter()
        evidence_map: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for skeleton in skeletons:
            structure = tuple(skeleton.file_structure)
            if not structure:
                continue
            structures[structure] += 1
            evidence_map[structure].append(skeleton.path)

        if not structures:
            return None
        structure, count = structures.most_common(1)[0]
        if count < threshold:
            return None
        return DetectedPattern(
            pattern_type="file_structure",
            description=f"Most {role} files follow the order: {' -> '.join(structure)}.",
            evidence_files=sorted(evidence_map[structure]),
            coverage=count / len(skeletons),
            example_snippet="\n".join(structure),
        )


def _classify_name_style(name: str) -> str | None:
    if "-" in name:
        return "kebab-case"
    if "_" in name:
        return "snake_case"
    if name[:1].isupper():
        return "PascalCase"
    if any(character.isupper() for character in name[1:]):
        return "camelCase"
    return None


def _common_affix(values: list[str], suffix: bool) -> str:
    if not values:
        return ""
    shortest = min(values, key=len)
    candidates = []
    for length in range(2, len(shortest) + 1):
        part = shortest[-length:] if suffix else shortest[:length]
        if all(
            value.endswith(part) if suffix else value.startswith(part)
            for value in values
        ):
            candidates.append(part)
    return max(candidates, key=len, default="")
