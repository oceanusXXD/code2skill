from __future__ import annotations

from code2skill.skill_markdown import (
    ParsedSkillDocument,
    SkillDocumentSection,
    apply_section_updates,
    finalize_generated_skill,
    parse_skill_document,
)


def test_parse_skill_document_preserves_title_preamble_and_sections() -> None:
    document = parse_skill_document(
        "# Backend Architecture\n\nPreamble text.\n\n## Overview\nOverview body.\n\n## Core Rules\n- Rule\n"
    )

    assert document.title == "# Backend Architecture"
    assert document.preamble == "Preamble text."
    assert [section.heading for section in document.sections] == ["Overview", "Core Rules"]


def test_apply_section_updates_marks_updated_sections() -> None:
    existing = ParsedSkillDocument(
        title="# Backend Architecture",
        preamble="",
        sections=[
            SkillDocumentSection("Overview", "## Overview\nKeep."),
            SkillDocumentSection("Core Rules", "## Core Rules\n- Old rule"),
        ],
    )

    updated = apply_section_updates(
        existing_document=existing,
        updated_sections=[
            {
                "heading": "Core Rules",
                "content": "## Core Rules\n- New grounded rule",
            }
        ],
    )

    assert "## Overview\nKeep." in updated
    assert "## Core Rules\n<!-- UPDATED -->\n- New grounded rule" in updated
    assert "- Old rule" not in updated


def test_finalize_generated_skill_replaces_ungrounded_typical_patterns() -> None:
    finalized = finalize_generated_skill(
        raw_markdown=(
            "# Backend Architecture\n\n"
            "## Overview\nOverview.\n\n"
            "## Core Rules\n- Keep behavior grounded.\n\n"
            "## Typical Patterns\n"
            "```python\n"
            "def invented():\n    return 'nope'\n"
            "```\n\n"
            "## Avoid\n- Avoid guesses.\n\n"
            "## Common Flows\n- Flow.\n"
        ),
        context_files=[
            {
                "path": "services/user_service.py",
                "content": "def ping():\n    return 'pong'\n",
            }
        ],
    )

    assert "def invented()" not in finalized
    assert "Source: services/user_service.py" in finalized
    assert "def ping():" in finalized
