from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lab_sidecar.core.models import ArtifactRecord, TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path


DEFAULT_OMITTED = {
    "full_command": "omitted_by_default",
    "full_stdout": "omitted_by_default",
    "full_stderr": "omitted_by_default",
    "metrics_rows": "omitted_by_default",
    "artifact_bodies": "omitted_by_default",
}
MAX_ARTIFACTS = 40
MAX_WARNINGS = 10
MAX_COMMAND_CHARS = 500
MAX_FAILURE_SUMMARY_CHARS = 1200
MAX_LOG_TAIL_LINES = 20
REDACTION_TEXT = "[REDACTED]"
SECRET_PATTERNS = [
    re.compile(r"(?i)(--(?:api[-_]?key|token|password|secret)(?:=|\s+))([^\s\"']+)"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)([^\s\"']+)"),
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9_\-./+=]{8,})"),
    re.compile(r"\b(sk)-[A-Za-z0-9_\-]{8,}\b"),
]


def base_response(
    record: TaskRecord | None,
    summary: dict[str, Any],
    artifacts: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    next_actions: list[str] | None = None,
    omitted: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "task_id": record.task_id if record else None,
        "task_status": record.status.value if record else None,
        "summary": summary,
        "artifacts": artifacts or [],
        "warnings": (warnings or [])[:MAX_WARNINGS],
        "next_actions": next_actions or [],
        "omitted": {**DEFAULT_OMITTED, **(omitted or {})},
    }


def safety_response(summary: dict[str, Any]) -> dict[str, Any]:
    return base_response(
        None,
        summary=summary,
        warnings=summary.get("reasons", []),
        next_actions=["revise the command or provide the returned confirmation token when confirmation is allowed"],
    )


def artifact_list(record: TaskRecord, include_logs: bool = True) -> list[dict[str, Any]]:
    items = []
    for artifact in record.artifacts[:MAX_ARTIFACTS]:
        if not include_logs and artifact.type == "log":
            continue
        items.append(artifact_to_dict(artifact))
    return items


def artifact_to_dict(artifact: ArtifactRecord) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "path": artifact.path,
        "description": artifact.description,
        "source_paths": artifact.source_paths,
    }


def task_summary(root: Path, record: TaskRecord) -> dict[str, Any]:
    return {
        "mode": record.mode,
        "status": record.status.value,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "exit_code": record.exit_code,
        "working_dir": record.working_dir,
        "command": command_preview(record.command),
        "artifact_dir": record.paths.task_dir,
        "artifact_count": record.artifact_count(),
        "failure_summary": _short_text(record.failure_summary, MAX_FAILURE_SUMMARY_CHARS),
    }


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def compact_task_outputs(root: Path, record: TaskRecord) -> dict[str, Any]:
    task_path = resolve_workspace_path(record.paths.task_dir, root)
    collection = read_json_if_exists(task_path / "metrics" / "collection-summary.json")
    figures = read_json_if_exists(task_path / "figures" / "figure-summary.json")
    report = read_json_if_exists(task_path / "reports" / "report-summary.json")
    slides = read_json_if_exists(task_path / "slides" / "slides-summary.json")

    return {
        "metrics": {
            "present": bool(collection),
            "row_count": collection.get("row_count", 0),
            "detected_fields": collection.get("detected_fields", []),
            "candidate_count": collection.get("candidate_count", 0),
            "processed_files": collection.get("processed_files", [])[:MAX_WARNINGS],
        },
        "figures": {
            "present": bool(figures),
            "figure_count": figures.get("figure_count", 0),
            "warnings": figures.get("warnings", [])[:MAX_WARNINGS],
            "errors": figures.get("errors", [])[:MAX_WARNINGS],
        },
        "report": {
            "present": bool(report),
            "template": report.get("template"),
            "path": report.get("report_path"),
        },
        "slides": {
            "present": bool(slides),
            "template": slides.get("template"),
            "slide_count": slides.get("slide_count"),
            "qa_checks": _compact_qa(slides.get("qa_checks", {})),
        },
    }


def bounded_log_tail(path: Path, line_count: int) -> list[str]:
    lines = min(max(line_count, 0), MAX_LOG_TAIL_LINES)
    if lines == 0 or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]


def command_preview(command: str | None) -> str | None:
    if command is None:
        return None
    preview = command
    for pattern in SECRET_PATTERNS:
        preview = pattern.sub(_redacted_secret, preview)
    return _short_text(preview, MAX_COMMAND_CHARS)


def _redacted_secret(match: re.Match[str]) -> str:
    if match.lastindex == 1:
        return f"{match.group(1)}-{REDACTION_TEXT}"
    return f"{match.group(1)}{REDACTION_TEXT}"


def _compact_qa(qa_checks: Any) -> dict[str, bool | None]:
    if not isinstance(qa_checks, dict):
        return {}
    result = {}
    for key, value in qa_checks.items():
        if isinstance(value, dict):
            result[key] = value.get("passed")
    return result


def _short_text(value: str | None, limit: int) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
