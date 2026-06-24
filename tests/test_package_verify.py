from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.test_cli_smoke import copy_examples, extract_task_id, invoke


def _create_result_package(workspace: Path) -> tuple[str, Path]:
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(workspace, ["run", command]).output)
    for args in [
        ["collect", task_id],
        ["figures", task_id],
        ["report", task_id],
        ["slides", task_id],
    ]:
        result = invoke(workspace, args)
        assert result.exit_code == 0, result.output
    package_path = workspace / f"lab-sidecar-package-{task_id}"
    package_result = invoke(workspace, ["package", task_id, "--output", package_path.as_posix()])
    assert package_result.exit_code == 0, package_result.output
    return task_id, package_path


def test_package_verify_passes_for_exported_package(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)

    digest_path = package_path / "artifact-index.sha256"
    assert digest_path.is_file()
    assert "artifact-index.json" in digest_path.read_text(encoding="utf-8")
    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 0
    assert "Package verified:" in verify.output
    assert "Checked files:" in verify.output
    assert not (package_path / "stdout.log").exists()
    assert not (package_path / "stderr.log").exists()
    assert not (package_path / "raw" / "source_refs.json").exists()


def test_package_verify_detects_tampered_included_artifact(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    report_path = package_path / "reports" / "report-fragment.md"
    report_path.write_text(report_path.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "Package verification failed:" in verify.output
    assert "sha256 mismatch for reports/report-fragment.md" in verify.output


def test_package_verify_detects_tampered_artifact_index(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    index_path = package_path / "artifact-index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["package_type"] = "tampered"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "sha256 mismatch for artifact-index.json" in verify.output


def test_package_verify_detects_missing_digest(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    (package_path / "artifact-index.sha256").unlink()

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "artifact-index.sha256 is missing" in verify.output


def test_package_verify_detects_malformed_artifact_index(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    (package_path / "artifact-index.json").write_text("{not-json\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "sha256 mismatch for artifact-index.json" in verify.output
    assert "artifact-index.json could not be parsed" in verify.output


def test_package_verify_detects_malformed_package_summary(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    (package_path / "package-summary.json").write_text("{not-json\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "sha256 mismatch for package-summary.json" in verify.output
    assert "package-summary.json could not be parsed" in verify.output


def test_package_verify_detects_missing_included_file(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    (package_path / "metrics" / "normalized_metrics.csv").unlink()

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "missing package file: metrics/normalized_metrics.csv" in verify.output


def test_package_verify_detects_unregistered_extra_file(tmp_path: Path) -> None:
    _task_id, package_path = _create_result_package(tmp_path)
    (package_path / "stdout.log").write_text("full log should not be inside package\n", encoding="utf-8")

    verify = invoke(tmp_path, ["package-verify", package_path.as_posix()])

    assert verify.exit_code == 5
    assert "unexpected package file: stdout.log" in verify.output
