from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .config import infer_language

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
    re.compile(r"__future__\s*\.?\s*annotations", flags=re.IGNORECASE),
    re.compile(r"\bimport(?:s|ing)?\s+path\b", flags=re.IGNORECASE),
    re.compile(r"\bpath\b.*\bimport", flags=re.IGNORECASE),
    re.compile(r"\bimport\s+order\b", flags=re.IGNORECASE),
    re.compile(r"\bempty\s+__init__\.py\b", flags=re.IGNORECASE),
]


@dataclass
class SkillDocumentSection:
    heading: str
    content: str


@dataclass
class ParsedSkillDocument:
    title: str
    preamble: str
    sections: list[SkillDocumentSection]


def parse_skill_document(markdown: str) -> ParsedSkillDocument:
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
        sections.append(SkillDocumentSection(heading="Body", content=f"## Body\n{body}".strip()))

    return ParsedSkillDocument(
        title=title,
        preamble="\n".join(preamble_lines).strip(),
        sections=sections,
    )


def apply_section_updates(
    existing_document: ParsedSkillDocument,
    updated_sections: list[object],
) -> str:
    sections = [
        SkillDocumentSection(heading=section.heading, content=section.content)
        for section in existing_document.sections
    ]
    section_index = {section.heading: index for index, section in enumerate(sections)}

    for item in updated_sections:
        if not isinstance(item, dict):
            raise RuntimeError("Each updated section must be an object.")
        heading = str(item.get("heading", "")).strip()
        content = str(item.get("content", "")).strip()
        if not heading or heading not in section_index:
            raise RuntimeError(f"Unknown section heading in incremental update: {heading}")
        sections[section_index[heading]] = SkillDocumentSection(
            heading=heading,
            content=_normalize_updated_section_content(heading=heading, content=content),
        )

    parts = [existing_document.title]
    if existing_document.preamble:
        parts.append(existing_document.preamble)
    parts.extend(section.content for section in sections if section.content)
    return sanitize_markdown("\n\n".join(part.strip() for part in parts if part.strip()))


def finalize_generated_skill(raw_markdown: str, context_files: list[dict[str, str]]) -> str:
    cleaned = sanitize_markdown(raw_markdown)
    if _has_only_grounded_code_blocks(cleaned, context_files):
        return cleaned
    return _replace_typical_patterns_section(
        markdown=cleaned,
        replacement_body=_build_grounded_typical_patterns(context_files),
    )


def sanitize_markdown(text: str) -> str:
    cleaned = textwrap.dedent(text).replace("\r\n", "\n").strip()
    cleaned = _EMOJI_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return _remove_low_value_core_rules(cleaned)


def _normalize_updated_section_content(heading: str, content: str) -> str:
    normalized = content.strip()
    expected_heading = f"## {heading}"
    if not normalized.startswith(expected_heading):
        raise RuntimeError(f"Updated section content must start with '{expected_heading}'.")
    lines = normalized.splitlines()
    if "<!-- UPDATED -->" not in normalized:
        lines.insert(1, "<!-- UPDATED -->")
    return "\n".join(lines).strip()


def _has_only_grounded_code_blocks(markdown: str, context_files: list[dict[str, str]]) -> bool:
    blocks = re.findall(r"```[^\n]*\n(.*?)```", markdown, flags=re.DOTALL)
    if not blocks:
        return True
    normalized_context = [context["content"].replace("\r\n", "\n") for context in context_files]
    for block in blocks:
        snippet = block.strip()
        if not snippet:
            continue
        if any(snippet in content for content in normalized_context):
            continue
        return False
    return True


def _replace_typical_patterns_section(markdown: str, replacement_body: str) -> str:
    document = parse_skill_document(markdown)
    sections: list[SkillDocumentSection] = []
    for section in document.sections:
        if section.heading == "Typical Patterns":
            sections.append(
                SkillDocumentSection(
                    heading=section.heading,
                    content=f"## Typical Patterns\n{replacement_body}".strip(),
                )
            )
            continue
        sections.append(section)

    parts = [document.title]
    if document.preamble:
        parts.append(document.preamble)
    parts.extend(section.content for section in sections if section.content)
    return sanitize_markdown("\n\n".join(part.strip() for part in parts if part.strip()))


def _build_grounded_typical_patterns(context_files: list[dict[str, str]]) -> str:
    snippets: list[str] = []
    for context in context_files:
        language = infer_language(Path(context["path"])) or ""
        for snippet in _extract_grounded_snippets(context["content"], language):
            fence = language if language else ""
            snippets.append(
                "\n".join([f"Source: {context['path']}", f"```{fence}", snippet, "```"])
            )
            if len(snippets) >= 3:
                return "\n\n".join(snippets)

    if snippets:
        return "\n\n".join(snippets)
    return "- [Needs confirmation] No exact grounded snippet is available in the provided context."


def _extract_grounded_snippets(content: str, language: str) -> list[str]:
    normalized = content.replace("\r\n", "\n").strip("\n")
    if not normalized:
        return []
    if language == "python":
        try:
            tree = ast.parse(normalized)
        except SyntaxError:
            return _fallback_grounded_snippets(normalized)
        lines = normalized.splitlines()
        snippets: list[str] = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            start = max(node.lineno - 1, 0)
            end = getattr(node, "end_lineno", node.lineno)
            end = min(end, start + 12)
            snippet = "\n".join(lines[start:end]).strip()
            if snippet:
                snippets.append(snippet)
            if len(snippets) >= 2:
                break
        if snippets:
            return snippets
    return _fallback_grounded_snippets(normalized)


def _fallback_grounded_snippets(content: str) -> list[str]:
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        return []
    return ["\n".join(lines[: min(len(lines), 8)])]


def _remove_low_value_core_rules(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines: list[str] = []
    in_core_rules = False
    kept_rule_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_core_rules and kept_rule_count == 0:
                cleaned_lines.append(
                    "- [Needs confirmation] The current context is not sufficient to derive high-value rules."
                )
            in_core_rules = stripped == "## Core Rules"
            if in_core_rules:
                kept_rule_count = 0
            cleaned_lines.append(line)
            continue

        if in_core_rules and stripped.startswith("- "):
            if _is_low_value_rule(stripped):
                continue
            kept_rule_count += 1

        cleaned_lines.append(line)

    if in_core_rules and kept_rule_count == 0:
        cleaned_lines.append(
            "- [Needs confirmation] The current context is not sufficient to derive high-value rules."
        )

    return "\n".join(cleaned_lines).strip() + "\n"


def _is_low_value_rule(line: str) -> bool:
    return any(pattern.search(line) for pattern in _LOW_VALUE_RULE_PATTERNS)
