from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileCandidate:
    absolute_path: Path
    relative_path: Path
    size_bytes: int
    char_count: int
    sha256: str
    language: str | None
    inferred_role: str
    priority: int
    priority_reasons: list[str]
    content: str | None = None
    gitignored: bool = False


@dataclass(frozen=True)
class RepositoryInventory:
    repo_path: Path
    candidates: list[FileCandidate]
    directory_counts: dict[str, int]
    gitignore_patterns: list[str]
    discovery_method: str
    bytes_read: int


@dataclass(frozen=True)
class BudgetSelection:
    selected: list[FileCandidate]
    dropped: list[FileCandidate]
    total_chars: int


@dataclass(frozen=True)
class RouteSummary:
    method: str
    path: str
    handler: str
    framework: str


@dataclass(frozen=True)
class ImportInfo:
    module: str
    kind: str = "import"
    is_relative: bool = False
    is_dynamic: bool = False


@dataclass(frozen=True)
class ExportInfo:
    name: str
    kind: str = "named"


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    signature: str = ""
    decorators: list[str] = field(default_factory=list)
    return_type: str | None = None


@dataclass(frozen=True)
class ClassInfo:
    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceFileSummary:
    path: str
    inferred_role: str
    language: str | None
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    import_details: list[ImportInfo] = field(default_factory=list)
    export_details: list[ExportInfo] = field(default_factory=list)
    top_level_symbols: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    function_details: list[FunctionInfo] = field(default_factory=list)
    class_details: list[ClassInfo] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    routes: list[RouteSummary] = field(default_factory=list)
    models_or_schemas: list[str] = field(default_factory=list)
    state_signals: list[str] = field(default_factory=list)
    export_styles: list[str] = field(default_factory=list)
    file_structure: list[str] = field(default_factory=list)
    internal_dependencies: list[str] = field(default_factory=list)
    short_doc_summary: str = ""
    notes: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass(frozen=True)
class ConfigSummary:
    path: str
    kind: str
    summary: str
    framework_signals: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectProfile:
    name: str
    repo_type: str
    languages: list[str]
    framework_signals: list[str]
    package_topology: str
    entrypoints: list[str]
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DomainSummary:
    name: str
    summary: str
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DirectorySummary:
    path: str
    file_count: int
    dominant_roles: list[str] = field(default_factory=list)
    sample_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ApiSummary:
    kind: str
    name: str
    source: str
    details: str = ""


@dataclass(frozen=True)
class RuleSummary:
    name: str
    rule: str
    rationale: str
    evidence_files: list[str] = field(default_factory=list)
    source: str = "heuristic"
    confidence: float = 0.4
    example_snippet: str | None = None

    @property
    def evidence(self) -> list[str]:
        return self.evidence_files


@dataclass(frozen=True)
class WorkflowSummary:
    name: str
    summary: str
    steps: list[str]
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SkillRecommendation:
    name: str
    purpose: str
    scope: str
    source_evidence: list[str]
    why_split: str
    likely_inputs: list[str]
    likely_outputs: list[str]


@dataclass(frozen=True)
class SkillPlanEntry:
    name: str
    title: str
    scope: str
    why: str
    read_files: list[str]
    read_reason: str


@dataclass(frozen=True)
class SkillPlan:
    skills: list[SkillPlanEntry]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportGraphCluster:
    name: str
    files: list[str]


@dataclass(frozen=True)
class ImportGraphStats:
    total_internal_edges: int
    hub_files: list[str]
    entry_points: list[str]
    cluster_count: int
    clusters: list[ImportGraphCluster] = field(default_factory=list)


@dataclass(frozen=True)
class SkillBlueprint:
    project_profile: ProjectProfile
    tech_stack: dict[str, Any]
    domains: list[DomainSummary]
    directory_summary: list[DirectorySummary]
    key_configs: list[ConfigSummary]
    core_modules: list[SourceFileSummary]
    important_apis: list[ApiSummary]
    abstract_rules: list[RuleSummary]
    concrete_workflows: list[WorkflowSummary]
    recommended_skills: list[SkillRecommendation]
    import_graph_stats: ImportGraphStats | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CachedFileRecord:
    path: str
    sha256: str
    size_bytes: int
    char_count: int
    language: str | None
    inferred_role: str
    priority: int
    priority_reasons: list[str]
    gitignored: bool
    selected: bool = False
    config_summary: ConfigSummary | None = None
    source_summary: SourceFileSummary | None = None


@dataclass(frozen=True)
class SkillImpactIndexEntry:
    name: str
    purpose: str
    source_evidence: list[str]
    related_paths: list[str]


@dataclass(frozen=True)
class DiffHunk:
    header: str
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FileDiffPatch:
    path: str
    change_type: str
    patch: str
    previous_path: str | None = None
    hunks: list[DiffHunk] = field(default_factory=list)


@dataclass(frozen=True)
class StateSnapshot:
    version: int
    generated_at: str
    repo_root: str
    head_commit: str | None
    selected_paths: list[str]
    directory_counts: dict[str, int]
    gitignore_patterns: list[str]
    discovery_method: str
    candidate_count: int
    total_chars: int
    bytes_read: int
    files: dict[str, CachedFileRecord]
    reverse_dependencies: dict[str, list[str]]
    skill_index: dict[str, SkillImpactIndexEntry]


@dataclass(frozen=True)
class SkillCostBreakdown:
    name: str
    input_chars: int
    input_tokens: int
    output_chars: int
    output_tokens: int
    estimated_usd: float


@dataclass(frozen=True)
class CostEstimateSummary:
    strategy: str
    skill_count: int
    input_chars: int
    input_tokens: int
    output_chars: int
    output_tokens: int
    estimated_usd: float
    assumptions: list[str]
    per_skill: list[SkillCostBreakdown] = field(default_factory=list)


@dataclass(frozen=True)
class ImpactSummary:
    changed_files: list[str]
    affected_files: list[str]
    affected_skills: list[str]


@dataclass(frozen=True)
class ExecutionReport:
    generated_at: str
    command: str
    requested_mode: str
    effective_mode: str
    repo_path: str
    output_dir: str
    base_ref: str | None
    head_ref: str
    head_commit: str | None
    discovery_method: str
    candidate_count: int
    selected_count: int
    total_chars: int
    bytes_read: int
    written_files: list[str]
    updated_files: list[str]
    impact: ImpactSummary
    first_generation_cost: CostEstimateSummary
    incremental_rewrite_cost: CostEstimateSummary
    incremental_patch_cost: CostEstimateSummary
    pricing: dict[str, Any]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScanExecution:
    repo_path: Path
    output_dir: Path
    output_files: list[Path]
    candidate_count: int
    selected_count: int
    total_chars: int
    blueprint: SkillBlueprint
    run_mode: str = "full"
    changed_files: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    affected_skills: list[str] = field(default_factory=list)
    report_path: Path | None = None
    report: ExecutionReport | None = None
