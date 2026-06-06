from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.intelligence import (
    cancel_sidecar_task,
    delegate_experiment_artifacts,
    inspect_sidecar_task,
    preview_sidecar_artifact,
)
from lab_sidecar.runner.service import RunnerService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_examples(workspace: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "examples", workspace / "examples")


def simple_success_command() -> str:
    return f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'


def artifact_path(result: dict, artifact_id: str) -> str:
    for artifact in result["artifacts"]:
        if artifact["artifact_id"] == artifact_id:
            return artifact["path"]
    raise AssertionError(f"artifact not found: {artifact_id}")


def test_host_smoke_delegate_inspect_preview_and_cancel(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)

    delegated = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate all artifacts for host smoke.",
        command=simple_success_command(),
        desired_outputs=["slides"],
        intelligent_mode="off",
    )
    inspected = inspect_sidecar_task(tmp_path, delegated["task_id"])
    csv_preview = preview_sidecar_artifact(
        tmp_path,
        delegated["task_id"],
        artifact_path(inspected, "metrics_normalized_csv"),
        max_rows=2,
    )

    script = tmp_path / "long_task.py"
    script.write_text("import time\nprint('ready', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    running = RunnerService(tmp_path).run(f'"{sys.executable}" long_task.py', background=True)
    cancelled = cancel_sidecar_task(tmp_path, running.task_id)

    assert delegated["status"] == "completed"
    assert inspected["status"] == "completed"
    assert csv_preview["preview_type"] == "csv_rows"
    assert csv_preview["preview"]["row_count_returned"] == 2
    assert cancelled["status"] == "cancelled"
    assert "ready" not in json.dumps(cancelled)


def test_preview_rejects_external_and_unregistered_paths(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate metrics.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )
    outside = tmp_path.parent / "outside.csv"
    outside.write_text("a,b\n1,2\n", encoding="utf-8")
    unregistered = tmp_path / "notes.md"
    unregistered.write_text("# private notes\n", encoding="utf-8")

    outside_result = preview_sidecar_artifact(tmp_path, result["task_id"], str(outside))
    unregistered_result = preview_sidecar_artifact(tmp_path, result["task_id"], "notes.md")

    assert outside_result["status"] == "rejected"
    assert unregistered_result["status"] == "rejected"
    assert outside_result["risk_flags"] == ["artifact_preview_rejected"]
    assert "private notes" not in json.dumps(unregistered_result)


def test_preview_returns_bounded_csv_markdown_image_pptx_and_log(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate all previewable artifacts.",
        command=simple_success_command(),
        desired_outputs=["slides"],
        intelligent_mode="off",
    )
    task_id = result["task_id"]
    inspected = inspect_sidecar_task(tmp_path, task_id)

    csv_result = preview_sidecar_artifact(tmp_path, task_id, artifact_path(inspected, "metrics_normalized_csv"), max_rows=1)
    report_result = preview_sidecar_artifact(tmp_path, task_id, artifact_path(inspected, "report_fragment_md"), max_lines=3)
    png_path = next(artifact["path"] for artifact in inspected["artifacts"] if artifact["type"] == "figure" and artifact["path"].endswith(".png"))
    image_result = preview_sidecar_artifact(tmp_path, task_id, png_path)
    ppt_result = preview_sidecar_artifact(tmp_path, task_id, artifact_path(inspected, "slides_presentation_draft_pptx"))
    log_result = preview_sidecar_artifact(tmp_path, task_id, artifact_path(inspected, "log_stdout"), max_lines=2)

    assert csv_result["preview_type"] == "csv_rows"
    assert csv_result["preview"]["row_count_returned"] == 1
    assert len(csv_result["preview"]["rows"]) == 1
    assert report_result["preview_type"] == "markdown_lines"
    assert 0 < report_result["preview"]["line_count_returned"] <= 3
    assert image_result["preview_type"] == "image_metadata"
    assert image_result["preview"]["width"] > 0
    assert image_result["preview"]["height"] > 0
    assert ppt_result["preview_type"] == "pptx_metadata"
    assert ppt_result["preview"]["slide_count"] >= 1
    assert log_result["preview_type"] == "log_tail"
    assert log_result["preview"]["line_count_returned"] <= 2


def test_preview_does_not_return_complete_artifact_bodies_by_default(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate all artifacts without body leaks.",
        command=simple_success_command(),
        desired_outputs=["slides"],
        intelligent_mode="off",
    )
    inspected = inspect_sidecar_task(tmp_path, result["task_id"])
    csv_path = artifact_path(inspected, "metrics_normalized_csv")
    preview = preview_sidecar_artifact(tmp_path, result["task_id"], csv_path, max_rows=1)
    serialized = json.dumps(preview, ensure_ascii=False)

    assert preview["omitted"]["complete_artifact"] == "omitted_by_default"
    assert "Best val_accuracy=0.86" not in serialized
    assert serialized.count("val_accuracy") <= 2
    assert "presentation-draft.pptx" not in serialized


def test_preview_rejects_unsupported_registered_artifact(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "result.bin"
    source.write_bytes(b"\x00\x01\x02\x03")
    record = RunnerService(tmp_path).ingest_source(source)
    result = preview_sidecar_artifact(tmp_path, record.task_id, "raw/source_refs.json")

    assert result["status"] == "rejected"
    assert result["risk_flags"] == ["artifact_preview_rejected"]
