from __future__ import annotations

import csv
import json
import math
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from lab_sidecar.comparisons.models import (
    ComparisonBuildResult,
    ComparisonDuplicateTaskIds,
    ComparisonInvalidId,
    ComparisonManifest,
    ComparisonMetricsMissing,
    ComparisonNotFound,
    ComparisonOutputError,
    ComparisonTaskNotFound,
    NoCommonComparisonMetrics,
)
from lab_sidecar.comparisons.paths import comparisons_dir, comparison_dir, is_valid_comparison_id
from lab_sidecar.core.manifest import load_task
from lab_sidecar.core.models import ArtifactRecord
from lab_sidecar.core.paths import resolve_workspace_path, tasks_dir, to_manifest_path
from lab_sidecar.core.provenance import file_provenance, python_executable
from lab_sidecar.figures.render import render_figure
from lab_sidecar.figures.specs import FigureOutput, FigureSpec, friendly_label


COMPARISON_SCHEMA_VERSION = "1"
ROW_SELECTION = "final_row"
MAX_COMPARE_TASKS = 5
MIN_COMPARE_TASKS = 2
MAX_COMPARED_METRICS = 20
MAX_SUMMARY_METRICS = 12
MAX_FIGURES = 3
MAX_WARNINGS = 20
MAX_SKIPPED_FIELDS = 40
MAX_STRING_CHARS = 180
SUMMARY_RELATIVE_PATH = Path("comparison-summary.json")
TABLE_CSV_RELATIVE_PATH = Path("comparison-table.csv")
TABLE_JSON_RELATIVE_PATH = Path("comparison-table.json")
MANIFEST_RELATIVE_PATH = Path("comparison-manifest.json")
FIGURE_SUMMARY_RELATIVE_PATH = Path("figures") / "figure-summary.json"
REPORT_RELATIVE_PATH = Path("reports") / "comparison-report-fragment.md"
REPORT_SUMMARY_RELATIVE_PATH = Path("reports") / "comparison-report-summary.json"
TRACEABILITY_RELATIVE_PATH = Path("provenance") / "traceability.json"
SOURCE_METRICS_RELATIVE_PATH = Path("metrics") / "normalized_metrics.csv"
SOURCE_SCENARIO_RELATIVE_PATH = Path("metrics") / "scenario-summary.json"
SOURCE_COLLECTION_RELATIVE_PATH = Path("metrics") / "collection-summary.json"
METADATA_COLUMNS = {
    "source_file",
    "source_path",
    "file",
    "path",
    "epoch",
    "step",
    "iter",
    "iteration",
    "checkpoint",
    "ckpt",
    "timestamp",
    "seed",
    "trial",
    "run_id",
    "config_id",
}
HIGHER_IS_BETTER_HINTS = (
    "accuracy",
    "acc",
    "f1",
    "precision",
    "recall",
    "auc",
    "score",
    "throughput",
)
LOWER_IS_BETTER_HINTS = (
    "loss",
    "error",
    "runtime",
    "latency",
    "duration",
    "time",
    "memory",
)


@dataclass(frozen=True)
class ComparisonArtifactPresence:
    comparison_id: str
    comparison_dir: Path
    paths: list[str]
    artifact_count: int
    figure_count: int
    report_present: bool


class ComparisonService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def create(
        self,
        task_ids: list[str],
        *,
        name: str | None = None,
        generate_figures: bool = False,
        generate_report: bool = False,
    ) -> ComparisonBuildResult:
        if len(task_ids) < MIN_COMPARE_TASKS:
            raise ValueError("comparison requires at least 2 task ids")
        if len(task_ids) > MAX_COMPARE_TASKS:
            raise ValueError("comparison supports at most 5 task ids")
        if len(set(task_ids)) != len(task_ids):
            raise ComparisonDuplicateTaskIds("comparison task ids must be unique")

        comparison_id = generate_comparison_id()
        output_dir = comparison_dir(self.root, comparison_id)
        created_at = _now_iso()
        task_inputs = self._load_task_inputs(task_ids)
        plan = self._build_comparison_plan(
            comparison_id=comparison_id,
            created_at=created_at,
            name=name,
            task_inputs=task_inputs,
        )
        if output_dir.exists():
            raise ComparisonOutputError(f"comparison directory already exists: {output_dir}")
        try:
            output_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise ComparisonOutputError(str(exc)) from exc
        manifest = ComparisonManifest(
            comparison_id=comparison_id,
            created_at=created_at,
            updated_at=created_at,
            name=name,
            task_ids=task_ids,
            paths={
                "comparison_dir": to_manifest_path(output_dir, self.root),
                "manifest": MANIFEST_RELATIVE_PATH.as_posix(),
                "summary": SUMMARY_RELATIVE_PATH.as_posix(),
                "table_csv": TABLE_CSV_RELATIVE_PATH.as_posix(),
                "table_json": TABLE_JSON_RELATIVE_PATH.as_posix(),
                "traceability": TRACEABILITY_RELATIVE_PATH.as_posix(),
            },
            source_tasks=plan["source_tasks"],
            warnings=plan["warnings"],
        )

        try:
            _write_csv(output_dir / TABLE_CSV_RELATIVE_PATH, plan["table_rows"])
            _write_json(output_dir / TABLE_JSON_RELATIVE_PATH, plan["table_json"])
            _write_json(output_dir / SUMMARY_RELATIVE_PATH, plan["summary"])
            figure_summary_path = (
                self._generate_figures(output_dir, manifest, plan) if generate_figures else None
            )
            report_paths = self._generate_report(output_dir, manifest, plan) if generate_report else None
            manifest = refresh_comparison_artifacts(self.root, manifest)
        except OSError as exc:
            raise ComparisonOutputError(str(exc)) from exc

        return ComparisonBuildResult(
            manifest=manifest,
            comparison_dir=output_dir,
            summary_path=output_dir / SUMMARY_RELATIVE_PATH,
            table_csv_path=output_dir / TABLE_CSV_RELATIVE_PATH,
            table_json_path=output_dir / TABLE_JSON_RELATIVE_PATH,
            figure_summary_path=figure_summary_path,
            report_path=report_paths[0] if report_paths else None,
            report_summary_path=report_paths[1] if report_paths else None,
            traceability_path=output_dir / TRACEABILITY_RELATIVE_PATH,
        )

    def load(self, comparison_id: str) -> ComparisonManifest:
        return load_comparison(self.root, comparison_id)

    def refresh(self, manifest: ComparisonManifest) -> ComparisonManifest:
        return refresh_comparison_artifacts(self.root, manifest)

    def _load_task_inputs(self, task_ids: list[str]) -> list[dict[str, Any]]:
        inputs: list[dict[str, Any]] = []
        for task_id in task_ids:
            try:
                record = load_task(self.root, task_id)
            except FileNotFoundError as exc:
                raise ComparisonTaskNotFound(f"task '{task_id}' was not found") from exc
            task_path = resolve_workspace_path(record.paths.task_dir, self.root).resolve()
            _ensure_task_boundary(task_path, self.root, task_id)
            metrics_path = task_path / SOURCE_METRICS_RELATIVE_PATH
            if not metrics_path.is_file():
                raise ComparisonMetricsMissing(f"metrics/normalized_metrics.csv is missing for task '{task_id}'")
            fields, rows = _read_csv_rows(metrics_path)
            if not rows:
                raise ComparisonMetricsMissing(f"metrics/normalized_metrics.csv has no rows for task '{task_id}'")
            scenario = _read_json(task_path / SOURCE_SCENARIO_RELATIVE_PATH)
            collection = _read_json(task_path / SOURCE_COLLECTION_RELATIVE_PATH)
            final_row = rows[-1]
            metrics_provenance = file_provenance(metrics_path)
            inputs.append(
                {
                    "record": record,
                    "task_path": task_path,
                    "metrics_path": metrics_path,
                    "fields": fields,
                    "rows": rows,
                    "final_row": final_row,
                    "final_row_number": len(rows),
                    "scenario": scenario,
                    "collection": collection,
                    "metrics_provenance": metrics_provenance,
                }
            )
        return inputs

    def _build_comparison_plan(
        self,
        *,
        comparison_id: str,
        created_at: str,
        name: str | None,
        task_inputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        common_fields = set(task_inputs[0]["fields"])
        for item in task_inputs[1:]:
            common_fields &= set(item["fields"])
        ordered_common = [field for field in task_inputs[0]["fields"] if field in common_fields]
        excluded_fields = [field for field in ordered_common if field in METADATA_COLUMNS]
        candidate_fields = [field for field in ordered_common if field not in METADATA_COLUMNS]

        common_numeric_fields: list[str] = []
        skipped_common_fields: list[dict[str, str]] = []
        for field in candidate_fields:
            values = [item["final_row"].get(field) for item in task_inputs]
            if not all(str(value or "").strip() for value in values):
                skipped_common_fields.append({"field": field, "reason": "missing final-row value"})
                continue
            if not all(_parse_number(value) is not None for value in values):
                skipped_common_fields.append({"field": field, "reason": "non-numeric final-row value"})
                continue
            common_numeric_fields.append(field)

        if not common_numeric_fields:
            raise NoCommonComparisonMetrics("no common numeric metric fields were found across the selected tasks")

        compared_fields = common_numeric_fields[:MAX_COMPARED_METRICS]
        omitted_metric_count = max(0, len(common_numeric_fields) - len(compared_fields))
        warnings: list[str] = []
        if omitted_metric_count:
            warnings.append(
                f"comparison metrics truncated from {len(common_numeric_fields)} to {MAX_COMPARED_METRICS}"
            )
        for item in task_inputs:
            record = item["record"]
            if getattr(record, "status", None) and record.status.value != "completed":
                warnings.append(f"source task {record.task_id} status is {record.status.value}")
            if not item["scenario"]:
                warnings.append(f"source task {record.task_id} has no scenario summary")

        table_rows: list[dict[str, Any]] = []
        for item in task_inputs:
            record = item["record"]
            task_name = record.name or ""
            for field in compared_fields:
                parsed = _parse_number(item["final_row"].get(field))
                if parsed is None:
                    continue
                table_rows.append(
                    {
                        "task_id": record.task_id,
                        "task_name": task_name,
                        "status": record.status.value,
                        "metric": field,
                        "value": _json_number(parsed),
                        "source_metrics_path": to_manifest_path(item["metrics_path"], self.root),
                        "row_selection": ROW_SELECTION,
                        "source_row_number": item["final_row_number"],
                    }
                )

        source_tasks = [_source_task_summary(self.root, item) for item in task_inputs]
        skipped_by_task = _skipped_by_task(task_inputs, common_fields)
        skipped_fields = {
            "excluded_metadata_fields": _bounded_strings(excluded_fields, MAX_SKIPPED_FIELDS),
            "common_non_numeric_fields": skipped_common_fields[:MAX_SKIPPED_FIELDS],
            "task_specific_fields": skipped_by_task,
            "omitted_common_numeric_metric_count": omitted_metric_count,
        }
        metrics_summary = _metrics_summary(table_rows, compared_fields, task_inputs)
        summary = {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "comparison_id": comparison_id,
            "created_at": created_at,
            "name": name,
            "task_ids": [item["record"].task_id for item in task_inputs],
            "source_tasks": source_tasks,
            "common_numeric_fields": compared_fields,
            "all_common_numeric_field_count": len(common_numeric_fields),
            "skipped_fields": skipped_fields,
            "row_selection": {
                "method": ROW_SELECTION,
                "description": "final row from each source task metrics/normalized_metrics.csv",
            },
            "metrics": metrics_summary["metrics"][:MAX_SUMMARY_METRICS],
            "omitted_metric_summary_count": max(0, len(metrics_summary["metrics"]) - MAX_SUMMARY_METRICS),
            "best_by_metric": metrics_summary["best_by_metric"][:MAX_SUMMARY_METRICS],
            "warnings": _bounded_strings(warnings, MAX_WARNINGS),
            "omitted": _omitted_contract(),
            "evidence": {
                "comparison_table_csv": TABLE_CSV_RELATIVE_PATH.as_posix(),
                "comparison_table_json": TABLE_JSON_RELATIVE_PATH.as_posix(),
                "source_metrics": [
                    {
                        "task_id": item["record"].task_id,
                        "path": to_manifest_path(item["metrics_path"], self.root),
                        "row_selection": ROW_SELECTION,
                        "source_row_number": item["final_row_number"],
                        "sha256": item["metrics_provenance"]["sha256"],
                        "size_bytes": item["metrics_provenance"]["size_bytes"],
                    }
                    for item in task_inputs
                ],
            },
        }
        return {
            "source_tasks": source_tasks,
            "summary": summary,
            "table_rows": table_rows,
            "table_json": {
                "schema_version": COMPARISON_SCHEMA_VERSION,
                "comparison_id": comparison_id,
                "row_selection": ROW_SELECTION,
                "rows": table_rows,
            },
            "warnings": _bounded_strings(warnings, MAX_WARNINGS),
        }

    def _generate_figures(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        plan: dict[str, Any],
    ) -> Path:
        figures_dir = output_dir / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        table_rows = plan["table_rows"]
        figure_metrics = _figure_metric_order(plan["summary"])[:MAX_FIGURES]
        generated: list[dict[str, Any]] = []
        warnings: list[str] = []
        for metric in figure_metrics:
            data_rows = [row for row in table_rows if row["metric"] == metric]
            if len(data_rows) < 2:
                warnings.append(f"skipped figure for {metric}: fewer than 2 task values")
                continue
            df = pd.DataFrame(
                [
                    {
                        "task_label": _task_label(row),
                        metric: row["value"],
                    }
                    for row in data_rows
                ]
            )
            slug = _slug(metric)
            spec = FigureSpec(
                figure_id=f"comparison_{slug}",
                chart_type="bar",
                title=f"Comparison: {friendly_label(metric)}",
                x="task_label",
                y=metric,
                output=FigureOutput(
                    png=f"figures/comparison_{slug}.png",
                    svg=f"figures/comparison_{slug}.svg",
                ),
                source=TABLE_CSV_RELATIVE_PATH.as_posix(),
            )
            try:
                png_path, svg_path = render_figure(df, spec, output_dir)
            except Exception as exc:
                warnings.append(f"failed to render comparison figure for {metric}: {exc}")
                continue
            generated.append(
                {
                    "figure_id": spec.figure_id,
                    "chart_type": spec.chart_type,
                    "png_path": png_path.relative_to(output_dir).as_posix(),
                    "svg_path": svg_path.relative_to(output_dir).as_posix(),
                    "source_table": TABLE_CSV_RELATIVE_PATH.as_posix(),
                    "metric": metric,
                    "x": "task_label",
                    "y": metric,
                    "row_selection": ROW_SELECTION,
                }
            )
        summary = {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "comparison_id": manifest.comparison_id,
            "generated_at": _now_iso(),
            "source_table": TABLE_CSV_RELATIVE_PATH.as_posix(),
            "figure_count": len(generated),
            "figures": generated,
            "generated_figures": generated,
            "omitted_metric_count": max(0, len(_figure_metric_order(plan["summary"])) - len(generated)),
            "warnings": warnings,
            "errors": [],
        }
        summary_path = output_dir / FIGURE_SUMMARY_RELATIVE_PATH
        _write_json(summary_path, summary)
        return summary_path

    def _generate_report(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        plan: dict[str, Any],
    ) -> tuple[Path, Path]:
        reports_dir = output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / REPORT_RELATIVE_PATH
        summary_path = output_dir / REPORT_SUMMARY_RELATIVE_PATH
        summary = plan["summary"]
        figure_summary = _read_json(output_dir / FIGURE_SUMMARY_RELATIVE_PATH)
        markdown = _comparison_report_markdown(manifest, summary, plan["table_rows"], figure_summary)
        report_path.write_text(markdown, encoding="utf-8")
        report_summary = {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "comparison_id": manifest.comparison_id,
            "generated_at": _now_iso(),
            "report_path": REPORT_RELATIVE_PATH.as_posix(),
            "summary_path": REPORT_SUMMARY_RELATIVE_PATH.as_posix(),
            "source_artifacts": [
                SUMMARY_RELATIVE_PATH.as_posix(),
                TABLE_CSV_RELATIVE_PATH.as_posix(),
                TABLE_JSON_RELATIVE_PATH.as_posix(),
                *([FIGURE_SUMMARY_RELATIVE_PATH.as_posix()] if figure_summary else []),
            ],
            "claim_traces": _comparison_report_claim_traces(summary),
            "non_claim_note": "This comparison is descriptive only; no statistical significance or model superiority is inferred.",
            "warnings": summary.get("warnings") or [],
        }
        _write_json(summary_path, report_summary)
        return report_path, summary_path


def generate_comparison_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(3)
    return f"comparison_{stamp}_{suffix}"


def load_comparison(root: Path, comparison_id: str) -> ComparisonManifest:
    if not is_valid_comparison_id(comparison_id):
        raise ComparisonInvalidId(f"invalid comparison id: {comparison_id!r}")
    path = comparison_artifact_dir(root, comparison_id) / MANIFEST_RELATIVE_PATH
    manifest = ComparisonManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.comparison_id != comparison_id:
        raise ComparisonInvalidId(
            f"comparison manifest id {manifest.comparison_id!r} does not match requested id {comparison_id!r}"
        )
    return manifest


def list_comparison_ids(root: Path) -> list[str]:
    output_dir = comparisons_dir(root).resolve()
    if not output_dir.is_dir():
        return []
    candidates: list[tuple[float, str]] = []
    for path in output_dir.iterdir():
        if path.is_symlink() or not path.is_dir() or not is_valid_comparison_id(path.name):
            continue
        try:
            path.resolve().relative_to(output_dir)
        except ValueError:
            continue
        manifest_path = path / MANIFEST_RELATIVE_PATH
        try:
            sort_time = manifest_path.stat().st_mtime if manifest_path.is_file() else path.stat().st_mtime
        except OSError:
            continue
        candidates.append((sort_time, path.name))
    return [comparison_id for _sort_time, comparison_id in sorted(candidates, reverse=True)]


def load_comparison_manifest(root: Path, comparison_id: str) -> ComparisonManifest:
    return load_comparison(root, comparison_id)


def comparison_artifact_dir(root: Path, comparison_id: str) -> Path:
    if not is_valid_comparison_id(comparison_id):
        raise ComparisonInvalidId(f"invalid comparison id: {comparison_id!r}")
    comparisons_root = comparisons_dir(root).resolve()
    output_dir = comparison_dir(root, comparison_id).resolve()
    try:
        output_dir.relative_to(comparisons_root)
    except ValueError as exc:
        raise ComparisonInvalidId(f"invalid comparison id: {comparison_id!r}") from exc
    if not (output_dir / MANIFEST_RELATIVE_PATH).is_file():
        raise ComparisonNotFound(f"comparison '{comparison_id}' was not found")
    return output_dir


def comparison_artifact_presence(root: Path, comparison_id: str) -> ComparisonArtifactPresence:
    output_dir = comparison_artifact_dir(root, comparison_id)
    paths: list[str] = []
    for relative in [
        MANIFEST_RELATIVE_PATH,
        SUMMARY_RELATIVE_PATH,
        TABLE_CSV_RELATIVE_PATH,
        TABLE_JSON_RELATIVE_PATH,
        FIGURE_SUMMARY_RELATIVE_PATH,
    ]:
        if (output_dir / relative).is_file():
            paths.append(relative.as_posix())

    figures_dir = output_dir / "figures"
    figure_paths: list[Path] = []
    if figures_dir.is_dir():
        figure_paths = sorted([*figures_dir.glob("*.png"), *figures_dir.glob("*.svg")], key=lambda path: path.as_posix())
        paths.extend(path.relative_to(output_dir).as_posix() for path in figure_paths if path.is_file())

    for relative in [
        REPORT_RELATIVE_PATH,
        REPORT_SUMMARY_RELATIVE_PATH,
        TRACEABILITY_RELATIVE_PATH,
    ]:
        if (output_dir / relative).is_file():
            paths.append(relative.as_posix())

    return ComparisonArtifactPresence(
        comparison_id=comparison_id,
        comparison_dir=output_dir,
        paths=paths,
        artifact_count=len(paths),
        figure_count=len([path for path in figure_paths if path.is_file()]),
        report_present=(output_dir / REPORT_RELATIVE_PATH).is_file(),
    )


def refresh_comparison_artifacts(root: Path, manifest: ComparisonManifest) -> ComparisonManifest:
    root = root.resolve()
    output_dir = comparison_dir(root, manifest.comparison_id)
    artifacts = _comparison_artifacts(output_dir)
    manifest = manifest.model_copy(
        update={
            "updated_at": _now_iso(),
            "artifacts": artifacts,
            "paths": {
                **manifest.paths,
                "traceability": TRACEABILITY_RELATIVE_PATH.as_posix(),
            },
        }
    )
    traceability_path = output_dir / TRACEABILITY_RELATIVE_PATH
    traceability_path.parent.mkdir(parents=True, exist_ok=True)
    traceability = _comparison_traceability(root, output_dir, manifest, artifacts)
    _write_json(traceability_path, traceability)
    trace_artifact = _artifact(
        output_dir,
        TRACEABILITY_RELATIVE_PATH,
        "provenance_traceability_json",
        "provenance",
        "Comparison-local provenance and traceability index",
        source_paths=[
            MANIFEST_RELATIVE_PATH.as_posix(),
            SUMMARY_RELATIVE_PATH.as_posix(),
            TABLE_CSV_RELATIVE_PATH.as_posix(),
            TABLE_JSON_RELATIVE_PATH.as_posix(),
        ],
    )
    manifest.artifacts = [
        artifact for artifact in artifacts if artifact.artifact_id != "provenance_traceability_json"
    ]
    manifest.artifacts.append(trace_artifact)
    _write_manifest(output_dir / MANIFEST_RELATIVE_PATH, manifest)
    return manifest


def _comparison_artifacts(output_dir: Path) -> list[ArtifactRecord]:
    specs: list[tuple[Path, str, str, str, list[str]]] = [
        (
            SUMMARY_RELATIVE_PATH,
            "comparison_summary_json",
            "config",
            "Bounded comparison summary",
            [TABLE_CSV_RELATIVE_PATH.as_posix()],
        ),
        (
            TABLE_CSV_RELATIVE_PATH,
            "comparison_table_csv",
            "table",
            "Normalized comparison table",
            [],
        ),
        (
            TABLE_JSON_RELATIVE_PATH,
            "comparison_table_json",
            "table",
            "Normalized comparison table JSON",
            [TABLE_CSV_RELATIVE_PATH.as_posix()],
        ),
        (
            FIGURE_SUMMARY_RELATIVE_PATH,
            "comparison_figure_summary_json",
            "config",
            "Comparison figure generation summary",
            [TABLE_CSV_RELATIVE_PATH.as_posix()],
        ),
        (
            REPORT_RELATIVE_PATH,
            "comparison_report_fragment_md",
            "report",
            "Markdown comparison report fragment",
            [SUMMARY_RELATIVE_PATH.as_posix(), TABLE_CSV_RELATIVE_PATH.as_posix()],
        ),
        (
            REPORT_SUMMARY_RELATIVE_PATH,
            "comparison_report_summary_json",
            "config",
            "Comparison report summary and provenance",
            [REPORT_RELATIVE_PATH.as_posix()],
        ),
    ]
    artifacts = [
        _artifact(output_dir, relative, artifact_id, artifact_type, description, source_paths=source_paths)
        for relative, artifact_id, artifact_type, description, source_paths in specs
        if (output_dir / relative).is_file()
    ]
    figures_dir = output_dir / "figures"
    if figures_dir.is_dir():
        for path in sorted([*figures_dir.glob("*.png"), *figures_dir.glob("*.svg")], key=lambda item: item.name):
            suffix = path.suffix.lower().lstrip(".")
            artifacts.append(
                _artifact(
                    output_dir,
                    path.relative_to(output_dir),
                    f"comparison_figure_{path.stem}_{suffix}",
                    "figure",
                    "Generated comparison figure image",
                    source_paths=[TABLE_CSV_RELATIVE_PATH.as_posix(), FIGURE_SUMMARY_RELATIVE_PATH.as_posix()],
                )
            )
    return artifacts


def _artifact(
    output_dir: Path,
    relative: Path,
    artifact_id: str,
    artifact_type: str,
    description: str,
    *,
    source_paths: list[str],
) -> ArtifactRecord:
    path = output_dir / relative
    provenance = file_provenance(path) if path.is_file() else {"size_bytes": None, "sha256": None}
    return ArtifactRecord(
        artifact_id=artifact_id,
        type=artifact_type,
        path=relative.as_posix(),
        description=description,
        source_paths=source_paths,
        size_bytes=provenance["size_bytes"],
        sha256=provenance["sha256"],
    )


def _comparison_traceability(
    root: Path,
    output_dir: Path,
    manifest: ComparisonManifest,
    artifacts: list[ArtifactRecord],
) -> dict[str, Any]:
    summary = _read_json(output_dir / SUMMARY_RELATIVE_PATH)
    report_summary = _read_json(output_dir / REPORT_SUMMARY_RELATIVE_PATH)
    figure_summary = _read_json(output_dir / FIGURE_SUMMARY_RELATIVE_PATH)
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_id": manifest.comparison_id,
        "generated_at": _now_iso(),
        "comparison": {
            "name": manifest.name,
            "status": manifest.status.value,
            "row_selection": manifest.row_selection,
            "manifest_path": MANIFEST_RELATIVE_PATH.as_posix(),
            "summary_path": SUMMARY_RELATIVE_PATH.as_posix(),
            "table_csv_path": TABLE_CSV_RELATIVE_PATH.as_posix(),
            "table_json_path": TABLE_JSON_RELATIVE_PATH.as_posix(),
        },
        "environment": {
            "python_executable": python_executable(),
        },
        "source_tasks": manifest.source_tasks,
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "type": artifact.type,
                "path": artifact.path,
                "description": artifact.description,
                "source_paths": artifact.source_paths,
                "exists": (output_dir / artifact.path).is_file(),
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in artifacts
        ],
        "metric_lineage": {
            "row_selection": summary.get("row_selection"),
            "common_numeric_fields": summary.get("common_numeric_fields") or [],
            "source_metrics": (summary.get("evidence") or {}).get("source_metrics") or [],
            "comparison_table_csv": TABLE_CSV_RELATIVE_PATH.as_posix(),
            "comparison_table_json": TABLE_JSON_RELATIVE_PATH.as_posix(),
        },
        "figure_lineage": {
            "present": bool(figure_summary),
            "summary_path": FIGURE_SUMMARY_RELATIVE_PATH.as_posix() if figure_summary else None,
            "figure_count": figure_summary.get("figure_count") if figure_summary else 0,
            "figures": figure_summary.get("figures") or [],
        },
        "report_lineage": {
            "present": bool(report_summary),
            "path": report_summary.get("report_path") if report_summary else None,
            "summary_path": report_summary.get("summary_path") if report_summary else None,
            "source_artifacts": report_summary.get("source_artifacts") if report_summary else [],
            "claim_trace_count": len(report_summary.get("claim_traces") or []) if report_summary else 0,
        },
        "claim_traces": report_summary.get("claim_traces") or [],
        "omitted": [
            *(_omitted_contract_list(root)),
            {
                "path": ".lab-sidecar/tasks/*/metrics/normalized_metrics.csv",
                "category": "source_metrics",
                "reason": "source task full normalized metrics tables are referenced by path and digest but not copied or embedded",
            },
        ],
        "traceability_artifact": {
            "artifact_id": "provenance_traceability_json",
            "path": TRACEABILITY_RELATIVE_PATH.as_posix(),
            "self_digest_note": "self digest is recorded in manifest/package metadata, not inside the self-referential trace body",
        },
        "warnings": manifest.warnings,
    }


def _metrics_summary(
    table_rows: list[dict[str, Any]],
    compared_fields: list[str],
    task_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    scenario_directions = _scenario_directions(task_inputs)
    metrics: list[dict[str, Any]] = []
    best_by_metric: list[dict[str, Any]] = []
    for metric in compared_fields:
        rows = [row for row in table_rows if row["metric"] == metric]
        direction = scenario_directions.get(metric) or _metric_direction(metric)
        values = [
            {
                "task_id": row["task_id"],
                "task_name": row["task_name"],
                "value": row["value"],
                "evidence": {
                    "artifact_id": "metrics_normalized_csv",
                    "path": row["source_metrics_path"],
                    "row_number": row["source_row_number"],
                    "body": "omitted",
                },
            }
            for row in rows
        ]
        metrics.append(
            {
                "metric": metric,
                "direction": direction,
                "values": values,
                "value_count": len(values),
            }
        )
        selected = _selected_descriptive_value(rows, direction)
        if selected is not None:
            best_by_metric.append(
                {
                    "metric": metric,
                    "direction": direction,
                    "selection": "descriptive_final_row_sort",
                    "task_id": selected["task_id"],
                    "task_name": selected["task_name"],
                    "value": selected["value"],
                    "evidence": {
                        "artifact_id": "metrics_normalized_csv",
                        "path": selected["source_metrics_path"],
                        "row_number": selected["source_row_number"],
                        "body": "omitted",
                    },
                    "claim_limit": "descriptive comparison only; no statistical significance or model superiority is inferred",
                }
            )
    return {"metrics": metrics, "best_by_metric": best_by_metric}


def _source_task_summary(root: Path, item: dict[str, Any]) -> dict[str, Any]:
    record = item["record"]
    scenario = item["scenario"]
    primary_metric = scenario.get("primary_metric") if isinstance(scenario.get("primary_metric"), dict) else {}
    collection = item["collection"]
    return {
        "task_id": record.task_id,
        "task_name": record.name,
        "status": record.status.value,
        "mode": record.mode,
        "metrics_path": to_manifest_path(item["metrics_path"], root),
        "metrics_size_bytes": item["metrics_provenance"]["size_bytes"],
        "metrics_sha256": item["metrics_provenance"]["sha256"],
        "row_count": len(item["rows"]),
        "selected_row_number": item["final_row_number"],
        "row_selection": ROW_SELECTION,
        "scenario_summary_path": SOURCE_SCENARIO_RELATIVE_PATH.as_posix()
        if (item["task_path"] / SOURCE_SCENARIO_RELATIVE_PATH).is_file()
        else None,
        "collection_summary_path": SOURCE_COLLECTION_RELATIVE_PATH.as_posix()
        if (item["task_path"] / SOURCE_COLLECTION_RELATIVE_PATH).is_file()
        else None,
        "scenario_type": scenario.get("scenario_type"),
        "primary_metric": {
            "name": primary_metric.get("name"),
            "direction": primary_metric.get("direction"),
            "unit": primary_metric.get("unit"),
        },
        "detected_fields": _bounded_strings(collection.get("detected_fields") or [], MAX_SKIPPED_FIELDS),
    }


def _comparison_report_markdown(
    manifest: ComparisonManifest,
    summary: dict[str, Any],
    table_rows: list[dict[str, Any]],
    figure_summary: dict[str, Any],
) -> str:
    title = manifest.name or manifest.comparison_id
    lines = [
        f"# Comparison: {title}",
        "",
        f"Comparison id: `{manifest.comparison_id}`",
        f"Created: `{summary.get('created_at')}`",
        "",
        "This comparison is descriptive only; no statistical significance or model superiority is inferred.",
        "",
        "## Source Tasks",
        "",
        "| task_id | name | status | selected row | metrics |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for task in summary.get("source_tasks") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{task.get('task_id')}`",
                    _md(str(task.get("task_name") or "")),
                    f"`{task.get('status')}`",
                    str(task.get("selected_row_number") or ""),
                    f"`{task.get('metrics_path')}`",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Row Selection",
            "",
            "`final_row` from each source task's `metrics/normalized_metrics.csv`.",
            "",
            "## Common Numeric Metrics",
            "",
            ", ".join(f"`{metric}`" for metric in summary.get("common_numeric_fields") or []) or "(none)",
            "",
            "## Comparison Table",
            "",
            "| task_id | metric | value | source row |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in table_rows[:80]:
        lines.append(
            f"| `{row['task_id']}` | `{row['metric']}` | {row['value']} | {row['source_row_number']} |"
        )
    omitted_rows = max(0, len(table_rows) - 80)
    if omitted_rows:
        lines.append(f"| ... | ... | omitted {omitted_rows} row(s) from report display | ... |")
    if figure_summary:
        lines.extend(["", "## Figures", ""])
        for figure in figure_summary.get("figures") or []:
            lines.append(f"- `{figure.get('png_path')}` / `{figure.get('svg_path')}`")
    warnings = summary.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {_md(str(warning))}")
    lines.extend(
        [
            "",
            "## Omitted By Default",
            "",
            "- Full source task logs",
            "- Full source metric rows",
            "- Raw source files",
            "- SQLite indexes and unrelated workspace files",
        ]
    )
    return "\n".join(lines) + "\n"


def _comparison_report_claim_traces(summary: dict[str, Any]) -> list[dict[str, Any]]:
    traces = [
        {
            "claim_id": "comparison.source_task_count",
            "surface": "comparison_report",
            "claim_type": "source_task_count",
            "value": len(summary.get("task_ids") or []),
            "evidence": [
                {
                    "artifact_id": "comparison_summary_json",
                    "path": SUMMARY_RELATIVE_PATH.as_posix(),
                    "field": "task_ids",
                    "body": "omitted",
                }
            ],
        },
        {
            "claim_id": "comparison.row_selection",
            "surface": "comparison_report",
            "claim_type": "row_selection",
            "value": ROW_SELECTION,
            "evidence": [
                {
                    "artifact_id": "comparison_summary_json",
                    "path": SUMMARY_RELATIVE_PATH.as_posix(),
                    "field": "row_selection",
                    "body": "omitted",
                }
            ],
        },
    ]
    for item in (summary.get("best_by_metric") or [])[:MAX_SUMMARY_METRICS]:
        traces.append(
            {
                "claim_id": f"comparison.descriptive_sort.{item.get('metric')}",
                "surface": "comparison_report",
                "claim_type": "descriptive_final_row_sort",
                "value": {
                    "metric": item.get("metric"),
                    "task_id": item.get("task_id"),
                    "value": item.get("value"),
                    "direction": item.get("direction"),
                },
                "evidence": [item.get("evidence")],
            }
        )
    return traces


def _figure_metric_order(summary: dict[str, Any]) -> list[str]:
    primary = []
    for task in summary.get("source_tasks") or []:
        metric = ((task.get("primary_metric") or {}).get("name")) if isinstance(task, dict) else None
        if isinstance(metric, str) and metric in summary.get("common_numeric_fields", []):
            primary.append(metric)
    ordered = []
    for metric in [*primary, *(summary.get("common_numeric_fields") or [])]:
        if metric not in ordered:
            ordered.append(metric)
    return ordered


def _selected_descriptive_value(rows: list[dict[str, Any]], direction: str | None) -> dict[str, Any] | None:
    if not rows:
        return None
    if direction == "min":
        return min(rows, key=lambda row: (float(row["value"]), str(row["task_id"])))
    return max(rows, key=lambda row: (float(row["value"]), str(row["task_id"])))


def _scenario_directions(task_inputs: list[dict[str, Any]]) -> dict[str, str]:
    directions: dict[str, list[str]] = {}
    for item in task_inputs:
        primary = item["scenario"].get("primary_metric")
        if not isinstance(primary, dict):
            continue
        name = primary.get("name")
        direction = primary.get("direction")
        if isinstance(name, str) and direction in {"max", "min"}:
            directions.setdefault(name, []).append(direction)
    return {
        metric: values[0]
        for metric, values in directions.items()
        if len(values) == len(task_inputs) and len(set(values)) == 1
    }


def _metric_direction(metric: str) -> str:
    normalized = metric.lower()
    if any(hint in normalized for hint in LOWER_IS_BETTER_HINTS):
        return "min"
    if any(hint in normalized for hint in HIGHER_IS_BETTER_HINTS):
        return "max"
    return "max"


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                return [], []
            rows = [{key: value for key, value in row.items() if key is not None} for row in reader]
            return list(reader.fieldnames), rows
    except OSError as exc:
        raise FileNotFoundError(path) from exc


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task_id",
        "task_name",
        "status",
        "metric",
        "value",
        "source_metrics_path",
        "row_selection",
        "source_row_number",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_manifest(path: Path, manifest: ComparisonManifest) -> None:
    _write_json(path, manifest.model_dump(mode="json", exclude_none=False))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _json_number(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return float(value)


def _skipped_by_task(task_inputs: list[dict[str, Any]], common_fields: set[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for item in task_inputs:
        task_id = item["record"].task_id
        skipped = [field for field in item["fields"] if field not in common_fields]
        if skipped:
            result[task_id] = _bounded_strings(skipped, MAX_SKIPPED_FIELDS)
    return result


def _bounded_strings(values: list[Any], limit: int) -> list[str]:
    result = []
    for value in values[:limit]:
        result.append(_short(str(value)))
    return result


def _short(value: str, limit: int = MAX_STRING_CHARS) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip()).strip("_").lower()
    return slug or "metric"


def _task_label(row: dict[str, Any]) -> str:
    name = str(row.get("task_name") or "").strip()
    task_id = str(row.get("task_id") or "")
    if name:
        return f"{name} ({task_id[-6:]})"
    return task_id


def _md(value: str) -> str:
    return value.replace("|", "\\|")


def _omitted_contract() -> dict[str, str]:
    return {
        "full_stdout": "omitted_by_default",
        "full_stderr": "omitted_by_default",
        "full_source_metric_rows": "omitted_by_default",
        "raw_source_files": "omitted_by_default",
        "report_body": "omitted_by_default_in_summary",
        "ppt_contents": "omitted_by_default",
        "worker_prompt_response": "omitted_by_default",
        "artifact_bytes": "omitted_by_default",
    }


def _omitted_contract_list(root: Path) -> list[dict[str, Any]]:
    omitted = [
        {
            "path": ".lab-sidecar/tasks/*/stdout.log",
            "category": "log",
            "reason": "source task full stdout logs are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/stderr.log",
            "category": "log",
            "reason": "source task full stderr logs are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/raw",
            "category": "raw",
            "reason": "source task raw files are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/intelligence",
            "category": "worker",
            "reason": "source task worker audit files are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/intelligence/*/sandbox",
            "category": "sandbox",
            "reason": "source task temporary sandbox files are omitted by default",
        },
        {
            "path": "workspace/*",
            "category": "workspace",
            "reason": "unrelated workspace files are not copied or embedded",
        },
    ]
    if (root / ".lab-sidecar" / "index.sqlite").exists():
        omitted.append(
            {
                "path": ".lab-sidecar/index.sqlite",
                "category": "index",
                "reason": "local SQLite indexes are omitted by default",
            }
        )
    return omitted


def _ensure_task_boundary(task_path: Path, root: Path, task_id: str) -> None:
    try:
        task_path.relative_to(tasks_dir(root).resolve())
    except ValueError as exc:
        raise ComparisonTaskNotFound(
            f"task '{task_id}' artifact directory is outside .lab-sidecar/tasks"
        ) from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
