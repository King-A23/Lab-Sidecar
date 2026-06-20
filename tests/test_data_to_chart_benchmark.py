from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from lab_sidecar.cli.app import app


runner = CliRunner()


def invoke(workspace: Path, args: list[str]):
    old_cwd = Path.cwd()
    os.chdir(workspace)
    try:
        return runner.invoke(app, args, prog_name="labsidecar", env={}, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def extract_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Imported as task: "):
            return line.split(": ", 1)[1]
        if line.startswith("Task created: "):
            return line.split(": ", 1)[1]
    raise AssertionError(f"No task id in output:\n{output}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_nonblank_png(path: Path) -> None:
    assert path.is_file()
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        assert rgb.size[0] >= 800
        assert rgb.size[1] >= 450
        colors = rgb.getcolors(maxcolors=1_000_000)
        assert colors is not None
        assert len(colors) > 1


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_auto_box_chart_for_multi_seed_distribution(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "seed-results"
    rows = []
    for method, base in [("baseline", 0.78), ("candidate", 0.84)]:
        for seed in [1, 2, 3, 4]:
            rows.append({"raw_method": method, "raw_seed": seed, "raw_accuracy": base + seed * 0.002})
    write_csv(source / "metrics.csv", rows)
    (tmp_path / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - seed-results/metrics.csv",
                "fields:",
                "  method: raw_method",
                "  seed: raw_seed",
                "  accuracy:",
                "    source: raw_accuracy",
                "    unit: ratio",
                "groups:",
                "  primary: method",
                "  secondary: seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "seed-results"]).output)
    assert invoke(tmp_path, ["collect", task_id, "--config", "metrics.yaml"]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    summary = read_json(task_path / "figures" / "figure-summary.json")
    figure = summary["generated_figures"][0]
    assert figure["chart_type"] == "box"
    assert figure["x"] == "method"
    assert figure["y"] == "accuracy"
    assert figure["field_sources"] == {"method": ["raw_method"], "accuracy": ["raw_accuracy"]}
    assert_nonblank_png(task_path / "figures" / "box_accuracy_by_method.png")


def test_auto_grouped_bar_records_group_and_traceability(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "categorical"
    write_csv(
        source / "metrics.csv",
        [
            {"raw_model": "baseline", "raw_dataset": "a", "raw_accuracy": 0.78},
            {"raw_model": "candidate", "raw_dataset": "a", "raw_accuracy": 0.83},
            {"raw_model": "baseline", "raw_dataset": "b", "raw_accuracy": 0.75},
            {"raw_model": "candidate", "raw_dataset": "b", "raw_accuracy": 0.81},
        ],
    )
    (tmp_path / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - categorical/metrics.csv",
                "fields:",
                "  model: raw_model",
                "  dataset: raw_dataset",
                "  accuracy:",
                "    source: raw_accuracy",
                "    unit: ratio",
                "groups:",
                "  primary: model",
                "  secondary: dataset",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "categorical"]).output)
    assert invoke(tmp_path, ["collect", task_id, "--config", "metrics.yaml"]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    summary = read_json(task_path / "figures" / "figure-summary.json")
    figure = summary["generated_figures"][0]
    assert figure["chart_type"] == "bar"
    assert figure["x"] == "model"
    assert figure["y"] == "accuracy"
    assert figure["group_by"] == "dataset"
    assert figure["field_sources"]["dataset"] == ["raw_dataset"]
    traceability = read_json(task_path / "provenance" / "traceability.json")
    lineage_figure = traceability["figure_lineage"]["figures"][0]
    assert lineage_figure["chart_type"] == "bar"
    assert {"model", "accuracy", "dataset"}.issubset(lineage_figure["columns"])
    assert lineage_figure["field_sources"]["dataset"] == ["raw_dataset"]
    assert_nonblank_png(task_path / "figures" / "bar_accuracy_by_model.png")


def test_auto_datetime_time_series_line_chart(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "service-timeseries"
    rows = []
    for service, base in [("api", 900), ("worker", 620)]:
        for index in range(5):
            rows.append(
                {
                    "raw_ts": f"2026-06-20T10:{index * 5:02d}:00+00:00",
                    "raw_service": service,
                    "raw_throughput": base + index * 4,
                }
            )
    write_csv(source / "metrics.csv", rows)
    (tmp_path / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - service-timeseries/metrics.csv",
                "fields:",
                "  timestamp: raw_ts",
                "  service: raw_service",
                "  throughput_rps:",
                "    source: raw_throughput",
                "    unit: rps",
                "groups:",
                "  primary: service",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "service-timeseries"]).output)
    assert invoke(tmp_path, ["collect", task_id, "--config", "metrics.yaml"]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    summary = read_json(task_path / "figures" / "figure-summary.json")
    figure = summary["generated_figures"][0]
    assert figure["chart_type"] == "line"
    assert figure["x"] == "timestamp"
    assert figure["y"] == "throughput_rps"
    assert figure["group_by"] == "service"
    assert figure["field_sources"] == {
        "timestamp": ["raw_ts"],
        "throughput_rps": ["raw_throughput"],
        "service": ["raw_service"],
    }
    assert_nonblank_png(task_path / "figures" / "line_throughput_rps_over_timestamp.png")


def test_data_to_chart_benchmark_runner_smoke(tmp_path: Path) -> None:
    benchmark_root = tmp_path / "d2c-benchmark"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/data_to_chart_benchmark.py",
            "--scale",
            "smoke",
            "--benchmark-root",
            benchmark_root.as_posix(),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["aggregate"]["passed"] is True
    assert payload["aggregate"]["score_total"] == payload["aggregate"]["score_max"]
    assert payload["aggregate"]["sidecar_raw_metric_row_bytes_exposed"] == 0
    assert payload["aggregate"]["context_reduction_pct"] > 0


def test_alpha4_bounded_chart_fallback_benchmark_runner_smoke(tmp_path: Path) -> None:
    benchmark_root = tmp_path / "alpha4-fallback-benchmark"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/alpha4_bounded_chart_fallback_benchmark.py",
            "--scale",
            "smoke",
            "--benchmark-root",
            benchmark_root.as_posix(),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    aggregate = payload["aggregate"]
    assert aggregate["passed"] is True
    assert aggregate["deterministic_covered_count"] == 0
    assert aggregate["fallback_covered_count"] == aggregate["scenario_count"]
    assert aggregate["coverage_delta"] == aggregate["scenario_count"]
    assert aggregate["sidecar_raw_metric_row_bytes_exposed"] == 0
    assert aggregate["sidecar_violation_count"] == 0
    assert aggregate["context_reduction_pct"] > 0
