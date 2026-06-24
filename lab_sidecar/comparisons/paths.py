from __future__ import annotations

import re
from pathlib import Path

from lab_sidecar.core.paths import state_dir


COMPARISONS_DIR_NAME = "comparisons"
COMPARISON_ID_PATTERN = re.compile(r"^comparison_\d{8}_\d{6}_[0-9a-f]{6}$")


def comparisons_dir(root: Path) -> Path:
    return state_dir(root) / COMPARISONS_DIR_NAME


def is_valid_comparison_id(comparison_id: str) -> bool:
    return bool(COMPARISON_ID_PATTERN.fullmatch(comparison_id))


def comparison_dir(root: Path, comparison_id: str) -> Path:
    return comparisons_dir(root) / comparison_id


def comparison_manifest_path(root: Path, comparison_id: str) -> Path:
    return comparison_dir(root, comparison_id) / "comparison-manifest.json"
