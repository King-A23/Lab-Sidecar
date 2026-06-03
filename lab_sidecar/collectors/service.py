from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.csv_collector import collect_csv
from lab_sidecar.collectors.json_collector import collect_json
from lab_sidecar.collectors.scan import CandidateFile, scan_metric_candidates
from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord, TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path, to_manifest_path
from lab_sidecar.storage.sqlite_index import upsert_task


class NoMetricsFoundError(RuntimeError):
    def __init__(self, message: str, summary: dict[str, Any]):
        super().__init__(message)
        self.summary = summary


@dataclass
class CollectResult:
    record: TaskRecord
    rows: list[dict[str, object]]
    detected_fields: list[str]
    summary: dict[str, Any]
    csv_path: Path
    json_path: Path
    summary_path: Path


@dataclass
class _CollectedFile:
    source_file: str
    file_type: str
    row_count: int
    detected_fields: list[str] = field(default_factory=list)


class MetricsCollectionService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def collect(self, task_id: str, config_path: Path | None = None) -> CollectResult:
        record = load_task(self.root, task_id)
        task_path = resolve_workspace_path(record.paths.task_dir, self.root)
        metrics_dir = task_path / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        csv_path = metrics_dir / "normalized_metrics.csv"
        json_path = metrics_dir / "normalized_metrics.json"
        summary_path = metrics_dir / "collection-summary.json"

        candidates = scan_metric_candidates(self.root, record)
        rows: list[dict[str, object]] = []
        collected_files: list[_CollectedFile] = []
        warnings: list[str] = []
        skipped_files: list[dict[str, str]] = []

        for candidate in candidates:
            try:
                file_rows, detected_fields, file_warnings = self._collect_candidate(candidate)
            except Exception as exc:
                source_file = to_manifest_path(candidate.path, self.root)
                warnings.append(f"Failed to parse {source_file}: {exc}")
                skipped_files.append({"source_file": source_file, "reason": "parse_failed"})
                continue

            source_file = to_manifest_path(candidate.path, self.root)
            warnings.extend(file_warnings)
            if not file_rows:
                skipped_files.append({"source_file": source_file, "reason": "no_detected_metrics"})
                continue

            for row in file_rows:
                row["source_file"] = source_file
            rows.extend(file_rows)
            collected_files.append(
                _CollectedFile(
                    source_file=source_file,
                    file_type=candidate.path.suffix.lower().lstrip("."),
                    row_count=len(file_rows),
                    detected_fields=detected_fields,
                )
            )

        detected_fields = _merge_detected_fields(collected_files)
        summary = self._build_summary(
            record=record,
            candidates=candidates,
            collected_files=collected_files,
            skipped_files=skipped_files,
            warnings=warnings,
            detected_fields=detected_fields,
            row_count=len(rows),
            config_path=config_path,
            outputs=[csv_path, json_path],
        )
        _write_json(summary_path, summary)
        self._upsert_summary_artifact(record, summary_path)

        if not rows:
            record.updated_at = _now_iso()
            write_manifest(manifest_path(self.root, task_id), record)
            upsert_task(self.root, record)
            message = (
                f"no supported metrics files were found for task '{task_id}'"
                if not candidates
                else f"no metrics could be collected for task '{task_id}'"
            )
            raise NoMetricsFoundError(message, summary)

        _write_csv(csv_path, rows)
        _write_json(json_path, rows)

        self._upsert_metrics_artifacts(record, csv_path, json_path, summary_path, collected_files)
        record.updated_at = _now_iso()
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)

        return CollectResult(
            record=record,
            rows=rows,
            detected_fields=detected_fields,
            summary=summary,
            csv_path=csv_path,
            json_path=json_path,
            summary_path=summary_path,
        )

    def _collect_candidate(self, candidate: CandidateFile) -> tuple[list[dict[str, object]], list[str], list[str]]:
        suffix = candidate.path.suffix.lower()
        if suffix == ".csv":
            result = collect_csv(candidate.path)
            return result.rows, result.detected_fields, []
        if suffix == ".json":
            result = collect_json(candidate.path)
            return result.rows, result.detected_fields, result.warnings
        return [], [], []

    def _build_summary(
        self,
        record: TaskRecord,
        candidates: list[CandidateFile],
        collected_files: list[_CollectedFile],
        skipped_files: list[dict[str, str]],
        warnings: list[str],
        detected_fields: list[str],
        row_count: int,
        config_path: Path | None,
        outputs: list[Path],
    ) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "task_status": record.status.value,
            "collected_at": _now_iso(),
            "config_path": to_manifest_path(config_path, self.root) if config_path else None,
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "source_file": to_manifest_path(candidate.path, self.root),
                    "origin": candidate.origin,
                    "suffix": candidate.path.suffix.lower(),
                }
                for candidate in candidates
            ],
            "processed_files": [
                {
                    "source_file": item.source_file,
                    "file_type": item.file_type,
                    "row_count": item.row_count,
                    "detected_fields": item.detected_fields,
                }
                for item in collected_files
            ],
            "skipped_files": skipped_files,
            "warnings": warnings,
            "row_count": row_count,
            "detected_fields": detected_fields,
            "output_files": [to_manifest_path(path, self.root) for path in outputs] if row_count else [],
        }

    def _upsert_summary_artifact(self, record: TaskRecord, summary_path: Path) -> None:
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="metrics_collection_summary",
                type="config",
                path=to_manifest_path(summary_path, self.root),
                description="Metrics collection summary and warnings",
                source_paths=[],
            ),
        )

    def _upsert_metrics_artifacts(
        self,
        record: TaskRecord,
        csv_path: Path,
        json_path: Path,
        summary_path: Path,
        collected_files: list[_CollectedFile],
    ) -> None:
        source_paths = [item.source_file for item in collected_files]
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="metrics_normalized_csv",
                type="table",
                path=to_manifest_path(csv_path, self.root),
                description="Normalized metrics table",
                source_paths=source_paths,
            ),
        )
        _upsert_artifact(
            record,
            ArtifactRecord(
                artifact_id="metrics_normalized_json",
                type="table",
                path=to_manifest_path(json_path, self.root),
                description="Normalized metrics as JSON rows",
                source_paths=source_paths,
            ),
        )
        self._upsert_summary_artifact(record, summary_path)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = _fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fieldnames(rows: list[dict[str, object]]) -> list[str]:
    ordered: list[str] = []
    for row in rows:
        for key in row:
            if key not in ordered:
                ordered.append(key)
    if "source_file" in ordered:
        ordered.remove("source_file")
        return ["source_file", *ordered]
    return ordered


def _merge_detected_fields(collected_files: list[_CollectedFile]) -> list[str]:
    fields: list[str] = []
    for item in collected_files:
        for field_name in item.detected_fields:
            if field_name not in fields:
                fields.append(field_name)
    return fields


def _upsert_artifact(record: TaskRecord, artifact: ArtifactRecord) -> None:
    record.artifacts = [item for item in record.artifacts if item.artifact_id != artifact.artifact_id]
    record.artifacts.append(artifact)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

