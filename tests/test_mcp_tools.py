from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.mcp.safety import assess_run_command
from lab_sidecar.mcp.tools import LabSidecarMCPTools


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_examples(workspace: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "examples", workspace / "examples")


def test_mcp_safety_blocks_destructive_commands(tmp_path: Path) -> None:
    init_workspace(tmp_path)

    decision = assess_run_command(tmp_path, "Remove-Item -Recurse .")

    assert decision.allowed is False
    assert decision.requires_confirmation is False
    assert decision.level == "blocked"
    assert decision.reasons


def test_mcp_safety_requires_confirmation_for_shell_chaining(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    command = f'"{sys.executable}" -c "print(1)" && echo done'

    decision = assess_run_command(tmp_path, command)

    assert decision.allowed is False
    assert decision.requires_confirmation is True
    assert decision.confirmation_token

    confirmed = assess_run_command(tmp_path, command, risk_acceptance=decision.confirmation_token)
    assert confirmed.allowed is True
    assert confirmed.level == "confirmed"


def test_mcp_safety_blocks_workspace_external_cwd(tmp_path: Path) -> None:
    init_workspace(tmp_path)

    decision = assess_run_command(tmp_path, f'"{sys.executable}" -c "print(1)"', cwd=tmp_path.parent)

    assert decision.allowed is False
    assert "outside" in " ".join(decision.reasons)


def test_mcp_safety_blocks_workspace_external_absolute_path_argument(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    outside = tmp_path.parent / "outside.csv"
    inside = tmp_path / "inside.csv"

    blocked = assess_run_command(tmp_path, f'"{sys.executable}" script.py --output "{outside}"')
    allowed = assess_run_command(tmp_path, f'"{sys.executable}" script.py --output "{inside}"')

    assert blocked.allowed is False
    assert "outside" in " ".join(blocked.reasons)
    assert allowed.allowed is True


def test_mcp_direct_success_chain_uses_summaries_and_artifacts(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    tools = LabSidecarMCPTools(tmp_path)
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'

    run_result = tools.run_experiment(command, background=False)

    assert run_result["task_status"] == "completed"
    task_id = run_result["task_id"]
    assert task_id
    assert run_result["omitted"]["full_stdout"] == "omitted_by_default"
    assert "Best val_accuracy" not in str(run_result)

    inspect_result = tools.inspect_results(task_id)
    assert inspect_result["task_status"] == "completed"
    assert inspect_result["summary"]["metrics"]["row_count"] == 5
    assert inspect_result["summary"]["metrics"]["processed_files"][0]["source_file"] == "metrics.csv"
    assert "log_tail" not in inspect_result["summary"]
    assert inspect_result["omitted"]["log_tail"] == "omitted_by_default"

    figures_result = tools.make_figures(task_id)
    assert figures_result["summary"]["figure_count"] == 2

    report_result = tools.generate_report_fragment(task_id)
    assert report_result["summary"]["report_path"].endswith("reports/report-fragment.md")
    assert report_result["summary"]["preview"] is None

    slides_result = tools.generate_slides(task_id)
    assert slides_result["summary"]["slide_count"] == 7
    assert all(slides_result["summary"]["qa_checks"].values())
    artifact_paths = {artifact["path"] for artifact in slides_result["artifacts"]}
    assert "slides/presentation-draft.pptx" in artifact_paths
    assert "slides/slides-summary.json" in artifact_paths


def test_mcp_inspect_log_tail_is_opt_in_and_bounded(tmp_path: Path) -> None:
    script = tmp_path / "many_lines.py"
    script.write_text(
        "\n".join(
            [
                "for index in range(30):",
                "    print(f'line-{index}', flush=True)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    init_workspace(tmp_path)
    tools = LabSidecarMCPTools(tmp_path)
    result = tools.run_experiment(f'"{sys.executable}" many_lines.py', background=False)
    task_id = result["task_id"]

    default_inspect = tools.inspect_results(task_id, collect_metrics=False)
    assert "log_tail" not in default_inspect["summary"]
    assert default_inspect["omitted"]["log_tail"] == "omitted_by_default"

    with_tail = tools.inspect_results(task_id, collect_metrics=False, include_log_tail=True, log_tail_lines=100)
    tail = with_tail["summary"]["log_tail"]["stdout"]
    assert with_tail["omitted"]["log_tail"] == "bounded_tail_returned"
    assert len(tail) == 20
    assert tail[0] == "line-10"
    assert tail[-1] == "line-29"
    assert "line-0" not in str(with_tail)


def test_mcp_report_preview_is_omitted_by_default_and_bounded(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    tools = LabSidecarMCPTools(tmp_path)
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = tools.run_experiment(command, background=False)["task_id"]

    default_report = tools.generate_report_fragment(task_id)
    assert default_report["summary"]["preview"] is None
    assert default_report["omitted"]["report_markdown"] == "omitted_by_default"

    preview_report = tools.generate_report_fragment(task_id, preview_chars=5000)
    preview = preview_report["summary"]["preview"]
    assert isinstance(preview, str)
    assert 0 < len(preview) <= 2000
    assert preview_report["omitted"]["report_markdown"] == "bounded_preview_returned"
    assert preview.startswith("#")


def test_mcp_failed_task_returns_failure_summary_without_full_stderr(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    init_workspace(tmp_path)
    tools = LabSidecarMCPTools(tmp_path)

    result = tools.run_experiment(f'"{sys.executable}" examples/simple-failure/fail.py', background=False)

    assert result["task_status"] == "failed"
    assert "FileNotFoundError" in result["summary"]["failure_summary"]
    assert "Traceback" not in str(result["artifacts"])
    assert result["omitted"]["full_stderr"] == "omitted_by_default"


def test_mcp_background_long_task_returns_task_id_without_log_body(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    script = tmp_path / "long_task.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('ready', flush=True)",
                "time.sleep(5)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    tools = LabSidecarMCPTools(tmp_path)

    result = tools.run_experiment(f'"{sys.executable}" long_task.py', background=True)

    assert result["task_id"]
    assert result["task_status"] == "running"
    assert "ready" not in str(result)

    task_id = result["task_id"]
    deadline = time.time() + 2
    while time.time() < deadline:
        inspect = tools.inspect_results(task_id, collect_metrics=False)
        if inspect["task_status"] == "running":
            break
        time.sleep(0.1)
    assert inspect["task_status"] == "running"

    cancel = tools.cancel_experiment(task_id)

    assert cancel["task_status"] == "cancelled"
    assert "ready" not in str(cancel)
    inspected = tools.inspect_results(task_id, collect_metrics=False)
    assert inspected["task_status"] == "cancelled"
