from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

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


def _state_snapshot(workspace: Path) -> dict[str, tuple[int, int]]:
    state = workspace / ".lab-sidecar"
    if not state.exists():
        return {}
    return {
        path.relative_to(state).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }


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


def test_comparison_report_formatting_is_descriptive_and_evidence_bounded(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a", task_name="baseline|pipe")
    second = _create_collected_task(tmp_path, "run-b", task_name="model-a")

    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])

    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    comparison_path = _comparison_path(tmp_path, comparison_id)
    report_text = (comparison_path / "reports" / "comparison-report-fragment.md").read_text(encoding="utf-8")
    summary = json.loads((comparison_path / "comparison-summary.json").read_text(encoding="utf-8"))
    report_summary = json.loads((comparison_path / "reports" / "comparison-report-summary.json").read_text(encoding="utf-8"))

    for heading in [
        "## Source Tasks",
        "## Row Selection",
        "## Comparison Table",
        "## Evidence Paths",
        "## Omitted And Skipped",
        "## Omitted By Default",
    ]:
        assert heading in report_text
    assert "baseline\\|pipe" in report_text
    assert "This comparison is descriptive only; no statistical significance or model superiority is inferred." in report_text
    assert "Comparison table CSV: `comparison-table.csv`" in report_text
    assert "Source metrics:" in report_text
    assert f"`{first}`" in report_text
    assert "metrics/normalized_metrics.csv" in report_text
    assert report_summary["non_claim_note"].startswith("This comparison is descriptive only")
    assert summary["metrics"]
    assert "epoch,val_accuracy,val_loss" not in report_text
    for fragment in ["winner", "is superior", "statistically significant result", "deployment-ready", "AI-written conclusion"]:
        assert fragment not in report_text


def test_list_comparisons_empty_workspace(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    before = _state_snapshot(tmp_path)

    result = invoke(tmp_path, ["list-comparisons"])

    assert result.exit_code == 0
    assert result.output.strip() == "No comparisons found."
    assert _state_snapshot(tmp_path) == before


def test_list_comparisons_shows_saved_records_counts_and_limit(tmp_path: Path) -> None:
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
    first_result = invoke(
        tmp_path,
        ["compare", first, second, "--save", "--name", "baseline-vs-model-a", "--figures", "--report"],
    )
    assert first_result.exit_code == 0, first_result.output
    first_comparison = _comparison_id(first_result.output)
    second_result = invoke(tmp_path, ["compare", first, second, "--save", "--name", "second-comparison"])
    assert second_result.exit_code == 0, second_result.output
    second_comparison = _comparison_id(second_result.output)
    before = _state_snapshot(tmp_path)

    listing = invoke(tmp_path, ["list-comparisons"])
    limited = invoke(tmp_path, ["list-comparisons", "--limit", "1"])

    assert listing.exit_code == 0, listing.output
    assert "comparison_id" in listing.output
    assert "name" in listing.output
    assert "created_at" in listing.output
    assert "source_tasks" in listing.output
    assert "artifacts" in listing.output
    assert "figures" in listing.output
    assert "report" in listing.output
    assert first_comparison in listing.output
    assert "baseline-vs-model-a" in listing.output
    assert second_comparison in listing.output
    assert "second-comparison" in listing.output
    assert first in listing.output
    assert second in listing.output

    assert limited.exit_code == 0, limited.output
    limited_rows = [line for line in limited.output.splitlines() if line.startswith("comparison_20")]
    assert len(limited_rows) == 1
    assert second_comparison in limited.output
    assert first_comparison not in limited.output
    assert _state_snapshot(tmp_path) == before


def test_list_comparisons_bounds_long_names(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    long_name = "comparison-" + ("very-long-name-" * 20)
    result = invoke(tmp_path, ["compare", first, second, "--save", "--name", long_name])
    assert result.exit_code == 0, result.output
    before = _state_snapshot(tmp_path)

    listing = invoke(tmp_path, ["list-comparisons", "--limit", "1"])

    assert listing.exit_code == 0, listing.output
    assert long_name not in listing.output
    assert "..." in listing.output
    assert _state_snapshot(tmp_path) == before


def test_open_comparison_prints_absolute_path_and_rejects_missing_or_escaped_ids(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    before = _state_snapshot(tmp_path)

    opened = invoke(tmp_path, ["open-comparison", comparison_id])
    missing = invoke(tmp_path, ["open-comparison", "comparison_20260101_000000_deadbe"])
    escaped = invoke(tmp_path, ["open-comparison", "../escape"])

    assert opened.exit_code == 0
    assert opened.output.strip() == str(_comparison_path(tmp_path, comparison_id).resolve())
    assert missing.exit_code == 3
    assert "was not found" in missing.output
    assert "list-comparisons" in missing.output
    assert escaped.exit_code == 2
    assert "invalid comparison id" in escaped.output
    assert _state_snapshot(tmp_path) == before


def test_open_comparison_rejects_symlink_escape_for_valid_id(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    comparison_root = tmp_path / ".lab-sidecar" / "comparisons"
    comparison_root.mkdir()
    escaped_target = tmp_path / "outside-comparison"
    escaped_target.mkdir()
    comparison_id = "comparison_20260101_000000_abcdef"
    (escaped_target / "comparison-manifest.json").write_text(
        json.dumps(
            {
                "comparison_id": comparison_id,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "task_ids": ["task_a", "task_b"],
                "paths": {},
            }
        ),
        encoding="utf-8",
    )
    try:
        (comparison_root / comparison_id).symlink_to(escaped_target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is not available: {exc}")
    before = (escaped_target / "comparison-manifest.json").stat().st_mtime_ns

    opened = invoke(tmp_path, ["open-comparison", comparison_id])
    listed = invoke(tmp_path, ["list-comparisons", "--limit", "1"])

    assert opened.exit_code == 2
    assert "invalid comparison id" in opened.output
    assert listed.exit_code == 0
    assert "No comparisons found." in listed.output
    assert "Traceback" not in listed.output
    assert "Warning: skipped damaged comparison manifest" not in listed.output
    assert (escaped_target / "comparison-manifest.json").stat().st_mtime_ns == before


def test_comparison_artifacts_lists_paths_without_bodies_and_is_read_only(tmp_path: Path) -> None:
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
    result = invoke(tmp_path, ["compare", first, second, "--save", "--figures", "--report"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    before = _state_snapshot(tmp_path)

    artifacts = invoke(tmp_path, ["comparison-artifacts", comparison_id])
    escaped = invoke(tmp_path, ["comparison-artifacts", "../escape"])
    missing = invoke(tmp_path, ["comparison-artifacts", "comparison_20260101_000000_deadbe"])

    assert artifacts.exit_code == 0, artifacts.output
    for expected in [
        "comparison-manifest.json",
        "comparison-summary.json",
        "comparison-table.csv",
        "comparison-table.json",
        "figures/figure-summary.json",
        "reports/comparison-report-fragment.md",
        "reports/comparison-report-summary.json",
        "provenance/traceability.json",
    ]:
        assert expected in artifacts.output
    assert "figures/comparison_val_accuracy.png" in artifacts.output
    assert "figures/comparison_val_accuracy.svg" in artifacts.output
    assert "val_accuracy, val_loss" not in artifacts.output
    assert "This comparison is descriptive only" not in artifacts.output
    assert first not in artifacts.output
    assert second not in artifacts.output
    assert escaped.exit_code == 2
    assert "invalid comparison id" in escaped.output
    assert missing.exit_code == 3
    assert "was not found" in missing.output
    assert _state_snapshot(tmp_path) == before


def test_list_comparisons_warns_on_damaged_manifest_without_traceback(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    comparison_root = tmp_path / ".lab-sidecar" / "comparisons"
    damaged_id = "comparison_20260101_000000_badbad"
    damaged_dir = comparison_root / damaged_id
    damaged_dir.mkdir(parents=True)
    (damaged_dir / "comparison-manifest.json").write_text("{not-json\n", encoding="utf-8")
    before = _state_snapshot(tmp_path)

    result = invoke(tmp_path, ["list-comparisons"])

    assert result.exit_code == 0
    assert "No comparisons found." in result.output
    assert "Warning: skipped damaged comparison manifest" in result.output
    assert damaged_id in result.output
    assert "Traceback" not in result.output
    assert _state_snapshot(tmp_path) == before


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


def test_validate_comparison_missing_artifacts_show_next_actions(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)

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

    assert validate.exit_code == 5
    assert "[fail] figures:" in validate.output
    assert "--save --figures creates a fresh saved comparison" in validate.output
    assert "[fail] report:" in validate.output
    assert "--save --report creates a fresh saved comparison" in validate.output
    assert "[fail] package-ready:" in validate.output
    assert "--save --figures --report to create a fresh saved comparison" in validate.output
    assert "Traceback" not in validate.output


def test_validate_comparison_detects_tampered_positive_claim(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    first = _create_collected_task(tmp_path, "run-a")
    second = _create_collected_task(tmp_path, "run-b")
    result = invoke(tmp_path, ["compare", first, second, "--save", "--report"])
    assert result.exit_code == 0, result.output
    comparison_id = _comparison_id(result.output)
    report_path = _comparison_path(tmp_path, comparison_id) / "reports" / "comparison-report-fragment.md"
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\nThis result is statistically significant and superior.\n",
        encoding="utf-8",
    )

    validate = invoke(tmp_path, ["validate-comparison", comparison_id, "--require", "report"])

    assert validate.exit_code == 5
    assert "report contains forbidden claim fragment: statistically significant" in validate.output
    assert "report contains forbidden claim fragment: superior" in validate.output
    assert "This comparison is descriptive only" not in validate.output


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
