from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_sidecar.comparisons.models import ComparisonManifest
from lab_sidecar.comparisons.paths import comparison_dir
from lab_sidecar.comparisons.service import (
    FIGURE_SUMMARY_RELATIVE_PATH,
    MANIFEST_RELATIVE_PATH,
    REPORT_RELATIVE_PATH,
    REPORT_SUMMARY_RELATIVE_PATH,
    SUMMARY_RELATIVE_PATH,
    TABLE_CSV_RELATIVE_PATH,
    TABLE_JSON_RELATIVE_PATH,
    TRACEABILITY_RELATIVE_PATH,
    comparison_figure_image_paths,
    refresh_comparison_artifacts,
)
from lab_sidecar.storage.package_export import (
    ARTIFACT_INDEX_DIGEST_PATH,
    ARTIFACT_INDEX_PATH,
    PACKAGE_SCHEMA_VERSION,
    PackageExportResult,
    PackageOutputError,
)


class ComparisonPackageExportError(RuntimeError):
    """Raised when a comparison package cannot be created."""


@dataclass(frozen=True)
class ComparisonPackageFileSpec:
    relative_path: Path
    category: str
    description: str
    required: bool = False


COMPARISON_PACKAGE_FILE_SPECS = [
    ComparisonPackageFileSpec(MANIFEST_RELATIVE_PATH, "manifest", "Comparison manifest.", required=True),
    ComparisonPackageFileSpec(SUMMARY_RELATIVE_PATH, "comparison", "Bounded comparison summary.", required=True),
    ComparisonPackageFileSpec(TABLE_CSV_RELATIVE_PATH, "comparison", "Normalized comparison table CSV.", required=True),
    ComparisonPackageFileSpec(TABLE_JSON_RELATIVE_PATH, "comparison", "Normalized comparison table JSON.", required=True),
    ComparisonPackageFileSpec(FIGURE_SUMMARY_RELATIVE_PATH, "figures", "Comparison figure generation summary."),
    ComparisonPackageFileSpec(REPORT_RELATIVE_PATH, "reports", "Generated comparison report fragment."),
    ComparisonPackageFileSpec(REPORT_SUMMARY_RELATIVE_PATH, "reports", "Comparison report summary."),
    ComparisonPackageFileSpec(TRACEABILITY_RELATIVE_PATH, "provenance", "Comparison-local traceability evidence."),
]


def export_comparison_package(
    root: Path,
    manifest: ComparisonManifest,
    output_dir: Path,
) -> PackageExportResult:
    root = root.resolve()
    output_path = _prepare_output_dir(root, output_dir)
    manifest = refresh_comparison_artifacts(root, manifest)
    source_dir = comparison_dir(root, manifest.comparison_id)
    included: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []

    try:
        seen: set[Path] = set()
        for spec in _package_specs(source_dir):
            if spec.relative_path in seen:
                continue
            seen.add(spec.relative_path)
            source = source_dir / spec.relative_path
            if source.is_file():
                included.append(_copy_file(source, output_path / spec.relative_path, spec))
                continue
            if spec.required:
                raise ComparisonPackageExportError(f"required package file is missing: {spec.relative_path.as_posix()}")
            unavailable.append(
                {
                    "path": spec.relative_path.as_posix(),
                    "category": spec.category,
                    "reason": "not generated or not available for this comparison",
                }
            )

        omitted = _omitted_entries(root, manifest)
        created_at = _now_iso()
        package_type = "comparison"
        summary = _package_summary(
            manifest=manifest,
            package_name=output_path.name,
            created_at=created_at,
            included=included,
            omitted=omitted,
            unavailable=unavailable,
        )
        artifact_index = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "created_at": created_at,
            "comparison_id": manifest.comparison_id,
            "package_type": package_type,
            "included": included,
            "omitted": omitted,
            "unavailable": unavailable,
        }
        _write_json(output_path / "package-summary.json", summary)
        (output_path / "redaction-notes.md").write_text(_redaction_notes(manifest, omitted, unavailable), encoding="utf-8")
        (output_path / "README.md").write_text(_readme(manifest, included, omitted, unavailable), encoding="utf-8")
        artifact_index["package_metadata"] = _package_metadata_entries(output_path)
        _write_json(output_path / ARTIFACT_INDEX_PATH, artifact_index)
        _write_index_digest(output_path)
    except OSError as exc:
        raise ComparisonPackageExportError(str(exc)) from exc

    return PackageExportResult(
        path=output_path,
        package_type=package_type,
        included_count=len(included),
        omitted_count=len(omitted),
        unavailable_count=len(unavailable),
        digest_path=output_path / ARTIFACT_INDEX_DIGEST_PATH,
    )


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
    try:
        output_path.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise PackageOutputError(str(exc)) from exc
    return output_path


def _package_specs(source_dir: Path) -> list[ComparisonPackageFileSpec]:
    specs = list(COMPARISON_PACKAGE_FILE_SPECS)
    for path in comparison_figure_image_paths(source_dir):
        specs.append(
            ComparisonPackageFileSpec(
                path,
                "figures",
                "Generated comparison figure image.",
            )
        )
    return specs


def _copy_file(source: Path, destination: Path, spec: ComparisonPackageFileSpec) -> dict[str, Any]:
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


def _omitted_entries(root: Path, manifest: ComparisonManifest) -> list[dict[str, Any]]:
    omitted = [
        {
            "path": ".lab-sidecar/tasks/*/stdout.log",
            "category": "log",
            "reason": "source task full stdout logs are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/stderr.log",
            "category": "log",
            "reason": "source task full stderr logs are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/raw",
            "category": "raw",
            "reason": "source task raw files are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/metrics/normalized_metrics.csv",
            "category": "source_metrics",
            "reason": "source task full normalized metrics tables are referenced by path and digest but not copied",
        },
        {
            "path": ".lab-sidecar/tasks/*/intelligence",
            "category": "worker",
            "reason": "source task worker audit files are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/intelligence/*/ai-provider-prompt.json",
            "category": "worker",
            "reason": "source task worker prompt bodies are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/intelligence/*/ai-provider-response.json",
            "category": "worker",
            "reason": "source task worker response bodies are omitted by default",
        },
        {
            "path": ".lab-sidecar/tasks/*/intelligence/*/sandbox",
            "category": "sandbox",
            "reason": "source task temporary sandbox files are omitted by default",
        },
        {
            "path": "workspace/*",
            "category": "workspace",
            "reason": "unrelated workspace files are not copied by default",
        },
    ]
    if (root / ".lab-sidecar" / "index.sqlite").exists():
        omitted.append(
            {
                "path": ".lab-sidecar/index.sqlite",
                "category": "index",
                "reason": "local SQLite indexes are omitted by default",
            }
        )
    for item in manifest.source_tasks:
        task_id = item.get("task_id")
        omitted.append(
            {
                "path": f".lab-sidecar/tasks/{task_id}",
                "category": "source_task",
                "reason": "source task folders are referenced but not copied wholesale",
            }
        )
    return _dedupe_entries(omitted)


def _package_summary(
    *,
    manifest: ComparisonManifest,
    package_name: str,
    created_at: str,
    included: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "created_at": created_at,
        "package_type": "comparison",
        "package_name": package_name,
        "comparison": {
            "comparison_id": manifest.comparison_id,
            "name": manifest.name,
            "status": manifest.status.value,
            "task_ids": manifest.task_ids,
            "created_at": manifest.created_at,
            "row_selection": manifest.row_selection,
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
        "omission_policy": "allowlist comparison package; source task logs, raw files, full normalized source metric tables, local indexes, worker transcripts, sandbox files, and unrelated workspace files are omitted by default",
    }


def _readme(
    manifest: ComparisonManifest,
    included: list[dict[str, Any]],
    omitted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> str:
    lines = [
        "# Lab-Sidecar Comparison Package",
        "",
        f"Comparison id: `{manifest.comparison_id}`",
        f"Comparison name: `{manifest.name or '(unnamed)'}`",
        f"Source tasks: {', '.join(f'`{task_id}`' for task_id in manifest.task_ids)}",
        "",
        "This comparison is descriptive only; no statistical significance or model superiority is inferred.",
        "",
        "## Included Artifacts",
        "",
    ]
    grouped = _group_paths(included)
    if grouped:
        for category, paths in grouped.items():
            lines.append(f"- {category}: {', '.join(f'`{path}`' for path in paths)}")
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "## Omission Notes",
            "",
            "This package uses a conservative allowlist. Source task stdout/stderr logs, raw source files, full source normalized metrics tables, local SQLite indexes, worker transcripts, sandbox files, and unrelated workspace files were not copied by default.",
            "",
            "See `artifact-index.json` for included, omitted, and unavailable files, and `artifact-index.sha256` for the package index digest. Run `labsidecar package-verify <package_dir>` to check the digest, indexed file hashes and sizes, and unexpected files.",
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
    manifest: ComparisonManifest,
    omitted: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> str:
    lines = [
        "# Redaction Notes",
        "",
        f"Package comparison id: `{manifest.comparison_id}`",
        "",
        "This package was built with a local allowlist. It includes comparison metadata, comparison tables, generated comparison figures, report fragments, and traceability when present.",
        "",
        "The default package does not copy source task full logs, source task raw files, source tasks' full normalized metrics tables, `.lab-sidecar/index.sqlite`, worker prompt or response bodies, temporary sandbox files, or unrelated workspace files.",
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


def _group_paths(included: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in included:
        grouped.setdefault(item["category"], []).append(item["package_path"])
    return {category: sorted(paths) for category, paths in sorted(grouped.items())}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_index_digest(package_path: Path) -> None:
    digest = _sha256(package_path / ARTIFACT_INDEX_PATH)
    (package_path / ARTIFACT_INDEX_DIGEST_PATH).write_text(
        f"{digest}  {ARTIFACT_INDEX_PATH.as_posix()}\n",
        encoding="utf-8",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
