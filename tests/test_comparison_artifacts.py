from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from tests.test_cli_smoke import extract_task_id, invoke


def _write_metric_source(workspace: Path, name: str, rows: list[dict[str, str]]) -> None:
    source = workspace / name
    source.mkdir()
    fields = list(rows[0])
    with (source / "metrics.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _create_collected_task(
    workspace: Path,
    source_name: str,
    *,
    task_name: str | None = None,
    rows: list[dict[str, str]] | None = None,
) -> str:
    _write_metric_source(
        workspace,
        source_name,
        rows
        or [
            {"epoch": "1", "val_accuracy": "0.70", "val_loss": "0.50", "seed": "1"},
            {"epoch": "2", "val_accuracy": "0.80", "val_loss": "0.40", "seed": "1"},
        ],
    )
    args = ["ingest", source_name]
    if task_name:
        args.extend(["--name", task_name])
    task_id = extract_task_id(invoke(workspace, args).output)
    collect = invoke(workspace, ["collect", task_id])
    assert collect.exit_code == 0, collect.output
    return task_id


def _comparison_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Comparison created: "):
            return line.split(": ", 1)[1].strip()
    raise AssertionError(f"No comparison id in output:\n{output}")


def _comparison_path(workspace: Path, comparison_id: str) -> Path:
    return workspace / ".lab-sidecar" / "comparisons" / comparison_id


def test_compare_legacy_print_remains_compatible(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a", task_name="baseline")
    second = _create_collected_task(
        tmp_path,
        "run-b",
        task_name="model-a",
        rows=[
            {"epoch": "1", "val_accuracy": "0.72", "val_loss": "0.48", "seed": "2"},
            {"epoch": "2", "val_accuracy": "0.85", "val_loss": "0.35", "seed": "2"},
        ],
    )

    result = invoke(tmp_path, ["compare", first, second])

    assert result.exit_code == 0
    assert "Compared tasks: 2" in result.output
    assert "Common numeric fields:" in result.output
    assert "task_id" in result.output
    assert "val_accuracy" in result.output
    assert "Comparison created:" not in result.output
    assert not (tmp_path / ".lab-sidecar" / "comparisons").exists()


def test_compare_rejects_duplicate_task_ids_and_more_than_five_tasks(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = _create_collected_task(tmp_path, "run-a")

    legacy_duplicate = invoke(tmp_path, ["compare", task_id, task_id])
    saved_duplicate = invoke(tmp_path, ["compare", task_id, task_id, "--save"])
    too_many = invoke(tmp_path, ["compare", task_id, task_id, task_id, task_id, task_id, task_id, "--save"])

    assert legacy_duplicate.exit_code == 2
    assert "duplicate task ids are not allowed" in legacy_duplicate.output
    assert saved_duplicate.exit_code == 2
    assert "duplicate task ids are not allowed" in saved_duplicate.output
    assert too_many.exit_code == 2
    assert "at most 5 task ids" in too_many.output
    assert not (tmp_path / ".lab-sidecar" / "comparisons").exists()


def test_compare_save_generates_bounded_artifacts_figures_report_validate_and_package(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a", task_name="baseline")
    second = _create_collected_task(
        tmp_path,
        "run-b",
        task_name="model-a",
        rows=[
            {"epoch": "1", "val_accuracy": "0.72", "val_loss": "0.48", "seed": "2"},
            {"epoch": "2", "val_accuracy": "0.85", "val_loss": "0.35", "seed": "2"},
        ],
    )

    result = invoke(
        tmp_path,
        [
            "compare",
            first,
            second,
            "--save",
            "--name",
            "baseline-vs-model-a",
            "--figures",
            "--report",
        ],
    )

    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    comparison_path = _comparison_path(tmp_path, comparison_id)
    assert f"Artifacts: .lab-sidecar/comparisons/{comparison_id}" in result.output
    for relative in [
        "comparison-manifest.json",
        "comparison-summary.json",
        "comparison-table.csv",
        "comparison-table.json",
        "figures/figure-summary.json",
        "reports/comparison-report-fragment.md",
        "reports/comparison-report-summary.json",
        "provenance/traceability.json",
    ]:
        assert (comparison_path / relative).is_file(), relative
    assert list((comparison_path / "figures").glob("*.png"))
    assert list((comparison_path / "figures").glob("*.svg"))

    manifest = json.loads((comparison_path / "comparison-manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((comparison_path / "comparison-summary.json").read_text(encoding="utf-8"))
    traceability = json.loads((comparison_path / "provenance" / "traceability.json").read_text(encoding="utf-8"))
    report_text = (comparison_path / "reports" / "comparison-report-fragment.md").read_text(encoding="utf-8")
    serialized = json.dumps(summary, ensure_ascii=False)

    assert manifest["comparison_id"] == comparison_id
    assert manifest["task_ids"] == [first, second]
    assert summary["name"] == "baseline-vs-model-a"
    assert summary["row_selection"]["method"] == "final_row"
    assert "val_accuracy" in summary["common_numeric_fields"]
    assert "val_loss" in summary["common_numeric_fields"]
    assert "epoch" not in summary["common_numeric_fields"]
    assert "seed" not in summary["common_numeric_fields"]
    assert all("full_metric_rows" not in json.dumps(item) for item in summary["metrics"])
    assert "epoch,val_accuracy,val_loss" not in serialized
    assert "Best val_accuracy" not in serialized
    assert "This comparison is descriptive only" in report_text
    assert "deployment-ready" not in report_text
    assert traceability["comparison_id"] == comparison_id
    assert "source_metrics" in traceability["metric_lineage"]
    assert any(item["path"] == "comparison-table.csv" for item in traceability["artifacts"])

    validate = invoke(
        tmp_path,
        [
            "validate-comparison",
            comparison_id,
            "--require",
            "figures",
            "--require",
            "report",
            "--require",
            "package-ready",
        ],
    )
    assert validate.exit_code == 0, validate.output
    assert "Result: ok" in validate.output
    assert "[ok] package-ready:" in validate.output

    package_path = tmp_path / f"pkg-{comparison_id}"
    package_result = invoke(tmp_path, ["package-comparison", comparison_id, "--output", package_path.as_posix()])
    assert package_result.exit_code == 0, package_result.output
    assert "Type: comparison" in package_result.output
    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])
    assert verify.exit_code == 0, verify.output

    package_index = json.loads((package_path / "artifact-index.json").read_text(encoding="utf-8"))
    included_paths = {item["package_path"] for item in package_index["included"]}
    omitted_paths = {item["path"] for item in package_index["omitted"]}
    assert "comparison-summary.json" in included_paths
    assert "comparison-table.csv" in included_paths
    assert "provenance/traceability.json" in included_paths
    assert ".lab-sidecar/tasks/*/stdout.log" in omitted_paths
    assert ".lab-sidecar/tasks/*/stderr.log" in omitted_paths
    assert ".lab-sidecar/tasks/*/metrics/normalized_metrics.csv" in omitted_paths
    assert ".lab-sidecar/tasks/*/intelligence" in omitted_paths
    assert ".lab-sidecar/tasks/*/intelligence/*/sandbox" in omitted_paths
    assert not (package_path / "stdout.log").exists()
    assert not (package_path / "stderr.log").exists()
    assert not (package_path / "raw").exists()


def test_compare_save_supports_three_to_five_tasks(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_ids = [
        _create_collected_task(
            tmp_path,
            f"run-{index}",
            rows=[
                {"epoch": "1", "score": f"0.{70 + index}", "latency_ms": str(40 + index), "seed": str(index)},
                {"epoch": "2", "score": f"0.{75 + index}", "latency_ms": str(35 + index), "seed": str(index)},
            ],
        )
        for index in range(5)
    ]

    result = invoke(tmp_path, ["compare", *task_ids, "--save"])

    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    summary = json.loads((_comparison_path(tmp_path, comparison_id) / "comparison-summary.json").read_text(encoding="utf-8"))
    assert summary["task_ids"] == task_ids
    assert set(summary["common_numeric_fields"]) == {"score", "latency_ms"}
    assert len(summary["source_tasks"]) == 5


def test_compare_save_missing_metrics_and_no_common_numeric_fail(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    metric_task = _create_collected_task(tmp_path, "run-a")
    missing_source = tmp_path / "missing"
    missing_source.mkdir()
    (missing_source / "notes.txt").write_text("no metrics\n", encoding="utf-8")
    missing_task = extract_task_id(invoke(tmp_path, ["ingest", "missing"]).output)

    missing = invoke(tmp_path, ["compare", metric_task, missing_task, "--save"])

    assert missing.exit_code == 5
    assert "metrics/normalized_metrics.csv is missing" in missing.output
    assert "labsidecar collect <task_id>" in missing.output

    first_text = _create_collected_task(
        tmp_path,
        "text-a",
        rows=[{"model": "alpha", "label": "good"}],
    )
    second_text = _create_collected_task(
        tmp_path,
        "text-b",
        rows=[{"model": "beta", "label": "better"}],
    )

    no_common = invoke(tmp_path, ["compare", first_text, second_text, "--save"])

    assert no_common.exit_code == 5
    assert "no common numeric metric fields" in no_common.output
    assert not (tmp_path / ".lab-sidecar" / "comparisons").exists()


def test_compare_excludes_non_finite_and_metadata_fields(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(
        tmp_path,
        "run-a",
        rows=[
            {
                "epoch": "1",
                "step": "10",
                "run_id": "101",
                "config_id": "201",
                "checkpoint": "5",
                "score": "0.80",
                "loss": "nan",
                "latency_ms": "32",
            }
        ],
    )
    second = _create_collected_task(
        tmp_path,
        "run-b",
        rows=[
            {
                "epoch": "1",
                "step": "10",
                "run_id": "102",
                "config_id": "202",
                "checkpoint": "5",
                "score": "0.82",
                "loss": "inf",
                "latency_ms": "30",
            }
        ],
    )

    result = invoke(tmp_path, ["compare", first, second, "--save"])

    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    summary = json.loads((_comparison_path(tmp_path, comparison_id) / "comparison-summary.json").read_text(encoding="utf-8"))
    table = json.loads((_comparison_path(tmp_path, comparison_id) / "comparison-table.json").read_text(encoding="utf-8"))
    assert set(summary["common_numeric_fields"]) == {"score", "latency_ms"}
    assert "loss" not in summary["common_numeric_fields"]
    for field in ["epoch", "step", "run_id", "config_id", "checkpoint"]:
        assert field not in summary["common_numeric_fields"]
        assert field in summary["skipped_fields"]["excluded_metadata_fields"]
    assert {row["metric"] for row in table["rows"]} == {"score", "latency_ms"}


def test_compare_failed_task_with_metrics_is_descriptive_with_warning(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    script = tmp_path / "write_then_fail.py"
    script.write_text(
        "from pathlib import Path\n"
        "Path('metrics.csv').write_text('epoch,val_accuracy,val_loss\\n1,0.77,0.45\\n', encoding='utf-8')\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    failed_task = extract_task_id(invoke(tmp_path, ["run", f'"{sys.executable}" {script.name}']).output)
    collect = invoke(tmp_path, ["collect", failed_task])
    assert collect.exit_code == 0, collect.output

    result = invoke(tmp_path, ["compare", first, failed_task, "--save"])

    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    summary = json.loads((_comparison_path(tmp_path, comparison_id) / "comparison-summary.json").read_text(encoding="utf-8"))
    assert f"source task {failed_task} status is failed" in summary["warnings"]


def test_validate_comparison_detects_stale_source_metrics_and_package_verify_tamper(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)

    source_metrics = tmp_path / ".lab-sidecar" / "tasks" / first / "metrics" / "normalized_metrics.csv"
    source_metrics.write_text(source_metrics.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale = invoke(tmp_path, ["validate-comparison", comparison_id])

    assert stale.exit_code == 5
    assert "source metrics digest changed" in stale.output

    # Restore by making a fresh comparison package and then tamper with it.
    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])
    comparison_id = _comparison_id(result.output)
    package_path = tmp_path / f"pkg-{comparison_id}"
    assert invoke(tmp_path, ["package-comparison", comparison_id, "--output", package_path.as_posix()]).exit_code == 0
    report_path = package_path / "reports" / "comparison-report-fragment.md"
    report_path.write_text(report_path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "sha256 mismatch for reports/comparison-report-fragment.md" in verify.output


def test_validate_and_package_comparison_reject_invalid_ids_and_manifest_mismatch(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)

    for args in [
        ["validate-comparison", "../outside"],
        ["package-comparison", "../outside", "--output", "pkg-outside"],
    ]:
        invalid = invoke(tmp_path, args)
        assert invalid.exit_code == 2
        assert "invalid comparison id" in invalid.output

    manifest_path = _comparison_path(tmp_path, comparison_id) / "comparison-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["comparison_id"] = "comparison_20260101_000000_deadbe"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validate = invoke(tmp_path, ["validate-comparison", comparison_id])
    package = invoke(tmp_path, ["package-comparison", comparison_id, "--output", "pkg-mismatch"])

    assert validate.exit_code == 5
    assert "manifest comparison_id" in validate.output
    assert package.exit_code == 2
    assert "does not match requested id" in package.output


def test_validate_comparison_rejects_escaped_internal_paths(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    comparison_path = _comparison_path(tmp_path, comparison_id)

    figure_summary_path = comparison_path / "figures" / "figure-summary.json"
    figure_summary = json.loads(figure_summary_path.read_text(encoding="utf-8"))
    figure_summary["figures"][0]["png_path"] = "../outside.png"
    figure_summary_path.write_text(json.dumps(figure_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    traceability_path = comparison_path / "provenance" / "traceability.json"
    traceability = json.loads(traceability_path.read_text(encoding="utf-8"))
    traceability["artifacts"].append(
        {
            "artifact_id": "escaped",
            "type": "table",
            "path": "../comparison-table.csv",
            "description": "escaped path",
            "source_paths": [],
            "exists": True,
            "size_bytes": 1,
            "sha256": "x",
        }
    )
    traceability_path.write_text(json.dumps(traceability, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validate = invoke(tmp_path, ["validate-comparison", comparison_id, "--require", "figures"])

    assert validate.exit_code == 5
    assert "figure png_path escapes comparison directory" in validate.output
    assert "traceability artifact path escapes comparison directory" in validate.output


def test_validate_comparison_rejects_escaped_source_metrics_path(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    manifest_path = _comparison_path(tmp_path, comparison_id) / "comparison-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_tasks"][0]["metrics_path"] = "../outside.csv"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validate = invoke(tmp_path, ["validate-comparison", comparison_id])

    assert validate.exit_code == 5
    assert "source metrics path escapes .lab-sidecar/tasks" in validate.output


def test_package_verify_detects_tampered_comparison_summary(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    package_path = tmp_path / f"pkg-{comparison_id}"
    assert invoke(tmp_path, ["package-comparison", comparison_id, "--output", package_path.as_posix()]).exit_code == 0
    summary_path = package_path / "comparison-summary.json"
    summary_path.write_text(summary_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "sha256 mismatch for comparison-summary.json" in verify.output
