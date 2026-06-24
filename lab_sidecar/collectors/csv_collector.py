from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from lab_sidecar.collectors.fields import detect_metric_fields


@dataclass
class CsvCollectionResult:
    rows: list[dict[str, object]] = field(default_factory=list)
    detected_fields: list[str] = field(default_factory=list)


def read_csv_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh, strict=True)
        if not reader.fieldnames:
            return []

        return [
            {key: value for key, value in row.items() if key is not None}
            for row in reader
        ]


def collect_csv(path: Path) -> CsvCollectionResult:
    rows = read_csv_rows(path)
    if not rows:
        return CsvCollectionResult()

    field_names = _field_names(rows)
    detected = detect_metric_fields(field_names)
    if not detected:
        return CsvCollectionResult(detected_fields=[])

    for row in rows:
        row["source_file"] = path.as_posix()
    return CsvCollectionResult(rows=rows, detected_fields=detected)


def _field_names(rows: list[dict[str, object]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for field_name in row:
            if field_name not in fields:
                fields.append(field_name)
    return fields
