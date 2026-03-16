from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from ..config import (
    BINARY_EXTENSIONS,
    DEFAULT_IGNORE_DIRS,
    HIGH_VALUE_BASENAMES,
    LOW_VALUE_BASENAMES,
    STYLE_EXTENSIONS,
    is_high_value_path,
    matches_any_glob,
)


@dataclass(frozen=True)
class FilterDecision:
    include: bool
    reason: str
    gitignored: bool = False


@dataclass(frozen=True)
class GitIgnoreRule:
    pattern: str
    negate: bool = False
    directory_only: bool = False
    anchored: bool = False


class GitIgnoreMatcher:
    """只实现 MVP 需要的 `.gitignore` 核心匹配语义。"""

    def __init__(self, rules: list[GitIgnoreRule]) -> None:
        self.rules = rules

    @classmethod
    def from_repo(cls, repo_path: Path) -> "GitIgnoreMatcher":
        """从仓库根目录读取 `.gitignore` 规则。"""

        gitignore_path = repo_path / ".gitignore"
        if not gitignore_path.exists():
            return cls([])
        rules: list[GitIgnoreRule] = []
        raw_text = gitignore_path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:]
            directory_only = line.endswith("/")
            if directory_only:
                line = line[:-1]
            anchored = line.startswith("/")
            if anchored:
                line = line[1:]
            rules.append(
                GitIgnoreRule(
                    pattern=line,
                    negate=negate,
                    directory_only=directory_only,
                    anchored=anchored,
                )
            )
        return cls(rules)

    def matches(self, relative_path: Path, is_dir: bool = False) -> bool:
        """按 gitignore 的顺序规则判断路径是否被忽略。"""

        text = relative_path.as_posix()
        basename = relative_path.name
        matched = False
        for rule in self.rules:
            if _matches_rule(rule, text, basename, is_dir):
                matched = not rule.negate
        return matched

    def patterns(self) -> list[str]:
        rendered: list[str] = []
        for rule in self.rules:
            pattern = rule.pattern
            if rule.anchored:
                pattern = f"/{pattern}"
            if rule.directory_only:
                pattern = f"{pattern}/"
            if rule.negate:
                pattern = f"!{pattern}"
            rendered.append(pattern)
        return rendered


def _matches_rule(rule: GitIgnoreRule, text: str, basename: str, is_dir: bool) -> bool:
    """执行单条 gitignore 规则匹配。"""

    pattern = rule.pattern
    if not pattern:
        return False

    if rule.directory_only:
        if text == pattern or text.startswith(f"{pattern}/"):
            return True
        return False

    if rule.anchored:
        return fnmatch(text, pattern)

    if "/" in pattern:
        return fnmatch(text, pattern) or text.startswith(f"{pattern}/")

    if fnmatch(basename, pattern):
        return True
    return any(fnmatch(part, pattern) for part in text.split("/"))


class FileFilter:
    """统一处理目录、后缀、大小和内容层面的过滤逻辑。"""

    def __init__(self, max_file_size_kb: int, gitignore_matcher: GitIgnoreMatcher) -> None:
        self.max_file_size_bytes = max_file_size_kb * 1024
        self.gitignore_matcher = gitignore_matcher

    def should_include_path(self, relative_path: Path, size_bytes: int) -> FilterDecision:
        """先基于路径和大小做快速过滤，减少无意义 IO。"""

        lower_name = relative_path.name.lower()
        lower_path = relative_path.as_posix().lower()
        high_value = is_high_value_path(relative_path)

        if any(part in DEFAULT_IGNORE_DIRS for part in relative_path.parts[:-1]):
            return FilterDecision(False, "ignored directory")

        if lower_name in LOW_VALUE_BASENAMES and not high_value:
            return FilterDecision(False, "low-value lock file")

        if lower_name.endswith(".snap"):
            return FilterDecision(False, "snapshot file")

        suffixes = {suffix.lower() for suffix in relative_path.suffixes}
        if suffixes & BINARY_EXTENSIONS:
            return FilterDecision(False, "binary or bundled asset")

        if lower_name.endswith(".min.js") or lower_name.endswith(".min.css"):
            return FilterDecision(False, "minified asset")

        if lower_name.endswith(".map"):
            return FilterDecision(False, "source map")

        if size_bytes > self.max_file_size_bytes and not high_value:
            return FilterDecision(False, "file exceeds size budget")

        gitignored = self.gitignore_matcher.matches(relative_path)
        if gitignored and not high_value:
            return FilterDecision(False, "ignored by .gitignore", gitignored=True)

        if matches_any_glob(relative_path, ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg")):
            return FilterDecision(False, "image asset")

        if relative_path.suffix.lower() in STYLE_EXTENSIONS:
            return FilterDecision(True, "style file", gitignored=gitignored)

        if relative_path.name in HIGH_VALUE_BASENAMES:
            return FilterDecision(True, "high-value config or documentation", gitignored=gitignored)

        return FilterDecision(True, "text candidate", gitignored=gitignored)

    def should_include_content(self, relative_path: Path, content: str) -> FilterDecision:
        """在读取文本后，基于内容进一步剔除低价值文件。"""

        if looks_generated(content) and not is_high_value_path(relative_path):
            return FilterDecision(False, "generated file")
        if not content.strip():
            return FilterDecision(False, "empty file")
        return FilterDecision(True, "content accepted")

    @staticmethod
    def looks_binary_blob(data: bytes) -> bool:
        """用轻量启发式判断字节流是否接近二进制文件。"""

        if not data:
            return False
        if b"\x00" in data[:1024]:
            return True
        sample = data[:1024]
        suspicious = 0
        for byte in sample:
            if byte < 9:
                suspicious += 1
        return suspicious > max(8, len(sample) // 10)


def looks_generated(content: str) -> bool:
    """识别常见“自动生成文件”标记。"""

    lowered = content.lower()
    markers = (
        "@generated",
        "auto-generated",
        "automatically generated",
        "do not edit",
    )
    return any(marker in lowered for marker in markers)
