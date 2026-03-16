from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..config import (
    CONFIG_FILE_GLOBS,
    ENTRYPOINT_BASENAMES,
    HIGH_VALUE_BASENAMES,
    is_high_value_path,
    matches_any_glob,
)
from ..models import SourceFileSummary


Matcher = Callable[[Path, str | None], bool]


@dataclass(frozen=True)
class PriorityRule:
    score: int
    reason: str
    role: str
    matcher: Matcher


class FilePrioritizer:
    """用规则表而不是散落 if/else 的方式给文件打分。"""

    def __init__(self) -> None:
        self.rules = [
            PriorityRule(100, "root config", "config", self._is_root_config),
            PriorityRule(95, "architecture documentation", "documentation", self._is_documentation),
            PriorityRule(92, "project entrypoint", "entrypoint", self._is_entrypoint),
            PriorityRule(90, "workspace or build config", "config", self._is_config_file),
            PriorityRule(85, "route or controller", "route", self._is_route_file),
            PriorityRule(82, "service or repository layer", "service", self._is_service_file),
            PriorityRule(79, "model or schema", "model", self._is_model_file),
            PriorityRule(64, "utility", "utility", self._is_utility_file),
            PriorityRule(52, "test", "test", self._is_test_file),
            PriorityRule(20, "general source", "source", self._is_source_file),
        ]

    def score(self, relative_path: Path, language: str | None) -> tuple[int, list[str], str]:
        """返回优先级分数、命中原因以及推断角色。"""

        matches = self._matched_rules(relative_path, language)
        if not matches:
            return 10, ["fallback candidate"], "source"

        matches.sort(key=lambda rule: rule.score, reverse=True)
        score = matches[0].score + min(len(matches) - 1, 3)
        reasons = [rule.reason for rule in matches]
        return score, reasons, matches[0].role

    def refine(
        self,
        relative_path: Path,
        language: str | None,
        current_score: int,
        current_role: str,
        current_reasons: list[str],
        summary: SourceFileSummary | None,
        in_degree: int,
        out_degree: int,
        pagerank_score: float,
        is_entry_point: bool,
        is_hub: bool,
    ) -> tuple[int, list[str], str]:
        role = current_role
        reasons = list(current_reasons)

        if summary is not None:
            content_role, content_reasons = self.infer_role_from_content(summary)
            if content_role and self._should_override_role(current_role, content_role):
                role = content_role
                reasons.append(f"content role: {content_role}")
            reasons.extend(content_reasons)

        score = current_score
        if in_degree:
            score += in_degree * 3
            reasons.append(f"in_degree:{in_degree}")
        if pagerank_score:
            score += int(round(pagerank_score * 50))
            reasons.append(f"pagerank:{pagerank_score:.3f}")
        if is_entry_point:
            score += 20
            reasons.append("import-graph entrypoint")
        if is_hub:
            score += 15
            reasons.append("import-graph hub")
        if in_degree == 0 and out_degree == 0:
            score -= 10
            reasons.append("isolated file")

        return score, _dedupe(reasons), role

    def infer_role_from_content(
        self,
        summary: SourceFileSummary,
    ) -> tuple[str | None, list[str]]:
        reasons: list[str] = []
        role: str | None = None

        if summary.routes:
            role = "route"
            reasons.append("content signal: route definitions")

        crud_methods = {"create", "get", "update", "delete", "list"}
        method_names = {
            method.split(".", 1)[-1].lower()
            for method in summary.methods
        } | {
            function.name.lower()
            for function in summary.function_details
        }
        if role is None and (
            any(class_info.name.endswith("Service") for class_info in summary.class_details)
            or len(crud_methods & method_names) >= 2
        ):
            role = "service"
            reasons.append("content signal: service methods")

        if role is None and (
            summary.models_or_schemas
            or any(
                any(
                    token in base.lower()
                    for token in ("model", "basemodel", "schema", "db.model")
                )
                for class_info in summary.class_details
                for base in class_info.bases
            )
        ):
            role = "model"
            reasons.append("content signal: model/schema")

        if role is None and len(summary.functions) >= 2:
            role = "utility"
            reasons.append("content signal: exported helpers")

        return role, reasons

    def _matched_rules(
        self,
        relative_path: Path,
        language: str | None,
    ) -> list[PriorityRule]:
        return [
            rule for rule in self.rules if rule.matcher(relative_path, language)
        ]

    @staticmethod
    def _should_override_role(current_role: str, content_role: str) -> bool:
        return current_role in {"source", "utility", "entrypoint"}

    @staticmethod
    def _is_root_config(path: Path, language: str | None) -> bool:
        return is_high_value_path(path)

    @staticmethod
    def _is_documentation(path: Path, language: str | None) -> bool:
        return path.name.lower().startswith("readme") or "architecture" in path.stem.lower()

    @staticmethod
    def _is_entrypoint(path: Path, language: str | None) -> bool:
        return path.name in ENTRYPOINT_BASENAMES or (
            language == "python"
            and path.stem.lower() in {"cli", "main", "app", "server"}
        )

    @staticmethod
    def _is_config_file(path: Path, language: str | None) -> bool:
        return path.name in HIGH_VALUE_BASENAMES or matches_any_glob(path, CONFIG_FILE_GLOBS)

    @staticmethod
    def _is_route_file(path: Path, language: str | None) -> bool:
        lowered = path.as_posix().lower()
        return language == "python" and any(
            token in lowered for token in ("route", "router", "controller", "/api/", "handler")
        )

    @staticmethod
    def _is_service_file(path: Path, language: str | None) -> bool:
        lowered = path.as_posix().lower()
        return language == "python" and any(
            token in lowered for token in ("service", "repository", "repo", "client")
        )

    @staticmethod
    def _is_model_file(path: Path, language: str | None) -> bool:
        lowered = path.as_posix().lower()
        return language == "python" and any(token in lowered for token in ("model", "schema", "entity", "dto"))

    @staticmethod
    def _is_utility_file(path: Path, language: str | None) -> bool:
        lowered = path.as_posix().lower()
        return language == "python" and any(token in lowered for token in ("util", "utils", "helper"))

    @staticmethod
    def _is_test_file(path: Path, language: str | None) -> bool:
        lowered = path.as_posix().lower()
        return language == "python" and any(token in lowered for token in ("test", "spec"))

    @staticmethod
    def _is_source_file(path: Path, language: str | None) -> bool:
        return language == "python"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
