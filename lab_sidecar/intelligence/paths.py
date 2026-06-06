from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path

from lab_sidecar.core.paths import task_dir


INTELLIGENCE_DIR_NAME = "intelligence"
SANDBOX_DIR_NAME = "sandbox"


def generate_worker_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"worker_run_{stamp}_{secrets.token_hex(3)}"


def intelligence_dir(root: Path, task_id: str) -> Path:
    return task_dir(root, task_id) / INTELLIGENCE_DIR_NAME


def worker_run_dir(root: Path, task_id: str, worker_run_id: str) -> Path:
    return intelligence_dir(root, task_id) / worker_run_id


def sandbox_dir(root: Path, task_id: str, worker_run_id: str) -> Path:
    return worker_run_dir(root, task_id, worker_run_id) / SANDBOX_DIR_NAME


def create_worker_run_dirs(root: Path, task_id: str, worker_run_id: str) -> Path:
    run_dir = worker_run_dir(root, task_id, worker_run_id)
    sandbox = run_dir / SANDBOX_DIR_NAME
    sandbox.mkdir(parents=True, exist_ok=False)
    return run_dir
