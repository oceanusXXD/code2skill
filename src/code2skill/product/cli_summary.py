from __future__ import annotations

from ..domain.results import CommandRunSummary


def render_summary_lines(summary: CommandRunSummary) -> list[str]:
    lines = [f"command: {summary.command}"]
    if summary.mode is not None:
        lines.append(f"mode: {summary.mode}")
    if summary.structure_only is not None:
        lines.append(f"structure_only: {'true' if summary.structure_only else 'false'}")
    lines.append(f"repo: {summary.repo_path}")
    if summary.llm_provider is not None:
        lines.append(f"llm_provider: {summary.llm_provider}")
    if summary.llm_model is not None:
        lines.append(f"llm_model: {summary.llm_model}")
    if summary.target is not None:
        lines.append(f"target: {summary.target}")
    if summary.source_dir is not None:
        lines.append(f"source_dir: {summary.source_dir}")
    if summary.repo_type is not None:
        lines.append(f"repo_type: {summary.repo_type}")
    if summary.selected_count is not None and summary.candidate_count is not None:
        lines.append(f"selected_files: {summary.selected_count}/{summary.candidate_count}")
    if summary.total_chars is not None:
        lines.append(f"total_chars: {summary.total_chars}")
    if summary.changed_files:
        lines.append(f"changed_files: {len(summary.changed_files)}")
    if summary.affected_skills:
        lines.append(f"affected_skills: {', '.join(summary.affected_skills)}")
    if summary.generated_skills:
        lines.append(f"generated_skills: {', '.join(summary.generated_skills)}")
    if summary.output_dir is not None:
        lines.append(f"output_dir: {summary.output_dir}")
    if summary.report_path is not None:
        lines.append(f"report: {summary.report_path}")
    lines.extend(f"note: {note}" for note in summary.notes)
    lines.extend(f"updated: {path}" for path in summary.updated_paths)
    lines.extend(f"wrote: {path}" for path in summary.written_paths)
    return lines
