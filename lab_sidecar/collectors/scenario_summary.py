from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from lab_sidecar.core.models import TaskRecord


SCENARIO_SUMMARY_SCHEMA_VERSION = "1"
SCENARIO_SUMMARY_RELATIVE_PATH = "metrics/scenario-summary.json"
NORMALIZED_METRICS_RELATIVE_PATH = "metrics/normalized_metrics.csv"
COLLECTION_SUMMARY_RELATIVE_PATH = "metrics/collection-summary.json"

MAX_BEST_ROWS = 4
MAX_LAST_ROWS = 6
MAX_SEED_AGGREGATES = 12
MAX_SELECTED_FIELDS = 12
MAX_SOURCE_FILES = 20
MAX_COLUMNS = 40
MAX_SOURCE_FIELDS = 40
MAX_UNITS = 40
MAX_STRING_CHARS = 160

HIGHER_IS_BETTER = (
    "val_accuracy",
    "test_accuracy",
    "accuracy",
    "acc",
    "macro_f1",
    "f1_score",
    "f1",
    "precision",
    "recall",
    "auc",
    "score",
    "throughput",
    "throughput_rps",
)
LOWER_IS_BETTER = (
    "val_loss",
    "test_loss",
    "train_loss",
    "loss",
    "error_rate",
    "runtime_ms",
    "latency_ms",
    "duration_ms",
    "time_ms",
    "memory_mb",
    "errors",
)
PRIMARY_GROUP_FIELDS = ("method", "model", "algorithm", "variant", "service", "config_id")
SEED_FIELDS = ("seed", "trial", "run_id")
CHECKPOINT_FIELDS = ("epoch", "step", "iter", "iteration", "checkpoint", "ckpt", "timestamp")
CONTEXT_GROUP_FIELDS = ("input_size", "dataset", "dataset_slice", "split", "benchmark", "case")
IDENTITY_FIELDS = (
    "source_file",
    "method",
    "model",
    "algorithm",
    "variant",
    "service",
    "config_id",
    "seed",
    "trial",
    "run_id",
    "input_size",
    "dataset",
    "split",
    "epoch",
    "step",
    "iter",
    "iteration",
    "timestamp",
)
SELECTED_FIELD_PRIORITY = (
    *IDENTITY_FIELDS,
    "checkpoint",
    "ckpt",
    "status",
    "anomaly_code",
    "artifact_present",
)


def build_scenario_summary(
    *,
    record: TaskRecord,
    rows: list[dict[str, object]],
    collection_summary: dict[str, Any],
    units: dict[str, str] | None = None,
    configured_groups: dict[str, str] | None = None,
) -> dict[str, Any]:
    fields = _fieldnames(rows)
    groups = _infer_groups(fields, configured_groups or {})
    primary_metric = _primary_metric(rows, units or {})
    scenario_type = _scenario_type(fields, groups)
    best_rows = _best_rows(rows, primary_metric)
    last_rows = _last_rows(rows, groups, primary_metric)
    seed_aggregates = _seed_aggregates(rows, groups, primary_metric)
    warnings = _warnings(primary_metric, seed_aggregates)

    return {
        "schema_version": SCENARIO_SUMMARY_SCHEMA_VERSION,
        "task_id": record.task_id,
        "generated_at": _now_iso(),
        "scenario_type": scenario_type,
        "primary_metric": primary_metric,
        "groups": groups,
        "units": _bounded_mapping(units or {}, MAX_UNITS),
        "omitted_unit_count": max(0, len(units or {}) - MAX_UNITS),
        "best_rows": best_rows,
        "last_rows": last_rows,
        "seed_aggregates": seed_aggregates,
        "evidence": _evidence(collection_summary, fields, len(rows)),
        "omitted": {
            "full_stdout": "omitted_by_default",
            "full_stderr": "omitted_by_default",
            "full_metric_rows": "omitted_by_default",
            "report_body": "omitted_by_default",
            "ppt_contents": "omitted_by_default",
            "worker_prompt_response": "omitted_by_default",
            "artifact_bytes": "omitted_by_default",
        },
        "warnings": warnings,
    }


def _infer_groups(fields: list[str], configured_groups: dict[str, str]) -> dict[str, Any]:
    field_set = set(fields)
    configured_primary = configured_groups.get("primary")
    configured_secondary = configured_groups.get("secondary")
    primary = configured_primary if configured_primary in field_set else _first_present(field_set, PRIMARY_GROUP_FIELDS)
    seed = _first_present(field_set, SEED_FIELDS)
    secondary = configured_secondary if configured_secondary in field_set else seed
    context = [field for field in CONTEXT_GROUP_FIELDS if field in field_set]
    inferred = [field for field in [primary, secondary, *context] if field]
    return {
        "configured": dict(configured_groups),
        "primary": primary,
        "secondary": secondary,
        "seed": seed,
        "context": context,
        "inferred": _dedupe(inferred),
    }


def _scenario_type(fields: list[str], groups: dict[str, Any]) -> str:
    field_set = set(fields)
    has_checkpoint = any(field in field_set for field in CHECKPOINT_FIELDS)
    if groups.get("primary") and (groups.get("seed") or groups.get("context") or not has_checkpoint):
        return "algorithm-benchmark"
    return "training-run"


def _primary_metric(rows: list[dict[str, object]], units: dict[str, str]) -> dict[str, Any]:
    candidates = _candidate_metrics(rows)
    if not candidates:
        return {
            "name": None,
            "direction": None,
            "unit": None,
            "selection_reason": "no priority numeric metric detected",
        }
    name, direction, reason = candidates[0]
    return {
        "name": name,
        "direction": direction,
        "unit": _bounded_scalar(units.get(name)),
        "selection_reason": reason,
    }


def _best_rows(rows: list[dict[str, object]], primary_metric: dict[str, Any]) -> list[dict[str, Any]]:
    ordered_metrics = _candidate_metrics(rows)
    primary_name = primary_metric.get("name")
    if primary_name:
        ordered_metrics = sorted(ordered_metrics, key=lambda item: 0 if item[0] == primary_name else 1)
    best: list[dict[str, Any]] = []
    seen_metrics: set[str] = set()
    for metric, direction, reason in ordered_metrics:
        if metric in seen_metrics:
            continue
        seen_metrics.add(metric)
        selected = _best_row_for_metric(rows, metric, direction)
        if selected is None:
            continue
        row_number, row, value = selected
        selected_fields = _selected_fields(row, metric)
        best.append(
            {
                "metric": metric,
                "direction": direction,
                "selection_reason": reason,
                "value": _json_number(value),
                "row_number": row_number,
                "selected_fields": selected_fields,
                "omitted_field_count": max(0, len(row) - len(selected_fields)),
                "evidence": _row_evidence(row_number),
            }
        )
        if len(best) >= MAX_BEST_ROWS:
            break
    return best


def _last_rows(
    rows: list[dict[str, object]],
    groups: dict[str, Any],
    primary_metric: dict[str, Any],
) -> list[dict[str, Any]]:
    if not rows:
        return []
    group_fields = [field for field in [groups.get("primary"), *groups.get("context", [])] if isinstance(field, str)]
    checkpoint = _checkpoint_field(_fieldnames(rows))
    grouped: dict[tuple[str, ...], tuple[int, dict[str, object]]] = {}
    for index, row in enumerate(rows, start=1):
        key = tuple(_string_value(row.get(field)) for field in group_fields) if group_fields else ("__all__",)
        current = grouped.get(key)
        if current is None or _is_later_checkpoint(row, current[1], checkpoint, index, current[0]):
            grouped[key] = (index, row)

    items: list[dict[str, Any]] = []
    metric = primary_metric.get("name") if isinstance(primary_metric.get("name"), str) else ""
    for key, (row_number, row) in sorted(grouped.items(), key=lambda item: item[1][0]):
        group_values = {
            field: _bounded_scalar(row.get(field))
            for field in group_fields
            if not _is_empty_value(row.get(field))
        }
        items.append(
            {
                "group": group_values,
                "row_number": row_number,
                "checkpoint_field": checkpoint,
                "selected_fields": _selected_fields(row, metric),
                "evidence": _row_evidence(row_number),
            }
        )
        if len(items) >= MAX_LAST_ROWS:
            break
    return items


def _seed_aggregates(
    rows: list[dict[str, object]],
    groups: dict[str, Any],
    primary_metric: dict[str, Any],
) -> dict[str, Any]:
    metric = primary_metric.get("name")
    direction = primary_metric.get("direction")
    seed_field = groups.get("seed")
    primary_group = groups.get("primary")
    if not isinstance(metric, str) or not isinstance(seed_field, str) or not isinstance(primary_group, str):
        return {
            "present": False,
            "reason": "seed aggregates require a primary group, seed field, and primary metric",
            "items": [],
        }

    context_fields = [field for field in groups.get("context", []) if isinstance(field, str)]
    group_fields = [primary_group, *context_fields]
    checkpoint = _checkpoint_field(_fieldnames(rows))

    latest_by_seed: dict[tuple[str, ...], tuple[int, dict[str, object]]] = {}
    for index, row in enumerate(rows, start=1):
        value = _parse_number(row.get(metric))
        if value is None or _is_empty_value(row.get(seed_field)):
            continue
        key = tuple(_string_value(row.get(field)) for field in [*group_fields, seed_field])
        current = latest_by_seed.get(key)
        if current is None or _is_later_checkpoint(row, current[1], checkpoint, index, current[0]):
            latest_by_seed[key] = (index, row)

    aggregate_rows: dict[tuple[str, ...], list[tuple[int, dict[str, object], float]]] = {}
    for key, (row_number, row) in latest_by_seed.items():
        group_key = key[: len(group_fields)]
        value = _parse_number(row.get(metric))
        if value is None:
            continue
        aggregate_rows.setdefault(group_key, []).append((row_number, row, value))

    items: list[dict[str, Any]] = []
    for group_key, grouped_rows in sorted(aggregate_rows.items(), key=lambda item: item[0]):
        values = [value for _row_number, _row, value in grouped_rows]
        row_numbers = [row_number for row_number, _row, _value in grouped_rows]
        sample_row = grouped_rows[0][1]
        group = {
            field: _bounded_scalar(sample_row.get(field))
            for field in group_fields
            if not _is_empty_value(sample_row.get(field))
        }
        items.append(
            {
                "group": group,
                "metric": metric,
                "direction": direction,
                "aggregation_scope": "last_row_per_group_seed",
                "row_count": len(values),
                "seed_count": len({_string_value(row.get(seed_field)) for _row_number, row, _value in grouped_rows}),
                "mean": _json_number(sum(values) / len(values)),
                "min": _json_number(min(values)),
                "max": _json_number(max(values)),
                "evidence": {
                    "artifact_id": "metrics_normalized_csv",
                    "path": NORMALIZED_METRICS_RELATIVE_PATH,
                    "row_numbers": row_numbers[:MAX_LAST_ROWS],
                    "body": "omitted",
                },
            }
        )

    ordered = sorted(
        items,
        key=lambda item: (
            item["mean"] if direction == "min" else -float(item["mean"]),
            str(item["group"]),
        ),
    )
    return {
        "present": bool(ordered),
        "metric": metric,
        "direction": direction,
        "group_by": group_fields,
        "seed_field": seed_field,
        "aggregation_scope": "last_row_per_group_seed",
        "items": ordered[:MAX_SEED_AGGREGATES],
        "omitted_group_count": max(0, len(ordered) - MAX_SEED_AGGREGATES),
        "claim_limit": "descriptive aggregate only; no statistical significance is inferred",
    }


def _candidate_metrics(rows: list[dict[str, object]]) -> list[tuple[str, str, str]]:
    fields = _fieldnames(rows)
    numeric_fields = {field for field in fields if _has_numeric_value(rows, field)}
    candidates: list[tuple[str, str, str]] = []
    for metric in HIGHER_IS_BETTER:
        for field in fields:
            if field in numeric_fields and _normalized(field) == metric:
                _append_metric(candidates, field, "max", "higher_is_better_name_hint")
    for metric in LOWER_IS_BETTER:
        for field in fields:
            if field in numeric_fields and _normalized(field) == metric:
                _append_metric(candidates, field, "min", "lower_is_better_name_hint")
    for field in fields:
        if field not in numeric_fields:
            continue
        direction = _metric_direction(field)
        if direction:
            reason = "higher_is_better_substring_hint" if direction == "max" else "lower_is_better_substring_hint"
            _append_metric(candidates, field, direction, reason)
    return candidates


def _append_metric(candidates: list[tuple[str, str, str]], field: str, direction: str, reason: str) -> None:
    if not any(existing == field for existing, _direction, _reason in candidates):
        candidates.append((field, direction, reason))


def _metric_direction(field: str) -> str | None:
    normalized = _normalized(field)
    if normalized in HIGHER_IS_BETTER:
        return "max"
    if normalized in LOWER_IS_BETTER:
        return "min"
    if any(hint in normalized for hint in HIGHER_IS_BETTER):
        return "max"
    if any(hint in normalized for hint in LOWER_IS_BETTER):
        return "min"
    return None


def _best_row_for_metric(rows: list[dict[str, object]], metric: str, direction: str) -> tuple[int, dict[str, object], float] | None:
    best: tuple[int, dict[str, object], float] | None = None
    for index, row in enumerate(rows, start=1):
        value = _parse_number(row.get(metric))
        if value is None:
            continue
        if best is None:
            best = (index, row, value)
            continue
        best_value = best[2]
        if direction == "max" and value > best_value:
            best = (index, row, value)
        elif direction == "min" and value < best_value:
            best = (index, row, value)
    return best


def _evidence(collection_summary: dict[str, Any], fields: list[str], row_count: int) -> dict[str, Any]:
    processed_files = []
    for item in collection_summary.get("processed_files") or []:
        if not isinstance(item, dict):
            continue
        processed_files.append(
            {
                "source_file": _bounded_scalar(item.get("source_file")),
                "file_type": _bounded_scalar(item.get("file_type")),
                "row_count": item.get("row_count"),
                "detected_fields": _bounded_list(item.get("detected_fields") or [], MAX_SOURCE_FIELDS),
                "omitted_detected_field_count": _omitted_count(item.get("detected_fields") or [], MAX_SOURCE_FIELDS),
                "mapped_fields": _bounded_list(item.get("mapped_fields") or [], MAX_SOURCE_FIELDS),
                "omitted_mapped_field_count": _omitted_count(item.get("mapped_fields") or [], MAX_SOURCE_FIELDS),
            }
        )
        if len(processed_files) >= MAX_SOURCE_FILES:
            break
    return {
        "metrics": {
            "artifact_id": "metrics_normalized_csv",
            "path": NORMALIZED_METRICS_RELATIVE_PATH,
            "row_count": row_count,
            "columns": _bounded_list(fields, MAX_COLUMNS),
            "omitted_column_count": max(0, len(fields) - MAX_COLUMNS),
            "body": "omitted",
        },
        "collection_summary": {
            "artifact_id": "metrics_collection_summary",
            "path": COLLECTION_SUMMARY_RELATIVE_PATH,
            "candidate_count": collection_summary.get("candidate_count"),
            "processed_file_count": len(collection_summary.get("processed_files") or []),
        },
        "source_files": processed_files,
        "omitted_source_file_count": max(0, len(collection_summary.get("processed_files") or []) - MAX_SOURCE_FILES),
    }


def _warnings(primary_metric: dict[str, Any], seed_aggregates: dict[str, Any]) -> list[str]:
    warnings = [
        "scenario summary is descriptive and deterministic; it does not infer statistical significance or scientific conclusions",
    ]
    if not primary_metric.get("name"):
        warnings.append("primary metric was not detected from priority metric name hints")
    if not seed_aggregates.get("present"):
        warnings.append(str(seed_aggregates.get("reason") or "seed aggregates are unavailable"))
    return warnings


def _fieldnames(rows: list[dict[str, object]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    return fields


def _checkpoint_field(fields: list[str]) -> str | None:
    field_set = set(fields)
    for field in CHECKPOINT_FIELDS:
        if field in field_set:
            return field
    return None


def _is_later_checkpoint(
    candidate: dict[str, object],
    current: dict[str, object],
    checkpoint: str | None,
    candidate_index: int,
    current_index: int,
) -> bool:
    if not checkpoint:
        return candidate_index > current_index
    candidate_value = _parse_number(candidate.get(checkpoint))
    current_value = _parse_number(current.get(checkpoint))
    if candidate_value is None or current_value is None:
        return candidate_index > current_index
    if candidate_value == current_value:
        return candidate_index > current_index
    return candidate_value > current_value


def _selected_fields(row: dict[str, object], metric: str) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for field in [*SELECTED_FIELD_PRIORITY, metric, *HIGHER_IS_BETTER, *LOWER_IS_BETTER]:
        if field in row and field not in selected and not _is_empty_value(row.get(field)):
            selected[field] = _bounded_scalar(row[field])
        if len(selected) >= MAX_SELECTED_FIELDS:
            return selected
    return selected


def _row_evidence(row_number: int) -> dict[str, Any]:
    return {
        "artifact_id": "metrics_normalized_csv",
        "path": NORMALIZED_METRICS_RELATIVE_PATH,
        "row_number": row_number,
        "body": "omitted",
    }


def _parse_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        parsed = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _has_numeric_value(rows: list[dict[str, object]], field: str) -> bool:
    return any(_parse_number(row.get(field)) is not None for row in rows)


def _json_number(value: float) -> int | float:
    if value.is_integer():
        return int(value)
    return float(round(value, 12))


def _bounded_scalar(value: object) -> object:
    if isinstance(value, bool | int | float) or value is None:
        return value
    text = str(value)
    if len(text) <= MAX_STRING_CHARS:
        return text
    return text[: MAX_STRING_CHARS - 3].rstrip() + "..."


def _bounded_list(values: object, limit: int) -> list[object]:
    if not isinstance(values, list):
        return []
    bounded: list[object] = []
    for value in values[:limit]:
        bounded.append(_bounded_scalar(value))
    return bounded


def _bounded_mapping(values: dict[str, str], limit: int) -> dict[str, object]:
    return {
        str(key)[:MAX_STRING_CHARS]: _bounded_scalar(value)
        for key, value in list(values.items())[:limit]
    }


def _omitted_count(values: object, limit: int) -> int:
    return max(0, len(values) - limit) if isinstance(values, list) else 0


def _is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _first_present(field_set: set[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in field_set:
            return candidate
    return None


def _dedupe(values: list[str | None]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _string_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _normalized(value: str) -> str:
    return value.strip().lower()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
