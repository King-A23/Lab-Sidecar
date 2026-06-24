from __future__ import annotations

import json
from pathlib import Path

import yaml

from tests.test_cli_smoke import assert_non_empty_file, extract_task_id, invoke


def _prepare_metrics_task(workspace: Path) -> tuple[str, Path]:
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "figure-results"
    source.mkdir()
    (source / "metrics.csv").write_text(
        "\n".join(
            [
                "epoch,method,seed,accuracy,runtime_ms,loss",
                "1,baseline,1,0.70,52,0.62",
                "2,baseline,1,0.75,48,0.56",
                "1,baseline,2,0.72,50,0.60",
                "2,baseline,2,0.78,46,0.53",
                "1,candidate,1,0.82,40,0.48",
                "2,candidate,1,0.88,35,0.39",
                "1,candidate,2,0.80,42,0.49",
                "2,candidate,2,0.90,34,0.37",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(workspace, ["ingest", "figure-results"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    return task_id, workspace / ".lab-sidecar" / "tasks" / task_id


def _figure_summary(task_path: Path) -> dict:
    return json.loads((task_path / "figures" / "figure-summary.json").read_text(encoding="utf-8"))


def test_legacy_single_explicit_spec_still_generates(tmp_path: Path) -> None:
    task_id, task_path = _prepare_metrics_task(tmp_path)
    (tmp_path / "single.yaml").write_text(
        "\n".join(
            [
                "figure_id: accuracy_line",
                "chart_type: line",
                "title: Accuracy over Epoch",
                "x: epoch",
                "y: accuracy",
                "group_by: method",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["figures", task_id, "--spec", "single.yaml"])

    assert result.exit_code == 0
    assert_non_empty_file(task_path / "figures" / "accuracy_line.png")
    assert_non_empty_file(task_path / "figures" / "accuracy_line.svg")
    summary = _figure_summary(task_path)
    assert summary["figure_count"] == 1
    assert summary["generated_figures"][0]["figure_id"] == "accuracy_line"
    assert summary["errors"] == []


def test_multi_explicit_spec_generates_line_bar_and_box(tmp_path: Path) -> None:
    task_id, task_path = _prepare_metrics_task(tmp_path)
    (tmp_path / "multi.yaml").write_text(
        "\n".join(
            [
                "figures:",
                "  - figure_id: accuracy_line",
                "    chart_type: line",
                "    title: Accuracy over Epoch",
                "    x: epoch",
                "    y: accuracy",
                "    group_by: method",
                "  - figure_id: runtime_bar",
                "    chart_type: bar",
                "    title: Runtime by Method",
                "    x: method",
                "    y: runtime_ms",
                "  - figure_id: accuracy_box",
                "    chart_type: box",
                "    title: Accuracy Distribution by Method",
                "    x: method",
                "    y: accuracy",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["figures", task_id, "--spec", "multi.yaml"])

    assert result.exit_code == 0
    figures_dir = task_path / "figures"
    for figure_id in ["accuracy_line", "runtime_bar", "accuracy_box"]:
        assert_non_empty_file(figures_dir / f"{figure_id}.png")
        assert_non_empty_file(figures_dir / f"{figure_id}.svg")

    generated_spec = yaml.safe_load((figures_dir / "figure-spec.yaml").read_text(encoding="utf-8"))
    assert [item["figure_id"] for item in generated_spec["figures"]] == [
        "accuracy_line",
        "runtime_bar",
        "accuracy_box",
    ]
    summary = _figure_summary(task_path)
    assert summary["figure_count"] == 3
    assert [item["chart_type"] for item in summary["generated_figures"]] == ["line", "bar", "box"]
    assert summary["errors"] == []
    assert summary["skipped_candidates"] == []
    assert summary["fallback"]["mode"] == "off"
    assert summary["fallback"]["attempted"] is False


def test_multi_explicit_spec_partial_failures_record_diagnostics(tmp_path: Path) -> None:
    task_id, task_path = _prepare_metrics_task(tmp_path)
    (tmp_path / "partial.yaml").write_text(
        "\n".join(
            [
                "figures:",
                "  - figure_id: accuracy_line",
                "    chart_type: line",
                "    title: Accuracy over Epoch",
                "    x: epoch",
                "    y: accuracy",
                "  - figure_id: missing_metric",
                "    chart_type: line",
                "    title: Missing Metric",
                "    x: epoch",
                "    y: does_not_exist",
                "  - figure_id: unsupported_scatter",
                "    chart_type: scatter",
                "    title: Unsupported Scatter",
                "    x: epoch",
                "    y: accuracy",
                "  - figure_id: invalid_missing_title",
                "    chart_type: bar",
                "    x: method",
                "    y: runtime_ms",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["figures", task_id, "--spec", "partial.yaml"])

    assert result.exit_code == 0
    assert "Generated 1 figure(s)" in result.output
    figures_dir = task_path / "figures"
    assert_non_empty_file(figures_dir / "accuracy_line.png")
    assert not (figures_dir / "missing_metric.png").exists()
    assert not (figures_dir / "unsupported_scatter.png").exists()
    assert not (figures_dir / "invalid_missing_title.png").exists()

    summary = _figure_summary(task_path)
    assert summary["figure_count"] == 1
    assert summary["generated_figures"][0]["figure_id"] == "accuracy_line"
    assert summary["errors"]
    assert any("does_not_exist" in error for error in summary["errors"])
    assert any("invalid_missing_title" in error and "title" in error for error in summary["errors"])
    skipped_ids = {item["figure_id"] for item in summary["skipped_candidates"]}
    assert {"missing_metric", "unsupported_scatter", "invalid_missing_title"} <= skipped_ids
    assert summary["unsupported_chart_diagnostics"]
    assert summary["unsupported_chart_diagnostics"][0]["requested_chart_intent"]["chart_type"] == "scatter"
    assert summary["fallback"]["mode"] == "off"
    assert summary["fallback"]["attempted"] is False
    assert not (task_path / "intelligence").exists()


def test_auto_figures_try_bar_when_line_default_has_too_few_points(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "sparse-results"
    source.mkdir()
    (source / "metrics.csv").write_text(
        "\n".join(
            [
                "epoch,method,accuracy,runtime_ms",
                "1,baseline,0.72,51",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "sparse-results"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    summary = _figure_summary(task_path)
    assert summary["figure_count"] == 1
    assert summary["generated_figures"][0]["chart_type"] == "bar"
    assert summary["generated_figures"][0]["x"] == "method"
    assert summary["generated_figures"][0]["y"] == "accuracy"
    assert any("fewer than 2 numeric points" in item["reason"] for item in summary["skipped_candidates"])
    assert_non_empty_file(task_path / "figures" / "bar_accuracy_by_method.png")
