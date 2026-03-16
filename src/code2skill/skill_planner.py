from __future__ import annotations

import json
import re
from pathlib import Path

from .json_utils import parse_json_object
from .llm_backend import LLMBackend
from .models import SkillBlueprint, SkillPlan, SkillPlanEntry


PLANNER_SYSTEM = (
    "你是一个严谨的项目分析器。"
    "你只能根据给定的结构摘要规划 Skill。"
    "不要补造不存在的模块、框架、语言、流程或未来规划。"
    "默认使用中文，不要使用 emoji。"
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\uFE0F"
    "]",
    flags=re.UNICODE,
)


class SkillPlanner:
    def __init__(self, backend: LLMBackend, max_skills: int = 8) -> None:
        self.backend = backend
        self.max_skills = max_skills

    def plan(self, blueprint: SkillBlueprint, repo_path: Path) -> SkillPlan:
        prompt = self._build_prompt(blueprint)
        raw = self.backend.complete(prompt=prompt, system=PLANNER_SYSTEM)
        payload = parse_json_object(
            raw,
            error_context="Skill planner response was not valid JSON",
            backend=self.backend,
            expected_top_level_key="skills",
            repair_hint=(
                "输出必须是 {\"skills\": [...]} 结构；"
                "skills 中的每一项保留 name/title/scope/why/read_files/read_reason。"
            ),
        )

        normalized: list[SkillPlanEntry] = []
        for item in payload.get("skills", [])[: self.max_skills]:
            if not isinstance(item, dict):
                continue
            read_files = _normalize_read_files(
                item.get("read_files", []),
                repo_path=repo_path,
                limit=10,
            )
            normalized.append(
                SkillPlanEntry(
                    name=_to_kebab_case(str(item.get("name", "unnamed-skill"))),
                    title=_sanitize_plain_text(str(item.get("title", ""))) or "未命名 Skill",
                    scope=_sanitize_plain_text(str(item.get("scope", ""))),
                    why=_sanitize_plain_text(str(item.get("why", ""))),
                    read_files=read_files,
                    read_reason=_sanitize_plain_text(str(item.get("read_reason", ""))),
                )
            )

        deduped: list[SkillPlanEntry] = []
        seen: set[str] = set()
        for item in normalized:
            if not item.name or item.name in seen:
                continue
            seen.add(item.name)
            deduped.append(item)

        if not deduped:
            raise RuntimeError("Skill planner did not return any valid skills.")

        return SkillPlan(skills=deduped)

    def _build_prompt(self, blueprint: SkillBlueprint) -> str:
        project_profile_text = "\n".join(
            [
                f"- 名称: {blueprint.project_profile.name}",
                f"- 类型: {blueprint.project_profile.repo_type}",
                f"- 语言: {', '.join(blueprint.project_profile.languages) or '[未检测到]'}",
                f"- 框架信号: {', '.join(blueprint.project_profile.framework_signals) or '[未检测到]'}",
                f"- 包结构: {blueprint.project_profile.package_topology}",
                f"- 入口文件: {', '.join(blueprint.project_profile.entrypoints) or '[未检测到]'}",
            ]
        )
        tech_stack_list = _render_tech_stack(blueprint.tech_stack)
        domains_text = "\n".join(
            [
                f"- {domain.name}: {domain.summary} | evidence={', '.join(domain.evidence[:4]) or '[none]'}"
                for domain in blueprint.domains[:8]
            ]
        ) or "[未检测到领域摘要]"
        directory_summary_text = "\n".join(
            [
                (
                    f"- {item.path}: {item.file_count} files; "
                    f"roles={', '.join(item.dominant_roles) or '[unknown]'}; "
                    f"samples={', '.join(item.sample_files) or '[none]'}"
                )
                for item in blueprint.directory_summary[:16]
            ]
        ) or "[未检测到目录摘要]"
        key_configs_text = "\n".join(
            [
                (
                    f"- {item.path} [{item.kind}] summary={item.summary}; "
                    f"frameworks={', '.join(item.framework_signals[:4]) or '-'}; "
                    f"entrypoints={', '.join(item.entrypoints[:4]) or '-'}"
                )
                for item in blueprint.key_configs[:10]
            ]
        ) or "[未检测到关键配置]"
        core_modules_list = "\n".join(
            [
                (
                    f"- {module.path} [{module.inferred_role}] "
                    f"deps={', '.join(module.internal_dependencies[:4]) or '-'}; "
                    f"symbols={', '.join((module.classes + module.functions)[:6]) or '-'}; "
                    f"summary={module.short_doc_summary or '[none]'}"
                )
                for module in blueprint.core_modules[:16]
            ]
        ) or "[未检测到核心模块]"
        abstract_rules_text = "\n".join(
            [
                (
                    f"- {rule.name}: {rule.rule} "
                    f"(confidence={rule.confidence:.0%}; source={rule.source}; "
                    f"evidence={', '.join(rule.evidence[:3]) or '[none]'})"
                )
                for rule in blueprint.abstract_rules[:12]
            ]
        ) or "[未检测到稳定规则]"
        workflow_text = "\n".join(
            [
                (
                    f"- {workflow.name}: {workflow.summary} | "
                    f"steps={'; '.join(workflow.steps[:4]) or '[none]'} | "
                    f"evidence={', '.join(workflow.evidence[:4]) or '[none]'}"
                )
                for workflow in blueprint.concrete_workflows[:8]
            ]
        ) or "[未检测到稳定流程]"
        import_graph_text = _render_import_graph(blueprint)
        recommended_skills_text = "\n".join(
            [
                f"- {skill.name}: {skill.scope} | evidence={', '.join(skill.source_evidence[:4]) or '[none]'}"
                for skill in blueprint.recommended_skills[:8]
            ]
        ) or "[无启发式推荐]"

        return f"""
你是一个项目分析器。根据以下项目结构摘要，决定应该生成哪些 Skill 文件。

输出语言要求：
1. 默认使用中文描述
2. 保留英文代码标识符、路径、类名、函数名
3. 不要使用 emoji

项目信息：
{project_profile_text}

技术栈：{tech_stack_list}

领域摘要：
{domains_text}

目录结构（含文件数和角色标签）：
{directory_summary_text}

关键配置：
{key_configs_text}

依赖关系摘要：
{import_graph_text}

高价值文件：
{core_modules_list}

已检测到的结构模式：
{abstract_rules_text}

已检测到的固定流程：
{workflow_text}

启发式推荐（低优先级参考，不要盲从）：
{recommended_skills_text}

强约束：
1. 只能基于输入中出现的证据规划 Skill
2. 不要补造不存在的模块、框架、语言、分层或未来扩展方向
3. 如果证据不足，宁可少生成 Skill，也不要为了凑数量强行拆分
4. Skill 数量通常 2-6 个，最多 {self.max_skills} 个
5. 每个 Skill 只聚焦一个明确领域，不要大而全
6. 为每个 Skill 选出最多 10 个需要阅读的关键文件
7. 优先按包边界、目录边界、依赖簇、稳定流程来拆 Skill，而不是按空泛概念命名
8. 优先选择入口文件、核心模型、配置文件、典型服务或分析器
9. 同类文件只选 1-2 个典型样例，不需要全读
10. 如果多个候选 Skill 依赖高度重叠，应合并而不是拆散
11. 除非文件明确支持一个独立子系统，否则不要生成类似“通用架构”“领域建模”这种过泛 Skill
12. Skill 名称必须使用 kebab-case
13. `scope`、`why`、`read_reason` 必须尽量体现证据来源，不写空泛措辞
14. 测试相关 Skill 默认次要，只有当测试目录规模明显、存在共享 fixture/测试基础设施、或测试本身就是仓库的重要子系统时才生成

输出严格 JSON 格式：
{{
  "skills": [
    {{
      "name": "string, kebab-case 文件名",
      "title": "string, 中文标题",
      "scope": "string, 覆盖范围描述",
      "why": "string, 为什么需要这个 skill",
      "read_files": ["string, 文件路径"],
      "read_reason": "string, 为什么选这些文件"
    }}
  ]
}}
""".strip()


def load_skill_plan(path: Path) -> SkillPlan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    skills = [
        SkillPlanEntry(
            name=str(item["name"]),
            title=str(item["title"]),
            scope=str(item.get("scope", "")),
            why=str(item.get("why", "")),
            read_files=list(item.get("read_files", [])),
            read_reason=str(item.get("read_reason", "")),
        )
        for item in payload.get("skills", [])
    ]
    return SkillPlan(skills=skills)


def render_skill_plan(plan: SkillPlan) -> str:
    return json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)


def _render_tech_stack(tech_stack: dict[str, object]) -> str:
    parts: list[str] = []
    for key, value in tech_stack.items():
        if isinstance(value, list):
            display = ", ".join(str(item) for item in value) or "[empty]"
        elif isinstance(value, dict):
            display = ", ".join(
                f"{nested_key}={nested_value}"
                for nested_key, nested_value in value.items()
            ) or "[empty]"
        else:
            display = str(value)
        parts.append(f"{key}: {display}")
    return "; ".join(parts) or "[未检测到]"


def _normalize_read_files(
    raw_paths: object,
    repo_path: Path,
    limit: int,
) -> list[str]:
    if not isinstance(raw_paths, list):
        return []
    normalized: list[str] = []
    for item in raw_paths:
        value = str(item).strip().replace("\\", "/").removeprefix("./")
        if not value:
            continue
        candidate = repo_path / Path(value)
        if not candidate.exists() or not candidate.is_file():
            continue
        normalized.append(Path(value).as_posix())

    deduped: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:limit]


def _to_kebab_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "unnamed-skill"


def _sanitize_plain_text(value: str) -> str:
    value = _EMOJI_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _render_import_graph(blueprint: SkillBlueprint) -> str:
    stats = blueprint.import_graph_stats
    if stats is None:
        return "[未检测到内部依赖图]"

    cluster_lines = [
        f"  - {cluster.name}: {len(cluster.files)} files; examples={', '.join(cluster.files[:4])}"
        for cluster in stats.clusters[:6]
    ]
    lines = [
        f"- hub_files: {', '.join(stats.hub_files[:8]) or '[none]'}",
        f"- entry_points: {', '.join(stats.entry_points[:8]) or '[none]'}",
        f"- total_internal_edges: {stats.total_internal_edges}",
        f"- clusters:",
        *(cluster_lines or ["  - [none]"]),
    ]
    return "\n".join(lines)
