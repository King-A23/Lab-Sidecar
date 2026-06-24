from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.test_cli_smoke import copy_examples, extract_task_id, invoke


def _run_success_pipeline(workspace: Path) -> str:
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    run_result = invoke(workspace, ["run", command])
    assert run_result.exit_code == 0
    task_id = extract_task_id(run_result.output)
    for args in [
        ["collect", task_id],
        ["figures", task_id],
        ["report", task_id],
        ["slides", task_id],
    ]:
        result = invoke(workspace, args)
        assert result.exit_code == 0, result.output
    return task_id


def _task_path(workspace: Path, task_id: str) -> Path:
    return workspace / ".lab-sidecar" / "tasks" / task_id


def _resolve_workspace_path(workspace: Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return workspace / path


def test_validate_full_success_task_passes(tmp_path: Path) -> None:
    task_id = _run_success_pipeline(tmp_path)

    result = invoke(
        tmp_path,
        [
            "validate",
            task_id,
            "--require",
            "metrics",
            "--require",
            "figures",
            "--require",
            "report",
            "--require",
            "slides",
            "--require",
            "package-ready",
        ],
    )

    assert result.exit_code == 0
    assert "Result: ok" in result.output
    assert "Task status: completed" in result.output
    assert "Diagnostic mode: no" in result.output
    assert "[ok] manifest:" in result.output
    assert "[ok] metrics:" in result.output
    assert "[ok] figures:" in result.output
    assert "[ok] report:" in result.output
    assert "[ok] slides:" in result.output
    assert "[ok] traceability:" in result.output
    assert "[ok] package-ready:" in result.output


def test_validate_partial_task_warns_with_next_actions(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    run_result = invoke(tmp_path, ["run", command])
    assert run_result.exit_code == 0
    task_id = extract_task_id(run_result.output)

    result = invoke(tmp_path, ["validate", task_id])

    assert result.exit_code == 0
    assert "Result: warn" in result.output
    assert "[fail]" not in result.output
    assert "[warn] metrics:" in result.output
    assert f"next: labsidecar collect {task_id}" in result.output
    assert "[warn] figures:" in result.output
    assert f"next: labsidecar figures {task_id}" in result.output
    assert "[warn] report:" in result.output
    assert f"next: labsidecar report {task_id}" in result.output
    assert "[warn] slides:" in result.output
    assert f"next: labsidecar slides {task_id}" in result.output
    assert not (_task_path(tmp_path, task_id) / "packages").exists()


def test_validate_missing_figure_artifact_fails_with_path(tmp_path: Path) -> None:
    task_id = _run_success_pipeline(tmp_path)
    figure_summary_path = _task_path(tmp_path, task_id) / "figures" / "figure-summary.json"
    figure_summary = json.loads(figure_summary_path.read_text(encoding="utf-8"))
    missing_path_text = figure_summary["generated_figures"][0]["png_path"]
    missing_path = _resolve_workspace_path(tmp_path, missing_path_text)
    missing_path.unlink()

    result = invoke(tmp_path, ["validate", task_id])

    assert result.exit_code == 5
    assert "Result: fail" in result.output
    assert "[fail] figures:" in result.output
    assert missing_path_text in result.output


def test_validate_failed_diagnostic_task(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-failure/fail.py'
    run_result = invoke(tmp_path, ["run", command])
    assert run_result.exit_code == 0
    task_id = extract_task_id(run_result.output)
    assert invoke(tmp_path, ["report", task_id]).exit_code == 0
    assert invoke(tmp_path, ["slides", task_id]).exit_code == 0

    result = invoke(tmp_path, ["validate", task_id])

    assert result.exit_code == 0
    assert "Task status: failed" in result.output
    assert "Diagnostic mode: yes" in result.output
    assert "[ok] report:" in result.output
    assert "[ok] slides:" in result.output
    assert "[ok] traceability:" in result.output
    assert "[fail]" not in result.output
