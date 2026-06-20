from __future__ import annotations

import base64
import io
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol
from xml.etree import ElementTree

from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lab_sidecar.intelligence.sandbox import SandboxBoundaryError, resolve_sandbox_path
from lab_sidecar.intelligence.schemas import ValidatorCheck, ValidatorResult


FALLBACK_PROPOSAL_SCHEMA_VERSION = "1"
FALLBACK_WORKER_SCHEMA_VERSION = "1"
FALLBACK_PROPOSAL_TYPE = "figure_fallback"
MOCK_WORKER_TYPE = "mock_chart_fallback"

_TINY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO6pC2QAAAAASUVORK5CYII="
)
MIN_FALLBACK_PNG_WIDTH = 320
MIN_FALLBACK_PNG_HEIGHT = 180
MIN_FALLBACK_SVG_WIDTH = 320
MIN_FALLBACK_SVG_HEIGHT = 180
_SAFE_FIGURE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


FallbackWorkerMode = Literal[
    "unavailable",
    "mock",
    "mock-escape",
    "mock-malformed-image",
    "mock-missing-field",
    "mock-tiny-image",
]
FallbackWorkerStatus = Literal["proposal_created", "rejected", "unavailable"]


class FigureFallbackArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    png_path: str | None = None
    svg_path: str | None = None


class FigureFallbackProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = FALLBACK_PROPOSAL_SCHEMA_VERSION
    proposal_type: Literal["figure_fallback"] = FALLBACK_PROPOSAL_TYPE
    task_id: str
    worker_run_id: str
    figure_id: str
    chart_type: str
    title: str
    x: str
    y: str
    group_by: str | None = None
    source_metrics_fields: list[str] = Field(default_factory=list)
    output_paths: FigureFallbackArtifacts
    deterministic_refusal_reason: str
    omitted: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)


class FigureFallbackWorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = FALLBACK_WORKER_SCHEMA_VERSION
    task_id: str
    worker_run_id: str
    worker_type: str
    figure_request_path: str
    sandbox_path: str
    requested_chart_intent: dict[str, Any] | None = None
    available_fields: list[str] = Field(default_factory=list)
    row_count: int | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    )


class FigureFallbackWorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = FALLBACK_WORKER_SCHEMA_VERSION
    task_id: str
    worker_run_id: str
    worker_type: str
    status: FallbackWorkerStatus
    proposal_path: str | None = None
    artifact_paths: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class FigureFallbackWorker(Protocol):
    worker_type: str

    def run(
        self,
        request: FigureFallbackWorkerRequest,
        figure_request: dict[str, Any],
        sandbox_path: Path,
    ) -> FigureFallbackWorkerResult:
        ...


@dataclass(frozen=True)
class FigureFallbackValidation:
    validator: ValidatorResult
    proposal: FigureFallbackProposal | None = None
    sandbox_png_path: Path | None = None
    sandbox_svg_path: Path | None = None


def configured_fallback_worker(mode: FallbackWorkerMode) -> FigureFallbackWorker | None:
    if mode == "mock":
        return MockFigureFallbackWorker(failure_mode=None)
    if mode == "mock-escape":
        return MockFigureFallbackWorker(failure_mode="escape")
    if mode == "mock-malformed-image":
        return MockFigureFallbackWorker(failure_mode="malformed_image")
    if mode == "mock-missing-field":
        return MockFigureFallbackWorker(failure_mode="missing_field")
    if mode == "mock-tiny-image":
        return MockFigureFallbackWorker(failure_mode="tiny_image")
    return None


def validate_proposal_contract(data: dict[str, Any]) -> FigureFallbackProposal:
    return FigureFallbackProposal.model_validate(data)


def write_worker_request(path: Path, request: FigureFallbackWorkerRequest) -> None:
    path.write_text(json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_worker_result(path: Path, result: FigureFallbackWorkerResult) -> None:
    path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_fallback_result(
    task_id: str,
    worker_run_id: str,
    sandbox_path: Path,
    figure_request: dict[str, Any],
    worker_result: FigureFallbackWorkerResult,
) -> ValidatorResult:
    return validate_fallback_output(
        task_id=task_id,
        worker_run_id=worker_run_id,
        sandbox_path=sandbox_path,
        figure_request=figure_request,
        worker_result=worker_result,
    ).validator


def validate_fallback_output(
    task_id: str,
    worker_run_id: str,
    sandbox_path: Path,
    figure_request: dict[str, Any],
    worker_result: FigureFallbackWorkerResult,
) -> FigureFallbackValidation:
    diagnostics = list(worker_result.diagnostics)
    checks: list[ValidatorCheck] = [_check_worker_identity(task_id, worker_run_id, worker_result)]

    if worker_result.proposal_path is None:
        checks.append(
            ValidatorCheck(
                name="proposal_present",
                status="failed",
                message="worker did not produce a fallback proposal",
            )
        )
        diagnostics.append("figure_fallback_proposal_missing: worker did not produce a proposal file.")
        return _validation(
            checks=checks,
            diagnostics=diagnostics,
        )

    if Path(worker_result.proposal_path).is_absolute():
        checks.append(
            ValidatorCheck(
                name="proposal_path",
                status="failed",
                message=f"proposal path must be relative to sandbox: {worker_result.proposal_path}",
            )
        )
        diagnostics.append(f"figure_fallback_proposal_path_error: absolute path rejected: {worker_result.proposal_path}")
        return _validation(checks=checks, diagnostics=diagnostics)
    if _path_has_traversal(worker_result.proposal_path):
        checks.append(
            ValidatorCheck(
                name="proposal_path",
                status="failed",
                message=f"proposal path escapes sandbox via path traversal: {worker_result.proposal_path}",
            )
        )
        diagnostics.append(f"figure_fallback_proposal_path_error: path escapes sandbox via path traversal: {worker_result.proposal_path}")
        return _validation(checks=checks, diagnostics=diagnostics)

    try:
        proposal_file = resolve_sandbox_path(sandbox_path, worker_result.proposal_path)
    except SandboxBoundaryError as exc:
        checks.append(ValidatorCheck(name="proposal_path", status="failed", message=str(exc)))
        diagnostics.append(str(exc))
        return _validation(checks=checks, diagnostics=diagnostics)

    if not proposal_file.exists():
        checks.append(
            ValidatorCheck(
                name="proposal_path",
                status="failed",
                message=f"proposal file is missing: {worker_result.proposal_path}",
            )
        )
        diagnostics.append(f"figure_fallback_proposal_missing: {worker_result.proposal_path}")
        return _validation(checks=checks, diagnostics=diagnostics)

    try:
        raw_data = json.loads(proposal_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        checks.append(
            ValidatorCheck(
                name="proposal_contract",
                status="failed",
                message=f"proposal could not be parsed: {exc}",
            )
        )
        diagnostics.append(f"figure_fallback_proposal_invalid_json: {exc}")
        return _validation(checks=checks, diagnostics=diagnostics)

    if not isinstance(raw_data, dict):
        checks.append(
            ValidatorCheck(
                name="proposal_contract",
                status="failed",
                message="proposal must be a JSON object",
            )
        )
        diagnostics.append("figure_fallback_proposal_invalid: proposal must be a JSON object.")
        return _validation(checks=checks, diagnostics=diagnostics)

    try:
        proposal = validate_proposal_contract(raw_data)
    except ValidationError as exc:
        checks.append(
            ValidatorCheck(
                name="proposal_contract",
                status="failed",
                message="proposal did not match the figure fallback contract",
            )
        )
        diagnostics.extend(_validation_error_diagnostics(exc))
        return _validation(checks=checks, diagnostics=diagnostics)

    sandbox_png_path = _resolve_optional_artifact_path(sandbox_path, proposal.output_paths.png_path)
    sandbox_svg_path = _resolve_optional_artifact_path(sandbox_path, proposal.output_paths.svg_path)

    checks.extend(
        [
            ValidatorCheck(name="proposal_path", status="passed"),
            ValidatorCheck(name="proposal_contract", status="passed"),
            _check_proposal_identity(task_id, worker_run_id, proposal, diagnostics),
            _check_proposal_identity_fields(proposal, diagnostics),
            _check_proposal_fields(proposal, figure_request, diagnostics),
            _check_source_metrics_and_field_sources(proposal, figure_request, diagnostics),
            _check_worker_artifact_paths(worker_result, sandbox_path, diagnostics),
            _check_proposal_artifacts(proposal, sandbox_path, diagnostics),
            _check_visual_artifacts(proposal, sandbox_path, diagnostics),
            _check_proposal_omitted_contract(proposal, diagnostics),
        ]
    )
    accepted = all(check.status == "passed" for check in checks)
    return FigureFallbackValidation(
        validator=ValidatorResult(
            accepted=accepted,
            proposal_type=proposal.proposal_type,
            checks=checks,
            diagnostics=_dedupe(diagnostics),
        ),
        proposal=proposal if accepted else None,
        sandbox_png_path=sandbox_png_path if accepted else None,
        sandbox_svg_path=sandbox_svg_path if accepted else None,
    )


class MockFigureFallbackWorker:
    worker_type = MOCK_WORKER_TYPE

    def __init__(self, failure_mode: str | None) -> None:
        self.failure_mode = failure_mode

    def run(
        self,
        request: FigureFallbackWorkerRequest,
        figure_request: dict[str, Any],
        sandbox_path: Path,
    ) -> FigureFallbackWorkerResult:
        diagnostics: list[str] = []
        observed_request_path = "mock-worker-observed-request.json"
        self._write_text(sandbox_path, observed_request_path, _json_text(figure_request))

        intent = figure_request.get("requested_chart_intent") if isinstance(figure_request.get("requested_chart_intent"), dict) else {}
        figure_id = _safe_string(intent.get("figure_id"), "bounded_chart_fallback")
        chart_type = _safe_string(intent.get("chart_type"), "unsupported")
        title = _safe_string(intent.get("title"), "Bounded Chart Fallback")
        x_field = _safe_string(intent.get("x"), "x")
        y_field = _safe_string(intent.get("y"), "y")
        group_by = intent.get("group_by") if isinstance(intent.get("group_by"), str) else None

        if self.failure_mode == "escape":
            png_path = "../figures/escape.png"
            svg_path = "../figures/escape.svg"
        else:
            png_path = f"{figure_id}-fallback.png"
            svg_path = f"{figure_id}-fallback.svg"
        proposal_y_field = "missing_metric_for_validator" if self.failure_mode == "missing_field" else y_field

        proposal = FigureFallbackProposal(
            task_id=request.task_id,
            worker_run_id=request.worker_run_id,
            figure_id=figure_id,
            chart_type=chart_type,
            title=title,
            x=x_field,
            y=proposal_y_field,
            group_by=group_by,
            source_metrics_fields=_bounded_source_metrics_fields(
                {**intent, "y": proposal_y_field},
            ),
            output_paths=FigureFallbackArtifacts(png_path=png_path, svg_path=svg_path),
            deterministic_refusal_reason=_deterministic_refusal_reason(figure_request),
            omitted=dict(_bounded_omitted_contract(figure_request)),
            diagnostics=["mock worker wrote proposal from bounded figure-request.json only."],
        )
        proposal_path = "figure-fallback-proposal.json"

        artifact_paths = [observed_request_path]
        if self.failure_mode == "escape":
            self._write_text(sandbox_path, proposal_path, _json_text(proposal.model_dump(mode="json")))
            diagnostics.append("figure_fallback_worker_rejected: mock worker proposed sandbox-escaping outputs.")
            return FigureFallbackWorkerResult(
                task_id=request.task_id,
                worker_run_id=request.worker_run_id,
                worker_type=self.worker_type,
                status="rejected",
                proposal_path=proposal_path,
                artifact_paths=artifact_paths + [proposal_path],
                diagnostics=diagnostics,
                summary={"headline": "Mock chart fallback worker proposed sandbox-escaping outputs."},
            )

        if self.failure_mode == "malformed_image":
            self._write_text(sandbox_path, png_path, "not a png\n")
            self._write_text(sandbox_path, svg_path, _mock_svg(title))
        elif self.failure_mode == "tiny_image":
            self._write_bytes(sandbox_path, png_path, _TINY_PNG_BYTES)
            self._write_text(
                sandbox_path,
                svg_path,
                '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect width="1" height="1"/></svg>\n',
            )
        else:
            self._write_bytes(sandbox_path, png_path, _mock_png(title))
            self._write_text(sandbox_path, svg_path, _mock_svg(title))
        self._write_text(sandbox_path, proposal_path, _json_text(proposal.model_dump(mode="json")))
        artifact_paths.extend([png_path, svg_path, proposal_path])
        diagnostics.append("figure_fallback_proposal_created: mock worker wrote bounded sandbox outputs only.")
        return FigureFallbackWorkerResult(
            task_id=request.task_id,
            worker_run_id=request.worker_run_id,
            worker_type=self.worker_type,
            status="proposal_created",
            proposal_path=proposal_path,
            artifact_paths=artifact_paths,
            diagnostics=diagnostics,
            summary={"headline": "Mock chart fallback worker produced a bounded sandbox proposal."},
        )

    def _write_bytes(self, sandbox_path: Path, raw_path: str, payload: bytes) -> None:
        path = resolve_sandbox_path(sandbox_path, raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def _write_text(self, sandbox_path: Path, raw_path: str, payload: str) -> None:
        path = resolve_sandbox_path(sandbox_path, raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")


def sandbox_display_path(task_path: Path, sandbox_path: Path, raw_path: str) -> str:
    resolved = resolve_sandbox_path(sandbox_path, raw_path)
    return resolved.resolve().relative_to(task_path.resolve()).as_posix()


def worker_output_display_paths(task_path: Path, sandbox_path: Path, raw_paths: list[str]) -> list[str]:
    outputs: list[str] = []
    for raw_path in raw_paths:
        try:
            outputs.append(sandbox_display_path(task_path, sandbox_path, raw_path))
        except SandboxBoundaryError:
            continue
    return outputs


def _bounded_omitted_contract(figure_request: dict[str, Any]) -> dict[str, str]:
    omitted = figure_request.get("omitted")
    if not isinstance(omitted, dict):
        return {}
    return {str(key): str(value) for key, value in omitted.items() if isinstance(value, str)}


def _check_worker_identity(
    task_id: str,
    worker_run_id: str,
    worker_result: FigureFallbackWorkerResult,
) -> ValidatorCheck:
    failures: list[str] = []
    if worker_result.task_id != task_id:
        failures.append(f"task_id mismatch: {worker_result.task_id}")
    if worker_result.worker_run_id != worker_run_id:
        failures.append(f"worker_run_id mismatch: {worker_result.worker_run_id}")
    if failures:
        return ValidatorCheck(name="worker_identity", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="worker_identity", status="passed")


def _check_proposal_identity(
    task_id: str,
    worker_run_id: str,
    proposal: FigureFallbackProposal,
    diagnostics: list[str],
) -> ValidatorCheck:
    failures: list[str] = []
    if proposal.task_id != task_id:
        failures.append(f"task_id mismatch: {proposal.task_id}")
    if proposal.worker_run_id != worker_run_id:
        failures.append(f"worker_run_id mismatch: {proposal.worker_run_id}")
    if failures:
        diagnostics.extend(f"figure_fallback_identity_error: {item}" for item in failures)
        return ValidatorCheck(name="proposal_identity", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="proposal_identity", status="passed")


def _check_proposal_identity_fields(
    proposal: FigureFallbackProposal,
    diagnostics: list[str],
) -> ValidatorCheck:
    if not _SAFE_FIGURE_ID_PATTERN.match(proposal.figure_id):
        message = "figure_id must use only letters, numbers, underscores, or hyphens and must not be path-like"
        diagnostics.append(f"figure_fallback_identity_error: {message}: {proposal.figure_id}")
        return ValidatorCheck(name="proposal_identity_fields", status="failed", message=message)
    return ValidatorCheck(name="proposal_identity_fields", status="passed")


def _check_proposal_fields(
    proposal: FigureFallbackProposal,
    figure_request: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    available_fields = {
        item
        for item in figure_request.get("available_fields", [])
        if isinstance(item, str)
    }
    available_fields.update(
        item
        for item in figure_request.get("metric_columns", [])
        if isinstance(item, str)
    )
    failures: list[str] = []
    if not proposal.deterministic_refusal_reason:
        failures.append("missing deterministic_refusal_reason")
    intent = figure_request.get("requested_chart_intent")
    if isinstance(intent, dict):
        for field_name in ["figure_id", "chart_type", "x", "y", "group_by"]:
            requested = intent.get(field_name)
            proposed = getattr(proposal, field_name)
            if isinstance(requested, str) and requested and proposed != requested:
                failures.append(f"proposal {field_name} does not match bounded request: {proposed}")
    referenced_fields = [proposal.x, proposal.y, *proposal.source_metrics_fields]
    if proposal.group_by:
        referenced_fields.append(proposal.group_by)
    for field in referenced_fields:
        if field not in available_fields:
            failures.append(f"field outside bounded metrics fields: {field}")
    for field in [proposal.x, proposal.y, *([proposal.group_by] if proposal.group_by else [])]:
        if field not in proposal.source_metrics_fields:
            failures.append(f"source_metrics_fields missing referenced field: {field}")
    if failures:
        diagnostics.extend(f"figure_fallback_field_error: {item}" for item in failures)
        return ValidatorCheck(name="bounded_fields_only", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="bounded_fields_only", status="passed")


def _check_source_metrics_and_field_sources(
    proposal: FigureFallbackProposal,
    figure_request: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    failures: list[str] = []
    artifacts = figure_request.get("artifacts")
    metrics_artifacts = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("artifact_id") == "metrics_normalized_csv"
    ] if isinstance(artifacts, list) else []
    if not metrics_artifacts:
        failures.append("bounded request did not identify source metrics artifact")
    else:
        path = metrics_artifacts[0].get("path")
        if not isinstance(path, str) or not path.endswith("metrics/normalized_metrics.csv"):
            failures.append("source metrics artifact path is missing or unexpected")

    field_sources = figure_request.get("field_sources")
    referenced_fields = [proposal.x, proposal.y, *([proposal.group_by] if proposal.group_by else [])]
    if isinstance(field_sources, dict):
        for field in referenced_fields:
            if field in field_sources:
                mappings = field_sources[field]
                if not isinstance(mappings, list) or not all(isinstance(item, str) for item in mappings):
                    failures.append(f"field_sources for {field} must be a list of strings")

    if failures:
        diagnostics.extend(f"figure_fallback_traceability_error: {item}" for item in failures)
        return ValidatorCheck(name="source_metrics_traceability", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="source_metrics_traceability", status="passed")


def _check_worker_artifact_paths(
    worker_result: FigureFallbackWorkerResult,
    sandbox_path: Path,
    diagnostics: list[str],
) -> ValidatorCheck:
    failures: list[str] = []
    paths = [path for path in worker_result.artifact_paths if isinstance(path, str) and path]
    if worker_result.proposal_path:
        paths.append(worker_result.proposal_path)
    for raw_path in paths:
        if Path(raw_path).is_absolute():
            failures.append(f"worker artifact path must be relative to sandbox: {raw_path}")
            continue
        if _path_has_traversal(raw_path):
            failures.append(f"worker artifact path escapes sandbox via path traversal: {raw_path}")
            continue
        try:
            resolve_sandbox_path(sandbox_path, raw_path)
        except SandboxBoundaryError as exc:
            failures.append(str(exc))
    if failures:
        diagnostics.extend(f"figure_fallback_artifact_error: {item}" for item in failures)
        return ValidatorCheck(name="worker_artifact_paths", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="worker_artifact_paths", status="passed")


def _check_proposal_artifacts(
    proposal: FigureFallbackProposal,
    sandbox_path: Path,
    diagnostics: list[str],
) -> ValidatorCheck:
    failures: list[str] = []
    artifact_paths = [
        proposal.output_paths.png_path,
        proposal.output_paths.svg_path,
    ]
    present_paths = [path for path in artifact_paths if isinstance(path, str) and path]
    if len(present_paths) != 2:
        failures.append("proposal must declare both PNG and SVG sandbox artifact paths")
    for raw_path in present_paths:
        if Path(raw_path).is_absolute():
            failures.append(f"sandbox artifact path must be relative: {raw_path}")
            continue
        if _path_has_traversal(raw_path):
            failures.append(f"sandbox artifact path escapes sandbox via path traversal: {raw_path}")
            continue
        try:
            resolved = resolve_sandbox_path(sandbox_path, raw_path)
        except SandboxBoundaryError as exc:
            failures.append(str(exc))
            continue
        if not resolved.exists():
            failures.append(f"sandbox artifact is missing: {raw_path}")
    if failures:
        diagnostics.extend(f"figure_fallback_artifact_error: {item}" for item in failures)
        return ValidatorCheck(name="sandbox_paths_only", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="sandbox_paths_only", status="passed")


def _check_visual_artifacts(
    proposal: FigureFallbackProposal,
    sandbox_path: Path,
    diagnostics: list[str],
) -> ValidatorCheck:
    failures: list[str] = []
    if proposal.output_paths.png_path:
        failures.extend(_validate_png(sandbox_path, proposal.output_paths.png_path))
    if proposal.output_paths.svg_path:
        failures.extend(_validate_svg(sandbox_path, proposal.output_paths.svg_path))
    if failures:
        diagnostics.extend(f"figure_fallback_visual_error: {item}" for item in failures)
        return ValidatorCheck(name="visual_artifacts", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="visual_artifacts", status="passed")


def _check_proposal_omitted_contract(
    proposal: FigureFallbackProposal,
    diagnostics: list[str],
) -> ValidatorCheck:
    required_keys = {
        "raw_rows",
        "raw_logs",
        "raw_source_bodies",
        "report_bodies",
        "pptx_internals",
        "worker_transcripts",
        "artifact_bodies",
    }
    missing = sorted(key for key in required_keys if key not in proposal.omitted)
    if missing:
        diagnostics.extend(f"figure_fallback_omitted_error: missing omitted key {key}" for key in missing)
        return ValidatorCheck(
            name="omitted_contract",
            status="failed",
            message=f"proposal omitted contract is missing keys: {', '.join(missing)}",
        )
    return ValidatorCheck(name="omitted_contract", status="passed")


def _bounded_source_metrics_fields(intent: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key in ["x", "y", "group_by"]:
        value = intent.get(key)
        if isinstance(value, str) and value not in fields:
            fields.append(value)
    return fields


def _deterministic_refusal_reason(figure_request: dict[str, Any]) -> str:
    diagnostics = figure_request.get("unsupported_chart_diagnostics")
    if isinstance(diagnostics, list) and diagnostics:
        first = diagnostics[0]
        if isinstance(first, dict) and isinstance(first.get("reason"), str):
            return first["reason"]
    return "Deterministic figures rejected this chart request."


def _mock_svg(title: str) -> str:
    escaped = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">'
        '<rect width="640" height="360" fill="#ffffff"/>'
        '<rect x="64" y="68" width="96" height="220" fill="#4E79A7"/>'
        '<rect x="196" y="118" width="96" height="170" fill="#F28E2B"/>'
        '<rect x="328" y="92" width="96" height="196" fill="#59A14F"/>'
        '<line x1="48" y1="288" x2="520" y2="288" stroke="#333333" stroke-width="3"/>'
        '<line x1="48" y1="48" x2="48" y2="288" stroke="#333333" stroke-width="3"/>'
        f'<text x="64" y="38" fill="#222222" font-size="24">{escaped}</text>'
        "</svg>\n"
    )


def _mock_png(title: str) -> bytes:
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([64, 68, 160, 288], fill="#4E79A7")
    draw.rectangle([196, 118, 292, 288], fill="#F28E2B")
    draw.rectangle([328, 92, 424, 288], fill="#59A14F")
    draw.line([48, 288, 520, 288], fill="#333333", width=3)
    draw.line([48, 48, 48, 288], fill="#333333", width=3)
    draw.text((64, 20), title[:80], fill="#222222")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _resolve_optional_artifact_path(sandbox_path: Path, raw_path: str | None) -> Path | None:
    if not raw_path or Path(raw_path).is_absolute():
        return None
    try:
        return resolve_sandbox_path(sandbox_path, raw_path)
    except SandboxBoundaryError:
        return None


def _validate_png(sandbox_path: Path, raw_path: str) -> list[str]:
    failures: list[str] = []
    if Path(raw_path).is_absolute():
        return [f"PNG path must be relative: {raw_path}"]
    if _path_has_traversal(raw_path):
        return [f"PNG path escapes sandbox via path traversal: {raw_path}"]
    try:
        path = resolve_sandbox_path(sandbox_path, raw_path)
    except SandboxBoundaryError as exc:
        return [str(exc)]
    if not path.exists():
        return [f"PNG is missing: {raw_path}"]
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            if width < MIN_FALLBACK_PNG_WIDTH or height < MIN_FALLBACK_PNG_HEIGHT:
                failures.append(
                    f"PNG dimensions are too small: {width}x{height}; minimum is {MIN_FALLBACK_PNG_WIDTH}x{MIN_FALLBACK_PNG_HEIGHT}"
                )
            rgb = image.convert("RGB")
            colors = rgb.getcolors(maxcolors=1_000_000)
            if colors is None:
                return failures
            if len(colors) <= 1:
                failures.append("PNG appears blank or single-color")
    except Exception as exc:
        failures.append(f"PNG could not be parsed: {exc}")
    return failures


def _validate_svg(sandbox_path: Path, raw_path: str) -> list[str]:
    failures: list[str] = []
    if Path(raw_path).is_absolute():
        return [f"SVG path must be relative: {raw_path}"]
    if _path_has_traversal(raw_path):
        return [f"SVG path escapes sandbox via path traversal: {raw_path}"]
    try:
        path = resolve_sandbox_path(sandbox_path, raw_path)
    except SandboxBoundaryError as exc:
        return [str(exc)]
    if not path.exists():
        return [f"SVG is missing: {raw_path}"]
    try:
        root = ElementTree.parse(path).getroot()
    except Exception as exc:
        return [f"SVG could not be parsed as XML: {exc}"]
    tag = root.tag.rsplit("}", 1)[-1] if "}" in root.tag else root.tag
    if tag != "svg":
        failures.append(f"SVG root element is not svg: {tag}")
    width = _svg_dimension(root.get("width"))
    height = _svg_dimension(root.get("height"))
    if (width is None or height is None) and root.get("viewBox"):
        viewbox = _svg_viewbox(root.get("viewBox") or "")
        if viewbox:
            width = width or viewbox[2]
            height = height or viewbox[3]
    if width is None or height is None:
        failures.append("SVG dimensions are missing")
    elif width < MIN_FALLBACK_SVG_WIDTH or height < MIN_FALLBACK_SVG_HEIGHT:
        failures.append(
            f"SVG dimensions are too small: {width:g}x{height:g}; minimum is {MIN_FALLBACK_SVG_WIDTH}x{MIN_FALLBACK_SVG_HEIGHT}"
        )
    if not _svg_has_visible_content(root):
        failures.append("SVG appears blank")
    return failures


def _svg_has_visible_content(root: ElementTree.Element) -> bool:
    visual_tags = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "image"}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1] if "}" in element.tag else element.tag
        if tag not in visual_tags:
            continue
        if tag == "text" and "".join(element.itertext()).strip():
            return True
        if tag == "image":
            return True
        if _svg_paint_is_visible(element.get("fill")) or _svg_paint_is_visible(element.get("stroke")):
            return True
        style = element.get("style")
        if style and _svg_style_has_visible_paint(style):
            return True
    return False


def _svg_style_has_visible_paint(style: str) -> bool:
    for declaration in style.split(";"):
        key, sep, value = declaration.partition(":")
        if sep and key.strip() in {"fill", "stroke"} and _svg_paint_is_visible(value):
            return True
    return False


def _svg_paint_is_visible(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized not in {"", "none", "transparent", "#fff", "#ffffff", "white", "rgb(255,255,255)", "rgb(255, 255, 255)"}


def _svg_dimension(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    return float(match.group(1))


def _svg_viewbox(value: str) -> tuple[float, float, float, float] | None:
    parts = re.split(r"[\s,]+", value.strip())
    if len(parts) != 4:
        return None
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _validation(
    checks: list[ValidatorCheck],
    diagnostics: list[str],
    proposal_type: str = FALLBACK_PROPOSAL_TYPE,
) -> FigureFallbackValidation:
    return FigureFallbackValidation(
        validator=ValidatorResult(
            accepted=False,
            proposal_type=proposal_type,
            checks=checks,
            diagnostics=_dedupe(diagnostics),
        )
    )


def _path_has_traversal(path_text: str) -> bool:
    return any(part == ".." for part in Path(path_text).parts)


def _json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _safe_string(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _validation_error_diagnostics(exc: ValidationError) -> list[str]:
    diagnostics: list[str] = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", []))
        diagnostics.append(f"figure_fallback_contract_error: {location or 'proposal'}: {error.get('msg')}")
    return diagnostics


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
