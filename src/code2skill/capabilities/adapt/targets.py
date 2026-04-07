from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetDefinition:
    name: str
    mode: str
    destination: str


TARGET_DEFINITIONS = {
    "cursor": TargetDefinition(name="cursor", mode="copy", destination=".cursor/rules/"),
    "claude": TargetDefinition(name="claude", mode="merge", destination="CLAUDE.md"),
    "codex": TargetDefinition(name="codex", mode="merge", destination="AGENTS.md"),
    "copilot": TargetDefinition(
        name="copilot",
        mode="merge",
        destination=".github/copilot-instructions.md",
    ),
    "windsurf": TargetDefinition(name="windsurf", mode="merge", destination=".windsurfrules"),
}


def get_target_definition(name: str) -> TargetDefinition:
    return TARGET_DEFINITIONS[name]


def get_target_definitions(target: str) -> list[TargetDefinition]:
    if target == "all":
        return [TARGET_DEFINITIONS[name] for name in TARGET_DEFINITIONS]
    return [get_target_definition(target)]
