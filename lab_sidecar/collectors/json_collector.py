from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.fields import detect_metric_fields


@dataclass
class JsonCollectionResult:
    rows: list[dict[str, object]] = field(default_factory=list)
    detected_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def collect_json(path: Path) -> JsonCollectionResult:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows, warnings = _rows_from_json(data)
    if not rows:
        return JsonCollectionResult(warnings=warnings)

    flattened_rows: list[dict[str, object]] = []
    skipped_complex = False
    for row in rows:
        flattened, had_complex = _flatten_object(row)
        skipped_complex = skipped_complex or had_complex
        flattened["source_file"] = path.as_posix()
        flattened_rows.append(flattened)

    field_names = sorted({key for row in flattened_rows for key in row if key != "source_file"})
    detected = detect_metric_fields(field_names)
    if not detected:
        return JsonCollectionResult(warnings=warnings)

    if skipped_complex:
        warnings.append(f"Skipped complex nested values in {path.as_posix()}.")
    return JsonCollectionResult(rows=flattened_rows, detected_fields=detected, warnings=warnings)


def _rows_from_json(data: Any) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if isinstance(data, list):
        rows = [item for item in data if isinstance(item, dict)]
        if len(rows) != len(data):
            warnings.append("Skipped non-object items in JSON list.")
        return rows, warnings

    if not isinstance(data, dict):
        warnings.append("Skipped JSON value because it is not an object or list of objects.")
        return [], warnings

    object_list_key = _find_object_list_key(data)
    if object_list_key:
        context = {
            key: value
            for key, value in data.items()
            if key != object_list_key and _is_scalar(value)
        }
        return [
            {**context, **item}
            for item in data[object_list_key]
            if isinstance(item, dict)
        ], warnings

    return [data], warnings


def _find_object_list_key(data: dict[str, Any]) -> str | None:
    for key, value in data.items():
        if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            return key
    return None


def _flatten_object(data: dict[str, Any]) -> tuple[dict[str, object], bool]:
    flattened: dict[str, object] = {}
    had_complex = False
    for key, value in data.items():
        if _is_scalar(value):
            flattened[key] = value
            continue
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                if _is_scalar(child_value):
                    flattened[f"{key}_{child_key}"] = child_value
                else:
                    had_complex = True
            continue
        had_complex = True
    return flattened, had_complex


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)

