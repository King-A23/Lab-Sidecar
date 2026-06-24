from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.traceability import refresh_traceability
from tests.test_cli_smoke import (
    assert_traceability_is_bounded,
    copy_examples,
    extract_task_id,
    invoke,
    read_traceability,
)


REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "task_id",
    "generated_at",
    "task",
    "environment",
    "sources",
    "artifacts",
    "metric_lineage",
    "figure_lineage",
    "report_lineage",
    "slide_lineage",
    "claim_traces",
    "omitted",
    "traceability_artifact",
    "warnings",
}
REQUIRED_TASK_KEYS = {
    "mode",
    "status",
    "working_dir",
    "manifest_path",
    "command_path",
    "run_spec_path",
    "run_mode",
    "argv",
    "safe_profile",
    "source_path",
}
REQUIRED_ENVIRONMENT_KEYS = {
    "python_executable",
    "env_path",
    "git_path",
    "dependencies_path",
}
REQUIRED_ARTIFACT_KEYS = {
    "artifact_id",
    "type",
    "path",
    "description",
    "source_paths",
    "exists",
    "size_bytes",
    "sha256",
}
OPTIONAL_ARTIFACT_KEYS = {"digest_omitted_reason"}
REQUIRED_SOURCE_KEYS = {"path", "role", "size_bytes", "sha256"}
OPTIONAL_SOURCE_KEYS = {
    "file_type",
    "row_count",
    "detected_fields",
    "mapped_fields",
    "origin",
    "suffix",
    "source_type",
    "name",
}
REQUIRED_METRIC_LINEAGE_KEYS = {
    "present",
    "path",
    "json_path",
    "collection_summary_path",
    "scenario_summary_path",
    "scenario_type",
    "primary_metric",
    "scenario_claim_limit",
    "row_count",
    "columns",
    "detected_fields",
    "source_files",
    "output_files",
}
REQUIRED_FIGURE_LINEAGE_KEYS = {
    "present",
    "summary_path",
    "spec_path",
    "figure_count",
    "figures",
    "unsupported_chart_diagnostics",
    "fallback",
    "warnings",
    "errors",
}
REQUIRED_FIGURE_ITEM_KEYS = {
    "figure_id",
    "chart_type",
    "source",
    "worker_run_id",
    "validation_status",
    "artifact_ids",
    "paths",
    "source_metrics",
    "columns",
    "units",
    "field_sources",
    "fallback_lineage",
}
EXPECTED_FALLBACK_LINEAGE_KEYS = {
    "source_metrics",
    "fields_used",
    "field_sources",
    "worker_run_id",
    "request_path",
    "worker_request_path",
    "worker_result_path",
    "validator_result_path",
    "sandbox_png_path",
    "sandbox_svg_path",
    "adopted_png_path",
    "adopted_svg_path",
}
EXPECTED_FALLBACK_KEYS = {
    "mode",
    "attempted",
    "worker_run_id",
    "status",
    "request_path",
    "validator_result_path",
    "adoption_record_path",
    "validation_status",
    "validation_checks",
    "adopted_figures",
    "adopted_artifact_paths",
    "diagnostics",
}
REQUIRED_REPORT_LINEAGE_KEYS = {
    "present",
    "path",
    "summary_path",
    "template",
    "source_artifacts",
    "claim_trace_count",
    "claim_ids",
}
REQUIRED_SLIDE_LINEAGE_KEYS = {
    "present",
    "pptx_path",
    "summary_path",
    "template",
    "slide_count",
    "slides",
    "included_figures",
    "metrics",
}
REQUIRED_SLIDE_METRICS_KEYS = {"present", "path", "row_count", "key_columns", "numeric_columns"}
REQUIRED_SLIDE_ITEM_KEYS = {
    "slide_index",
    "title",
    "purpose",
    "source_artifacts",
    "evidence",
    "empty_source_reason",
}
REQUIRED_CLAIM_TRACE_KEYS = {"claim_id", "surface", "claim_type", "value", "evidence"}
OPTIONAL_CLAIM_TRACE_KEYS = {"field", "operation"}
REQUIRED_OMITTED_KEYS = {"path", "category", "reason"}
REQUIRED_TRACEABILITY_ARTIFACT_KEYS = {"artifact_id", "path", "self_digest_note"}
STATUS_VALUES = {"pending", "running", "completed", "failed", "cancelled"}
FORBIDDEN_REFERENCE_ONLY_FRAGMENTS = (
    "# 实验报告片段",
    "# 失败实验报告片段",
    "# 取消实验报告片段",
    "## 实验概览",
    "## 失败概览",
    "## 取消概览",
    "ppt/presentation.xml",
    "<p:sld",
    '"prompt":"secret"',
    '"response":"secret"',
    "worker transcript body\n",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_path(workspace: Path, task_id: str) -> Path:
    return workspace / ".lab-sidecar" / "tasks" / task_id


def _resolve_task_or_workspace_path(workspace: Path, task_id: str, path_text: str) -> Path:
    path = Path(path_text)
    task_path = _task_path(workspace, task_id)
    if path.is_absolute():
        return path
    if (task_path / path).exists():
        return task_path / path
    return workspace / path


def _assert_traceability_contract(
    traceability: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
    expected_mode: str,
    expected_status: str,
    metric_present: bool,
    figure_present: bool,
    report_present: bool,
    slide_present: bool,
) -> None:
    task_path = _task_path(workspace, expected_task_id)

    assert REQUIRED_TOP_LEVEL_KEYS <= set(traceability)
    assert traceability["schema_version"] == "1"
    assert traceability["task_id"] == expected_task_id
    assert isinstance(traceability["generated_at"], str) and traceability["generated_at"]

    _assert_task_section(
        traceability["task"],
        workspace=workspace,
        expected_task_id=expected_task_id,
        expected_mode=expected_mode,
        expected_status=expected_status,
    )
    _assert_environment_section(traceability["environment"], task_path=task_path)
    _assert_sources(traceability["sources"], workspace=workspace, expected_task_id=expected_task_id)
    _assert_artifacts(traceability["artifacts"], workspace=workspace, expected_task_id=expected_task_id)
    _assert_metric_lineage(
        traceability["metric_lineage"],
        workspace=workspace,
        expected_task_id=expected_task_id,
        expected_present=metric_present,
    )
    _assert_figure_lineage(
        traceability["figure_lineage"],
        workspace=workspace,
        expected_task_id=expected_task_id,
        expected_present=figure_present,
    )
    _assert_report_lineage(
        traceability["report_lineage"],
        workspace=workspace,
        expected_task_id=expected_task_id,
        expected_present=report_present,
    )
    _assert_slide_lineage(
        traceability["slide_lineage"],
        workspace=workspace,
        expected_task_id=expected_task_id,
        expected_present=slide_present,
    )
    _assert_claim_traces(traceability["claim_traces"], workspace=workspace, expected_task_id=expected_task_id)
    _assert_omitted(traceability["omitted"])
    _assert_traceability_artifact(traceability["traceability_artifact"])
    _assert_traceability_is_reference_only(traceability)
    assert_traceability_is_bounded(traceability)


def _assert_task_section(
    task: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
    expected_mode: str,
    expected_status: str,
) -> None:
    assert set(task) == REQUIRED_TASK_KEYS
    assert task["mode"] == expected_mode
    assert task["status"] == expected_status
    assert task["status"] in STATUS_VALUES
    assert isinstance(task["working_dir"], str) and task["working_dir"]
    assert task["manifest_path"] == "manifest.json"
    assert (_task_path(workspace, expected_task_id) / task["manifest_path"]).is_file()
    assert task["command_path"] in {None, "reproduce/command.txt"}
    if task["command_path"] is not None:
        assert (_task_path(workspace, expected_task_id) / task["command_path"]).is_file()
    assert task["run_spec_path"] in {None, "reproduce/run.json"}
    if task["run_spec_path"] is not None:
        assert (_task_path(workspace, expected_task_id) / task["run_spec_path"]).is_file()
    if expected_mode == "run":
        assert task["run_mode"] in {"shell", "argv"}
    else:
        assert task["run_mode"] is None
    if task["argv"] is not None:
        assert isinstance(task["argv"], list)
        assert all(isinstance(value, str) for value in task["argv"])
    assert task["safe_profile"] is None or isinstance(task["safe_profile"], str)
    assert task["source_path"] is None or isinstance(task["source_path"], str)


def _assert_environment_section(environment: dict[str, Any], *, task_path: Path) -> None:
    assert set(environment) == REQUIRED_ENVIRONMENT_KEYS
    assert isinstance(environment["python_executable"], str) and environment["python_executable"]
    for key in ["env_path", "git_path", "dependencies_path"]:
        assert environment[key] in {None, f"reproduce/{key[:-5]}.json"} or isinstance(environment[key], str)
        if environment[key] is not None:
            assert (task_path / environment[key]).is_file()


def _assert_sources(items: list[dict[str, Any]], *, workspace: Path, expected_task_id: str) -> None:
    assert isinstance(items, list)
    seen_paths: set[str] = set()
    for item in items:
        assert REQUIRED_SOURCE_KEYS <= set(item)
        assert set(item) <= REQUIRED_SOURCE_KEYS | OPTIONAL_SOURCE_KEYS
        assert isinstance(item["path"], str) and item["path"]
        assert item["path"] not in seen_paths
        seen_paths.add(item["path"])
        assert isinstance(item["role"], str) and item["role"]
        path = _resolve_task_or_workspace_path(workspace, expected_task_id, item["path"])
        assert path.exists(), item["path"]
        assert item["size_bytes"] is None or isinstance(item["size_bytes"], int)
        assert item["sha256"] is None or isinstance(item["sha256"], str)
        if "row_count" in item:
            assert isinstance(item["row_count"], int)
            assert item["row_count"] >= 0
        for key in ["detected_fields", "mapped_fields"]:
            if key in item:
                assert isinstance(item[key], list)
                assert all(isinstance(value, str) and value for value in item[key])


def _assert_artifacts(items: list[dict[str, Any]], *, workspace: Path, expected_task_id: str) -> None:
    assert isinstance(items, list)
    assert items
    artifact_ids: set[str] = set()
    for item in items:
        assert REQUIRED_ARTIFACT_KEYS <= set(item)
        assert set(item) <= REQUIRED_ARTIFACT_KEYS | OPTIONAL_ARTIFACT_KEYS
        assert isinstance(item["artifact_id"], str) and item["artifact_id"]
        assert item["artifact_id"] not in artifact_ids
        artifact_ids.add(item["artifact_id"])
        assert isinstance(item["type"], str) and item["type"]
        assert isinstance(item["path"], str) and item["path"]
        assert isinstance(item["description"], str) and item["description"]
        assert isinstance(item["source_paths"], list)
        for source_path in item["source_paths"]:
            assert isinstance(source_path, str) and source_path
            resolved = _resolve_task_or_workspace_path(workspace, expected_task_id, source_path)
            assert resolved.exists(), source_path
        assert isinstance(item["exists"], bool)
        assert item["size_bytes"] is None or isinstance(item["size_bytes"], int)
        assert item["sha256"] is None or isinstance(item["sha256"], str)

        resolved_path = _resolve_task_or_workspace_path(workspace, expected_task_id, item["path"])
        if item["exists"]:
            assert resolved_path.is_file(), item["path"]
        if item["type"] == "log":
            assert item["sha256"] is None
            assert item["digest_omitted_reason"] == "full log files are not hashed in traceability by default"
        elif not item["exists"]:
            assert item["digest_omitted_reason"] == "artifact file is not present"


def _assert_metric_lineage(
    lineage: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
    expected_present: bool,
) -> None:
    assert set(lineage) == REQUIRED_METRIC_LINEAGE_KEYS
    assert lineage["present"] is expected_present
    assert lineage["path"] == "metrics/normalized_metrics.csv"
    assert lineage["json_path"] in {None, "metrics/normalized_metrics.json"}
    assert lineage["collection_summary_path"] in {None, "metrics/collection-summary.json"}
    assert lineage["scenario_summary_path"] in {None, "metrics/scenario-summary.json"}
    assert lineage["scenario_type"] is None or isinstance(lineage["scenario_type"], str)
    assert lineage["primary_metric"] is None or isinstance(lineage["primary_metric"], dict)
    assert lineage["scenario_claim_limit"] is None or isinstance(lineage["scenario_claim_limit"], str)
    assert isinstance(lineage["row_count"], int)
    assert isinstance(lineage["columns"], list)
    assert isinstance(lineage["detected_fields"], list)
    assert isinstance(lineage["source_files"], list)
    assert isinstance(lineage["output_files"], list)

    if expected_present:
        assert (_task_path(workspace, expected_task_id) / lineage["path"]).is_file()
        assert lineage["row_count"] > 0
        assert lineage["columns"]
        assert lineage["collection_summary_path"] == "metrics/collection-summary.json"
        for output_file in lineage["output_files"]:
            resolved = _resolve_task_or_workspace_path(workspace, expected_task_id, output_file)
            assert resolved.is_file(), output_file
    else:
        assert lineage["row_count"] == 0
        assert lineage["columns"] == []
        assert lineage["detected_fields"] == []
        assert lineage["source_files"] == []
        assert lineage["output_files"] == []


def _assert_figure_lineage(
    lineage: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
    expected_present: bool,
) -> None:
    assert set(lineage) == REQUIRED_FIGURE_LINEAGE_KEYS
    assert lineage["present"] is expected_present
    assert lineage["summary_path"] in {None, "figures/figure-summary.json"}
    assert lineage["spec_path"] in {None, "figures/figure-spec.yaml"}
    assert isinstance(lineage["figure_count"], int)
    assert isinstance(lineage["figures"], list)
    assert isinstance(lineage["unsupported_chart_diagnostics"], list)
    assert lineage["fallback"] is None or isinstance(lineage["fallback"], dict)
    assert isinstance(lineage["warnings"], list)
    assert isinstance(lineage["errors"], list)

    if expected_present:
        assert lineage["summary_path"] == "figures/figure-summary.json"
        assert (_task_path(workspace, expected_task_id) / lineage["summary_path"]).is_file()
        assert lineage["figure_count"] == len(lineage["figures"])
        if lineage["spec_path"] is not None:
            assert (_task_path(workspace, expected_task_id) / lineage["spec_path"]).is_file()
    else:
        assert lineage["summary_path"] is None
        assert lineage["spec_path"] is None
        assert lineage["figure_count"] == 0
        assert lineage["figures"] == []
        assert lineage["fallback"] is None

    for item in lineage["figures"]:
        assert set(item) == REQUIRED_FIGURE_ITEM_KEYS
        assert isinstance(item["figure_id"], str) and item["figure_id"]
        assert isinstance(item["chart_type"], str) and item["chart_type"]
        assert item["source"] in {"deterministic", "fallback"}
        assert item["worker_run_id"] is None or isinstance(item["worker_run_id"], str)
        assert item["validation_status"] is None or isinstance(item["validation_status"], str)
        assert isinstance(item["artifact_ids"], list)
        assert all(isinstance(value, str) and value for value in item["artifact_ids"])
        assert isinstance(item["paths"], list)
        assert all(isinstance(value, str) and value for value in item["paths"])
        for path_text in item["paths"]:
            assert _resolve_task_or_workspace_path(workspace, expected_task_id, path_text).is_file()
        assert item["source_metrics"] is None or isinstance(item["source_metrics"], str)
        assert isinstance(item["columns"], list)
        assert all(isinstance(value, str) and value for value in item["columns"])
        assert isinstance(item["units"], dict)
        assert isinstance(item["field_sources"], dict)
        assert set(item["fallback_lineage"]) == set() or set(item["fallback_lineage"]) == EXPECTED_FALLBACK_LINEAGE_KEYS

    if lineage["fallback"] is not None:
        assert set(lineage["fallback"]) == EXPECTED_FALLBACK_KEYS
        assert lineage["fallback"]["mode"] in {"off", "bounded"}
        assert isinstance(lineage["fallback"]["attempted"], bool)
        assert lineage["fallback"]["status"] in {"not_needed", "unavailable", "rejected", "adopted"}
        assert isinstance(lineage["fallback"]["validation_checks"], list)
        assert isinstance(lineage["fallback"]["adopted_figures"], list)
        assert isinstance(lineage["fallback"]["adopted_artifact_paths"], list)
        assert isinstance(lineage["fallback"]["diagnostics"], list)


def _assert_report_lineage(
    lineage: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
    expected_present: bool,
) -> None:
    assert set(lineage) == REQUIRED_REPORT_LINEAGE_KEYS
    assert lineage["present"] is expected_present
    assert lineage["path"] in {None, "reports/report-fragment.md"}
    assert lineage["summary_path"] in {None, "reports/report-summary.json"}
    assert lineage["template"] is None or isinstance(lineage["template"], str)
    assert isinstance(lineage["source_artifacts"], list)
    assert isinstance(lineage["claim_trace_count"], int)
    assert isinstance(lineage["claim_ids"], list)
    assert lineage["claim_trace_count"] == len(lineage["claim_ids"])

    if expected_present:
        assert lineage["summary_path"] == "reports/report-summary.json"
        assert (_task_path(workspace, expected_task_id) / lineage["summary_path"]).is_file()
        summary = _read_json(_task_path(workspace, expected_task_id) / lineage["summary_path"])
        assert lineage["claim_trace_count"] == len(summary["claim_traces"])
        assert lineage["claim_ids"] == [item["claim_id"] for item in summary["claim_traces"]]
    else:
        assert lineage["path"] is None
        assert lineage["summary_path"] is None
        assert lineage["claim_trace_count"] == 0
        assert lineage["claim_ids"] == []


def _assert_slide_lineage(
    lineage: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
    expected_present: bool,
) -> None:
    assert set(lineage) == REQUIRED_SLIDE_LINEAGE_KEYS
    assert lineage["present"] is expected_present
    assert lineage["pptx_path"] in {None, "slides/presentation-draft.pptx"}
    assert lineage["summary_path"] in {None, "slides/slides-summary.json"}
    assert lineage["template"] is None or isinstance(lineage["template"], str)
    assert isinstance(lineage["slide_count"], int)
    assert isinstance(lineage["slides"], list)
    assert isinstance(lineage["included_figures"], list)
    assert isinstance(lineage["metrics"], dict)

    if expected_present:
        assert lineage["pptx_path"] == "slides/presentation-draft.pptx"
        assert lineage["summary_path"] == "slides/slides-summary.json"
        assert (_task_path(workspace, expected_task_id) / lineage["pptx_path"]).is_file()
        assert (_task_path(workspace, expected_task_id) / lineage["summary_path"]).is_file()
        summary = _read_json(_task_path(workspace, expected_task_id) / lineage["summary_path"])
        assert lineage["slide_count"] == summary["slide_count"]
        assert len(lineage["slides"]) == lineage["slide_count"]
        assert set(lineage["metrics"]) == REQUIRED_SLIDE_METRICS_KEYS
    else:
        assert lineage["pptx_path"] is None
        assert lineage["summary_path"] is None
        assert lineage["slide_count"] == 0
        assert lineage["slides"] == []
        assert lineage["included_figures"] == []
        assert lineage["metrics"] == {}
        return

    metrics = lineage["metrics"]
    assert metrics["path"] == "metrics/normalized_metrics.csv"
    assert isinstance(metrics["present"], bool)
    assert isinstance(metrics["row_count"], int)
    assert isinstance(metrics["key_columns"], list)
    assert isinstance(metrics["numeric_columns"], list)

    for slide in lineage["slides"]:
        assert set(slide) == REQUIRED_SLIDE_ITEM_KEYS
        assert isinstance(slide["slide_index"], int)
        assert slide["slide_index"] >= 1
        assert isinstance(slide["title"], str) and slide["title"]
        assert isinstance(slide["purpose"], str) and slide["purpose"]
        assert isinstance(slide["source_artifacts"], list)
        assert isinstance(slide["evidence"], list)
        assert slide["empty_source_reason"] is None or isinstance(slide["empty_source_reason"], str)
        for source_artifact in slide["source_artifacts"]:
            assert isinstance(source_artifact, str) and source_artifact
        for evidence in slide["evidence"]:
            assert isinstance(evidence, dict)
            assert isinstance(evidence.get("artifact_id"), str) and evidence["artifact_id"]
            assert isinstance(evidence.get("path"), str) and evidence["path"]
            assert evidence.get("body") in {None, "omitted"}
            assert "rows" not in evidence


def _assert_claim_traces(items: list[dict[str, Any]], *, workspace: Path, expected_task_id: str) -> None:
    assert isinstance(items, list)
    seen_ids: set[str] = set()
    for item in items:
        assert REQUIRED_CLAIM_TRACE_KEYS <= set(item)
        assert set(item) <= REQUIRED_CLAIM_TRACE_KEYS | OPTIONAL_CLAIM_TRACE_KEYS
        assert isinstance(item["claim_id"], str) and item["claim_id"]
        assert item["claim_id"] not in seen_ids
        seen_ids.add(item["claim_id"])
        assert item["surface"] in {"report", "slides"}
        assert isinstance(item["claim_type"], str) and item["claim_type"]
        assert isinstance(item["evidence"], list)
        assert item["evidence"]
        if "field" in item:
            assert isinstance(item["field"], str) and item["field"]
        if "operation" in item:
            assert item["operation"] in {"mean", "min", "max", "final"}
        for evidence in item["evidence"]:
            assert isinstance(evidence, dict)
            assert isinstance(evidence.get("artifact_id"), str) and evidence["artifact_id"]
            assert isinstance(evidence.get("path"), str) and evidence["path"]
            path = _resolve_task_or_workspace_path(workspace, expected_task_id, evidence["path"])
            if evidence["artifact_id"] != "figures_summary":
                # Some claims intentionally point to a canonical path even when the file is not present.
                if path.exists():
                    assert path.is_file() or path.is_dir()
            assert evidence.get("body") in {None, "omitted"}
            assert "rows" not in evidence


def _assert_omitted(items: list[dict[str, Any]]) -> None:
    assert isinstance(items, list)
    assert items
    seen: set[tuple[str, str]] = set()
    for item in items:
        assert set(item) == REQUIRED_OMITTED_KEYS
        assert isinstance(item["path"], str) and item["path"]
        assert isinstance(item["category"], str) and item["category"]
        assert isinstance(item["reason"], str) and item["reason"]
        key = (item["path"], item["category"])
        assert key not in seen
        seen.add(key)


def _assert_traceability_artifact(item: dict[str, Any]) -> None:
    assert set(item) == REQUIRED_TRACEABILITY_ARTIFACT_KEYS
    assert item["artifact_id"] == "provenance_traceability_json"
    assert item["path"] == "provenance/traceability.json"
    assert "self digest" in item["self_digest_note"]


def _assert_traceability_is_reference_only(traceability: dict[str, Any]) -> None:
    serialized = json.dumps(traceability, ensure_ascii=False)
    for fragment in FORBIDDEN_REFERENCE_ONLY_FRAGMENTS:
        assert fragment not in serialized


def test_completed_full_chain_traceability_matches_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "traceability-contract-completed"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(workspace, ["run", command, "--name", "traceability-completed"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    assert invoke(workspace, ["figures", task_id]).exit_code == 0
    assert invoke(workspace, ["report", task_id]).exit_code == 0
    assert invoke(workspace, ["slides", task_id]).exit_code == 0

    traceability = read_traceability(workspace, task_id)
    _assert_traceability_contract(
        traceability,
        workspace=workspace,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="completed",
        metric_present=True,
        figure_present=True,
        report_present=True,
        slide_present=True,
    )

    omitted_paths = {item["path"] for item in traceability["omitted"]}
    assert {"stdout.log", "stderr.log", ".lab-sidecar/index.sqlite"} <= omitted_paths

    artifact_by_id = {item["artifact_id"]: item for item in traceability["artifacts"]}
    assert artifact_by_id["metrics_normalized_csv"]["sha256"]
    assert artifact_by_id["report_summary_json"]["sha256"]
    assert artifact_by_id["slides_presentation_draft_pptx"]["sha256"]
    assert artifact_by_id["log_stdout"]["digest_omitted_reason"] == "full log files are not hashed in traceability by default"
    assert artifact_by_id["log_stderr"]["digest_omitted_reason"] == "full log files are not hashed in traceability by default"

    report_summary = _read_json(_task_path(workspace, task_id) / "reports" / "report-summary.json")
    slides_summary = _read_json(_task_path(workspace, task_id) / "slides" / "slides-summary.json")
    expected_claim_ids = [
        *[item["claim_id"] for item in report_summary["claim_traces"]],
        *[item["claim_id"] for item in slides_summary["claim_traces"]],
    ]
    assert [item["claim_id"] for item in traceability["claim_traces"]] == expected_claim_ids
    assert traceability["report_lineage"]["claim_trace_count"] == len(report_summary["claim_traces"])
    assert traceability["slide_lineage"]["slide_count"] == slides_summary["slide_count"]


def test_failed_diagnostic_traceability_stays_bounded_and_reference_only(tmp_path: Path) -> None:
    workspace = tmp_path / "traceability-contract-failed"
    workspace.mkdir()
    script = workspace / "long_failure.py"
    script.write_text(
        "\n".join(
            [
                "import sys",
                "for index in range(40):",
                "    print(f'FORBIDDEN_STDOUT_EARLY_{index:04d} ' + ('x' * 32))",
                "    print(f'FORBIDDEN_STDERR_EARLY_{index:04d} ' + ('y' * 32), file=sys.stderr)",
                "for index in range(3):",
                "    print(f'VISIBLE_STDOUT_TAIL_{index:04d}')",
                "    print(f'VISIBLE_STDERR_TAIL_{index:04d}', file=sys.stderr)",
                "raise SystemExit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" long_failure.py'
    task_id = extract_task_id(invoke(workspace, ["run", command, "--name", "traceability-failed"]).output)
    assert invoke(workspace, ["report", task_id]).exit_code == 0
    assert invoke(workspace, ["slides", task_id]).exit_code == 0

    traceability = read_traceability(workspace, task_id)
    _assert_traceability_contract(
        traceability,
        workspace=workspace,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="failed",
        metric_present=False,
        figure_present=False,
        report_present=True,
        slide_present=True,
    )

    claim_ids = {item["claim_id"] for item in traceability["claim_traces"]}
    assert {
        "report.metrics.unavailable",
        "report.diagnostic.failed_status",
        "slides.metrics.unavailable",
        "slides.diagnostic.failed_status",
    } <= claim_ids

    serialized = json.dumps(traceability, ensure_ascii=False)
    assert "FORBIDDEN_STDOUT_EARLY_0000" not in serialized
    assert "FORBIDDEN_STDERR_EARLY_0000" not in serialized
    assert "VISIBLE_STDOUT_TAIL_0000" not in serialized
    assert "VISIBLE_STDERR_TAIL_0000" not in serialized

    artifact_by_id = {item["artifact_id"]: item for item in traceability["artifacts"]}
    assert artifact_by_id["log_stdout"]["sha256"] is None
    assert artifact_by_id["log_stderr"]["sha256"] is None
    assert artifact_by_id["log_stdout"]["digest_omitted_reason"] == "full log files are not hashed in traceability by default"
    assert artifact_by_id["log_stderr"]["digest_omitted_reason"] == "full log files are not hashed in traceability by default"


def test_packaged_traceability_matches_task_local_contract_and_shape(tmp_path: Path) -> None:
    workspace = tmp_path / "traceability-contract-package"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(workspace, ["run", command, "--name", "traceability-package"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    assert invoke(workspace, ["figures", task_id]).exit_code == 0
    assert invoke(workspace, ["report", task_id]).exit_code == 0
    assert invoke(workspace, ["slides", task_id]).exit_code == 0

    package_path = workspace / f"lab-sidecar-package-{task_id}"
    result = invoke(workspace, ["package", task_id, "--output", package_path.as_posix()])
    assert result.exit_code == 0

    task_traceability = read_traceability(workspace, task_id)
    _assert_traceability_contract(
        task_traceability,
        workspace=workspace,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="completed",
        metric_present=True,
        figure_present=True,
        report_present=True,
        slide_present=True,
    )

    package_traceability = _read_json(package_path / "provenance" / "traceability.json")
    assert package_traceability == task_traceability

    omitted_categories = {(item["path"], item["category"]) for item in package_traceability["omitted"]}
    assert ("stdout.log", "log") in omitted_categories
    assert ("stderr.log", "log") in omitted_categories
    assert (".lab-sidecar/index.sqlite", "index") in omitted_categories

    artifact_by_id = {item["artifact_id"]: item for item in package_traceability["artifacts"]}
    assert artifact_by_id["metrics_normalized_csv"]["sha256"]
    assert artifact_by_id["report_summary_json"]["sha256"]
    assert artifact_by_id["slides_presentation_draft_pptx"]["sha256"]


def test_missing_generated_artifact_keeps_lineage_and_records_digest_omission_reason(tmp_path: Path) -> None:
    workspace = tmp_path / "traceability-contract-missing-artifact"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(workspace, ["run", command, "--name", "traceability-missing"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    assert invoke(workspace, ["figures", task_id]).exit_code == 0
    assert invoke(workspace, ["report", task_id]).exit_code == 0

    report_fragment = _task_path(workspace, task_id) / "reports" / "report-fragment.md"
    assert report_fragment.is_file()
    report_fragment.unlink()

    record = load_task(workspace, task_id)
    record = refresh_traceability(workspace, record)
    write_manifest(manifest_path(workspace, task_id), record)

    traceability = read_traceability(workspace, task_id)
    _assert_traceability_contract(
        traceability,
        workspace=workspace,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="completed",
        metric_present=True,
        figure_present=True,
        report_present=True,
        slide_present=False,
    )

    report_artifact = next(item for item in traceability["artifacts"] if item["artifact_id"] == "report_fragment_md")
    assert report_artifact["exists"] is False
    assert report_artifact["digest_omitted_reason"] == "artifact file is not present"
    assert traceability["report_lineage"]["present"] is True
    assert traceability["report_lineage"]["path"] == "reports/report-fragment.md"


def test_traceability_truncates_sources_at_two_hundred_and_records_warning(tmp_path: Path) -> None:
    workspace = tmp_path / "traceability-contract-many-sources"
    workspace.mkdir()
    source_root = workspace / "many-sources"
    source_root.mkdir()
    for index in range(205):
        (source_root / f"metrics_{index:03d}.csv").write_text("step,score\n1,0.5\n", encoding="utf-8")

    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "many-sources", "--name", "traceability-many"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0

    traceability = read_traceability(workspace, task_id)
    _assert_traceability_contract(
        traceability,
        workspace=workspace,
        expected_task_id=task_id,
        expected_mode="ingest",
        expected_status="completed",
        metric_present=True,
        figure_present=False,
        report_present=False,
        slide_present=False,
    )

    assert len(traceability["sources"]) == 200
    assert "traceability sources truncated from 206 to 200" in traceability["warnings"]
    assert traceability["sources"][0]["path"] == "many-sources"
    assert traceability["sources"][-1]["path"].endswith("metrics_198.csv")
    omitted_paths = {(item["path"], item["category"]) for item in traceability["omitted"]}
    assert ("raw/source_refs.json", "raw") in omitted_paths
    assert ("many-sources", "raw_source") in omitted_paths
