from __future__ import annotations

from pathlib import Path

from code2skill.capabilities.blueprint_service import build_blueprint, record_to_candidate
from code2skill.models import CachedFileRecord, ConfigSummary, ImportGraphStats, ProjectProfile, SkillBlueprint, SourceFileSummary


def test_record_to_candidate_restores_cached_candidate_shape(tmp_path: Path) -> None:
    record = CachedFileRecord(
        path="src/app.py",
        sha256="abc",
        size_bytes=12,
        char_count=12,
        language="python",
        inferred_role="entrypoint",
        priority=5,
        priority_reasons=["entrypoint"],
        gitignored=False,
    )

    candidate = record_to_candidate(tmp_path, "src/app.py", record)

    assert candidate.absolute_path == tmp_path / "src" / "app.py"
    assert candidate.relative_path == Path("src/app.py")
    assert candidate.priority == 5


def test_build_blueprint_uses_collaborators_and_selected_source_summaries(monkeypatch, tmp_path: Path) -> None:
    module = __import__("code2skill.capabilities.blueprint_service", fromlist=["*"])
    config_summary = ConfigSummary(path="pyproject.toml", kind="pyproject", summary="python")
    selected_summary = SourceFileSummary(path="src/app.py", inferred_role="entrypoint", language="python")
    ignored_summary = SourceFileSummary(path="tests/test_app.py", inferred_role="test", language="python")
    records = {
        "src/app.py": CachedFileRecord(
            path="src/app.py",
            sha256="a",
            size_bytes=10,
            char_count=10,
            language="python",
            inferred_role="entrypoint",
            priority=1,
            priority_reasons=["entrypoint"],
            gitignored=False,
            config_summary=config_summary,
            source_summary=selected_summary,
        ),
        "tests/test_app.py": CachedFileRecord(
            path="tests/test_app.py",
            sha256="b",
            size_bytes=8,
            char_count=8,
            language="python",
            inferred_role="test",
            priority=1,
            priority_reasons=["test"],
            gitignored=False,
            source_summary=ignored_summary,
        ),
    }

    class FakeClassifier:
        def classify(self, repo_path, inventory_files, config_summaries, source_summaries):
            assert repo_path == tmp_path
            assert len(inventory_files) == 2
            assert config_summaries == [config_summary]
            assert source_summaries == [selected_summary]
            return ProjectProfile(
                name="repo",
                repo_type="library",
                languages=["python"],
                framework_signals=[],
                package_topology="flat",
                entrypoints=["src/app.py"],
            )

        def summarize_domains(self, source_summaries):
            assert source_summaries == [selected_summary]
            return []

        def build_tech_stack(self, project_profile, config_summaries):
            return {"language": ["python"]}

    class FakeRulesAnalyzer:
        def analyze(self, source_summaries, config_summaries):
            return []

    class FakeWorkflowAnalyzer:
        def analyze(self, source_summaries):
            return []

    class FakeBuilder:
        def build(self, **kwargs):
            return SkillBlueprint(
                project_profile=kwargs["profile"],
                tech_stack=kwargs["tech_stack"],
                domains=kwargs["domains"],
                directory_summary=[],
                key_configs=[config_summary],
                core_modules=[selected_summary],
                important_apis=[],
                abstract_rules=kwargs["abstract_rules"],
                concrete_workflows=kwargs["concrete_workflows"],
                recommended_skills=[],
                import_graph_stats=kwargs["import_graph_stats"],
            )

    monkeypatch.setattr(module, "ProjectClassifier", lambda: FakeClassifier())
    monkeypatch.setattr(module, "RulesAnalyzer", lambda: FakeRulesAnalyzer())
    monkeypatch.setattr(module, "WorkflowAnalyzer", lambda: FakeWorkflowAnalyzer())
    monkeypatch.setattr(module, "SkillBlueprintBuilder", lambda: FakeBuilder())

    blueprint = build_blueprint(
        repo_path=tmp_path,
        inventory=type("Inventory", (), {"directory_counts": {"src": 1}})(),
        selected_paths=["src/app.py"],
        records=records,
        import_graph_stats=ImportGraphStats(total_internal_edges=0, hub_files=[], entry_points=[], cluster_count=0),
    )

    assert blueprint.project_profile.name == "repo"
    assert blueprint.core_modules == [selected_summary]
