from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.figures.service import FigureGenerationService
from lab_sidecar.intelligence import (
    delegate_experiment_artifacts,
    inspect_sidecar_task,
)
from lab_sidecar.intelligence.paths import worker_run_dir
from lab_sidecar.intelligence.validator import validate_proposal


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_examples(workspace: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "examples", workspace / "examples")


def simple_success_command() -> str:
    return f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'


def test_delegate_creates_intelligence_directory_input_bundle_and_sandbox(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Collect metrics for the synthetic training run.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 2, "log_tail_lines": 3},
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)

    assert (run_dir / "input-bundle.json").is_file()
    assert (run_dir / "validator-result.json").is_file()
    assert (run_dir / "diagnostics.md").is_file()
    assert (run_dir / "sandbox").is_dir()

    bundle = json.loads((run_dir / "input-bundle.json").read_text(encoding="utf-8"))
    assert bundle["schema_version"] == "2.1"
    assert bundle["task_id"] == task_id
    assert bundle["worker_run_id"] == worker_run_id
    assert bundle["context_budget"]["preview_rows"] == 2
    assert bundle["context_budget"]["log_tail_lines"] == 3
    assert len(bundle["logs"]["stdout_tail"]) <= 3
    csv_previews = [preview for preview in bundle["data_previews"] if preview["type"] == "csv"]
    assert csv_previews
    assert csv_previews[0]["row_sample_count"] <= 2
    assert bundle["omitted"]["full_stdout"] == "omitted_by_default"
    assert bundle["omitted"]["artifact_bodies"] == "omitted_by_default"


def test_delegate_intelligent_mode_off_returns_v1_fallback_summary(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Collect metrics only.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )

    task_id = result["task_id"]
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id

    assert result["status"] == "completed"
    assert "V1 deterministic fallback completed" in result["summary"]["headline"]
    assert result["risk_flags"] == ["intelligent_mode_off"]
    assert "intelligence" not in result["summary"]
    assert (task_path / "metrics" / "normalized_metrics.csv").is_file()
    assert not (task_path / "intelligence").exists()


def test_worker_unavailable_fallback_sets_risk_flag_and_keeps_v1_workflows_usable(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Prepare deterministic metrics, then continue with V1 figures.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 0},
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    validator = json.loads(
        (worker_run_dir(tmp_path, task_id, worker_run_id) / "validator-result.json").read_text(encoding="utf-8")
    )

    assert "intelligent_worker_unavailable" in result["risk_flags"]
    assert validator["accepted"] is False
    assert validator["checks"][0]["name"] == "worker_available"
    assert (task_path / "metrics" / "normalized_metrics.csv").is_file()

    figures = FigureGenerationService(tmp_path).generate(task_id)
    assert figures.generated
    assert (task_path / "figures" / "figure-summary.json").is_file()


def test_default_responses_omit_full_bodies_and_rows(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Collect metrics without returning bodies.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )
    inspected = inspect_sidecar_task(tmp_path, result["task_id"])

    for response in [result, inspected]:
        assert response["omitted"]["full_stdout"] == "omitted_by_default"
        assert response["omitted"]["full_stderr"] == "omitted_by_default"
        assert response["omitted"]["metrics_rows"] == "omitted_by_default"
        assert response["omitted"]["report_body"] == "omitted_by_default"
        assert response["omitted"]["ppt_content"] == "omitted_by_default"
        assert response["omitted"]["worker_prompt_response"] == "omitted_by_default"
        assert response["omitted"]["artifact_bodies"] == "omitted_by_default"
        serialized = json.dumps(response, ensure_ascii=False)
        assert "Best val_accuracy=0.86" not in serialized
        assert '"epoch": 1' not in serialized
        assert "# " not in serialized
        assert "ppt/slides" not in serialized


def test_sandbox_escape_proposal_is_rejected_without_official_artifact_changes(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Create scaffold for validation.",
        command=simple_success_command(),
        desired_outputs=["metrics"],
        intelligent_mode="auto",
    )
    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    official_before = sorted(path.relative_to(task_path).as_posix() for path in (task_path / "figures").glob("**/*"))

    validation = validate_proposal(
        root=tmp_path,
        task_id=task_id,
        worker_run_id=worker_run_id,
        proposal={
            "schema_version": "2.1",
            "proposal_type": "figure",
            "task_id": task_id,
            "worker_run_id": worker_run_id,
            "figures": [
                {
                    "figure_id": "escape",
                    "output_path": f"{task_path / 'figures' / 'escape.png'}",
                }
            ],
        },
    )

    diagnostics = (worker_run_dir(tmp_path, task_id, worker_run_id) / "diagnostics.md").read_text(encoding="utf-8")
    official_after = sorted(path.relative_to(task_path).as_posix() for path in (task_path / "figures").glob("**/*"))

    assert validation.accepted is False
    assert any(check.name == "sandbox_paths_only" and check.status == "failed" for check in validation.checks)
    assert "path escapes sandbox" in diagnostics
    assert official_after == official_before
    assert not (task_path / "figures" / "escape.png").exists()
