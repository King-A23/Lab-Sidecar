from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.parse
import venv
from pathlib import Path
from typing import Any


MARKER_FILE = ".lab-sidecar-release-asset-smoke"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Install a supplied Lab-Sidecar wheel into an isolated venv and run a "
            "compact CLI smoke. Local wheel paths are the default release check; "
            "HTTP(S) wheel URLs are explicit manual release checks."
        )
    )
    parser.add_argument("--wheel", required=True, help="Wheel file path, file:// URL, or explicit HTTP(S) wheel URL.")
    parser.add_argument("--version", help="Expected installed lab-sidecar version, for example 0.1.5.")
    parser.add_argument("--workspace", type=Path, required=True, help="Temporary workspace to create or clean.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root for examples. Defaults to cwd.")
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Leave the prepared workspace and venv in place after the smoke.",
    )
    args = parser.parse_args()

    repo = args.repo.resolve()
    wheel = _resolve_wheel(args.wheel)
    workspace = _prepare_workspace(args.workspace, repo)
    try:
        summary = run_release_asset_smoke(workspace=workspace, repo=repo, wheel=wheel, version=args.version)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        if not args.keep_workspace:
            shutil.rmtree(workspace, ignore_errors=True)


def run_release_asset_smoke(*, workspace: Path, repo: Path, wheel: str, version: str | None = None) -> dict[str, Any]:
    venv_dir = workspace / "venv"
    smoke_workspace = workspace / "run-workspace"
    smoke_workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / "examples", smoke_workspace / "examples")

    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    installed_python = _venv_python(venv_dir)
    installed_labsidecar = _venv_script(venv_dir, "labsidecar")
    env = _smoke_env(workspace)

    commands: list[dict[str, Any]] = []
    commands.append(_run_json([str(installed_python), "-m", "pip", "install", wheel], cwd=workspace, env=env))
    installed_version = _installed_version(installed_python, cwd=workspace, env=env)
    if version is not None and installed_version != version:
        raise RuntimeError(f"installed lab-sidecar version is {installed_version!r}; expected {version!r}")
    commands.append(_run_json([str(installed_labsidecar), "--help"], cwd=smoke_workspace, env=env))
    commands.append(_run_json([str(installed_labsidecar), "init"], cwd=smoke_workspace, env=env))
    commands.append(_run_json([str(installed_labsidecar), "doctor"], cwd=smoke_workspace, env=env))

    run_command = _shell_command([str(installed_python), "examples/simple-success/train.py", "--output", "metrics.csv"])
    run_result = _run_json([str(installed_labsidecar), "run", run_command], cwd=smoke_workspace, env=env)
    commands.append(run_result)
    task_id = _extract_task_id(run_result["stdout"])

    for args in [
        ["collect", task_id],
        ["validate", task_id, "--require", "metrics"],
    ]:
        result = _run_json([str(installed_labsidecar), *args], cwd=smoke_workspace, env=env)
        commands.append(result)
        if args[0] == "validate":
            _assert_contains(result["stdout"], ["[ok] metrics:"])

    return {
        "workspace": str(workspace),
        "run_workspace": str(smoke_workspace),
        "wheel": wheel,
        "python": str(installed_python),
        "console_script": str(installed_labsidecar),
        "installed_version": installed_version,
        "task_id": task_id,
        "status": "passed",
        "commands": commands,
    }


def _resolve_wheel(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in {"http", "https"}:
        if not parsed.path.endswith(".whl"):
            raise RuntimeError(f"wheel URL must end in .whl: {value}")
        return value
    if parsed.scheme == "file":
        path = Path(urllib.parse.unquote(parsed.path)).resolve()
    else:
        path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"wheel file was not found: {path}")
    if path.suffix != ".whl":
        raise RuntimeError(f"wheel file must end in .whl: {path}")
    return str(path)


def _installed_version(installed_python: Path, *, cwd: Path, env: dict[str, str]) -> str:
    command = [
        str(installed_python),
        "-c",
        "from importlib.metadata import version; print(version('lab-sidecar'))",
    ]
    result = _run(command, cwd=cwd, env=env)
    return result.stdout.strip()


def _prepare_workspace(path: Path, repo: Path) -> Path:
    if not (repo / "pyproject.toml").is_file():
        raise RuntimeError(f"pyproject.toml was not found under repo: {repo}")
    if not (repo / "examples").is_dir():
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
    (workspace / MARKER_FILE).write_text("temporary Lab-Sidecar release asset smoke workspace\n", encoding="utf-8")
    return workspace


def _smoke_env(workspace: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.setdefault("MPLBACKEND", "Agg")
    env["MPLCONFIGDIR"] = str(workspace / ".matplotlib")
    env["PIP_CACHE_DIR"] = str(workspace / ".pip-cache")
    return env


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_script(venv_dir: Path, name: str) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


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


def _assert_contains(output: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in output]
    if missing:
        raise RuntimeError(f"missing expected CLI output {missing!r} in:\n{output}")


if __name__ == "__main__":
    main()
