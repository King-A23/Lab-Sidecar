from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PIL import Image, ImageChops


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "data-to-chart-benchmark.md"
DATA_PATH = REPO_ROOT / "docs" / "data-to-chart-benchmark-data.json"
SENTINEL = "D2C_RAW_SENTINEL_DO_NOT_EXPOSE"
RAW_PADDING_CHARS = 5000
ALLOWED_SIDECAR_READS = {
    "metrics/collection-summary.json",
    "figures/figure-summary.json",
    "provenance/traceability.json",
}


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    expected_chart_type: str
    expected_x: str
    expected_y: str
    expected_group_by: str | None
    raw_filename: str
    metrics_yaml: str


SCENARIOS = [
    Scenario(
        scenario_id="training_curve",
        expected_chart_type="line",
        expected_x="epoch",
        expected_y="accuracy",
        expected_group_by="split",
        raw_filename="training_curve.csv",
        metrics_yaml="""sources:
  - inputs/training_curve.csv
fields:
  epoch: raw_epoch
  split: raw_split
  accuracy:
    source: metric_value
    unit: ratio
groups:
  primary: split
""",
    ),
    Scenario(
        scenario_id="multi_run_sweep",
        expected_chart_type="line",
        expected_x="step",
        expected_y="val_accuracy",
        expected_group_by="config_id",
        raw_filename="multi_run_sweep.csv",
        metrics_yaml="""sources:
  - inputs/multi_run_sweep.csv
fields:
  step: raw_step
  config_id: raw_config
  seed: raw_seed
  val_accuracy:
    source: raw_score
    unit: ratio
groups:
  primary: config_id
  secondary: seed
""",
    ),
    Scenario(
        scenario_id="ablation",
        expected_chart_type="bar",
        expected_x="variant",
        expected_y="accuracy",
        expected_group_by=None,
        raw_filename="ablation.csv",
        metrics_yaml="""sources:
  - inputs/ablation.csv
fields:
  variant: raw_variant
  accuracy:
    source: raw_accuracy
    unit: ratio
units:
  accuracy: ratio
""",
    ),
    Scenario(
        scenario_id="error_analysis",
        expected_chart_type="bar",
        expected_x="class",
        expected_y="error_rate",
        expected_group_by="split",
        raw_filename="error_analysis.csv",
        metrics_yaml="""sources:
  - inputs/error_analysis.csv
fields:
  class: raw_class
  split: raw_split
  error_rate:
    source: raw_error_rate
    unit: ratio
groups:
  primary: class
  secondary: split
""",
    ),
    Scenario(
        scenario_id="time_series",
        expected_chart_type="line",
        expected_x="timestamp",
        expected_y="throughput_rps",
        expected_group_by="service",
        raw_filename="time_series.csv",
        metrics_yaml="""sources:
  - inputs/time_series.csv
fields:
  timestamp: raw_ts
  service: raw_service
  throughput_rps:
    source: raw_throughput
    unit: rps
groups:
  primary: service
""",
    ),
    Scenario(
        scenario_id="categorical_comparison",
        expected_chart_type="bar",
        expected_x="model",
        expected_y="accuracy",
        expected_group_by="dataset",
        raw_filename="categorical_comparison.csv",
        metrics_yaml="""sources:
  - inputs/categorical_comparison.csv
fields:
  model: raw_model
  dataset: raw_dataset
  accuracy:
    source: raw_accuracy
    unit: ratio
groups:
  primary: model
  secondary: dataset
""",
    ),
    Scenario(
        scenario_id="multi_seed_distribution",
        expected_chart_type="box",
        expected_x="method",
        expected_y="accuracy",
        expected_group_by=None,
        raw_filename="multi_seed_distribution.csv",
        metrics_yaml="""sources:
  - inputs/multi_seed_distribution.csv
fields:
  method: raw_method
  seed: raw_seed
  accuracy:
    source: raw_accuracy
    unit: ratio
groups:
  primary: method
  secondary: seed
""",
    ),
]


def main() -> None:
    args = parse_args()
    benchmark_root = args.benchmark_root or Path(tempfile.mkdtemp(prefix="lab-sidecar-data-to-chart-benchmark-", dir="/private/tmp"))
    benchmark_root = benchmark_root.resolve()
    if benchmark_root.exists():
        shutil.rmtree(benchmark_root)
    benchmark_root.mkdir(parents=True)

    python_path = resolve_python_path(Path(args.python))
    data = run_benchmark(benchmark_root=benchmark_root, python_path=python_path, scale=args.scale)
    if args.write_docs:
        docs_data = redact_for_docs(data, benchmark_root=benchmark_root, python_path=python_path)
        DATA_PATH.write_text(json.dumps(docs_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        DOC_PATH.write_text(render_report(docs_data), encoding="utf-8")
        print(f"Wrote {DATA_PATH.relative_to(REPO_ROOT)}")
        print(f"Wrote {DOC_PATH.relative_to(REPO_ROOT)}")
    else:
        print(json.dumps(_brief_result(data), ensure_ascii=False, indent=2))

    failed = [scenario["scenario_id"] for scenario in data["scenarios"] if not scenario["passed"]]
    if failed:
        raise SystemExit(f"Data-to-Chart benchmark failed: {', '.join(failed)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Lab-Sidecar Data-to-Chart benchmark.")
    parser.add_argument("--scale", choices=["smoke", "full"], default="full")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--benchmark-root", type=Path, default=None)
    parser.add_argument("--write-docs", action="store_true")
    return parser.parse_args()


def run_benchmark(benchmark_root: Path, python_path: Path, scale: str) -> dict[str, Any]:
    python_path = resolve_python_path(python_path)
    scenarios: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        scenario_root = benchmark_root / scenario.scenario_id
        fixture_dir = scenario_root / "inputs"
        workspace = scenario_root / "workspace"
        fixture_dir.mkdir(parents=True)
        workspace.mkdir(parents=True)
        write_fixture(scenario, fixture_dir, scale)
        workspace_inputs = workspace / "inputs"
        shutil.copytree(fixture_dir, workspace_inputs)
        metrics_config = workspace / "metrics.yaml"
        metrics_config.write_text(scenario.metrics_yaml, encoding="utf-8")

        raw_context = measure_raw_context(fixture_dir / scenario.raw_filename)
        sidecar_result = run_sidecar(
            scenario=scenario,
            workspace=workspace,
            fixture_dir=workspace_inputs,
            metrics_config=metrics_config,
            python_path=python_path,
        )
        scenario_result = score_scenario(scenario, raw_context, sidecar_result)
        scenarios.append(scenario_result)

    aggregate = aggregate_results(scenarios)
    return {
        "schema_version": "1",
        "date": datetime.now(timezone.utc).astimezone().date().isoformat(),
        "package_version": package_version(),
        "benchmark_root": benchmark_root.as_posix(),
        "scale": scale,
        "token_estimate": {
            "method": "ceil(chars / 4)",
            "exact_provider_tokens_available": False,
        },
        "sidecar_allowed_reads": sorted(ALLOWED_SIDECAR_READS),
        "scenarios": scenarios,
        "aggregate": aggregate,
    }


def write_fixture(scenario: Scenario, fixture_dir: Path, scale: str) -> None:
    row_scale = 1 if scale == "smoke" else 20
    writer = FIXTURE_WRITERS[scenario.scenario_id]
    writer(fixture_dir / scenario.raw_filename, row_scale)


def write_training_curve(path: Path, row_scale: int) -> None:
    rows = []
    epochs = 6 * row_scale
    for epoch in range(1, epochs + 1):
        for split, offset in [("train", 0.06), ("val", 0.0)]:
            rows.append(
                {
                    "raw_epoch": epoch,
                    "raw_split": split,
                    "metric_value": round(0.52 + epoch * 0.006 + offset, 5),
                    "raw_only_secret": raw_only_secret(epoch, split),
                }
            )
    write_csv(path, rows)


def write_multi_run_sweep(path: Path, row_scale: int) -> None:
    rows = []
    steps = 6 * row_scale
    for config_index, config_id in enumerate(["cfg_a", "cfg_b", "cfg_c"], start=1):
        for seed in [11, 13]:
            for step_index in range(1, steps + 1):
                rows.append(
                    {
                        "raw_step": step_index * 100,
                        "raw_config": config_id,
                        "raw_seed": seed,
                        "raw_score": round(0.58 + config_index * 0.035 + step_index * 0.002 - seed * 0.0001, 5),
                        "raw_only_secret": raw_only_secret(config_id, seed, step_index),
                    }
                )
    write_csv(path, rows)


def write_ablation(path: Path, row_scale: int) -> None:
    rows = [
        {"raw_variant": "baseline", "raw_accuracy": 0.804, "raw_only_secret": raw_only_secret("baseline")},
        {"raw_variant": "no_dropout", "raw_accuracy": 0.781, "raw_only_secret": raw_only_secret("no_dropout")},
        {"raw_variant": "no_aug", "raw_accuracy": 0.766, "raw_only_secret": raw_only_secret("no_aug")},
        {"raw_variant": "full_plus", "raw_accuracy": 0.818, "raw_only_secret": raw_only_secret("full_plus")},
    ]
    write_csv(path, rows)


def write_error_analysis(path: Path, row_scale: int) -> None:
    rows = []
    for label in ["cat", "dog", "bird", "truck"]:
        for split, base in [("validation", 0.08), ("test", 0.1)]:
            rows.append(
                {
                    "raw_class": label,
                    "raw_split": split,
                    "raw_error_rate": round(base + len(label) * 0.006, 4),
                    "raw_only_secret": raw_only_secret(label, split),
                }
            )
    write_csv(path, rows)


def write_time_series(path: Path, row_scale: int) -> None:
    rows = []
    start = datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)
    for service, base in [("api", 920), ("worker", 650)]:
        for index in range(8 * row_scale):
            rows.append(
                {
                    "raw_ts": (start + timedelta(minutes=5 * index)).isoformat(),
                    "raw_service": service,
                    "raw_throughput": round(base + index * 3.5, 2),
                    "raw_only_secret": raw_only_secret(service, index),
                }
            )
    write_csv(path, rows)


def write_categorical_comparison(path: Path, row_scale: int) -> None:
    rows = []
    for dataset, offset in [("dataset_a", 0.0), ("dataset_b", -0.025)]:
        for model, base in [("baseline", 0.78), ("candidate_a", 0.815), ("candidate_b", 0.834)]:
            rows.append(
                {
                    "raw_model": model,
                    "raw_dataset": dataset,
                    "raw_accuracy": round(base + offset, 4),
                    "raw_only_secret": raw_only_secret(dataset, model),
                }
            )
    write_csv(path, rows)


def write_multi_seed_distribution(path: Path, row_scale: int) -> None:
    rows = []
    seeds = list(range(1, 1 + 4 * row_scale))
    for method, base in [("baseline", 0.79), ("candidate", 0.835), ("regularized", 0.822)]:
        for seed in seeds:
            rows.append(
                {
                    "raw_method": method,
                    "raw_seed": seed,
                    "raw_accuracy": round(base + ((seed % 5) - 2) * 0.004, 4),
                    "raw_only_secret": raw_only_secret(method, seed),
                }
            )
    write_csv(path, rows)


FIXTURE_WRITERS = {
    "training_curve": write_training_curve,
    "multi_run_sweep": write_multi_run_sweep,
    "ablation": write_ablation,
    "error_analysis": write_error_analysis,
    "time_series": write_time_series,
    "categorical_comparison": write_categorical_comparison,
    "multi_seed_distribution": write_multi_seed_distribution,
}


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def raw_only_secret(*parts: object) -> str:
    prefix = "_".join(str(part) for part in parts)
    return f"{SENTINEL}_{prefix}_" + ("x" * RAW_PADDING_CHARS)


def measure_raw_context(raw_path: Path) -> dict[str, Any]:
    text = raw_path.read_text(encoding="utf-8")
    return {
        "files_read": [
            {
                "path": raw_path.as_posix(),
                "bytes": raw_path.stat().st_size,
                "chars": len(text),
                "purpose": "raw_agent_table_context",
            }
        ],
        "context_bytes": raw_path.stat().st_size,
        "context_chars": len(text),
        "estimated_context_tokens": estimate_tokens(len(text)),
        "raw_metric_row_bytes_exposed": raw_path.stat().st_size,
    }


def run_sidecar(
    scenario: Scenario,
    workspace: Path,
    fixture_dir: Path,
    metrics_config: Path,
    python_path: Path,
) -> dict[str, Any]:
    commands = []
    context_parts: list[str] = []

    def command(args: list[str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            REPO_ROOT.as_posix()
            if not existing_pythonpath
            else f"{REPO_ROOT.as_posix()}{os.pathsep}{existing_pythonpath}"
        )
        result = subprocess.run(
            [python_path.as_posix(), "-m", "lab_sidecar.cli.app", *args],
            cwd=workspace,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        commands.append(
            {
                "args": [python_path.as_posix(), "-m", "lab_sidecar.cli.app", *args],
                "cwd": workspace.as_posix(),
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        context_parts.extend([result.stdout, result.stderr])
        if result.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(args)}\n{result.stdout}\n{result.stderr}")
        return result

    command(["init"])
    ingest_result = command(["ingest", fixture_dir.as_posix(), "--name", f"data-to-chart {scenario.scenario_id}"])
    task_id = extract_task_id(ingest_result.stdout)
    command(["collect", task_id, "--config", metrics_config.as_posix()])
    command(["figures", task_id])

    task_path = workspace / ".lab-sidecar" / "tasks" / task_id
    files_read = []
    allowed_data = {}
    for rel_path in sorted(ALLOWED_SIDECAR_READS):
        path = task_path / rel_path
        text = path.read_text(encoding="utf-8")
        context_parts.append(text)
        files_read.append(
            {
                "path": rel_path,
                "bytes": path.stat().st_size,
                "chars": len(text),
                "purpose": "allowed_sidecar_summary",
            }
        )
        allowed_data[rel_path] = json.loads(text)

    context = "".join(context_parts)
    return {
        "workspace": workspace.as_posix(),
        "task_id": task_id,
        "task_path": task_path.as_posix(),
        "commands_run": commands,
        "files_read": files_read,
        "context_bytes": len(context.encode("utf-8")),
        "context_chars": len(context),
        "estimated_context_tokens": estimate_tokens(len(context)),
        "raw_metric_row_bytes_exposed": 0,
        "collection_summary": allowed_data["metrics/collection-summary.json"],
        "figure_summary": allowed_data["figures/figure-summary.json"],
        "traceability": allowed_data["provenance/traceability.json"],
    }


def extract_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Imported as task: "):
            return line.split(": ", 1)[1]
        if line.startswith("Task created: "):
            return line.split(": ", 1)[1]
    raise ValueError(f"task id not found in output:\n{output}")


def score_scenario(scenario: Scenario, raw_context: dict[str, Any], sidecar: dict[str, Any]) -> dict[str, Any]:
    figure_summary = sidecar["figure_summary"]
    figures = figure_summary.get("generated_figures") or []
    figure = figures[0] if figures and isinstance(figures[0], dict) else {}
    traceability = sidecar["traceability"]
    serialized_sidecar = json.dumps(
        {
            "collection_summary": sidecar["collection_summary"],
            "figure_summary": figure_summary,
            "traceability": traceability,
            "commands_run": sidecar["commands_run"],
        },
        ensure_ascii=False,
    )
    visual = validate_visuals(sidecar["task_path"], figure)
    expected_fields = [scenario.expected_x, scenario.expected_y]
    if scenario.expected_group_by:
        expected_fields.append(scenario.expected_group_by)

    scores = {
        "chart_type_correct": figure.get("chart_type") == scenario.expected_chart_type,
        "axes_group_correct": (
            figure.get("x") == scenario.expected_x
            and figure.get("y") == scenario.expected_y
            and figure.get("group_by") == scenario.expected_group_by
        ),
        "units_field_mapping_correct": units_and_mapping_correct(figure, expected_fields),
        "visual_artifacts_valid": visual["passed"],
        "traceability_complete": traceability_complete(traceability, scenario),
        "sidecar_bounded": SENTINEL not in serialized_sidecar and sidecar["raw_metric_row_bytes_exposed"] == 0,
        "context_reduction_positive": sidecar["context_chars"] < raw_context["context_chars"],
    }
    violations = []
    if SENTINEL in serialized_sidecar:
        violations.append({"reason": "sentinel_exposed_in_sidecar_context"})
    if sidecar["raw_metric_row_bytes_exposed"]:
        violations.append({"reason": "raw_metric_rows_exposed_in_sidecar_context"})

    context_reduction_pct = pct_reduction(raw_context["context_chars"], sidecar["context_chars"])
    return {
        "scenario_id": scenario.scenario_id,
        "expected": {
            "chart_type": scenario.expected_chart_type,
            "x": scenario.expected_x,
            "y": scenario.expected_y,
            "group_by": scenario.expected_group_by,
        },
        "raw_agent": raw_context,
        "lab_sidecar": {
            "workspace": sidecar["workspace"],
            "task_ids": [sidecar["task_id"]],
            "commands_run": sidecar["commands_run"],
            "files_read": sidecar["files_read"],
            "context_bytes": sidecar["context_bytes"],
            "context_chars": sidecar["context_chars"],
            "estimated_context_tokens": sidecar["estimated_context_tokens"],
            "raw_metric_row_bytes_exposed": sidecar["raw_metric_row_bytes_exposed"],
            "generated_figure": {
                key: figure.get(key)
                for key in ["figure_id", "chart_type", "png_path", "svg_path", "x", "y", "group_by", "units", "field_sources"]
            },
            "traceability_present": bool(traceability),
        },
        "scores": scores,
        "score_total": sum(1 for value in scores.values() if value),
        "passed": all(scores.values()),
        "context_reduction_pct": context_reduction_pct,
        "visual_validation": visual,
        "violations": violations,
    }


def units_and_mapping_correct(figure: dict[str, Any], expected_fields: list[str]) -> bool:
    units = figure.get("units")
    field_sources = figure.get("field_sources")
    if not isinstance(units, dict) or not isinstance(field_sources, dict):
        return False
    if not units.get(str(figure.get("y"))):
        return False
    return all(field in field_sources and field_sources[field] for field in expected_fields)


def validate_visuals(task_path_text: str, figure: dict[str, Any]) -> dict[str, Any]:
    task_path = Path(task_path_text)
    png_text = figure.get("png_path")
    svg_text = figure.get("svg_path")
    if not isinstance(png_text, str) or not isinstance(svg_text, str):
        return {"passed": False, "reason": "missing figure paths"}
    png_path = resolve_task_path(task_path, png_text)
    svg_path = resolve_task_path(task_path, svg_text)
    checks: dict[str, Any] = {
        "png_path": png_text,
        "svg_path": svg_text,
        "png_exists": png_path.is_file(),
        "svg_exists": svg_path.is_file(),
    }
    if not png_path.is_file() or not svg_path.is_file():
        checks["passed"] = False
        return checks

    with Image.open(png_path) as image:
        rgb = image.convert("RGB")
        checks["png_size"] = list(rgb.size)
        background = Image.new("RGB", rgb.size, "white")
        diff = ImageChops.difference(rgb, background)
        bbox = diff.getbbox()
        nonwhite_ratio = nonwhite_pixel_ratio(rgb)
        checks["nonwhite_pixel_ratio"] = round(nonwhite_ratio, 5)
        checks["content_bbox"] = list(bbox) if bbox else None
        border_margin_ok = True
        if bbox:
            width, height = rgb.size
            left, top, right, bottom = bbox
            border_margin_ok = left > 0 and top > 0 and right < width and bottom < height
        checks["border_margin_ok"] = border_margin_ok

    try:
        root = ElementTree.parse(svg_path).getroot()
        svg_ok = root.tag.endswith("svg") and svg_path.stat().st_size > 200
    except ElementTree.ParseError:
        svg_ok = False
    checks["svg_parseable"] = svg_ok
    checks["passed"] = (
        checks["png_size"][0] >= 800
        and checks["png_size"][1] >= 450
        and checks["nonwhite_pixel_ratio"] > 0.01
        and checks["border_margin_ok"]
        and svg_ok
    )
    return checks


def resolve_task_path(task_path: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == ".lab-sidecar":
        return task_path.parents[2] / path
    return task_path / path


def nonwhite_pixel_ratio(image: Image.Image) -> float:
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    total = image.width * image.height
    nonwhite = sum(1 for red, green, blue in pixels if (red, green, blue) != (255, 255, 255))
    return nonwhite / total if total else 0.0


def traceability_complete(traceability: dict[str, Any], scenario: Scenario) -> bool:
    figure_lineage = traceability.get("figure_lineage")
    if not isinstance(figure_lineage, dict) or not figure_lineage.get("present"):
        return False
    figures = figure_lineage.get("figures")
    if not isinstance(figures, list) or not figures:
        return False
    figure = figures[0]
    if figure.get("chart_type") != scenario.expected_chart_type:
        return False
    columns = set(figure.get("columns") or [])
    expected = {scenario.expected_x, scenario.expected_y}
    if scenario.expected_group_by:
        expected.add(scenario.expected_group_by)
    return expected.issubset(columns) and bool(figure.get("artifact_ids"))


def aggregate_results(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    raw_chars = sum(item["raw_agent"]["context_chars"] for item in scenarios)
    sidecar_chars = sum(item["lab_sidecar"]["context_chars"] for item in scenarios)
    raw_tokens = sum(item["raw_agent"]["estimated_context_tokens"] for item in scenarios)
    sidecar_tokens = sum(item["lab_sidecar"]["estimated_context_tokens"] for item in scenarios)
    raw_metric_bytes = sum(item["raw_agent"]["raw_metric_row_bytes_exposed"] for item in scenarios)
    sidecar_metric_bytes = sum(item["lab_sidecar"]["raw_metric_row_bytes_exposed"] for item in scenarios)
    return {
        "scenario_count": len(scenarios),
        "passed_count": sum(1 for item in scenarios if item["passed"]),
        "passed": all(item["passed"] for item in scenarios),
        "raw_context_chars": raw_chars,
        "sidecar_context_chars": sidecar_chars,
        "context_reduction_pct": pct_reduction(raw_chars, sidecar_chars),
        "raw_estimated_tokens": raw_tokens,
        "sidecar_estimated_tokens": sidecar_tokens,
        "token_reduction_pct": pct_reduction(raw_tokens, sidecar_tokens),
        "raw_metric_row_bytes_exposed": raw_metric_bytes,
        "sidecar_raw_metric_row_bytes_exposed": sidecar_metric_bytes,
        "raw_metric_exposure_reduction_pct": pct_reduction(raw_metric_bytes, sidecar_metric_bytes),
        "sidecar_violation_count": sum(len(item["violations"]) for item in scenarios),
        "score_total": sum(item["score_total"] for item in scenarios),
        "score_max": len(scenarios) * 7,
    }


def render_report(data: dict[str, Any]) -> str:
    lines = [
        "# Data-to-Chart Benchmark",
        "",
        f"Date: {data['date']}",
        "",
        "## Methodology",
        "",
        "This benchmark generates deterministic fixtures under `/private/tmp`, runs the local Lab-Sidecar CLI path, and scores generated `PNG/SVG` figures plus `figures/figure-summary.json` without reading full normalized metrics or raw source files in the sidecar arm.",
        "",
        "Token counts use the deterministic proxy `ceil(chars / 4)`.",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Expected | Generated | Axes | Score | Passed | Context reduction |",
        "| --- | --- | --- | --- | ---: | --- | ---: |",
    ]
    for item in data["scenarios"]:
        generated = item["lab_sidecar"]["generated_figure"]
        axes = f"{generated.get('x')} / {generated.get('y')} / {display_null(generated.get('group_by'))}"
        expected = item["expected"]
        expected_text = f"{expected['chart_type']} {expected['x']}/{expected['y']}/{display_null(expected['group_by'])}"
        lines.append(
            "| {scenario} | {expected} | {generated_type} | {axes} | {score}/7 | {passed} | {reduction:.2f}% |".format(
                scenario=item["scenario_id"],
                expected=expected_text,
                generated_type=generated.get("chart_type"),
                axes=axes,
                score=item["score_total"],
                passed="yes" if item["passed"] else "no",
                reduction=item["context_reduction_pct"],
            )
        )
    aggregate = data["aggregate"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            "| Raw chars | Sidecar chars | Context reduction | Raw est. tokens | Sidecar est. tokens | Token reduction | Score | Violations |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| {raw_chars} | {sidecar_chars} | {ctx:.2f}% | {raw_tokens} | {sidecar_tokens} | {tok:.2f}% | {score}/{score_max} | {violations} |".format(
                raw_chars=aggregate["raw_context_chars"],
                sidecar_chars=aggregate["sidecar_context_chars"],
                ctx=aggregate["context_reduction_pct"],
                raw_tokens=aggregate["raw_estimated_tokens"],
                sidecar_tokens=aggregate["sidecar_estimated_tokens"],
                tok=aggregate["token_reduction_pct"],
                score=aggregate["score_total"],
                score_max=aggregate["score_max"],
                violations=aggregate["sidecar_violation_count"],
            ),
            "",
            "## Acceptance Status",
            "",
            "Passed." if aggregate["passed"] else "Failed.",
            "",
            "Sidecar context was limited to CLI output, collection summary, figure summary, and task-local traceability. Full normalized metric rows and raw source files were not read by the benchmark sidecar arm.",
            "",
            "## Limitations",
            "",
            "- Token counts are a character-based proxy, not provider billing data.",
            "- Visual validation is deterministic and catches blank or obviously clipped figures; it is not a human design review.",
            "- The benchmark exercises local CLI behavior only, not MCP or hosted workflows.",
            "",
        ]
    )
    return "\n".join(lines)


def package_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    return "unknown"


def resolve_python_path(python_path: Path) -> Path:
    if not python_path.is_absolute():
        return (Path.cwd() / python_path).absolute()
    return python_path


def redact_for_docs(data: dict[str, Any], benchmark_root: Path, python_path: Path) -> dict[str, Any]:
    replacements = [
        (python_path.as_posix(), "<python>"),
        (benchmark_root.as_posix(), "<benchmark-root>"),
        (REPO_ROOT.as_posix(), "<repo>"),
    ]
    return _redact_value(data, replacements)


def _redact_value(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: _redact_value(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, replacements) for item in value]
    if isinstance(value, str):
        for original, replacement in replacements:
            if original:
                value = value.replace(original, replacement)
        return value
    return value


def display_null(value: object) -> object:
    return "null" if value is None else value


def estimate_tokens(chars: int) -> int:
    return int(math.ceil(chars / 4))


def pct_reduction(raw: int, sidecar: int) -> float:
    if raw == 0:
        return 0.0
    return round(100 * (1 - sidecar / raw), 2)


def _brief_result(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_root": data["benchmark_root"],
        "scale": data["scale"],
        "aggregate": data["aggregate"],
        "scenarios": [
            {
                "scenario_id": item["scenario_id"],
                "passed": item["passed"],
                "score_total": item["score_total"],
                "context_reduction_pct": item["context_reduction_pct"],
            }
            for item in data["scenarios"]
        ],
    }


if __name__ == "__main__":
    main()
