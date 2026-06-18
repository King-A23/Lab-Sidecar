from __future__ import annotations

from pathlib import Path
from typing import Any

from lab_sidecar.collectors.service import MetricsCollectionService, NoMetricsFoundError
from lab_sidecar.core.manifest import load_task
from lab_sidecar.core.models import TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path, state_dir
from lab_sidecar.figures.service import FigureGenerationService, MetricsNotReadyError
from lab_sidecar.intelligence.sandbox import is_path_within
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
            omitted={
                "log_tail": "omitted_by_default" if not include_log_tail else "bounded_tail_returned",
            },
        )

    def cancel_experiment(self, task_id: str) -> dict[str, Any]:
        try:
            record = RunnerService(self.root).cancel(task_id)
        except FileNotFoundError as exc:
            return base_response(
                None,
                summary={
                    "status": "not_cancelled",
                    "task_id": task_id,
                    "headline": f"Task {task_id} could not be cancelled because it was not found.",
                },
                warnings=[str(exc)],
                next_actions=[],
                omitted={"cancellation": "not_applicable"},
            )
        except RuntimeError as exc:
            current_status = str(exc)
            record = load_task(self.root, task_id)
            return base_response(
                record,
                summary={
                    **task_summary(self.root, record),
                    "cancellation": {
                        "status": "not_cancelled",
                        "reason": "task is not running",
                        "current_status": current_status,
                    },
                },
                artifacts=artifact_list(record),
                warnings=[f"Current status: {current_status}"],
                next_actions=[f"inspect_results {record.task_id}"],
                omitted={"cancellation": "not_applicable"},
            )
        return base_response(
            record,
            summary=task_summary(self.root, record),
            artifacts=artifact_list(record),
            next_actions=[f"inspect_results {record.task_id}"],
        )

    def delegate_experiment_artifacts(
        self,
        user_goal: str,
        command: str | None = None,
        result_path: str | Path | None = None,
        desired_outputs: list[str] | None = None,
        intelligent_mode: str = "auto",
        context_budget: dict[str, Any] | None = None,
        risk_acceptance: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if command:
            decision = assess_run_command(self.root, command, None, risk_acceptance)
            if not decision.allowed:
                return safety_response(
                    {
                        "status": "requires_confirmation" if decision.requires_confirmation else "blocked",
                        "safety": decision.to_dict(),
                        "reasons": decision.reasons,
                    }
                )
        if result_path is not None:
            path_error = self._validate_workspace_input_path(result_path)
            if path_error is not None:
                return safety_response(path_error)

        try:
            from lab_sidecar.intelligence.tools import delegate_experiment_artifacts as v2_delegate_experiment_artifacts

            return v2_delegate_experiment_artifacts(
                workspace_path=self.root,
                user_goal=user_goal,
                command=command,
                result_path=result_path,
                desired_outputs=desired_outputs,
                intelligent_mode=intelligent_mode,
                context_budget=context_budget,
            )
        except (RuntimeError, ValueError) as exc:
            return {
                "schema_version": "2.1",
                "task_id": None,
                "status": "rejected",
                "summary": {"headline": str(exc)},
                "artifacts": [],
                "warnings": [str(exc)],
                "next_actions": ["Revise the delegation request and retry."],
                "risk_flags": ["delegate_experiment_artifacts_rejected"],
                "omitted": {
                    "full_command": "omitted_by_default",
                    "full_stdout": "omitted_by_default",
                    "full_stderr": "omitted_by_default",
                    "metrics_rows": "omitted_by_default",
                    "artifact_bodies": "omitted_by_default",
                    "report_markdown": "omitted_by_default",
                    "ppt_contents": "omitted_by_default",
                    "worker_prompt_response": "omitted_by_default",
                    "full_data_files": "omitted_by_default",
                },
            }

    def inspect_sidecar_task(self, task_id: str) -> dict[str, Any]:
        from lab_sidecar.intelligence.tools import inspect_sidecar_task as v2_inspect_sidecar_task

        return v2_inspect_sidecar_task(self.root, task_id)

    def cancel_sidecar_task(self, task_id: str) -> dict[str, Any]:
        try:
            from lab_sidecar.intelligence.tools import cancel_sidecar_task as v2_cancel_sidecar_task

            return v2_cancel_sidecar_task(self.root, task_id)
        except RuntimeError as exc:
            return {
                "schema_version": "2.1",
                "task_id": task_id,
                "status": "not_cancelled",
                "summary": {"headline": f"Task {task_id} could not be cancelled: {exc}."},
                "artifacts": [],
                "warnings": [str(exc)],
                "next_actions": [f"inspect_sidecar_task {task_id}"],
                "risk_flags": ["cancel_sidecar_task_not_applicable"],
                "omitted": {
                    "full_command": "omitted_by_default",
                    "full_stdout": "omitted_by_default",
                    "full_stderr": "omitted_by_default",
                    "metrics_rows": "omitted_by_default",
                    "artifact_bodies": "omitted_by_default",
                    "report_markdown": "omitted_by_default",
                    "ppt_contents": "omitted_by_default",
                    "worker_prompt_response": "omitted_by_default",
                    "full_data_files": "omitted_by_default",
                },
            }

    def preview_sidecar_artifact(
        self,
        task_id: str,
        artifact_path: str,
        max_rows: int = 20,
        max_lines: int = 40,
    ) -> dict[str, Any]:
        from lab_sidecar.intelligence.tools import preview_sidecar_artifact as v2_preview_sidecar_artifact

        return v2_preview_sidecar_artifact(
            self.root,
            task_id,
            artifact_path,
            max_rows=max_rows,
            max_lines=max_lines,
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

    def _validate_workspace_input_path(self, path: str | Path) -> dict[str, Any] | None:
        try:
            resolved = resolve_workspace_path(str(path), self.root).resolve()
        except (OSError, RuntimeError) as exc:
            return {
                "status": "blocked",
                "safety": {"level": "blocked", "reasons": [str(exc)]},
                "reasons": [str(exc)],
            }
        if not is_path_within(resolved, self.root):
            return {
                "status": "blocked",
                "safety": {"level": "blocked", "reasons": ["result_path is outside the configured workspace"]},
                "reasons": ["result_path is outside the configured workspace"],
            }
        if is_path_within(resolved, state_dir(self.root).resolve()):
            return {
                "status": "blocked",
                "safety": {"level": "blocked", "reasons": ["result_path is inside .lab-sidecar"]},
                "reasons": ["result_path is inside .lab-sidecar"],
            }
        return None


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
