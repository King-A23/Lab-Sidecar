from __future__ import annotations

from pathlib import Path


STATE_DIR_NAME = ".lab-sidecar"
TASKS_DIR_NAME = "tasks"


def workspace_root(path: Path | None = None) -> Path:
    return (path or Path.cwd()).resolve()


def state_dir(root: Path) -> Path:
    return root / STATE_DIR_NAME


def tasks_dir(root: Path) -> Path:
    return state_dir(root) / TASKS_DIR_NAME


def sqlite_path(root: Path) -> Path:
    return state_dir(root) / "index.sqlite"


def config_path(root: Path) -> Path:
    return state_dir(root) / "config.yaml"


def task_dir(root: Path, task_id: str) -> Path:
    return tasks_dir(root) / task_id


def to_manifest_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        value = resolved.relative_to(root_resolved)
    except ValueError:
        value = resolved
    return value.as_posix()


def resolve_workspace_path(path_text: str, root: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return root / path
