from __future__ import annotations

from pathlib import Path
from typing import Any

from lab_sidecar.collectors.service import MetricsCollectionService, NoMetricsFoundError
from lab_sidecar.core.manifest import load_task
from lab_sidecar.core.models import TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path
from lab_sidecar.figures.service import FigureGenerationService, MetricsNotReadyError
from lab_sidecar.mcp.responses import (
    artifact_list,
    base_response,
    bounded_log_tail,
    compact_task_outputs,
    safety_response,
    task_summary,
)
from lab_sidecar.mcp.safety import assess_run_command
from lab_sidecar.reports.service import ReportGenerationService, ReportMetricsRequiredError
from lab_sidecar.runner.service import RunnerService
from lab_sidecar.slides.service import SlidesGenerationService


class LabSidecarMCPTools:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def run_experiment(
        self,
        command: str,
        cwd: str | Path | None = None,
        name: str | None = None,
        background: bool = True,
        risk_acceptance: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision = assess_run_command(self.root, command, Path(cwd) if cwd else None, risk_acceptance)
        if not decision.allowed:
            return safety_response(
                {
                    "status": "requires_confirmation" if decision.requires_confirmation else "blocked",
                    "safety": decision.to_dict(),
                    "reasons": decision.reasons,
                }
            )

        record = RunnerService(self.root).run(
            command,
            name=name,
            cwd=decision.cwd,
            background=background,
        )
        return base_response(
            record,
            summary={
                **task_summary(self.root, record),
                "safety": decision.to_dict(),
            },
            artifacts=artifact_list(record),
            next_actions=[f"inspect_results {record.task_id}"],
        )

    def inspect_results(
        self,
        task_id: str,
        refresh: bool = True,
        collect_metrics: bool = True,
        include_log_tail: bool = False,
        log_tail_lines: int = 20,
    ) -> dict[str, Any]:
        record = RunnerService(self.root).refresh(task_id) if refresh else load_task(self.root, task_id)
        warnings: list[str] = []
        if collect_metrics and record.status == TaskStatus.COMPLETED:
            task_path = resolve_workspace_path(record.paths.task_dir, self.root)
            if not (task_path / "metrics" / "normalized_metrics.csv").exists():
                try:
                    MetricsCollectionService(self.root).collect(task_id)
                except NoMetricsFoundError as exc:
                    warnings.append(str(exc))
                record = load_task(self.root, task_id)

        summary = {
            **task_summary(self.root, record),
            **compact_task_outputs(self.root, record),
        }
        if include_log_tail:
            stdout_path = resolve_workspace_path(record.paths.stdout, self.root)
            stderr_path = resolve_workspace_path(record.paths.stderr, self.root)
            summary["log_tail"] = {
                "stdout": bounded_log_tail(stdout_path, log_tail_lines),
                "stderr": bounded_log_tail(stderr_path, log_tail_lines),
            }

        return base_response(
            record,
            summary=summary,
            artifacts=artifact_list(record),
            warnings=warnings,
        )

    def make_figures(
        self,
        task_id: str,
        spec_path: str | Path | None = None,
        collect_if_missing: bool = True,
    ) -> dict[str, Any]:
        self._collect_if_needed(task_id, collect_if_missing)
        result = FigureGenerationService(self.root).generate(
            task_id,
            spec_path=Path(spec_path) if spec_path else None,
        )
        record = result.record
        return base_response(
            record,
            summary={
                **task_summary(self.root, record),
                "figure_count": len(result.generated),
                "spec_path": _relative(result.spec_path, self.root),
                "summary_path": _relative(result.summary_path, self.root),
            },
            artifacts=artifact_list(record),
            warnings=result.warnings,
            next_actions=[f"generate_report_fragment {task_id}", f"generate_slides {task_id}"],
        )

    def generate_report_fragment(
        self,
        task_id: str,
        template: str = "zh-lab",
        collect_if_missing: bool = True,
        preview_chars: int = 0,
    ) -> dict[str, Any]:
        record = load_task(self.root, task_id)
        if record.status not in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            self._collect_if_needed(task_id, collect_if_missing)
        result = ReportGenerationService(self.root).generate(task_id, template=template)
        record = result.record
        preview = None
        if preview_chars > 0:
            limit = min(preview_chars, 2000)
            preview = result.report_path.read_text(encoding="utf-8", errors="replace")[:limit]
        return base_response(
            record,
            summary={
                **task_summary(self.root, record),
                "template": result.template,
                "report_path": _relative(result.report_path, self.root),
                "summary_path": _relative(result.summary_path, self.root),
                "preview": preview,
            },
            artifacts=artifact_list(record),
            next_actions=[f"generate_slides {task_id}"],
            omitted={"report_markdown": "omitted_by_default" if preview is None else "bounded_preview_returned"},
        )

    def generate_slides(
        self,
        task_id: str,
        template: str = "zh-summary",
        ensure_metrics: bool = True,
        ensure_figures: bool = True,
        ensure_report: bool = True,
    ) -> dict[str, Any]:
        record = load_task(self.root, task_id)
        if record.status not in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            self._collect_if_needed(task_id, ensure_metrics)
            if ensure_figures:
                try:
                    FigureGenerationService(self.root).generate(task_id)
                except MetricsNotReadyError:
                    pass
            if ensure_report:
                try:
                    ReportGenerationService(self.root).generate(task_id)
                except ReportMetricsRequiredError:
                    pass

        result = SlidesGenerationService(self.root).generate(task_id, template=template)
        record = result.record
        return base_response(
            record,
            summary={
                **task_summary(self.root, record),
                "template": result.template,
                "pptx_path": _relative(result.pptx_path, self.root),
                "summary_path": _relative(result.summary_path, self.root),
                "slide_count": result.summary.get("slide_count"),
                "qa_checks": {
                    key: value.get("passed")
                    for key, value in result.summary.get("qa_checks", {}).items()
                    if isinstance(value, dict)
                },
            },
            artifacts=artifact_list(record),
        )

    def _collect_if_needed(self, task_id: str, enabled: bool) -> None:
        if not enabled:
            return
        record = load_task(self.root, task_id)
        task_path = resolve_workspace_path(record.paths.task_dir, self.root)
        if (task_path / "metrics" / "normalized_metrics.csv").exists():
            return
        MetricsCollectionService(self.root).collect(task_id)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
