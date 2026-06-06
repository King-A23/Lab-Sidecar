from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.service import MetricsCollectionService
from lab_sidecar.core.paths import to_manifest_path
from lab_sidecar.figures.service import FigureGenerationService
from lab_sidecar.intelligence.heuristic_worker import write_yaml
from lab_sidecar.intelligence.paths import worker_run_dir
from lab_sidecar.intelligence.schemas import ValidatorResult
from lab_sidecar.intelligence.validator import write_validator_outputs


def adopt_proposal(
    root: Path,
    task_id: str,
    worker_run_id: str,
    proposal: dict[str, Any],
    validation: ValidatorResult,
) -> dict[str, Any] | None:
    if not validation.accepted:
        return None

    proposal_type = proposal.get("proposal_type")
    if proposal_type == "metrics":
        return _adopt_metrics(root, task_id, worker_run_id, proposal, validation)
    if proposal_type == "figure":
        return _adopt_figure(root, task_id, worker_run_id, proposal, validation)
    return None


def _adopt_metrics(
    root: Path,
    task_id: str,
    worker_run_id: str,
    proposal: dict[str, Any],
    validation: ValidatorResult,
) -> dict[str, Any]:
    config = _metrics_config_from_proposal(proposal)
    run_dir = worker_run_dir(root, task_id, worker_run_id)
    config_path = run_dir / "adopted-metrics-config.yaml"
    write_yaml(config_path, config)
    result = MetricsCollectionService(root).collect(task_id, config_path=config_path)
    record = _write_adoption_record(
        root=root,
        task_id=task_id,
        worker_run_id=worker_run_id,
        proposal_type="metrics",
        proposal_path=run_dir / "metrics-proposal.yaml",
        adopted_config_path=config_path,
        official_artifacts=[result.csv_path, result.json_path, result.summary_path],
    )
    validation.adopted_config_path = to_manifest_path(config_path, root)
    write_validator_outputs(root, task_id, worker_run_id, validation)
    return record


def _adopt_figure(
    root: Path,
    task_id: str,
    worker_run_id: str,
    proposal: dict[str, Any],
    validation: ValidatorResult,
) -> dict[str, Any]:
    config = _figure_spec_from_proposal(proposal)
    run_dir = worker_run_dir(root, task_id, worker_run_id)
    spec_path = run_dir / "adopted-figure-spec.yaml"
    write_yaml(spec_path, config)
    result = FigureGenerationService(root).generate(task_id, spec_path=spec_path)
    official_artifacts: list[Path] = [result.spec_path, result.summary_path]
    for figure in result.generated:
        official_artifacts.extend([figure.png_path, figure.svg_path])
    record = _write_adoption_record(
        root=root,
        task_id=task_id,
        worker_run_id=worker_run_id,
        proposal_type="figure",
        proposal_path=run_dir / "figure-proposal.yaml",
        adopted_config_path=spec_path,
        official_artifacts=official_artifacts,
    )
    validation.adopted_config_path = to_manifest_path(spec_path, root)
    write_validator_outputs(root, task_id, worker_run_id, validation)
    return record


def _metrics_config_from_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "sources": [
            source["path"]
            for source in proposal.get("source_files", [])
            if isinstance(source, dict) and isinstance(source.get("path"), str)
        ],
        "fields": {
            mapping["target"]: {"sources": mapping["sources"]}
            for mapping in proposal.get("field_mappings", [])
            if isinstance(mapping, dict)
            and isinstance(mapping.get("target"), str)
            and isinstance(mapping.get("sources"), list)
        },
    }


def _figure_spec_from_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    figures = [figure for figure in proposal.get("figures", []) if isinstance(figure, dict)]
    if not figures:
        raise ValueError("accepted figure proposal did not include a figure")
    figure = figures[0]
    spec = {
        "schema_version": "1",
        "figure_id": figure["figure_id"],
        "chart_type": figure["chart_type"],
        "title": figure["title"],
        "x": figure["x"],
        "y": figure["y"],
        "output": figure.get("output"),
    }
    if figure.get("group_by"):
        spec["group_by"] = figure["group_by"]
    return spec


def _write_adoption_record(
    root: Path,
    task_id: str,
    worker_run_id: str,
    proposal_type: str,
    proposal_path: Path,
    adopted_config_path: Path,
    official_artifacts: list[Path],
) -> dict[str, Any]:
    path = worker_run_dir(root, task_id, worker_run_id) / "adoption-record.json"
    record = {
        "proposal_type": proposal_type,
        "adopted_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "proposal_path": to_manifest_path(proposal_path, root),
        "adopted_config_path": to_manifest_path(adopted_config_path, root),
        "official_artifacts": [to_manifest_path(path, root) for path in official_artifacts],
    }
    envelope = {
        "schema_version": "2.1",
        "task_id": task_id,
        "worker_run_id": worker_run_id,
        "adoptions": [],
    }
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = None
        if isinstance(existing, dict) and isinstance(existing.get("adoptions"), list):
            envelope["adoptions"] = existing["adoptions"]
    envelope["adoptions"].append(record)
    path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return envelope
