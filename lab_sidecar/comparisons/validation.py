from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lab_sidecar.comparisons.models import (
    ComparisonInvalidId,
    ComparisonManifest,
    ComparisonNotFound,
    ComparisonValidationCheck,
    ComparisonValidationRequirement,
    ComparisonValidationResult,
    ComparisonValidationStatus,
)
from lab_sidecar.comparisons.paths import comparison_dir, comparison_manifest_path, is_valid_comparison_id
from lab_sidecar.comparisons.service import (
    FIGURE_SUMMARY_RELATIVE_PATH,
    MANIFEST_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    REPORT_SUMMARY_RELATIVE_PATH,
    SUMMARY_RELATIVE_PATH,
    TABLE_CSV_RELATIVE_PATH,
    TABLE_JSON_RELATIVE_PATH,
    TRACEABILITY_RELATIVE_PATH,
)
from lab_sidecar.core.provenance import file_sha256
from lab_sidecar.core.paths import resolve_workspace_path, tasks_dir


MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_TEXT_BYTES = 5 * 1024 * 1024
DESCRIPTIVE_ONLY_NOTE = "This comparison is descriptive only; no statistical significance or model superiority is inferred."
TRACE_FORBIDDEN_FRAGMENTS = [
    "epoch,train_loss,val_loss",
    "Best val_accuracy",
    "FileNotFoundError: simulated missing dataset file",
    "ppt/presentation.xml",
    "<p:sld",
]


class ComparisonValidationService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def validate(
        self,
        comparison_id: str,
        requirements: list[ComparisonValidationRequirement] | None = None,
    ) -> ComparisonValidationResult:
        required = set(requirements or [])
        checks: list[ComparisonValidationCheck] = []
        if not is_valid_comparison_id(comparison_id):
            raise ComparisonInvalidId(f"invalid comparison id: {comparison_id!r}")
        manifest_path = comparison_manifest_path(self.root, comparison_id)
        if not manifest_path.exists():
            raise ComparisonNotFound(f"comparison '{comparison_id}' was not found")

        manifest = self._load_manifest(comparison_id, manifest_path, checks)
        if manifest is None:
            return ComparisonValidationResult(comparison_id=comparison_id, checks=checks)

        output_dir = comparison_dir(self.root, comparison_id)
        self._check_paths(output_dir, checks)
        self._check_summary(output_dir, manifest, checks)
        self._check_table(output_dir, manifest, checks)
        figures_present = self._check_figures(output_dir, manifest, checks, required)
        report_present = self._check_report(output_dir, manifest, checks, required)
        traceability_present = self._check_traceability(output_dir, manifest, checks, required)
        self._check_source_metrics(manifest, checks)
        self._check_package_ready(
            manifest=manifest,
            output_dir=output_dir,
            checks=checks,
            required=required,
            figures_present=figures_present,
            report_present=report_present,
            traceability_present=traceability_present,
        )
        return ComparisonValidationResult(comparison_id=comparison_id, checks=checks)

    def _load_manifest(
        self,
        comparison_id: str,
        path: Path,
        checks: list[ComparisonValidationCheck],
    ) -> ComparisonManifest | None:
        try:
            raw = _read_text_bounded(path, MAX_TEXT_BYTES)
        except OSError as exc:
            checks.append(
                ComparisonValidationCheck(
                    name="manifest",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"comparison manifest could not be read: {exc}",
                    path=_display_path(path, self.root),
                    next_action="inspect .lab-sidecar/comparisons/ or rerun labsidecar compare --save",
                )
            )
            return None
        try:
            manifest = ComparisonManifest.model_validate_json(raw)
        except (ValueError, ValidationError) as exc:
            checks.append(
                ComparisonValidationCheck(
                    name="manifest",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"comparison-manifest.json is not valid: {exc}",
                    path=MANIFEST_RELATIVE_PATH.as_posix(),
                    next_action="inspect comparison-artifacts for the saved id or rerun labsidecar compare --save",
                )
            )
            return None
        if manifest.comparison_id != comparison_id:
            checks.append(
                ComparisonValidationCheck(
                    name="manifest",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"manifest comparison_id is {manifest.comparison_id!r}, expected {comparison_id!r}",
                    path=MANIFEST_RELATIVE_PATH.as_posix(),
                    next_action=f"run labsidecar list-comparisons and inspect labsidecar comparison-artifacts {comparison_id}",
                )
            )
            return manifest
        checks.append(
            ComparisonValidationCheck(
                name="manifest",
                status=ComparisonValidationStatus.OK,
                message="comparison-manifest.json is present and parseable",
                path=MANIFEST_RELATIVE_PATH.as_posix(),
            )
        )
        return manifest

    def _check_paths(self, output_dir: Path, checks: list[ComparisonValidationCheck]) -> None:
        if output_dir.is_dir():
            checks.append(
                ComparisonValidationCheck(
                    name="paths",
                    status=ComparisonValidationStatus.OK,
                    message="comparison artifact directory exists",
                    path=_display_path(output_dir, self.root),
                )
            )
            return
        checks.append(
            ComparisonValidationCheck(
                name="paths",
                status=ComparisonValidationStatus.FAIL,
                message="comparison artifact directory is missing",
                path=_display_path(output_dir, self.root),
                next_action="run labsidecar list-comparisons to find saved comparison ids",
            )
        )

    def _check_summary(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        checks: list[ComparisonValidationCheck],
    ) -> bool:
        path = output_dir / SUMMARY_RELATIVE_PATH
        try:
            summary = _read_json_object(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(
                ComparisonValidationCheck(
                    name="summary",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"comparison summary could not be parsed: {exc}",
                    path=SUMMARY_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id} or rerun labsidecar compare --save",
                )
            )
            return False
        errors = []
        if summary.get("row_selection", {}).get("method") != "final_row":
            errors.append("summary row_selection method is not final_row")
        if summary.get("comparison_id") != manifest.comparison_id:
            errors.append("summary comparison_id does not match manifest")
        if summary.get("task_ids") != manifest.task_ids:
            errors.append("summary task_ids do not match manifest")
        if not summary.get("common_numeric_fields"):
            errors.append("summary has no common_numeric_fields")
        serialized = json.dumps(summary, ensure_ascii=False)
        for fragment in TRACE_FORBIDDEN_FRAGMENTS:
            if fragment in serialized:
                errors.append(f"summary appears to embed forbidden body content fragment: {fragment[:40]!r}")
        if errors:
            checks.append(
                ComparisonValidationCheck(
                    name="summary",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison summary is inconsistent: " + "; ".join(errors),
                    path=SUMMARY_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id} or rerun labsidecar compare --save",
                )
            )
            return False
        checks.append(
            ComparisonValidationCheck(
                name="summary",
                status=ComparisonValidationStatus.OK,
                message="comparison summary is present and bounded",
                path=SUMMARY_RELATIVE_PATH.as_posix(),
            )
        )
        return True

    def _check_table(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        checks: list[ComparisonValidationCheck],
    ) -> bool:
        csv_path = output_dir / TABLE_CSV_RELATIVE_PATH
        json_path = output_dir / TABLE_JSON_RELATIVE_PATH
        if not csv_path.is_file() or not json_path.is_file():
            checks.append(
                ComparisonValidationCheck(
                    name="table",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison table CSV or JSON is missing",
                    path=TABLE_CSV_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id} or rerun labsidecar compare --save",
                )
            )
            return False
        try:
            with csv_path.open("r", newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            payload = _read_json_object(json_path)
        except (OSError, csv.Error, ValueError, json.JSONDecodeError) as exc:
            checks.append(
                ComparisonValidationCheck(
                    name="table",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"comparison table could not be read: {exc}",
                    path=TABLE_CSV_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id} or rerun labsidecar compare --save",
                )
            )
            return False
        errors = []
        if payload.get("row_selection") != "final_row":
            errors.append("comparison-table.json row_selection is not final_row")
        if not rows:
            errors.append("comparison table has no rows")
        if payload.get("comparison_id") != manifest.comparison_id:
            errors.append("comparison-table.json comparison_id does not match manifest")
        if len(payload.get("rows") or []) != len(rows):
            errors.append("comparison-table.json row count does not match CSV")
        if errors:
            checks.append(
                ComparisonValidationCheck(
                    name="table",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison table is inconsistent: " + "; ".join(errors),
                    path=TABLE_CSV_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id} or rerun labsidecar compare --save",
                )
            )
            return False
        checks.append(
            ComparisonValidationCheck(
                name="table",
                status=ComparisonValidationStatus.OK,
                message=f"comparison table CSV and JSON are present (rows={len(rows)})",
                path=TABLE_CSV_RELATIVE_PATH.as_posix(),
            )
        )
        return True

    def _check_figures(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        checks: list[ComparisonValidationCheck],
        required: set[ComparisonValidationRequirement],
    ) -> bool:
        path = output_dir / FIGURE_SUMMARY_RELATIVE_PATH
        generated = path.exists() or any(artifact.type == "figure" for artifact in manifest.artifacts)
        is_required = ComparisonValidationRequirement.FIGURES in required
        if not generated:
            checks.append(
                ComparisonValidationCheck(
                    name="figures",
                    status=ComparisonValidationStatus.FAIL if is_required else ComparisonValidationStatus.WARN,
                    message="comparison figures have not been generated",
                    next_action=f"labsidecar compare {' '.join(manifest.task_ids)} --save --figures creates a fresh saved comparison with figures",
                )
            )
            return False
        try:
            summary = _read_json_object(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(
                ComparisonValidationCheck(
                    name="figures",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"figure summary could not be parsed: {exc}",
                    path=FIGURE_SUMMARY_RELATIVE_PATH.as_posix(),
                    next_action=f"rerun labsidecar compare {' '.join(manifest.task_ids)} --save --figures to create a fresh saved comparison",
                )
            )
            return False
        errors = []
        if is_required and len(summary.get("figures") or []) == 0:
            errors.append("figure summary has no generated figures")
        for item in summary.get("figures") or []:
            if not isinstance(item, dict):
                continue
            for key in ("png_path", "svg_path"):
                value = item.get(key)
                if not isinstance(value, str):
                    errors.append(f"figure entry missing {key}")
                    continue
                image_path = _safe_comparison_path(output_dir, value, errors, f"figure {key}")
                if image_path is None:
                    continue
                if not image_path.is_file() or image_path.stat().st_size == 0:
                    errors.append(f"{value} is missing or empty")
        if errors:
            checks.append(
                ComparisonValidationCheck(
                    name="figures",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison figure artifacts are incomplete: " + "; ".join(errors),
                    path=FIGURE_SUMMARY_RELATIVE_PATH.as_posix(),
                    next_action=f"rerun labsidecar compare {' '.join(manifest.task_ids)} --save --figures to create a fresh saved comparison",
                )
            )
            return False
        checks.append(
            ComparisonValidationCheck(
                name="figures",
                status=ComparisonValidationStatus.OK,
                message=f"figure summary and {len(summary.get('figures') or [])} generated figure(s) are present",
                path=FIGURE_SUMMARY_RELATIVE_PATH.as_posix(),
            )
        )
        return True

    def _check_report(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        checks: list[ComparisonValidationCheck],
        required: set[ComparisonValidationRequirement],
    ) -> bool:
        report_path = output_dir / REPORT_RELATIVE_PATH
        summary_path = output_dir / REPORT_SUMMARY_RELATIVE_PATH
        generated = report_path.exists() or summary_path.exists() or any(
            artifact.artifact_id.startswith("comparison_report") for artifact in manifest.artifacts
        )
        is_required = ComparisonValidationRequirement.REPORT in required
        if not generated:
            checks.append(
                ComparisonValidationCheck(
                    name="report",
                    status=ComparisonValidationStatus.FAIL if is_required else ComparisonValidationStatus.WARN,
                    message="comparison report has not been generated",
                    next_action=f"labsidecar compare {' '.join(manifest.task_ids)} --save --report creates a fresh saved comparison with a report",
                )
            )
            return False
        errors = []
        if not report_path.is_file() or report_path.stat().st_size == 0:
            errors.append(f"{REPORT_RELATIVE_PATH.as_posix()} is missing or empty")
        try:
            summary = _read_json_object(summary_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{REPORT_SUMMARY_RELATIVE_PATH.as_posix()} could not be parsed: {exc}")
            summary = {}
        text = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
        forbidden_claims = _report_forbidden_claim_fragments(text)
        for fragment in forbidden_claims:
            errors.append(f"report contains forbidden claim fragment: {fragment}")
        if DESCRIPTIVE_ONLY_NOTE not in text:
            errors.append("report is missing descriptive-only non-claim note")
        if summary and not (summary.get("source_artifacts") or summary.get("claim_traces")):
            errors.append("report summary has neither source_artifacts nor claim_traces")
        if errors:
            checks.append(
                ComparisonValidationCheck(
                    name="report",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison report artifacts are incomplete: " + "; ".join(errors),
                    path="reports/",
                    next_action=f"rerun labsidecar compare {' '.join(manifest.task_ids)} --save --report to create a fresh saved comparison",
                )
            )
            return False
        checks.append(
            ComparisonValidationCheck(
                name="report",
                status=ComparisonValidationStatus.OK,
                message=f"comparison report fragment and summary are present (claim_traces={len(summary.get('claim_traces') or [])})",
                path="reports/",
            )
        )
        return True

    def _check_traceability(
        self,
        output_dir: Path,
        manifest: ComparisonManifest,
        checks: list[ComparisonValidationCheck],
        required: set[ComparisonValidationRequirement],
    ) -> bool:
        path = output_dir / TRACEABILITY_RELATIVE_PATH
        is_required = ComparisonValidationRequirement.PACKAGE_READY in required
        if not path.exists():
            checks.append(
                ComparisonValidationCheck(
                    name="traceability",
                    status=ComparisonValidationStatus.FAIL if is_required else ComparisonValidationStatus.WARN,
                    message="comparison traceability index has not been generated yet",
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                    next_action=f"run labsidecar package-comparison {manifest.comparison_id} --output <package_dir> or rerun labsidecar compare --save",
                )
            )
            return False
        try:
            raw = _read_text_bounded(path, MAX_TEXT_BYTES)
            data = json.loads(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(
                ComparisonValidationCheck(
                    name="traceability",
                    status=ComparisonValidationStatus.FAIL,
                    message=f"comparison traceability could not be parsed: {exc}",
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id}",
                )
            )
            return False
        errors = []
        if data.get("comparison_id") != manifest.comparison_id:
            errors.append("traceability comparison_id does not match manifest")
        for fragment in TRACE_FORBIDDEN_FRAGMENTS:
            if fragment in raw:
                errors.append(f"traceability appears to include forbidden body content fragment: {fragment[:40]!r}")
        for item in data.get("artifacts") or []:
            if not isinstance(item, dict) or item.get("exists") is not True:
                continue
            path_text = item.get("path")
            if not isinstance(path_text, str):
                errors.append(f"traceability artifact path does not exist: {path_text}")
                continue
            artifact_path = _safe_comparison_path(output_dir, path_text, errors, "traceability artifact path")
            if artifact_path is None:
                continue
            if not artifact_path.is_file():
                errors.append(f"traceability artifact path does not exist: {path_text}")
        if errors:
            checks.append(
                ComparisonValidationCheck(
                    name="traceability",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison traceability is inconsistent: " + "; ".join(errors),
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                    next_action=f"inspect labsidecar comparison-artifacts {manifest.comparison_id}",
                )
            )
            return False
        checks.append(
            ComparisonValidationCheck(
                name="traceability",
                status=ComparisonValidationStatus.OK,
                message="comparison traceability is present, bounded, and points to existing artifacts",
                path=TRACEABILITY_RELATIVE_PATH.as_posix(),
            )
        )
        return True

    def _check_source_metrics(
        self,
        manifest: ComparisonManifest,
        checks: list[ComparisonValidationCheck],
    ) -> bool:
        errors = []
        for item in manifest.source_tasks:
            metrics_path_text = item.get("metrics_path")
            task_id = item.get("task_id")
            if not isinstance(metrics_path_text, str):
                errors.append(f"source task {task_id} is missing metrics_path")
                continue
            metrics_path = resolve_workspace_path(metrics_path_text, self.root).resolve()
            try:
                metrics_path.relative_to(tasks_dir(self.root).resolve())
            except ValueError:
                errors.append(f"source metrics path escapes .lab-sidecar/tasks for task {task_id}: {metrics_path_text}")
                continue
            if not metrics_path.is_file():
                errors.append(f"source metrics are missing for task {task_id}: {metrics_path_text}")
                continue
            expected_sha = item.get("metrics_sha256")
            if isinstance(expected_sha, str) and expected_sha and file_sha256(metrics_path) != expected_sha:
                errors.append(f"source metrics digest changed for task {task_id}: {metrics_path_text}")
        if errors:
            checks.append(
                ComparisonValidationCheck(
                    name="source metrics",
                    status=ComparisonValidationStatus.FAIL,
                    message="source metrics are unavailable or stale: " + "; ".join(errors),
                    next_action="rerun labsidecar collect <task_id> for stale sources, then rerun labsidecar compare --save",
                )
            )
            return False
        checks.append(
            ComparisonValidationCheck(
                name="source metrics",
                status=ComparisonValidationStatus.OK,
                message=f"source metric artifact references are present and digest-checked (tasks={len(manifest.source_tasks)})",
            )
        )
        return True

    def _check_package_ready(
        self,
        *,
        manifest: ComparisonManifest,
        output_dir: Path,
        checks: list[ComparisonValidationCheck],
        required: set[ComparisonValidationRequirement],
        figures_present: bool,
        report_present: bool,
        traceability_present: bool,
    ) -> None:
        if ComparisonValidationRequirement.PACKAGE_READY not in required:
            return
        missing_registered = [
            artifact.path
            for artifact in manifest.artifacts
            if artifact.artifact_id != "provenance_traceability_json"
            and not _registered_artifact_exists(output_dir, artifact.path)
        ]
        if missing_registered:
            checks.append(
                ComparisonValidationCheck(
                    name="package-ready",
                    status=ComparisonValidationStatus.FAIL,
                    message="manifest registers missing artifact(s): " + ", ".join(sorted(missing_registered)),
                    next_action=f"run labsidecar comparison-artifacts {manifest.comparison_id} and regenerate missing artifacts",
                )
            )
            return
        if not (figures_present and report_present and traceability_present):
            checks.append(
                ComparisonValidationCheck(
                    name="package-ready",
                    status=ComparisonValidationStatus.FAIL,
                    message="comparison is missing figures, report, or traceability needed for a result package",
                    next_action=f"rerun labsidecar compare {' '.join(manifest.task_ids)} --save --figures --report to create a fresh saved comparison",
                )
            )
            return
        checks.append(
            ComparisonValidationCheck(
                name="package-ready",
                status=ComparisonValidationStatus.OK,
                message="registered comparison artifacts exist and comparison is ready for labsidecar package-comparison",
            )
        )


def _read_text_bounded(path: Path, max_bytes: int) -> str:
    if path.stat().st_size > max_bytes:
        raise ValueError(f"{path.name} exceeds bounded read limit ({max_bytes} bytes)")
    return path.read_text(encoding="utf-8")


def _read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(_read_text_bounded(path, MAX_JSON_BYTES))
    if isinstance(data, dict):
        return data
    raise ValueError(f"{path.name} did not contain a JSON object")


def _safe_comparison_path(
    output_dir: Path,
    path_text: str,
    errors: list[str],
    label: str,
) -> Path | None:
    relative_path = Path(path_text)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        errors.append(f"{label} escapes comparison directory: {path_text}")
        return None
    candidate = (output_dir / relative_path).resolve()
    try:
        candidate.relative_to(output_dir.resolve())
    except ValueError:
        errors.append(f"{label} escapes comparison directory: {path_text}")
        return None
    return candidate


def _registered_artifact_exists(output_dir: Path, path_text: str) -> bool:
    errors: list[str] = []
    path = _safe_comparison_path(output_dir, path_text, errors, "manifest artifact path")
    return path is not None and path.is_file()


def _report_forbidden_claim_fragments(text: str) -> list[str]:
    scannable = text.replace(DESCRIPTIVE_ONLY_NOTE, "")
    lowered = scannable.lower()
    forbidden: list[str] = []
    for fragment in [
        "statistically significant",
        "model superiority is inferred",
        "deployment-ready",
        "ai-written conclusion",
    ]:
        if fragment in lowered:
            forbidden.append(fragment)
    for pattern, label in [
        (r"\bwinner\b", "winner"),
        (r"\bsuperior\b", "superior"),
    ]:
        if re.search(pattern, lowered):
            forbidden.append(label)
    return forbidden


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
