from __future__ import annotations

from pathlib import Path

from ..config import infer_language

FRAMEWORK_PACKAGE_MAP = {
    "fastapi": {"fastapi"},
    "flask": {"flask"},
    "django": {"django", "djangorestframework"},
    "pytest": {"pytest"},
}

def detect_language(path: Path) -> str | None:
    """按后缀识别当前文件属于哪种源码语言。"""

    return infer_language(path)


def detect_framework_signals(package_names: set[str]) -> list[str]:
    """根据依赖名集合识别框架信号。"""

    lowered = {package_name.lower() for package_name in package_names}
    detected: list[str] = []
    for framework, aliases in FRAMEWORK_PACKAGE_MAP.items():
        if any(alias in lowered or any(name.startswith(alias) for name in lowered) for alias in aliases):
            detected.append(framework)
    return sorted(set(detected))


def infer_role_domain(role: str) -> str:
    """把文件角色映射到更高层的领域标签。"""

    if role in {"route", "service", "model"}:
        return "backend"
    if role in {"config", "entrypoint"}:
        return "shared"
    if role in {"test"}:
        return "quality"
    return "shared"
