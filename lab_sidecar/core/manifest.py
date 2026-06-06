from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from lab_sidecar.core.models import TaskRecord, model_dump_jsonable
from lab_sidecar.core.paths import task_dir


def manifest_path(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / "manifest.json"


def write_manifest(path: Path, record: TaskRecord) -> None:
    payload = json.dumps(model_dump_jsonable(record), ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            tmp_name = fh.name
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
        _fsync_directory(path.parent)
    finally:
        if tmp_name is not None:
            try:
                Path(tmp_name).unlink()
            except FileNotFoundError:
                pass


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    fd: int | None = None
    try:
        fd = os.open(directory, os.O_RDONLY)
        os.fsync(fd)
    except OSError:
        return
    finally:
        if fd is not None:
            os.close(fd)


def read_manifest(path: Path) -> TaskRecord:
    return TaskRecord.model_validate_json(path.read_text(encoding="utf-8"))


def load_task(root: Path, task_id: str) -> TaskRecord:
    path = manifest_path(root, task_id)
    if not path.exists():
        raise FileNotFoundError(f"task '{task_id}' was not found")
    return read_manifest(path)
