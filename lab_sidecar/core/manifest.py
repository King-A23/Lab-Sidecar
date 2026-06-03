from __future__ import annotations

import json
from pathlib import Path

from lab_sidecar.core.models import TaskRecord, model_dump_jsonable
from lab_sidecar.core.paths import task_dir


def manifest_path(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / "manifest.json"


def write_manifest(path: Path, record: TaskRecord) -> None:
    path.write_text(
        json.dumps(model_dump_jsonable(record), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_manifest(path: Path) -> TaskRecord:
    return TaskRecord.model_validate_json(path.read_text(encoding="utf-8"))


def load_task(root: Path, task_id: str) -> TaskRecord:
    path = manifest_path(root, task_id)
    if not path.exists():
        raise FileNotFoundError(f"task '{task_id}' was not found")
    return read_manifest(path)
