from __future__ import annotations

import csv
import json
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.intelligence import delegate_experiment_artifacts
from lab_sidecar.intelligence.adoption import adopt_proposal
from lab_sidecar.intelligence.paths import create_worker_run_dirs, worker_run_dir
from lab_sidecar.intelligence.validator import validate_proposal
from lab_sidecar.runner.service import RunnerService


def write_nonstandard_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["iter", "variant", "acc", "err"])
        writer.writeheader()
        writer.writerows(
            [
                {"iter": 1, "variant": "baseline", "acc": 0.62, "err": 0.9},
                {"iter": 2, "variant": "baseline", "acc": 0.68, "err": 0.72},
                {"iter": 1, "variant": "candidate", "acc": 0.66, "err": 0.82},
                {"iter": 2, "variant": "candidate", "acc": 0.75, "err": 0.61},
            ]
        )


def test_nonstandard_csv_heuristic_metrics_proposal_adopts_official_metrics(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Collect non-standard experiment metrics.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)
    normalized = tmp_path / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv"
    rows = list(csv.DictReader(normalized.open(newline="", encoding="utf-8")))
    adoption = json.loads((run_dir / "adoption-record.json").read_text(encoding="utf-8"))
    validator = json.loads((run_dir / "validator-result.json").read_text(encoding="utf-8"))

    assert "heuristic_proposal_rejected" not in result["risk_flags"]
    assert "intelligent_worker_unavailable" not in result["risk_flags"]
    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert (run_dir / "metrics-proposal.yaml").is_file()
    assert (run_dir / "adopted-metrics-config.yaml").is_file()
    assert validator["accepted"] is True
    assert rows
    assert {"epoch", "model", "accuracy", "loss"}.issubset(rows[0])
    assert adoption["adoptions"][0]["proposal_type"] == "metrics"
    assert "metrics/normalized_metrics.csv" in "\n".join(adoption["adoptions"][0]["official_artifacts"])


def test_valid_figure_proposal_adopts_official_figures_and_summary(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Collect metrics and generate a comparison figure.",
        result_path=source,
        desired_outputs=["figures"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)
    adoption = json.loads((run_dir / "adoption-record.json").read_text(encoding="utf-8"))
    official = "\n".join(path for adoption_item in adoption["adoptions"] for path in adoption_item["official_artifacts"])

    assert "heuristic_proposal_rejected" not in result["risk_flags"]
    assert "intelligent_worker_unavailable" not in result["risk_flags"]
    assert (run_dir / "figure-proposal.yaml").is_file()
    assert (run_dir / "adopted-figure-spec.yaml").is_file()
    assert (task_path / "figures" / "figure-summary.json").is_file()
    assert list((task_path / "figures").glob("*.png"))
    assert list((task_path / "figures").glob("*.svg"))
    assert ".png" in official
    assert ".svg" in official


def test_missing_field_figure_proposal_rejected_without_official_figures(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)
    record = RunnerService(tmp_path).ingest_source(source)
    worker_run_id = "worker_run_missing_field"
    create_worker_run_dirs(tmp_path, record.task_id, worker_run_id)
    source_metrics = f".lab-sidecar/tasks/{record.task_id}/metrics/normalized_metrics.csv"

    bundle = {
        "schema_version": "2.1",
        "task_id": record.task_id,
        "worker_run_id": worker_run_id,
        "data_previews": [
            {
                "path": source_metrics,
                "type": "csv",
                "columns": ["epoch", "accuracy"],
                "inferred_types": {"epoch": "number", "accuracy": "number"},
                "descriptive_stats": {"epoch": {"count": 2}, "accuracy": {"count": 2}},
            }
        ],
        "candidate_previews": [],
        "artifacts": [],
    }
    run_dir = worker_run_dir(tmp_path, record.task_id, worker_run_id)
    (run_dir / "input-bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    proposal = {
        "schema_version": "2.1",
        "proposal_type": "figure",
        "task_id": record.task_id,
        "worker_run_id": worker_run_id,
        "source_metrics": source_metrics,
        "source_metrics_fields": ["epoch", "accuracy"],
        "figures": [
            {
                "figure_id": "bad_missing",
                "chart_type": "line",
                "title": "Bad Missing Field",
                "x": "epoch",
                "y": "does_not_exist",
                "output": {"png": "figures/bad_missing.png", "svg": "figures/bad_missing.svg"},
            }
        ],
    }

    validation = validate_proposal(tmp_path, record.task_id, worker_run_id, proposal)
    adopted = adopt_proposal(tmp_path, record.task_id, worker_run_id, proposal, validation)

    diagnostics = "\n".join(validation.diagnostics)
    task_path = tmp_path / ".lab-sidecar" / "tasks" / record.task_id
    assert validation.accepted is False
    assert adopted is None
    assert "missing field: does_not_exist" in diagnostics
    assert not (run_dir / "adoption-record.json").exists()
    assert not list((task_path / "figures").glob("*.png"))
    assert not (task_path / "figures" / "bad_missing.png").exists()


def test_validator_uses_bundle_fields_not_proposal_declared_fields(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)
    record = RunnerService(tmp_path).ingest_source(source)
    worker_run_id = "worker_run_field_bypass"
    create_worker_run_dirs(tmp_path, record.task_id, worker_run_id)
    source_metrics = f".lab-sidecar/tasks/{record.task_id}/metrics/normalized_metrics.csv"
    run_dir = worker_run_dir(tmp_path, record.task_id, worker_run_id)
    (run_dir / "input-bundle.json").write_text(
        json.dumps(
            {
                "schema_version": "2.1",
                "task_id": record.task_id,
                "worker_run_id": worker_run_id,
                "data_previews": [
                    {
                        "path": source_metrics,
                        "type": "csv",
                        "columns": ["epoch", "accuracy"],
                        "inferred_types": {"epoch": "number", "accuracy": "number"},
                        "descriptive_stats": {"epoch": {"count": 2}, "accuracy": {"count": 2}},
                    }
                ],
                "candidate_previews": [],
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    validation = validate_proposal(
        tmp_path,
        record.task_id,
        worker_run_id,
        {
            "schema_version": "2.1",
            "proposal_type": "figure",
            "task_id": record.task_id,
            "worker_run_id": worker_run_id,
            "source_metrics": source_metrics,
            "source_metrics_fields": ["epoch", "accuracy", "forged_metric"],
            "figures": [
                {
                    "figure_id": "forged",
                    "chart_type": "line",
                    "title": "Forged Metric",
                    "x": "epoch",
                    "y": "forged_metric",
                    "output": {"png": "figures/forged.png", "svg": "figures/forged.svg"},
                }
            ],
        },
    )

    assert validation.accepted is False
    assert "missing field: forged_metric" in "\n".join(validation.diagnostics)


def test_heuristic_mode_requires_no_ai_provider_configuration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="No AI provider should be required.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
    )

    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert result["risk_flags"] == ["ai_provider_unavailable"]


def test_intelligent_mode_off_preserves_v1_fallback_for_rejected_or_disabled_planning(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Do not use heuristic planning.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )

    task_path = tmp_path / ".lab-sidecar" / "tasks" / result["task_id"]
    assert result["risk_flags"] == ["intelligent_mode_off"]
    assert "intelligence" not in result["summary"]
    assert not (task_path / "intelligence").exists()
    assert not (task_path / "metrics" / "normalized_metrics.csv").exists()
