# Python API

`code2skill` can be used as a Python package as well as a CLI.

## Supported High-Level API

The supported high-level API is available from `code2skill.api` and re-exported from the package root:

```python
from code2skill import adapt_repository, create_scan_config, estimate, run_ci, scan
```

These helpers are intended for application code and automation scripts.

## Shortcut Functions

### `scan(...)`

Run the full repository pipeline and write the normal artifact set.

### `estimate(...)`

Run the report-only preview path. This writes `report.json` but does not write Skills or state.

### `run_ci(...)`

Run the automation-oriented path that can choose between full and incremental execution.

### `adapt_repository(...)`

Adapt generated Skills into one or more target instruction-file formats under the target repository root.

## Config Builder

Use `create_scan_config(...)` when you need direct control over `ScanConfig` before calling lower-level functions such as:

```python
from code2skill import create_scan_config, run_ci_repository

config = create_scan_config(
    repo_path="/path/to/repo",
    command="ci",
    mode="auto",
    output_dir=".code2skill",
    base_ref="origin/main",
)
result = run_ci_repository(config)
```

## Path Semantics

`create_scan_config(...)` treats `repo_path` as the repository root.

- Relative `output_dir` values are resolved from `repo_path`
- Relative `report_path`, `diff_file`, and `pricing_file` values are resolved from `repo_path`
- Relative `source_dir` values passed to `adapt_repository(...)` are resolved from `repo_path`
- If `report_path` is omitted, it defaults to `output_dir/report.json`

## Returned Results

The pipeline functions return `ScanExecution`, which includes:

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

The lower-level config and report dataclasses are also exported from the package root:

```python
from code2skill import PricingConfig, RunOptions, ScanConfig, ScanExecution, ScanLimits
```

## Incremental-State Safety

Incremental state is reused only when the saved snapshot belongs to the same resolved repository root.
Invalid or damaged state files are treated as missing state and fall back safely.
