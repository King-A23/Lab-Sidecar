from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from lab_sidecar.core.models import TaskRecord
from lab_sidecar.core.paths import resolve_workspace_path, state_dir


SUPPORTED_SUFFIXES = {".csv", ".json"}
TASK_METADATA_FILES = {"manifest.json"}
RUN_WORKING_DIR_MTIME_TOLERANCE_SECONDS = 2


@dataclass(frozen=True)
class CandidateFile:
    path: Path
    origin: str

    @property
    def source_file(self) -> str:
        return self.path.as_posix()


def scan_metric_candidates(root: Path, record: TaskRecord) -> list[CandidateFile]:
    """Return supported metric files without recursively scanning large trees."""
    task_path = resolve_workspace_path(record.paths.task_dir, root)
    candidates: dict[str, CandidateFile] = {}

    _add_task_directory_files(task_path, candidates)
    _add_source_ref_files(root, task_path, candidates)
    _add_run_working_directory_files(root, record, candidates)

    return sorted(candidates.values(), key=lambda candidate: candidate.path.as_posix().lower())


def _add_task_directory_files(task_path: Path, candidates: dict[str, CandidateFile]) -> None:
    if not task_path.exists():
        return
    for child in task_path.iterdir():
        if child.name in TASK_METADATA_FILES:
            continue
        if child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
            _add_candidate(candidates, child.resolve(), "task_dir")


def _add_source_ref_files(root: Path, task_path: Path, candidates: dict[str, CandidateFile]) -> None:
    refs_path = task_path / "raw" / "source_refs.json"
    if not refs_path.exists():
        return

    try:
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    source_type = refs.get("source_type")
    if source_type == "file":
        source_path = _resolve_ref_path(root, refs.get("source_path"))
        if source_path and source_path.is_file() and source_path.suffix.lower() in SUPPORTED_SUFFIXES:
            _add_candidate(candidates, source_path.resolve(), "source_refs")
        return

    if source_type == "directory":
        for path_text in _iter_directory_ref_files(refs):
            source_path = _resolve_ref_path(root, path_text)
            if source_path and source_path.is_file() and source_path.suffix.lower() in SUPPORTED_SUFFIXES:
                _add_candidate(candidates, source_path.resolve(), "source_refs")


def _add_run_working_directory_files(
    root: Path,
    record: TaskRecord,
    candidates: dict[str, CandidateFile],
) -> None:
    if record.mode != "run":
        return

    working_dir = resolve_workspace_path(record.working_dir, root).resolve()
    root = root.resolve()
    if not _is_within(working_dir, root):
        return
    if _is_within(working_dir, state_dir(root).resolve()):
        return
    if not working_dir.is_dir():
        return

    cutoff = _task_cutoff_timestamp(record)
    for child in working_dir.iterdir():
        if not child.is_file() or child.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            modified_at = child.stat().st_mtime
        except OSError:
            continue
        if cutoff is not None and modified_at < cutoff:
            continue
        _add_candidate(candidates, child.resolve(), "run_working_dir")


def _iter_directory_ref_files(refs: dict[str, Any]) -> list[str]:
    candidate_files = refs.get("candidate_files")
    if isinstance(candidate_files, list):
        return [item for item in candidate_files if isinstance(item, str)]

    children = refs.get("children")
    if not isinstance(children, list):
        return []

    files: list[str] = []
    for child in children:
        if (
            isinstance(child, dict)
            and child.get("type") == "file"
            and child.get("is_candidate") is True
            and isinstance(child.get("path"), str)
        ):
            files.append(child["path"])
    return files


def _resolve_ref_path(root: Path, path_text: object) -> Path | None:
    if not isinstance(path_text, str) or not path_text:
        return None
    return resolve_workspace_path(path_text, root)


def _add_candidate(candidates: dict[str, CandidateFile], path: Path, origin: str) -> None:
    candidates[path.as_posix()] = CandidateFile(path=path, origin=origin)


def _task_cutoff_timestamp(record: TaskRecord) -> float | None:
    timestamp = record.started_at or record.created_at
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    return (parsed - timedelta(seconds=RUN_WORKING_DIR_MTIME_TOLERANCE_SECONDS)).timestamp()


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True
