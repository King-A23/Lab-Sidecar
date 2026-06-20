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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "alpha4-bounded-chart-fallback-benchmark.md"
DATA_PATH = REPO_ROOT / "docs" / "alpha4-bounded-chart-fallback-benchmark-data.json"
SENTINEL = "ALPHA4_FALLBACK_RAW_SENTINEL_DO_NOT_EXPOSE"
RAW_PADDING_CHARS = 4000
ALLOWED_SIDECAR_READS = {
    "metrics/collection-summary.json",
    "figures/figure-summary.json",
    "provenance/traceability.json",
}
ALLOWED_FALLBACK_READS = {
    "figure_request": "request_path",
    "validator_result": "validator_result_path",
    "adoption_record": "adoption_record_path",
}


@dataclass(frozen=True)
class FallbackScenario:
    scenario_id: str
    chart_type: str
    figure_id: str
    title: str
    x: str
    y: str
    group_by: str | None
    raw_filename: str
    metrics_yaml: str


SCENARIOS = [
    FallbackScenario(
        scenario_id="scatter_correlation",
        chart_type="scatter",
        figure_id="fallback_scatter_correlation",
        title="Validation Accuracy Correlation",
        x="epoch",
        y="val_accuracy",
        group_by="model",
        raw_filename="scatter_correlation.csv",
        metrics_yaml="""sources:
  - inputs/scatter_correlation.csv
fields:
  epoch: raw_epoch
  model: raw_model
  val_accuracy:
    source: raw_val_accuracy
    unit: ratio
groups:
  primary: model
""",
    ),
    FallbackScenario(
        scenario_id="heatmap_confusion_matrix",
        chart_type="heatmap",
        figure_id="fallback_confusion_heatmap",
        title="Confusion Matrix Heatmap",
        x="predicted_class",
        y="true_class",
        group_by=None,
        raw_filename="heatmap_confusion_matrix.csv",
        metrics_yaml="""sources:
  - inputs/heatmap_confusion_matrix.csv
fields:
  predicted_class: raw_predicted
  true_class: raw_actual
  count:
    source: raw_count
    unit: count
groups:
  primary: true_class
  secondary: predicted_class
""",
    ),
    FallbackScenario(
        scenario_id="histogram_distribution",
        chart_type="histogram",
        figure_id="fallback_latency_histogram",
        title="Latency Distribution",
        x="latency_ms",
        y="latency_ms",
        group_by="service",
        raw_filename="histogram_distribution.csv",
        metrics_yaml="""sources:
  - inputs/histogram_distribution.csv
fields:
  latency_ms:
    source: raw_latency_ms
    unit: ms
  service: raw_service
groups:
  primary: service
""",
    ),
    FallbackScenario(
        scenario_id="stacked_category_composition",
        chart_type="stacked_bar",
        figure_id="fallback_category_composition",
        title="Category Composition",
        x="category",
        y="share",
        group_by="segment",
        raw_filename="stacked_category_composition.csv",
        metrics_yaml="""sources:
  - inputs/stacked_category_composition.csv
fields:
  category: raw_category
  segment: raw_segment
  share:
    source: raw_share
    unit: ratio
groups:
  primary: category
  secondary: segment
""",
    ),
]


def main() -> None:
    args = parse_args()
    benchmark_root = args.benchmark_root or Path(
        tempfile.mkdtemp(prefix="lab-sidecar-alpha4-fallback-benchmark-", dir="/private/tmp")
    )
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
        raise SystemExit(f"Alpha4 bounded chart fallback benchmark failed: {', '.join(failed)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Alpha4 bounded chart fallback benchmark.")
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
        fixture_dir.mkdir(parents=True)
        write_fixture(scenario, fixture_dir, scale)
        raw_context = measure_raw_context(fixture_dir / scenario.raw_filename)
        deterministic_arm = run_sidecar_arm(
            scenario=scenario,
            scenario_root=scenario_root,
            fixture_dir=fixture_dir,
            python_path=python_path,
            arm="deterministic_off",
        )
        fallback_arm = run_sidecar_arm(
            scenario=scenario,
            scenario_root=scenario_root,
            fixture_dir=fixture_dir,
            python_path=python_path,
            arm="fallback_bounded_mock",
        )
        scenarios.append(score_scenario(scenario, raw_context, deterministic_arm, fallback_arm))

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
        "fallback_allowed_reads": ALLOWED_FALLBACK_READS,
        "scenarios": scenarios,
        "aggregate": aggregate,
    }


def write_fixture(scenario: FallbackScenario, fixture_dir: Path, scale: str) -> None:
    row_scale = 1 if scale == "smoke" else 20
    writer = FIXTURE_WRITERS[scenario.scenario_id]
    writer(fixture_dir / scenario.raw_filename, row_scale)


def write_scatter_correlation(path: Path, row_scale: int) -> None:
    rows = []
    for model, offset in [("baseline", 0.0), ("candidate", 0.045)]:
        for epoch in range(1, 1 + 8 * row_scale):
            rows.append(
                {
                    "raw_epoch": epoch,
                    "raw_model": model,
                    "raw_val_accuracy": round(0.61 + epoch * 0.007 + offset, 5),
                    "raw_only_secret": raw_only_secret("scatter", model, epoch),
                }
            )
    write_csv(path, rows)


def write_heatmap_confusion_matrix(path: Path, row_scale: int) -> None:
    rows = []
    labels = ["cat", "dog", "bird", "truck"]
    for actual_index, actual in enumerate(labels):
        for predicted_index, predicted in enumerate(labels):
            count = (24 if actual == predicted else 4 + abs(actual_index - predicted_index)) * row_scale
            rows.append(
                {
                    "raw_actual": actual,
                    "raw_predicted": predicted,
                    "raw_count": count,
                    "raw_only_secret": raw_only_secret("heatmap", actual, predicted),
                }
            )
    write_csv(path, rows)


def write_histogram_distribution(path: Path, row_scale: int) -> None:
    rows = []
    for service, base in [("api", 85), ("worker", 130)]:
        for index in range(1, 1 + 24 * row_scale):
            rows.append(
                {
                    "raw_service": service,
                    "raw_latency_ms": round(base + (index % 9) * 5.5 + index * 0.15, 3),
                    "raw_only_secret": raw_only_secret("histogram", service, index),
                }
            )
    write_csv(path, rows)


def write_stacked_category_composition(path: Path, row_scale: int) -> None:
    rows = []
    categories = ["small", "medium", "large"]
    segments = [("success", 0.72), ("warning", 0.18), ("failure", 0.10)]
    for repeat in range(1, 1 + 8 * row_scale):
        for category_index, category in enumerate(categories):
            for segment, base_share in segments:
                rows.append(
                    {
                        "raw_category": category,
                        "raw_segment": segment,
                        "raw_share": round(base_share + category_index * 0.015 + repeat * 0.0001, 4),
                        "raw_only_secret": raw_only_secret("stacked", category, segment, repeat),
                    }
                )
    write_csv(path, rows)


FIXTURE_WRITERS = {
    "scatter_correlation": write_scatter_correlation,
    "heatmap_confusion_matrix": write_heatmap_confusion_matrix,
    "histogram_distribution": write_histogram_distribution,
    "stacked_category_composition": write_stacked_category_composition,
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


def run_sidecar_arm(
    scenario: FallbackScenario,
    scenario_root: Path,
    fixture_dir: Path,
    python_path: Path,
    arm: str,
) -> dict[str, Any]:
    workspace = scenario_root / arm / "workspace"
    workspace.mkdir(parents=True)
    shutil.copytree(fixture_dir, workspace / "inputs")
    metrics_config = workspace / "metrics.yaml"
    metrics_config.write_text(scenario.metrics_yaml, encoding="utf-8")
    spec_path = workspace / "figure.yaml"
    spec_path.write_text(render_spec(scenario), encoding="utf-8")

    commands: list[dict[str, Any]] = []
    context_parts: list[str] = []

    def command(args: list[str], expected_exit_codes: set[int] | None = None) -> subprocess.CompletedProcess[str]:
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
        allowed = expected_exit_codes or {0}
        if result.returncode not in allowed:
            raise RuntimeError(f"command failed: {' '.join(args)}\n{result.stdout}\n{result.stderr}")
        return result

    command(["init"])
    ingest_result = command(["ingest", "inputs", "--name", f"alpha4 fallback {scenario.scenario_id}"])
    task_id = extract_task_id(ingest_result.stdout)
    command(["collect", task_id, "--config", metrics_config.as_posix()])
    if arm == "fallback_bounded_mock":
        command(
            [
                "figures",
                task_id,
                "--spec",
                spec_path.as_posix(),
                "--fallback",
                "bounded",
                "--fallback-worker",
                "mock",
            ]
        )
    else:
        command(["figures", task_id, "--spec", spec_path.as_posix()], expected_exit_codes={5})

    task_path = workspace / ".lab-sidecar" / "tasks" / task_id
    allowed_records = read_allowed_records(task_path, include_fallback=arm == "fallback_bounded_mock")
    for record in allowed_records.values():
        context_parts.append(record["text"])
    context = "".join(context_parts)
    return {
        "arm": arm,
        "workspace": workspace.as_posix(),
        "task_id": task_id,
        "task_path": task_path.as_posix(),
        "commands_run": commands,
        "files_read": [
            {
                "path": item["relative_path"],
                "bytes": item["bytes"],
                "chars": item["chars"],
                "purpose": item["purpose"],
            }
            for item in allowed_records.values()
        ],
        "context_bytes": len(context.encode("utf-8")),
        "context_chars": len(context),
        "estimated_context_tokens": estimate_tokens(len(context)),
        "raw_metric_row_bytes_exposed": 0,
        "records": {name: item["data"] for name, item in allowed_records.items()},
    }


def read_allowed_records(task_path: Path, include_fallback: bool) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for rel_path in sorted(ALLOWED_SIDECAR_READS):
        path = task_path / rel_path
        records[rel_path] = read_record(path, rel_path, "allowed_sidecar_summary")

    if include_fallback:
        fallback = records["figures/figure-summary.json"]["data"].get("fallback")
        if isinstance(fallback, dict):
            for record_name, fallback_key in ALLOWED_FALLBACK_READS.items():
                rel_path = fallback.get(fallback_key)
                if isinstance(rel_path, str) and rel_path:
                    records[record_name] = read_record(task_path / rel_path, rel_path, "allowed_fallback_audit")
    return records


def read_record(path: Path, relative_path: str, purpose: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data: Any = json.loads(text)
    else:
        data = text
    return {
        "relative_path": relative_path,
        "bytes": path.stat().st_size,
        "chars": len(text),
        "purpose": purpose,
        "text": text,
        "data": data,
    }


def render_spec(scenario: FallbackScenario) -> str:
    lines = [
        f"figure_id: {scenario.figure_id}",
        f"chart_type: {scenario.chart_type}",
        f"title: {scenario.title}",
        f"x: {scenario.x}",
        f"y: {scenario.y}",
    ]
    if scenario.group_by:
        lines.append(f"group_by: {scenario.group_by}")
    return "\n".join(lines) + "\n"


def extract_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Imported as task: "):
            return line.split(": ", 1)[1]
        if line.startswith("Task created: "):
            return line.split(": ", 1)[1]
    raise ValueError(f"task id not found in output:\n{output}")


def score_scenario(
    scenario: FallbackScenario,
    raw_context: dict[str, Any],
    deterministic_arm: dict[str, Any],
    fallback_arm: dict[str, Any],
) -> dict[str, Any]:
    deterministic_summary = deterministic_arm["records"]["figures/figure-summary.json"]
    fallback_summary = fallback_arm["records"]["figures/figure-summary.json"]
    fallback = fallback_summary.get("fallback") if isinstance(fallback_summary.get("fallback"), dict) else {}
    figures = fallback_summary.get("generated_figures") or []
    figure = figures[0] if figures and isinstance(figures[0], dict) else {}
    traceability = fallback_arm["records"]["provenance/traceability.json"]
    validator = fallback_arm["records"].get("validator_result", {})
    adoption = fallback_arm["records"].get("adoption_record", {})

    deterministic_generated = deterministic_summary.get("generated_figures") or []
    deterministic_covered = bool(deterministic_generated)
    fallback_covered = (
        fallback.get("status") == "adopted"
        and validator.get("accepted") is True
        and figure.get("source") == "fallback"
    )
    visual = validate_visuals(fallback_arm["task_path"], figure)
    expected_fields = [scenario.x, scenario.y]
    if scenario.group_by:
        expected_fields.append(scenario.group_by)

    serialized_sidecar = json.dumps(
        {
            "deterministic_arm": deterministic_arm,
            "fallback_arm": fallback_arm,
        },
        ensure_ascii=False,
    )
    violations = boundedness_violations(serialized_sidecar, fallback_arm)
    scores = {
        "deterministic_refused_unsupported": deterministic_refused(deterministic_summary, scenario),
        "deterministic_no_official_artifact": not deterministic_covered,
        "fallback_adopted": fallback_covered,
        "coverage_improved": (not deterministic_covered) and fallback_covered,
        "chart_intent_preserved": chart_intent_preserved(figure, scenario),
        "official_artifacts_valid": visual["passed"],
        "validator_accepted": validator.get("accepted") is True,
        "adoption_record_present": adoption_record_complete(adoption, scenario),
        "traceability_lineage_complete": traceability_lineage_complete(traceability, scenario),
        "sidecar_bounded": not violations and fallback_arm["raw_metric_row_bytes_exposed"] == 0,
        "context_reduction_positive": fallback_arm["context_chars"] < raw_context["context_chars"],
    }

    return {
        "scenario_id": scenario.scenario_id,
        "expected": {
            "chart_type": scenario.chart_type,
            "x": scenario.x,
            "y": scenario.y,
            "group_by": scenario.group_by,
        },
        "raw_agent": raw_context,
        "deterministic_only": summarize_arm(deterministic_arm, deterministic_summary),
        "fallback_enabled": summarize_arm(fallback_arm, fallback_summary),
        "coverage": {
            "deterministic_covered": deterministic_covered,
            "fallback_covered": fallback_covered,
            "coverage_improved": (not deterministic_covered) and fallback_covered,
        },
        "scores": scores,
        "score_total": sum(1 for value in scores.values() if value),
        "score_max": len(scores),
        "passed": all(scores.values()),
        "context_reduction_pct": pct_reduction(raw_context["context_chars"], fallback_arm["context_chars"]),
        "visual_validation": visual,
        "violations": violations,
    }


def summarize_arm(arm: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    fallback = summary.get("fallback") if isinstance(summary.get("fallback"), dict) else {}
    figures = summary.get("generated_figures") or []
    figure = figures[0] if figures and isinstance(figures[0], dict) else {}
    return {
        "workspace": arm["workspace"],
        "task_ids": [arm["task_id"]],
        "commands_run": arm["commands_run"],
        "files_read": arm["files_read"],
        "context_bytes": arm["context_bytes"],
        "context_chars": arm["context_chars"],
        "estimated_context_tokens": arm["estimated_context_tokens"],
        "raw_metric_row_bytes_exposed": arm["raw_metric_row_bytes_exposed"],
        "fallback_status": fallback.get("status"),
        "worker_run_id": fallback.get("worker_run_id"),
        "generated_figure": {
            key: figure.get(key)
            for key in [
                "figure_id",
                "chart_type",
                "png_path",
                "svg_path",
                "x",
                "y",
                "group_by",
                "source",
                "worker_run_id",
                "validation_status",
                "field_sources",
                "fallback_lineage",
            ]
        },
    }


def deterministic_refused(summary: dict[str, Any], scenario: FallbackScenario) -> bool:
    fallback = summary.get("fallback") if isinstance(summary.get("fallback"), dict) else {}
    diagnostics = summary.get("unsupported_chart_diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        return False
    intent = diagnostics[0].get("requested_chart_intent") if isinstance(diagnostics[0], dict) else None
    return (
        summary.get("figure_count") == 0
        and fallback.get("mode") == "off"
        and fallback.get("attempted") is False
        and isinstance(intent, dict)
        and intent.get("chart_type") == scenario.chart_type
        and intent.get("x") == scenario.x
        and intent.get("y") == scenario.y
    )


def chart_intent_preserved(figure: dict[str, Any], scenario: FallbackScenario) -> bool:
    return (
        figure.get("figure_id") == scenario.figure_id
        and figure.get("chart_type") == scenario.chart_type
        and figure.get("x") == scenario.x
        and figure.get("y") == scenario.y
        and figure.get("group_by") == scenario.group_by
        and figure.get("source") == "fallback"
        and figure.get("validation_status") == "accepted"
    )


def adoption_record_complete(adoption: Any, scenario: FallbackScenario) -> bool:
    if not isinstance(adoption, dict):
        return False
    figure = adoption.get("figure")
    official = adoption.get("official_artifacts")
    fields = set(adoption.get("fields_used") or [])
    expected = {scenario.x, scenario.y}
    if scenario.group_by:
        expected.add(scenario.group_by)
    return (
        isinstance(figure, dict)
        and figure.get("figure_id") == scenario.figure_id
        and figure.get("chart_type") == scenario.chart_type
        and isinstance(official, list)
        and any(str(path).endswith("-fallback.png") for path in official)
        and any(str(path).endswith("-fallback.svg") for path in official)
        and expected.issubset(fields)
    )


def traceability_lineage_complete(traceability: dict[str, Any], scenario: FallbackScenario) -> bool:
    figure_lineage = traceability.get("figure_lineage")
    if not isinstance(figure_lineage, dict):
        return False
    fallback = figure_lineage.get("fallback")
    if not isinstance(fallback, dict) or fallback.get("status") != "adopted":
        return False
    figures = figure_lineage.get("figures")
    if not isinstance(figures, list) or not figures:
        return False
    figure = figures[0]
    fallback_lineage = figure.get("fallback_lineage")
    fields = set(fallback_lineage.get("fields_used") or []) if isinstance(fallback_lineage, dict) else set()
    expected = {scenario.x, scenario.y}
    if scenario.group_by:
        expected.add(scenario.group_by)
    return (
        figure.get("source") == "fallback"
        and figure.get("chart_type") == scenario.chart_type
        and figure.get("validation_status") == "accepted"
        and expected.issubset(fields)
        and bool(fallback.get("adoption_record_path"))
    )


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
        colors = rgb.getcolors(maxcolors=1_000_000)
        checks["color_count"] = len(colors) if colors is not None else None
        checks["nonblank"] = colors is None or len(colors) > 1

    try:
        root = ElementTree.parse(svg_path).getroot()
        tag = root.tag.rsplit("}", 1)[-1] if "}" in root.tag else root.tag
        svg_ok = tag == "svg" and svg_path.stat().st_size > 200
    except ElementTree.ParseError:
        svg_ok = False
    checks["svg_parseable"] = svg_ok
    checks["passed"] = (
        checks["png_size"][0] >= 320
        and checks["png_size"][1] >= 180
        and checks["nonblank"]
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


def boundedness_violations(serialized_sidecar: str, fallback_arm: dict[str, Any]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    if SENTINEL in serialized_sidecar:
        violations.append({"reason": "sentinel_exposed_in_sidecar_context"})
    if '"prompt":' in serialized_sidecar.lower():
        violations.append({"reason": "worker_prompt_body_key_exposed"})
    if '"response":' in serialized_sidecar.lower():
        violations.append({"reason": "worker_response_body_key_exposed"})
    if fallback_arm["raw_metric_row_bytes_exposed"]:
        violations.append({"reason": "raw_metric_rows_exposed_in_sidecar_context"})
    return violations


def aggregate_results(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    raw_chars = sum(item["raw_agent"]["context_chars"] for item in scenarios)
    fallback_chars = sum(item["fallback_enabled"]["context_chars"] for item in scenarios)
    raw_tokens = sum(item["raw_agent"]["estimated_context_tokens"] for item in scenarios)
    fallback_tokens = sum(item["fallback_enabled"]["estimated_context_tokens"] for item in scenarios)
    raw_metric_bytes = sum(item["raw_agent"]["raw_metric_row_bytes_exposed"] for item in scenarios)
    sidecar_metric_bytes = sum(item["fallback_enabled"]["raw_metric_row_bytes_exposed"] for item in scenarios)
    deterministic_covered = sum(1 for item in scenarios if item["coverage"]["deterministic_covered"])
    fallback_covered = sum(1 for item in scenarios if item["coverage"]["fallback_covered"])
    return {
        "scenario_count": len(scenarios),
        "passed_count": sum(1 for item in scenarios if item["passed"]),
        "passed": all(item["passed"] for item in scenarios),
        "deterministic_covered_count": deterministic_covered,
        "fallback_covered_count": fallback_covered,
        "coverage_delta": fallback_covered - deterministic_covered,
        "raw_context_chars": raw_chars,
        "sidecar_context_chars": fallback_chars,
        "context_reduction_pct": pct_reduction(raw_chars, fallback_chars),
        "raw_estimated_tokens": raw_tokens,
        "sidecar_estimated_tokens": fallback_tokens,
        "token_reduction_pct": pct_reduction(raw_tokens, fallback_tokens),
        "raw_metric_row_bytes_exposed": raw_metric_bytes,
        "sidecar_raw_metric_row_bytes_exposed": sidecar_metric_bytes,
        "raw_metric_exposure_reduction_pct": pct_reduction(raw_metric_bytes, sidecar_metric_bytes),
        "sidecar_violation_count": sum(len(item["violations"]) for item in scenarios),
        "score_total": sum(item["score_total"] for item in scenarios),
        "score_max": sum(item["score_max"] for item in scenarios),
    }


def render_report(data: dict[str, Any]) -> str:
    lines = [
        "# Alpha4 Bounded Chart Fallback Benchmark",
        "",
        f"Date: {data['date']}",
        "",
        "## Methodology",
        "",
        "This benchmark creates fallback-only chart requests that deterministic `line`, `bar`, and `box` planning intentionally does not cover. Each scenario is run twice: first with fallback off to confirm deterministic refusal, then with `--fallback bounded --fallback-worker mock` to validate and adopt a sandboxed fallback artifact.",
        "",
        "The sidecar arm reads only bounded task-local summaries, fallback request metadata, validator results, adoption records, and traceability. It does not read full raw source files, full normalized metric rows, full logs, worker prompt/response bodies, or sandbox proposal bodies.",
        "",
        "Token counts use the deterministic proxy `ceil(chars / 4)`.",
        "",
        "## Scenario Results",
        "",
        "| Scenario | Unsupported request | Deterministic covered | Fallback covered | Score | Passed | Context reduction |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ]
    for item in data["scenarios"]:
        expected = item["expected"]
        request = f"{expected['chart_type']} {expected['x']}/{expected['y']}/{display_null(expected['group_by'])}"
        lines.append(
            "| {scenario} | {request} | {deterministic} | {fallback} | {score}/{score_max} | {passed} | {reduction:.2f}% |".format(
                scenario=item["scenario_id"],
                request=request,
                deterministic=1 if item["coverage"]["deterministic_covered"] else 0,
                fallback=1 if item["coverage"]["fallback_covered"] else 0,
                score=item["score_total"],
                score_max=item["score_max"],
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
            "| Scenarios | Deterministic covered | Fallback covered | Coverage delta | Raw chars | Sidecar chars | Context reduction | Score | Violations |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| {scenarios} | {det} | {fallback} | {delta} | {raw_chars} | {sidecar_chars} | {ctx:.2f}% | {score}/{score_max} | {violations} |".format(
                scenarios=aggregate["scenario_count"],
                det=aggregate["deterministic_covered_count"],
                fallback=aggregate["fallback_covered_count"],
                delta=aggregate["coverage_delta"],
                raw_chars=aggregate["raw_context_chars"],
                sidecar_chars=aggregate["sidecar_context_chars"],
                ctx=aggregate["context_reduction_pct"],
                score=aggregate["score_total"],
                score_max=aggregate["score_max"],
                violations=aggregate["sidecar_violation_count"],
            ),
            "",
            "## Boundedness",
            "",
            f"- Sidecar raw metric row exposure: `{aggregate['sidecar_raw_metric_row_bytes_exposed']}` bytes.",
            f"- Sidecar violation count: `{aggregate['sidecar_violation_count']}`.",
            "- Fallback request, validator, adoption, summary, and traceability records are included as bounded evidence.",
            "- Worker prompt/response bodies and sandbox proposal bodies are not included in the sidecar context arm.",
            "",
            "## Acceptance Status",
            "",
            "Passed." if aggregate["passed"] else "Failed.",
            "",
            "## Limitations",
            "",
            "- The benchmark uses the local mock chart fallback worker to exercise validator and adoption mechanics; it does not evaluate an AI provider.",
            "- Visual validation checks parseability, size, and nonblank output. It does not grade chart design quality.",
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
                "score_max": item["score_max"],
                "deterministic_covered": item["coverage"]["deterministic_covered"],
                "fallback_covered": item["coverage"]["fallback_covered"],
                "context_reduction_pct": item["context_reduction_pct"],
            }
            for item in data["scenarios"]
        ],
    }


if __name__ == "__main__":
    main()
