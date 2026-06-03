from __future__ import annotations

import yaml
from pathlib import Path

from lab_sidecar.core.models import LabConfig
from lab_sidecar.core.paths import config_path, state_dir, tasks_dir
from lab_sidecar.storage.sqlite_index import ensure_index


def init_workspace(root: Path, force: bool = False) -> tuple[bool, LabConfig]:
    sidecar_dir = state_dir(root)
    cfg_path = config_path(root)

    existed = sidecar_dir.exists()
    if existed and not force:
        raise FileExistsError(f"{root} is already initialized")

    sidecar_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir(root).mkdir(parents=True, exist_ok=True)

    config = LabConfig()
    if not cfg_path.exists():
        cfg_path.write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")

    ensure_index(root)
    return (not existed), config


def load_config(root: Path) -> LabConfig:
    cfg_path = config_path(root)
    if not cfg_path.exists():
        raise FileNotFoundError("Lab-Sidecar workspace is not initialized")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return LabConfig.model_validate(data)
