from __future__ import annotations

import json
from pathlib import Path

from lab_sidecar.core.models import ArtifactRecord
from lab_sidecar.core.paths import to_manifest_path
from lab_sidecar.core.provenance import file_provenance

SOURCE_CANDIDATE_SUFFIXES = {".csv", ".json", ".log", ".txt", ".md"}
MAX_RECURSIVE_SOURCE_REF_FILES = 1000


def default_task_artifacts(task_dir: Path, root: Path) -> list[ArtifactRecord]:
    stdout = task_dir / "stdout.log"
    stderr = task_dir / "stderr.log"
    command = task_dir / "reproduce" / "command.txt"
    env = task_dir / "reproduce" / "env.json"
    git = task_dir / "reproduce" / "git.json"
    dependencies = task_dir / "reproduce" / "dependencies.json"
    return [
        ArtifactRecord(
            artifact_id="log_stdout",
            type="log",
            path=to_manifest_path(stdout, root),
            description="Captured stdout log",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="log_stderr",
            type="log",
            path=to_manifest_path(stderr, root),
            description="Captured stderr log",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="reproduce_command",
            type="reproduce",
            path=to_manifest_path(command, root),
            description="Original command used to run the task",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="reproduce_env",
            type="reproduce",
            path=to_manifest_path(env, root),
            description="Environment snapshot captured at task start",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="reproduce_git",
            type="reproduce",
            path=to_manifest_path(git, root),
            description="Git snapshot captured at task start",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="reproduce_dependencies",
            type="reproduce",
            path=to_manifest_path(dependencies, root),
            description="Python dependency snapshot captured at task start",
            source_paths=[],
        ),
    ]


def ingest_task_artifacts(task_dir: Path, root: Path) -> list[ArtifactRecord]:
    stdout = task_dir / "stdout.log"
    stderr = task_dir / "stderr.log"
    source_refs = task_dir / "raw" / "source_refs.json"
    return [
        ArtifactRecord(
            artifact_id="log_stdout",
            type="log",
            path=to_manifest_path(stdout, root),
            description="Empty stdout log for imported results",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="log_stderr",
            type="log",
            path=to_manifest_path(stderr, root),
            description="Empty stderr log for imported results",
            source_paths=[],
        ),
        ArtifactRecord(
            artifact_id="raw_source_refs",
            type="raw",
            path=to_manifest_path(source_refs, root),
            description="References to imported source files",
            source_paths=[],
        ),
    ]


def source_path_kind(source: Path, root: Path) -> str:
    try:
        source.resolve().relative_to(root.resolve())
    except ValueError:
        return "absolute"
    return "relative"


def build_source_refs(source: Path, root: Path) -> dict:
    resolved = source.resolve()
    path_kind = source_path_kind(resolved, root)
    stat = resolved.stat()
    data = {
        "source_path": to_manifest_path(resolved, root),
        "path_kind": path_kind,
        "source_type": "directory" if resolved.is_dir() else "file",
        "modified_at": _mtime_iso(stat.st_mtime),
        "candidate_suffixes": sorted(SOURCE_CANDIDATE_SUFFIXES),
    }
    if resolved.is_file():
        data.update(file_provenance(resolved))
        data["is_candidate"] = resolved.suffix.lower() in SOURCE_CANDIDATE_SUFFIXES
        return data

    children = []
    candidate_files = []
    for child in sorted(resolved.iterdir(), key=lambda item: item.name.lower()):
        child_stat = child.stat()
        child_summary = {
            "path": to_manifest_path(child.resolve(), root),
            "name": child.name,
            "type": "directory" if child.is_dir() else "file",
            "modified_at": _mtime_iso(child_stat.st_mtime),
        }
        if child.is_file():
            child_summary.update(file_provenance(child))
            child_summary["suffix"] = child.suffix.lower()
            child_summary["is_candidate"] = child.suffix.lower() in SOURCE_CANDIDATE_SUFFIXES
            if child_summary["is_candidate"]:
                candidate_files.append(child_summary["path"])
        children.append(child_summary)

    candidate_refs, truncated = _recursive_candidate_file_refs(resolved, root)
    data["children"] = children
    data["child_count"] = len(children)
    data["candidate_files"] = candidate_files
    data["candidate_file_refs"] = candidate_refs
    data["candidate_file_count"] = len(candidate_refs)
    data["candidate_files_truncated"] = truncated
    return data


def write_source_refs(path: Path, refs: dict) -> None:
    path.write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mtime_iso(timestamp: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone().isoformat(timespec="seconds")


def _recursive_candidate_file_refs(source: Path, root: Path) -> tuple[list[dict], bool]:
    refs: list[dict] = []
    for child in sorted(source.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not child.is_file() or child.suffix.lower() not in SOURCE_CANDIDATE_SUFFIXES:
            continue
        child_stat = child.stat()
        item = {
            "path": to_manifest_path(child.resolve(), root),
            "name": child.name,
            "suffix": child.suffix.lower(),
            "modified_at": _mtime_iso(child_stat.st_mtime),
            "is_candidate": True,
        }
        item.update(file_provenance(child))
        refs.append(item)
        if len(refs) >= MAX_RECURSIVE_SOURCE_REF_FILES:
            return refs, True
    return refs, False
