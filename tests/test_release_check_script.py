from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts import release_check


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_minimal_repo(repo: Path, *, version: str = "0.1.5") -> Path:
    (repo / "lab_sidecar").mkdir()
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "lab-sidecar"',
                f'version = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (repo / "lab_sidecar" / "__init__.py").write_text(
        f'"""Lab-Sidecar package."""\n\n__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (repo / "CHANGELOG.md").write_text(f"# Changelog\n\n## [{version}] - 2026-06-25\n\n- Test entry.\n", encoding="utf-8")
    dist = repo / "dist"
    dist.mkdir()
    _write_wheel(dist / f"lab_sidecar-{version}-py3-none-any.whl", version=version)
    _write_sdist(dist / f"lab_sidecar-{version}.tar.gz", version=version)
    return dist


def _metadata_text(version: str) -> str:
    return f"Metadata-Version: 2.4\nName: lab-sidecar\nVersion: {version}\n"


def _write_wheel(path: Path, *, version: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"lab_sidecar-{version}.dist-info/METADATA", _metadata_text(version))
        archive.writestr(f"lab_sidecar-{version}.dist-info/WHEEL", "Wheel-Version: 1.0\n")


def _write_sdist(path: Path, *, version: str) -> None:
    payload = _metadata_text(version).encode("utf-8")
    info = tarfile.TarInfo(f"lab_sidecar-{version}/PKG-INFO")
    info.size = len(payload)
    with tarfile.open(path, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(payload))


def _patch_git_diff_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, cwd: Path, text: bool, stdout, stderr, check: bool):
        assert command in (
            ["git", "diff", "--check"],
            ["git", "diff", "--cached", "--check"],
            ["git", "diff-tree", "--check", "--root", "--no-commit-id", "-r", "HEAD"],
        )
        assert text is True
        assert check is False
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(release_check.subprocess, "run", fake_run)


def test_release_check_passes_and_reports_dist_digests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo)
    _patch_git_diff_ok(monkeypatch)

    messages = release_check.run_release_check(repo=repo, version="0.1.5", tag="v0.1.5")

    expected_wheel_digest = hashlib.sha256((repo / "dist" / "lab_sidecar-0.1.5-py3-none-any.whl").read_bytes()).hexdigest()
    expected_sdist_digest = hashlib.sha256((repo / "dist" / "lab_sidecar-0.1.5.tar.gz").read_bytes()).hexdigest()
    assert "ok: pyproject.toml project.version is 0.1.5" in messages
    assert "ok: lab_sidecar.__version__ is 0.1.5" in messages
    assert "ok: CHANGELOG.md contains a [0.1.5] entry" in messages
    assert "ok: git diff --check passed" in messages
    assert "ok: staged git diff --check passed" in messages
    assert "ok: committed HEAD whitespace check passed" in messages
    assert "ok: repository root does not contain .lab-sidecar" in messages
    assert "ok: lab_sidecar-0.1.5-py3-none-any.whl metadata declares lab-sidecar 0.1.5" in messages
    assert "ok: lab_sidecar-0.1.5.tar.gz metadata declares lab-sidecar 0.1.5" in messages
    assert f"sha256 lab_sidecar-0.1.5-py3-none-any.whl {expected_wheel_digest}" in messages
    assert f"sha256 lab_sidecar-0.1.5.tar.gz {expected_sdist_digest}" in messages
    assert messages[-1] == "ok: release check completed without creating tags, releases, uploads, or publishes"


def test_release_check_rejects_version_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo, version="0.1.4")
    _patch_git_diff_ok(monkeypatch)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5")

    message = "\n".join(exc_info.value.failures)
    assert "pyproject.toml project.version is '0.1.4'; expected '0.1.5'" in message
    assert "lab_sidecar/__init__.py __version__ is '0.1.4'; expected '0.1.5'" in message
    assert "CHANGELOG.md does not contain a heading for [0.1.5]" in message


def test_release_check_rejects_stale_dist_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    dist = _write_minimal_repo(repo)
    (dist / "lab_sidecar-0.1.4-py3-none-any.whl").write_text("old wheel\n", encoding="utf-8")
    _patch_git_diff_ok(monkeypatch)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5")

    assert "stale or wrong-version Lab-Sidecar artifact" in "\n".join(exc_info.value.failures)


def test_release_check_rejects_right_name_with_wrong_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    dist = _write_minimal_repo(repo)
    _write_wheel(dist / "lab_sidecar-0.1.5-py3-none-any.whl", version="0.1.4")
    _write_sdist(dist / "lab_sidecar-0.1.5.tar.gz", version="0.1.4")
    _patch_git_diff_ok(monkeypatch)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5")

    message = "\n".join(exc_info.value.failures)
    assert "lab_sidecar-0.1.5-py3-none-any.whl metadata Version is '0.1.4'; expected '0.1.5'" in message
    assert "lab_sidecar-0.1.5.tar.gz metadata Version is '0.1.4'; expected '0.1.5'" in message


def test_release_check_rejects_root_lab_sidecar_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo)
    (repo / ".lab-sidecar").mkdir()
    _patch_git_diff_ok(monkeypatch)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5")

    assert "repository root contains .lab-sidecar" in "\n".join(exc_info.value.failures)


def test_release_check_rejects_mismatched_tag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo)
    _patch_git_diff_ok(monkeypatch)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5", tag="v0.1.4")

    assert "--tag must be 'v0.1.5'" in "\n".join(exc_info.value.failures)


def test_release_check_can_require_clean_git_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo)

    def fake_run(command, cwd: Path, text: bool, stdout, stderr, check: bool):
        assert text is True
        assert check is False
        if command == ["git", "diff", "--check"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "diff", "--cached", "--check"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "diff-tree", "--check", "--root", "--no-commit-id", "-r", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "status", "--porcelain", "--untracked-files=all"]:
            return subprocess.CompletedProcess(command, 0, "?? docs/v0.1.5-plan.md\n", "")
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(release_check.subprocess, "run", fake_run)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5", require_clean_git=True)

    assert "git working tree is not clean" in "\n".join(exc_info.value.failures)


def test_release_check_rejects_staged_whitespace_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo)

    def fake_run(command, cwd: Path, text: bool, stdout, stderr, check: bool):
        assert text is True
        assert check is False
        if command == ["git", "diff", "--check"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "diff", "--cached", "--check"]:
            return subprocess.CompletedProcess(command, 2, "README.md:2: trailing whitespace.\n", "")
        if command == ["git", "diff-tree", "--check", "--root", "--no-commit-id", "-r", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(release_check.subprocess, "run", fake_run)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5")

    assert "git diff --cached --check failed" in "\n".join(exc_info.value.failures)


def test_release_check_rejects_committed_whitespace_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_minimal_repo(repo)

    def fake_run(command, cwd: Path, text: bool, stdout, stderr, check: bool):
        assert text is True
        assert check is False
        if command == ["git", "diff", "--check"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "diff", "--cached", "--check"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "diff-tree", "--check", "--root", "--no-commit-id", "-r", "HEAD"]:
            return subprocess.CompletedProcess(command, 2, "README.md:1: trailing whitespace.\n", "")
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(release_check.subprocess, "run", fake_run)

    with pytest.raises(release_check.ReleaseCheckError) as exc_info:
        release_check.run_release_check(repo=repo, version="0.1.5")

    assert "git diff-tree --check HEAD failed" in "\n".join(exc_info.value.failures)


def test_release_check_script_help() -> None:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "release_check.py"), "--help"],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--version" in result.stdout
    assert "--require-clean-git" in result.stdout
    assert "never tags, uploads, publishes" in result.stdout
