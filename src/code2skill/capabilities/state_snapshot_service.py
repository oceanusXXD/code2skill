from __future__ import annotations

from code2skill.config import ScanConfig
from code2skill.models import CachedFileRecord, SkillImpactIndexEntry, StateSnapshot


def build_state_snapshot(
    *,
    config: ScanConfig,
    inventory,
    budget,
    records: dict[str, CachedFileRecord],
    reverse_dependencies: dict[str, list[str]],
    skill_index: dict[str, SkillImpactIndexEntry],
    bytes_read: int,
    head_commit: str | None,
    generated_at: str,
) -> StateSnapshot:
    return StateSnapshot(
        version=1,
        generated_at=generated_at,
        repo_root=str(config.repo_path),
        head_commit=head_commit,
        selected_paths=[candidate.relative_path.as_posix() for candidate in budget.selected],
        directory_counts=inventory.directory_counts,
        gitignore_patterns=inventory.gitignore_patterns,
        discovery_method=inventory.discovery_method,
        candidate_count=len(inventory.candidates),
        total_chars=budget.total_chars,
        bytes_read=bytes_read,
        files=records,
        reverse_dependencies=reverse_dependencies,
        skill_index=skill_index,
    )
