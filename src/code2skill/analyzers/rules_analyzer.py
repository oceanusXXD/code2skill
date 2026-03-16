from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ..models import ConfigSummary, RuleSummary, SourceFileSummary
from ..pattern_detector import PatternDetector


class RulesAnalyzer:
    """从项目证据中总结较稳定、可复用的抽象规则。"""

    def analyze(
        self,
        source_summaries: list[SourceFileSummary],
        config_summaries: list[ConfigSummary],
    ) -> list[RuleSummary]:
        rules: list[RuleSummary] = []
        pattern_detector = PatternDetector()
        grouped_by_role: dict[str, list[SourceFileSummary]] = defaultdict(list)
        for summary in source_summaries:
            grouped_by_role[summary.inferred_role].append(summary)

        for role, skeletons in sorted(grouped_by_role.items()):
            if len(skeletons) >= 2:
                patterns = pattern_detector.detect_patterns(role, skeletons)
                for index, pattern in enumerate(patterns, start=1):
                    rules.append(
                        RuleSummary(
                            name=f"{role}-pattern-{index}",
                            rule=pattern.description,
                            rationale=(
                                f"Pattern detection found this structure in {len(pattern.evidence_files)} "
                                f"of {len(skeletons)} analyzed {role} files."
                            ),
                            evidence_files=pattern.evidence_files,
                            source="pattern_detection",
                            confidence=pattern.coverage,
                            example_snippet=pattern.example_snippet,
                        )
                    )

            naming = pattern_detector.detect_naming_conventions(
                role=role,
                file_paths=[item.path for item in skeletons],
            )
            if naming is not None:
                rules.append(
                    RuleSummary(
                        name=f"{role}-naming",
                        rule=(
                            f"{role} files follow the naming pattern {naming.pattern} "
                            f"using {naming.case_style}."
                        ),
                        rationale=(
                            f"Detected from {len(naming.examples)} representative files "
                            f"with {naming.coverage:.0%} coverage."
                        ),
                        evidence_files=naming.examples,
                        source="naming_detection",
                        confidence=naming.coverage,
                    )
                )

        rules.extend(self._heuristic_rules(source_summaries, config_summaries))
        rules.sort(key=lambda item: (-item.confidence, item.source, item.name))
        return rules

    def _heuristic_rules(
        self,
        source_summaries: list[SourceFileSummary],
        config_summaries: list[ConfigSummary],
    ) -> list[RuleSummary]:
        rules: list[RuleSummary] = []
        naming_rule = self._detect_repository_naming_rule(source_summaries)
        if naming_rule is not None:
            rules.append(naming_rule)

        roles = {summary.inferred_role for summary in source_summaries}
        if {"route", "service", "model"} & roles and {"route", "service"} <= roles:
            rules.append(
                RuleSummary(
                    name="layered-backend",
                    rule="HTTP-facing handlers appear to be separated from service and model concerns.",
                    rationale=(
                        "Route/controller signals coexist with dedicated service and model/schema files, "
                        "which suggests a layered backend boundary."
                    ),
                    evidence_files=_collect_evidence(source_summaries, {"route", "service", "model"}),
                    source="heuristic",
                    confidence=0.45,
                )
            )
        if any(summary.kind in {"pyproject", "requirements", "docker"} for summary in config_summaries):
            rules.append(
                RuleSummary(
                    name="root-configs",
                    rule="Project-level tooling is centralized in a small number of root configuration files.",
                    rationale="Root manifests provide the main build and dependency signals for the repository.",
                    evidence_files=[summary.path for summary in config_summaries[:4]],
                    source="heuristic",
                    confidence=0.4,
                )
            )
        if any(summary.inferred_role == "test" for summary in source_summaries):
            rules.append(
                RuleSummary(
                    name="testing-convention",
                    rule="Dedicated test files are present and should stay aligned with feature-level changes.",
                    rationale="The repository exposes test entrypoints, so new behaviors likely belong with tests.",
                    evidence_files=_collect_evidence(source_summaries, {"test"}),
                    source="heuristic",
                    confidence=0.35,
                )
            )
        return rules

    def _detect_repository_naming_rule(
        self,
        source_summaries: list[SourceFileSummary],
    ) -> RuleSummary | None:
        styles = Counter()
        evidence: list[str] = []
        for summary in source_summaries:
            style = _classify_name_style(Path(summary.path).stem)
            if style is None:
                continue
            styles[style] += 1
            if len(evidence) < 5:
                evidence.append(summary.path)
        if not styles:
            return None
        dominant_style, count = styles.most_common(1)[0]
        coverage = count / max(len(source_summaries), 1)
        return RuleSummary(
            name="file-naming",
            rule=f"Most source files follow {dominant_style} naming.",
            rationale=f"The dominant naming style appears in {count} analyzed files.",
            evidence_files=evidence,
            source="heuristic",
            confidence=min(0.5, coverage),
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


def _collect_evidence(source_summaries: list[SourceFileSummary], roles: set[str]) -> list[str]:
    return [summary.path for summary in source_summaries if summary.inferred_role in roles][:8]
