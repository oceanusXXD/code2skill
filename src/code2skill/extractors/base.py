from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import FileCandidate, SourceFileSummary


class SourceExtractor(ABC):
    @abstractmethod
    def extract(self, candidate: FileCandidate) -> SourceFileSummary:
        """Extract a language-specific source skeleton."""
