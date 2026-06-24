from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


MARKER_FILE = ".lab-sidecar-cli-full-smoke"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the canonical local CLI full smoke for Lab-Sidecar.")
    parser.add_argument("--workspace", type=Path, required=True, help="Temporary workspace to create or clean.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root. Defaults to the current directory.")
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Leave the prepared workspace in place after the smoke for inspection.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    workspace = _prepare_workspace(args.workspace, repo)
    summary: dict[str, Any] | None = None
    try:
        summary = _run_smoke(workspace, repo)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        if not args.keep_workspace:
            shutil.rmtree(workspace, ignore_errors=True)


def _prepare_workspace(path: Path, repo: Path) -> Path:
    examples = repo / "examples"
    if not examples.is_dir():
        raise RuntimeError(f"examples directory was not found under repo: {repo}")

    workspace = path.resolve()
    if workspace.exists():
        has_existing_content = any(workspace.iterdir())
        marker = workspace / MARKER_FILE
        if has_existing_content and not marker.is_file():
            raise RuntimeError(f"refusing to clear non-smoke workspace without {MARKER_FILE}: {workspace}")
        if has_existing_content:
            shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / MARKER_FILE).write_text("temporary Lab-Sidecar CLI full smoke workspace\n", encoding="utf-8")
    shutil.copytree(examples, workspace / "examples")
    return workspace


def _run_smoke(workspace: Path, repo: Path) -> dict[str, Any]:
    env = _subprocess_env(repo)
    cli_python = _python_for_repo(repo)
    tasks: dict[str, str] = {}
    statuses: dict[str, str] = {}
    results: dict[str, dict[str, Any]] = {}

    _run_cli(workspace, env, cli_python, ["init"])
    _run_cli(workspace, env, cli_python, ["doctor"])

    success_task = _success_flow(workspace, env, cli_python)
    tasks["success"] = success_task["task_id"]
    statuses["success"] = success_task["status"]
    results["success"] = success_task

    failure_task = _failure_flow(workspace, env, cli_python)
    tasks["failure"] = failure_task["task_id"]
    statuses["failure"] = failure_task["status"]
    results["failure"] = failure_task

    ingest_task = _ingest_flow(workspace, env, cli_python)
    tasks["ingest"] = ingest_task["task_id"]
    statuses["ingest"] = ingest_task["status"]
    results["ingest"] = ingest_task

    comparison = _comparison_flow(
        workspace,
        env,
        cli_python,
        success_task["task_id"],
        ingest_task["task_id"],
    )
    tasks["comparison"] = comparison["comparison_id"]
    statuses["comparison"] = comparison["status"]
    results["comparison"] = comparison

    return {
        "workspace": str(workspace),
        "python": cli_python,
        "task_ids": tasks,
        "statuses": statuses,
        "key_artifact_paths": {
            key: value["artifacts"]
            for key, value in results.items()
        },
        "package_paths": {
            key: value.get("package_path")
            for key, value in results.items()
            if value.get("package_path")
        },
        "comparison": _comparison_summary(comparison),
        "results": results,
    }


def _success_flow(workspace: Path, env: dict[str, str], cli_python: str) -> dict[str, Any]:
    command = _shell_command([cli_python, "examples/simple-success/train.py", "--output", "metrics.csv"])
    output = _run_cli(workspace, env, cli_python, ["run", command]).stdout
    task_id = _extract_task_id(output)
    for args in [
        ["collect", task_id],
        ["figures", task_id],
        ["report", task_id],
        ["slides", task_id],
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
    ]:
        _run_cli(workspace, env, cli_python, args)

    package_path = workspace / "packages" / f"success-{task_id}"
    _run_cli(workspace, env, cli_python, ["package", task_id, "--output", package_path.as_posix()])
    _run_cli(workspace, env, cli_python, ["package-verify", package_path.as_posix()])
    task_path = _task_path(workspace, task_id)
    artifacts = _common_completed_artifacts(task_path)
    artifacts["package"] = package_path.as_posix()
    _assert_artifacts_exist(artifacts)
    return {
        "task_id": task_id,
        "status": _manifest(task_path)["status"],
        "artifacts": artifacts,
        "package_path": package_path.as_posix(),
        "package_type": _package_type(package_path),
        "package_verified": True,
    }


def _failure_flow(workspace: Path, env: dict[str, str], cli_python: str) -> dict[str, Any]:
    command = _shell_command([cli_python, "examples/simple-failure/fail.py"])
    output = _run_cli(workspace, env, cli_python, ["run", command]).stdout
    task_id = _extract_task_id(output)
    for args in [
        ["status", task_id],
        ["report", task_id],
        ["slides", task_id],
        ["validate", task_id],
    ]:
        _run_cli(workspace, env, cli_python, args)

    package_path = workspace / "packages" / f"failure-{task_id}"
    _run_cli(workspace, env, cli_python, ["package", task_id, "--output", package_path.as_posix()])
    _run_cli(workspace, env, cli_python, ["package-verify", package_path.as_posix()])
    task_path = _task_path(workspace, task_id)
    artifacts = {
        "manifest": (task_path / "manifest.json").as_posix(),
        "stdout": (task_path / "stdout.log").as_posix(),
        "stderr": (task_path / "stderr.log").as_posix(),
        "report": (task_path / "reports" / "report-fragment.md").as_posix(),
        "report_summary": (task_path / "reports" / "report-summary.json").as_posix(),
        "slides": (task_path / "slides" / "presentation-draft.pptx").as_posix(),
        "slides_summary": (task_path / "slides" / "slides-summary.json").as_posix(),
        "traceability": (task_path / "provenance" / "traceability.json").as_posix(),
        "package": package_path.as_posix(),
    }
    _assert_artifacts_exist(artifacts)
    return {
        "task_id": task_id,
        "status": _manifest(task_path)["status"],
        "artifacts": artifacts,
        "package_path": package_path.as_posix(),
        "package_type": _package_type(package_path),
        "package_verified": True,
    }


def _ingest_flow(workspace: Path, env: dict[str, str], cli_python: str) -> dict[str, Any]:
    output = _run_cli(workspace, env, cli_python, ["ingest", "examples/csv-comparison"]).stdout
    task_id = _extract_task_id(output)
    for args in [
        ["collect", task_id],
        ["figures", task_id],
        ["report", task_id],
        ["slides", task_id],
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
        ["artifacts", task_id],
    ]:
        _run_cli(workspace, env, cli_python, args)

    task_path = _task_path(workspace, task_id)
    artifacts = _common_completed_artifacts(task_path)
    _assert_artifacts_exist(artifacts)
    return {
        "task_id": task_id,
        "status": _manifest(task_path)["status"],
        "artifacts": artifacts,
        "package_path": None,
        "package_type": None,
        "package_verified": None,
    }


def _comparison_flow(
    workspace: Path,
    env: dict[str, str],
    cli_python: str,
    first_task_id: str,
    second_task_id: str,
) -> dict[str, Any]:
    output = _run_cli(
        workspace,
        env,
        cli_python,
        [
            "compare",
            first_task_id,
            second_task_id,
            "--save",
            "--name",
            "smoke-comparison",
            "--figures",
            "--report",
        ],
    ).stdout
    comparison_id = _extract_comparison_id(output)
    _run_cli(workspace, env, cli_python, ["list-comparisons"])
    _run_cli(workspace, env, cli_python, ["comparison-artifacts", comparison_id])
    _run_cli(workspace, env, cli_python, ["open-comparison", comparison_id])
    _run_cli(
        workspace,
        env,
        cli_python,
        [
            "validate-comparison",
            comparison_id,
            "--require",
            "figures",
            "--require",
            "report",
            "--require",
            "package-ready",
        ],
    )
    package_path = workspace / "packages" / f"comparison-{comparison_id}"
    _run_cli(workspace, env, cli_python, ["package-comparison", comparison_id, "--output", package_path.as_posix()])
    _run_cli(workspace, env, cli_python, ["package-verify", package_path.as_posix()])
    comparison_path = workspace / ".lab-sidecar" / "comparisons" / comparison_id
    artifacts = _comparison_artifacts(comparison_path)
    artifacts["package"] = package_path.as_posix()
    artifacts["package_index"] = (package_path / "artifact-index.json").as_posix()
    artifacts["package_digest"] = (package_path / "artifact-index.sha256").as_posix()
    _assert_artifacts_exist(artifacts)
    return {
        "comparison_id": comparison_id,
        "comparison_dir": comparison_path.as_posix(),
        "status": _comparison_manifest(comparison_path)["status"],
        "artifacts": artifacts,
        "package_path": package_path.as_posix(),
        "package_type": _package_type(package_path),
        "package_verified": True,
    }


def _common_completed_artifacts(task_path: Path) -> dict[str, str]:
    figure_paths = sorted((task_path / "figures").glob("*.png"))
    figure_paths.extend(sorted((task_path / "figures").glob("*.svg")))
    return {
        "manifest": (task_path / "manifest.json").as_posix(),
        "stdout": (task_path / "stdout.log").as_posix(),
        "stderr": (task_path / "stderr.log").as_posix(),
        "metrics_csv": (task_path / "metrics" / "normalized_metrics.csv").as_posix(),
        "metrics_json": (task_path / "metrics" / "normalized_metrics.json").as_posix(),
        "collection_summary": (task_path / "metrics" / "collection-summary.json").as_posix(),
        "scenario_summary": (task_path / "metrics" / "scenario-summary.json").as_posix(),
        "figure_summary": (task_path / "figures" / "figure-summary.json").as_posix(),
        "figures": [path.as_posix() for path in figure_paths],
        "report": (task_path / "reports" / "report-fragment.md").as_posix(),
        "report_summary": (task_path / "reports" / "report-summary.json").as_posix(),
        "slides": (task_path / "slides" / "presentation-draft.pptx").as_posix(),
        "slides_summary": (task_path / "slides" / "slides-summary.json").as_posix(),
        "traceability": (task_path / "provenance" / "traceability.json").as_posix(),
    }


def _comparison_artifacts(comparison_path: Path) -> dict[str, Any]:
    figure_paths = sorted((comparison_path / "figures").glob("*.png"))
    figure_paths.extend(sorted((comparison_path / "figures").glob("*.svg")))
    return {
        "manifest": (comparison_path / "comparison-manifest.json").as_posix(),
        "summary": (comparison_path / "comparison-summary.json").as_posix(),
        "table_csv": (comparison_path / "comparison-table.csv").as_posix(),
        "table_json": (comparison_path / "comparison-table.json").as_posix(),
        "figure_summary": (comparison_path / "figures" / "figure-summary.json").as_posix(),
        "figures": [path.as_posix() for path in figure_paths],
        "report": (comparison_path / "reports" / "comparison-report-fragment.md").as_posix(),
        "report_summary": (comparison_path / "reports" / "comparison-report-summary.json").as_posix(),
        "traceability": (comparison_path / "provenance" / "traceability.json").as_posix(),
    }


def _assert_artifacts_exist(artifacts: dict[str, Any]) -> None:
    for key, value in artifacts.items():
        if isinstance(value, list):
            if not value:
                raise RuntimeError(f"expected at least one artifact path for {key}")
            for item in value:
                _assert_non_empty_path(Path(item), key)
            continue
        _assert_non_empty_path(Path(value), key)


def _assert_non_empty_path(path: Path, key: str) -> None:
    if path.is_dir():
        if not any(path.iterdir()):
            raise RuntimeError(f"artifact directory is empty for {key}: {path}")
        return
    if key in {"stdout", "stderr"}:
        if not path.is_file():
            raise RuntimeError(f"log file is missing for {key}: {path}")
        return
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"artifact is missing or empty for {key}: {path}")


def _run_cli(workspace: Path, env: dict[str, str], cli_python: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    command = [cli_python, "-m", "lab_sidecar.cli.app", *args]
    result = subprocess.run(
        command,
        cwd=workspace,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "CLI command failed\n"
            f"command: {command}\n"
            f"exit_code: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    print(f"ok: labsidecar {' '.join(args[:2])}", file=sys.stderr)
    return result


def _subprocess_env(repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(repo) if not existing else os.pathsep.join([str(repo), existing])
    env.setdefault("MPLBACKEND", "Agg")
    return env


def _python_for_repo(repo: Path) -> str:
    configured = os.environ.get("LABSIDECAR_PYTHON")
    if configured:
        return configured
    candidates = [
        repo / ".venv" / "bin" / "python",
        repo / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def _shell_command(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def _extract_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Task created: "):
            return line.split(": ", 1)[1].strip()
        if line.startswith("Imported as task: "):
            return line.split(": ", 1)[1].strip()
    raise RuntimeError(f"no task id found in CLI output:\n{output}")


def _extract_comparison_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Comparison created: "):
            return line.split(": ", 1)[1].strip()
    raise RuntimeError(f"no comparison id found in CLI output:\n{output}")


def _task_path(workspace: Path, task_id: str) -> Path:
    return workspace / ".lab-sidecar" / "tasks" / task_id


def _manifest(task_path: Path) -> dict[str, Any]:
    return json.loads((task_path / "manifest.json").read_text(encoding="utf-8"))


def _comparison_manifest(comparison_path: Path) -> dict[str, Any]:
    return json.loads((comparison_path / "comparison-manifest.json").read_text(encoding="utf-8"))


def _comparison_summary(comparison: dict[str, Any]) -> dict[str, Any]:
    artifacts = comparison["artifacts"]
    return {
        "comparison_id": comparison["comparison_id"],
        "comparison_dir": comparison["comparison_dir"],
        "table_path": artifacts["table_csv"],
        "summary_path": artifacts["summary"],
        "package_path": comparison["package_path"],
        "package_verify_status": "passed" if comparison["package_verified"] else "failed",
    }


def _package_type(package_path: Path) -> str:
    summary = json.loads((package_path / "package-summary.json").read_text(encoding="utf-8"))
    return str(summary["package_type"])


if __name__ == "__main__":
    main()
