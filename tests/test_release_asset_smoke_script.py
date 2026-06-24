from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts import release_asset_smoke


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_asset_smoke_resolves_local_wheel_and_file_url(tmp_path: Path) -> None:
    wheel = tmp_path / "lab_sidecar-0.1.5-py3-none-any.whl"
    wheel.write_text("wheel\n", encoding="utf-8")

    assert release_asset_smoke._resolve_wheel(str(wheel)) == str(wheel.resolve())
    assert release_asset_smoke._resolve_wheel(wheel.resolve().as_uri()) == str(wheel.resolve())


def test_release_asset_smoke_resolves_https_wheel_url_unchanged() -> None:
    wheel_url = "https://example.invalid/releases/lab_sidecar-0.1.5-py3-none-any.whl"

    assert release_asset_smoke._resolve_wheel(wheel_url) == wheel_url


def test_release_asset_smoke_refuses_non_wheel_file(tmp_path: Path) -> None:
    path = tmp_path / "not-a-wheel.txt"
    path.write_text("not wheel\n", encoding="utf-8")

    try:
        release_asset_smoke._resolve_wheel(str(path))
    except RuntimeError as exc:
        assert "must end in .whl" in str(exc)
    else:
        raise AssertionError("expected non-wheel file to be rejected")


def test_release_asset_smoke_refuses_non_wheel_http_urls() -> None:
    for wheel_url in [
        "http://example.invalid/releases/lab_sidecar-0.1.5.zip",
        "https://example.invalid/releases/lab_sidecar-0.1.5",
    ]:
        try:
            release_asset_smoke._resolve_wheel(wheel_url)
        except RuntimeError as exc:
            message = str(exc)
            assert "wheel URL must end in .whl" in message
            assert wheel_url in message
        else:
            raise AssertionError(f"expected non-wheel URL to be rejected: {wheel_url}")


def test_release_asset_smoke_refuses_non_smoke_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "user-file.txt").write_text("do not delete\n", encoding="utf-8")
    wheel = tmp_path / "lab_sidecar-0.1.5-py3-none-any.whl"
    wheel.write_text("wheel\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "release_asset_smoke.py"),
            "--workspace",
            str(workspace),
            "--repo",
            str(PROJECT_ROOT),
            "--wheel",
            str(wheel),
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


def test_release_asset_smoke_local_wheel_flow_is_summary_shaped(tmp_path: Path, monkeypatch) -> None:
    wheel = tmp_path / "lab_sidecar-0.1.5-py3-none-any.whl"
    wheel.write_text("wheel\n", encoding="utf-8")
    workspace = tmp_path / "workspace"

    def fake_venv_create(self, env_dir):
        bin_dir = Path(env_dir) / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "python").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "labsidecar").write_text("#!/bin/sh\n", encoding="utf-8")

    def fake_run_json(command, cwd: Path, env):
        args = [str(part) for part in command]
        text = " ".join(args)
        if " run " in f" {text} ":
            stdout = "Task created: task_asset\n"
        elif " validate " in f" {text} ":
            stdout = "Result: ok\n[ok] metrics: present\n"
        else:
            stdout = ""
        return {
            "command": release_asset_smoke._display_command(args),
            "exit_code": 0,
            "stdout": stdout,
            "stderr": "",
        }

    def fake_installed_version(installed_python: Path, *, cwd: Path, env):
        return "0.1.5"

    monkeypatch.setattr(release_asset_smoke.venv.EnvBuilder, "create", fake_venv_create)
    monkeypatch.setattr(release_asset_smoke, "_run_json", fake_run_json)
    monkeypatch.setattr(release_asset_smoke, "_installed_version", fake_installed_version)

    prepared = release_asset_smoke._prepare_workspace(workspace, PROJECT_ROOT)
    summary = release_asset_smoke.run_release_asset_smoke(
        workspace=prepared,
        repo=PROJECT_ROOT,
        wheel=str(wheel),
        version="0.1.5",
    )

    assert summary["wheel"] == str(wheel)
    assert summary["installed_version"] == "0.1.5"
    assert summary["task_id"] == "task_asset"
    assert summary["status"] == "passed"
    command_log = "\n".join(item["command"] for item in summary["commands"])
    assert "pip install" in command_log
    assert "labsidecar --help" in command_log
    assert "labsidecar doctor" in command_log
    assert "labsidecar collect task_asset" in command_log
    assert "labsidecar validate task_asset --require metrics" in command_log
    assert not (PROJECT_ROOT / ".lab-sidecar").exists()


def test_release_asset_smoke_rejects_unexpected_installed_version(tmp_path: Path, monkeypatch) -> None:
    wheel = tmp_path / "lab_sidecar-0.1.4-py3-none-any.whl"
    wheel.write_text("wheel\n", encoding="utf-8")
    workspace = tmp_path / "workspace"

    def fake_venv_create(self, env_dir):
        bin_dir = Path(env_dir) / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "python").write_text("#!/bin/sh\n", encoding="utf-8")
        (bin_dir / "labsidecar").write_text("#!/bin/sh\n", encoding="utf-8")

    def fake_run_json(command, cwd: Path, env):
        return {
            "command": release_asset_smoke._display_command([str(part) for part in command]),
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }

    def fake_installed_version(installed_python: Path, *, cwd: Path, env):
        return "0.1.4"

    monkeypatch.setattr(release_asset_smoke.venv.EnvBuilder, "create", fake_venv_create)
    monkeypatch.setattr(release_asset_smoke, "_run_json", fake_run_json)
    monkeypatch.setattr(release_asset_smoke, "_installed_version", fake_installed_version)

    prepared = release_asset_smoke._prepare_workspace(workspace, PROJECT_ROOT)
    try:
        release_asset_smoke.run_release_asset_smoke(
            workspace=prepared,
            repo=PROJECT_ROOT,
            wheel=str(wheel),
            version="0.1.5",
        )
    except RuntimeError as exc:
        assert "installed lab-sidecar version is '0.1.4'; expected '0.1.5'" in str(exc)
    else:
        raise AssertionError("expected version mismatch to be rejected")


def test_release_asset_smoke_script_help() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "release_asset_smoke.py"), "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--wheel" in result.stdout
    assert "--version" in result.stdout
    assert "HTTP(S) wheel URLs" in result.stdout
    assert "manual release checks" in result.stdout
