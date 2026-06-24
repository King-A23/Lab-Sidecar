from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from tests.test_cli_smoke import copy_examples, extract_task_id, invoke, read_manifest, wait_for_output


REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "task_id",
    "mode",
    "status",
    "created_at",
    "updated_at",
    "working_dir",
    "paths",
    "artifacts",
}
REQUIRED_PATH_KEYS = {"task_dir", "stdout", "stderr"}
STATUS_VALUES = {"pending", "running", "completed", "failed", "cancelled"}
REVIEW_REQUIRED_LOCAL_METADATA_KEYS = {"command", "working_dir", "source_path", "failure_summary"}
FORBIDDEN_EMBEDDED_FRAGMENTS = (
    "Starting synthetic training run",
    "Best val_accuracy=0.86 at epoch 5",
    "epoch,model,seed,val_accuracy,val_loss",
    '"rows":',
    "Experimental Summary Fragment",
    "ppt/presentation.xml",
    "<p:sld",
)


def assert_manifest_contract(
    manifest: dict[str, Any],
    *,
    expected_task_id: str,
    expected_mode: str,
    expected_status: str,
) -> None:
    assert REQUIRED_TOP_LEVEL_KEYS <= set(manifest)
    assert manifest["schema_version"] == "1"
    assert manifest["task_id"] == expected_task_id
    assert manifest["mode"] == expected_mode
    assert manifest["status"] == expected_status
    assert manifest["mode"] in {"run", "ingest"}
    assert manifest["status"] in STATUS_VALUES
    assert isinstance(manifest["created_at"], str) and manifest["created_at"]
    assert isinstance(manifest["updated_at"], str) and manifest["updated_at"]
    assert isinstance(manifest["working_dir"], str) and manifest["working_dir"]

    paths = manifest["paths"]
    assert REQUIRED_PATH_KEYS <= set(paths)
    for key in REQUIRED_PATH_KEYS:
        assert isinstance(paths[key], str) and paths[key]
        assert "\n" not in paths[key]

    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    artifact_ids = [artifact["artifact_id"] for artifact in artifacts]
    assert len(artifact_ids) == len(set(artifact_ids))
    for artifact in artifacts:
        _assert_artifact_item_shape(artifact)

    serialized = json.dumps(manifest, ensure_ascii=False)
    _assert_manifest_is_reference_only(serialized)


def _assert_artifact_item_shape(artifact: dict[str, Any]) -> None:
    assert set(artifact) == {
        "artifact_id",
        "type",
        "path",
        "description",
        "source_paths",
        "size_bytes",
        "sha256",
    }
    assert isinstance(artifact["artifact_id"], str) and artifact["artifact_id"]
    assert isinstance(artifact["type"], str) and artifact["type"]
    assert isinstance(artifact["path"], str) and artifact["path"]
    assert "\n" not in artifact["path"]
    assert isinstance(artifact["description"], str) and artifact["description"]
    assert isinstance(artifact["source_paths"], list)
    assert all(isinstance(path, str) and path and "\n" not in path for path in artifact["source_paths"])
    assert artifact["size_bytes"] is None or isinstance(artifact["size_bytes"], int)
    assert artifact["sha256"] is None or isinstance(artifact["sha256"], str)


def _assert_manifest_is_reference_only(serialized: str) -> None:
    assert '"stdout":"' not in serialized
    assert '"stderr":"' not in serialized
    for fragment in FORBIDDEN_EMBEDDED_FRAGMENTS:
        assert fragment not in serialized


def _assert_local_metadata_policy(manifest: dict[str, Any]) -> None:
    present = REVIEW_REQUIRED_LOCAL_METADATA_KEYS & set(manifest)
    assert present
    for key in present:
        value = manifest[key]
        assert value is None or isinstance(value, str)


def test_completed_run_manifest_matches_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "manifest-contract-run"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    result = invoke(workspace, ["run", command])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    manifest = read_manifest(workspace, task_id)

    assert_manifest_contract(
        manifest,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="completed",
    )
    _assert_local_metadata_policy(manifest)
    assert manifest["command"] == command
    assert manifest["run_mode"] == "shell"
    assert manifest["argv"] is None
    assert manifest["safe_profile"] is None
    assert manifest["source_path"] is None
    assert manifest["exit_code"] == 0
    assert manifest["paths"]["task_dir"] == f".lab-sidecar/tasks/{task_id}"
    assert manifest["paths"]["stdout"] == f".lab-sidecar/tasks/{task_id}/stdout.log"
    assert manifest["paths"]["stderr"] == f".lab-sidecar/tasks/{task_id}/stderr.log"
    artifact_ids = {artifact["artifact_id"] for artifact in manifest["artifacts"]}
    assert {
        "log_stdout",
        "log_stderr",
        "reproduce_command",
        "reproduce_run",
        "reproduce_env",
        "reproduce_git",
        "reproduce_dependencies",
    } <= artifact_ids


def test_completed_ingest_manifest_matches_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "manifest-contract-ingest"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    result = invoke(workspace, ["ingest", "examples/csv-comparison", "--name", "contract-ingest"])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    manifest = read_manifest(workspace, task_id)

    assert_manifest_contract(
        manifest,
        expected_task_id=task_id,
        expected_mode="ingest",
        expected_status="completed",
    )
    _assert_local_metadata_policy(manifest)
    assert manifest["command"] is None
    assert manifest["run_mode"] is None
    assert manifest["argv"] is None
    assert manifest["safe_profile"] is None
    assert manifest["source_path"] == "examples/csv-comparison"
    assert manifest["exit_code"] == 0
    artifact_ids = {artifact["artifact_id"] for artifact in manifest["artifacts"]}
    assert {"log_stdout", "log_stderr", "raw_source_refs"} <= artifact_ids


def test_failed_run_manifest_matches_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "manifest-contract-failed"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-failure/fail.py'
    result = invoke(workspace, ["run", command])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    manifest = read_manifest(workspace, task_id)

    assert_manifest_contract(
        manifest,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="failed",
    )
    _assert_local_metadata_policy(manifest)
    assert manifest["command"] == command
    assert manifest["run_mode"] == "shell"
    assert manifest["argv"] is None
    assert manifest["safe_profile"] is None
    assert manifest["exit_code"] != 0
    assert isinstance(manifest["failure_summary"], str) and "FileNotFoundError" in manifest["failure_summary"]


def test_running_and_cancelled_background_manifests_match_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "manifest-contract-background"
    workspace.mkdir()
    script = workspace / "long_task.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('manifest-contract-ready', flush=True)",
                "time.sleep(30)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" long_task.py'
    result = invoke(workspace, ["run", command, "--background"])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    wait_for_output(workspace, task_id, "manifest-contract-ready")

    running_manifest = read_manifest(workspace, task_id)
    assert_manifest_contract(
        running_manifest,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="running",
    )
    _assert_local_metadata_policy(running_manifest)
    assert running_manifest["worker_pid"]
    assert running_manifest["run_mode"] == "shell"
    assert running_manifest["argv"] is None

    cancel = invoke(workspace, ["cancel", task_id])
    assert cancel.exit_code == 0
    cancelled_manifest = read_manifest(workspace, task_id)
    assert_manifest_contract(
        cancelled_manifest,
        expected_task_id=task_id,
        expected_mode="run",
        expected_status="cancelled",
    )
    _assert_local_metadata_policy(cancelled_manifest)
    assert cancelled_manifest["pid"] is None
    assert cancelled_manifest["worker_pid"] is None
    assert cancelled_manifest["run_mode"] == "shell"


def test_manifest_artifacts_remain_unique_and_shaped_after_collect_figures_report_slides(tmp_path: Path) -> None:
    workspace = tmp_path / "manifest-contract-pipeline"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    task_id = extract_task_id(invoke(workspace, ["ingest", "examples/csv-comparison"]).output)

    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    assert invoke(workspace, ["figures", task_id]).exit_code == 0
    assert invoke(workspace, ["figures", task_id]).exit_code == 0
    assert invoke(workspace, ["report", task_id]).exit_code == 0
    assert invoke(workspace, ["report", task_id, "--template", "zh-summary"]).exit_code == 0
    assert invoke(workspace, ["slides", task_id]).exit_code == 0
    assert invoke(workspace, ["slides", task_id, "--template", "en-summary"]).exit_code == 0

    manifest = read_manifest(workspace, task_id)
    assert_manifest_contract(
        manifest,
        expected_task_id=task_id,
        expected_mode="ingest",
        expected_status="completed",
    )
    _assert_local_metadata_policy(manifest)

    artifacts = {artifact["artifact_id"]: artifact for artifact in manifest["artifacts"]}
    assert {
        "metrics_collection_summary",
        "metrics_normalized_csv",
        "metrics_normalized_json",
        "metrics_scenario_summary",
        "figures_spec",
        "figures_summary",
        "report_fragment_md",
        "report_summary_json",
        "slides_presentation_draft_pptx",
        "slides_summary_json",
        "provenance_traceability_json",
    } <= set(artifacts)
    figure_artifact_ids = [artifact_id for artifact_id in artifacts if artifact_id.startswith("figure_")]
    assert figure_artifact_ids

    assert artifacts["metrics_collection_summary"]["path"].endswith("metrics/collection-summary.json")
    assert artifacts["metrics_normalized_csv"]["path"].endswith("metrics/normalized_metrics.csv")
    assert artifacts["metrics_normalized_json"]["path"].endswith("metrics/normalized_metrics.json")
    assert artifacts["metrics_scenario_summary"]["path"].endswith("metrics/scenario-summary.json")
    assert artifacts["figures_spec"]["path"].endswith("figures/figure-spec.yaml")
    assert artifacts["figures_summary"]["path"].endswith("figures/figure-summary.json")
    assert artifacts["report_fragment_md"]["path"].endswith("reports/report-fragment.md")
    assert artifacts["report_summary_json"]["path"].endswith("reports/report-summary.json")
    assert artifacts["slides_presentation_draft_pptx"]["path"].endswith("slides/presentation-draft.pptx")
    assert artifacts["slides_summary_json"]["path"].endswith("slides/slides-summary.json")
    assert artifacts["provenance_traceability_json"]["path"].endswith("provenance/traceability.json")

    for artifact_id, artifact in artifacts.items():
        if artifact["type"] == "log":
            assert artifact["size_bytes"] is not None
            assert artifact["sha256"] is None
            continue
        assert artifact["size_bytes"] is not None, artifact_id
        assert artifact["size_bytes"] > 0, artifact_id
        assert isinstance(artifact["sha256"], str) and artifact["sha256"], artifact_id

    index_path = workspace / ".lab-sidecar" / "index.sqlite"
    with sqlite3.connect(index_path) as conn:
        task_row = conn.execute(
            """
            SELECT task_id, mode, status, created_at, updated_at, working_dir, command, source_path, exit_code
            FROM tasks WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
        indexed_artifacts = conn.execute(
            """
            SELECT artifact_id, type, path, description
            FROM artifacts WHERE task_id = ?
            ORDER BY artifact_id
            """,
            (task_id,),
        ).fetchall()

    assert task_row == (
        manifest["task_id"],
        manifest["mode"],
        manifest["status"],
        manifest["created_at"],
        manifest["updated_at"],
        manifest["working_dir"],
        manifest["command"],
        manifest["source_path"],
        manifest["exit_code"],
    )
    assert indexed_artifacts == sorted(
        (
            artifact["artifact_id"],
            artifact["type"],
            artifact["path"],
            artifact["description"],
        )
        for artifact in manifest["artifacts"]
    )
