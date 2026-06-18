from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import ArtifactRecord
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


def test_cancel_completed_and_missing_tasks_return_bounded_not_applicable(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)

    delegated = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate metrics for completed cancellation test.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )

    completed_cancel = cancel_sidecar_task(tmp_path, delegated["task_id"])
    missing_cancel = cancel_sidecar_task(tmp_path, "task_missing")
    serialized = json.dumps({"completed": completed_cancel, "missing": missing_cancel})

    assert completed_cancel["status"] == "not_cancelled"
    assert completed_cancel["summary"]["current_status"] == "completed"
    assert completed_cancel["risk_flags"] == ["cancel_sidecar_task_not_applicable"]
    assert missing_cancel["status"] == "not_cancelled"
    assert missing_cancel["risk_flags"] == ["cancel_sidecar_task_missing"]
    assert "Best val_accuracy=0.86" not in serialized
    assert completed_cancel["omitted"]["full_stdout"] == "omitted_by_default"
    assert missing_cancel["omitted"]["worker_prompt_response"] == "omitted_by_default"


def test_inspect_after_v2_cancel_returns_cancelled_state_without_log_body(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    script = tmp_path / "long_task.py"
    script.write_text("import time\nprint('cancel-ready', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    running = RunnerService(tmp_path).run(f'"{sys.executable}" long_task.py', background=True)

    cancelled = cancel_sidecar_task(tmp_path, running.task_id)
    inspected = inspect_sidecar_task(tmp_path, running.task_id)

    assert cancelled["status"] == "cancelled"
    assert inspected["status"] == "cancelled"
    assert "cancel-ready" not in json.dumps(inspected)
    assert inspected["omitted"]["full_stdout"] == "omitted_by_default"


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


def test_preview_withholds_complete_small_csv_markdown_and_log_bodies(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    script = tmp_path / "tiny_artifacts.py"
    script.write_text(
        "from pathlib import Path\n"
        "print('tiny-log-line', flush=True)\n"
        "Path('metrics.csv').write_text('epoch,accuracy\\n1,0.7\\n2,0.8\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate tiny artifacts for preview body withholding.",
        command=f'"{sys.executable}" tiny_artifacts.py',
        desired_outputs=["report"],
        intelligent_mode="off",
    )
    inspected = inspect_sidecar_task(tmp_path, result["task_id"])

    csv_result = preview_sidecar_artifact(
        tmp_path,
        result["task_id"],
        artifact_path(inspected, "metrics_normalized_csv"),
        max_rows=20,
    )
    report_result = preview_sidecar_artifact(
        tmp_path,
        result["task_id"],
        artifact_path(inspected, "report_fragment_md"),
        max_lines=80,
    )
    log_result = preview_sidecar_artifact(
        tmp_path,
        result["task_id"],
        artifact_path(inspected, "log_stdout"),
        max_lines=80,
    )

    assert csv_result["preview"]["withheld_complete_body"] is True
    assert csv_result["preview"]["row_count_returned"] == 1
    assert report_result["preview"]["withheld_complete_body"] is True
    assert log_result["preview"]["withheld_complete_body"] is True
    assert log_result["preview"]["line_count_returned"] == 0
    assert "tiny-log-line" not in json.dumps(log_result)


def test_preview_rejects_unsupported_registered_artifact(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "result.bin"
    source.write_bytes(b"\x00\x01\x02\x03")
    record = RunnerService(tmp_path).ingest_source(source)
    result = preview_sidecar_artifact(tmp_path, record.task_id, "raw/source_refs.json")

    assert result["status"] == "rejected"
    assert result["risk_flags"] == ["artifact_preview_rejected"]


def test_preview_explicitly_rejects_registered_raw_and_worker_audit_artifacts(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "result.txt"
    source.write_text("raw result body\n", encoding="utf-8")
    record = RunnerService(tmp_path).ingest_source(source)
    task_path = tmp_path / ".lab-sidecar" / "tasks" / record.task_id
    raw_notes = task_path / "raw" / "raw-notes.txt"
    raw_notes.write_text("raw secret body\n", encoding="utf-8")
    audit_dir = task_path / "intelligence" / "worker_run_test"
    audit_dir.mkdir(parents=True)
    audit_notes = audit_dir / "prompt.md"
    audit_notes.write_text("worker prompt body\n", encoding="utf-8")

    stored = load_task(tmp_path, record.task_id)
    stored.artifacts.extend(
        [
            ArtifactRecord(
                artifact_id="raw_notes_txt",
                type="raw",
                path=f"{stored.paths.task_dir}/raw/raw-notes.txt",
                description="Raw notes.",
            ),
            ArtifactRecord(
                artifact_id="worker_prompt_md",
                type="worker",
                path=f"{stored.paths.task_dir}/intelligence/worker_run_test/prompt.md",
                description="Worker prompt.",
            ),
        ]
    )
    write_manifest(manifest_path(tmp_path, record.task_id), stored)

    raw_preview = preview_sidecar_artifact(tmp_path, record.task_id, f"{stored.paths.task_dir}/raw/raw-notes.txt")
    audit_preview = preview_sidecar_artifact(
        tmp_path,
        record.task_id,
        f"{stored.paths.task_dir}/intelligence/worker_run_test/prompt.md",
    )
    serialized = json.dumps({"raw": raw_preview, "audit": audit_preview})

    assert raw_preview["status"] == "rejected"
    assert audit_preview["status"] == "rejected"
    assert "raw secret body" not in serialized
    assert "worker prompt body" not in serialized


def test_preview_rejects_worker_audit_paths_even_when_task_local(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate worker audit files for preview rejection.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="auto",
    )
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    task_path = tmp_path / ".lab-sidecar" / "tasks" / result["task_id"]
    prompt_path = task_path / "intelligence" / worker_run_id / "ai-provider-prompt.json"
    prompt_path.write_text('{"prompt":"secret worker prompt"}\n', encoding="utf-8")

    preview = preview_sidecar_artifact(
        tmp_path,
        result["task_id"],
        f".lab-sidecar/tasks/{result['task_id']}/intelligence/{worker_run_id}/ai-provider-prompt.json",
    )

    assert preview["status"] == "rejected"
    assert preview["risk_flags"] == ["artifact_preview_rejected"]
    assert "secret worker prompt" not in json.dumps(preview)


def test_preview_caps_large_requested_limits(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "metrics.csv"
    source.parent.mkdir(parents=True)
    with source.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["epoch", "accuracy"])
        writer.writeheader()
        for index in range(30):
            writer.writerow({"epoch": index, "accuracy": 0.5 + index / 100})

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Generate metrics for preview cap testing.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )
    inspected = inspect_sidecar_task(tmp_path, result["task_id"])
    csv_result = preview_sidecar_artifact(
        tmp_path,
        result["task_id"],
        artifact_path(inspected, "metrics_normalized_csv"),
        max_rows=999,
    )

    script = tmp_path / "many_lines.py"
    script.write_text(
        "\n".join(
            [
                "for index in range(120):",
                "    print(f'line-{index}-' + 'x' * 1200, flush=True)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    log_record = RunnerService(tmp_path).run(f'"{sys.executable}" many_lines.py', background=False)
    log_result = preview_sidecar_artifact(
        tmp_path,
        log_record.task_id,
        log_record.paths.stdout,
        max_lines=999,
    )

    assert csv_result["preview_type"] == "csv_rows"
    assert csv_result["preview"]["row_count_returned"] == 20
    assert csv_result["preview"]["truncated"] is True
    assert log_result["preview_type"] == "log_tail"
    assert log_result["preview"]["line_count_returned"] == 80
    assert log_result["preview"]["truncated"] is True
    assert len(log_result["preview"]["tail"][0]) == 1000
    assert "line-0" not in json.dumps(log_result)
