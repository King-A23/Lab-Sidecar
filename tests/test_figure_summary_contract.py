from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.test_cli_smoke import copy_examples, extract_task_id, invoke


REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "task_id",
    "task_status",
    "generated_at",
    "metrics_path",
    "source_metrics",
    "figure_count",
    "generated_figures",
    "unsupported_chart_diagnostics",
    "skipped_candidates",
    "warnings",
    "errors",
    "fallback",
}
OPTIONAL_TOP_LEVEL_KEYS = {
    "spec_path",
    "spec_input_path",
    "units",
    "groups",
    "field_sources",
    "figures",
}
TASK_STATUS_VALUES = {"pending", "running", "completed", "failed", "cancelled"}
ALLOWED_SKIPPED_KEYS = {"figure_id", "reason", "chart_type", "x", "y", "group_by"}
REQUIRED_FIGURE_KEYS = {
    "figure_id",
    "chart_type",
    "png_path",
    "svg_path",
    "source_metrics",
    "x",
    "y",
    "group_by",
    "units",
    "field_sources",
}
ALLOWED_GENERATED_FIGURE_KEYS = REQUIRED_FIGURE_KEYS | {
    "source",
    "worker_run_id",
    "validation_status",
    "validation_checks",
    "fallback_lineage",
}
REQUIRED_ALIAS_FIGURE_KEYS = {
    "figure_id",
    "chart_type",
    "png",
    "svg",
    "x",
    "y",
    "group_by",
    "units",
    "field_sources",
}
ALLOWED_ALIAS_FIGURE_KEYS = REQUIRED_ALIAS_FIGURE_KEYS | {
    "source",
    "worker_run_id",
    "validation_status",
    "validation_checks",
    "fallback_lineage",
}
REQUIRED_UNSUPPORTED_DIAGNOSTIC_KEYS = {
    "figure_id",
    "requested_chart_intent",
    "available_fields",
    "reason",
}
ALLOWED_UNSUPPORTED_DIAGNOSTIC_KEYS = REQUIRED_UNSUPPORTED_DIAGNOSTIC_KEYS | {"safe_next_action"}
REQUIRED_FALLBACK_KEYS = {
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
ALLOWED_FALLBACK_KEYS = REQUIRED_FALLBACK_KEYS | {
    "worker_type",
    "worker_request_path",
    "worker_result_path",
    "proposal_path",
    "sandbox_artifact_paths",
}
FORBIDDEN_EMBEDDED_FRAGMENTS = (
    "Best val_accuracy=0.86 at epoch 5",
    "epoch,train_loss,val_loss",
    "ALPHA4_WORKER_RAW_SENTINEL_ROW",
    "worker transcript body\n",
    '"prompt":"secret"',
    '"response":"secret"',
    "ppt/presentation.xml",
)


def read_figure_summary(workspace: Path, task_id: str) -> dict[str, Any]:
    path = workspace / ".lab-sidecar" / "tasks" / task_id / "figures" / "figure-summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_figure_summary_contract(
    summary: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
) -> None:
    task_path = workspace / ".lab-sidecar" / "tasks" / expected_task_id

    assert REQUIRED_TOP_LEVEL_KEYS <= set(summary)
    assert summary["schema_version"] == "1"
    assert summary["task_id"] == expected_task_id
    assert summary["task_status"] in TASK_STATUS_VALUES
    assert isinstance(summary["generated_at"], str) and summary["generated_at"]

    metrics_path = summary["metrics_path"]
    source_metrics = summary["source_metrics"]
    assert isinstance(metrics_path, str) and metrics_path
    assert isinstance(source_metrics, str) and source_metrics
    assert metrics_path == source_metrics
    assert (workspace / metrics_path).is_file()

    figure_count = summary["figure_count"]
    assert isinstance(figure_count, int)
    assert figure_count >= 0

    generated_figures = summary["generated_figures"]
    assert isinstance(generated_figures, list)
    assert len(generated_figures) == figure_count
    for item in generated_figures:
        _assert_generated_figure_entry(item, workspace=workspace, expected_task_id=expected_task_id)

    # `generated_figures` is the richer current list. `figures` remains an accepted alias.
    alias_figures = summary.get("figures")
    if alias_figures is not None:
        assert isinstance(alias_figures, list)
        assert len(alias_figures) == figure_count
        for item in alias_figures:
            _assert_alias_figure_entry(item, workspace=workspace, expected_task_id=expected_task_id)
        _assert_alias_matches_canonical(generated_figures, alias_figures)

    for key in ["warnings", "errors"]:
        value = summary[key]
        assert isinstance(value, list)
        assert all(isinstance(item, str) and item for item in value)

    skipped_candidates = summary["skipped_candidates"]
    assert isinstance(skipped_candidates, list)
    for item in skipped_candidates:
        _assert_skipped_candidate(item)

    unsupported = summary["unsupported_chart_diagnostics"]
    assert isinstance(unsupported, list)
    for item in unsupported:
        _assert_unsupported_chart_diagnostic(item)

    _assert_optional_top_level_fields(summary, workspace=workspace)
    _assert_fallback_summary(summary["fallback"], workspace=workspace, task_path=task_path)

    serialized = json.dumps(summary, ensure_ascii=False)
    assert '"prompt":' not in serialized.lower()
    assert '"response":' not in serialized.lower()
    for fragment in FORBIDDEN_EMBEDDED_FRAGMENTS:
        assert fragment not in serialized


def _assert_optional_top_level_fields(summary: dict[str, Any], *, workspace: Path) -> None:
    assert OPTIONAL_TOP_LEVEL_KEYS >= {"spec_path", "spec_input_path", "units", "groups", "field_sources", "figures"}

    spec_path = summary.get("spec_path")
    spec_input_path = summary.get("spec_input_path")
    if spec_path is None or spec_input_path is None:
        assert spec_path is None
        assert spec_input_path is None
    else:
        assert isinstance(spec_path, str) and spec_path
        assert isinstance(spec_input_path, str) and spec_input_path
        assert spec_path == spec_input_path
        assert (workspace / spec_path).is_file()

    if "units" in summary:
        units = summary["units"]
        assert isinstance(units, dict)
        assert all(isinstance(field, str) and field for field in units)
        assert all(isinstance(unit, str) and unit for unit in units.values())

    if "groups" in summary:
        groups = summary["groups"]
        assert isinstance(groups, dict)
        assert all(isinstance(group_name, str) and group_name for group_name in groups)
        assert all(isinstance(field, str) and field for field in groups.values())

    if "field_sources" in summary:
        _assert_field_sources(summary["field_sources"])


def _assert_generated_figure_entry(
    item: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
) -> None:
    assert REQUIRED_FIGURE_KEYS <= set(item)
    assert set(item) <= ALLOWED_GENERATED_FIGURE_KEYS
    assert isinstance(item["figure_id"], str) and item["figure_id"]
    assert isinstance(item["chart_type"], str) and item["chart_type"]
    assert isinstance(item["png_path"], str) and item["png_path"].endswith(".png")
    assert isinstance(item["svg_path"], str) and item["svg_path"].endswith(".svg")
    assert (workspace / item["png_path"]).is_file()
    assert (workspace / item["svg_path"]).is_file()
    assert item["source_metrics"] == f".lab-sidecar/tasks/{expected_task_id}/metrics/normalized_metrics.csv"
    assert isinstance(item["x"], str) and item["x"]
    assert isinstance(item["y"], str) and item["y"]
    assert item["group_by"] is None or isinstance(item["group_by"], str)
    _assert_units(item["units"])
    _assert_field_sources(item["field_sources"], allowed_fields=_figure_fields(item))
    _assert_optional_generated_figure_fields(item, expected_task_id=expected_task_id)


def _assert_alias_figure_entry(
    item: dict[str, Any],
    *,
    workspace: Path,
    expected_task_id: str,
) -> None:
    assert REQUIRED_ALIAS_FIGURE_KEYS <= set(item)
    assert set(item) <= ALLOWED_ALIAS_FIGURE_KEYS
    assert isinstance(item["figure_id"], str) and item["figure_id"]
    assert isinstance(item["chart_type"], str) and item["chart_type"]
    assert isinstance(item["png"], str) and item["png"].endswith(".png")
    assert isinstance(item["svg"], str) and item["svg"].endswith(".svg")
    assert item["png"].startswith(f".lab-sidecar/tasks/{expected_task_id}/figures/")
    assert item["svg"].startswith(f".lab-sidecar/tasks/{expected_task_id}/figures/")
    assert (workspace / item["png"]).is_file()
    assert (workspace / item["svg"]).is_file()
    assert isinstance(item["x"], str) and item["x"]
    assert isinstance(item["y"], str) and item["y"]
    assert item["group_by"] is None or isinstance(item["group_by"], str)
    _assert_units(item["units"])
    _assert_field_sources(item["field_sources"], allowed_fields=_figure_fields(item))
    _assert_optional_generated_figure_fields(item)


def _assert_optional_generated_figure_fields(
    item: dict[str, Any],
    *,
    expected_task_id: str | None = None,
) -> None:
    if "source" in item:
        assert item["source"] in {"deterministic", "fallback"}

    if "worker_run_id" in item:
        assert item["worker_run_id"] is None or isinstance(item["worker_run_id"], str)

    if "validation_status" in item:
        assert item["validation_status"] in {None, "accepted", "rejected"}

    if "validation_checks" in item:
        assert isinstance(item["validation_checks"], list)
        for check in item["validation_checks"]:
            _assert_validation_check(check)

    if "fallback_lineage" in item:
        fallback_lineage = item["fallback_lineage"]
        assert isinstance(fallback_lineage, dict)
        if not fallback_lineage:
            return
        required_keys = {
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
        assert required_keys <= set(fallback_lineage)
        if expected_task_id is not None:
            assert fallback_lineage["source_metrics"] == (
                f".lab-sidecar/tasks/{expected_task_id}/metrics/normalized_metrics.csv"
            )
            assert fallback_lineage["adopted_png_path"].startswith(
                f".lab-sidecar/tasks/{expected_task_id}/figures/"
            )
            assert fallback_lineage["adopted_svg_path"].startswith(
                f".lab-sidecar/tasks/{expected_task_id}/figures/"
            )
        assert isinstance(fallback_lineage["fields_used"], list)
        assert all(isinstance(field, str) and field for field in fallback_lineage["fields_used"])
        _assert_field_sources(
            fallback_lineage["field_sources"],
            allowed_fields=set(fallback_lineage["fields_used"]),
        )
        for key in [
            "worker_run_id",
            "request_path",
            "worker_request_path",
            "worker_result_path",
            "validator_result_path",
            "sandbox_png_path",
            "sandbox_svg_path",
            "adopted_png_path",
            "adopted_svg_path",
        ]:
            assert isinstance(fallback_lineage[key], str) and fallback_lineage[key]


def _assert_alias_matches_canonical(
    generated_figures: list[dict[str, Any]],
    alias_figures: list[dict[str, Any]],
) -> None:
    for generated, alias in zip(generated_figures, alias_figures, strict=True):
        assert alias["figure_id"] == generated["figure_id"]
        assert alias["chart_type"] == generated["chart_type"]
        assert alias["png"] == generated["png_path"]
        assert alias["svg"] == generated["svg_path"]
        assert alias["x"] == generated["x"]
        assert alias["y"] == generated["y"]
        assert alias["group_by"] == generated["group_by"]
        assert alias["units"] == generated["units"]
        assert alias["field_sources"] == generated["field_sources"]
        if "source" in alias and "source" in generated:
            assert alias["source"] == generated["source"]
        if "worker_run_id" in alias and "worker_run_id" in generated:
            assert alias["worker_run_id"] == generated["worker_run_id"]
        if "validation_status" in alias and "validation_status" in generated:
            assert alias["validation_status"] == generated["validation_status"]


def _assert_skipped_candidate(item: dict[str, Any]) -> None:
    assert {"figure_id", "reason"} <= set(item)
    assert set(item) <= ALLOWED_SKIPPED_KEYS
    assert "body" not in item
    assert "rows" not in item
    assert isinstance(item["figure_id"], str) and item["figure_id"]
    assert isinstance(item["reason"], str) and item["reason"]
    for key in ["chart_type", "x", "y", "group_by"]:
        if key in item:
            assert isinstance(item[key], str) and item[key]


def _assert_unsupported_chart_diagnostic(item: dict[str, Any]) -> None:
    assert REQUIRED_UNSUPPORTED_DIAGNOSTIC_KEYS <= set(item)
    assert set(item) <= ALLOWED_UNSUPPORTED_DIAGNOSTIC_KEYS
    assert "body" not in item
    assert "rows" not in item
    assert isinstance(item["figure_id"], str) and item["figure_id"]

    requested = item["requested_chart_intent"]
    assert set(requested) == {"figure_id", "chart_type", "title", "x", "y", "group_by"}
    assert isinstance(requested["figure_id"], str) and requested["figure_id"]
    assert isinstance(requested["chart_type"], str) and requested["chart_type"]
    assert isinstance(requested["title"], str) and requested["title"]
    assert isinstance(requested["x"], str) and requested["x"]
    assert isinstance(requested["y"], str) and requested["y"]
    assert requested["group_by"] is None or isinstance(requested["group_by"], str)

    available_fields = item["available_fields"]
    assert isinstance(available_fields, list)
    assert all(isinstance(field, str) and field for field in available_fields)
    assert len(available_fields) == len(set(available_fields))

    assert isinstance(item["reason"], str) and item["reason"]
    if "safe_next_action" in item:
        assert isinstance(item["safe_next_action"], str) and item["safe_next_action"]


def _assert_fallback_summary(
    fallback: dict[str, Any],
    *,
    workspace: Path,
    task_path: Path,
) -> None:
    assert REQUIRED_FALLBACK_KEYS <= set(fallback)
    assert set(fallback) <= ALLOWED_FALLBACK_KEYS
    assert fallback["mode"] in {"off", "bounded"}
    assert isinstance(fallback["attempted"], bool)
    assert fallback["status"] in {"not_needed", "unavailable", "rejected", "adopted"}
    assert fallback["worker_run_id"] is None or isinstance(fallback["worker_run_id"], str)
    _assert_task_relative_path_or_none(fallback["request_path"], task_path=task_path)
    _assert_task_relative_path_or_none(fallback["validator_result_path"], task_path=task_path)
    _assert_task_relative_path_or_none(fallback["adoption_record_path"], task_path=task_path)
    assert fallback["validation_status"] in {None, "accepted", "rejected"}
    assert isinstance(fallback["validation_checks"], list)
    for check in fallback["validation_checks"]:
        _assert_validation_check(check)

    assert isinstance(fallback["adopted_figures"], list)
    for item in fallback["adopted_figures"]:
        _assert_adopted_figure_metadata(item, workspace=workspace)

    adopted_artifact_paths = fallback["adopted_artifact_paths"]
    assert isinstance(adopted_artifact_paths, list)
    for path in adopted_artifact_paths:
        assert isinstance(path, str) and path
        assert (workspace / path).is_file()

    diagnostics = fallback["diagnostics"]
    assert isinstance(diagnostics, list)
    assert all(isinstance(item, str) and item for item in diagnostics)

    if "worker_type" in fallback:
        assert isinstance(fallback["worker_type"], str) and fallback["worker_type"]
    if "worker_request_path" in fallback:
        _assert_task_relative_path_or_none(fallback["worker_request_path"], task_path=task_path)
    if "worker_result_path" in fallback:
        _assert_task_relative_path_or_none(fallback["worker_result_path"], task_path=task_path)
    if "proposal_path" in fallback:
        _assert_task_relative_path_or_none(fallback["proposal_path"], task_path=task_path)
    if "sandbox_artifact_paths" in fallback:
        assert isinstance(fallback["sandbox_artifact_paths"], list)
        for path in fallback["sandbox_artifact_paths"]:
            assert isinstance(path, str) and path
            assert (task_path / path).is_file()

    status = fallback["status"]
    if status == "not_needed":
        assert fallback["attempted"] is False
        assert fallback["worker_run_id"] is None
        assert fallback["request_path"] is None
        assert fallback["validator_result_path"] is None
        assert fallback["adoption_record_path"] is None
        assert fallback["validation_status"] is None
        assert fallback["adopted_figures"] == []
        assert fallback["adopted_artifact_paths"] == []
        return

    assert fallback["attempted"] is True
    assert isinstance(fallback["worker_run_id"], str) and fallback["worker_run_id"]
    assert isinstance(fallback["request_path"], str) and fallback["request_path"]
    assert isinstance(fallback["validator_result_path"], str) and fallback["validator_result_path"]

    if status == "unavailable":
        assert fallback["validation_status"] == "rejected"
        assert fallback["adoption_record_path"] is None
        assert fallback["adopted_figures"] == []
        assert fallback["adopted_artifact_paths"] == []
        return

    assert isinstance(fallback.get("worker_request_path"), str) and fallback["worker_request_path"]
    assert isinstance(fallback.get("worker_result_path"), str) and fallback["worker_result_path"]
    assert isinstance(fallback.get("worker_type"), str) and fallback["worker_type"]

    if status == "rejected":
        assert fallback["validation_status"] == "rejected"
        assert fallback["adoption_record_path"] is None
        assert fallback["adopted_figures"] == []
        assert fallback["adopted_artifact_paths"] == []
        return

    assert fallback["validation_status"] == "accepted"
    assert isinstance(fallback["adoption_record_path"], str) and fallback["adoption_record_path"]
    assert fallback["adopted_figures"]
    assert fallback["adopted_artifact_paths"]


def _assert_adopted_figure_metadata(item: dict[str, Any], *, workspace: Path) -> None:
    assert set(item) == {
        "figure_id",
        "chart_type",
        "png",
        "svg",
        "source_metrics",
        "fields_used",
        "field_sources",
    }
    assert isinstance(item["figure_id"], str) and item["figure_id"]
    assert isinstance(item["chart_type"], str) and item["chart_type"]
    assert isinstance(item["png"], str) and item["png"].endswith(".png")
    assert isinstance(item["svg"], str) and item["svg"].endswith(".svg")
    assert isinstance(item["source_metrics"], str) and item["source_metrics"].endswith(
        "/metrics/normalized_metrics.csv"
    )
    assert (workspace / item["png"]).is_file()
    assert (workspace / item["svg"]).is_file()
    assert (workspace / item["source_metrics"]).is_file()
    assert isinstance(item["fields_used"], list)
    assert all(isinstance(field, str) and field for field in item["fields_used"])
    _assert_field_sources(item["field_sources"], allowed_fields=set(item["fields_used"]))


def _assert_validation_check(check: dict[str, Any]) -> None:
    assert {"name", "status"} <= set(check)
    assert set(check) <= {"name", "status", "message"}
    assert isinstance(check["name"], str) and check["name"]
    assert check["status"] in {"passed", "failed", "skipped"}
    if "message" in check and check["message"] is not None:
        assert isinstance(check["message"], str) and check["message"]


def _assert_units(units: dict[str, Any]) -> None:
    assert isinstance(units, dict)
    assert all(isinstance(field, str) and field for field in units)
    assert all(isinstance(unit, str) and unit for unit in units.values())


def _assert_field_sources(
    field_sources: dict[str, Any],
    *,
    allowed_fields: set[str] | None = None,
) -> None:
    assert isinstance(field_sources, dict)
    if allowed_fields is not None:
        assert set(field_sources).issubset(allowed_fields)
    for field_name, source_fields in field_sources.items():
        assert isinstance(field_name, str) and field_name
        assert isinstance(source_fields, list)
        assert source_fields
        assert all(isinstance(source_field, str) and source_field for source_field in source_fields)
        assert len(source_fields) == len(set(source_fields))


def _assert_task_relative_path_or_none(value: Any, *, task_path: Path) -> None:
    if value is None:
        return
    assert isinstance(value, str) and value
    assert not value.startswith("/")
    assert (task_path / value).exists()


def _figure_fields(item: dict[str, Any]) -> set[str]:
    fields = {item["x"], item["y"]}
    if item["group_by"] is not None:
        fields.add(item["group_by"])
    return fields


def test_generated_figure_summary_matches_public_contract_for_deterministic_success(tmp_path: Path) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0

    result = invoke(workspace, ["figures", task_id])

    assert result.exit_code == 0
    summary = read_figure_summary(workspace, task_id)

    assert_figure_summary_contract(summary, workspace=workspace, expected_task_id=task_id)
    assert summary["figure_count"] > 0
    assert summary["unsupported_chart_diagnostics"] == []
    assert summary["fallback"]["mode"] == "off"
    assert summary["fallback"]["status"] == "not_needed"
    assert summary["spec_path"] is None
    assert summary["spec_input_path"] is None


def test_generated_figure_summary_matches_public_contract_for_unsupported_explicit_chart_without_fallback(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    (workspace / "scatter.yaml").write_text(
        "\n".join(
            [
                "figure_id: accuracy_scatter",
                "chart_type: scatter",
                "title: Accuracy Scatter",
                "x: epoch",
                "y: val_accuracy",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(workspace, ["figures", task_id, "--spec", "scatter.yaml"])

    assert result.exit_code == 5
    summary = read_figure_summary(workspace, task_id)

    assert_figure_summary_contract(summary, workspace=workspace, expected_task_id=task_id)
    assert summary["figure_count"] == 0
    assert summary["generated_figures"] == []
    assert summary["figures"] == []
    assert summary["unsupported_chart_diagnostics"]
    assert summary["fallback"]["mode"] == "off"
    assert summary["fallback"]["status"] == "not_needed"
    assert summary["spec_path"] == "scatter.yaml"


def test_generated_figure_summary_matches_public_contract_for_bounded_fallback_unavailable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    (workspace / "heatmap.yaml").write_text(
        "\n".join(
            [
                "figure_id: confusion_heatmap",
                "chart_type: heatmap",
                "title: Confusion Heatmap",
                "x: epoch",
                "y: val_accuracy",
                "group_by: source_file",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(workspace, ["figures", task_id, "--spec", "heatmap.yaml", "--fallback", "bounded"])

    assert result.exit_code == 5
    summary = read_figure_summary(workspace, task_id)

    assert_figure_summary_contract(summary, workspace=workspace, expected_task_id=task_id)
    assert summary["figure_count"] == 0
    assert summary["generated_figures"] == []
    assert summary["fallback"]["mode"] == "bounded"
    assert summary["fallback"]["status"] == "unavailable"
    assert summary["fallback"]["request_path"]
    assert summary["fallback"]["validator_result_path"]
    assert summary["spec_input_path"] == "heatmap.yaml"


def test_generated_figure_summary_matches_public_contract_for_bounded_fallback_adopted(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    assert invoke(workspace, ["init"]).exit_code == 0
    source = workspace / "fallback-metrics"
    source.mkdir()
    (source / "metrics.csv").write_text(
        "\n".join(
            [
                "epoch,val_accuracy,secret_payload",
                "1,0.70,ALPHA4_WORKER_RAW_SENTINEL_ROW_001",
                "2,0.82,ALPHA4_WORKER_RAW_SENTINEL_ROW_002",
                "3,0.91,ALPHA4_WORKER_RAW_SENTINEL_ROW_003",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "metrics.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - fallback-metrics/metrics.csv",
                "fields:",
                "  epoch: epoch",
                "  val_accuracy:",
                "    source: val_accuracy",
                "    unit: ratio",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(workspace, ["ingest", "fallback-metrics"]).output)
    assert invoke(workspace, ["collect", task_id, "--config", "metrics.yaml"]).exit_code == 0
    (workspace / "heatmap.yaml").write_text(
        "\n".join(
            [
                "figure_id: alpha4_heatmap",
                "chart_type: heatmap",
                "title: Alpha4 Heatmap",
                "x: epoch",
                "y: val_accuracy",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(
        workspace,
        ["figures", task_id, "--spec", "heatmap.yaml", "--fallback", "bounded", "--fallback-worker", "mock"],
    )

    assert result.exit_code == 0
    summary = read_figure_summary(workspace, task_id)

    assert_figure_summary_contract(summary, workspace=workspace, expected_task_id=task_id)
    assert summary["figure_count"] == 1
    assert summary["generated_figures"][0]["source"] == "fallback"
    assert summary["fallback"]["status"] == "adopted"
    assert summary["fallback"]["validation_status"] == "accepted"
    assert summary["fallback"]["adopted_figures"][0]["figure_id"] == "alpha4_heatmap"
    assert summary["spec_input_path"] == "heatmap.yaml"


def test_generated_figure_summary_matches_public_contract_for_bounded_fallback_rejected(
    tmp_path: Path,
) -> None:
    workspace = tmp_path
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    (workspace / "heatmap.yaml").write_text(
        "\n".join(
            [
                "figure_id: malformed_heatmap",
                "chart_type: heatmap",
                "title: Malformed Heatmap",
                "x: epoch",
                "y: val_accuracy",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(
        workspace,
        [
            "figures",
            task_id,
            "--spec",
            "heatmap.yaml",
            "--fallback",
            "bounded",
            "--fallback-worker",
            "mock-malformed-image",
        ],
    )

    assert result.exit_code == 5
    summary = read_figure_summary(workspace, task_id)

    assert_figure_summary_contract(summary, workspace=workspace, expected_task_id=task_id)
    assert summary["figure_count"] == 0
    assert summary["generated_figures"] == []
    assert summary["fallback"]["status"] == "rejected"
    assert summary["fallback"]["validation_status"] == "rejected"
    assert summary["fallback"]["adopted_figures"] == []
    assert summary["spec_input_path"] == "heatmap.yaml"
