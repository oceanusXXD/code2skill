from __future__ import annotations

import subprocess
from pathlib import Path

from code2skill.config import RunOptions, ScanConfig
from code2skill.core import run_ci_repository
from code2skill.models import (
    CachedFileRecord,
    ProjectProfile,
    SkillImpactIndexEntry,
    SkillPlan,
    SkillPlanEntry,
    SourceFileSummary,
    StateSnapshot,
)
from code2skill.skill_planner import render_skill_plan
from code2skill.state_store import StateStore


class FakeBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self.response


def test_run_ci_repository_uses_git_diff_for_incremental_skill_patch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "services").mkdir()
    (repo_path / "app.py").write_text(
        "from services.user_service import ping\n\n"
        "def handler():\n"
        "    return ping()\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "user_service.py").write_text(
        "def ping():\n"
        "    return 'pong-v1'\n",
        encoding="utf-8",
    )

    _git(repo_path, "init")
    _git(repo_path, "config", "user.email", "codex@example.com")
    _git(repo_path, "config", "user.name", "Codex")
    _git(repo_path, "add", ".")
    _git(repo_path, "commit", "-m", "initial")
    head_commit = _git(repo_path, "rev-parse", "HEAD").strip()

    output_dir = repo_path / ".code2skill"
    (output_dir / "skills").mkdir(parents=True)
    (output_dir / "skills" / "backend-architecture.md").write_text(
        "# 后端架构\n\n"
        "## 概述\n"
        "原有概述。\n\n"
        "## 核心规则\n"
        "- 旧规则\n",
        encoding="utf-8",
    )
    (output_dir / "skill-plan.json").write_text(
        render_skill_plan(
            SkillPlan(
                skills=[
                    SkillPlanEntry(
                        name="backend-architecture",
                        title="后端架构",
                        scope="服务层",
                        why="服务文件驱动主要行为。",
                        read_files=["app.py", "services/user_service.py"],
                        read_reason="入口与服务文件。",
                    )
                ]
            )
        ),
        encoding="utf-8",
    )
    StateStore(output_dir).save(
        StateSnapshot(
            version=1,
            generated_at="2026-03-16T00:00:00+00:00",
            repo_root=str(repo_path),
            head_commit=head_commit,
            selected_paths=["app.py", "services/user_service.py"],
            directory_counts={".": 2, "services": 1},
            gitignore_patterns=[],
            discovery_method="git",
            candidate_count=2,
            total_chars=0,
            bytes_read=0,
            files={
                "app.py": CachedFileRecord(
                    path="app.py",
                    sha256="app-old",
                    size_bytes=0,
                    char_count=0,
                    language="python",
                    inferred_role="entrypoint",
                    priority=1,
                    priority_reasons=["entrypoint"],
                    gitignored=False,
                    source_summary=SourceFileSummary(
                        path="app.py",
                        inferred_role="entrypoint",
                        language="python",
                        imports=["services.user_service"],
                        functions=["handler"],
                        short_doc_summary="应用入口。",
                    ),
                ),
                "services/user_service.py": CachedFileRecord(
                    path="services/user_service.py",
                    sha256="svc-old",
                    size_bytes=0,
                    char_count=0,
                    language="python",
                    inferred_role="service",
                    priority=1,
                    priority_reasons=["service"],
                    gitignored=False,
                    source_summary=SourceFileSummary(
                        path="services/user_service.py",
                        inferred_role="service",
                        language="python",
                        functions=["ping"],
                        short_doc_summary="旧的 ping 逻辑。",
                    ),
                ),
            },
            reverse_dependencies={
                "services/user_service.py": ["app.py"]
            },
            skill_index={
                "backend-architecture": SkillImpactIndexEntry(
                    name="backend-architecture",
                    purpose="服务层规则",
                    source_evidence=["services/user_service.py"],
                    related_paths=["app.py", "services/user_service.py"],
                )
            },
        )
    )

    (repo_path / "services" / "user_service.py").write_text(
        "def ping():\n"
        "    return 'pong-v2'\n",
        encoding="utf-8",
    )

    backend = FakeBackend(
        '{"updated_sections":[{"heading":"核心规则","content":"## 核心规则\\n- 新规则：调用服务层时保持稳定返回值。"}]}'
    )
    monkeypatch.setattr(
        "code2skill.core.build_llm_backend",
        lambda provider, model: backend,
    )

    result = run_ci_repository(
        ScanConfig(
            repo_path=repo_path,
            output_dir=output_dir,
            run=RunOptions(
                command="ci",
                mode="auto",
                llm_provider="openai",
            ),
        )
    )

    updated_skill = (output_dir / "skills" / "backend-architecture.md").read_text(
        encoding="utf-8"
    )
    prompt = backend.calls[0][0]

    assert result.run_mode == "incremental"
    assert "services/user_service.py" in result.changed_files
    assert "backend-architecture" in result.affected_skills
    assert "diff --git a/services/user_service.py b/services/user_service.py" in prompt
    assert "return 'pong-v2'" in prompt
    assert "## 概述\n原有概述。" in updated_skill
    assert "<!-- UPDATED -->" in updated_skill
    assert "新规则：调用服务层时保持稳定返回值。" in updated_skill


def _git(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout
