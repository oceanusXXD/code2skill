from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import infer_language
from .extractors.config_extractor import ConfigExtractor
from .extractors.python_extractor import PythonExtractor
from .json_utils import parse_json_object
from .llm_backend import LLMBackend
from .models import (
    CachedFileRecord,
    ConfigSummary,
    FileCandidate,
    FileDiffPatch,
    RuleSummary,
    SkillBlueprint,
    SkillPlan,
    SkillPlanEntry,
    SkillRecommendation,
    SourceFileSummary,
    StateSnapshot,
)
from .scanner.prioritizer import FilePrioritizer


SKILL_SYSTEM = (
    "你是一个严格的项目规范分析器。"
    "你只能根据给出的代码、骨架摘要和规则生成 Skill 文档。"
    "默认使用中文，不要使用 emoji，不要补造不存在的模块、框架、语言、流程、未来计划或最佳实践。"
)
INCREMENTAL_SYSTEM = (
    "你是一个严格的项目规范分析器。"
    "你要根据变更内容修订现有 Skill 文档，不保留已经失效的规则。"
    "默认使用中文，不要使用 emoji，不要补造上下文中没有的内容。"
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
_LOW_VALUE_RULE_PATTERNS = [
    re.compile(r"from __future__ import annotations", flags=re.IGNORECASE),
    re.compile(r"导入\s+`?Path`?", flags=re.IGNORECASE),
    re.compile(r"import\s+`?Path`?", flags=re.IGNORECASE),
    re.compile(r"import\s+排序", flags=re.IGNORECASE),
    re.compile(r"导入顺序", flags=re.IGNORECASE),
]

try:
    CODE2SKILL_VERSION = version("code2skill")
except PackageNotFoundError:
    CODE2SKILL_VERSION = "0.3.0"


@dataclass
class SkillDocumentSection:
    heading: str
    content: str


@dataclass
class ParsedSkillDocument:
    title: str
    preamble: str
    sections: list[SkillDocumentSection]


class SkillGenerator:
    def __init__(
        self,
        backend: LLMBackend,
        repo_path: Path,
        output_dir: Path,
        max_inline_chars: int,
    ) -> None:
        self.backend = backend
        self.repo_path = repo_path
        self.output_dir = output_dir
        self.max_inline_chars = max_inline_chars
        self.config_extractor = ConfigExtractor()
        self.python_extractor = PythonExtractor()
        self.prioritizer = FilePrioritizer()

    def generate_all(
        self,
        blueprint: SkillBlueprint,
        plan: SkillPlan,
    ) -> dict[str, str]:
        artifacts: dict[str, str] = {}
        for skill in plan.skills:
            artifacts[f"skills/{skill.name}.md"] = self._generate_skill(
                blueprint=blueprint,
                skill=skill,
            )
        artifacts["skills/index.md"] = render_skill_index(plan)
        return artifacts

    def generate_incremental(
        self,
        blueprint: SkillBlueprint,
        plan: SkillPlan,
        affected_skill_names: list[str],
        changed_files: list[str],
        changed_diffs: list[FileDiffPatch],
        previous_state: StateSnapshot | None,
    ) -> dict[str, str]:
        affected = set(affected_skill_names)
        changed = set(changed_files)
        changed_by_path = {
            item.path: item
            for item in changed_diffs
        }
        recommendations = {
            item.name: item
            for item in blueprint.recommended_skills
        }
        artifacts: dict[str, str] = {}

        for skill in plan.skills:
            if skill.name not in affected:
                continue
            skill_path = self.output_dir / "skills" / f"{skill.name}.md"
            relevant_diffs = self._collect_relevant_diffs(
                skill=skill,
                recommendation=recommendations.get(skill.name),
                changed_files=changed,
                changed_by_path=changed_by_path,
            )
            if skill_path.exists() and relevant_diffs:
                artifacts[f"skills/{skill.name}.md"] = self._update_skill(
                    blueprint=blueprint,
                    skill=skill,
                    existing_skill_md=skill_path.read_text(encoding="utf-8"),
                    changed_diffs=relevant_diffs,
                    previous_state=previous_state,
                )
                continue
            artifacts[f"skills/{skill.name}.md"] = self._generate_skill(
                blueprint=blueprint,
                skill=skill,
            )

        if artifacts:
            artifacts["skills/index.md"] = render_skill_index(plan)
        return artifacts

    def _collect_relevant_diffs(
        self,
        skill: SkillPlanEntry,
        recommendation: SkillRecommendation | None,
        changed_files: set[str],
        changed_by_path: dict[str, FileDiffPatch],
    ) -> list[FileDiffPatch]:
        relevant_paths: list[str] = []
        seen: set[str] = set()
        candidate_paths = [
            *skill.read_files,
            *(recommendation.source_evidence if recommendation else []),
        ]
        for path in candidate_paths:
            if path not in changed_files or path in seen:
                continue
            diff_entry = changed_by_path.get(path)
            if diff_entry is None:
                continue
            relevant_paths.append(path)
            seen.add(path)

        if relevant_paths:
            return [changed_by_path[path] for path in relevant_paths]

        return [
            changed_by_path[path]
            for path in sorted(changed_files)
            if path in changed_by_path
        ]

    def _generate_skill(
        self,
        blueprint: SkillBlueprint,
        skill: SkillPlanEntry,
    ) -> str:
        context_files = [
            entry
            for path in skill.read_files
            if (entry := self._load_file_context(path)) is not None
        ]
        relevant_rules = filter_rules_by_skill(blueprint.abstract_rules, skill)
        prompt = self._build_generation_prompt(
            blueprint=blueprint,
            skill=skill,
            context_files=context_files,
            relevant_rules=relevant_rules,
        )
        raw = self.backend.complete(prompt=prompt, system=SKILL_SYSTEM)
        return _sanitize_markdown(raw)

    def _update_skill(
        self,
        blueprint: SkillBlueprint,
        skill: SkillPlanEntry,
        existing_skill_md: str,
        changed_diffs: list[FileDiffPatch],
        previous_state: StateSnapshot | None,
    ) -> str:
        existing_document = _parse_skill_document(existing_skill_md)
        change_sections: list[str] = []
        for diff_entry in changed_diffs:
            before_path = diff_entry.previous_path or diff_entry.path
            before = (
                "[新增文件]"
                if diff_entry.change_type == "add"
                else self._load_previous_context(before_path, previous_state)
            )
            after = (
                None
                if diff_entry.change_type == "delete"
                else self._load_file_context(diff_entry.path)
            )
            metadata = [
                f"--- {diff_entry.path} ---",
                f"change_type: {diff_entry.change_type}",
            ]
            if diff_entry.previous_path is not None:
                metadata.append(f"previous_path: {diff_entry.previous_path}")
            change_sections.append(
                "\n".join(
                    [
                        *metadata,
                        "统一 diff：",
                        diff_entry.patch.strip() or "[空补丁]",
                        "",
                        "变更前骨架：",
                        before,
                        "",
                        "变更后骨架：",
                        after["content"] if after is not None else "[文件已删除]",
                    ]
                )
            )

        prompt = f"""
以下是该 Skill 当前的内容：
{existing_skill_md}

Skill 元信息：
- 名称: {skill.name}
- 标题: {skill.title}
- 范围: {skill.scope}
- 规划原因: {skill.why}

当前可更新的 section 标题：
{chr(10).join(f"- {section.heading}" for section in existing_document.sections) or "[无可用 section]"}

以下文件发生了变更：

{chr(10).join(change_sections)}

已知项目上下文：
- 项目类型: {blueprint.project_profile.repo_type}
- 技术栈: {json.dumps(blueprint.tech_stack, ensure_ascii=False)}

修订要求：
1. 只根据当前 Skill 内容和上述变更文件修订，不要重写成全新的文档风格
2. 只修改受到变更影响的规则、流程、示例和反模式
3. 保留仍然有效的内容，删除已经失效的规则
4. 无法确认是否仍然成立的地方，写成 [待确认]
5. 只有代码明确体现时，才使用“必须”“禁止”“统一”等强措辞
6. 优先保留行为约束、调用顺序、扩展点、数据契约，不要把语法习惯或偶然共性升级为规则
7. 不要增加额外章节，不要使用 emoji，不要加入未来计划、扩展建议、总结
7. 只返回受到影响的 section，不要返回完整文档
8. section 标题必须来自现有 section 列表

输出严格 JSON：
{{
  "updated_sections": [
    {{
      "heading": "section 标题",
      "content": "完整 section Markdown，必须以 ## {{heading}} 开头"
    }}
  ]
}}
""".strip()
        raw = self.backend.complete(prompt=prompt, system=INCREMENTAL_SYSTEM)
        payload = parse_json_object(
            raw,
            error_context="Incremental skill update response was not valid JSON",
            backend=self.backend,
            expected_top_level_key="updated_sections",
            repair_hint=(
                "输出必须是 {\"updated_sections\": [...]} 结构；"
                "每个 section 项保留 heading 和 content。"
            ),
        )
        updated_sections = payload.get("updated_sections", [])
        if not isinstance(updated_sections, list):
            raise RuntimeError("Incremental skill update payload must contain a list.")
        return _apply_section_updates(
            existing_document=existing_document,
            updated_sections=updated_sections,
        )

    def _build_generation_prompt(
        self,
        blueprint: SkillBlueprint,
        skill: SkillPlanEntry,
        context_files: list[dict[str, str]],
        relevant_rules: list[RuleSummary],
    ) -> str:
        rendered_rules = "\n".join(
            [
                (
                    f"- {rule.name}: {rule.rule} "
                    f"(confidence={rule.confidence:.0%}; source={rule.source}; "
                    f"evidence={', '.join(rule.evidence) or '[none]'})"
                )
                for rule in relevant_rules
            ]
        ) or "[未匹配到明确规则]"
        rendered_files = "\n\n".join(
            [
                f"--- {item['path']} ---\n{item['content']}"
                for item in context_files
            ]
        ) or "[没有可用的关键文件内容]"

        return f"""
你是一个项目规范分析器。根据以下代码文件，生成一份供 AI 编程助手消费的 Skill 规范文档。

项目类型: {blueprint.project_profile.repo_type}
技术栈: {json.dumps(blueprint.tech_stack, ensure_ascii=False)}
Skill 名称: {skill.name}
Skill 标题: {skill.title}
此 Skill 聚焦: {skill.scope}
为什么需要它: {skill.why}
阅读计划说明: {skill.read_reason}

已知的结构性规则：
{rendered_rules}

以下是此领域的关键代码文件：

{rendered_files}

写作硬约束：
1. 只基于上面的规则和文件内容推断，不要编造不存在的模式、框架、目录、设计目标或未来规划
2. 默认使用中文，保留英文代码标识符、路径、类名、函数名
3. 不要使用 emoji、勾选符号或装饰性标记
4. 不要输出额外章节；只允许输出下面列出的 5 个章节
5. 每条“核心规则”都必须带来源文件路径；如果能定位到类、函数或符号，直接写出符号名
6. 只有在代码明确体现时，才使用“必须”“禁止”“统一”“总是”等强措辞
7. 如果只能看出“当前常见写法”，请明确写成“当前样例显示”“现有实现通常”“倾向于”，不要上升为硬约束
8. 如果证据不足，请明确标注 [待确认]
9. 不要复述通用工程最佳实践；只写这个仓库已经体现出来的做法
10. 不要引入当前上下文中没有出现的技术名词或框架名
11. 核心规则优先提炼行为边界、调用顺序、模块边界、数据契约、扩展点
12. 不要把 `from __future__ import annotations`、普通类型注解、常规 import 排序、空的 `__init__.py`、文件恰好都导入 `Path` 这类表面共性写成核心规则，除非它直接影响行为或扩展接口
13. 核心规则控制在 4-6 条，宁缺毋滥

请生成 Markdown 格式的 Skill 文档，严格使用以下结构：

# {skill.title}

## 概述
1-2 句话说明这个领域在项目中的角色和重要性。

## 核心规则
- 使用单层列表
- 每条规则必须具体、可执行，并在同一条中写明“来源: 路径[:符号]”
- 如果某条规则只被部分样例支持，要写清楚适用范围或标记 [待确认]
- 不要把纯语法、纯格式或偶然共性写成规则

## 典型模式
用 1-3 个短代码片段展示标准写法，并在片段前说明来源文件。

## 避免的写法
只写能从当前代码推断出的反模式；如果证据不足，写一条 “[待确认] 当前上下文不足以稳定归纳反模式”。

## 常见流程
如果该领域有固定操作步骤，写成 step-by-step；如果没有稳定流程，写一条 “[待确认] 当前上下文没有显示稳定流程”。
""".strip()

    def _load_file_context(self, relative_path: str) -> dict[str, str] | None:
        absolute_path = self.repo_path / Path(relative_path)
        if not absolute_path.exists() or not absolute_path.is_file():
            return None
        content = absolute_path.read_text(encoding="utf-8", errors="ignore")
        if len(content) <= self.max_inline_chars:
            return {"path": relative_path, "content": content}
        return {
            "path": relative_path,
            "content": self._build_skeleton_from_content(relative_path, content),
        }

    def _load_previous_context(
        self,
        relative_path: str,
        previous_state: StateSnapshot | None,
    ) -> str:
        if previous_state is None:
            return "[历史版本不可用]"
        record = previous_state.files.get(relative_path)
        if record is None:
            return "[历史版本不可用]"
        if record.config_summary is not None:
            return _render_config_summary(record.config_summary)
        if record.source_summary is not None:
            return _render_source_summary(record.source_summary)
        return "[历史版本不可用]"

    def _build_skeleton_from_content(self, relative_path: str, content: str) -> str:
        relative = Path(relative_path)
        language = infer_language(relative)
        _, reasons, role = self.prioritizer.score(relative, language)
        candidate = FileCandidate(
            absolute_path=self.repo_path / relative,
            relative_path=relative,
            size_bytes=len(content.encode("utf-8")),
            char_count=len(content),
            sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            language=language,
            inferred_role=role,
            priority=0,
            priority_reasons=reasons,
            content=content,
            gitignored=False,
        )

        config_summary = self.config_extractor.extract(candidate)
        if config_summary is not None:
            return _render_config_summary(config_summary)
        if language == "python":
            return _render_source_summary(self.python_extractor.extract(candidate))
        return content[: self.max_inline_chars]


def match_planned_skills(affected_files: list[str], plan: SkillPlan) -> list[str]:
    affected = set(affected_files)
    matched = [
        skill.name
        for skill in plan.skills
        if affected & set(skill.read_files)
    ]
    return matched


def filter_rules_by_skill(
    abstract_rules: list[RuleSummary],
    skill: SkillPlanEntry,
) -> list[RuleSummary]:
    tokens = _tokenize(
        " ".join(
            [
                skill.name,
                skill.title,
                skill.scope,
                skill.why,
                " ".join(skill.read_files),
            ]
        )
    )
    scored: list[tuple[int, RuleSummary]] = []
    for rule in abstract_rules:
        score = 0
        evidence = set(rule.evidence)
        if evidence & set(skill.read_files):
            score += 5
        rule_tokens = _tokenize(" ".join([rule.name, rule.rule, rule.rationale]))
        score += len(tokens & rule_tokens)
        score += int(rule.confidence * 3)
        if score > 0:
            scored.append((score, rule))

    if not scored:
        return abstract_rules[:5]
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1].confidence,
            item[1].name,
        )
    )
    return [rule for _, rule in scored[:8]]


def render_skill_index(plan: SkillPlan) -> str:
    rows = "\n".join(
        [
            f"| {skill.title} | {skill.scope or '-'} | [{skill.name}.md](./{skill.name}.md) |"
            for skill in plan.skills
        ]
    )
    return f"""# 项目 Skill 索引

| Skill | 范围 | 文件 |
|---|---|---|
{rows}

生成时间: {datetime.now(timezone.utc).isoformat()}
生成工具: code2skill v{CODE2SKILL_VERSION}
""".strip() + "\n"


def _parse_skill_document(markdown: str) -> ParsedSkillDocument:
    stripped = markdown.strip()
    if not stripped:
        raise RuntimeError("Existing skill document is empty.")

    lines = stripped.splitlines()
    title = lines[0].strip()
    if not title.startswith("# "):
        raise RuntimeError("Existing skill document must start with a level-1 heading.")

    preamble_lines: list[str] = []
    sections: list[SkillDocumentSection] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines[1:]:
        if line.startswith("## "):
            if current_heading is not None:
                sections.append(
                    SkillDocumentSection(
                        heading=current_heading,
                        content="\n".join(current_lines).strip(),
                    )
                )
            current_heading = line[3:].strip()
            current_lines = [line]
            continue

        if current_heading is None:
            preamble_lines.append(line)
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append(
            SkillDocumentSection(
                heading=current_heading,
                content="\n".join(current_lines).strip(),
            )
        )

    if not sections:
        body = "\n".join(lines[1:]).strip()
        sections.append(
            SkillDocumentSection(
                heading="正文",
                content=f"## 正文\n{body}".strip(),
            )
        )

    return ParsedSkillDocument(
        title=title,
        preamble="\n".join(preamble_lines).strip(),
        sections=sections,
    )


def _apply_section_updates(
    existing_document: ParsedSkillDocument,
    updated_sections: list[object],
) -> str:
    sections = [
        SkillDocumentSection(
            heading=section.heading,
            content=section.content,
        )
        for section in existing_document.sections
    ]
    section_index = {
        section.heading: index
        for index, section in enumerate(sections)
    }

    for item in updated_sections:
        if not isinstance(item, dict):
            raise RuntimeError("Each updated section must be an object.")
        heading = str(item.get("heading", "")).strip()
        content = str(item.get("content", "")).strip()
        if not heading or heading not in section_index:
            raise RuntimeError(f"Unknown section heading in incremental update: {heading}")
        sections[section_index[heading]] = SkillDocumentSection(
            heading=heading,
            content=_normalize_updated_section_content(
                heading=heading,
                content=content,
            ),
        )

    parts = [existing_document.title]
    if existing_document.preamble:
        parts.append(existing_document.preamble)
    parts.extend(section.content for section in sections if section.content)
    return _sanitize_markdown(
        "\n\n".join(part.strip() for part in parts if part.strip())
    )


def _normalize_updated_section_content(heading: str, content: str) -> str:
    normalized = content.strip()
    expected_heading = f"## {heading}"
    if not normalized.startswith(expected_heading):
        raise RuntimeError(
            f"Updated section content must start with '{expected_heading}'."
        )
    lines = normalized.splitlines()
    if "<!-- UPDATED -->" not in normalized:
        lines.insert(1, "<!-- UPDATED -->")
    return "\n".join(lines).strip()


def _render_config_summary(summary: ConfigSummary) -> str:
    details = json.dumps(summary.details, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            f"[CONFIG SKELETON] {summary.path}",
            f"kind: {summary.kind}",
            f"summary: {summary.summary}",
            f"framework_signals: {', '.join(summary.framework_signals) or '-'}",
            f"entrypoints: {', '.join(summary.entrypoints) or '-'}",
            "details:",
            details,
        ]
    )


def _render_source_summary(summary: SourceFileSummary) -> str:
    route_lines = [
        f"- {route.method} {route.path} -> {route.handler} ({route.framework})"
        for route in summary.routes
    ]
    return "\n".join(
        [
            f"[SOURCE SKELETON] {summary.path}",
            f"role: {summary.inferred_role}",
            f"language: {summary.language or '-'}",
            f"summary: {summary.short_doc_summary}",
            f"imports: {', '.join(summary.imports) or '-'}",
            f"exports: {', '.join(summary.exports) or '-'}",
            f"classes: {', '.join(summary.classes) or '-'}",
            f"functions: {', '.join(summary.functions) or '-'}",
            f"methods: {', '.join(summary.methods) or '-'}",
            f"models_or_schemas: {', '.join(summary.models_or_schemas) or '-'}",
            f"state_signals: {', '.join(summary.state_signals) or '-'}",
            "routes:",
        ]
        + (route_lines or ["-"])
        + [
            f"notes: {', '.join(summary.notes) or '-'}",
        ]
    )


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-zA-Z0-9_/.-]+", text.lower())
        if token
    }


def _sanitize_markdown(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").strip()
    cleaned = _EMOJI_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return _remove_low_value_core_rules(cleaned)


def _remove_low_value_core_rules(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines: list[str] = []
    in_core_rules = False
    kept_rule_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_core_rules and kept_rule_count == 0:
                cleaned_lines.append("- [待确认] 当前上下文不足以稳定提炼高价值规则")
            in_core_rules = stripped == "## 核心规则"
            kept_rule_count = 0 if in_core_rules else kept_rule_count
            cleaned_lines.append(line)
            continue

        if in_core_rules and stripped.startswith("- "):
            if _is_low_value_rule(stripped):
                continue
            kept_rule_count += 1

        cleaned_lines.append(line)

    if in_core_rules and kept_rule_count == 0:
        cleaned_lines.append("- [待确认] 当前上下文不足以稳定提炼高价值规则")

    return "\n".join(cleaned_lines).strip() + "\n"


def _is_low_value_rule(line: str) -> bool:
    return any(pattern.search(line) for pattern in _LOW_VALUE_RULE_PATTERNS)
