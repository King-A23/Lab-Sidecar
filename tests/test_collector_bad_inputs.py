from __future__ import annotations

import json
import sys
from pathlib import Path

from lab_sidecar.collectors.scenario_summary import MAX_COLUMNS
from tests.test_cli_smoke import extract_task_id, invoke, read_csv_rows


def _task_path(workspace: Path, task_id: str) -> Path:
    return workspace / ".lab-sidecar" / "tasks" / task_id


def _summary(workspace: Path, task_id: str) -> dict:
    return json.loads((_task_path(workspace, task_id) / "metrics" / "collection-summary.json").read_text(encoding="utf-8"))


def test_bad_csv_json_empty_csv_and_missing_metric_columns_are_diagnostic_only(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "bad-inputs"
    source.mkdir()
    (source / "bad.csv").write_text('epoch,accuracy\n1,"unterminated\n', encoding="utf-8")
    (source / "bad.json").write_text('{"epoch": 1, "accuracy": ', encoding="utf-8")
    (source / "empty.csv").write_text("", encoding="utf-8")
    (source / "missing_metric_columns.csv").write_text(
        "name,notes\nalpha,SECRET-FREE-TEXT should not be copied\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "bad-inputs"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 5
    assert "CSV/JSON candidates were found, but no metrics could be collected" in result.output
    summary = _summary(tmp_path, task_id)
    assert summary["candidate_count"] == 4
    assert summary["row_count"] == 0
    assert summary["output_files"] == []
    skipped = {(Path(item["source_file"]).name, item["reason"]) for item in summary["skipped_files"]}
    assert ("bad.csv", "parse_failed") in skipped
    assert ("bad.json", "parse_failed") in skipped
    assert ("empty.csv", "no_detected_metrics") in skipped
    assert ("missing_metric_columns.csv", "no_detected_metrics") in skipped
    diagnostic_reasons = {item["reason"] for item in summary["diagnostics"]}
    assert "parse_failed" in diagnostic_reasons
    assert "no_detected_metrics" in diagnostic_reasons
    no_metric_messages = [
        item["message"]
        for item in summary["diagnostics"]
        if item["reason"] == "no_detected_metrics"
    ]
    assert any("empty or has no readable header" in message for message in no_metric_messages)
    assert any("fields seen: name, notes" in message for message in no_metric_messages)
    assert any("collect --config fields" in message for message in no_metric_messages)
    serialized = json.dumps(summary, ensure_ascii=False)
    assert '1,"unterminated' not in serialized
    assert '{"epoch": 1, "accuracy":' not in serialized
    assert "SECRET-FREE-TEXT" not in serialized
    task_path = _task_path(tmp_path, task_id)
    assert not (task_path / "metrics" / "normalized_metrics.csv").exists()
    assert not (task_path / "metrics" / "normalized_metrics.json").exists()
    assert not (task_path / "metrics" / "scenario-summary.json").exists()


def test_missing_configured_field_records_diagnostic_without_outputs(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "configured-results"
    source.mkdir()
    (source / "run.csv").write_text("iter,algo,score_pct\n1,baseline,0.70\n", encoding="utf-8")
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "configured-results"]).output)
    (tmp_path / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - configured-results/run.csv",
                "fields:",
                "  epoch: iter",
                "  method: algo",
                "  accuracy: score_pct",
                "  seed: missing_seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["collect", task_id, "--config", "metrics.yaml"])

    assert result.exit_code == 5
    assert "missing_seed" in result.output
    summary = _summary(tmp_path, task_id)
    assert summary["candidate_count"] == 1
    assert summary["row_count"] == 0
    assert summary["skipped_files"][0]["reason"] == "missing_configured_field"
    assert summary["diagnostics"][0]["reason"] == "missing_configured_field"
    assert "missing_seed" in summary["warnings"][0]
    task_path = _task_path(tmp_path, task_id)
    assert not (task_path / "metrics" / "normalized_metrics.csv").exists()
    assert not (task_path / "metrics" / "scenario-summary.json").exists()


def test_no_detected_metrics_diagnostic_bounds_long_field_names(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "long-field-results"
    source.mkdir()
    long_field = "private_column_" + "x" * 240
    (source / "notes.csv").write_text(
        f"{long_field},label\nsecret value,baseline\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "long-field-results"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 5
    summary = _summary(tmp_path, task_id)
    serialized = json.dumps(summary, ensure_ascii=False)
    assert long_field not in serialized
    diagnostic = next(item for item in summary["diagnostics"] if item["reason"] == "no_detected_metrics")
    assert "private_column_" in diagnostic["message"]
    assert "..." in diagnostic["message"]
    assert "secret value" not in serialized


def test_include_exclude_globs_record_skips_and_unit_conflict_without_conversion(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "mixed-results"
    (source / "runs").mkdir(parents=True)
    (source / "debug").mkdir(parents=True)
    (source / "scratch").mkdir(parents=True)
    (source / "runs" / "run_ms.csv").write_text(
        "iter,algo,trial,score_pct,runtime_ms\n1,baseline,1,0.70,25\n",
        encoding="utf-8",
    )
    (source / "runs" / "run_s.csv").write_text(
        "iter,algo,trial,score_pct,runtime_s\n1,candidate,1,0.80,0.02\n",
        encoding="utf-8",
    )
    (source / "direct.csv").write_text(
        "iter,algo,trial,score_pct,runtime_ms\n1,direct,1,0.75,30\n",
        encoding="utf-8",
    )
    (source / "debug" / "debug_metrics.csv").write_text(
        "iter,algo,trial,score_pct,runtime_ms\n1,debug,0,0.01,999\n",
        encoding="utf-8",
    )
    (source / "scratch" / "scratch.csv").write_text(
        "iter,algo,trial,score_pct,runtime_ms\n1,scratch,0,0.02,999\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "mixed-results"]).output)
    (tmp_path / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  include:",
                "    - mixed-results/**/*.csv",
                "  exclude:",
                "    - mixed-results/debug/*.csv",
                "    - mixed-results/scratch/*",
                "fields:",
                "  epoch: iter",
                "  method: algo",
                "  seed: trial",
                "  accuracy: score_pct",
                "  latency_ms:",
                "    sources: [runtime_ms, runtime_s]",
                "    unit: ms",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["collect", task_id, "--config", "metrics.yaml"])

    assert result.exit_code == 0
    task_path = _task_path(tmp_path, task_id)
    rows = read_csv_rows(task_path / "metrics" / "normalized_metrics.csv")
    assert {Path(row["source_file"]).name for row in rows} == {"direct.csv", "run_ms.csv", "run_s.csv"}
    assert any(row["method"] == "candidate" and row["latency_ms"] == "0.02" for row in rows)
    summary = _summary(tmp_path, task_id)
    assert summary["candidate_count"] == 3
    skipped = {(Path(item["source_file"]).name, item["reason"]) for item in summary["skipped_files"]}
    assert ("debug_metrics.csv", "configured_source_excluded") in skipped
    assert ("scratch.csv", "configured_source_excluded") in skipped
    assert summary["units"] == {"latency_ms": "ms"}
    assert summary["matched_source_fields"]["latency_ms"] == ["runtime_ms", "runtime_s"]
    assert summary["unit_diagnostics"]
    assert summary["unit_diagnostics"][0]["reason"] == "mixed_source_units"
    assert "runtime_ms=ms" in summary["unit_diagnostics"][0]["message"]
    assert "runtime_s=s" in summary["unit_diagnostics"][0]["message"]


def test_configured_unit_self_conflict_is_recorded_as_diagnostic(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "unit-config-conflict"
    source.mkdir()
    (source / "run.csv").write_text(
        "iter,algo,trial,runtime_ms\n1,baseline,1,25\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "unit-config-conflict"]).output)
    (tmp_path / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - unit-config-conflict/run.csv",
                "fields:",
                "  epoch: iter",
                "  method: algo",
                "  seed: trial",
                "  latency_ms:",
                "    source: runtime_ms",
                "    unit: ms",
                "units:",
                "  latency_ms: s",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["collect", task_id, "--config", "metrics.yaml"])

    assert result.exit_code == 0
    summary = _summary(tmp_path, task_id)
    assert summary["units"] == {"latency_ms": "ms"}
    assert any(item["reason"] == "configured_unit_conflict" for item in summary["diagnostics"])
    assert any("field mapping declares 'ms' but units declares 's'" in warning for warning in summary["warnings"])


def test_wide_table_and_free_text_do_not_leak_into_scenario_selected_fields(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "wide-results"
    source.mkdir()
    extra_columns = [f"extra_{index:02d}" for index in range(70)]
    header = ["epoch", "variant", "accuracy", "prompt", *extra_columns]
    rows = [
        ["1", "baseline", "0.70", "SECRET-COLLECTOR-PROMPT baseline", *["1" for _ in extra_columns]],
        ["2", "candidate", "0.91", "SECRET-COLLECTOR-PROMPT candidate", *["2" for _ in extra_columns]],
    ]
    (source / "wide.csv").write_text(
        ",".join(header) + "\n" + "\n".join(",".join(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "wide-results"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 0
    collection_summary = _summary(tmp_path, task_id)
    collection_serialized = json.dumps(collection_summary, ensure_ascii=False)
    assert "SECRET-COLLECTOR-PROMPT" not in collection_serialized
    assert all(
        "prompt" not in item["selected_fields"]
        for item in collection_summary["bounded_analysis"]["best_rows"]
    )
    scenario = json.loads((_task_path(tmp_path, task_id) / "metrics" / "scenario-summary.json").read_text(encoding="utf-8"))
    assert len(scenario["evidence"]["metrics"]["columns"]) == MAX_COLUMNS
    assert scenario["evidence"]["metrics"]["omitted_column_count"] == len(header) + 1 - MAX_COLUMNS
    serialized = json.dumps(scenario, ensure_ascii=False)
    assert "SECRET-COLLECTOR-PROMPT" not in serialized
    assert "prompt" not in scenario["best_rows"][0]["selected_fields"]
    assert "prompt" not in scenario["last_rows"][0]["selected_fields"]


def test_run_collect_does_not_recursively_scan_workspace_by_default(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    (tmp_path / "make_nested_metrics.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "Path('nested').mkdir(exist_ok=True)",
                "Path('nested/metrics.csv').write_text('epoch,accuracy\\n1,0.9\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    command = f'"{sys.executable}" make_nested_metrics.py'
    run_result = invoke(tmp_path, ["run", command])
    assert run_result.exit_code == 0
    task_id = extract_task_id(run_result.output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 5
    assert "no CSV/JSON metric candidates were found" in result.output
    summary = _summary(tmp_path, task_id)
    assert summary["candidate_count"] == 0
    assert summary["candidates"] == []
    assert (tmp_path / "nested" / "metrics.csv").is_file()
