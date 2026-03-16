from __future__ import annotations

import json
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


# 默认忽略目录。
# 这里把构建产物、缓存目录和编辑器目录统一收口，避免散落在多处判断。
DEFAULT_IGNORE_DIRS = {
    ".code2skill",
    ".git",
    ".idea",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "bin",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "obj",
    "out",
    "target",
    "temp",
    "tmp",
    "vendor",
    "venv",
}

LOW_VALUE_BASENAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "cargo.lock",
}

HIGH_VALUE_BASENAMES = {
    "README",
    "README.md",
    "README.txt",
    "Dockerfile",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
}

HIGH_VALUE_GLOBS = (
    "Dockerfile.*",
)

CONFIG_FILE_GLOBS = (
    ".env.example",
    "docker-compose*.yml",
    "docker-compose*.yaml",
)

ENTRYPOINT_BASENAMES = {
    "app.py",
    "main.py",
    "manage.py",
    "server.py",
}

STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less"}

BINARY_EXTENSIONS = {
    ".7z",
    ".a",
    ".avi",
    ".class",
    ".dll",
    ".dylib",
    ".eot",
    ".exe",
    ".flac",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".map",
    ".min.css",
    ".min.js",
    ".mov",
    ".mp3",
    ".mp4",
    ".o",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".svg",
    ".tar",
    ".ttf",
    ".wav",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
}

BACKEND_FRAMEWORKS = {
    "django",
    "fastapi",
    "flask",
}

STATE_DIRNAME = "state"
STATE_FILENAME = "analysis-state.json"
DEFAULT_REPORT_FILENAME = "report.json"


def matches_any_glob(path: Path, patterns: tuple[str, ...]) -> bool:
    name = path.name
    full_path = path.as_posix()
    return any(
        fnmatch(name, pattern) or fnmatch(full_path, pattern)
        for pattern in patterns
    )


def infer_language(path: Path) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower())


def is_high_value_path(path: Path) -> bool:
    if path.name in HIGH_VALUE_BASENAMES:
        return True
    if matches_any_glob(path, HIGH_VALUE_GLOBS):
        return True
    return path.name in ENTRYPOINT_BASENAMES


@dataclass(frozen=True)
class ScanLimits:
    max_files: int = 40
    max_file_size_kb: int = 256
    max_total_chars: int = 120000


# 价格配置单独抽出来，后续可以直接接 CI 的 secrets 或配置文件。
@dataclass(frozen=True)
class PricingConfig:
    model: str = "heuristic"
    input_per_1m: float = 0.0
    output_per_1m: float = 0.0
    chars_per_token: float = 4.0

    @classmethod
    def from_file(cls, path: Path | None) -> "PricingConfig":
        if path is None:
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            model=str(data.get("model", "heuristic")),
            input_per_1m=float(data.get("input_per_1m", 0.0)),
            output_per_1m=float(data.get("output_per_1m", 0.0)),
            chars_per_token=float(data.get("chars_per_token", 4.0)),
        )


# 运行选项统一描述 scan / estimate / ci 三种入口，
# 这样核心流水线只认一套参数对象。
@dataclass(frozen=True)
class RunOptions:
    command: str = "scan"
    mode: str = "full"
    base_ref: str | None = None
    head_ref: str = "HEAD"
    diff_file: Path | None = None
    report_path: Path | None = None
    pricing: PricingConfig = field(default_factory=PricingConfig)
    structure_only: bool = False
    llm_provider: str = "openai"
    llm_model: str | None = None
    max_skills: int = 8
    write_outputs: bool = True
    write_state: bool = True
    max_incremental_changed_files: int = 64
    force_full_on_config_change: bool = True


@dataclass(frozen=True)
class ScanConfig:
    repo_path: Path
    output_dir: Path
    limits: ScanLimits = field(default_factory=ScanLimits)
    run: RunOptions = field(default_factory=RunOptions)
