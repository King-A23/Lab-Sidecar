from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any


MARKER_FILE = ".lab-sidecar-wheel-smoke"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Lab-Sidecar wheel and smoke-test an installed CLI. "
            "Dependency installation uses pip's environment, so online PyPI "
            "access or a prepared wheelhouse via PIP_NO_INDEX/PIP_FIND_LINKS "
            "is required."
        )
    )
    parser.add_argument("--workspace", type=Path, required=True, help="Temporary workspace to create or clean.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root. Defaults to the current directory.")
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Leave the prepared workspace and build venv in place after the smoke.",
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


def _run_smoke(workspace: Path, repo: Path) -> dict[str, Any]:
    dist_dir = workspace / "dist"
    venv_dir = workspace / "venv"
    smoke_workspace = workspace / "run-workspace"
    smoke_workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / "examples", smoke_workspace / "examples")

    build_python = _python_for_repo(repo)
    env = _smoke_env(workspace, repo)
    _run([build_python, "-m", "build", "--outdir", str(dist_dir)], cwd=repo, env=env)
    wheel = _latest_wheel(dist_dir)

    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    installed_python = _venv_python(venv_dir)
    installed_labsidecar = _venv_script(venv_dir, "labsidecar")
    env = _smoke_env(workspace)
    _run([installed_python, "-m", "pip", "install", str(wheel)], cwd=workspace, env=env)

    commands: list[dict[str, Any]] = []
    commands.append(_run_json([installed_python, "-m", "lab_sidecar.cli.app", "--help"], cwd=smoke_workspace, env=env))
    commands.append(_run_json([str(installed_labsidecar), "--help"], cwd=smoke_workspace, env=env))
    commands.append(_run_json([str(installed_labsidecar), "init"], cwd=smoke_workspace, env=env))
    commands.append(_run_json([str(installed_labsidecar), "doctor"], cwd=smoke_workspace, env=env))

    run_command = _shell_command([str(installed_python), "examples/simple-success/train.py", "--output", "metrics.csv"])
    run_result = _run_json([str(installed_labsidecar), "run", run_command], cwd=smoke_workspace, env=env)
    commands.append(run_result)
    task_id = _extract_task_id(run_result["stdout"])

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
        result = _run_json([str(installed_labsidecar), *args], cwd=smoke_workspace, env=env)
        commands.append(result)
        if args[0] == "validate":
            _assert_contains(result["stdout"], ["Result: ok", "[ok] package-ready:", "[ok] traceability:"])

    package_path = smoke_workspace / "packages" / f"success-{task_id}"
    commands.append(
        _run_json(
            [str(installed_labsidecar), "package", task_id, "--output", package_path.as_posix()],
            cwd=smoke_workspace,
            env=env,
        )
    )
    verify = _run_json([str(installed_labsidecar), "package-verify", package_path.as_posix()], cwd=smoke_workspace, env=env)
    commands.append(verify)
    _assert_contains(verify["stdout"], ["Package verified:", "Checked files:"])

    task_path = smoke_workspace / ".lab-sidecar" / "tasks" / task_id
    second_task_id = _create_installed_comparison_task(
        smoke_workspace=smoke_workspace,
        installed_labsidecar=installed_labsidecar,
        commands=commands,
        env=env,
    )
    comparison_id, comparison_package_path = _run_installed_comparison_flow(
        smoke_workspace=smoke_workspace,
        installed_labsidecar=installed_labsidecar,
        commands=commands,
        env=env,
        first_task_id=task_id,
        second_task_id=second_task_id,
    )
    comparison_path = smoke_workspace / ".lab-sidecar" / "comparisons" / comparison_id
    artifacts = _expected_artifacts(task_path, package_path)
    comparison_artifacts = _expected_comparison_artifacts(comparison_path, comparison_package_path)
    _assert_artifacts_exist(artifacts)
    _assert_artifacts_exist(comparison_artifacts)

    return {
        "workspace": str(workspace),
        "run_workspace": str(smoke_workspace),
        "wheel": str(wheel),
        "python": str(installed_python),
        "console_script": str(installed_labsidecar),
        "task_id": task_id,
        "comparison_id": comparison_id,
        "status": _manifest(task_path)["status"],
        "package_path": str(package_path),
        "package_verified": True,
        "artifacts": artifacts,
        "comparison_artifacts": comparison_artifacts,
        "comparison": _comparison_summary(
            comparison_id=comparison_id,
            comparison_path=comparison_path,
            comparison_artifacts=comparison_artifacts,
            package_path=comparison_package_path,
        ),
        "commands": commands,
    }


def _create_installed_comparison_task(
    *,
    smoke_workspace: Path,
    installed_labsidecar: Path,
    commands: list[dict[str, Any]],
    env: dict[str, str],
) -> str:
    source = smoke_workspace / "comparison-run"
    source.mkdir()
    (source / "metrics.csv").write_text(
        "epoch,val_accuracy,val_loss\n1,0.72,0.48\n2,0.84,0.36\n",
        encoding="utf-8",
    )
    ingest = _run_json([str(installed_labsidecar), "ingest", "comparison-run", "--name", "wheel-comparison"], cwd=smoke_workspace, env=env)
    commands.append(ingest)
    task_id = _extract_ingested_task_id(ingest["stdout"])
    commands.append(_run_json([str(installed_labsidecar), "collect", task_id], cwd=smoke_workspace, env=env))
    return task_id


def _run_installed_comparison_flow(
    *,
    smoke_workspace: Path,
    installed_labsidecar: Path,
    commands: list[dict[str, Any]],
    env: dict[str, str],
    first_task_id: str,
    second_task_id: str,
) -> tuple[str, Path]:
    compare = _run_json(
        [
            str(installed_labsidecar),
            "compare",
            first_task_id,
            second_task_id,
            "--save",
            "--name",
            "wheel-smoke-comparison",
            "--figures",
            "--report",
        ],
        cwd=smoke_workspace,
        env=env,
    )
    commands.append(compare)
    comparison_id = _extract_comparison_id(compare["stdout"])
    listing = _run_json([str(installed_labsidecar), "list-comparisons"], cwd=smoke_workspace, env=env)
    commands.append(listing)
    _assert_contains(listing["stdout"], [comparison_id, "wheel-smoke-comparison", "source_tasks", "figures", "report"])
    artifact_listing = _run_json([str(installed_labsidecar), "comparison-artifacts", comparison_id], cwd=smoke_workspace, env=env)
    commands.append(artifact_listing)
    _assert_contains(
        artifact_listing["stdout"],
        [
            "comparison-manifest.json",
            "comparison-summary.json",
            "comparison-table.csv",
            "reports/comparison-report-fragment.md",
            "provenance/traceability.json",
        ],
    )
    opened = _run_json([str(installed_labsidecar), "open-comparison", comparison_id], cwd=smoke_workspace, env=env)
    commands.append(opened)
    _assert_contains(opened["stdout"], [(smoke_workspace / ".lab-sidecar" / "comparisons" / comparison_id).resolve().as_posix()])
    validation = _run_json(
        [
            str(installed_labsidecar),
            "validate-comparison",
            comparison_id,
            "--require",
            "figures",
            "--require",
            "report",
            "--require",
            "package-ready",
        ],
        cwd=smoke_workspace,
        env=env,
    )
    commands.append(validation)
    _assert_contains(validation["stdout"], ["Result: ok", "[ok] package-ready:", "[ok] traceability:"])
    package_path = smoke_workspace / "packages" / f"comparison-{comparison_id}"
    commands.append(
        _run_json(
            [str(installed_labsidecar), "package-comparison", comparison_id, "--output", package_path.as_posix()],
            cwd=smoke_workspace,
            env=env,
        )
    )
    verify = _run_json([str(installed_labsidecar), "package-verify", package_path.as_posix()], cwd=smoke_workspace, env=env)
    commands.append(verify)
    _assert_contains(verify["stdout"], ["Package verified:", "Checked files:"])
    return comparison_id, package_path


def _prepare_workspace(path: Path, repo: Path) -> Path:
    if not (repo / "pyproject.toml").is_file():
        raise RuntimeError(f"pyproject.toml was not found under repo: {repo}")
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
    (workspace / MARKER_FILE).write_text("temporary Lab-Sidecar wheel smoke workspace\n", encoding="utf-8")
    return workspace


def _smoke_env(workspace: Path, repo: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if repo is None:
        env.pop("PYTHONPATH", None)
    else:
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(repo) if not existing else os.pathsep.join([str(repo), existing])
    env.setdefault("MPLBACKEND", "Agg")
    env["MPLCONFIGDIR"] = str(workspace / ".matplotlib")
    env["PIP_CACHE_DIR"] = str(workspace / ".pip-cache")
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


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def _latest_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("*.whl"), key=lambda path: path.stat().st_mtime)
    if not wheels:
        raise RuntimeError(f"no wheel was built under {dist_dir}")
    return wheels[-1]


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(_failure_message(command, result))
    print(f"ok: {_display_command(command)}", file=sys.stderr)
    return result


def _run_json(command: list[str], cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    result = _run(command, cwd=cwd, env=env)
    return {
        "command": _display_command(command),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _failure_message(command: list[str], result: subprocess.CompletedProcess[str]) -> str:
    return (
        "command failed\n"
        f"command: {_display_command(command)}\n"
        f"exit_code: {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _display_command(command: list[os.PathLike[str] | str]) -> str:
    parts = [os.fspath(part) for part in command]
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def _shell_command(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def _extract_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Task created: "):
            return line.split(": ", 1)[1].strip()
    raise RuntimeError(f"no task id found in CLI output:\n{output}")


def _extract_ingested_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Imported as task: "):
            return line.split(": ", 1)[1].strip()
    raise RuntimeError(f"no ingested task id found in CLI output:\n{output}")


def _extract_comparison_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Comparison created: "):
            return line.split(": ", 1)[1].strip()
    raise RuntimeError(f"no comparison id found in CLI output:\n{output}")


def _expected_artifacts(task_path: Path, package_path: Path) -> dict[str, Any]:
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
        "figure_spec": (task_path / "figures" / "figure-spec.yaml").as_posix(),
        "figure_summary": (task_path / "figures" / "figure-summary.json").as_posix(),
        "figures": [path.as_posix() for path in figure_paths],
        "report": (task_path / "reports" / "report-fragment.md").as_posix(),
        "report_summary": (task_path / "reports" / "report-summary.json").as_posix(),
        "slides": (task_path / "slides" / "presentation-draft.pptx").as_posix(),
        "slides_summary": (task_path / "slides" / "slides-summary.json").as_posix(),
        "traceability": (task_path / "provenance" / "traceability.json").as_posix(),
        "package": package_path.as_posix(),
        "package_index": (package_path / "artifact-index.json").as_posix(),
        "package_digest": (package_path / "artifact-index.sha256").as_posix(),
    }


def _expected_comparison_artifacts(comparison_path: Path, package_path: Path) -> dict[str, Any]:
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
        "package": package_path.as_posix(),
        "package_index": (package_path / "artifact-index.json").as_posix(),
        "package_digest": (package_path / "artifact-index.sha256").as_posix(),
    }


def _comparison_summary(
    *,
    comparison_id: str,
    comparison_path: Path,
    comparison_artifacts: dict[str, Any],
    package_path: Path,
) -> dict[str, Any]:
    return {
        "comparison_id": comparison_id,
        "comparison_dir": comparison_path.as_posix(),
        "table_path": comparison_artifacts["table_csv"],
        "summary_path": comparison_artifacts["summary"],
        "package_path": package_path.as_posix(),
        "package_verify_status": "passed",
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


def _assert_contains(output: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in output]
    if missing:
        raise RuntimeError(f"missing expected CLI output {missing!r} in:\n{output}")


def _manifest(task_path: Path) -> dict[str, Any]:
    return json.loads((task_path / "manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
