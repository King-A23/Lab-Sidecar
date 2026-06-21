from __future__ import annotations

import json
from pathlib import Path

from lab_sidecar.collectors.scenario_summary import build_scenario_summary
from lab_sidecar.core.models import TaskPaths, TaskRecord, TaskStatus


def record(task_id: str = "task_test") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        mode="ingest",
        status=TaskStatus.COMPLETED,
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
        working_dir=".",
        source_path="results",
        paths=TaskPaths(task_dir=".lab-sidecar/tasks/task_test", stdout="stdout.log", stderr="stderr.log"),
    )


def test_training_run_scenario_summary_is_bounded() -> None:
    rows = [
        {"epoch": 1, "train_loss": 1.2, "val_loss": 1.0, "val_accuracy": 0.61, "notes": "x" * 300},
        {"epoch": 2, "train_loss": 0.9, "val_loss": 0.8, "val_accuracy": 0.72, "notes": "x" * 300},
        {"epoch": 3, "train_loss": 0.7, "val_loss": 0.6, "val_accuracy": 0.83, "notes": "x" * 300},
    ]

    summary = build_scenario_summary(
        record=record(),
        rows=rows,
        collection_summary={"processed_files": [{"source_file": "results/metrics.csv", "file_type": "csv", "row_count": 3}]},
        units={"val_accuracy": "ratio"},
        configured_groups={},
    )
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["scenario_type"] == "training-run"
    assert summary["primary_metric"]["name"] == "val_accuracy"
    assert summary["best_rows"][0]["row_number"] == 3
    assert summary["last_rows"][0]["checkpoint_field"] == "epoch"
    assert summary["omitted"]["full_metric_rows"] == "omitted_by_default"
    assert "xxx" in serialized
    assert "x" * 300 not in serialized
    assert "statistical significance" in " ".join(summary["warnings"])


def test_algorithm_benchmark_seed_aggregates_are_descriptive() -> None:
    rows = []
    for method, base in [("baseline", 0.70), ("candidate", 0.80)]:
        for seed in [1, 2, 3]:
            rows.append({"method": method, "seed": seed, "epoch": 1, "accuracy": base + seed / 100})
            rows.append({"method": method, "seed": seed, "epoch": 2, "accuracy": base + 0.05 + seed / 100})

    summary = build_scenario_summary(
        record=record(),
        rows=rows,
        collection_summary={"processed_files": [{"source_file": "results/multiseed.csv", "file_type": "csv", "row_count": 12}]},
        units={"accuracy": "ratio"},
        configured_groups={"primary": "method", "secondary": "seed"},
    )

    assert summary["scenario_type"] == "algorithm-benchmark"
    assert summary["groups"]["primary"] == "method"
    assert summary["groups"]["seed"] == "seed"
    assert summary["seed_aggregates"]["present"] is True
    assert summary["seed_aggregates"]["metric"] == "accuracy"
    assert summary["seed_aggregates"]["items"][0]["group"]["method"] == "candidate"
    assert summary["seed_aggregates"]["items"][0]["seed_count"] == 3
    assert summary["seed_aggregates"]["claim_limit"] == "descriptive aggregate only; no statistical significance is inferred"

