from __future__ import annotations

import hashlib
import importlib.metadata
import subprocess
import sys
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_provenance(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "size_bytes": stat.st_size,
        "sha256": file_sha256(path),
    }


def dependency_snapshot() -> dict[str, str]:
    packages: dict[str, str] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        packages[name] = dist.version
    return dict(sorted(packages.items(), key=lambda item: item[0].lower()))


def git_snapshot(cwd: Path) -> dict[str, Any]:
    repo_root = _git(["rev-parse", "--show-toplevel"], cwd)
    if repo_root is None:
        return {"is_repository": False}

    commit = _git(["rev-parse", "HEAD"], cwd)
    branch = _git(["branch", "--show-current"], cwd)
    status = _git(["status", "--short"], cwd)
    return {
        "is_repository": True,
        "root": repo_root,
        "commit": commit,
        "branch": branch or None,
        "status_short": status.splitlines() if status else [],
        "dirty": bool(status),
    }


def _git(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def python_executable() -> str:
    return sys.executable
