from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.service import (
    MAX_BOUNDED_ANOMALY_GROUPS,
    MAX_BOUNDED_BEST_ROWS,
    MAX_BOUNDED_SELECTED_FIELDS,
    MAX_BOUNDED_STRING_CHARS,
)
from tests.test_cli_smoke import (
    copy_examples,
    extract_task_id,
    invoke,
    read_csv_rows,
    write_stage3_messy_results,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "task_id",
    "task_status",
    "collected_at",
    "candidate_count",
    "candidates",
    "processed_files",
    "skipped_files",
    "warnings",
    "diagnostics",
    "unit_diagnostics",
    "row_count",
    "detected_fields",
    "bounded_analysis",
    "output_files",
}
OPTIONAL_TOP_LEVEL_KEYS = {
    "config_path",
    "config",
    "units",
    "groups",
    "matched_source_fields",
}
TASK_STATUS_VALUES = {"pending", "running", "completed", "failed", "cancelled"}
ALLOWED_SKIPPED_KEYS = {"source_file", "reason", "message"}
ALLOWED_DIAGNOSTIC_KEYS = {"source_file", "reason", "message", "field", "source_fields"}


def read_collection_summary(workspace: Path, task_id: str) -> dict[str, Any]:
    path = workspace / ".lab-sidecar" / "tasks" / task_id / "metrics" / "collection-summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_collection_summary_contract(
    summary: dict[str, Any],
    *,
    expected_task_id: str,
) -> None:
    assert REQUIRED_TOP_LEVEL_KEYS <= set(summary)
    assert summary["schema_version"] == "1"
    assert summary["task_id"] == expected_task_id
    assert summary["task_status"] in TASK_STATUS_VALUES
    assert isinstance(summary["collected_at"], str) and summary["collected_at"]

    candidate_count = summary["candidate_count"]
    assert isinstance(candidate_count, int)
    assert candidate_count >= 0
    assert len(summary["candidates"]) == candidate_count
    for candidate in summary["candidates"]:
        _assert_candidate_entry(candidate)

    processed_files = summary["processed_files"]
    assert isinstance(processed_files, list)
    for item in processed_files:
        _assert_processed_file_entry(item)

    skipped_files = summary["skipped_files"]
    assert isinstance(skipped_files, list)
    for item in skipped_files:
        _assert_skipped_file_entry(item)

    warnings = summary["warnings"]
    assert isinstance(warnings, list)
    assert all(isinstance(warning, str) and warning and "\n" not in warning for warning in warnings)

    diagnostics = summary["diagnostics"]
    assert isinstance(diagnostics, list)
    for item in diagnostics:
        _assert_diagnostic_entry(item)

    unit_diagnostics = summary["unit_diagnostics"]
    assert isinstance(unit_diagnostics, list)
    for item in unit_diagnostics:
        _assert_diagnostic_entry(item)
        assert isinstance(item.get("field"), str) and item["field"]

    row_count = summary["row_count"]
    assert isinstance(row_count, int)
    assert row_count >= 0
    assert row_count == sum(item["row_count"] for item in processed_files)

    detected_fields = summary["detected_fields"]
    assert isinstance(detected_fields, list)
    assert all(isinstance(field, str) and field for field in detected_fields)
    assert len(detected_fields) == len(set(detected_fields))
    expected_detected_fields = {
        field_name
        for item in processed_files
        for field_name in item["detected_fields"]
    }
    assert set(detected_fields) == expected_detected_fields

    _assert_optional_fields(summary, processed_files)
    _assert_output_files(summary["output_files"], row_count, expected_task_id=expected_task_id)
    _assert_bounded_analysis(summary["bounded_analysis"], row_count)


def _assert_candidate_entry(candidate: dict[str, Any]) -> None:
    assert set(candidate) == {"source_file", "origin", "suffix", "source_provenance"}
    assert isinstance(candidate["source_file"], str) and candidate["source_file"] and "\n" not in candidate["source_file"]
    assert isinstance(candidate["origin"], str) and candidate["origin"]
    assert candidate["suffix"] in {".csv", ".json"}
    _assert_source_provenance(candidate["source_provenance"])


def _assert_processed_file_entry(item: dict[str, Any]) -> None:
    assert set(item) == {
        "source_file",
        "file_type",
        "row_count",
        "source_provenance",
        "detected_fields",
        "mapped_fields",
        "matched_source_fields",
    }
    assert isinstance(item["source_file"], str) and item["source_file"] and "\n" not in item["source_file"]
    assert item["file_type"] in {"csv", "json"}
    assert isinstance(item["row_count"], int)
    assert item["row_count"] >= 1
    _assert_source_provenance(item["source_provenance"])
    assert isinstance(item["detected_fields"], list)
    assert all(isinstance(field, str) and field for field in item["detected_fields"])
    assert len(item["detected_fields"]) == len(set(item["detected_fields"]))
    assert isinstance(item["mapped_fields"], list)
    assert all(isinstance(field, str) and field for field in item["mapped_fields"])
    assert set(item["mapped_fields"]).issubset(set(item["detected_fields"]))
    _assert_matched_source_fields(item["matched_source_fields"])


def _assert_source_provenance(provenance: dict[str, Any]) -> None:
    assert isinstance(provenance, dict)
    if not provenance:
        return
    assert set(provenance) == {"size_bytes", "sha256"}
    assert isinstance(provenance["size_bytes"], int)
    assert provenance["size_bytes"] >= 0
    assert isinstance(provenance["sha256"], str) and provenance["sha256"]


def _assert_skipped_file_entry(item: dict[str, Any]) -> None:
    assert {"source_file", "reason"} <= set(item)
    assert set(item) <= ALLOWED_SKIPPED_KEYS
    assert "body" not in item
    assert "rows" not in item
    assert isinstance(item["source_file"], str) and item["source_file"] and "\n" not in item["source_file"]
    assert isinstance(item["reason"], str) and item["reason"] and "\n" not in item["reason"]
    if "message" in item:
        assert isinstance(item["message"], str) and item["message"] and "\n" not in item["message"]


def _assert_diagnostic_entry(item: dict[str, Any]) -> None:
    assert isinstance(item, dict)
    assert "reason" in item
    assert set(item) <= ALLOWED_DIAGNOSTIC_KEYS
    assert "body" not in item
    assert "rows" not in item
    assert isinstance(item["reason"], str) and item["reason"] and "\n" not in item["reason"]
    if "source_file" in item:
        assert isinstance(item["source_file"], str) and item["source_file"] and "\n" not in item["source_file"]
    if "field" in item:
        assert isinstance(item["field"], str) and item["field"] and "\n" not in item["field"]
    if "source_fields" in item:
        assert isinstance(item["source_fields"], str) and item["source_fields"] and "\n" not in item["source_fields"]
    if "message" in item:
        assert isinstance(item["message"], str) and item["message"] and "\n" not in item["message"]


def _assert_optional_fields(
    summary: dict[str, Any],
    processed_files: list[dict[str, Any]],
) -> None:
    assert set(summary) >= OPTIONAL_TOP_LEVEL_KEYS

    config_path = summary["config_path"]
    config = summary["config"]
    if config is None:
        assert config_path is None
    else:
        assert isinstance(config_path, str) and config_path and "\n" not in config_path
        assert isinstance(config, dict)
        assert {"sources", "field_mappings", "units"} <= set(config)
        assert isinstance(config["sources"], list)
        assert isinstance(config["field_mappings"], list)
        assert isinstance(config["units"], dict)
        if "exclude_sources" in config:
            assert isinstance(config["exclude_sources"], list)
        if "groups" in config:
            assert isinstance(config["groups"], dict)
        if "diagnostics" in config:
            assert isinstance(config["diagnostics"], list)
            for item in config["diagnostics"]:
                _assert_diagnostic_entry(item)

    units = summary["units"]
    assert isinstance(units, dict)
    assert all(isinstance(field, str) and field for field in units)
    assert all(isinstance(unit, str) and unit for unit in units.values())

    groups = summary["groups"]
    assert isinstance(groups, dict)
    assert all(isinstance(field, str) and field for field in groups)
    assert all(isinstance(group, str) and group for group in groups.values())

    matched_source_fields = summary["matched_source_fields"]
    _assert_matched_source_fields(matched_source_fields)
    assert matched_source_fields == _merge_matched_source_fields(processed_files)


def _assert_matched_source_fields(value: dict[str, list[str]]) -> None:
    assert isinstance(value, dict)
    for field_name, source_fields in value.items():
        assert isinstance(field_name, str) and field_name
        assert isinstance(source_fields, list)
        assert all(isinstance(source_field, str) and source_field for source_field in source_fields)
        assert len(source_fields) == len(set(source_fields))


def _merge_matched_source_fields(processed_files: list[dict[str, Any]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for item in processed_files:
        for target, source_fields in item["matched_source_fields"].items():
            merged.setdefault(target, [])
            for source_field in source_fields:
                if source_field not in merged[target]:
                    merged[target].append(source_field)
    return merged


def _assert_output_files(output_files: list[str], row_count: int, *, expected_task_id: str) -> None:
    assert isinstance(output_files, list)
    if row_count > 0:
        assert output_files == [
            f".lab-sidecar/tasks/{expected_task_id}/metrics/normalized_metrics.csv",
            f".lab-sidecar/tasks/{expected_task_id}/metrics/normalized_metrics.json",
        ]
        return
    assert output_files == []


def _assert_bounded_analysis(bounded: dict[str, Any], row_count: int) -> None:
    assert set(bounded) == {
        "schema_version",
        "row_count",
        "limits",
        "best_rows",
        "checkpoint_summary",
        "anomaly_summary",
    }
    assert bounded["schema_version"] == "1"
    assert bounded["row_count"] == row_count
    assert bounded["limits"] == {
        "best_rows": MAX_BOUNDED_BEST_ROWS,
        "selected_fields_per_row": MAX_BOUNDED_SELECTED_FIELDS,
        "anomaly_groups": MAX_BOUNDED_ANOMALY_GROUPS,
        "string_chars": MAX_BOUNDED_STRING_CHARS,
    }

    best_rows = bounded["best_rows"]
    assert isinstance(best_rows, list)
    assert len(best_rows) <= MAX_BOUNDED_BEST_ROWS
    for row in best_rows:
        _assert_best_row(row)

    _assert_checkpoint_summary(bounded["checkpoint_summary"])
    _assert_anomaly_summary(bounded["anomaly_summary"])


def _assert_best_row(row: dict[str, Any]) -> None:
    assert set(row) == {
        "metric",
        "direction",
        "value",
        "row_number",
        "selected_fields",
        "omitted_field_count",
        "evidence",
    }
    assert isinstance(row["metric"], str) and row["metric"]
    assert row["direction"] in {"max", "min"}
    assert isinstance(row["value"], int | float)
    assert isinstance(row["row_number"], int) and row["row_number"] >= 1
    _assert_selected_fields(row["selected_fields"])
    assert isinstance(row["omitted_field_count"], int)
    assert row["omitted_field_count"] >= 0
    _assert_row_evidence(row["evidence"], row["row_number"])


def _assert_selected_fields(selected_fields: dict[str, Any]) -> None:
    assert isinstance(selected_fields, dict)
    assert len(selected_fields) <= MAX_BOUNDED_SELECTED_FIELDS
    assert all(isinstance(field, str) and field for field in selected_fields)
    for value in selected_fields.values():
        if isinstance(value, str):
            assert len(value) <= MAX_BOUNDED_STRING_CHARS
        else:
            assert value is None or isinstance(value, bool | int | float)


def _assert_row_evidence(evidence: dict[str, Any], row_number: int) -> None:
    assert evidence == {
        "artifact_id": "metrics_normalized_csv",
        "path": "metrics/normalized_metrics.csv",
        "row_number": row_number,
        "body": "omitted",
    }


def _assert_checkpoint_summary(checkpoint: dict[str, Any]) -> None:
    assert isinstance(checkpoint, dict)
    assert isinstance(checkpoint["present"], bool)
    if not checkpoint["present"]:
        assert isinstance(checkpoint["reason"], str) and checkpoint["reason"]
        if "checkpoint_fields" in checkpoint:
            assert isinstance(checkpoint["checkpoint_fields"], list)
            assert isinstance(checkpoint["available_checkpoint_count"], int)
        return

    assert isinstance(checkpoint["checkpoint_fields"], list)
    assert all(isinstance(field, str) and field for field in checkpoint["checkpoint_fields"])
    assert isinstance(checkpoint["available_checkpoint_count"], int)
    assert checkpoint["available_checkpoint_count"] >= 1
    assert isinstance(checkpoint["unique_checkpoint_count"], int)
    assert checkpoint["unique_checkpoint_count"] >= 1
    assert isinstance(checkpoint["omitted_checkpoint_count"], int)
    assert checkpoint["omitted_checkpoint_count"] >= 0

    selected = checkpoint["selected"]
    assert isinstance(selected, dict)
    assert {
        "checkpoint_field",
        "checkpoint",
        "selection_metric",
        "selection_direction",
        "selection_value",
        "row_number",
        "selected_fields",
        "evidence",
    } <= set(selected)
    assert isinstance(selected["checkpoint_field"], str) and selected["checkpoint_field"]
    assert selected["selection_metric"] is None or isinstance(selected["selection_metric"], str)
    assert isinstance(selected["selection_direction"], str) and selected["selection_direction"]
    assert selected["selection_value"] is None or isinstance(selected["selection_value"], int | float)
    assert isinstance(selected["row_number"], int) and selected["row_number"] >= 1
    _assert_selected_fields(selected["selected_fields"])
    _assert_row_evidence(selected["evidence"], selected["row_number"])


def _assert_anomaly_summary(anomaly: dict[str, Any]) -> None:
    assert isinstance(anomaly, dict)
    assert isinstance(anomaly["present"], bool)
    assert isinstance(anomaly["anomaly_row_count"], int)
    assert anomaly["anomaly_row_count"] >= 0
    assert isinstance(anomaly["anomaly_group_count"], int)
    assert anomaly["anomaly_group_count"] >= 0
    assert isinstance(anomaly["counts_by_reason"], list)
    for item in anomaly["counts_by_reason"]:
        assert set(item) == {"reason", "row_count"}
        assert isinstance(item["reason"], str) and item["reason"]
        assert isinstance(item["row_count"], int) and item["row_count"] >= 1
    assert isinstance(anomaly["examples"], list)
    assert len(anomaly["examples"]) <= MAX_BOUNDED_ANOMALY_GROUPS
    if "omitted_group_count" in anomaly:
        assert isinstance(anomaly["omitted_group_count"], int)
        assert anomaly["omitted_group_count"] >= 0
    for example in anomaly["examples"]:
        assert {
            "reasons",
            "row_count",
            "first_row_number",
            "last_row_number",
            "selected_fields",
            "evidence",
        } <= set(example)
        assert isinstance(example["reasons"], list)
        assert all(isinstance(reason, str) and reason for reason in example["reasons"])
        assert isinstance(example["row_count"], int) and example["row_count"] >= 1
        assert isinstance(example["first_row_number"], int) and example["first_row_number"] >= 1
        assert isinstance(example["last_row_number"], int)
        assert example["last_row_number"] >= example["first_row_number"]
        _assert_selected_fields(example["selected_fields"])
        assert example["evidence"] == {
            "artifact_id": "metrics_normalized_csv",
            "path": "metrics/normalized_metrics.csv",
            "body": "omitted",
        }


def test_generated_csv_collection_summary_matches_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/csv-comparison"]).output)

    result = invoke(workspace, ["collect", task_id])

    assert result.exit_code == 0
    rows = read_csv_rows(
        workspace / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv"
    )
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["candidate_count"] == 3
    assert summary["row_count"] == len(rows)
    assert {Path(item["source_file"]).name for item in summary["processed_files"]} == {
        "baseline.csv",
        "model_a.csv",
        "model_b.csv",
    }


def test_generated_json_collection_summary_matches_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/algorithm-benchmark/results.json"]).output)

    result = invoke(workspace, ["collect", task_id])

    assert result.exit_code == 0
    rows = read_csv_rows(
        workspace / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv"
    )
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["candidate_count"] == 1
    assert summary["row_count"] == len(rows)
    assert summary["processed_files"][0]["file_type"] == "json"
    assert {"algorithm", "seed", "runtime_ms", "memory_mb"}.issubset(summary["detected_fields"])


def test_explicit_config_collection_summary_records_units_groups_and_matched_fields(tmp_path: Path) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    write_stage3_messy_results(workspace)
    task_id = extract_task_id(invoke(workspace, ["ingest", "messy-results"]).output)
    (workspace / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  include:",
                "    - messy-results/**/*.csv",
                "  exclude:",
                "    - messy-results/debug/*.csv",
                "    - messy-results/scratch/*",
                "fields:",
                "  epoch:",
                "    sources: [epoch, step, iter]",
                "  method:",
                "    sources: [model, method, algo, variant]",
                "  seed:",
                "    sources: [seed, trial, run_id]",
                "  accuracy:",
                "    sources: [val_accuracy, score_pct, acc]",
                "    unit: ratio",
                "  latency_ms:",
                "    sources: [runtime_ms, latency_ms, time_ms]",
                "    unit: ms",
                "groups:",
                "  primary: method",
                "  secondary: seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(workspace, ["collect", task_id, "--config", "metrics.yaml"])

    assert result.exit_code == 0
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["config_path"] == "metrics.yaml"
    assert summary["candidate_count"] == 6
    assert summary["units"] == {"accuracy": "ratio", "latency_ms": "ms"}
    assert summary["groups"] == {"primary": "method", "secondary": "seed"}
    assert summary["matched_source_fields"] == {
        "epoch": ["iter"],
        "method": ["algo"],
        "seed": ["trial"],
        "accuracy": ["score_pct"],
        "latency_ms": ["runtime_ms"],
    }
    skipped = {(Path(item["source_file"]).name, item["reason"]) for item in summary["skipped_files"]}
    assert ("debug_metrics.csv", "configured_source_excluded") in skipped
    assert ("scratch.csv", "configured_source_excluded") in skipped


def test_no_candidate_collection_summary_matches_contract_without_outputs(tmp_path: Path) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "notes-only"
    source.mkdir()
    (source / "notes.txt").write_text("no metrics here\n", encoding="utf-8")
    task_id = extract_task_id(invoke(workspace, ["ingest", "notes-only"]).output)

    result = invoke(workspace, ["collect", task_id])

    assert result.exit_code == 5
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["candidate_count"] == 0
    assert summary["candidates"] == []
    assert summary["processed_files"] == []
    assert summary["skipped_files"] == []
    assert summary["diagnostics"] == []
    assert summary["unit_diagnostics"] == []


def test_bad_and_empty_input_collection_summary_matches_contract_without_outputs(tmp_path: Path) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "bad-inputs"
    source.mkdir()
    (source / "bad.json").write_text('{"epoch": 1, "accuracy": ', encoding="utf-8")
    (source / "empty.csv").write_text("", encoding="utf-8")
    (source / "missing_metric_columns.csv").write_text(
        "name,notes\nalpha,no metric columns\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(workspace, ["ingest", "bad-inputs"]).output)

    result = invoke(workspace, ["collect", task_id])

    assert result.exit_code == 5
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["candidate_count"] == 3
    assert summary["row_count"] == 0
    skipped = {(Path(item["source_file"]).name, item["reason"]) for item in summary["skipped_files"]}
    assert ("bad.json", "parse_failed") in skipped
    assert ("empty.csv", "no_detected_metrics") in skipped
    assert ("missing_metric_columns.csv", "no_detected_metrics") in skipped

    serialized = json.dumps(summary, ensure_ascii=False)
    assert '{"epoch": 1, "accuracy": ' not in serialized
    assert "alpha,no metric columns" not in serialized
    task_path = workspace / ".lab-sidecar" / "tasks" / task_id
    assert not (task_path / "metrics" / "normalized_metrics.csv").exists()
    assert not (task_path / "metrics" / "normalized_metrics.json").exists()


def test_missing_configured_field_collection_summary_matches_contract_without_outputs(tmp_path: Path) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "configured-results"
    source.mkdir()
    (source / "run_a.csv").write_text("iter,algo,score_pct\n1,baseline,0.70\n", encoding="utf-8")
    task_id = extract_task_id(invoke(workspace, ["ingest", "configured-results"]).output)
    (workspace / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - configured-results/run_a.csv",
                "fields:",
                "  epoch: iter",
                "  accuracy: score_pct",
                "  method: algo",
                "  seed: missing_seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(workspace, ["collect", task_id, "--config", "metrics.yaml"])

    assert result.exit_code == 5
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["config_path"] == "metrics.yaml"
    assert summary["candidate_count"] == 1
    assert summary["row_count"] == 0
    assert summary["skipped_files"][0]["reason"] == "missing_configured_field"
    assert summary["diagnostics"][0]["reason"] == "missing_configured_field"
    assert any("missing_seed" in warning for warning in summary["warnings"])


def test_mixed_unit_collection_summary_matches_contract_and_records_diagnostics(tmp_path: Path) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "unit-results"
    source.mkdir()
    (source / "run_a.csv").write_text("iter,algo,trial,runtime_ms\n1,baseline,1,25\n", encoding="utf-8")
    (source / "run_b.csv").write_text("iter,algo,trial,runtime_s\n1,candidate,1,0.02\n", encoding="utf-8")
    task_id = extract_task_id(invoke(workspace, ["ingest", "unit-results"]).output)
    (workspace / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - unit-results/*.csv",
                "fields:",
                "  epoch: iter",
                "  method: algo",
                "  seed: trial",
                "  latency_ms:",
                "    sources: [runtime_ms, runtime_s]",
                "    unit: ms",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(workspace, ["collect", task_id, "--config", "metrics.yaml"])

    assert result.exit_code == 0
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    assert summary["units"] == {"latency_ms": "ms"}
    assert summary["matched_source_fields"]["latency_ms"] == ["runtime_ms", "runtime_s"]
    assert summary["unit_diagnostics"]
    assert summary["unit_diagnostics"][0]["reason"] == "mixed_source_units"
    assert "runtime_ms=ms" in summary["unit_diagnostics"][0]["message"]
    assert "runtime_s=s" in summary["unit_diagnostics"][0]["message"]


def test_bounded_analysis_collection_summary_matches_contract_for_checkpoint_and_anomalies(tmp_path: Path) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "sweep-results"
    source.mkdir()
    (source / "metrics.csv").write_text(
        "\n".join(
            [
                "variant,run_id,config_id,seed,epoch,step,val_accuracy,val_loss,checkpoint,status,error_flag,warning_flag,incomplete_flag,unstable_flag,artifact_present,anomaly_code",
                "baseline,run_001,cfg_00,11,1,100,0.700,0.620,,ok,0,0,0,0,true,none",
                "candidate,run_002,cfg_01,13,1,100,0.820,0.440,checkpoints/run_002/step_100.pt,ok,0,0,0,0,true,none",
                "candidate,run_002,cfg_01,13,2,200,0.910,0.280,checkpoints/run_002/final.pt,ok,0,0,0,0,true,none",
                "broken,run_003,cfg_02,17,1,100,0.510,0.910,,missing_final_metric,1,0,1,0,false,missing_final_metric",
                "broken,run_003,cfg_02,17,2,200,0.500,0.940,,missing_final_metric,1,0,1,0,false,missing_final_metric",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(workspace, ["ingest", "sweep-results"]).output)

    result = invoke(workspace, ["collect", task_id])

    assert result.exit_code == 0
    summary = read_collection_summary(workspace, task_id)

    assert_collection_summary_contract(summary, expected_task_id=task_id)
    bounded = summary["bounded_analysis"]
    best_accuracy = next(item for item in bounded["best_rows"] if item["metric"] == "val_accuracy")
    assert best_accuracy["evidence"]["body"] == "omitted"
    assert bounded["checkpoint_summary"]["present"] is True
    assert bounded["checkpoint_summary"]["selected"]["evidence"]["body"] == "omitted"
    assert bounded["anomaly_summary"]["present"] is True
    assert bounded["anomaly_summary"]["examples"][0]["evidence"]["body"] == "omitted"
