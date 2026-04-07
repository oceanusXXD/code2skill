from __future__ import annotations

import json

from .models import FileDiffPatch, RuleSummary, SkillBlueprint, SkillPlanEntry, StateSnapshot
from .skill_markdown import ParsedSkillDocument


def build_default_generation_prompt(
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
    ) or "[no explicit repository rules matched]"
    rendered_files = "\n\n".join(
        [f"--- {item['path']} ---\n{item['content']}" for item in context_files]
    ) or "[no readable file context available]"

    return f"""
You are a repository standards analyst. Generate one Skill document for an AI coding assistant using only the evidence below.

Project type: {blueprint.project_profile.repo_type}
Tech stack: {json.dumps(blueprint.tech_stack, ensure_ascii=False)}
Skill name: {skill.name}
Skill title: {skill.title}
Skill scope: {skill.scope}
Why this skill exists: {skill.why}
Read-plan rationale: {skill.read_reason}

Known repository rules:
{rendered_rules}

Relevant code and skeleton context:

{rendered_files}

Hard requirements:
1. Infer only from the provided rules and file context.
2. Do not invent missing modules, frameworks, workflows, directories, design goals, or future plans.
3. Write the final Skill document in English.
4. Do not use emoji, decorative symbols, or extra headings.
5. Output exactly the 5 sections listed below and nothing else.
6. Every bullet under "Core Rules" must include a source path in the same bullet.
7. Use strong wording such as "must", "never", or "always" only when the code clearly supports it.
8. If the evidence only shows a common pattern instead of a hard rule, say so explicitly.
9. Mark uncertainty as [Needs confirmation].
10. Prefer behavior constraints, call order, module boundaries, data contracts, and extension points over style trivia.
11. Do not turn `from __future__ import annotations`, routine typing, import ordering, empty `__init__.py`, or a shared `Path` import into a rule unless it materially affects behavior.
12. Keep "Core Rules" to 4-6 high-value bullets.
13. Every code block must be copied verbatim from the provided file context. Do not simplify, abbreviate, or synthesize snippets.
14. If you cannot quote an exact code snippet from the provided context, write one bullet under "Typical Patterns": "[Needs confirmation] No exact grounded snippet is available in the provided context."

Return Markdown with exactly this structure:

# {skill.title}

## Overview
Write 1-2 sentences describing the role and importance of this area in the repository.

## Core Rules
- Use a single-level bullet list.
- Each bullet must be concrete, actionable, and include "Source: path[:symbol]".
- If a rule is only partially supported, describe the scope or mark it [Needs confirmation].
- Do not turn syntax trivia or accidental similarity into a rule.

## Typical Patterns
Show 1-3 short code snippets. Explain the source file before each snippet.

## Avoid
List only anti-patterns that can be inferred from the current code. If evidence is insufficient, write one bullet: "[Needs confirmation] The current context is not sufficient to derive a stable anti-pattern."

## Common Flows
If this area has a stable operational flow, write it step by step. Otherwise write one bullet: "[Needs confirmation] The current context does not show a stable flow."
""".strip()


def build_default_incremental_prompt(
    blueprint: SkillBlueprint,
    skill: SkillPlanEntry,
    existing_skill_md: str,
    changed_diffs: list[FileDiffPatch],
    previous_state: StateSnapshot | None,
    existing_document: ParsedSkillDocument,
) -> str:
    from .skill_generator import _load_current_context, _load_previous_context

    change_sections: list[str] = []
    for diff_entry in changed_diffs:
        before_path = diff_entry.previous_path or diff_entry.path
        before = (
            "[new file]"
            if diff_entry.change_type == "add"
            else _load_previous_context(before_path, previous_state)
        )
        if diff_entry.change_type == "delete":
            after = "[file deleted]"
        else:
            after = (
                _load_current_context(previous_state, blueprint, diff_entry.path)
                or "[current version unavailable]"
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
                    "Unified diff:",
                    diff_entry.patch.strip() or "[empty patch]",
                    "",
                    "Before:",
                    before,
                    "",
                    "After:",
                    after,
                ]
            )
        )

    return f"""
Here is the current Skill document:
{existing_skill_md}

Skill metadata:
- Name: {skill.name}
- Title: {skill.title}
- Scope: {skill.scope}
- Why it exists: {skill.why}

Existing section headings that may be updated:
{chr(10).join(f"- {section.heading}" for section in existing_document.sections) or "[none]"}

Changed files and supporting context:

{chr(10).join(change_sections)}

Repository context:
- Project type: {blueprint.project_profile.repo_type}
- Tech stack: {json.dumps(blueprint.tech_stack, ensure_ascii=False)}

Revision requirements:
1. Update only the parts justified by the supplied file changes.
2. Preserve still-valid content and remove rules that are no longer supported.
3. Do not rewrite the whole document into a new style.
4. Keep the final content in English.
5. Use [Needs confirmation] where the change makes a previous rule uncertain.
6. Use strong wording only when the changed code clearly supports it.
7. Do not add new sections or use emoji.
8. Return only the affected sections, not the full document.
9. Each section heading must come from the existing section list.

Return strict JSON:
{{
  "updated_sections": [
    {{
      "heading": "section heading",
      "content": "full section markdown that starts with ## {{heading}}"
    }}
  ]
}}
""".strip()
