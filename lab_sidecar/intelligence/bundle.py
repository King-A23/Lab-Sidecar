from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.scan import scan_metric_candidates
from lab_sidecar.core.models import TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path, to_manifest_path
from lab_sidecar.mcp.responses import compact_task_outputs, task_summary


DEFAULT_SUMMARY_TOKENS = 800
DEFAULT_PREVIEW_ROWS = 20
DEFAULT_LOG_TAIL_LINES = 80
MAX_PREVIEW_ROWS = 20
MAX_LOG_TAIL_LINES = 80
MAX_TEXT_CHARS = 4000
MAX_ARTIFACTS = 40
MAX_JSON_PREVIEW_BYTES = 64 * 1024


@dataclass(frozen=True)
class ContextBudget:
    summary_tokens: int = DEFAULT_SUMMARY_TOKENS
    preview_rows: int = DEFAULT_PREVIEW_ROWS
    log_tail_lines: int = DEFAULT_LOG_TAIL_LINES

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "ContextBudget":
        value = value or {}
        return cls(
            summary_tokens=_bounded_int(value.get("summary_tokens"), DEFAULT_SUMMARY_TOKENS, 100, 4000),
            preview_rows=_bounded_int(value.get("preview_rows"), DEFAULT_PREVIEW_ROWS, 0, MAX_PREVIEW_ROWS),
            log_tail_lines=_bounded_int(value.get("log_tail_lines"), DEFAULT_LOG_TAIL_LINES, 0, MAX_LOG_TAIL_LINES),
        )


def build_input_bundle(
    root: Path,
    record: TaskRecord,
    worker_run_id: str,
    user_goal: str,
    desired_outputs: list[str] | None = None,
    context_budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    budget = ContextBudget.from_dict(context_budget)
    task_path = resolve_workspace_path(record.paths.task_dir, root)

    return {
        "schema_version": "2.1",
        "task_id": record.task_id,
        "worker_run_id": worker_run_id,
        "user_goal": _short_text(user_goal, MAX_TEXT_CHARS),
        "desired_outputs": desired_outputs or [],
        "context_budget": {
            "summary_tokens": budget.summary_tokens,
            "preview_rows": budget.preview_rows,
            "log_tail_lines": budget.log_tail_lines,
        },
        "task": {
            **task_summary(root, record),
            **compact_task_outputs(root, record),
        },
        "artifacts": [_artifact_metadata(root, artifact) for artifact in record.artifacts[:MAX_ARTIFACTS]],
        "logs": {
            "stdout_tail": _bounded_log_tail(resolve_workspace_path(record.paths.stdout, root), budget.log_tail_lines),
            "stderr_tail": _bounded_log_tail(resolve_workspace_path(record.paths.stderr, root), budget.log_tail_lines),
        },
        "data_previews": _build_data_previews(root, task_path, budget.preview_rows),
        "candidate_previews": _build_candidate_previews(root, record, budget.preview_rows),
        "omitted": omitted_contract(),
    }


def omitted_contract() -> dict[str, str]:
    return {
        "full_command": "omitted_by_default",
        "full_stdout": "omitted_by_default",
        "full_stderr": "omitted_by_default",
        "metrics_rows": "omitted_by_default",
        "report_body": "omitted_by_default",
        "ppt_content": "omitted_by_default",
        "worker_prompt_response": "omitted_by_default",
        "artifact_bodies": "omitted_by_default",
        "full_data_files": "omitted_by_default",
    }


def _artifact_metadata(root: Path, artifact: Any) -> dict[str, Any]:
    artifact_path = resolve_workspace_path(artifact.path, root)
    return {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "path": artifact.path,
        "description": artifact.description,
        "source_paths": artifact.source_paths,
        "exists": artifact_path.exists(),
        "size_bytes": artifact_path.stat().st_size if artifact_path.exists() else None,
        "sha256": _file_hash(artifact_path) if artifact_path.exists() else None,
    }


def _build_data_previews(root: Path, task_path: Path, preview_rows: int) -> list[dict[str, Any]]:
    if preview_rows <= 0:
        return []

    previews: list[dict[str, Any]] = []
    candidates = [
        task_path / "metrics" / "collection-summary.json",
        task_path / "metrics" / "scenario-summary.json",
        task_path / "metrics" / "normalized_metrics.csv",
        task_path / "metrics" / "normalized_metrics.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        if path.suffix.lower() == ".csv":
            previews.append(_csv_preview(root, path, preview_rows))
        elif path.suffix.lower() == ".json":
            previews.append(_json_preview(root, path, preview_rows))
    return previews


def _build_candidate_previews(root: Path, record: TaskRecord, preview_rows: int) -> list[dict[str, Any]]:
    if preview_rows <= 0:
        return []

    previews: list[dict[str, Any]] = []
    task_path = resolve_workspace_path(record.paths.task_dir, root)
    existing_paths = {
        task_path / "metrics" / "collection-summary.json",
        task_path / "metrics" / "scenario-summary.json",
        task_path / "metrics" / "normalized_metrics.csv",
        task_path / "metrics" / "normalized_metrics.json",
    }
    for candidate in scan_metric_candidates(root, record):
        if candidate.path in existing_paths or candidate.path.resolve() in {path.resolve() for path in existing_paths if path.exists()}:
            continue
        if candidate.path.suffix.lower() == ".csv":
            preview = _csv_preview(root, candidate.path, preview_rows)
        elif candidate.path.suffix.lower() == ".json":
            preview = _json_preview(root, candidate.path, preview_rows)
        else:
            continue
        preview["candidate_origin"] = candidate.origin
        preview["is_metric_candidate"] = True
        previews.append(preview)
    return previews[:MAX_ARTIFACTS]


def _csv_preview(root: Path, path: Path, preview_rows: int) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    columns: list[str] = []
    sample_truncated = False
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames or [])
        for row in reader:
            if len(rows) < preview_rows:
                rows.append(dict(row))
                continue
            sample_truncated = True
            break
    return {
        "path": to_manifest_path(path, root),
        "type": "csv",
        "size_bytes": path.stat().st_size,
        "sha256": _file_hash(path),
        "columns": columns,
        "row_sample": rows,
        "row_sample_count": len(rows),
        "inferred_types": _infer_column_types(rows, columns),
        "null_counts": _sample_null_counts(rows, columns),
        "descriptive_stats": _sample_descriptive_stats(rows, columns),
        "row_count_if_scanned": None,
        "sample_truncated": sample_truncated,
    }


def _json_preview(root: Path, path: Path, preview_rows: int) -> dict[str, Any]:
    size_bytes = path.stat().st_size
    sample_omitted = None
    if size_bytes > MAX_JSON_PREVIEW_BYTES:
        data = None
        sample_omitted = f"json_preview_limited_to_{MAX_JSON_PREVIEW_BYTES}_bytes"
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            data = None
            sample_omitted = "json_parse_failed"

    if isinstance(data, list):
        sample = data[:preview_rows]
        keys = sorted({key for item in sample if isinstance(item, dict) for key in item.keys()})
        total = len(data)
        sample_truncated = len(data) > len(sample)
    elif isinstance(data, dict):
        sample = _compact_json_dict(data)
        keys = sorted(data.keys())
        total = None
        sample_truncated = False
    else:
        sample = None
        keys = []
        total = None
        sample_truncated = False
    return {
        "path": to_manifest_path(path, root),
        "type": "json",
        "size_bytes": size_bytes,
        "sha256": _file_hash(path),
        "keys": keys,
        "columns": keys,
        "sample": sample,
        "row_sample": sample if isinstance(sample, list) else [],
        "row_sample_count": len(sample) if isinstance(sample, list) else None,
        "inferred_types": _infer_column_types(sample, keys) if isinstance(sample, list) else {},
        "null_counts": _sample_null_counts(sample, keys) if isinstance(sample, list) else {},
        "descriptive_stats": _sample_descriptive_stats(sample, keys) if isinstance(sample, list) else {},
        "row_count_if_scanned": total,
        "sample_truncated": sample_truncated,
        "sample_omitted": sample_omitted,
    }


def _infer_column_types(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, str]:
    inferred: dict[str, str] = {}
    for column in columns:
        values = [_coerce_non_empty(row.get(column)) for row in rows]
        values = [value for value in values if value is not None]
        if not values:
            inferred[column] = "unknown"
        elif all(_as_float(value) is not None for value in values):
            inferred[column] = "number"
        elif all(_as_bool(value) is not None for value in values):
            inferred[column] = "boolean"
        else:
            inferred[column] = "string"
    return inferred


def _sample_null_counts(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, int]:
    return {
        column: sum(1 for row in rows if _coerce_non_empty(row.get(column)) is None)
        for column in columns
    }


def _sample_descriptive_stats(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for column in columns:
        values = [_as_float(row.get(column)) for row in rows]
        numeric = [value for value in values if value is not None and math.isfinite(value)]
        if not numeric:
            continue
        stats[column] = {
            "count": float(len(numeric)),
            "min": min(numeric),
            "max": max(numeric),
            "mean": sum(numeric) / len(numeric),
        }
    return stats


def _coerce_non_empty(value: Any) -> Any | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _as_float(value: Any) -> float | None:
    value = _coerce_non_empty(value)
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    value = _coerce_non_empty(value)
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    return None


def _compact_json_dict(data: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            compact[key] = value
        elif isinstance(value, list):
            compact[key] = {"type": "list", "count": len(value)}
        elif isinstance(value, dict):
            compact[key] = {"type": "object", "keys": sorted(value.keys())[:20]}
        else:
            compact[key] = {"type": type(value).__name__}
    return compact


def _bounded_log_tail(path: Path, line_count: int) -> list[str]:
    if line_count <= 0 or not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [_short_text(line, 1000) for line in lines[-min(line_count, MAX_LOG_TAIL_LINES) :]]


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _short_text(value: str | None, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)
