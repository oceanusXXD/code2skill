from __future__ import annotations

import importlib

try:
    tomllib = importlib.import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = importlib.import_module("tomli")

from ..models import ConfigSummary, FileCandidate
from ..scanner.detector import detect_framework_signals


class ConfigExtractor:
    """从高价值配置文件中提取框架、入口和拓扑信号。"""

    def extract(self, candidate: FileCandidate) -> ConfigSummary | None:
        """按配置文件类型分派不同的轻量解析逻辑。"""

        name = candidate.relative_path.name
        if name == "pyproject.toml":
            return self._extract_pyproject(candidate)
        if name == "requirements.txt":
            return self._extract_requirements(candidate)
        if name.startswith("Dockerfile"):
            entrypoints = _extract_docker_entrypoints(_candidate_text(candidate))
            return ConfigSummary(
                path=candidate.relative_path.as_posix(),
                kind="docker",
                summary="Container build instructions.",
                entrypoints=entrypoints,
            )
        return None

    def _extract_pyproject(self, candidate: FileCandidate) -> ConfigSummary:
        """提取 Python 项目的依赖、入口和框架线索。"""

        raw_data = tomllib.loads(_candidate_text(candidate))
        data = _mapping_value(raw_data)
        project = _mapping_value(data.get("project"))
        tool_config = _mapping_value(data.get("tool"))
        poetry = _mapping_value(tool_config.get("poetry"))
        dependencies = _normalize_python_dependencies(project.get("dependencies"))
        poetry_dependencies = _normalize_python_dependencies(
            list(_mapping_value(poetry.get("dependencies")).keys())
        )
        framework_signals = detect_framework_signals(set(dependencies + poetry_dependencies))
        entrypoints = _extract_pyproject_entrypoints(project)
        summary = "Python project metadata"
        if framework_signals:
            summary = f"Python project metadata with {', '.join(framework_signals)} signals."
        return ConfigSummary(
            path=candidate.relative_path.as_posix(),
            kind="pyproject",
            summary=summary,
            framework_signals=framework_signals,
            entrypoints=entrypoints,
            details={
                "name": project.get("name") or poetry.get("name"),
                "dependencies": sorted(set(dependencies + poetry_dependencies))[:20],
            },
        )

    def _extract_requirements(self, candidate: FileCandidate) -> ConfigSummary:
        """提取 requirements.txt 中的框架信号。"""

        dependencies = _normalize_python_dependencies(_candidate_text(candidate).splitlines())
        framework_signals = detect_framework_signals(set(dependencies))
        summary = "Pinned Python dependencies."
        if framework_signals:
            summary = f"Python dependency file with {', '.join(framework_signals)} signals."
        return ConfigSummary(
            path=candidate.relative_path.as_posix(),
            kind="requirements",
            summary=summary,
            framework_signals=framework_signals,
            details={"dependencies": dependencies[:30]},
        )


def _candidate_text(candidate: FileCandidate) -> str:
    return candidate.content or ""


def _mapping_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _normalize_python_dependencies(values: object) -> list[str]:
    """把版本表达式归一化为纯包名，便于做框架识别。"""

    if not isinstance(values, list):
        return []
    dependencies: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        raw = value.strip()
        if not raw or raw.startswith("#") or raw.startswith("python"):
            continue
        for separator in ("[", "=", "<", ">", "!", "~"):
            if separator in raw:
                raw = raw.split(separator, 1)[0]
        dependencies.append(raw.strip())
    return sorted(set(item for item in dependencies if item))


def _extract_pyproject_entrypoints(project: dict[str, object]) -> list[str]:
    """从 pyproject 的 scripts 区块提取入口点。"""

    scripts = _mapping_value(project.get("scripts"))
    return sorted(
        value for value in (_string_value(script_target) for script_target in scripts.values()) if value
    )


def _extract_docker_entrypoints(content: str) -> list[str]:
    """提取 Dockerfile 中声明的启动命令。"""

    entrypoints: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("CMD ") or stripped.startswith("ENTRYPOINT "):
            entrypoints.append(stripped)
    return entrypoints


def _string_value(value: object) -> str:
    """把可能的任意对象安全压缩成字符串。"""

    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return ""
    return str(value) if value is not None else ""
