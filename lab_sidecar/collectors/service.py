from __future__ import annotations

import csv
import json
import fnmatch
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.config import (
    FieldMapping,
    MetricsCollectionConfig,
    MetricsConfigError,
    load_metrics_config,
)
from lab_sidecar.collectors.csv_collector import collect_csv, read_csv_rows
from lab_sidecar.collectors.json_collector import collect_json, read_json_rows
from lab_sidecar.collectors.scan import SUPPORTED_SUFFIXES, CandidateFile, scan_metric_candidates
from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord, TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path, to_manifest_path
from lab_sidecar.core.provenance import file_provenance
from lab_sidecar.core.traceability import refresh_traceability
from lab_sidecar.storage.sqlite_index import upsert_task


class NoMetricsFoundError(RuntimeError):
    def __init__(self, message: str, summary: dict[str, Any]):
        super().__init__(message)
        self.summary = summary


class MetricsConfigLoadError(RuntimeError):
    pass


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
    source_provenance: dict[str, Any] = field(default_factory=dict)
    detected_fields: list[str] = field(default_factory=list)
    mapped_fields: list[str] = field(default_factory=list)
    matched_source_fields: dict[str, list[str]] = field(default_factory=dict)


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

        config = self._load_config(config_path) if config_path else None
        auto_candidates = scan_metric_candidates(self.root, record)
        warnings: list[str] = []
        diagnostics: list[dict[str, str]] = []
        if config:
            diagnostics.extend(config.diagnostics)
            warnings.extend(item["message"] for item in config.diagnostics if item.get("message"))
        skipped_files: list[dict[str, str]] = []
        candidates = self._select_candidates(
            record,
            auto_candidates,
            config,
            warnings,
            skipped_files,
            diagnostics,
        )
        rows: list[dict[str, object]] = []
        collected_files: list[_CollectedFile] = []

        for candidate in candidates:
            try:
                (
                    file_rows,
                    detected_fields,
                    mapped_fields,
                    matched_source_fields,
                    file_warnings,
                ) = self._collect_candidate(candidate, config)
            except _CandidateSkipped as exc:
                source_file = to_manifest_path(candidate.path, self.root)
                warnings.append(exc.message)
                skipped_files.append({"source_file": source_file, "reason": exc.reason})
                diagnostics.append({"source_file": source_file, "reason": exc.reason, "message": exc.message})
                continue
            except Exception as exc:
                source_file = to_manifest_path(candidate.path, self.root)
                message = f"Failed to parse {source_file}: {exc}"
                warnings.append(message)
                skipped_files.append({"source_file": source_file, "reason": "parse_failed"})
                diagnostics.append({"source_file": source_file, "reason": "parse_failed", "message": message})
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
                    source_provenance=file_provenance(candidate.path),
                    detected_fields=detected_fields,
                    mapped_fields=mapped_fields,
                    matched_source_fields=matched_source_fields,
                )
            )

        detected_fields = _merge_detected_fields(collected_files)
        unit_diagnostics = _unit_diagnostics(config, collected_files) if config else []
        diagnostics.extend(unit_diagnostics)
        existing_warnings = set(warnings)
        for diagnostic in unit_diagnostics:
            message = diagnostic.get("message")
            if message and message not in existing_warnings:
                warnings.append(message)
                existing_warnings.add(message)
        summary = self._build_summary(
            record=record,
            candidates=candidates,
            collected_files=collected_files,
            skipped_files=skipped_files,
            warnings=warnings,
            diagnostics=diagnostics,
            unit_diagnostics=unit_diagnostics,
            detected_fields=detected_fields,
            row_count=len(rows),
            config_path=config_path,
            config=config,
            outputs=[csv_path, json_path],
        )
        _write_json(summary_path, summary)
        self._upsert_summary_artifact(record, summary_path)

        if not rows:
            record.updated_at = _now_iso()
            record = refresh_traceability(self.root, record)
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
        record = refresh_traceability(self.root, record)
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

    def _load_config(self, config_path: Path) -> MetricsCollectionConfig:
        try:
            return load_metrics_config(config_path)
        except MetricsConfigError as exc:
            raise MetricsConfigLoadError(str(exc)) from exc

    def _select_candidates(
        self,
        record: TaskRecord,
        auto_candidates: list[CandidateFile],
        config: MetricsCollectionConfig | None,
        warnings: list[str],
        skipped_files: list[dict[str, str]],
        diagnostics: list[dict[str, str]],
    ) -> list[CandidateFile]:
        if config is None or not config.has_explicit_sources:
            return auto_candidates

        selected, source_warnings, source_skips = _configured_candidates(
            root=self.root,
            record=record,
            patterns=config.sources,
            exclude_patterns=config.exclude_sources,
        )
        warnings.extend(source_warnings)
        skipped_files.extend(source_skips)
        diagnostics.extend(_diagnostics_from_skipped_files(source_skips))
        return selected

    def _collect_candidate(
        self,
        candidate: CandidateFile,
        config: MetricsCollectionConfig | None,
    ) -> tuple[list[dict[str, object]], list[str], list[str], dict[str, list[str]], list[str]]:
        if config is not None and config.has_field_mappings:
            return self._collect_explicit_candidate(candidate, config)

        suffix = candidate.path.suffix.lower()
        if suffix == ".csv":
            result = collect_csv(candidate.path)
            return result.rows, result.detected_fields, [], {}, []
        if suffix == ".json":
            result = collect_json(candidate.path)
            return result.rows, result.detected_fields, [], {}, result.warnings
        return [], [], [], {}, []

    def _collect_explicit_candidate(
        self,
        candidate: CandidateFile,
        config: MetricsCollectionConfig,
    ) -> tuple[list[dict[str, object]], list[str], list[str], dict[str, list[str]], list[str]]:
        raw_rows, warnings = _read_candidate_rows(candidate)
        if not raw_rows:
            return [], [], [], {}, warnings

        source_file = to_manifest_path(candidate.path, self.root)
        mapped_rows: list[dict[str, object]] = []
        missing_by_target: dict[str, list[str]] = {}
        matched_source_fields: dict[str, list[str]] = {}
        for row in raw_rows:
            mapped: dict[str, object] = {}
            row_complete = True
            for mapping in config.field_mappings:
                found, value, _source_field = _mapped_value(row, mapping)
                if not found:
                    row_complete = False
                    if mapping.target not in missing_by_target:
                        missing_by_target[mapping.target] = list(mapping.sources)
                    continue
                mapped[mapping.target] = value
                _append_unique(matched_source_fields.setdefault(mapping.target, []), _source_field)
            if row_complete:
                mapped["source_file"] = source_file
                mapped_rows.append(mapped)

        if missing_by_target:
            details = [
                f"{target} from {', '.join(sources)}"
                for target, sources in sorted(missing_by_target.items())
            ]
            raise _CandidateSkipped(
                reason="missing_configured_field",
                message=f"Configured field(s) missing in {source_file}: {'; '.join(details)}",
            )

        detected_fields = [mapping.target for mapping in config.field_mappings]
        return mapped_rows, detected_fields, detected_fields, matched_source_fields, warnings

    def _build_summary(
        self,
        record: TaskRecord,
        candidates: list[CandidateFile],
        collected_files: list[_CollectedFile],
        skipped_files: list[dict[str, str]],
        warnings: list[str],
        diagnostics: list[dict[str, str]],
        unit_diagnostics: list[dict[str, str]],
        detected_fields: list[str],
        row_count: int,
        config_path: Path | None,
        config: MetricsCollectionConfig | None,
        outputs: list[Path],
    ) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "task_id": record.task_id,
            "task_status": record.status.value,
            "collected_at": _now_iso(),
            "config_path": to_manifest_path(config_path, self.root) if config_path else None,
            "config": config.to_summary() if config else None,
            "units": dict(config.units) if config else {},
            "groups": dict(config.groups) if config else {},
            "candidate_count": len(candidates),
            "candidates": [
                {
                    "source_file": to_manifest_path(candidate.path, self.root),
                    "origin": candidate.origin,
                    "suffix": candidate.path.suffix.lower(),
                    "source_provenance": _safe_file_provenance(candidate.path),
                }
                for candidate in candidates
            ],
            "processed_files": [
                {
                    "source_file": item.source_file,
                    "file_type": item.file_type,
                    "row_count": item.row_count,
                    "source_provenance": item.source_provenance,
                    "detected_fields": item.detected_fields,
                    "mapped_fields": item.mapped_fields,
                    "matched_source_fields": item.matched_source_fields,
                }
                for item in collected_files
            ],
            "skipped_files": skipped_files,
            "warnings": warnings,
            "diagnostics": diagnostics,
            "unit_diagnostics": unit_diagnostics,
            "matched_source_fields": _merge_matched_source_fields(collected_files),
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


def _safe_file_provenance(path: Path) -> dict[str, Any]:
    try:
        return file_provenance(path)
    except OSError:
        return {}


class _CandidateSkipped(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _configured_candidates(
    root: Path,
    record: TaskRecord,
    patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...] = (),
) -> tuple[list[CandidateFile], list[str], list[dict[str, str]]]:
    selected: dict[str, CandidateFile] = {}
    warnings: list[str] = []
    skipped_files: list[dict[str, str]] = []
    allowed_files = _allowed_source_files(root, record)

    for pattern in patterns:
        if _pattern_outside_workspace(root, pattern):
            message = f"Configured source is outside the workspace: {pattern}"
            warnings.append(message)
            skipped_files.append({"source_file": pattern, "reason": "outside_workspace", "message": message})
            continue
        matches = _resolve_source_pattern(root, pattern)
        if not matches:
            message = f"Configured source matched no files: {pattern}"
            warnings.append(message)
            skipped_files.append({"source_file": pattern, "reason": "configured_source_missing", "message": message})
            continue

        for path in matches:
            source_file = to_manifest_path(path, root)
            if _matches_any_source_pattern(root, path, exclude_patterns):
                skipped_files.append({"source_file": source_file, "reason": "configured_source_excluded"})
                continue
            if not _is_within(path, root):
                message = f"Configured source is outside the workspace: {source_file}"
                warnings.append(message)
                skipped_files.append({"source_file": source_file, "reason": "outside_workspace", "message": message})
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                message = f"Configured source is not a supported CSV/JSON file: {source_file}"
                warnings.append(message)
                skipped_files.append(
                    {"source_file": source_file, "reason": "unsupported_configured_source", "message": message}
                )
                continue
            if allowed_files is not None and path.resolve().as_posix() not in allowed_files:
                message = f"Configured source is not part of this task source refs: {source_file}"
                warnings.append(message)
                skipped_files.append({"source_file": source_file, "reason": "not_in_source_refs", "message": message})
                continue
            selected[path.resolve().as_posix()] = CandidateFile(path=path.resolve(), origin="config")

    return (
        sorted(selected.values(), key=lambda candidate: candidate.path.as_posix().lower()),
        warnings,
        skipped_files,
    )


def _allowed_source_files(root: Path, record: TaskRecord) -> set[str] | None:
    if record.mode != "ingest":
        return None

    task_path = resolve_workspace_path(record.paths.task_dir, root)
    refs_path = task_path / "raw" / "source_refs.json"
    if not refs_path.exists():
        return set()

    try:
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    files: list[str] = []
    if refs.get("source_type") == "file" and isinstance(refs.get("source_path"), str):
        files.append(refs["source_path"])
    elif refs.get("source_type") == "directory":
        candidate_refs = refs.get("candidate_file_refs")
        if isinstance(candidate_refs, list):
            for item in candidate_refs:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    files.append(item["path"])
        candidate_files = refs.get("candidate_files")
        if isinstance(candidate_files, list):
            files.extend(item for item in candidate_files if isinstance(item, str))
        else:
            children = refs.get("children")
            if isinstance(children, list):
                for child in children:
                    if (
                        isinstance(child, dict)
                        and child.get("type") == "file"
                        and child.get("is_candidate") is True
                        and isinstance(child.get("path"), str)
                    ):
                        files.append(child["path"])
    return {resolve_workspace_path(path_text, root).resolve().as_posix() for path_text in files}


def _resolve_source_pattern(root: Path, pattern: str) -> list[Path]:
    normalized_pattern = pattern.replace("\\", "/")
    path = Path(pattern)
    if path.is_absolute():
        base_pattern = path.as_posix()
        search_root = root.resolve()
    else:
        base_pattern = (root / path).as_posix()
        search_root = root.resolve()

    if not _has_glob_magic(pattern):
        candidate = Path(base_pattern).resolve()
        return [candidate] if candidate.exists() and candidate.is_file() else []

    matches: list[Path] = []
    for candidate in search_root.rglob("*"):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        relative = candidate.relative_to(search_root).as_posix()
        if fnmatch.fnmatch(relative, normalized_pattern) or fnmatch.fnmatch(resolved.as_posix(), base_pattern):
            matches.append(resolved)
    return matches


def _has_glob_magic(value: str) -> bool:
    return any(char in value for char in "*?[")


def _pattern_outside_workspace(root: Path, pattern: str) -> bool:
    prefix = _static_pattern_prefix(root, pattern)
    return not _is_within(prefix, root)


def _static_pattern_prefix(root: Path, pattern: str) -> Path:
    path = Path(pattern)
    if not _has_glob_magic(pattern):
        return path.resolve() if path.is_absolute() else (root / path).resolve()
    parts: list[str] = []
    for part in path.parts:
        if _has_glob_magic(part):
            break
        parts.append(part)
    if not parts:
        return root.resolve()
    prefix = Path(*parts)
    return prefix.resolve() if prefix.is_absolute() else (root / prefix).resolve()


def _matches_any_source_pattern(root: Path, path: Path, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return False
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        relative = resolved.as_posix()
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        pattern_path = Path(pattern)
        if pattern_path.is_absolute():
            base_pattern = pattern_path.as_posix()
            if fnmatch.fnmatch(resolved.as_posix(), base_pattern):
                return True
            continue
        if fnmatch.fnmatch(relative, normalized):
            return True
    return False


def _read_candidate_rows(candidate: CandidateFile) -> tuple[list[dict[str, object]], list[str]]:
    suffix = candidate.path.suffix.lower()
    if suffix == ".csv":
        return read_csv_rows(candidate.path), []
    if suffix == ".json":
        return read_json_rows(candidate.path)
    return [], []


def _mapped_value(row: dict[str, object], mapping: FieldMapping) -> tuple[bool, object | None, str]:
    for source in mapping.sources:
        if source in row:
            return True, row[source], source
    return False, None, mapping.sources[0]


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


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


def _merge_matched_source_fields(collected_files: list[_CollectedFile]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for item in collected_files:
        for target, source_fields in item.matched_source_fields.items():
            target_fields = merged.setdefault(target, [])
            for source_field in source_fields:
                _append_unique(target_fields, source_field)
    return merged


def _diagnostics_from_skipped_files(skipped_files: list[dict[str, str]]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    for item in skipped_files:
        if item.get("message"):
            diagnostics.append(
                {
                    "source_file": item.get("source_file", ""),
                    "reason": item.get("reason", ""),
                    "message": item["message"],
                }
            )
    return diagnostics


def _append_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _unit_diagnostics(
    config: MetricsCollectionConfig,
    collected_files: list[_CollectedFile],
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    matched = _merge_matched_source_fields(collected_files)
    for mapping in config.field_mappings:
        source_fields = matched.get(mapping.target, [])
        source_units = _named_source_units(source_fields)
        unit_values = sorted(set(source_units.values()))
        if len(unit_values) > 1:
            diagnostics.append(
                {
                    "reason": "mixed_source_units",
                    "field": mapping.target,
                    "source_fields": ", ".join(source_fields),
                    "message": (
                        f"Mapped field '{mapping.target}' matched source fields with mixed unit suffixes: "
                        f"{_format_source_units(source_units)}."
                    ),
                }
            )
            continue

        configured_unit = mapping.unit
        if configured_unit and source_units:
            inferred_units = set(source_units.values())
            if len(inferred_units) == 1:
                inferred_unit = next(iter(inferred_units))
                if _canonical_unit(configured_unit) != inferred_unit:
                    diagnostics.append(
                        {
                            "reason": "configured_unit_conflict",
                            "field": mapping.target,
                            "source_fields": ", ".join(source_fields),
                            "message": (
                                f"Configured unit for '{mapping.target}' is '{configured_unit}', "
                                f"but matched source field(s) suggest '{inferred_unit}': "
                                f"{', '.join(source_fields)}."
                            ),
                        }
                    )
    return diagnostics


def _named_source_units(source_fields: list[str]) -> dict[str, str]:
    units: dict[str, str] = {}
    for field_name in source_fields:
        unit = _field_unit_suffix(field_name)
        if unit:
            units[field_name] = unit
    return units


def _field_unit_suffix(field_name: str) -> str | None:
    normalized = field_name.strip().lower()
    suffixes = (
        ("_milliseconds", "ms"),
        ("_millisecond", "ms"),
        ("_ms", "ms"),
        ("_seconds", "s"),
        ("_second", "s"),
        ("_secs", "s"),
        ("_sec", "s"),
        ("_s", "s"),
        ("_mb", "mb"),
        ("_megabytes", "mb"),
        ("_megabyte", "mb"),
        ("_gb", "gb"),
        ("_gigabytes", "gb"),
        ("_gigabyte", "gb"),
    )
    for suffix, unit in suffixes:
        if normalized.endswith(suffix):
            return unit
    return None


def _canonical_unit(unit: str) -> str:
    normalized = unit.strip().lower()
    aliases = {
        "millisecond": "ms",
        "milliseconds": "ms",
        "second": "s",
        "seconds": "s",
        "sec": "s",
        "secs": "s",
        "megabyte": "mb",
        "megabytes": "mb",
        "gigabyte": "gb",
        "gigabytes": "gb",
    }
    return aliases.get(normalized, normalized)


def _format_source_units(source_units: dict[str, str]) -> str:
    return ", ".join(f"{source}={unit}" for source, unit in sorted(source_units.items()))


def _upsert_artifact(record: TaskRecord, artifact: ArtifactRecord) -> None:
    record.artifacts = [item for item in record.artifacts if item.artifact_id != artifact.artifact_id]
    record.artifacts.append(artifact)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
