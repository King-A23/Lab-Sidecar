from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import wheel_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_smoke_default_cleans_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"

    def fake_run_smoke(prepared_workspace: Path, repo: Path):
        assert prepared_workspace == workspace.resolve()
        assert repo == PROJECT_ROOT
        return {"workspace": str(prepared_workspace)}

    monkeypatch.setattr(wheel_smoke, "_run_smoke", fake_run_smoke)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "wheel_smoke.py",
            "--workspace",
            str(workspace),
            "--repo",
            str(PROJECT_ROOT),
        ],
    )

    wheel_smoke.main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["workspace"] == str(workspace.resolve())
    assert not workspace.exists()


def test_wheel_smoke_script_help() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "wheel_smoke.py"), "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--workspace" in result.stdout
    assert "--repo" in result.stdout
    assert "PIP_NO_INDEX/PIP_FIND_LINKS" in result.stdout


def test_wheel_smoke_refuses_non_smoke_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "user-file.txt").write_text("do not delete\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "wheel_smoke.py"),
            "--workspace",
            str(workspace),
            "--repo",
            str(PROJECT_ROOT),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode != 0
    assert "refusing to clear non-smoke workspace" in result.stderr
    assert (workspace / "user-file.txt").read_text(encoding="utf-8") == "do not delete\n"


def test_wheel_smoke_summary_includes_comparison_contract(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    before_repo_state = (PROJECT_ROOT / ".lab-sidecar").exists()

    def fake_run(command, cwd: Path, env):
        if "-m build" in " ".join(map(str, command)):
            dist_dir = Path(command[-1])
            dist_dir.mkdir(parents=True, exist_ok=True)
            (dist_dir / "lab_sidecar-0.1.0-py3-none-any.whl").write_text("wheel\n", encoding="utf-8")
        if command[:3] and command[-3:] == ["-m", "pip", "install"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_run_json(command, cwd: Path, env):
        args = [str(part) for part in command]
        text = " ".join(args)
        if " run " in f" {text} ":
            stdout = "Task created: task_success\n"
        elif " ingest " in f" {text} ":
            stdout = "Imported as task: task_comparison\n"
        elif " compare " in f" {text} ":
            stdout = "Comparison created: comparison_20260624_120000_abcdef\n"
        elif " open-comparison " in f" {text} ":
            stdout = str(cwd / ".lab-sidecar" / "comparisons" / "comparison_20260624_120000_abcdef") + "\n"
        else:
            stdout = ""
        return {
            "command": wheel_smoke._display_command(args),
            "exit_code": 0,
            "stdout": stdout,
            "stderr": "",
        }

    def fake_venv_create(self, env_dir):
        bin_dir = Path(env_dir) / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "python").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "labsidecar").write_text("#!/bin/sh\n", encoding="utf-8")

    def write_fixture_outputs(summary_workspace: Path) -> None:
        task_path = summary_workspace / "run-workspace" / ".lab-sidecar" / "tasks" / "task_success"
        comparison_path = summary_workspace / "run-workspace" / ".lab-sidecar" / "comparisons" / "comparison_20260624_120000_abcdef"
        package_path = summary_workspace / "run-workspace" / "packages" / "success-task_success"
        comparison_package_path = summary_workspace / "run-workspace" / "packages" / "comparison-comparison_20260624_120000_abcdef"
        for path in [
            task_path / "figures" / "plot.png",
            task_path / "figures" / "plot.svg",
            comparison_path / "figures" / "comparison_score.png",
            comparison_path / "figures" / "comparison_score.svg",
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("image\n", encoding="utf-8")
        for path in [
            task_path / "manifest.json",
            task_path / "stdout.log",
            task_path / "stderr.log",
            task_path / "metrics" / "normalized_metrics.csv",
            task_path / "metrics" / "normalized_metrics.json",
            task_path / "metrics" / "collection-summary.json",
            task_path / "metrics" / "scenario-summary.json",
            task_path / "figures" / "figure-spec.yaml",
            task_path / "figures" / "figure-summary.json",
            task_path / "reports" / "report-fragment.md",
            task_path / "reports" / "report-summary.json",
            task_path / "slides" / "presentation-draft.pptx",
            task_path / "slides" / "slides-summary.json",
            task_path / "provenance" / "traceability.json",
            package_path / "artifact-index.json",
            package_path / "artifact-index.sha256",
            comparison_path / "comparison-summary.json",
            comparison_path / "comparison-table.csv",
            comparison_path / "comparison-table.json",
            comparison_path / "figures" / "figure-summary.json",
            comparison_path / "reports" / "comparison-report-fragment.md",
            comparison_path / "reports" / "comparison-report-summary.json",
            comparison_path / "provenance" / "traceability.json",
            comparison_package_path / "artifact-index.json",
            comparison_package_path / "artifact-index.sha256",
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("artifact\n", encoding="utf-8")
        (task_path / "manifest.json").write_text(json.dumps({"status": "completed"}) + "\n", encoding="utf-8")
        (comparison_path / "comparison-manifest.json").write_text(
            json.dumps({"status": "completed"}) + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(wheel_smoke, "_run", fake_run)
    monkeypatch.setattr(wheel_smoke, "_run_json", fake_run_json)
    monkeypatch.setattr(wheel_smoke.venv.EnvBuilder, "create", fake_venv_create)

    prepared = wheel_smoke._prepare_workspace(workspace, PROJECT_ROOT)
    write_fixture_outputs(prepared)
    summary = wheel_smoke._run_smoke(prepared, PROJECT_ROOT)

    comparison = summary["comparison"]
    assert comparison["comparison_id"] == summary["comparison_id"]
    assert comparison["comparison_dir"].endswith("/.lab-sidecar/comparisons/comparison_20260624_120000_abcdef")
    assert comparison["table_path"] == summary["comparison_artifacts"]["table_csv"]
    assert comparison["summary_path"] == summary["comparison_artifacts"]["summary"]
    assert comparison["package_path"].endswith("/packages/comparison-comparison_20260624_120000_abcdef")
    assert comparison["package_verify_status"] == "passed"
    command_log = "\n".join(item["command"] for item in summary["commands"])
    for command in [
        "compare",
        "list-comparisons",
        "comparison-artifacts",
        "open-comparison",
        "validate-comparison",
        "package-comparison",
        "package-verify",
    ]:
        assert command in command_log
    assert (PROJECT_ROOT / ".lab-sidecar").exists() is before_repo_state
