from __future__ import annotations

import subprocess
from pathlib import Path

from .models import DiffHunk, FileDiffPatch


# 这个类只负责和 git 交互，不掺杂任何业务判断。
# 这样做有两个好处：
# 1. 仓库发现逻辑可以优先复用 git 的速度和忽略规则。
# 2. CI / 本地 / 非 git 目录的 fallback 行为更容易统一。
class GitClient:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path

    def is_repository(self) -> bool:
        result = self._run_git(["rev-parse", "--is-inside-work-tree"])
        return result.returncode == 0 and result.stdout.strip() == "true"

    def current_head(self) -> str | None:
        result = self._run_git(["rev-parse", "HEAD"])
        if result.returncode != 0:
            return None
        head = result.stdout.strip()
        return head or None

    def list_candidate_paths(self) -> list[Path]:
        result = self._run_git(
            [
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "--full-name",
            ]
        )
        if result.returncode != 0:
            return []
        return [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    def diff_paths(
        self,
        base_ref: str,
        head_ref: str = "HEAD",
        merge_base: bool = False,
    ) -> list[Path]:
        return [
            Path(item.path)
            for item in self.diff_patches(
                base_ref=base_ref,
                head_ref=head_ref,
                merge_base=merge_base,
            )
        ]

    def diff_patches(
        self,
        base_ref: str,
        head_ref: str = "HEAD",
        merge_base: bool = False,
    ) -> list[FileDiffPatch]:
        range_spec = (
            f"{base_ref}...{head_ref}"
            if merge_base
            else f"{base_ref}..{head_ref}"
        )
        return self._parse_git_diff(
            [
                "diff",
                "--no-ext-diff",
                "--no-color",
                "--unified=3",
                "--diff-filter=ACMRD",
                range_spec,
                "--",
            ]
        )

    def changed_paths_from_worktree(self, base_ref: str) -> list[Path]:
        combined = {
            Path(item.path)
            for item in self.changed_patches_from_worktree(base_ref)
        }
        return sorted(combined, key=lambda item: item.as_posix())

    def changed_patches_from_worktree(self, base_ref: str) -> list[FileDiffPatch]:
        tracked = self._parse_git_diff(
            [
                "diff",
                "--no-ext-diff",
                "--no-color",
                "--unified=3",
                base_ref,
                "--",
            ]
        )
        tracked_paths = {item.path for item in tracked}
        untracked = [
            _build_untracked_patch(path, self.repo_path / path)
            for path in self.untracked_paths()
            if path.as_posix() not in tracked_paths
        ]
        return sorted(
            [*tracked, *untracked],
            key=lambda item: item.path,
        )

    def untracked_paths(self) -> list[Path]:
        result = self._run_git(
            [
                "ls-files",
                "--others",
                "--exclude-standard",
                "--full-name",
            ]
        )
        if result.returncode != 0:
            return []
        return [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    def _name_only(self, args: list[str]) -> list[Path]:
        result = self._run_git(args)
        if result.returncode != 0:
            return []
        return [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip()
        ]

    def _parse_git_diff(self, args: list[str]) -> list[FileDiffPatch]:
        result = self._run_git(args)
        if result.returncode != 0:
            return []
        return parse_unified_diff(result.stdout)

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            text=True,
            capture_output=True,
            check=False,
        )


def parse_unified_diff(raw: str) -> list[FileDiffPatch]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        blocks.append(current)

    parsed: list[FileDiffPatch] = []
    for block in blocks:
        patch = _parse_diff_block(block)
        if patch is not None:
            parsed.append(patch)
    return parsed


def _parse_diff_block(lines: list[str]) -> FileDiffPatch | None:
    old_path: str | None = None
    new_path: str | None = None
    change_type = "modify"
    hunks: list[DiffHunk] = []
    current_hunk_header: str | None = None
    current_hunk_lines: list[str] = []

    for line in lines:
        if line.startswith("rename from "):
            old_path = line.removeprefix("rename from ").strip()
        elif line.startswith("rename to "):
            new_path = line.removeprefix("rename to ").strip()
        elif line.startswith("new file mode "):
            change_type = "add"
        elif line.startswith("deleted file mode "):
            change_type = "delete"
        elif line.startswith("--- "):
            old_path = _normalize_patch_path(line.removeprefix("--- "))
        elif line.startswith("+++ "):
            new_path = _normalize_patch_path(line.removeprefix("+++ "))
        elif line.startswith("@@"):
            if current_hunk_header is not None:
                hunks.append(
                    DiffHunk(
                        header=current_hunk_header,
                        lines=current_hunk_lines,
                    )
                )
            current_hunk_header = line
            current_hunk_lines = [line]
        elif current_hunk_header is not None:
            current_hunk_lines.append(line)

    if current_hunk_header is not None:
        hunks.append(
            DiffHunk(
                header=current_hunk_header,
                lines=current_hunk_lines,
            )
        )

    if old_path == "/dev/null":
        old_path = None
    if new_path == "/dev/null":
        new_path = None
    if change_type == "modify" and old_path and new_path and old_path != new_path:
        change_type = "rename"

    path = new_path or old_path
    if not path:
        return None

    previous_path = None
    if old_path and old_path != path:
        previous_path = old_path

    return FileDiffPatch(
        path=path,
        previous_path=previous_path,
        change_type=change_type,
        patch="\n".join(lines).rstrip() + "\n",
        hunks=hunks,
    )


def _normalize_patch_path(value: str) -> str | None:
    cleaned = value.strip().split("\t", 1)[0]
    if cleaned == "/dev/null":
        return "/dev/null"
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        return cleaned[2:]
    return cleaned or None


def _build_untracked_patch(relative_path: Path, absolute_path: Path) -> FileDiffPatch:
    content = absolute_path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    hunk_header = f"@@ -0,0 +1,{len(lines)} @@"
    hunk_lines = [hunk_header, *[f"+{line}" for line in lines]]
    patch_lines = [
        f"diff --git a/{relative_path.as_posix()} b/{relative_path.as_posix()}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{relative_path.as_posix()}",
        *hunk_lines,
    ]
    return FileDiffPatch(
        path=relative_path.as_posix(),
        previous_path=None,
        change_type="add",
        patch="\n".join(patch_lines).rstrip() + "\n",
        hunks=[
            DiffHunk(
                header=hunk_header,
                lines=hunk_lines,
            )
        ],
    )
