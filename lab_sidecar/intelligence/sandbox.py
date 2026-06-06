from __future__ import annotations

from pathlib import Path


OFFICIAL_ARTIFACT_DIRS = {
    "metrics",
    "figures",
    "reports",
    "slides",
    "reproduce",
}
OFFICIAL_ARTIFACT_FILES = {"manifest.json", "stdout.log", "stderr.log"}


def is_path_within(path: Path, boundary: Path) -> bool:
    try:
        path.resolve().relative_to(boundary.resolve())
    except ValueError:
        return False
    return True


def resolve_sandbox_path(sandbox: Path, path_text: str) -> Path:
    path = Path(path_text)
    candidate = path if path.is_absolute() else sandbox / path
    resolved = candidate.resolve()
    if not is_path_within(resolved, sandbox):
        raise SandboxBoundaryError(f"path escapes sandbox: {path_text}")
    return resolved


def is_official_artifact_path(path: Path, task_path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(task_path.resolve())
    except ValueError:
        return False
    if not relative.parts:
        return False
    return relative.parts[0] in OFFICIAL_ARTIFACT_DIRS or relative.parts[0] in OFFICIAL_ARTIFACT_FILES


class SandboxBoundaryError(ValueError):
    pass
