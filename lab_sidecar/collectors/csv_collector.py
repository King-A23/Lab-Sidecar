from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from lab_sidecar.collectors.fields import detect_metric_fields


@dataclass
class CsvCollectionResult:
    rows: list[dict[str, object]] = field(default_factory=list)
    detected_fields: list[str] = field(default_factory=list)


def collect_csv(path: Path) -> CsvCollectionResult:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return CsvCollectionResult()

        field_names = [field for field in reader.fieldnames if field is not None]
        detected = detect_metric_fields(field_names)
        if not detected:
            return CsvCollectionResult(detected_fields=[])

        rows: list[dict[str, object]] = []
        for row in reader:
            normalized = {key: value for key, value in row.items() if key is not None}
            normalized["source_file"] = path.as_posix()
            rows.append(normalized)
        return CsvCollectionResult(rows=rows, detected_fields=detected)

