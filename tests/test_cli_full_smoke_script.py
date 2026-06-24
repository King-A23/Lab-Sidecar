from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import cli_full_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cli_full_smoke_default_cleans_workspace(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"

    def fake_run_smoke(prepared_workspace: Path, repo: Path):
        assert prepared_workspace == workspace.resolve()
        assert repo == PROJECT_ROOT
        return {"workspace": str(prepared_workspace)}

    monkeypatch.setattr(cli_full_smoke, "_run_smoke", fake_run_smoke)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli_full_smoke.py",
            "--workspace",
            str(workspace),
            "--repo",
            str(PROJECT_ROOT),
        ],
    )

    cli_full_smoke.main()

    summary = json.loads(capsys.readouterr().out)
    assert summary["workspace"] == str(workspace.resolve())
    assert not workspace.exists()


def test_cli_full_smoke_script_runs_full_local_pipeline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    before_repo_state = (PROJECT_ROOT / ".lab-sidecar").exists()

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "cli_full_smoke.py"),
            "--workspace",
            str(workspace),
            "--repo",
            str(PROJECT_ROOT),
            "--keep-workspace",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["workspace"] == str(workspace.resolve())
    assert set(summary["task_ids"]) == {"success", "failure", "ingest", "comparison"}
    assert summary["statuses"] == {
        "success": "completed",
        "failure": "failed",
        "ingest": "completed",
        "comparison": "completed",
    }

    success = summary["results"]["success"]
    failure = summary["results"]["failure"]
    ingest = summary["results"]["ingest"]
    comparison = summary["results"]["comparison"]
    comparison_summary = summary["comparison"]
    assert success["package_type"] == "result"
    assert failure["package_type"] == "diagnostic"
    assert comparison["package_type"] == "comparison"
    assert success["package_verified"] is True
    assert failure["package_verified"] is True
    assert comparison["package_verified"] is True
    assert comparison_summary["comparison_id"] == comparison["comparison_id"]
    assert comparison_summary["comparison_dir"] == comparison["comparison_dir"]
    assert comparison_summary["table_path"] == comparison["artifacts"]["table_csv"]
    assert comparison_summary["summary_path"] == comparison["artifacts"]["summary"]
    assert comparison_summary["package_path"] == comparison["package_path"]
    assert comparison_summary["package_verify_status"] == "passed"
    assert ingest["package_path"] is None
    assert ingest["package_verified"] is None

    for result_item in [success, ingest]:
        artifacts = result_item["artifacts"]
        for key in [
            "metrics_csv",
            "metrics_json",
            "collection_summary",
            "scenario_summary",
            "figure_summary",
            "report",
            "report_summary",
            "slides",
            "slides_summary",
            "traceability",
        ]:
            assert _non_empty_path(artifacts[key]), key
        assert artifacts["figures"]
        assert all(_non_empty_path(path) for path in artifacts["figures"])

    for key in [
        "report",
        "report_summary",
        "slides",
        "slides_summary",
        "traceability",
        "package",
    ]:
        assert _non_empty_path(failure["artifacts"][key]), key

    for key in ["success", "failure"]:
        package_path = Path(summary["package_paths"][key])
        assert (package_path / "package-summary.json").is_file()
        assert (package_path / "provenance" / "traceability.json").is_file()

    comparison_artifacts = comparison["artifacts"]
    for key in [
        "summary",
        "table_csv",
        "table_json",
        "figure_summary",
        "report",
        "report_summary",
        "traceability",
        "package",
        "package_index",
        "package_digest",
    ]:
        assert _non_empty_path(comparison_artifacts[key]), key
    assert comparison_artifacts["figures"]
    assert all(_non_empty_path(path) for path in comparison_artifacts["figures"])
    comparison_package = Path(summary["package_paths"]["comparison"])
    assert (comparison_package / "package-summary.json").is_file()
    assert (comparison_package / "provenance" / "traceability.json").is_file()

    assert (PROJECT_ROOT / ".lab-sidecar").exists() is before_repo_state


def _non_empty_path(path_text: str) -> bool:
    path = Path(path_text)
    if path.is_dir():
        return any(path.iterdir())
    return path.is_file() and path.stat().st_size > 0
