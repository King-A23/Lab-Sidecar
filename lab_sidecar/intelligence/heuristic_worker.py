from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lab_sidecar.figures.specs import friendly_label
from lab_sidecar.intelligence.paths import worker_run_dir


NUMERIC_TYPES = {"number"}
PROCESS_ALIASES = {"epoch": "epoch", "step": "step", "iter": "epoch", "iteration": "epoch", "round": "epoch"}
GROUP_ALIASES = {"model": "model", "variant": "model", "method": "method", "algorithm": "method", "trial": "seed", "seed": "seed"}
METRIC_ALIASES = {
    "accuracy": "accuracy",
    "acc": "accuracy",
    "score": "score",
    "f1": "f1",
    "loss": "loss",
    "err": "loss",
    "error": "loss",
    "latency": "latency",
    "runtime": "latency",
    "duration": "duration",
}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def propose_metrics(root: Path, task_id: str, worker_run_id: str, bundle: dict[str, Any]) -> dict[str, Any] | None:
    preview = _best_metric_preview(bundle.get("candidate_previews", []))
    if not preview:
        return None

    mappings = _metric_mappings(preview)
    if not mappings:
        return None

    proposal = {
        "schema_version": "2.1",
        "proposal_type": "metrics",
        "task_id": task_id,
        "worker_run_id": worker_run_id,
        "source_files": [
            {
                "path": preview["path"],
                "sha256": preview.get("sha256"),
                "size_bytes": preview.get("size_bytes"),
                "columns": preview.get("columns", []),
            }
        ],
        "field_mappings": mappings,
        "group_fields": [item["target"] for item in mappings if item["target"] in {"model", "method", "seed"}],
        "confidence": 0.72,
        "rationale": "Mapped likely experiment fields from bounded column names, inferred types, null counts, row samples, and sample stats.",
    }
    path = worker_run_dir(root, task_id, worker_run_id) / "metrics-proposal.yaml"
    write_yaml(path, proposal)
    return proposal


def propose_figure(
    root: Path,
    task_id: str,
    worker_run_id: str,
    bundle: dict[str, Any],
) -> dict[str, Any] | None:
    preview = _best_figure_preview(bundle.get("data_previews", []))
    if not preview:
        return None

    columns = list(preview.get("columns") or preview.get("keys") or [])
    types = preview.get("inferred_types") or {}
    numeric = [column for column in columns if types.get(column) in NUMERIC_TYPES]
    x = _first_existing(columns, ["epoch", "step"])
    y = _first_existing(numeric, ["accuracy", "score", "f1", "loss", "latency", "duration"])
    group_by = _first_existing(columns, ["model", "method", "seed"])
    chart_type = "line" if x and y and x in numeric else "bar"

    if chart_type == "bar":
        x = _first_existing(columns, ["model", "method", "artifact_role", "source_file"]) or _first_non_numeric(columns, types)
        y = y or _first_existing(numeric, ["accuracy", "score", "f1", "loss", "latency", "duration"])
        group_by = None

    if not x or not y:
        return None

    figure_id = f"{chart_type}_{_slug(y)}_{'over' if chart_type == 'line' else 'by'}_{_slug(x)}"
    figure = {
        "figure_id": figure_id,
        "chart_type": chart_type,
        "title": f"{friendly_label(y)} {'over' if chart_type == 'line' else 'by'} {friendly_label(x)}",
        "x": x,
        "y": y,
        "output": {
            "png": f"figures/{figure_id}.png",
            "svg": f"figures/{figure_id}.svg",
        },
        "source_metrics": preview["path"],
        "numeric_claims": [],
    }
    if group_by:
        figure["group_by"] = group_by

    proposal = {
        "schema_version": "2.1",
        "proposal_type": "figure",
        "task_id": task_id,
        "worker_run_id": worker_run_id,
        "source_metrics": preview["path"],
        "source_metrics_fields": columns,
        "figures": [figure],
        "skipped_candidates": [],
        "confidence": 0.7,
        "rationale": "Selected a supported chart from bounded normalized-metrics columns, inferred types, and small row sample.",
    }
    path = worker_run_dir(root, task_id, worker_run_id) / "figure-proposal.yaml"
    write_yaml(path, proposal)
    return proposal


def _best_metric_preview(previews: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [preview for preview in previews if preview.get("type") in {"csv", "json"} and preview.get("columns")]
    scored = [(len(_metric_mappings(preview)), preview) for preview in candidates]
    scored = [item for item in scored if item[0] >= 2]
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _best_figure_preview(previews: list[dict[str, Any]]) -> dict[str, Any] | None:
    for preview in previews:
        if preview.get("path", "").endswith("metrics/normalized_metrics.csv") and preview.get("columns"):
            return preview
    return None


def _metric_mappings(preview: dict[str, Any]) -> list[dict[str, Any]]:
    columns = list(preview.get("columns") or [])
    types = preview.get("inferred_types") or {}
    used: set[str] = set()
    mappings: list[dict[str, Any]] = []

    for aliases in [PROCESS_ALIASES, GROUP_ALIASES, METRIC_ALIASES]:
        for column in columns:
            if column in used:
                continue
            target = _alias_target(column, aliases)
            if not target:
                continue
            if target in {"epoch", "step", "accuracy", "score", "f1", "loss", "latency", "duration"} and types.get(column) not in NUMERIC_TYPES:
                continue
            mappings.append({"target": target, "sources": [column]})
            used.add(column)

    return _dedupe_targets(mappings)


def _alias_target(column: str, aliases: dict[str, str]) -> str | None:
    normalized = _normalize(column)
    tokens = [token for token in normalized.replace("-", "_").split("_") if token]
    if normalized in aliases:
        return aliases[normalized]
    for token in tokens:
        if token in aliases:
            return aliases[token]
    return None


def _dedupe_targets(mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for mapping in mappings:
        target = mapping["target"]
        if target in seen:
            continue
        seen.add(target)
        result.append(mapping)
    return result


def _first_existing(columns: list[str], preferred: list[str]) -> str | None:
    for item in preferred:
        if item in columns:
            return item
    return None


def _first_non_numeric(columns: list[str], types: dict[str, str]) -> str | None:
    for column in columns:
        if types.get(column) != "number":
            return column
    return None


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_") or "figure"
