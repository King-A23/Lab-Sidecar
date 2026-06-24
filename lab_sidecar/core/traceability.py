from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_sidecar.core.models import ArtifactRecord, TaskRecord, effective_run_mode
from lab_sidecar.core.paths import resolve_workspace_path
from lab_sidecar.core.provenance import file_provenance, python_executable


TRACEABILITY_ARTIFACT_ID = "provenance_traceability_json"
TRACEABILITY_RELATIVE_PATH = Path("provenance") / "traceability.json"
TRACEABILITY_SCHEMA_VERSION = "1"
MAX_TRACE_SOURCES = 200


def refresh_traceability(root: Path, record: TaskRecord) -> TaskRecord:
    """Refresh the task-local provenance index and register it in the manifest."""
    root = root.resolve()
    task_path = resolve_workspace_path(record.paths.task_dir, root).resolve()
    trace_path = task_path / TRACEABILITY_RELATIVE_PATH
    trace_path.parent.mkdir(parents=True, exist_ok=True)

    artifacts = [
        _artifact_with_provenance(root, task_path, artifact)
        for artifact in record.artifacts
        if artifact.artifact_id != TRACEABILITY_ARTIFACT_ID
    ]
    record.artifacts = artifacts

    payload = build_traceability_index(root, record, task_path, artifacts)
    _write_json(trace_path, payload)

    trace_artifact = _artifact_with_provenance(
        root,
        task_path,
        ArtifactRecord(
            artifact_id=TRACEABILITY_ARTIFACT_ID,
            type="provenance",
            path=TRACEABILITY_RELATIVE_PATH.as_posix(),
            description="Task-local provenance and traceability index",
            source_paths=_traceability_source_paths(task_path),
        ),
    )
    record.artifacts = [
        artifact
        for artifact in record.artifacts
        if artifact.artifact_id != TRACEABILITY_ARTIFACT_ID
    ]
    record.artifacts.append(trace_artifact)
    return record


def build_traceability_index(
    root: Path,
    record: TaskRecord,
    task_path: Path,
    artifacts: list[ArtifactRecord],
) -> dict[str, Any]:
    collection_summary = _read_json(task_path / "metrics" / "collection-summary.json")
    scenario_summary = _read_json(task_path / "metrics" / "scenario-summary.json")
    figure_summary = _read_json(task_path / "figures" / "figure-summary.json")
    report_summary = _read_json(task_path / "reports" / "report-summary.json")
    slides_summary = _read_json(task_path / "slides" / "slides-summary.json")
    source_refs = _read_json(task_path / "raw" / "source_refs.json")

    warnings: list[str] = []
    sources = _build_sources(collection_summary, source_refs, warnings)
    trace_artifacts = [_artifact_to_trace(root, task_path, artifact) for artifact in artifacts]
    report_claims = _claim_traces_from_summary(report_summary)
    slide_claims = _claim_traces_from_summary(slides_summary)

    return {
        "schema_version": TRACEABILITY_SCHEMA_VERSION,
        "task_id": record.task_id,
        "generated_at": _now_iso(),
        "task": {
            "mode": record.mode,
            "status": record.status.value,
            "working_dir": record.working_dir,
            "manifest_path": "manifest.json",
            "command_path": "reproduce/command.txt" if (task_path / "reproduce" / "command.txt").exists() else None,
            "run_spec_path": "reproduce/run.json" if (task_path / "reproduce" / "run.json").exists() else None,
            "run_mode": effective_run_mode(record),
            "argv": record.argv,
            "safe_profile": record.safe_profile,
            "source_path": record.source_path,
        },
        "environment": {
            "python_executable": python_executable(),
            "env_path": "reproduce/env.json" if (task_path / "reproduce" / "env.json").exists() else None,
            "git_path": "reproduce/git.json" if (task_path / "reproduce" / "git.json").exists() else None,
            "dependencies_path": "reproduce/dependencies.json"
            if (task_path / "reproduce" / "dependencies.json").exists()
            else None,
        },
        "sources": sources,
        "artifacts": trace_artifacts,
        "metric_lineage": _metric_lineage(task_path, collection_summary, scenario_summary),
        "figure_lineage": _figure_lineage(task_path, figure_summary),
        "report_lineage": _report_lineage(report_summary),
        "slide_lineage": _slide_lineage(slides_summary),
        "claim_traces": [*report_claims, *slide_claims],
        "omitted": _omitted_contract(root, task_path, record),
        "traceability_artifact": {
            "artifact_id": TRACEABILITY_ARTIFACT_ID,
            "path": TRACEABILITY_RELATIVE_PATH.as_posix(),
            "self_digest_note": "self digest is recorded in manifest/package metadata, not inside the self-referential trace body",
        },
        "warnings": [*warnings, *_summary_warnings(collection_summary, figure_summary, report_summary, slides_summary)],
    }


def _artifact_with_provenance(root: Path, task_path: Path, artifact: ArtifactRecord) -> ArtifactRecord:
    path = _resolve_task_or_workspace_path(artifact.path, root, task_path)
    size_bytes = artifact.size_bytes
    sha256 = artifact.sha256
    if path.exists() and path.is_file():
        if artifact.type == "log":
            size_bytes = path.stat().st_size
            sha256 = None
        else:
            provenance = file_provenance(path)
            size_bytes = int(provenance["size_bytes"])
            sha256 = str(provenance["sha256"])
    return artifact.model_copy(update={"size_bytes": size_bytes, "sha256": sha256})


def _artifact_to_trace(root: Path, task_path: Path, artifact: ArtifactRecord) -> dict[str, Any]:
    path = _resolve_task_or_workspace_path(artifact.path, root, task_path)
    item: dict[str, Any] = {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "path": _portable_task_path(path, artifact.path, task_path),
        "description": artifact.description,
        "source_paths": [
            _portable_task_path(_resolve_task_or_workspace_path(source, root, task_path), source, task_path)
            for source in artifact.source_paths
        ],
        "exists": path.is_file(),
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
    }
    if artifact.type == "log":
        item["digest_omitted_reason"] = "full log files are not hashed in traceability by default"
    elif path.exists() and not path.is_file():
        item["digest_omitted_reason"] = "path is not a regular file"
    elif not path.exists():
        item["digest_omitted_reason"] = "artifact file is not present"
    return item


def _build_sources(
    collection_summary: dict[str, Any],
    source_refs: dict[str, Any],
    warnings: list[str],
) -> list[dict[str, Any]]:
    sources_by_path: dict[str, dict[str, Any]] = {}

    for item in collection_summary.get("processed_files") or []:
        if not isinstance(item, dict) or not isinstance(item.get("source_file"), str):
            continue
        source = {
            "path": item["source_file"],
            "role": "metrics_source",
            "file_type": item.get("file_type"),
            "row_count": item.get("row_count"),
            "detected_fields": item.get("detected_fields") or [],
            "mapped_fields": item.get("mapped_fields") or [],
            "size_bytes": None,
            "sha256": None,
        }
        provenance = item.get("source_provenance")
        if isinstance(provenance, dict):
            source.update(_provenance_fields(provenance))
        sources_by_path[item["source_file"]] = source

    for item in collection_summary.get("candidates") or []:
        if not isinstance(item, dict) or not isinstance(item.get("source_file"), str):
            continue
        path = item["source_file"]
        if path in sources_by_path:
            continue
        source = {
            "path": path,
            "role": "metric_candidate",
            "origin": item.get("origin"),
            "suffix": item.get("suffix"),
            "size_bytes": None,
            "sha256": None,
        }
        provenance = item.get("source_provenance")
        if isinstance(provenance, dict):
            source.update(_provenance_fields(provenance))
        sources_by_path[path] = source

    for item in _sources_from_source_refs(source_refs):
        path = item.get("path")
        if isinstance(path, str) and path not in sources_by_path:
            sources_by_path[path] = item

    sources = sorted(sources_by_path.values(), key=lambda source: str(source.get("path", "")))
    if len(sources) > MAX_TRACE_SOURCES:
        warnings.append(f"traceability sources truncated from {len(sources)} to {MAX_TRACE_SOURCES}")
        return sources[:MAX_TRACE_SOURCES]
    return sources


def _sources_from_source_refs(source_refs: dict[str, Any]) -> list[dict[str, Any]]:
    if not source_refs:
        return []
    sources: list[dict[str, Any]] = []
    source_path = source_refs.get("source_path")
    if isinstance(source_path, str):
        source = {
            "path": source_path,
            "role": "ingested_source",
            "source_type": source_refs.get("source_type"),
            "size_bytes": None,
            "sha256": None,
        }
        source.update(_provenance_fields(source_refs))
        sources.append(source)

    candidates = source_refs.get("candidate_file_refs")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                sources.append(_source_ref_item(item, role="ingested_candidate"))
        return sources

    for item in source_refs.get("children") or []:
        if not isinstance(item, dict) or item.get("type") != "file" or item.get("is_candidate") is not True:
            continue
        if isinstance(item.get("path"), str):
            sources.append(_source_ref_item(item, role="ingested_candidate"))
    return sources


def _source_ref_item(item: dict[str, Any], role: str) -> dict[str, Any]:
    source = {
        "path": item["path"],
        "role": role,
        "name": item.get("name"),
        "suffix": item.get("suffix"),
        "size_bytes": None,
        "sha256": None,
    }
    source.update(_provenance_fields(item))
    return source


def _metric_lineage(task_path: Path, collection_summary: dict[str, Any], scenario_summary: dict[str, Any]) -> dict[str, Any]:
    metrics_path = task_path / "metrics" / "normalized_metrics.csv"
    columns, row_count = _csv_header_and_count(metrics_path)
    raw_processed = collection_summary.get("processed_files")
    processed = raw_processed if isinstance(raw_processed, list) else []
    source_files = [
        item["source_file"]
        for item in processed
        if isinstance(item, dict) and isinstance(item.get("source_file"), str)
    ]
    output_files = collection_summary.get("output_files")
    return {
        "present": metrics_path.exists(),
        "path": "metrics/normalized_metrics.csv",
        "json_path": "metrics/normalized_metrics.json" if (task_path / "metrics" / "normalized_metrics.json").exists() else None,
        "collection_summary_path": "metrics/collection-summary.json"
        if (task_path / "metrics" / "collection-summary.json").exists()
        else None,
        "scenario_summary_path": "metrics/scenario-summary.json"
        if (task_path / "metrics" / "scenario-summary.json").exists()
        else None,
        "scenario_type": scenario_summary.get("scenario_type") if scenario_summary else None,
        "primary_metric": scenario_summary.get("primary_metric") if scenario_summary else None,
        "scenario_claim_limit": _scenario_claim_limit(scenario_summary),
        "row_count": row_count if row_count is not None else collection_summary.get("row_count", 0),
        "columns": columns,
        "detected_fields": collection_summary.get("detected_fields") or [],
        "source_files": source_files,
        "output_files": output_files if isinstance(output_files, list) else [],
    }


def _scenario_claim_limit(scenario_summary: dict[str, Any]) -> str | None:
    if not scenario_summary:
        return None
    seed_aggregates = scenario_summary.get("seed_aggregates")
    if isinstance(seed_aggregates, dict) and isinstance(seed_aggregates.get("claim_limit"), str):
        return seed_aggregates["claim_limit"]
    return "descriptive scenario summary only; no statistical significance is inferred"


def _figure_lineage(task_path: Path, figure_summary: dict[str, Any]) -> dict[str, Any]:
    raw_figures = figure_summary.get("generated_figures") or figure_summary.get("figures") or []
    figures: list[dict[str, Any]] = []
    for item in raw_figures:
        if not isinstance(item, dict):
            continue
        figure_id = str(item.get("figure_id") or "")
        png_path = item.get("png_path") or item.get("png")
        svg_path = item.get("svg_path") or item.get("svg")
        paths = [path for path in [png_path, svg_path] if isinstance(path, str)]
        columns = [
            str(value)
            for value in [item.get("x"), item.get("y"), item.get("group_by")]
            if value not in (None, "")
        ]
        figures.append(
            {
                "figure_id": figure_id,
                "chart_type": item.get("chart_type"),
                "source": item.get("source") or "deterministic",
                "worker_run_id": item.get("worker_run_id"),
                "validation_status": item.get("validation_status"),
                "artifact_ids": [artifact_id for artifact_id in _figure_artifact_ids(figure_id, paths) if artifact_id],
                "paths": paths,
                "source_metrics": item.get("source_metrics") or figure_summary.get("source_metrics"),
                "columns": columns,
                "units": item.get("units") or {},
                "field_sources": item.get("field_sources") or {},
                "fallback_lineage": _bounded_fallback_lineage(item.get("fallback_lineage")),
            }
        )
    return {
        "present": bool(figure_summary),
        "summary_path": "figures/figure-summary.json" if figure_summary else None,
        "spec_path": "figures/figure-spec.yaml" if (task_path / "figures" / "figure-spec.yaml").exists() else None,
        "figure_count": int(figure_summary.get("figure_count") or len(figures)) if figure_summary else 0,
        "figures": figures,
        "unsupported_chart_diagnostics": figure_summary.get("unsupported_chart_diagnostics") or [],
        "fallback": _bounded_figure_fallback(figure_summary.get("fallback")),
        "warnings": figure_summary.get("warnings") or [],
        "errors": figure_summary.get("errors") or [],
    }


def _report_lineage(report_summary: dict[str, Any]) -> dict[str, Any]:
    claims = _claim_traces_from_summary(report_summary)
    return {
        "present": bool(report_summary),
        "path": report_summary.get("report_path") if report_summary else None,
        "summary_path": report_summary.get("summary_path") if report_summary else None,
        "template": report_summary.get("template") if report_summary else None,
        "source_artifacts": report_summary.get("source_artifacts") or report_summary.get("generated_from") or [],
        "claim_trace_count": len(claims),
        "claim_ids": [claim.get("claim_id") for claim in claims if claim.get("claim_id")],
    }


def _slide_lineage(slides_summary: dict[str, Any]) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for slide in slides_summary.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        slides.append(
            {
                "slide_index": slide.get("slide_index"),
                "title": slide.get("title"),
                "purpose": slide.get("purpose"),
                "source_artifacts": slide.get("source_artifacts") or [],
                "evidence": slide.get("evidence") or [],
                "empty_source_reason": slide.get("empty_source_reason"),
            }
        )
    return {
        "present": bool(slides_summary),
        "pptx_path": slides_summary.get("pptx_path") if slides_summary else None,
        "summary_path": slides_summary.get("summary_path") if slides_summary else None,
        "template": slides_summary.get("template") if slides_summary else None,
        "slide_count": slides_summary.get("slide_count") if slides_summary else 0,
        "slides": slides,
        "included_figures": slides_summary.get("included_figures") or [],
        "metrics": _bounded_slide_metrics(slides_summary.get("included_metrics") or {}),
    }


def _bounded_slide_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    if not metrics:
        return {}
    return {
        "present": metrics.get("present"),
        "path": metrics.get("path"),
        "row_count": metrics.get("row_count"),
        "key_columns": metrics.get("key_columns") or [],
        "numeric_columns": [
            item.get("column")
            for item in metrics.get("numeric") or []
            if isinstance(item, dict) and item.get("column")
        ],
    }


def _bounded_figure_fallback(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "mode": value.get("mode"),
        "attempted": value.get("attempted"),
        "worker_run_id": value.get("worker_run_id"),
        "status": value.get("status"),
        "request_path": value.get("request_path"),
        "validator_result_path": value.get("validator_result_path"),
        "adoption_record_path": value.get("adoption_record_path"),
        "validation_status": value.get("validation_status"),
        "validation_checks": _bounded_validation_checks(value.get("validation_checks")),
        "adopted_figures": _bounded_adopted_figures(value.get("adopted_figures")),
        "adopted_artifact_paths": [
            item for item in value.get("adopted_artifact_paths") or [] if isinstance(item, str)
        ],
        "diagnostics": value.get("diagnostics") or [],
    }


def _bounded_fallback_lineage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        "source_metrics": value.get("source_metrics"),
        "fields_used": [item for item in value.get("fields_used") or [] if isinstance(item, str)],
        "field_sources": _bounded_string_list_mapping(value.get("field_sources")),
        "worker_run_id": value.get("worker_run_id"),
        "request_path": value.get("request_path"),
        "worker_request_path": value.get("worker_request_path"),
        "worker_result_path": value.get("worker_result_path"),
        "validator_result_path": value.get("validator_result_path"),
        "sandbox_png_path": value.get("sandbox_png_path"),
        "sandbox_svg_path": value.get("sandbox_svg_path"),
        "adopted_png_path": value.get("adopted_png_path"),
        "adopted_svg_path": value.get("adopted_svg_path"),
    }


def _bounded_adopted_figures(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    figures: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        figures.append(
            {
                "figure_id": item.get("figure_id"),
                "chart_type": item.get("chart_type"),
                "png": item.get("png"),
                "svg": item.get("svg"),
                "source_metrics": item.get("source_metrics"),
                "fields_used": [field for field in item.get("fields_used") or [] if isinstance(field, str)],
                "field_sources": _bounded_string_list_mapping(item.get("field_sources")),
            }
        )
    return figures


def _bounded_validation_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    checks: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "name": item.get("name"),
                "status": item.get("status"),
                "message": item.get("message"),
            }
        )
    return checks


def _bounded_string_list_mapping(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, raw_items in value.items():
        if not isinstance(key, str) or not isinstance(raw_items, list):
            continue
        items = [item for item in raw_items if isinstance(item, str)]
        if items:
            result[key] = items
    return result


def _claim_traces_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    traces = summary.get("claim_traces") if isinstance(summary, dict) else None
    if not isinstance(traces, list):
        return []
    return [trace for trace in traces if isinstance(trace, dict)]


def _omitted_contract(root: Path, task_path: Path, record: TaskRecord) -> list[dict[str, Any]]:
    omitted: list[dict[str, Any]] = []
    _add_omitted_if_exists(omitted, task_path / "stdout.log", task_path, "log", "full stdout body omitted")
    _add_omitted_if_exists(omitted, task_path / "stderr.log", task_path, "log", "full stderr body omitted")
    _add_omitted_if_exists(
        omitted,
        task_path / "raw" / "source_refs.json",
        task_path,
        "raw",
        "full raw source reference body omitted; distilled source hashes are recorded separately",
    )
    _add_omitted_if_exists(omitted, task_path / "worker.log", task_path, "worker", "worker transcript body omitted")
    _add_omitted_if_exists(omitted, task_path / "worker.err.log", task_path, "worker", "worker error log body omitted")
    intelligence_path = task_path / "intelligence"
    if intelligence_path.exists():
        _add_omitted_if_exists(omitted, intelligence_path, task_path, "worker", "worker audit directory omitted")
        for audit_path in sorted(
            [
                *intelligence_path.glob("*/ai-provider-prompt.json"),
                *intelligence_path.glob("*/ai-provider-response.json"),
            ]
        ):
            _add_omitted_if_exists(omitted, audit_path, task_path, "worker", "worker prompt/response body omitted")
        for sandbox_path in sorted(intelligence_path.glob("*/sandbox")):
            _add_omitted_if_exists(omitted, sandbox_path, task_path, "sandbox", "temporary sandbox files omitted")
    _add_omitted_if_exists(omitted, root / ".lab-sidecar" / "index.sqlite", root, "index", "local SQLite index omitted")
    if record.source_path:
        omitted.append(
            {
                "path": record.source_path,
                "category": "raw_source",
                "reason": "raw source files are referenced by path/hash but not copied or embedded",
            }
        )
    return _dedupe_entries(omitted)


def _add_omitted_if_exists(
    omitted: list[dict[str, Any]],
    path: Path,
    base: Path,
    category: str,
    reason: str,
) -> None:
    if not path.exists():
        return
    omitted.append(
        {
            "path": _relative_to(path, base),
            "category": category,
            "reason": reason,
        }
    )


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        key = (str(entry.get("path", "")), str(entry.get("category", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _summary_warnings(*summaries: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for summary in summaries:
        for key in ["warnings", "errors", "figure_warnings"]:
            value = summary.get(key)
            if isinstance(value, list):
                warnings.extend(str(item) for item in value)
    return warnings


def _traceability_source_paths(task_path: Path) -> list[str]:
    candidates = [
        "manifest.json",
        "raw/source_refs.json",
        "metrics/normalized_metrics.csv",
        "metrics/collection-summary.json",
        "metrics/scenario-summary.json",
        "figures/figure-spec.yaml",
        "figures/figure-summary.json",
        "reports/report-summary.json",
        "slides/slides-summary.json",
        "reproduce/command.txt",
        "reproduce/run.json",
        "reproduce/env.json",
        "reproduce/git.json",
        "reproduce/dependencies.json",
    ]
    return [path for path in candidates if (task_path / path).exists()]


def _figure_artifact_ids(figure_id: str, paths: list[str]) -> list[str]:
    artifact_ids: list[str] = []
    if not figure_id:
        return artifact_ids
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix == ".png":
            artifact_ids.append(f"figure_{figure_id}_png")
        elif suffix == ".svg":
            artifact_ids.append(f"figure_{figure_id}_svg")
    return artifact_ids


def _csv_header_and_count(path: Path) -> tuple[list[str], int | None]:
    if not path.exists():
        return [], None
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            return [str(column) for column in header], sum(1 for _row in reader)
    except OSError:
        return [], None


def _provenance_fields(data: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if isinstance(data.get("sha256"), str):
        fields["sha256"] = data["sha256"]
    if isinstance(data.get("size_bytes"), int):
        fields["size_bytes"] = data["size_bytes"]
    return fields


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_task_or_workspace_path(path_text: str, root: Path, task_path: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    task_candidate = task_path / path
    if task_candidate.exists():
        return task_candidate
    return resolve_workspace_path(path_text, root)


def _relative_to(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _portable_task_path(path: Path, fallback: str, task_path: Path) -> str:
    try:
        return path.resolve().relative_to(task_path.resolve()).as_posix()
    except ValueError:
        return fallback


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
