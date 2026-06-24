from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from lab_sidecar.core.artifacts import upsert_artifact
from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord, TaskRecord, TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path
from lab_sidecar.core.traceability import refresh_traceability
from lab_sidecar.reports.templates import SUPPORTED_TEMPLATES, UNKNOWN, render_report
from lab_sidecar.storage.sqlite_index import upsert_task


MAX_DISPLAY_COLUMNS = 20
MAX_NUMERIC_SUMMARY_COLUMNS = 8
STDERR_TAIL_LINES = 20


class InvalidReportTemplateError(RuntimeError):
    pass


class ReportMetricsRequiredError(RuntimeError):
    pass


class ReportWriteError(RuntimeError):
    pass


@dataclass
class ReportGenerationResult:
    record: TaskRecord
    template: str
    report_path: Path
    summary_path: Path
    summary: dict[str, Any]


class ReportGenerationService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def generate(self, task_id: str, template: str = "zh-lab") -> ReportGenerationResult:
        if template not in SUPPORTED_TEMPLATES:
            allowed = ", ".join(sorted(SUPPORTED_TEMPLATES))
            raise InvalidReportTemplateError(f"unsupported template '{template}'. Allowed: {allowed}")

        record = load_task(self.root, task_id)
        task_path = resolve_workspace_path(record.paths.task_dir, self.root)
        reports_dir = task_path / "reports"
        metrics_path = task_path / "metrics" / "normalized_metrics.csv"

        failure_status = record.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}
        if not metrics_path.exists() and not failure_status:
            raise ReportMetricsRequiredError("metrics/normalized_metrics.csv is missing")

        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / "report-fragment.md"
        summary_path = reports_dir / "report-summary.json"

        summary = self._build_summary(
            record=record,
            task_path=task_path,
            reports_dir=reports_dir,
            template=template,
            metrics_path=metrics_path,
        )
        markdown = render_report(template, summary)

        try:
            report_path.write_text(markdown, encoding="utf-8")
            summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise ReportWriteError(f"report files could not be written: {exc}") from exc

        self._upsert_artifacts(record, task_path)
        record.updated_at = _now_iso()
        record = refresh_traceability(self.root, record)
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)

        return ReportGenerationResult(
            record=record,
            template=template,
            report_path=report_path,
            summary_path=summary_path,
            summary=summary,
        )

    def _build_summary(
        self,
        record: TaskRecord,
        task_path: Path,
        reports_dir: Path,
        template: str,
        metrics_path: Path,
    ) -> dict[str, Any]:
        collection_summary_path = task_path / "metrics" / "collection-summary.json"
        scenario_summary_path = task_path / "metrics" / "scenario-summary.json"
        figure_summary_path = task_path / "figures" / "figure-summary.json"
        stderr_path = resolve_workspace_path(record.paths.stderr, self.root)
        reproduce_command_path = task_path / "reproduce" / "command.txt"
        generated_at = _now_iso()
        stderr_tail = _tail_lines(stderr_path, STDERR_TAIL_LINES)
        source_artifacts = self._source_artifacts(task_path)
        provenance = self._build_provenance(record)
        metrics = self._build_metrics_summary(metrics_path, collection_summary_path, scenario_summary_path)
        figures = self._build_figure_summary(record.task_id, figure_summary_path, task_path, reports_dir)
        failure = {
            "failure_summary": record.failure_summary or UNKNOWN,
            "stderr_tail": stderr_tail,
            "stderr_tail_line_count": len(stderr_tail),
            "reproduce_command_path": "reproduce/command.txt" if reproduce_command_path.exists() else UNKNOWN,
        }
        cancellation = {
            "note": _first_matching_line(stderr_tail, "cancellation") or (stderr_tail[-1] if stderr_tail else UNKNOWN),
            "stderr_tail": stderr_tail,
            "stderr_tail_line_count": len(stderr_tail),
        }
        reproduce = {
            "command_path": "reproduce/command.txt" if reproduce_command_path.exists() else UNKNOWN,
        }

        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "template": template,
            "generated_at": generated_at,
            "report_path": "reports/report-fragment.md",
            "summary_path": "reports/report-summary.json",
            "generated_from": source_artifacts,
            "provenance": provenance,
            "metrics": metrics,
            "figures": figures,
            "failure": failure,
            "cancellation": cancellation,
            "reproduce": reproduce,
            "claim_traces": _build_report_claim_traces(
                status=record.status,
                metrics=metrics,
                figures=figures,
                failure=failure,
                cancellation=cancellation,
            ),
            "source_artifacts": source_artifacts,
        }

    def _build_provenance(self, record: TaskRecord) -> dict[str, Any]:
        return {
            "task_id": record.task_id,
            "status": record.status.value,
            "mode": record.mode,
            "command": record.command or UNKNOWN,
            "source_path": record.source_path or UNKNOWN,
            "working_dir": record.working_dir or UNKNOWN,
            "created_at": record.created_at or UNKNOWN,
            "started_at": record.started_at or UNKNOWN,
            "finished_at": record.finished_at or UNKNOWN,
            "exit_code": record.exit_code if record.exit_code is not None else UNKNOWN,
        }

    def _build_metrics_summary(
        self,
        metrics_path: Path,
        collection_summary_path: Path,
        scenario_summary_path: Path,
    ) -> dict[str, Any]:
        scenario = _read_json(scenario_summary_path) if scenario_summary_path.exists() else {}
        if not metrics_path.exists():
            return {
                "present": False,
                "path": "metrics/normalized_metrics.csv",
                "collection_summary_path": "metrics/collection-summary.json" if collection_summary_path.exists() else None,
                "scenario_summary_path": "metrics/scenario-summary.json" if scenario_summary_path.exists() else None,
                "scenario": _report_scenario_summary(scenario),
                "row_count": 0,
                "columns": [],
                "displayed_columns": [],
                "omitted_column_count": 0,
                "numeric_summaries": [],
                "numeric_omitted_count": 0,
                "detected_fields": [],
            }

        df = pd.read_csv(metrics_path)
        columns = [str(column) for column in df.columns]
        numeric_summaries = _numeric_summaries(df)
        collection_summary = _read_json(collection_summary_path) if collection_summary_path.exists() else {}
        return {
            "present": True,
            "path": "metrics/normalized_metrics.csv",
            "collection_summary_path": "metrics/collection-summary.json" if collection_summary_path.exists() else None,
            "scenario_summary_path": "metrics/scenario-summary.json" if scenario_summary_path.exists() else None,
            "scenario": _report_scenario_summary(scenario),
            "row_count": int(len(df)),
            "columns": columns,
            "displayed_columns": columns[:MAX_DISPLAY_COLUMNS],
            "omitted_column_count": max(0, len(columns) - MAX_DISPLAY_COLUMNS),
            "numeric_summaries": numeric_summaries[:MAX_NUMERIC_SUMMARY_COLUMNS],
            "numeric_omitted_count": max(0, len(numeric_summaries) - MAX_NUMERIC_SUMMARY_COLUMNS),
            "detected_fields": collection_summary.get("detected_fields", []),
            "processed_files": collection_summary.get("processed_files", []),
            "candidate_count": collection_summary.get("candidate_count"),
        }

    def _build_figure_summary(
        self,
        task_id: str,
        figure_summary_path: Path,
        task_path: Path,
        reports_dir: Path,
    ) -> dict[str, Any]:
        if not figure_summary_path.exists():
            return {
                "present": False,
                "task_id": task_id,
                "summary_path": None,
                "figure_count": 0,
                "items": [],
                "warnings": [],
                "errors": [],
            }

        data = _read_json(figure_summary_path)
        raw_items = data.get("generated_figures") or data.get("figures") or []
        items = []
        for item in raw_items:
            png_path = item.get("png_path") or item.get("png")
            svg_path = item.get("svg_path") or item.get("svg")
            items.append(
                {
                    "figure_id": item.get("figure_id") or UNKNOWN,
                    "chart_type": item.get("chart_type") or UNKNOWN,
                    "png_path": self._report_relative_path(png_path, task_path, reports_dir) if png_path else UNKNOWN,
                    "svg_path": self._report_relative_path(svg_path, task_path, reports_dir) if svg_path else UNKNOWN,
                    "x": item.get("x") or UNKNOWN,
                    "y": item.get("y") or UNKNOWN,
                    "group_by": item.get("group_by") or UNKNOWN,
                }
            )

        return {
            "present": True,
            "task_id": task_id,
            "summary_path": "figures/figure-summary.json",
            "figure_count": len(items),
            "items": items,
            "warnings": data.get("warnings", []),
            "errors": data.get("errors", []),
        }

    def _report_relative_path(self, path_text: str, task_path: Path, reports_dir: Path) -> str:
        absolute = _resolve_task_or_workspace_path(path_text, self.root, task_path)
        return Path(os.path.relpath(absolute, reports_dir)).as_posix()

    def _source_artifacts(self, task_path: Path) -> list[str]:
        candidates = [
            task_path / "manifest.json",
            task_path / "metrics" / "normalized_metrics.csv",
            task_path / "metrics" / "collection-summary.json",
            task_path / "metrics" / "scenario-summary.json",
            task_path / "figures" / "figure-summary.json",
            task_path / "stderr.log",
            task_path / "stdout.log",
            task_path / "raw" / "source_refs.json",
            task_path / "reproduce" / "command.txt",
            task_path / "reproduce" / "env.json",
            task_path / "reproduce" / "git.json",
            task_path / "reproduce" / "dependencies.json",
        ]
        return [_task_relative(path, task_path) for path in candidates if path.exists()]

    def _upsert_artifacts(self, record: TaskRecord, task_path: Path) -> None:
        source_paths = self._source_artifacts(task_path)
        upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="report_fragment_md",
                type="report",
                path="reports/report-fragment.md",
                description="Markdown report fragment",
                source_paths=source_paths,
            ),
        )
        upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="report_summary_json",
                type="config",
                path="reports/report-summary.json",
                description="Report generation summary and provenance",
                source_paths=source_paths,
            ),
        )


def _numeric_summaries(df: pd.DataFrame) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for column in df.columns:
        values = pd.to_numeric(df[column], errors="coerce")
        count = int(values.notna().sum())
        if count == 0:
            continue
        summaries.append(
            {
                "column": str(column),
                "count": count,
                "mean": _json_float(values.mean()),
                "min": _json_float(values.min()),
                "max": _json_float(values.max()),
            }
        )
    return summaries


def _build_report_claim_traces(
    status: TaskStatus,
    metrics: dict[str, Any],
    figures: dict[str, Any],
    failure: dict[str, Any],
    cancellation: dict[str, Any],
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    metrics_path = str(metrics.get("path") or "metrics/normalized_metrics.csv")
    collection_path = metrics.get("collection_summary_path")
    if metrics.get("present"):
        row_count = int(metrics.get("row_count") or 0)
        traces.append(
            {
                "claim_id": "report.metrics.row_count",
                "surface": "report",
                "claim_type": "metrics_row_count",
                "value": row_count,
                "evidence": [
                    {
                        "artifact_id": "metrics_normalized_csv",
                        "path": metrics_path,
                        "row_count": row_count,
                    }
                ],
            }
        )
        traces.append(
            {
                "claim_id": "report.metrics.detected_fields",
                "surface": "report",
                "claim_type": "detected_fields",
                "value": metrics.get("detected_fields") or [],
                "evidence": [
                    {
                        "artifact_id": "metrics_collection_summary",
                        "path": collection_path or "metrics/collection-summary.json",
                        "field": "detected_fields",
                    }
                ],
            }
        )
        if metrics.get("numeric_omitted_count", 0):
            traces.append(
                {
                    "claim_id": "report.metrics.numeric_fields_omitted",
                    "surface": "report",
                    "claim_type": "omission",
                    "value": int(metrics.get("numeric_omitted_count") or 0),
                    "evidence": [
                        {
                            "artifact_id": "metrics_normalized_csv",
                            "path": metrics_path,
                            "reason": "numeric summary display limit",
                        }
                    ],
                }
            )
        for item in metrics.get("numeric_summaries") or []:
            if not isinstance(item, dict) or not item.get("column"):
                continue
            column = str(item["column"])
            for operation in ["mean", "min", "max"]:
                traces.append(
                    {
                        "claim_id": f"report.metric.{column}.{operation}",
                        "surface": "report",
                        "claim_type": "numeric_summary",
                        "operation": operation,
                        "field": column,
                        "value": item.get(operation),
                        "evidence": [
                            {
                                "artifact_id": "metrics_normalized_csv",
                                "path": metrics_path,
                                "columns": [column],
                                "summary_operation": operation,
                                "numeric_count": item.get("count"),
                                "row_count": row_count,
                            }
                        ],
                    }
                )
        scenario = metrics.get("scenario") if isinstance(metrics.get("scenario"), dict) else {}
        if scenario.get("present"):
            traces.append(
                {
                    "claim_id": "report.metrics.scenario_summary",
                    "surface": "report",
                    "claim_type": "scenario_summary",
                    "value": {
                        "scenario_type": scenario.get("scenario_type"),
                        "primary_metric": scenario.get("primary_metric"),
                    },
                    "evidence": [
                        {
                            "artifact_id": "metrics_scenario_summary",
                            "path": metrics.get("scenario_summary_path") or "metrics/scenario-summary.json",
                            "body": "omitted",
                        }
                    ],
                }
            )
    else:
        traces.append(
            {
                "claim_id": "report.metrics.unavailable",
                "surface": "report",
                "claim_type": "unknown_or_unavailable",
                "value": None,
                "evidence": [
                    {
                        "artifact_id": "metrics_normalized_csv",
                        "path": metrics_path,
                        "reason": "metrics artifact not present",
                    }
                ],
            }
        )

    traces.append(
        {
            "claim_id": "report.figures.count",
            "surface": "report",
            "claim_type": "figure_count",
            "value": int(figures.get("figure_count") or 0),
            "evidence": [
                {
                    "artifact_id": "figures_summary",
                    "path": figures.get("summary_path") or "figures/figure-summary.json",
                    "figure_ids": [item.get("figure_id") for item in figures.get("items") or []],
                }
            ],
        }
    )

    if status == TaskStatus.FAILED:
        traces.append(
            {
                "claim_id": "report.diagnostic.failed_status",
                "surface": "report",
                "claim_type": "diagnostic_status",
                "value": "failed",
                "evidence": [
                    {
                        "artifact_id": "log_stderr",
                        "path": "stderr.log",
                        "tail_line_count": failure.get("stderr_tail_line_count", 0),
                        "body": "omitted",
                    },
                    {
                        "artifact_id": "reproduce_command",
                        "path": failure.get("reproduce_command_path") or "reproduce/command.txt",
                    },
                ],
            }
        )
    elif status == TaskStatus.CANCELLED:
        traces.append(
            {
                "claim_id": "report.diagnostic.cancelled_status",
                "surface": "report",
                "claim_type": "diagnostic_status",
                "value": "cancelled",
                "evidence": [
                    {
                        "artifact_id": "log_stderr",
                        "path": "stderr.log",
                        "tail_line_count": cancellation.get("stderr_tail_line_count", 0),
                        "body": "omitted",
                    }
                ],
            }
        )
    return traces


def _json_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _report_scenario_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    if not scenario:
        return {"present": False}
    seed_aggregates = scenario.get("seed_aggregates") if isinstance(scenario.get("seed_aggregates"), dict) else {}
    return {
        "present": True,
        "path": "metrics/scenario-summary.json",
        "scenario_type": scenario.get("scenario_type"),
        "primary_metric": scenario.get("primary_metric") if isinstance(scenario.get("primary_metric"), dict) else {},
        "groups": scenario.get("groups") if isinstance(scenario.get("groups"), dict) else {},
        "best_rows": (scenario.get("best_rows") or [])[:3],
        "last_rows": (scenario.get("last_rows") or [])[:3],
        "seed_aggregates": {
            "present": seed_aggregates.get("present", False),
            "metric": seed_aggregates.get("metric"),
            "direction": seed_aggregates.get("direction"),
            "items": (seed_aggregates.get("items") or [])[:3],
            "claim_limit": seed_aggregates.get("claim_limit"),
        },
        "warnings": (scenario.get("warnings") or [])[:5],
        "omitted": scenario.get("omitted") if isinstance(scenario.get("omitted"), dict) else {},
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _tail_lines(path: Path, count: int) -> list[str]:
    if count <= 0 or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:]


def _first_matching_line(lines: list[str], needle: str) -> str | None:
    lowered = needle.lower()
    for line in reversed(lines):
        if lowered in line.lower():
            return line
    return None


def _resolve_task_or_workspace_path(path_text: str, root: Path, task_path: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path

    workspace_candidate = (root / path).resolve()
    if workspace_candidate.exists() or path_text.startswith(".lab-sidecar/"):
        return workspace_candidate
    return (task_path / path).resolve()


def _task_relative(path: Path, task_path: Path) -> str:
    return path.resolve().relative_to(task_path.resolve()).as_posix()



def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
