from __future__ import annotations

import json
from pathlib import Path

from tests.test_cli_smoke import (
    assert_non_empty_file,
    assert_readable_deck,
    copy_examples,
    extract_task_id,
    invoke,
    read_csv_rows,
)


def _task_path(workspace: Path, task_id: str) -> Path:
    return workspace / ".lab-sidecar" / "tasks" / task_id


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_messy_csv_checked_in_fixture_runs_package_ready_path(tmp_path: Path) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/messy-csv-results"]).output)

    collect = invoke(workspace, ["collect", task_id, "--config", "examples/messy-csv-results/metrics.yaml"])

    assert collect.exit_code == 0, collect.output
    task_path = _task_path(workspace, task_id)
    rows = read_csv_rows(task_path / "metrics" / "normalized_metrics.csv")
    summary = _read_json(task_path / "metrics" / "collection-summary.json")
    scenario = _read_json(task_path / "metrics" / "scenario-summary.json")

    assert len(rows) == 12
    assert summary["candidate_count"] == 5
    assert summary["source_selection"]["mode"] == "config"
    assert summary["source_selection"]["explicit_sources"] is True
    skipped = {(Path(item["source_file"]).name, item["reason"]) for item in summary["skipped_files"]}
    assert ("debug_metrics.csv", "configured_source_excluded") in skipped
    assert ("scratch.csv", "configured_source_excluded") in skipped
    assert ("readme.txt", "unsupported_configured_source") in skipped
    assert ("partial.csv", "missing_configured_field") in skipped
    assert summary["matched_source_fields"]["accuracy"] == ["val_accuracy", "acc", "score_pct"]
    assert summary["matched_source_fields"]["latency_ms"] == ["runtime_ms", "latency_ms", "time_ms", "runtime_s"]
    assert any(item["reason"] == "mixed_source_units" for item in summary["unit_diagnostics"])
    assert summary["bounded_analysis"]["anomaly_summary"]["present"] is True
    assert scenario["scenario_type"] == "algorithm-benchmark"
    assert scenario["seed_aggregates"]["claim_limit"] == "descriptive aggregate only; no statistical significance is inferred"

    for command in [["figures", task_id], ["report", task_id], ["slides", task_id]]:
        result = invoke(workspace, command)
        assert result.exit_code == 0, result.output

    figure_summary = _read_json(task_path / "figures" / "figure-summary.json")
    assert figure_summary["figure_count"] >= 1
    assert all(item["source"] == "deterministic" for item in figure_summary["generated_figures"])
    assert_non_empty_file(task_path / "reports" / "report-fragment.md")
    assert_readable_deck(task_path / "slides" / "presentation-draft.pptx")

    validate = invoke(workspace, ["validate", task_id, "--require", "package-ready"])
    assert validate.exit_code == 0, validate.output
    package_path = workspace / f"lab-sidecar-package-{task_id}"
    package = invoke(workspace, ["package", task_id, "--output", package_path.as_posix()])
    assert package.exit_code == 0, package.output
    verify = invoke(workspace, ["package-verify", package_path.as_posix()])
    assert verify.exit_code == 0, verify.output
    assert not (package_path / "raw" / "source_refs.json").exists()
    assert not (package_path / "stdout.log").exists()
    assert not (package_path / "stderr.log").exists()
    assert not (package_path / "examples").exists()


def test_json_benchmark_checked_in_fixture_runs_validate_path(tmp_path: Path) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/json-benchmark-results"]).output)

    collect = invoke(workspace, ["collect", task_id, "--config", "examples/json-benchmark-results/metrics.yaml"])

    assert collect.exit_code == 0, collect.output
    task_path = _task_path(workspace, task_id)
    rows = read_csv_rows(task_path / "metrics" / "normalized_metrics.csv")
    summary = _read_json(task_path / "metrics" / "collection-summary.json")
    scenario = _read_json(task_path / "metrics" / "scenario-summary.json")

    assert len(rows) == 7
    assert {row["method"] for row in rows} == {"linear_baseline", "tree_candidate", "nearest_neighbor"}
    assert summary["candidate_count"] == 2
    assert summary["source_selection"]["selected_count"] == 2
    assert summary["source_selection"]["skipped_counts_by_reason"] == [
        {"reason": "configured_source_excluded", "count": 1}
    ]
    assert any("Skipped non-object items in JSON list" in warning for warning in summary["warnings"])
    assert set(summary["matched_source_fields"]["accuracy"]) == {"metrics_accuracy", "accuracy"}
    assert set(summary["matched_source_fields"]["runtime_ms"]) == {"metrics_runtime_ms", "runtime_ms"}
    assert summary["bounded_analysis"]["anomaly_summary"]["present"] is True
    assert scenario["scenario_type"] == "algorithm-benchmark"
    assert scenario["primary_metric"]["name"] == "accuracy"

    for command in [["figures", task_id], ["report", task_id], ["slides", task_id], ["validate", task_id]]:
        result = invoke(workspace, command)
        assert result.exit_code == 0, result.output

    figure_summary = _read_json(task_path / "figures" / "figure-summary.json")
    assert figure_summary["generated_figures"][0]["chart_type"] == "box"
    slides_summary = _read_json(task_path / "slides" / "slides-summary.json")
    assert slides_summary["qa_checks"]["empty_slide_check"]["passed"] is True
    assert "statistical significance" in scenario["seed_aggregates"]["claim_limit"]
