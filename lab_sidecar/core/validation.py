from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lab_sidecar.core.manifest import manifest_path
from lab_sidecar.core.models import TaskRecord, TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path
from lab_sidecar.core.traceability import TRACEABILITY_RELATIVE_PATH


class ValidationRequirement(StrEnum):
    METRICS = "metrics"
    FIGURES = "figures"
    REPORT = "report"
    SLIDES = "slides"
    PACKAGE_READY = "package-ready"


class ValidationStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class ValidationTaskNotFound(FileNotFoundError):
    """Raised when the task directory or manifest is not present."""


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: ValidationStatus
    message: str
    path: str | None = None
    next_action: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    task_id: str
    task_status: str | None
    mode: str | None
    diagnostic_mode: bool
    checks: list[ValidationCheck] = field(default_factory=list)

    @property
    def status(self) -> ValidationStatus:
        statuses = {check.status for check in self.checks}
        if ValidationStatus.FAIL in statuses:
            return ValidationStatus.FAIL
        if ValidationStatus.WARN in statuses:
            return ValidationStatus.WARN
        return ValidationStatus.OK

    @property
    def has_failures(self) -> bool:
        return self.status == ValidationStatus.FAIL


METRICS_FILES = {
    "normalized CSV": Path("metrics/normalized_metrics.csv"),
    "normalized JSON": Path("metrics/normalized_metrics.json"),
    "collection summary": Path("metrics/collection-summary.json"),
    "scenario summary": Path("metrics/scenario-summary.json"),
}
FIGURE_SUMMARY_PATH = Path("figures/figure-summary.json")
REPORT_PATH = Path("reports/report-fragment.md")
REPORT_SUMMARY_PATH = Path("reports/report-summary.json")
SLIDES_PATH = Path("slides/presentation-draft.pptx")
SLIDES_SUMMARY_PATH = Path("slides/slides-summary.json")
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_CSV_COUNT_BYTES = 2 * 1024 * 1024
TASK_RELATIVE_PREFIXES = {"metrics", "figures", "reports", "slides", "provenance", "reproduce", "raw"}
TRACE_FORBIDDEN_FRAGMENTS = [
    "worker transcript body\n",
    '"prompt":"secret"',
    '"response":"secret"',
    "FileNotFoundError: simulated missing dataset file",
    "epoch,train_loss,val_loss",
    "ppt/presentation.xml",
    "<p:sld",
]


class TaskValidationService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def validate(
        self,
        task_id: str,
        requirements: list[ValidationRequirement] | None = None,
    ) -> ValidationResult:
        required = set(requirements or [])
        checks: list[ValidationCheck] = []
        manifest = manifest_path(self.root, task_id)
        if not manifest.exists():
            raise ValidationTaskNotFound(f"task '{task_id}' was not found")

        record = self._load_manifest(task_id, manifest, checks)
        if record is None:
            return ValidationResult(
                task_id=task_id,
                task_status=None,
                mode=None,
                diagnostic_mode=False,
                checks=checks,
            )

        task_path = resolve_workspace_path(record.paths.task_dir, self.root)
        diagnostic_mode = record.status in {TaskStatus.FAILED, TaskStatus.CANCELLED}

        self._check_manifest_paths(record, task_path, checks)
        self._check_logs(record, checks)
        metrics_present = self._check_metrics(record, task_path, checks, required)
        figures_present = self._check_figures(record, task_path, checks, required)
        report_present = self._check_report(record, task_path, checks, required)
        slides_present = self._check_slides(record, task_path, checks, required)
        self._check_traceability(record, task_path, checks, required)
        self._check_package_ready(
            record=record,
            task_path=task_path,
            checks=checks,
            required=required,
            metrics_present=metrics_present,
            figures_present=figures_present,
            report_present=report_present,
            slides_present=slides_present,
        )

        return ValidationResult(
            task_id=record.task_id,
            task_status=record.status.value,
            mode=record.mode,
            diagnostic_mode=diagnostic_mode,
            checks=checks,
        )

    def _load_manifest(self, task_id: str, path: Path, checks: list[ValidationCheck]) -> TaskRecord | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            checks.append(
                ValidationCheck(
                    name="manifest",
                    status=ValidationStatus.FAIL,
                    message=f"manifest.json could not be read: {exc}",
                    path=_display_path(path, self.root),
                )
            )
            return None
        try:
            record = TaskRecord.model_validate_json(raw)
        except (ValueError, ValidationError) as exc:
            checks.append(
                ValidationCheck(
                    name="manifest",
                    status=ValidationStatus.FAIL,
                    message=f"manifest.json is not a valid task manifest: {exc}",
                    path=_display_path(path, self.root),
                )
            )
            return None
        if record.task_id != task_id:
            checks.append(
                ValidationCheck(
                    name="manifest",
                    status=ValidationStatus.FAIL,
                    message=f"manifest task_id is {record.task_id!r}, expected {task_id!r}",
                    path=_display_path(path, self.root),
                )
            )
            return record
        checks.append(
            ValidationCheck(
                name="manifest",
                status=ValidationStatus.OK,
                message="manifest.json is present and parseable",
                path=_display_path(path, self.root),
            )
        )
        return record

    def _check_manifest_paths(self, record: TaskRecord, task_path: Path, checks: list[ValidationCheck]) -> None:
        if not task_path.is_dir():
            checks.append(
                ValidationCheck(
                    name="manifest paths",
                    status=ValidationStatus.FAIL,
                    message="manifest paths.task_dir does not point to an existing directory",
                    path=record.paths.task_dir,
                )
            )
            return
        checks.append(
            ValidationCheck(
                name="manifest paths",
                status=ValidationStatus.OK,
                message="task artifact directory exists",
                path=_display_path(task_path, self.root),
            )
        )

    def _check_logs(self, record: TaskRecord, checks: list[ValidationCheck]) -> None:
        missing = []
        for label, path_text in [("stdout.log", record.paths.stdout), ("stderr.log", record.paths.stderr)]:
            path = resolve_workspace_path(path_text, self.root)
            if not path.is_file():
                missing.append(f"{label}: {_display_path(path, self.root)}")
        if missing:
            checks.append(
                ValidationCheck(
                    name="logs",
                    status=ValidationStatus.FAIL,
                    message="required log file(s) are missing: " + "; ".join(missing),
                )
            )
            return
        stderr_path = resolve_workspace_path(record.paths.stderr, self.root)
        if record.status == TaskStatus.FAILED and stderr_path.stat().st_size == 0:
            checks.append(
                ValidationCheck(
                    name="logs",
                    status=ValidationStatus.WARN,
                    message="stdout.log and stderr.log exist, but failed task stderr.log is empty",
                    path=_display_path(stderr_path, self.root),
                )
            )
            return
        checks.append(
            ValidationCheck(
                name="logs",
                status=ValidationStatus.OK,
                message="stdout.log and stderr.log exist",
            )
        )

    def _check_metrics(
        self,
        record: TaskRecord,
        task_path: Path,
        checks: list[ValidationCheck],
        required: set[ValidationRequirement],
    ) -> bool:
        files = {label: task_path / relative for label, relative in METRICS_FILES.items()}
        generated = any(path.exists() for path in files.values()) or _has_artifact(
            record,
            {
                "metrics_normalized_csv",
                "metrics_normalized_json",
                "metrics_collection_summary",
                "metrics_scenario_summary",
            },
        )
        is_required = ValidationRequirement.METRICS in required
        if not generated:
            checks.append(
                ValidationCheck(
                    name="metrics",
                    status=ValidationStatus.FAIL if is_required else ValidationStatus.WARN,
                    message="metrics have not been collected",
                    next_action=f"labsidecar collect {record.task_id}",
                )
            )
            return False

        missing = [f"{label}: {_display_path(path, self.root)}" for label, path in files.items() if not path.is_file()]
        if missing:
            checks.append(
                ValidationCheck(
                    name="metrics",
                    status=ValidationStatus.FAIL,
                    message="metrics artifact file(s) are missing: " + "; ".join(missing),
                    next_action=f"labsidecar collect {record.task_id}",
                )
            )
            return False

        try:
            summary = _read_json_object_bounded(files["collection summary"])
            scenario = _read_json_object_bounded(files["scenario summary"])
            metrics_json = _read_json_bounded(files["normalized JSON"])
            csv_header, csv_row_count = _csv_header_and_count(files["normalized CSV"])
        except (OSError, ValueError, json.JSONDecodeError, csv.Error) as exc:
            checks.append(
                ValidationCheck(
                    name="metrics",
                    status=ValidationStatus.FAIL,
                    message=f"metrics artifact could not be read with bounded checks: {exc}",
                    path="metrics/",
                    next_action=f"labsidecar collect {record.task_id}",
                )
            )
            return True
        issues = _metrics_consistency_issues(summary, scenario, metrics_json, csv_header, csv_row_count)
        if issues:
            checks.append(
                ValidationCheck(
                    name="metrics",
                    status=ValidationStatus.FAIL,
                    message="metrics summaries are inconsistent: " + "; ".join(issues),
                    path="metrics/",
                )
            )
            return True
        row_count = summary.get("row_count")
        detected_fields = summary.get("detected_fields") or []
        checks.append(
            ValidationCheck(
                name="metrics",
                status=ValidationStatus.OK,
                message=f"metrics artifacts are present and internally consistent (rows={row_count}, fields={len(detected_fields)})",
                path="metrics/",
            )
        )
        return True

    def _check_figures(
        self,
        record: TaskRecord,
        task_path: Path,
        checks: list[ValidationCheck],
        required: set[ValidationRequirement],
    ) -> bool:
        summary_path = task_path / FIGURE_SUMMARY_PATH
        generated = summary_path.exists() or any(artifact.type == "figure" for artifact in record.artifacts)
        is_required = ValidationRequirement.FIGURES in required
        if not generated:
            checks.append(
                ValidationCheck(
                    name="figures",
                    status=ValidationStatus.FAIL if is_required else ValidationStatus.WARN,
                    message="figures have not been generated",
                    next_action=f"labsidecar figures {record.task_id}",
                )
            )
            return False
        if not summary_path.is_file():
            checks.append(
                ValidationCheck(
                    name="figures",
                    status=ValidationStatus.FAIL,
                    message="figure summary is missing",
                    path=FIGURE_SUMMARY_PATH.as_posix(),
                    next_action=f"labsidecar figures {record.task_id}",
                )
            )
            return False

        try:
            summary = _read_json_object_bounded(summary_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(
                ValidationCheck(
                    name="figures",
                    status=ValidationStatus.FAIL,
                    message=f"figure summary could not be parsed: {exc}",
                    path=FIGURE_SUMMARY_PATH.as_posix(),
                    next_action=f"labsidecar figures {record.task_id}",
                )
            )
            return False
        figures = _figure_items(summary)
        figure_count = _int_or_none(summary.get("figure_count"))
        errors: list[str] = []
        for item in figures:
            for key in ("png_path", "svg_path", "png", "svg"):
                value = item.get(key)
                if not isinstance(value, str) or not value:
                    continue
                path = self._resolve_task_or_workspace_path(value, task_path)
                if not path.is_file() or path.stat().st_size == 0:
                    errors.append(f"{value} is missing or empty")
        if figure_count is not None and figure_count > 0 and not figures:
            errors.append("figure_count is positive but summary does not list generated figures")
        if figures and not any(artifact.type == "figure" for artifact in record.artifacts):
            errors.append("manifest has no figure artifact entry")
        if errors:
            checks.append(
                ValidationCheck(
                    name="figures",
                    status=ValidationStatus.FAIL,
                    message="figure artifacts are incomplete: " + "; ".join(errors),
                    path=FIGURE_SUMMARY_PATH.as_posix(),
                    next_action=f"labsidecar figures {record.task_id}",
                )
            )
            return False
        if not figures:
            checks.append(
                ValidationCheck(
                    name="figures",
                    status=ValidationStatus.FAIL if is_required else ValidationStatus.WARN,
                    message="figure summary exists but no figures were generated",
                    path=FIGURE_SUMMARY_PATH.as_posix(),
                    next_action=f"labsidecar figures {record.task_id}",
                )
            )
            return False
        checks.append(
            ValidationCheck(
                name="figures",
                status=ValidationStatus.OK,
                message=f"figure summary and {len(figures)} generated figure(s) are present",
                path=FIGURE_SUMMARY_PATH.as_posix(),
            )
        )
        return True

    def _check_report(
        self,
        record: TaskRecord,
        task_path: Path,
        checks: list[ValidationCheck],
        required: set[ValidationRequirement],
    ) -> bool:
        report_path = task_path / REPORT_PATH
        summary_path = task_path / REPORT_SUMMARY_PATH
        generated = report_path.exists() or summary_path.exists() or _has_artifact(
            record,
            {"report_fragment_md", "report_summary_json"},
        )
        is_required = ValidationRequirement.REPORT in required
        if not generated:
            checks.append(
                ValidationCheck(
                    name="report",
                    status=ValidationStatus.FAIL if is_required else ValidationStatus.WARN,
                    message="report has not been generated",
                    next_action=f"labsidecar report {record.task_id}",
                )
            )
            return False
        errors: list[str] = []
        if not report_path.is_file() or report_path.stat().st_size == 0:
            errors.append(f"{REPORT_PATH.as_posix()} is missing or empty")
        if not summary_path.is_file():
            errors.append(f"{REPORT_SUMMARY_PATH.as_posix()} is missing")
        summary: dict[str, Any] = {}
        if summary_path.is_file():
            try:
                summary = _read_json_object_bounded(summary_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{REPORT_SUMMARY_PATH.as_posix()} could not be parsed: {exc}")
            else:
                source_artifacts = summary.get("source_artifacts") or summary.get("generated_from")
                claim_traces = summary.get("claim_traces")
                if not source_artifacts and not claim_traces:
                    errors.append("report summary has neither source_artifacts nor claim_traces")
        if errors:
            checks.append(
                ValidationCheck(
                    name="report",
                    status=ValidationStatus.FAIL,
                    message="report artifacts are incomplete: " + "; ".join(errors),
                    path="reports/",
                    next_action=f"labsidecar report {record.task_id}",
                )
            )
            return False
        claim_count = len(summary.get("claim_traces") or [])
        checks.append(
            ValidationCheck(
                name="report",
                status=ValidationStatus.OK,
                message=f"report fragment and summary are present (claim_traces={claim_count})",
                path="reports/",
            )
        )
        return True

    def _check_slides(
        self,
        record: TaskRecord,
        task_path: Path,
        checks: list[ValidationCheck],
        required: set[ValidationRequirement],
    ) -> bool:
        slides_path = task_path / SLIDES_PATH
        summary_path = task_path / SLIDES_SUMMARY_PATH
        generated = slides_path.exists() or summary_path.exists() or _has_artifact(
            record,
            {"slides_presentation_draft_pptx", "slides_summary_json"},
        )
        is_required = ValidationRequirement.SLIDES in required
        if not generated:
            checks.append(
                ValidationCheck(
                    name="slides",
                    status=ValidationStatus.FAIL if is_required else ValidationStatus.WARN,
                    message="slides have not been generated",
                    next_action=f"labsidecar slides {record.task_id}",
                )
            )
            return False
        errors: list[str] = []
        if not slides_path.is_file() or slides_path.stat().st_size == 0:
            errors.append(f"{SLIDES_PATH.as_posix()} is missing or empty")
        if not summary_path.is_file():
            errors.append(f"{SLIDES_SUMMARY_PATH.as_posix()} is missing")
        summary: dict[str, Any] = {}
        if summary_path.is_file():
            try:
                summary = _read_json_object_bounded(summary_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{SLIDES_SUMMARY_PATH.as_posix()} could not be parsed: {exc}")
                summary = {}
            if summary:
                slide_count = _int_or_none(summary.get("slide_count"))
                qa_checks = summary.get("qa_checks")
                if slide_count is None or slide_count <= 0 or slide_count > 100:
                    errors.append("slide_count is missing or unreasonable")
                if not isinstance(qa_checks, dict):
                    errors.append("qa_checks is missing")
                else:
                    failed_checks = [
                        name
                        for name, item in qa_checks.items()
                        if isinstance(item, dict) and item.get("passed") is False
                    ]
                    if failed_checks:
                        errors.append("qa_checks failed: " + ", ".join(sorted(failed_checks)))
        if errors:
            checks.append(
                ValidationCheck(
                    name="slides",
                    status=ValidationStatus.FAIL,
                    message="slides artifacts are incomplete: " + "; ".join(errors),
                    path="slides/",
                    next_action=f"labsidecar slides {record.task_id}",
                )
            )
            return False
        checks.append(
            ValidationCheck(
                name="slides",
                status=ValidationStatus.OK,
                message=f"presentation draft and summary are present (slides={summary.get('slide_count')})",
                path="slides/",
            )
        )
        return True

    def _check_traceability(
        self,
        record: TaskRecord,
        task_path: Path,
        checks: list[ValidationCheck],
        required: set[ValidationRequirement],
    ) -> bool:
        path = task_path / TRACEABILITY_RELATIVE_PATH
        is_required = ValidationRequirement.PACKAGE_READY in required
        if not path.exists():
            checks.append(
                ValidationCheck(
                    name="traceability",
                    status=ValidationStatus.FAIL if is_required else ValidationStatus.WARN,
                    message="traceability index has not been generated yet",
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                    next_action=f"labsidecar collect {record.task_id}",
                )
            )
            return False
        if not path.is_file() or path.stat().st_size == 0:
            checks.append(
                ValidationCheck(
                    name="traceability",
                    status=ValidationStatus.FAIL,
                    message="traceability index is missing or empty",
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                )
            )
            return False
        try:
            raw = _read_text_bounded(path, MAX_JSON_BYTES)
            data = json.loads(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            checks.append(
                ValidationCheck(
                    name="traceability",
                    status=ValidationStatus.FAIL,
                    message=f"traceability index could not be parsed: {exc}",
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                )
            )
            return False
        errors: list[str] = []
        if data.get("task_id") != record.task_id:
            errors.append("traceability task_id does not match manifest")
        for fragment in TRACE_FORBIDDEN_FRAGMENTS:
            if fragment in raw:
                errors.append(f"traceability appears to include forbidden body content fragment: {fragment[:40]!r}")
        for item in data.get("artifacts") or []:
            if not isinstance(item, dict) or item.get("exists") is not True:
                continue
            path_text = item.get("path")
            if not isinstance(path_text, str) or not path_text:
                errors.append("traceability artifact entry with exists=true has no path")
                continue
            artifact_path = self._resolve_task_or_workspace_path(path_text, task_path)
            if not artifact_path.is_file():
                errors.append(f"traceability artifact path does not exist: {path_text}")
        if errors:
            checks.append(
                ValidationCheck(
                    name="traceability",
                    status=ValidationStatus.FAIL,
                    message="traceability index is inconsistent: " + "; ".join(errors),
                    path=TRACEABILITY_RELATIVE_PATH.as_posix(),
                )
            )
            return False
        checks.append(
            ValidationCheck(
                name="traceability",
                status=ValidationStatus.OK,
                message="traceability index is present, bounded, and points to existing artifacts",
                path=TRACEABILITY_RELATIVE_PATH.as_posix(),
            )
        )
        return True

    def _check_package_ready(
        self,
        *,
        record: TaskRecord,
        task_path: Path,
        checks: list[ValidationCheck],
        required: set[ValidationRequirement],
        metrics_present: bool,
        figures_present: bool,
        report_present: bool,
        slides_present: bool,
    ) -> None:
        if ValidationRequirement.PACKAGE_READY not in required:
            return
        traceability_path = task_path / TRACEABILITY_RELATIVE_PATH
        if not traceability_path.is_file():
            checks.append(
                ValidationCheck(
                    name="package-ready",
                    status=ValidationStatus.FAIL,
                    message="traceability index is required before packaging readiness can be confirmed",
                    next_action=f"labsidecar collect {record.task_id}",
                )
            )
            return
        missing_registered = [
            artifact.path
            for artifact in record.artifacts
            if artifact.artifact_id != "provenance_traceability_json"
            and not self._resolve_task_or_workspace_path(artifact.path, task_path).is_file()
        ]
        if missing_registered:
            checks.append(
                ValidationCheck(
                    name="package-ready",
                    status=ValidationStatus.FAIL,
                    message="manifest registers missing artifact(s): " + ", ".join(sorted(missing_registered)),
                    next_action=f"labsidecar artifacts {record.task_id}",
                )
            )
            return
        if record.status == TaskStatus.COMPLETED and not (metrics_present and report_present and slides_present):
            checks.append(
                ValidationCheck(
                    name="package-ready",
                    status=ValidationStatus.FAIL,
                    message="completed task is missing deliverable artifacts needed for a result package",
                    next_action=f"labsidecar collect {record.task_id}",
                )
            )
            return
        if record.status in {TaskStatus.FAILED, TaskStatus.CANCELLED} and not (report_present and slides_present):
            checks.append(
                ValidationCheck(
                    name="package-ready",
                    status=ValidationStatus.FAIL,
                    message="diagnostic task is missing report or slides needed for a diagnostic package",
                    next_action=f"labsidecar report {record.task_id}",
                )
            )
            return
        checks.append(
            ValidationCheck(
                name="package-ready",
                status=ValidationStatus.OK,
                message="registered artifacts exist and task is ready for labsidecar package",
            )
        )

    def _resolve_task_or_workspace_path(self, path_text: str, task_path: Path) -> Path:
        path = Path(path_text)
        if path.is_absolute():
            return path
        if path.parts and path.parts[0] == ".lab-sidecar":
            return self.root / path
        if path.parts and path.parts[0] in TASK_RELATIVE_PREFIXES:
            return task_path / path
        if path.name in {"manifest.json", "stdout.log", "stderr.log"}:
            return task_path / path
        task_candidate = task_path / path
        if task_candidate.exists():
            return task_candidate
        return self.root / path


def _has_artifact(record: TaskRecord, artifact_ids: set[str]) -> bool:
    return any(artifact.artifact_id in artifact_ids for artifact in record.artifacts)


def _read_text_bounded(path: Path, max_bytes: int) -> str:
    if path.stat().st_size > max_bytes:
        raise ValueError(f"{path.name} exceeds bounded read limit ({max_bytes} bytes)")
    return path.read_text(encoding="utf-8")


def _read_json_bounded(path: Path) -> Any:
    raw = _read_text_bounded(path, MAX_JSON_BYTES)
    return json.loads(raw)


def _read_json_object_bounded(path: Path) -> dict[str, Any]:
    data = _read_json_bounded(path)
    if isinstance(data, dict):
        return data
    raise ValueError(f"{path.name} did not contain a JSON object")


def _csv_header_and_count(path: Path) -> tuple[list[str], int | None]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
    if path.stat().st_size > MAX_CSV_COUNT_BYTES:
        return header, None
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return header, sum(1 for row in reader if row)


def _metrics_consistency_issues(
    summary: dict[str, Any],
    scenario: dict[str, Any],
    metrics_json: Any,
    csv_header: list[str],
    csv_row_count: int | None,
) -> list[str]:
    issues: list[str] = []
    row_count = _int_or_none(summary.get("row_count"))
    detected_fields = summary.get("detected_fields")
    if row_count is None or row_count < 0:
        issues.append("collection-summary row_count is missing or invalid")
    if not isinstance(detected_fields, list):
        issues.append("collection-summary detected_fields is not a list")
        detected_fields = []
    if csv_header and detected_fields:
        missing_fields = [field for field in detected_fields if field not in csv_header]
        if missing_fields:
            issues.append("detected_fields not present in normalized CSV: " + ", ".join(map(str, missing_fields)))
    if csv_row_count is not None and row_count is not None and csv_row_count != row_count:
        issues.append(f"normalized CSV row count {csv_row_count} does not match summary row_count {row_count}")
    json_rows = metrics_json
    if isinstance(metrics_json, dict):
        json_rows = metrics_json.get("rows")
    if isinstance(json_rows, list) and row_count is not None and len(json_rows) != row_count:
        issues.append(f"normalized JSON row count {len(json_rows)} does not match summary row_count {row_count}")
    evidence = scenario.get("evidence")
    if isinstance(evidence, dict):
        evidence_row_count = _int_or_none(evidence.get("row_count"))
        if evidence_row_count is not None and row_count is not None and evidence_row_count != row_count:
            issues.append(
                f"scenario evidence row_count {evidence_row_count} does not match collection row_count {row_count}"
            )
    if row_count == 0:
        issues.append("metrics row_count is zero")
    return issues


def _figure_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    raw = summary.get("generated_figures") or summary.get("figures") or []
    return [item for item in raw if isinstance(item, dict)]


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
