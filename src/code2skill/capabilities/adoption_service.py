from __future__ import annotations

import json
import re
from pathlib import Path

from ..adapt import COPY_MANIFEST_NAME, MANAGED_BLOCK_END, MANAGED_BLOCK_START
from ..capabilities.adapt.targets import get_target_definitions
from ..domain.adoption import AdoptionCheck, AdoptionReadiness
from ..domain.artifacts import ArtifactLayout
from ..skill_planner import load_skill_plan
from ..state_codec import snapshot_from_dict


def inspect_adoption_readiness(
    repo_path: Path | str,
    *,
    output_dir: Path | str = ".code2skill",
    target: str | None = None,
) -> AdoptionReadiness:
    repo_root = Path(repo_path).expanduser().resolve()
    layout = ArtifactLayout.from_repo_root(repo_root, output_dir=output_dir)
    checks = [
        _check_path(
            name="artifact_bundle",
            path=layout.root,
            is_dir=True,
            present_message="Artifact bundle is present.",
            missing_message="Artifact bundle is missing. Run `code2skill scan .` first.",
        ),
        _check_path(
            name="project_summary",
            path=layout.project_summary_path,
            is_dir=False,
            present_message="Project summary is present.",
            missing_message="Project summary is missing. Run `code2skill scan . --structure-only` or a full scan.",
        ),
        _check_path(
            name="adoption_guide",
            path=layout.adoption_guide_path,
            is_dir=False,
            present_message="Adoption guide is present.",
            missing_message="Adoption guide is missing. Run `code2skill scan . --structure-only` or a full scan.",
        ),
        _check_report(layout.report_path),
        _check_skills(layout.skills_dir),
        _check_skill_plan(layout.skill_plan_path, layout.skills_dir),
        _check_state_snapshot(layout.state_path, repo_root),
    ]
    if target is not None:
        checks.extend(_check_target_outputs(repo_root, target, layout.skills_dir))

    failed = [check for check in checks if check.status != "ok"]
    score = round((len(checks) - len(failed)) / len(checks) * 100) if checks else 100
    return AdoptionReadiness(
        repo_path=repo_root,
        output_dir=layout.root,
        target=target,
        ready=not failed,
        score=score,
        checks=checks,
        missing_paths=[check.path for check in failed if check.path is not None],
        next_steps=_build_next_steps(failed, target),
    )


def _check_path(
    *,
    name: str,
    path: Path,
    is_dir: bool,
    present_message: str,
    missing_message: str,
) -> AdoptionCheck:
    exists = path.is_dir() if is_dir else path.is_file()
    return AdoptionCheck(
        name=name,
        status="ok" if exists else "missing",
        message=present_message if exists else missing_message,
        path=path,
    )


def _check_report(report_path: Path) -> AdoptionCheck:
    if not report_path.is_file():
        return AdoptionCheck(
            name="report",
            status="missing",
            message="Execution report is missing. Run `code2skill estimate .` or `code2skill scan .`.",
            path=report_path,
        )
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return AdoptionCheck(
            name="report",
            status="invalid",
            message="Execution report is not valid JSON.",
            path=report_path,
        )

    referenced_paths = _report_referenced_paths(payload)
    missing_paths = [
        path
        for path in referenced_paths
        if not path.exists()
    ]
    if missing_paths:
        preview = ", ".join(str(path) for path in missing_paths[:3])
        return AdoptionCheck(
            name="report",
            status="invalid",
            message=f"Execution report references missing files: {preview}",
            path=report_path,
        )
    return AdoptionCheck(
        name="report",
        status="ok",
        message="Execution report is present and parseable.",
        path=report_path,
    )


def _check_skills(skills_dir: Path) -> AdoptionCheck:
    index_path = skills_dir / "index.md"
    skill_files = [
        path
        for path in skills_dir.glob("*.md")
        if path.name != "index.md"
    ] if skills_dir.exists() else []
    if not index_path.is_file() or not skill_files:
        return AdoptionCheck(
            name="skill_products",
            status="missing",
            message="Generated Skills are missing. Run `code2skill scan .` without `--structure-only`.",
            path=skills_dir,
        )

    invalid_skills = [
        path.name
        for path in skill_files
        if not path.read_text(encoding="utf-8").lstrip().startswith("# ")
    ]
    if invalid_skills:
        return AdoptionCheck(
            name="skill_products",
            status="invalid",
            message=f"Skill files must start with a level-1 heading: {', '.join(invalid_skills[:3])}",
            path=skills_dir,
        )

    index_content = index_path.read_text(encoding="utf-8")
    linked_files = re.findall(r"\]\(\./([^)]+\.md)\)", index_content)
    missing_links = [
        filename
        for filename in linked_files
        if not (skills_dir / filename).is_file()
    ]
    if missing_links:
        return AdoptionCheck(
            name="skill_products",
            status="invalid",
            message=f"Skill index links to missing files: {', '.join(missing_links[:3])}",
            path=skills_dir,
        )

    ok = True
    return AdoptionCheck(
        name="skill_products",
        status="ok" if ok else "missing",
        message="Generated Skill products are present and internally linked.",
        path=skills_dir,
    )


def _check_skill_plan(plan_path: Path, skills_dir: Path) -> AdoptionCheck:
    if not plan_path.is_file():
        return AdoptionCheck(
            name="skill_plan",
            status="missing",
            message="Skill plan is missing. Run `code2skill scan .` without `--structure-only`.",
            path=plan_path,
        )
    try:
        plan = load_skill_plan(plan_path)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return AdoptionCheck(
            name="skill_plan",
            status="invalid",
            message="Skill plan is not valid or does not match the expected schema.",
            path=plan_path,
        )

    if not plan.skills:
        return AdoptionCheck(
            name="skill_plan",
            status="invalid",
            message="Skill plan does not contain any skills.",
            path=plan_path,
        )

    missing_skill_files = [
        f"{skill.name}.md"
        for skill in plan.skills
        if not (skills_dir / f"{skill.name}.md").is_file()
    ]
    empty_read_files = [
        skill.name
        for skill in plan.skills
        if not skill.read_files
    ]
    if missing_skill_files:
        return AdoptionCheck(
            name="skill_plan",
            status="invalid",
            message=f"Skill plan references missing skill files: {', '.join(missing_skill_files[:3])}",
            path=plan_path,
        )
    if empty_read_files:
        return AdoptionCheck(
            name="skill_plan",
            status="invalid",
            message=f"Skill plan entries have no read_files evidence: {', '.join(empty_read_files[:3])}",
            path=plan_path,
        )
    return AdoptionCheck(
        name="skill_plan",
        status="ok",
        message="Skill plan matches generated Skill files.",
        path=plan_path,
    )


def _check_state_snapshot(state_path: Path, repo_root: Path) -> AdoptionCheck:
    if not state_path.is_file():
        return AdoptionCheck(
            name="state_snapshot",
            status="missing",
            message="Incremental state is missing. Run `code2skill ci . --mode auto` or `code2skill scan .`.",
            path=state_path,
        )
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return AdoptionCheck(
            name="state_snapshot",
            status="invalid",
            message="Incremental state snapshot is not valid JSON.",
            path=state_path,
        )
    try:
        snapshot = snapshot_from_dict(payload)
    except (KeyError, TypeError, ValueError):
        return AdoptionCheck(
            name="state_snapshot",
            status="invalid",
            message="Incremental state snapshot does not match the expected schema.",
            path=state_path,
        )
    if Path(snapshot.repo_root).expanduser().resolve() != repo_root:
        return AdoptionCheck(
            name="state_snapshot",
            status="invalid",
            message="Incremental state snapshot belongs to a different repository root.",
            path=state_path,
        )
    return AdoptionCheck(
        name="state_snapshot",
        status="ok",
        message="Incremental state snapshot is present and repo-root matched.",
        path=state_path,
    )


def _check_target_outputs(repo_root: Path, target: str, skills_dir: Path) -> list[AdoptionCheck]:
    checks: list[AdoptionCheck] = []
    try:
        definitions = get_target_definitions(target)
    except KeyError:
        raise ValueError(f"Unsupported target: {target}") from None

    for definition in definitions:
        destination = (repo_root / definition.destination).resolve()
        if definition.mode == "copy":
            checks.append(_check_copy_target(definition.name, destination, skills_dir))
            continue
        else:
            ok = (
                destination.is_file()
                and MANAGED_BLOCK_START in destination.read_text(encoding="utf-8")
                and MANAGED_BLOCK_END in destination.read_text(encoding="utf-8")
            )
        checks.append(
            AdoptionCheck(
                name=f"target_{definition.name}",
                status="ok" if ok else "missing",
                message=(
                    f"{definition.name} target output is present."
                    if ok
                    else f"{definition.name} target output is missing. Run `code2skill adapt . --target {definition.name}`."
                ),
                path=destination,
            )
        )
    return checks


def _check_copy_target(name: str, destination: Path, skills_dir: Path) -> AdoptionCheck:
    expected_files = sorted(skills_dir.glob("*.md")) if skills_dir.is_dir() else []
    expected_names = {path.name for path in expected_files}
    if not expected_names or "index.md" not in expected_names:
        return AdoptionCheck(
            name=f"target_{name}",
            status="missing",
            message=f"{name} target output cannot be checked because generated Skills are missing.",
            path=destination,
        )
    if not destination.is_dir():
        return AdoptionCheck(
            name=f"target_{name}",
            status="missing",
            message=f"{name} target output is missing. Run `code2skill adapt . --target {name}`.",
            path=destination,
        )

    missing_files = [
        source_file.name
        for source_file in expected_files
        if not (destination / source_file.name).is_file()
    ]
    if missing_files:
        return AdoptionCheck(
            name=f"target_{name}",
            status="missing",
            message=f"{name} target output is missing generated files: {', '.join(missing_files[:3])}",
            path=destination,
        )

    stale_files = [
        source_file.name
        for source_file in expected_files
        if (destination / source_file.name).read_text(encoding="utf-8")
        != source_file.read_text(encoding="utf-8")
    ]
    if stale_files:
        return AdoptionCheck(
            name=f"target_{name}",
            status="invalid",
            message=f"{name} target output is out of date: {', '.join(stale_files[:3])}",
            path=destination,
        )

    manifest_path = destination / COPY_MANIFEST_NAME
    if manifest_path.is_file():
        try:
            manifest_names = _read_copy_manifest(manifest_path)
        except ValueError as exc:
            return AdoptionCheck(
                name=f"target_{name}",
                status="invalid",
                message=str(exc),
                path=manifest_path,
            )
        if manifest_names != expected_names:
            return AdoptionCheck(
                name=f"target_{name}",
                status="invalid",
                message=f"{name} target manifest does not match current generated Skills.",
                path=manifest_path,
            )

    return AdoptionCheck(
        name=f"target_{name}",
        status="ok",
        message=f"{name} target output is present and matches generated Skills.",
        path=destination,
    )


def _read_copy_manifest(manifest_path: Path) -> set[str]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Copy target manifest is not valid JSON: {manifest_path}") from exc
    raw_files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(raw_files, list) or not all(isinstance(name, str) for name in raw_files):
        raise ValueError(f"Copy target manifest does not match the expected schema: {manifest_path}")
    invalid_names = [
        name
        for name in raw_files
        if Path(name).name != name or not name.endswith(".md")
    ]
    if invalid_names:
        raise ValueError(f"Copy target manifest contains invalid filenames: {', '.join(invalid_names[:3])}")
    return set(raw_files)


def _build_next_steps(
    failed: list[AdoptionCheck],
    target: str | None,
) -> list[str]:
    failed_names = {check.name for check in failed}
    steps: list[str] = []
    if "artifact_bundle" in failed_names or "project_summary" in failed_names:
        steps.append("Run `code2skill scan . --structure-only` for a no-LLM structural smoke check.")
    if "skill_products" in failed_names:
        steps.append("Run `code2skill scan . --llm <provider> --model <model>` to generate Skills.")
    if "skill_plan" in failed_names:
        steps.append("Run `code2skill scan . --llm <provider> --model <model>` to rebuild the Skill plan and Skills.")
    if "report" in failed_names:
        steps.append("Run `code2skill estimate .` to create a report-only cost and impact preview.")
    if "state_snapshot" in failed_names:
        steps.append("Run `code2skill ci . --mode auto` once to seed incremental state.")
    if any(check.name.startswith("target_") for check in failed):
        target_arg = target or "codex"
        steps.append(f"Run `code2skill adapt . --target {target_arg}` to publish generated Skills.")
    return _dedupe_strings(steps)


def _report_referenced_paths(payload: object) -> list[Path]:
    if not isinstance(payload, dict):
        return []
    values: list[str] = []
    for key in ("written_files", "updated_files", "final_product_files", "intermediate_artifact_files"):
        raw = payload.get(key, [])
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
    return [
        Path(value).expanduser().resolve()
        for value in values
        if value
    ]


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
