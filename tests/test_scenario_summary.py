from __future__ import annotations

from pathlib import Path

import pytest

from lab_sidecar.collectors.scenario_summary import (
    MAX_BEST_ROWS,
    MAX_COLUMNS,
    MAX_LAST_ROWS,
    MAX_SEED_AGGREGATES,
    MAX_SELECTED_FIELDS,
    MAX_SOURCE_FIELDS,
    MAX_SOURCE_FILES,
    MAX_UNITS,
    build_scenario_summary,
)
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
    private_note = "PRIVATE-NOTES-" + "x" * 300
    rows = [
        {"epoch": 1, "train_loss": 1.2, "val_loss": 1.0, "val_accuracy": 0.61, "notes": private_note},
        {"epoch": 2, "train_loss": 0.9, "val_loss": 0.8, "val_accuracy": 0.72, "notes": private_note},
        {"epoch": 3, "train_loss": 0.7, "val_loss": 0.6, "val_accuracy": 0.83, "notes": private_note},
    ]

    summary = build_scenario_summary(
        record=record(),
        rows=rows,
        collection_summary={"processed_files": [{"source_file": "results/metrics.csv", "file_type": "csv", "row_count": 3}]},
        units={"val_accuracy": "ratio"},
        configured_groups={},
    )
    serialized = repr(summary)

    assert summary["scenario_type"] == "training-run"
    assert summary["primary_metric"]["name"] == "val_accuracy"
    assert summary["best_rows"][0]["row_number"] == 3
    assert summary["last_rows"][0]["checkpoint_field"] == "epoch"
    assert summary["omitted"]["full_metric_rows"] == "omitted_by_default"
    assert private_note not in serialized
    assert "PRIVATE-NOTES-" not in serialized
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


def test_wide_scenario_summary_records_omitted_counts_instead_of_dumping_fields() -> None:
    extra_columns = [f"extra_column_{index:02d}" for index in range(80)]
    rows = [
        {
            "algorithm": f"algo_{index % 3}",
            "seed": index,
            "epoch": index,
            "accuracy": 0.7 + index / 100,
            **{column: index for column in extra_columns},
        }
        for index in range(18)
    ]
    source_fields = [f"raw_field_{index:02d}" for index in range(75)]
    processed_files = [
        {
            "source_file": f"results/file_{index:02d}.csv",
            "file_type": "csv",
            "row_count": 1,
            "detected_fields": source_fields,
            "mapped_fields": source_fields,
        }
        for index in range(25)
    ]
    units = {f"unit_field_{index:02d}": "ratio" for index in range(60)}
    units["accuracy"] = "ratio"

    summary = build_scenario_summary(
        record=record(),
        rows=rows,
        collection_summary={"candidate_count": 25, "processed_files": processed_files},
        units=units,
        configured_groups={"primary": "algorithm", "secondary": "seed"},
    )

    assert len(summary["evidence"]["metrics"]["columns"]) == MAX_COLUMNS
    assert summary["evidence"]["metrics"]["omitted_column_count"] == len(rows[0]) - MAX_COLUMNS
    assert len(summary["evidence"]["source_files"]) == MAX_SOURCE_FILES
    assert summary["evidence"]["omitted_source_file_count"] == 25 - MAX_SOURCE_FILES
    assert len(summary["evidence"]["source_files"][0]["detected_fields"]) == MAX_SOURCE_FIELDS
    assert summary["evidence"]["source_files"][0]["omitted_detected_field_count"] == len(source_fields) - MAX_SOURCE_FIELDS
    assert len(summary["evidence"]["source_files"][0]["mapped_fields"]) == MAX_SOURCE_FIELDS
    assert summary["evidence"]["source_files"][0]["omitted_mapped_field_count"] == len(source_fields) - MAX_SOURCE_FIELDS
    assert len(summary["units"]) == MAX_UNITS
    assert summary["omitted_unit_count"] == len(units) - MAX_UNITS
    assert len(summary["best_rows"]) <= MAX_BEST_ROWS
    assert len(summary["last_rows"]) <= MAX_LAST_ROWS
    assert len(summary["seed_aggregates"]["items"]) <= MAX_SEED_AGGREGATES
    assert all(len(item["selected_fields"]) <= MAX_SELECTED_FIELDS for item in summary["best_rows"])
    assert all(len(item["selected_fields"]) <= MAX_SELECTED_FIELDS for item in summary["last_rows"])


@pytest.mark.parametrize("field_name", ["notes", "prompt", "error_message", "private_comment"])
def test_selected_fields_do_not_copy_free_text_columns(field_name: str) -> None:
    secret_text = f"SECRET-FREE-TEXT-{field_name}-" + "z" * 240
    rows = [
        {"variant": "baseline", "epoch": 1, "accuracy": 0.70, field_name: secret_text},
        {"variant": "candidate", "epoch": 2, "accuracy": 0.91, field_name: secret_text},
    ]

    summary = build_scenario_summary(
        record=record(),
        rows=rows,
        collection_summary={"processed_files": [{"source_file": "results/metrics.csv", "file_type": "csv", "row_count": 2}]},
        units={"accuracy": "ratio"},
        configured_groups={"primary": "variant"},
    )
    serialized = repr(summary)

    assert secret_text not in serialized
    assert f"SECRET-FREE-TEXT-{field_name}" not in serialized
    assert field_name not in summary["best_rows"][0]["selected_fields"]
    assert field_name not in summary["last_rows"][0]["selected_fields"]


def test_algorithm_benchmark_summary_stays_descriptive_without_significance_or_superiority_claims() -> None:
    rows = []
    for method, base in [("baseline", 0.70), ("candidate", 0.85)]:
        for seed in range(20):
            rows.append({"method": method, "seed": seed, "accuracy": base + seed / 1000})

    summary = build_scenario_summary(
        record=record(),
        rows=rows,
        collection_summary={"processed_files": [{"source_file": "results/benchmark.csv", "file_type": "csv", "row_count": 40}]},
        units={"accuracy": "ratio"},
        configured_groups={"primary": "method", "secondary": "seed"},
    )
    serialized = repr(summary).lower()

    assert summary["scenario_type"] == "algorithm-benchmark"
    assert summary["seed_aggregates"]["claim_limit"] == "descriptive aggregate only; no statistical significance is inferred"
    assert "statistically significant" not in serialized
    assert "significant improvement" not in serialized
    assert "superior" not in serialized
    assert "causal" not in serialized
    assert "deployment-ready" not in serialized
