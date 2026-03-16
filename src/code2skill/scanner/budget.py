from __future__ import annotations

from .prioritizer import FilePrioritizer
from ..config import ScanLimits
from ..models import BudgetSelection, FileCandidate


class BudgetManager:
    def __init__(self, limits: ScanLimits) -> None:
        self.limits = limits

    def select(self, candidates: list[FileCandidate]) -> BudgetSelection:
        ordered = sorted(
            candidates,
            key=lambda candidate: (
                -candidate.priority,
                candidate.char_count,
                candidate.relative_path.as_posix(),
            ),
        )

        selected: list[FileCandidate] = []
        dropped: list[FileCandidate] = []
        total_chars = 0
        for candidate in ordered:
            if len(selected) >= self.limits.max_files:
                dropped.append(candidate)
                continue
            if total_chars + candidate.char_count > self.limits.max_total_chars:
                dropped.append(candidate)
                continue
            selected.append(candidate)
            total_chars += candidate.char_count

        return BudgetSelection(selected=selected, dropped=dropped, total_chars=total_chars)
