from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lab_sidecar.core.paths import to_manifest_path
from lab_sidecar.figures.specs import friendly_label
from lab_sidecar.intelligence.paths import worker_run_dir
from lab_sidecar.intelligence.worker_invocation import WorkerRequest, WorkerResult, load_worker_input_bundle


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


class HeuristicWorker:
    worker_type = "heuristic"

    def __init__(
        self,
        root: Path,
        initial_warnings: list[str] | None = None,
        initial_risk_flags: list[str] | None = None,
    ) -> None:
        self.root = root
        self.initial_warnings = initial_warnings or []
        self.initial_risk_flags = initial_risk_flags or []

    def run(self, request: WorkerRequest) -> WorkerResult:
        bundle = load_worker_input_bundle(self.root, request)
        proposals: list[dict[str, Any]] = []
        desired_outputs = request.desired_outputs

        metrics_proposal = None
        if "metrics" in desired_outputs or any(output in desired_outputs for output in ["figures", "report", "slides"]):
            metrics_proposal = propose_metrics(self.root, request.task_id, request.worker_run_id, bundle)
            if metrics_proposal:
                proposals.append(metrics_proposal)

        if "figures" in desired_outputs or "slides" in desired_outputs:
            figure_proposal = propose_figure(self.root, request.task_id, request.worker_run_id, bundle)
            if figure_proposal is None and metrics_proposal is not None:
                figure_proposal = propose_figure_from_metrics_proposal(
                    self.root,
                    request.task_id,
                    request.worker_run_id,
                    metrics_proposal,
                )
            if figure_proposal:
                proposals.append(figure_proposal)

        if not proposals:
            return WorkerResult(
                task_id=request.task_id,
                worker_run_id=request.worker_run_id,
                worker_type=self.worker_type,
                status="unavailable",
                summary={"headline": "Heuristic worker produced no proposal from the bounded input bundle."},
                diagnostics=["heuristic_worker_unavailable: bounded previews did not contain enough usable fields."],
                risk_flags=[*self.initial_risk_flags, "intelligent_worker_unavailable"],
                warnings=[*self.initial_warnings],
            )

        proposal_paths = [_proposal_path(self.root, request.task_id, request.worker_run_id, proposal) for proposal in proposals]
        return WorkerResult(
            task_id=request.task_id,
            worker_run_id=request.worker_run_id,
            worker_type=self.worker_type,
            status="accepted",
            proposal=proposals[0],
            proposals=proposals,
            proposal_path=proposal_paths[0] if proposal_paths else None,
            proposal_paths=proposal_paths,
            summary={
                "headline": "Heuristic worker produced proposal(s) from bounded task context.",
                "proposal_count": len(proposals),
                "proposal_types": [proposal.get("proposal_type", "unknown") for proposal in proposals],
            },
            risk_flags=[*self.initial_risk_flags],
            warnings=[*self.initial_warnings],
        )


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

    return _figure_proposal_from_preview(
        root=root,
        task_id=task_id,
        worker_run_id=worker_run_id,
        preview=preview,
        rationale="Selected a supported chart from bounded normalized-metrics columns, inferred types, and small row sample.",
    )


def propose_figure_from_metrics_proposal(
    root: Path,
    task_id: str,
    worker_run_id: str,
    metrics_proposal: dict[str, Any],
) -> dict[str, Any] | None:
    columns = [
        mapping["target"]
        for mapping in metrics_proposal.get("field_mappings", [])
        if isinstance(mapping, dict) and isinstance(mapping.get("target"), str)
    ]
    if not columns:
        return None
    source_metrics = f".lab-sidecar/tasks/{task_id}/metrics/normalized_metrics.csv"
    preview = {
        "path": source_metrics,
        "type": "csv",
        "columns": columns,
        "inferred_types": {
            column: "number"
            for column in columns
            if column in {"epoch", "step", "accuracy", "score", "f1", "loss", "latency", "duration"}
        },
        "descriptive_stats": {
            column: {"source": "metrics_proposal_mapping"}
            for column in columns
            if column in {"epoch", "step", "accuracy", "score", "f1", "loss", "latency", "duration"}
        },
    }
    return _figure_proposal_from_preview(
        root=root,
        task_id=task_id,
        worker_run_id=worker_run_id,
        preview=preview,
        rationale="Selected a supported chart from a proposed normalized metrics mapping; validation re-checks the generated metrics bundle before adoption.",
    )


def _figure_proposal_from_preview(
    root: Path,
    task_id: str,
    worker_run_id: str,
    preview: dict[str, Any],
    rationale: str,
) -> dict[str, Any] | None:
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
        "rationale": rationale,
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


def _proposal_path(root: Path, task_id: str, worker_run_id: str, proposal: dict[str, Any]) -> str:
    proposal_type = proposal.get("proposal_type")
    filename = "metrics-proposal.yaml" if proposal_type == "metrics" else "figure-proposal.yaml"
    return to_manifest_path(worker_run_dir(root, task_id, worker_run_id) / filename, root)
