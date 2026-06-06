# Python API

`code2skill` can be used as a Python package as well as a CLI. The Python API follows the same product workflow: preview, scan, adapt, validate, and refresh in CI.

The supported high-level API is available from `code2skill.api` and re-exported from the package root.

## Imports

```python
from code2skill import (
    adapt_repository,
    create_scan_config,
    doctor,
    estimate,
    run_ci,
    scan,
)
```

Useful contracts are also exported:

```python
from code2skill import (
    AdoptionCheck,
    AdoptionReadiness,
    ArtifactLayout,
    CommandRunSummary,
    PricingConfig,
    RunOptions,
    ScanConfig,
    ScanExecution,
    ScanLimits,
)
```

## Recipes

### Preview Cost And Impact

```python
from code2skill import estimate

preview = estimate(".", output_dir=".code2skill")

print(preview.report_path)
print(preview.report.first_generation_cost.input_tokens)
```

`estimate(...)` writes `report.json`, does not call an LLM, and does not write Skills or state.

### Run A Structure-Only Smoke Check

```python
from code2skill import scan

result = scan(".", structure_only=True)

print(result.output_files)
```

This validates repository scanning and writes structural artifacts without planning or generating Skills.

### Generate Skills And Publish Codex Instructions

```python
from code2skill import adapt_repository, doctor, scan

result = scan(
    ".",
    llm_provider="qwen",
    llm_model="qwen-plus-latest",
    max_skills=6,
)
written = adapt_repository(".", target="codex")
readiness = doctor(".", target="codex")

print(result.generated_skills)
print(written)
print(readiness.ready, readiness.score)
```

### CI Refresh

```python
from code2skill import doctor, run_ci

result = run_ci(
    ".",
    mode="auto",
    base_ref="origin/main",
    head_ref="HEAD",
    llm_provider="qwen",
    llm_model="qwen-plus-latest",
)
readiness = doctor(".", target="codex")

if not readiness.ready:
    raise SystemExit(readiness.next_steps)
```

### Custom Config

Use `create_scan_config(...)` when you need to build a config once and pass it to a lower-level repository runner:

```python
from code2skill import create_scan_config, run_ci_repository

config = create_scan_config(
    repo_path=".",
    command="ci",
    mode="auto",
    output_dir=".code2skill",
    base_ref="origin/main",
    llm_provider="qwen",
    llm_model="qwen-plus-latest",
)
result = run_ci_repository(config)
```

## Function Summary

### `scan(...)`

Run the repository workflow and write the artifact bundle.

Common parameters:

- `repo_path="."`
- `output_dir=".code2skill"`
- `mode="full"`
- `structure_only=False`
- `llm_provider="openai"`
- `llm_model=None`
- `max_skills=8`

For OpenAI-compatible Responses endpoints, set `CODE2SKILL_OPENAI_API_KEY` and `CODE2SKILL_OPENAI_BASE_URL`; the Python API uses the same backend configuration as the CLI.

### `estimate(...)`

Run the report-only preview path.

Common parameters:

- `repo_path="."`
- `output_dir=".code2skill"`
- `mode="auto"`
- `base_ref=None`
- `head_ref="HEAD"`
- `pricing_file=None`

### `run_ci(...)`

Run the automation-oriented path that can choose between full and incremental execution.

Common parameters:

- `repo_path="."`
- `output_dir=".code2skill"`
- `mode="auto"`
- `base_ref=None`
- `head_ref="HEAD"`
- `diff_file=None`
- `structure_only=False`
- `llm_provider="openai"`
- `llm_model=None`

### `adapt_repository(...)`

Publish generated Skills to target tool files under the repository root.

```python
adapt_repository(".", target="codex")
adapt_repository(".", target="all")
```

Relative `source_dir` values are resolved from `repo_path`.

### `doctor(...)`

Inspect readiness without writing files or calling an LLM.

```python
readiness = doctor(".", target="codex")
```

`doctor(...)` returns `AdoptionReadiness`, including:

- `ready`
- `score`
- `checks`
- `missing_paths`
- `next_steps`

## Returned Results

`scan(...)`, `estimate(...)`, and `run_ci(...)` return `ScanExecution`:

- `repo_path`
- `output_dir`
- `output_files`
- `candidate_count`
- `selected_count`
- `total_chars`
- `run_mode`
- `changed_files`
- `affected_files`
- `affected_skills`
- `generated_skills`
- `report_path`
- `report`

The embedded `ExecutionReport` distinguishes:

- `final_product_files`: generated Skill artifacts inside the bundle
- `intermediate_artifact_files`: blueprint, plan, references, report, adoption guide, project summary, and state-side artifacts

## Path Semantics

`repo_path` is resolved first and treated as the repository root.

- Relative `output_dir` values are resolved from `repo_path`.
- Relative `report_path`, `diff_file`, and `pricing_file` values are resolved from `repo_path`.
- Relative `source_dir` values passed to `adapt_repository(...)` are resolved from `repo_path`.
- If `report_path` is omitted, it defaults to `output_dir/report.json`.

## Incremental-State Safety

Incremental state is reused only when the saved snapshot belongs to the same resolved repository root. Invalid or damaged state files are treated as missing state and fall back safely.
