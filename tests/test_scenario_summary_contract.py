from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "task_id",
    "generated_at",
    "scenario_type",
    "primary_metric",
    "groups",
    "units",
    "omitted_unit_count",
    "best_rows",
    "last_rows",
    "seed_aggregates",
    "evidence",
    "omitted",
    "warnings",
}
OMITTED_CONTRACT = {
    "full_stdout",
    "full_stderr",
    "full_metric_rows",
    "report_body",
    "ppt_contents",
    "worker_prompt_response",
    "artifact_bytes",
}
FORBIDDEN_CLAIM_TEXT = (
    "statistically significant",
    "significant improvement",
    "superior",
    "winner",
    "causal",
    "caused",
    "deployment-ready",
    "ready for deployment",
)


def record(task_id: str = "task_contract") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        mode="ingest",
        status=TaskStatus.COMPLETED,
        created_at="2026-06-21T00:00:00+00:00",
        updated_at="2026-06-21T00:00:00+00:00",
        working_dir=".",
        source_path="results",
        paths=TaskPaths(task_dir=".lab-sidecar/tasks/task_contract", stdout="stdout.log", stderr="stderr.log"),
    )


def assert_scenario_summary_contract(summary: dict[str, Any]) -> None:
    assert REQUIRED_TOP_LEVEL_KEYS <= set(summary)
    assert summary["schema_version"] == "1"
    assert isinstance(summary["task_id"], str) and summary["task_id"]
    assert isinstance(summary["generated_at"], str) and summary["generated_at"]
    assert summary["scenario_type"] in {"training-run", "algorithm-benchmark"}

    primary_metric = summary["primary_metric"]
    assert set(primary_metric) == {"name", "direction", "unit", "selection_reason"}
    assert primary_metric["name"] is None or isinstance(primary_metric["name"], str)
    assert primary_metric["direction"] in {"max", "min", None}
    assert primary_metric["unit"] is None or _is_bounded_scalar(primary_metric["unit"])
    assert _is_bounded_scalar(primary_metric["selection_reason"])

    groups = summary["groups"]
    assert set(groups) == {"configured", "primary", "secondary", "seed", "context", "inferred"}
    assert isinstance(groups["configured"], dict)
    assert groups["primary"] is None or isinstance(groups["primary"], str)
    assert groups["secondary"] is None or isinstance(groups["secondary"], str)
    assert groups["seed"] is None or isinstance(groups["seed"], str)
    assert isinstance(groups["context"], list)
    assert isinstance(groups["inferred"], list)

    assert isinstance(summary["units"], dict)
    assert len(summary["units"]) <= MAX_UNITS
    assert isinstance(summary["omitted_unit_count"], int)
    assert summary["omitted_unit_count"] >= 0

    assert len(summary["best_rows"]) <= MAX_BEST_ROWS
    for row in summary["best_rows"]:
        _assert_best_row(row)

    assert len(summary["last_rows"]) <= MAX_LAST_ROWS
    for row in summary["last_rows"]:
        _assert_last_row(row)

    _assert_seed_aggregates(summary["seed_aggregates"])
    _assert_evidence(summary["evidence"])
    _assert_omitted_contract(summary["omitted"])

    assert isinstance(summary["warnings"], list)
    assert all(isinstance(warning, str) for warning in summary["warnings"])
    _assert_bounded_string_scalars(summary)


def _assert_best_row(row: dict[str, Any]) -> None:
    assert {"metric", "direction", "selection_reason", "value", "row_number", "selected_fields", "omitted_field_count", "evidence"} <= set(row)
    assert isinstance(row["metric"], str)
    assert row["direction"] in {"max", "min"}
    assert _is_bounded_scalar(row["selection_reason"])
    assert isinstance(row["value"], int | float)
    assert isinstance(row["row_number"], int)
    assert row["row_number"] >= 1
    _assert_selected_fields(row["selected_fields"])
    assert isinstance(row["omitted_field_count"], int)
    assert row["omitted_field_count"] >= 0
    _assert_row_evidence(row["evidence"], row["row_number"])


def _assert_last_row(row: dict[str, Any]) -> None:
    assert {"group", "row_number", "checkpoint_field", "selected_fields", "evidence"} <= set(row)
    assert isinstance(row["group"], dict)
    assert isinstance(row["row_number"], int)
    assert row["row_number"] >= 1
    assert row["checkpoint_field"] is None or isinstance(row["checkpoint_field"], str)
    _assert_selected_fields(row["selected_fields"])
    _assert_row_evidence(row["evidence"], row["row_number"])


def _assert_selected_fields(selected_fields: dict[str, Any]) -> None:
    assert isinstance(selected_fields, dict)
    assert len(selected_fields) <= MAX_SELECTED_FIELDS
    assert all(isinstance(key, str) for key in selected_fields)
    assert all(_is_bounded_scalar(value) for value in selected_fields.values())


def _assert_row_evidence(evidence: dict[str, Any], row_number: int) -> None:
    assert evidence == {
        "artifact_id": "metrics_normalized_csv",
        "path": "metrics/normalized_metrics.csv",
        "row_number": row_number,
        "body": "omitted",
    }


def _assert_seed_aggregates(seed_aggregates: dict[str, Any]) -> None:
    assert isinstance(seed_aggregates["present"], bool)
    if not seed_aggregates["present"]:
        assert isinstance(seed_aggregates["reason"], str)
        assert seed_aggregates["items"] == []
        return

    assert seed_aggregates["direction"] in {"max", "min"}
    assert isinstance(seed_aggregates["metric"], str)
    assert isinstance(seed_aggregates["group_by"], list)
    assert isinstance(seed_aggregates["seed_field"], str)
    assert seed_aggregates["aggregation_scope"] == "last_row_per_group_seed"
    assert len(seed_aggregates["items"]) <= MAX_SEED_AGGREGATES
    assert isinstance(seed_aggregates["omitted_group_count"], int)
    assert seed_aggregates["omitted_group_count"] >= 0
    assert seed_aggregates["claim_limit"] == "descriptive aggregate only; no statistical significance is inferred"

    for item in seed_aggregates["items"]:
        assert {"group", "metric", "direction", "row_count", "seed_count", "mean", "min", "max", "evidence"} <= set(item)
        assert isinstance(item["group"], dict)
        assert item["metric"] == seed_aggregates["metric"]
        assert item["direction"] == seed_aggregates["direction"]
        if "aggregation_scope" in item:
            assert item["aggregation_scope"] == "last_row_per_group_seed"
        assert isinstance(item["row_count"], int)
        assert item["row_count"] >= 1
        assert isinstance(item["seed_count"], int)
        assert item["seed_count"] >= 1
        assert isinstance(item["mean"], int | float)
        assert isinstance(item["min"], int | float)
        assert isinstance(item["max"], int | float)
        assert item["evidence"]["artifact_id"] == "metrics_normalized_csv"
        assert item["evidence"]["path"] == "metrics/normalized_metrics.csv"
        assert isinstance(item["evidence"]["row_numbers"], list)
        assert len(item["evidence"]["row_numbers"]) <= MAX_LAST_ROWS
        assert item["evidence"]["body"] == "omitted"


def _assert_evidence(evidence: dict[str, Any]) -> None:
    assert set(evidence) == {"metrics", "collection_summary", "source_files", "omitted_source_file_count"}
    metrics = evidence["metrics"]
    assert metrics["artifact_id"] == "metrics_normalized_csv"
    assert metrics["path"] == "metrics/normalized_metrics.csv"
    assert isinstance(metrics["row_count"], int)
    assert len(metrics["columns"]) <= MAX_COLUMNS
    assert isinstance(metrics["omitted_column_count"], int)
    assert metrics["omitted_column_count"] >= 0
    assert metrics["body"] == "omitted"

    collection_summary = evidence["collection_summary"]
    assert collection_summary["artifact_id"] == "metrics_collection_summary"
    assert collection_summary["path"] == "metrics/collection-summary.json"
    assert "candidate_count" in collection_summary
    assert isinstance(collection_summary["processed_file_count"], int)

    assert len(evidence["source_files"]) <= MAX_SOURCE_FILES
    assert isinstance(evidence["omitted_source_file_count"], int)
    assert evidence["omitted_source_file_count"] >= 0
    for source_file in evidence["source_files"]:
        assert {"source_file", "file_type", "row_count", "detected_fields", "omitted_detected_field_count", "mapped_fields", "omitted_mapped_field_count"} <= set(source_file)
        assert source_file["source_file"] is None or _is_bounded_scalar(source_file["source_file"])
        assert source_file["file_type"] is None or _is_bounded_scalar(source_file["file_type"])
        assert len(source_file["detected_fields"]) <= MAX_SOURCE_FIELDS
        assert len(source_file["mapped_fields"]) <= MAX_SOURCE_FIELDS
        assert isinstance(source_file["omitted_detected_field_count"], int)
        assert isinstance(source_file["omitted_mapped_field_count"], int)


def _assert_omitted_contract(omitted: dict[str, Any]) -> None:
    assert set(omitted) == OMITTED_CONTRACT
    assert all(value == "omitted_by_default" for value in omitted.values())


def _assert_bounded_string_scalars(value: Any) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _assert_bounded_string_scalars(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _assert_bounded_string_scalars(nested)
        return
    if isinstance(value, str):
        assert len(value) <= 160


def _is_bounded_scalar(value: Any) -> bool:
    if isinstance(value, str):
        return len(value) <= 160
    return value is None or isinstance(value, bool | int | float)


def _serialized(summary: dict[str, Any]) -> str:
    return json.dumps(summary, ensure_ascii=False).lower()


def _assert_no_forbidden_claim_language(summary: dict[str, Any]) -> None:
    serialized = _serialized(summary)
    for fragment in FORBIDDEN_CLAIM_TEXT:
        assert fragment not in serialized


def _extract_json_examples(markdown: str) -> list[dict[str, Any]]:
    blocks = re.findall(r"```json\n(.*?)\n```", markdown, flags=re.DOTALL)
    return [json.loads(block) for block in blocks]


def test_documented_scenario_summary_examples_parse_and_match_contract() -> None:
    markdown = (PROJECT_ROOT / "docs" / "experiment-scenario-summary-examples.md").read_text(encoding="utf-8")
    examples = _extract_json_examples(markdown)

    assert [example["scenario_type"] for example in examples] == ["training-run", "algorithm-benchmark"]
    for example in examples:
        assert_scenario_summary_contract(example)


def test_generated_training_run_summary_matches_public_contract() -> None:
    rows = [
        {"epoch": 1, "train_loss": 1.2, "val_loss": 1.0, "val_accuracy": 0.61},
        {"epoch": 2, "train_loss": 0.9, "val_loss": 0.8, "val_accuracy": 0.72},
        {"epoch": 3, "train_loss": 0.7, "val_loss": 0.6, "val_accuracy": 0.83},
    ]

    summary = build_scenario_summary(
        record=record("task_contract_training"),
        rows=rows,
        collection_summary={
            "candidate_count": 1,
            "processed_files": [
                {
                    "source_file": "results/metrics.csv",
                    "file_type": "csv",
                    "row_count": 3,
                    "detected_fields": ["epoch", "train_loss", "val_loss", "val_accuracy"],
                    "mapped_fields": [],
                }
            ],
        },
        units={"val_accuracy": "ratio"},
        configured_groups={},
    )

    assert summary["scenario_type"] == "training-run"
    assert summary["primary_metric"]["name"] == "val_accuracy"
    assert_scenario_summary_contract(summary)
    assert summary["omitted"]["full_metric_rows"] == "omitted_by_default"
    assert summary["evidence"]["metrics"]["body"] == "omitted"
    assert all(row["evidence"]["body"] == "omitted" for row in summary["best_rows"])
    assert all(row["evidence"]["body"] == "omitted" for row in summary["last_rows"])


def test_generated_algorithm_benchmark_seed_aggregates_are_contract_bounded_claims() -> None:
    rows = []
    for algorithm, runtimes in {
        "baseline": [55.2, 54.8, 56.1],
        "candidate": [41.7, 39.9, 40.8],
    }.items():
        for seed, runtime_ms in enumerate(runtimes, start=1):
            rows.append({"algorithm": algorithm, "seed": seed, "input_size": 100, "runtime_ms": runtime_ms, "memory_mb": 128 + seed})

    summary = build_scenario_summary(
        record=record("task_contract_benchmark"),
        rows=rows,
        collection_summary={
            "candidate_count": 1,
            "processed_files": [
                {
                    "source_file": "nested-results/results.json",
                    "file_type": "json",
                    "row_count": len(rows),
                    "detected_fields": ["algorithm", "seed", "input_size", "runtime_ms", "memory_mb"],
                    "mapped_fields": ["algorithm", "seed", "input_size", "runtime_ms", "memory_mb"],
                }
            ],
        },
        units={"runtime_ms": "ms", "memory_mb": "MB"},
        configured_groups={"primary": "algorithm", "secondary": "seed"},
    )

    assert summary["scenario_type"] == "algorithm-benchmark"
    assert summary["seed_aggregates"]["present"] is True
    assert summary["seed_aggregates"]["items"]
    assert_scenario_summary_contract(summary)
    assert summary["seed_aggregates"]["claim_limit"] == "descriptive aggregate only; no statistical significance is inferred"
    _assert_no_forbidden_claim_language(summary)


def test_missing_primary_metric_summary_is_valid_without_ranking_claims() -> None:
    summary = build_scenario_summary(
        record=record("task_contract_missing_primary"),
        rows=[
            {"method": "baseline", "epoch": 1, "measurement": "21.4", "private_comment": "SECRET-MISSING-PRIMARY"},
            {"method": "candidate", "epoch": 2, "measurement": "22.1", "private_comment": "SECRET-MISSING-PRIMARY"},
        ],
        collection_summary={
            "candidate_count": 1,
            "processed_files": [{"source_file": "results/ambient.csv", "file_type": "csv", "row_count": 2}],
        },
        units={"measurement": "celsius"},
        configured_groups={"primary": "method"},
    )

    assert_scenario_summary_contract(summary)
    assert summary["primary_metric"]["name"] is None
    assert summary["primary_metric"]["direction"] is None
    assert summary["best_rows"] == []
    assert summary["seed_aggregates"]["present"] is False
    assert any("primary metric was not detected" in warning for warning in summary["warnings"])
    _assert_no_forbidden_claim_language(summary)
    assert "secret-missing-primary" not in _serialized(summary)


def test_wide_free_text_summary_stays_bounded_without_copying_sensitive_values() -> None:
    free_text_values = {
        "notes": "SECRET-NOTES-" + "n" * 220,
        "prompt": "SECRET-PROMPT-" + "p" * 220,
        "message": "SECRET-MESSAGE-" + "m" * 220,
        "error_message": "SECRET-ERROR-MESSAGE-" + "e" * 220,
        "private_comment": "SECRET-PRIVATE-COMMENT-" + "c" * 220,
    }
    extra_columns = {f"extra_column_{index:02d}": index for index in range(80)}
    rows = [
        {
            "algorithm": f"algo_{index % 3}",
            "seed": index,
            "runtime_ms": 100 - index,
            **free_text_values,
            **extra_columns,
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
        for index in range(45)
    ]
    units = {f"unit_field_{index:02d}": "ratio" for index in range(60)}
    units["runtime_ms"] = "ms"

    summary = build_scenario_summary(
        record=record("task_contract_wide_free_text"),
        rows=rows,
        collection_summary={"candidate_count": len(processed_files), "processed_files": processed_files},
        units=units,
        configured_groups={"primary": "algorithm", "secondary": "seed"},
    )

    assert_scenario_summary_contract(summary)
    assert len(summary["evidence"]["metrics"]["columns"]) == MAX_COLUMNS
    assert len(summary["evidence"]["source_files"]) == MAX_SOURCE_FILES
    assert len(summary["evidence"]["source_files"][0]["detected_fields"]) == MAX_SOURCE_FIELDS
    assert len(summary["evidence"]["source_files"][0]["mapped_fields"]) == MAX_SOURCE_FIELDS
    assert len(summary["units"]) == MAX_UNITS
    assert len(summary["best_rows"]) <= MAX_BEST_ROWS
    assert len(summary["last_rows"]) <= MAX_LAST_ROWS
    assert len(summary["seed_aggregates"]["items"]) <= MAX_SEED_AGGREGATES

    serialized = _serialized(summary)
    for value in free_text_values.values():
        assert value.lower() not in serialized
        assert value[:24].lower() not in serialized
    for row in [*summary["best_rows"], *summary["last_rows"]]:
        assert not ({"notes", "prompt", "message", "error_message", "private_comment"} & set(row["selected_fields"]))
