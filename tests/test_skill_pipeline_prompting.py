from __future__ import annotations

from pathlib import Path

from code2skill.analyzers.skill_blueprint_builder import SkillBlueprintBuilder
from code2skill.llm_backend import MockBackend
from code2skill.models import (
    ConfigSummary,
    DirectorySummary,
    DomainSummary,
    ImportGraphCluster,
    ImportGraphStats,
    ProjectProfile,
    RuleSummary,
    SkillBlueprint,
    SkillPlan,
    SkillPlanEntry,
    SourceFileSummary,
    WorkflowSummary,
)
from code2skill.skill_generator import SkillGenerator
from code2skill.skill_planner import SkillPlanner


def test_blueprint_builder_uses_nested_directories_and_core_module_evidence() -> None:
    builder = SkillBlueprintBuilder()
    blueprint = builder.build(
        profile=ProjectProfile(
            name="code2skill",
            repo_type="backend",
            languages=["python"],
            framework_signals=[],
            package_topology="single-package",
            entrypoints=["src/code2skill/cli.py"],
        ),
        tech_stack={"languages": ["python"]},
        domains=[
            DomainSummary(
                name="backend",
                summary="Backend-like Python package",
                evidence=["src/code2skill/core.py"],
            )
        ],
        directory_counts={
            "src/code2skill": 2,
            "src/code2skill/scanner": 2,
            ".": 1,
        },
        config_summaries=[
            ConfigSummary(
                path="pyproject.toml",
                kind="pyproject",
                summary="Project packaging and CLI config",
            )
        ],
        source_summaries=[
            SourceFileSummary(
                path="src/code2skill/cli.py",
                inferred_role="entrypoint",
                language="python",
                functions=["main"],
                short_doc_summary="CLI entrypoint",
                confidence=0.9,
            ),
            SourceFileSummary(
                path="src/code2skill/core.py",
                inferred_role="source",
                language="python",
                functions=["execute_repository"],
                internal_dependencies=["src/code2skill/scanner/repository.py"],
                short_doc_summary="Pipeline orchestration",
                confidence=0.95,
            ),
            SourceFileSummary(
                path="src/code2skill/scanner/repository.py",
                inferred_role="service",
                language="python",
                classes=["RepositoryScanner"],
                functions=["scan"],
                short_doc_summary="Repository scanning",
                confidence=0.85,
            ),
            SourceFileSummary(
                path="src/code2skill/scanner/detector.py",
                inferred_role="utility",
                language="python",
                functions=["detect_language"],
                short_doc_summary="Language detection",
                confidence=0.6,
            ),
        ],
        abstract_rules=[],
        concrete_workflows=[
            WorkflowSummary(
                name="scan-repository",
                summary="Discover files and build summaries",
                steps=["discover files", "extract summaries"],
                evidence=[
                    "src/code2skill/core.py",
                    "src/code2skill/scanner/repository.py",
                ],
            )
        ],
        import_graph_stats=ImportGraphStats(
            total_internal_edges=3,
            hub_files=[
                "src/code2skill/core.py",
                "src/code2skill/scanner/repository.py",
            ],
            entry_points=["src/code2skill/cli.py"],
            cluster_count=1,
            clusters=[
                ImportGraphCluster(
                    name="src/code2skill/scanner",
                    files=[
                        "src/code2skill/scanner/repository.py",
                        "src/code2skill/scanner/detector.py",
                    ],
                )
            ],
        ),
    )

    scanner_directory = next(
        item
        for item in blueprint.directory_summary
        if item.path == "src/code2skill/scanner"
    )
    assert scanner_directory.dominant_roles == ["service", "utility"]
    assert scanner_directory.sample_files == [
        "src/code2skill/scanner/repository.py",
        "src/code2skill/scanner/detector.py",
    ]

    core_paths = [summary.path for summary in blueprint.core_modules[:4]]
    assert core_paths[0] == "src/code2skill/cli.py"
    assert "src/code2skill/core.py" in core_paths
    assert "src/code2skill/scanner/repository.py" in core_paths


def test_skill_planner_prompt_includes_scan_context_and_sanitizes_output(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "src/code2skill/cli.py", "def main() -> None:\n    pass\n")
    _write(
        tmp_path / "src/code2skill/scanner/repository.py",
        "class RepositoryScanner:\n    def scan(self) -> None:\n        pass\n",
    )
    _write(
        tmp_path / "pyproject.toml",
        "[project]\nname = 'code2skill'\n",
    )

    backend = MockBackend(
        """
        {
          "skills": [
            {
              "name": "Scanner Flow",
              "title": "Scanner Flow ✨",
              "scope": "CLI entrypoint and repository scanning",
              "why": "Explains the main scan path ✨",
              "read_files": [
                "src/code2skill/cli.py",
                "src/code2skill/scanner/repository.py",
                "missing.py"
              ],
              "read_reason": "Entry path and scanner implementation ✨"
            }
          ]
        }
        """
    )
    planner = SkillPlanner(backend=backend, max_skills=4)

    plan = planner.plan(_sample_blueprint(), repo_path=tmp_path)

    assert plan.skills[0].name == "scanner-flow"
    assert plan.skills[0].title == "Scanner Flow"
    assert plan.skills[0].why == "Explains the main scan path"
    assert plan.skills[0].read_reason == "Entry path and scanner implementation"
    assert plan.skills[0].read_files == [
        "src/code2skill/cli.py",
        "src/code2skill/scanner/repository.py",
    ]

    prompt = str(backend.calls[0]["prompt"])
    assert "Key configuration:" in prompt
    assert "Dependency summary:" in prompt
    assert "Heuristic recommendations (low-priority reference, do not follow blindly):" in prompt
    assert "Prefer package boundaries, directory boundaries, dependency clusters, and stable workflows over generic labels." in prompt


def test_skill_generator_prompt_and_output_are_evidence_driven(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "src/code2skill/cli.py",
        "def main() -> None:\n    run_scan()\n",
    )
    output_dir = tmp_path / ".code2skill"
    backend = MockBackend(
        """
        # Scanner Flow Guide ✨
        ## Overview
        This area defines the command entrypoint.

        ## Core Rules
        - Every file must start with `from __future__ import annotations`. Source: src/code2skill/cli.py
        - Enter the scan flow through `main()`. Source: src/code2skill/cli.py:main

        ## Typical Patterns
        Source: src/code2skill/cli.py
        ```python
        def main() -> None:
            run_scan()
        ```

        ## Avoid
        - [Needs confirmation] The current context is not sufficient to derive a stable anti-pattern.

        ## Common Flows
        1. Call `main()`.
        """
    )
    generator = SkillGenerator(
        backend=backend,
        repo_path=tmp_path,
        output_dir=output_dir,
        max_inline_chars=4096,
    )
    artifacts = generator.generate_all(
        blueprint=_sample_blueprint(),
        plan=SkillPlan(
            skills=[
                SkillPlanEntry(
                    name="scanner-flow",
                    title="Scanner Flow Guide",
                    scope="Command entrypoint and scan orchestration",
                    why="This is the user-visible entry into the scan flow",
                    read_files=["src/code2skill/cli.py"],
                    read_reason="The entrypoint defines how the scan is invoked",
                )
            ]
        ),
    )

    content = artifacts["skills/scanner-flow.md"]
    assert "✨" not in content
    assert "# Scanner Flow Guide" in content
    assert "from __future__ import annotations" not in content
    prompt = str(backend.calls[0]["prompt"])
    assert "Do not use emoji, decorative symbols, or extra headings." in prompt
    assert "Output exactly the 5 sections listed below and nothing else." in prompt
    assert 'Every bullet under "Core Rules" must include a source path in the same bullet.' in prompt


def _sample_blueprint() -> SkillBlueprint:
    return SkillBlueprint(
        project_profile=ProjectProfile(
            name="code2skill",
            repo_type="backend",
            languages=["python"],
            framework_signals=[],
            package_topology="single-package",
            entrypoints=["src/code2skill/cli.py"],
            evidence=["pyproject.toml", "src/code2skill/cli.py"],
        ),
        tech_stack={"languages": ["python"], "tools": ["argparse"]},
        domains=[
            DomainSummary(
                name="core",
                summary="CLI and orchestration",
                evidence=["src/code2skill/cli.py", "src/code2skill/core.py"],
            )
        ],
        directory_summary=[
            DirectorySummary(
                path="src/code2skill",
                file_count=2,
                dominant_roles=["entrypoint", "source"],
                sample_files=[
                    "src/code2skill/cli.py",
                    "src/code2skill/core.py",
                ],
            ),
            DirectorySummary(
                path="src/code2skill/scanner",
                file_count=2,
                dominant_roles=["service", "utility"],
                sample_files=[
                    "src/code2skill/scanner/repository.py",
                    "src/code2skill/scanner/detector.py",
                ],
            ),
        ],
        key_configs=[
            ConfigSummary(
                path="pyproject.toml",
                kind="pyproject",
                summary="Project metadata and CLI entrypoint",
                framework_signals=["argparse"],
                entrypoints=["src/code2skill/cli.py"],
            )
        ],
        core_modules=[
            SourceFileSummary(
                path="src/code2skill/cli.py",
                inferred_role="entrypoint",
                language="python",
                functions=["main"],
                short_doc_summary="CLI entrypoint",
                confidence=0.9,
            ),
            SourceFileSummary(
                path="src/code2skill/scanner/repository.py",
                inferred_role="service",
                language="python",
                classes=["RepositoryScanner"],
                functions=["scan"],
                internal_dependencies=["src/code2skill/scanner/detector.py"],
                short_doc_summary="Repository scanning",
                confidence=0.8,
            ),
        ],
        important_apis=[],
        abstract_rules=[
            RuleSummary(
                name="cli-entrypoint",
                rule="The scan command enters the main execution path through `main()`.",
                rationale="The CLI module exposes a single entry function.",
                evidence_files=["src/code2skill/cli.py"],
                source="pattern_detection",
                confidence=0.8,
            )
        ],
        concrete_workflows=[
            WorkflowSummary(
                name="run-scan",
                summary="Enter the scan flow from the CLI layer",
                steps=["parse arguments", "call the scan entrypoint"],
                evidence=["src/code2skill/cli.py", "src/code2skill/core.py"],
            )
        ],
        recommended_skills=[],
        import_graph_stats=ImportGraphStats(
            total_internal_edges=2,
            hub_files=["src/code2skill/core.py"],
            entry_points=["src/code2skill/cli.py"],
            cluster_count=1,
            clusters=[
                ImportGraphCluster(
                    name="src/code2skill",
                    files=[
                        "src/code2skill/cli.py",
                        "src/code2skill/core.py",
                    ],
                )
            ],
        ),
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
