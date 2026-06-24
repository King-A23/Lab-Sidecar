from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_sidecar.core.models import TaskRecord, TaskStatus, effective_run_mode
from lab_sidecar.core.paths import resolve_workspace_path, sqlite_path
from lab_sidecar.core.traceability import TRACEABILITY_RELATIVE_PATH, refresh_traceability
from lab_sidecar.core.manifest import manifest_path, write_manifest
from lab_sidecar.storage.sqlite_index import upsert_task


PACKAGE_SCHEMA_VERSION = "1"
COMMAND_PREVIEW_CHARS = 160
FAILURE_SUMMARY_CHARS = 1200
ARTIFACT_INDEX_DIGEST_PATH = Path("artifact-index.sha256")
ARTIFACT_INDEX_PATH = Path("artifact-index.json")


class PackageExportError(RuntimeError):
    """Raised when a package cannot be created after inputs are validated."""


class PackageOutputError(PackageExportError):
    """Raised when the requested output path is not usable as a package directory."""


class PackageVerifyError(RuntimeError):
    """Raised when a package directory cannot be inspected."""


@dataclass(frozen=True)
class PackageExportResult:
    path: Path
    package_type: str
    included_count: int
    omitted_count: int
    unavailable_count: int
    digest_path: Path


@dataclass(frozen=True)
class PackageVerifyResult:
    path: Path
    checked_count: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class PackageFileSpec:
    relative_path: Path
    category: str
    description: str
    required: bool = False


PACKAGE_FILE_SPECS = [
    PackageFileSpec(Path("manifest.json"), "manifest", "Task manifest.", required=True),
    PackageFileSpec(Path("reproduce/command.txt"), "reproduce", "Original command."),
    PackageFileSpec(Path("reproduce/run.json"), "reproduce", "Structured run mode and argv metadata."),
    PackageFileSpec(Path("reproduce/env.json"), "reproduce", "Environment metadata."),
    PackageFileSpec(Path("reproduce/git.json"), "reproduce", "Git metadata."),
    PackageFileSpec(Path("reproduce/dependencies.json"), "reproduce", "Dependency metadata."),
    PackageFileSpec(Path("metrics/normalized_metrics.csv"), "metrics", "Normalized metrics table."),
    PackageFileSpec(Path("metrics/normalized_metrics.json"), "metrics", "Normalized metrics JSON."),
    PackageFileSpec(Path("metrics/collection-summary.json"), "metrics", "Metrics collection summary."),
    PackageFileSpec(Path("metrics/scenario-summary.json"), "metrics", "Bounded experiment scenario summary."),
    PackageFileSpec(Path("figures/figure-spec.yaml"), "figures", "Figure rendering specification."),
    PackageFileSpec(Path("figures/figure-summary.json"), "figures", "Figure generation summary."),
    PackageFileSpec(Path("reports/report-fragment.md"), "reports", "Generated report fragment."),
    PackageFileSpec(Path("reports/report-summary.json"), "reports", "Report generation summary."),
    PackageFileSpec(Path("slides/presentation-draft.pptx"), "slides", "Generated editable slide deck."),
    PackageFileSpec(Path("slides/slides-summary.json"), "slides", "Slide generation summary."),
    PackageFileSpec(TRACEABILITY_RELATIVE_PATH, "provenance", "Task-local traceability evidence."),
]


def export_task_package(root: Path, record: TaskRecord, output_dir: Path) -> PackageExportResult:
    root = root.resolve()
    task_path = resolve_workspace_path(record.paths.task_dir, root)
    output_path = _prepare_output_dir(root, output_dir)

    record = refresh_traceability(root, record)
    write_manifest(manifest_path(root, record.task_id), record)
    upsert_task(root, record)

    included: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []

    try:
        seen: set[Path] = set()
        for spec in _package_specs(task_path):
            if spec.relative_path in seen:
                continue
            seen.add(spec.relative_path)
            source = task_path / spec.relative_path
            if source.is_file():
                included.append(_copy_file(source, output_path / spec.relative_path, spec))
                continue
            if spec.required:
                raise PackageExportError(f"required package file is missing: {spec.relative_path.as_posix()}")
            unavailable.append(
                {
                    "path": spec.relative_path.as_posix(),
                    "category": spec.category,
                    "reason": "not generated or not available for this task",
                }
            )

        omitted = _omitted_entries(root, task_path, record)
        package_type = _package_type(record)
        created_at = _now_iso()
        summary = _package_summary(
            record=record,
            package_name=output_path.name,
            package_type=package_type,
            created_at=created_at,
            included=included,
            omitted=omitted,
            unavailable=unavailable,
        )
        artifact_index = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "created_at": created_at,
            "task_id": record.task_id,
            "package_type": package_type,
            "included": included,
            "omitted": omitted,
            "unavailable": unavailable,
        }

        _write_json(output_path / "package-summary.json", summary)
        (output_path / "redaction-notes.md").write_text(
            _redaction_notes(record, omitted, unavailable),
            encoding="utf-8",
        )
        (output_path / "README.md").write_text(
            _readme(record, summary, included, omitted, unavailable),
            encoding="utf-8",
        )
        artifact_index["package_metadata"] = _package_metadata_entries(output_path)
        _write_json(output_path / ARTIFACT_INDEX_PATH, artifact_index)
        _write_index_digest(output_path)
    except OSError as exc:
        raise PackageExportError(str(exc)) from exc

    return PackageExportResult(
        path=output_path,
        package_type=package_type,
        included_count=len(included),
        omitted_count=len(omitted),
        unavailable_count=len(unavailable),
        digest_path=output_path / ARTIFACT_INDEX_DIGEST_PATH,
    )


def verify_task_package(package_dir: Path) -> PackageVerifyResult:
    package_path = package_dir.resolve()
    if not package_path.is_dir():
        raise PackageVerifyError(f"{package_path} is not a package directory")

    errors: list[str] = []
    checked_paths: set[str] = set()
    index_path = package_path / ARTIFACT_INDEX_PATH
    digest_path = package_path / ARTIFACT_INDEX_DIGEST_PATH
    expected_index_digest = _read_index_digest(digest_path, errors)
    if expected_index_digest is not None:
        _check_file_digest(index_path, "artifact-index.json", expected_index_digest, errors)
        checked_paths.add(ARTIFACT_INDEX_PATH.as_posix())
    index = _read_package_index(index_path, errors)
    if index is None:
        return PackageVerifyResult(path=package_path, checked_count=len(checked_paths), errors=errors)

    for entry in index.get("included") or []:
        if isinstance(entry, dict):
            _check_index_entry(package_path, entry, errors)
            package_path_text = entry.get("package_path")
            if isinstance(package_path_text, str) and package_path_text:
                checked_paths.add(package_path_text)
    for entry in index.get("package_metadata") or []:
        if not isinstance(entry, dict):
            errors.append("package_metadata contains a non-object entry")
            continue
        package_path_text = entry.get("package_path")
        if not isinstance(package_path_text, str) or not package_path_text:
            errors.append("package_metadata entry is missing package_path")
            continue
        checked_paths.add(package_path_text)
        if package_path_text == ARTIFACT_INDEX_PATH.as_posix():
            continue
        _check_index_entry(package_path, entry, errors)
        if package_path_text == "package-summary.json":
            _check_package_summary_json(package_path / package_path_text, errors)

    checked_paths.add(ARTIFACT_INDEX_DIGEST_PATH.as_posix())
    for path in _package_files(package_path):
        relative = path.relative_to(package_path).as_posix()
        if relative not in checked_paths:
            errors.append(f"unexpected package file: {relative}")

    return PackageVerifyResult(path=package_path, checked_count=len(checked_paths), errors=errors)


def _prepare_output_dir(root: Path, output_dir: Path) -> Path:
    output_path = output_dir if output_dir.is_absolute() else root / output_dir
    output_path = output_path.resolve()
    if output_path.exists():
        if not output_path.is_dir():
            raise PackageOutputError(f"{output_path} exists and is not a directory")
        try:
            next(output_path.iterdir())
        except StopIteration:
            return output_path
        except OSError as exc:
            raise PackageOutputError(str(exc)) from exc
        raise PackageOutputError(f"{output_path} already exists and is not empty")

    parent = output_path.parent
    if parent.exists() and not parent.is_dir():
        raise PackageOutputError(f"{parent} exists and is not a directory")
    try:
        output_path.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise PackageOutputError(str(exc)) from exc
    return output_path


def _package_specs(task_path: Path) -> list[PackageFileSpec]:
    specs = list(PACKAGE_FILE_SPECS)
    figures_dir = task_path / "figures"
    if figures_dir.is_dir():
        for path in sorted([*figures_dir.glob("*.png"), *figures_dir.glob("*.svg")], key=lambda item: item.name.lower()):
            specs.append(
                PackageFileSpec(
                    path.relative_to(task_path),
                    "figures",
                    "Generated figure image.",
                )
            )
    else:
        specs.append(PackageFileSpec(Path("figures/*.png"), "figures", "Generated figure PNG files."))
        specs.append(PackageFileSpec(Path("figures/*.svg"), "figures", "Generated figure SVG files."))
    return specs


def _copy_file(source: Path, destination: Path, spec: PackageFileSpec) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "path": spec.relative_path.as_posix(),
        "package_path": spec.relative_path.as_posix(),
        "source_path": spec.relative_path.as_posix(),
        "category": spec.category,
        "description": spec.description,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
    }


def _package_metadata_entries(output_path: Path) -> list[dict[str, Any]]:
    entries = [
        _package_metadata_entry(output_path / "README.md", "Package README."),
        _package_metadata_entry(output_path / "package-summary.json", "Package summary metadata."),
        _package_metadata_entry(output_path / "redaction-notes.md", "Package redaction and omission notes."),
    ]
    entries.append(
        {
            "path": "artifact-index.json",
            "package_path": "artifact-index.json",
            "category": "package_metadata",
            "description": "Package artifact index.",
            "size_bytes": None,
            "sha256": None,
            "digest_omitted_reason": "artifact-index.json is self-referential; hash the file after package creation if an external digest is required",
        }
    )
    return entries


def _package_metadata_entry(path: Path, description: str) -> dict[str, Any]:
    return {
        "path": path.name,
        "package_path": path.name,
        "category": "package_metadata",
        "description": description,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _omitted_entries(root: Path, task_path: Path, record: TaskRecord) -> list[dict[str, Any]]:
    omitted: list[dict[str, Any]] = []
    _add_omitted_if_exists(omitted, task_path / "stdout.log", task_path, "log", "full stdout logs are omitted by default")
    _add_omitted_if_exists(omitted, task_path / "stderr.log", task_path, "log", "full stderr logs are omitted by default")
    _add_omitted_if_exists(
        omitted,
        task_path / "raw" / "source_refs.json",
        task_path,
        "raw",
        "raw source references are omitted by default",
    )
    for worker_path in [task_path / "worker.log", task_path / "worker.err.log"]:
        _add_omitted_if_exists(
            omitted,
            worker_path,
            task_path,
            "worker",
            "worker transcripts and worker logs are omitted by default",
        )
    intelligence_path = task_path / "intelligence"
    if intelligence_path.exists():
        _add_omitted_if_exists(
            omitted,
            intelligence_path,
            task_path,
            "worker",
            "worker audit files are omitted by default",
        )
        for audit_path in sorted(
            [
                *intelligence_path.glob("*/ai-provider-prompt.json"),
                *intelligence_path.glob("*/ai-provider-response.json"),
            ]
        ):
            _add_omitted_if_exists(
                omitted,
                audit_path,
                task_path,
                "worker",
                "worker prompt and response bodies are omitted by default",
            )
        for sandbox_path in sorted(intelligence_path.glob("*/sandbox")):
            _add_omitted_if_exists(
                omitted,
                sandbox_path,
                task_path,
                "sandbox",
                "temporary sandbox files are omitted by default",
            )
    _add_omitted_if_exists(
        omitted,
        task_path / "sandbox",
        task_path,
        "sandbox",
        "temporary sandbox files are omitted by default",
    )
    index_path = sqlite_path(root)
    if index_path.exists():
        omitted.append(
            {
                "path": ".lab-sidecar/index.sqlite",
                "category": "index",
                "reason": "local SQLite indexes are omitted by default",
            }
        )
    if record.source_path:
        omitted.append(
            {
                "path": record.source_path,
                "category": "raw_source",
                "reason": "raw ingested source files are referenced but not copied by default",
            }
        )
    omitted.append(
        {
            "path": "workspace/*",
            "category": "workspace",
            "reason": "unrelated workspace files are not copied by default",
        }
    )
    return _dedupe_entries(omitted)


def _add_omitted_if_exists(
    omitted: list[dict[str, Any]],
    path: Path,
    task_path: Path,
    category: str,
    reason: str,
) -> None:
    if not path.exists():
        return
    omitted.append(
        {
            "path": path.relative_to(task_path).as_posix(),
            "category": category,
            "reason": reason,
        }
    )


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped = []
    for entry in entries:
        key = (str(entry.get("path", "")), str(entry.get("category", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _package_type(record: TaskRecord) -> str:
    if record.status == TaskStatus.COMPLETED:
        return "result"
    return "diagnostic"


def _package_summary(
    record: TaskRecord,
    package_name: str,
    package_type: str,
    created_at: str,
    included: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "created_at": created_at,
        "package_type": package_type,
        "package_name": package_name,
        "task": {
            "task_id": record.task_id,
            "name": record.name,
            "mode": record.mode,
            "status": record.status.value,
            "exit_code": record.exit_code,
            "created_at": record.created_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "command_preview": _package_command_preview(record, included),
            "run_mode": effective_run_mode(record),
            "argv_count": len(record.argv or []) if effective_run_mode(record) == "argv" else None,
            "run_spec_path": "reproduce/run.json" if _has_run_spec(record, included) else None,
            "safe_profile": record.safe_profile,
            "source_path": record.source_path,
            "failure_summary": _bounded_failure_summary(record.failure_summary),
        },
        "counts": {
            "included": len(included),
            "omitted": len(omitted),
            "unavailable": len(unavailable),
        },
        "included_artifacts": [
            {
                "path": item["package_path"],
                "category": item["category"],
                "description": item["description"],
            }
            for item in included
        ],
        "omission_policy": "allowlist package; full logs, raw source files, local indexes, worker transcripts, sandbox files, and unrelated workspace files are omitted by default",
    }


def _has_run_spec(record: TaskRecord, included: list[dict[str, Any]]) -> bool:
    if record.mode != "run":
        return False
    return any(item.get("package_path") == "reproduce/run.json" for item in included)


def _package_command_preview(record: TaskRecord, included: list[dict[str, Any]]) -> str:
    if effective_run_mode(record) != "argv":
        return _preview(record.command)
    argv_count = len(record.argv or [])
    if _has_run_spec(record, included):
        return f"(argv mode; {argv_count} args; see reproduce/run.json)"
    return f"(argv mode; {argv_count} args; structured run metadata unavailable)"


def _readme(
    record: TaskRecord,
    summary: dict[str, Any],
    included: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> str:
    title = "Failed Task Diagnostic Package" if summary["package_type"] == "diagnostic" else "Lab-Sidecar Result Package"
    lines = [
        f"# {title}",
        "",
        f"Task id: `{record.task_id}`",
        f"Task name: `{record.name or '(unnamed)'}`",
        f"Status: `{record.status.value}`",
        f"Mode: `{record.mode}`",
        f"Exit code: `{record.exit_code}`",
    ]
    if record.mode == "ingest":
        lines.append(f"Source path: `{record.source_path or '(none)'}`")
    else:
        lines.append(f"Command preview: `{_package_command_preview(record, included)}`")
        lines.append(f"Run mode: `{effective_run_mode(record) or 'shell'}`")
    if summary["package_type"] == "diagnostic":
        lines.extend(
            [
                "",
                "This is a failed-task diagnostic package, not a successful experiment summary.",
            ]
        )
        failure_summary = _bounded_failure_summary(record.failure_summary)
        if failure_summary:
            lines.extend(["", "## Failure Summary", "", "```text", failure_summary, "```"])
    lines.extend(
        [
            "",
            "## Included Artifacts",
            "",
        ]
    )
    grouped = _group_paths(included)
    if grouped:
        for category, paths in grouped.items():
            lines.append(f"- {category}: {', '.join(f'`{path}`' for path in paths)}")
    else:
        lines.append("- (none)")
    reproduce_paths = [item["package_path"] for item in included if item["category"] == "reproduce"]
    lines.extend(["", "## Reproduce", ""])
    if reproduce_paths:
        lines.append("Start with these metadata files:")
        for path in reproduce_paths:
            lines.append(f"- `{path}`")
    else:
        lines.append("No reproduce metadata files were available for this task.")
    lines.extend(
        [
            "",
            "## Omission Notes",
            "",
            "This package uses a conservative allowlist. Full stdout/stderr logs, raw source files, local SQLite indexes, worker transcripts, sandbox files, and unrelated workspace files were not copied by default.",
            "",
            "See `artifact-index.json` for included, omitted, and unavailable files, "
            "and `artifact-index.sha256` for the package index digest. Run "
            "`labsidecar package-verify <package_dir>` to check the digest, "
            "indexed file hashes and sizes, and unexpected files. See "
            "`redaction-notes.md` for the default omission policy.",
        ]
    )
    if unavailable:
        lines.extend(["", "## Unavailable Optional Artifacts", ""])
        for item in unavailable:
            lines.append(f"- `{item['path']}`: {item['reason']}")
    if omitted:
        lines.extend(["", "## Omitted By Default", ""])
        for item in omitted:
            lines.append(f"- `{item['path']}`: {item['reason']}")
    return "\n".join(lines) + "\n"


def _redaction_notes(
    record: TaskRecord,
    omitted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> str:
    lines = [
        "# Redaction Notes",
        "",
        f"Package task id: `{record.task_id}`",
        "",
        "This package was built with a local allowlist. It includes the task manifest, reproduce metadata, normalized metrics, generated figures, report fragments, and slide drafts when those files are present.",
        "",
        "`manifest.json`, `reproduce/run.json`, and `provenance/traceability.json` can include command previews, argv values, local paths, and other run metadata. Review and redact those files before sharing outside a trusted context.",
        "",
        "The default package does not copy full stdout/stderr logs, raw source files, `.lab-sidecar/index.sqlite`, worker prompt or response bodies, temporary sandbox files, or unrelated workspace files.",
        "",
        "Use the original workspace and `labsidecar logs <task_id>` when full logs are needed for private debugging.",
        "",
        "## Omitted By Default",
        "",
    ]
    if omitted:
        for item in omitted:
            lines.append(f"- `{item['path']}`: {item['reason']}")
    else:
        lines.append("- (none recorded)")
    lines.extend(["", "## Unavailable Optional Artifacts", ""])
    if unavailable:
        for item in unavailable:
            lines.append(f"- `{item['path']}`: {item['reason']}")
    else:
        lines.append("- (none)")
    return "\n".join(lines) + "\n"


def _group_paths(included: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in included:
        grouped.setdefault(item["category"], []).append(item["package_path"])
    return {category: sorted(paths) for category, paths in sorted(grouped.items())}


def _preview(value: str | None, limit: int = COMMAND_PREVIEW_CHARS) -> str:
    if not value:
        return "(none)"
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _bounded_failure_summary(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if len(normalized) <= FAILURE_SUMMARY_CHARS:
        return normalized
    return normalized[: FAILURE_SUMMARY_CHARS - 3].rstrip() + "..."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_index_digest(package_path: Path) -> None:
    digest = _sha256(package_path / ARTIFACT_INDEX_PATH)
    (package_path / ARTIFACT_INDEX_DIGEST_PATH).write_text(
        f"{digest}  {ARTIFACT_INDEX_PATH.as_posix()}\n",
        encoding="utf-8",
    )


def _read_index_digest(path: Path, errors: list[str]) -> str | None:
    if not path.is_file():
        errors.append(f"{ARTIFACT_INDEX_DIGEST_PATH.as_posix()} is missing")
        return None
    try:
        line = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        errors.append(f"{ARTIFACT_INDEX_DIGEST_PATH.as_posix()} could not be read: {exc}")
        return None
    parts = line.split()
    if len(parts) != 2 or parts[1] != ARTIFACT_INDEX_PATH.as_posix() or len(parts[0]) != 64:
        errors.append(f"{ARTIFACT_INDEX_DIGEST_PATH.as_posix()} is not a valid artifact-index checksum")
        return None
    return parts[0]


def _check_file_digest(path: Path, display_path: str, expected_sha256: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"missing package file: {display_path}")
        return
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        errors.append(f"sha256 mismatch for {display_path}")


def _read_package_index(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{ARTIFACT_INDEX_PATH.as_posix()} is missing")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{ARTIFACT_INDEX_PATH.as_posix()} could not be parsed: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{ARTIFACT_INDEX_PATH.as_posix()} does not contain a JSON object")
        return None
    return data


def _check_index_entry(package_path: Path, entry: dict[str, Any], errors: list[str]) -> None:
    package_path_text = entry.get("package_path")
    if not isinstance(package_path_text, str) or not package_path_text:
        errors.append("artifact index entry is missing package_path")
        return
    relative_path = Path(package_path_text)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        errors.append(f"unsafe package path in artifact index: {package_path_text}")
        return
    file_path = package_path / relative_path
    if not file_path.is_file():
        errors.append(f"missing package file: {package_path_text}")
        return
    expected_size = entry.get("size_bytes")
    if isinstance(expected_size, int) and file_path.stat().st_size != expected_size:
        errors.append(f"size mismatch for {package_path_text}")
    expected_sha256 = entry.get("sha256")
    if isinstance(expected_sha256, str) and expected_sha256:
        _check_file_digest(file_path, package_path_text, expected_sha256, errors)


def _check_package_summary_json(path: Path, errors: list[str]) -> None:
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"package-summary.json could not be parsed: {exc}")
        return
    if not isinstance(data, dict):
        errors.append("package-summary.json does not contain a JSON object")
        return
    if not data.get("package_type"):
        errors.append("package-summary.json is missing package_type")


def _package_files(package_path: Path) -> list[Path]:
    return sorted(
        [path for path in package_path.rglob("*") if path.is_file()],
        key=lambda item: item.relative_to(package_path).as_posix(),
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
