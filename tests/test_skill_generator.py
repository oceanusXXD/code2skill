from __future__ import annotations

from pathlib import Path

from code2skill.models import (
    CachedFileRecord,
    FileDiffPatch,
    ProjectProfile,
    SkillBlueprint,
    SkillPlan,
    SkillPlanEntry,
    SkillRecommendation,
    SourceFileSummary,
    StateSnapshot,
)
from code2skill.skill_generator import SkillGenerator


class FakeBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self.response


def test_generate_incremental_uses_diff_and_updates_only_changed_sections(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "services").mkdir()
    (repo_path / "services" / "user_service.py").write_text(
        "def ping():\n    return 'pong-v2'\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    skill_dir = output_dir / "skills"
    skill_dir.mkdir(parents=True)
    (skill_dir / "backend-architecture.md").write_text(
        "# 后端架构\n\n"
        "## 概述\n"
        "保持不变。\n\n"
        "## 核心规则\n"
        "- 旧规则\n\n"
        "## 常见流程\n"
        "- 旧流程\n",
        encoding="utf-8",
    )

    backend = FakeBackend(
        '{"updated_sections":[{"heading":"核心规则","content":"## 核心规则\\n- 新规则：服务层返回稳定字符串。"}]}'
    )
    generator = SkillGenerator(
        backend=backend,
        repo_path=repo_path,
        output_dir=output_dir,
        max_inline_chars=4096,
    )
    plan = SkillPlan(
        skills=[
            SkillPlanEntry(
                name="backend-architecture",
                title="后端架构",
                scope="服务层",
                why="服务实现决定架构规则。",
                read_files=["app.py"],
                read_reason="入口文件。",
            )
        ]
    )
    blueprint = SkillBlueprint(
        project_profile=ProjectProfile(
            name="demo",
            repo_type="backend",
            languages=["python"],
            framework_signals=[],
            package_topology="flat",
            entrypoints=["app.py"],
        ),
        tech_stack={"language": ["python"]},
        domains=[],
        directory_summary=[],
        key_configs=[],
        core_modules=[],
        important_apis=[],
        abstract_rules=[],
        concrete_workflows=[],
        recommended_skills=[
            SkillRecommendation(
                name="backend-architecture",
                purpose="服务层规则",
                scope="服务层",
                source_evidence=["services/user_service.py"],
                why_split="服务层是主要变化点。",
                likely_inputs=[],
                likely_outputs=[],
            )
        ],
    )
    previous_state = StateSnapshot(
        version=1,
        generated_at="2026-03-16T00:00:00+00:00",
        repo_root=str(repo_path),
        head_commit="deadbeef",
        selected_paths=["services/user_service.py"],
        directory_counts={},
        gitignore_patterns=[],
        discovery_method="git",
        candidate_count=1,
        total_chars=0,
        bytes_read=0,
        files={
            "services/user_service.py": CachedFileRecord(
                path="services/user_service.py",
                sha256="old",
                size_bytes=24,
                char_count=24,
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
                    short_doc_summary="旧的 ping 实现。",
                ),
            )
        },
        reverse_dependencies={},
        skill_index={},
    )
    changed_diff = FileDiffPatch(
        path="services/user_service.py",
        change_type="modify",
        patch=(
            "diff --git a/services/user_service.py b/services/user_service.py\n"
            "--- a/services/user_service.py\n"
            "+++ b/services/user_service.py\n"
            "@@ -1 +1,2 @@\n"
            "-def ping():\n"
            "+def ping():\n"
            "+    return 'pong-v2'\n"
        ),
    )

    artifacts = generator.generate_incremental(
        blueprint=blueprint,
        plan=plan,
        affected_skill_names=["backend-architecture"],
        changed_files=["services/user_service.py"],
        changed_diffs=[changed_diff],
        previous_state=previous_state,
    )

    updated = artifacts["skills/backend-architecture.md"]
    prompt = backend.calls[0][0]

    assert "services/user_service.py" in prompt
    assert "@@ -1 +1,2 @@" in prompt
    assert "## 概述\n保持不变。" in updated
    assert "## 核心规则\n<!-- UPDATED -->\n- 新规则：服务层返回稳定字符串。" in updated
    assert "- 旧规则" not in updated
