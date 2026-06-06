from __future__ import annotations

from pathlib import Path

from code2skill.extractors.python_extractor import PythonExtractor
from code2skill.models import FileCandidate


def test_python_extractor_records_semantic_signals(tmp_path: Path) -> None:
    source = """
from . import services
from .models import User, UserInput
import importlib


class UserService(BaseService):
    client = Client()

    def create(self, payload: UserInput) -> User:
        user = User(**payload)
        return services.save(user)


def load_plugin(name: str):
    module = importlib.import_module("app.plugins.audit")
    raise RuntimeError(name)
"""

    summary = PythonExtractor().extract(
        FileCandidate(
            absolute_path=tmp_path / "src" / "app" / "handlers.py",
            relative_path=Path("src/app/handlers.py"),
            size_bytes=len(source.encode("utf-8")),
            char_count=len(source),
            sha256="sha",
            language="python",
            inferred_role="source",
            priority=20,
            priority_reasons=["general source"],
            content=source,
        )
    )

    assert summary.dynamic_imports == ["app.plugins.audit"]
    assert "importlib.import_module" in summary.call_targets
    assert "services.save" in summary.call_targets
    assert "User" in summary.instantiated_classes
    assert "RuntimeError" in summary.raised_exceptions
    assert "BaseService" in summary.type_references
    assert "UserInput" in summary.type_references
    assert "User" in summary.type_references
    assert "UserService:client<-Client" in summary.data_flow_edges
    assert "create:user<-User" in summary.data_flow_edges

    from_import = next(detail for detail in summary.import_details if detail.module == ".")
    assert from_import.names == ["services"]
    assert from_import.aliases == ["services"]
