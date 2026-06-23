from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from tests.test_cli_smoke import assert_traceability_is_bounded, copy_examples, extract_task_id, invoke


REQUIRED_SUMMARY_KEYS = {
    "schema_version",
    "created_at",
    "package_type",
    "package_name",
    "task",
    "counts",
    "included_artifacts",
    "omission_policy",
}
REQUIRED_SUMMARY_TASK_KEYS = {
    "task_id",
    "name",
    "mode",
    "status",
    "exit_code",
    "created_at",
    "started_at",
    "finished_at",
    "command_preview",
    "source_path",
    "failure_summary",
}
REQUIRED_SUMMARY_COUNT_KEYS = {"included", "omitted", "unavailable"}
REQUIRED_SUMMARY_INCLUDED_KEYS = {"path", "category", "description"}

REQUIRED_INDEX_KEYS = {
    "schema_version",
    "created_at",
    "task_id",
    "package_type",
    "included",
    "omitted",
    "unavailable",
    "package_metadata",
}
REQUIRED_INCLUDED_KEYS = {
    "path",
    "package_path",
    "source_path",
    "category",
    "description",
    "size_bytes",
    "sha256",
}
REQUIRED_REASON_ENTRY_KEYS = {"path", "category", "reason"}
REQUIRED_PACKAGE_METADATA_KEYS = {
    "path",
    "package_path",
    "category",
    "description",
    "size_bytes",
    "sha256",
}
OPTIONAL_PACKAGE_METADATA_KEYS = {"digest_omitted_reason"}

OMISSION_POLICY = (
    "allowlist package; full logs, raw source files, local indexes, worker transcripts, "
    "sandbox files, and unrelated workspace files are omitted by default"
)
UNAVAILABLE_REASON = "not generated or not available for this task"
SELF_REFERENTIAL_DIGEST_REASON = (
    "artifact-index.json is self-referential; hash the file after package creation if an external digest is required"
)
EXPECTED_PACKAGE_METADATA_DESCRIPTIONS = {
    "README.md": "Package README.",
    "package-summary.json": "Package summary metadata.",
    "redaction-notes.md": "Package redaction and omission notes.",
    "artifact-index.json": "Package artifact index.",
}
COMMON_FORBIDDEN_FRAGMENTS = (
    "ppt/presentation.xml",
    "<p:sld",
    "SQLite format 3",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_path(workspace: Path, task_id: str) -> Path:
    return workspace / ".lab-sidecar" / "tasks" / task_id


def _assert_sha256(value: str) -> None:
    assert re.fullmatch(r"[0-9a-f]{64}", value), value


def _assert_summary_contract(
    summary: dict[str, Any],
    index: dict[str, Any],
    *,
    expected_task_id: str,
    expected_package_name: str,
    expected_package_type: str,
    expected_task_name: str,
    expected_mode: str,
    expected_status: str,
    expected_exit_code: int,
    expected_command_preview: str,
    expected_source_path: str | None,
    expect_failure_summary: bool,
) -> None:
    assert set(summary) == REQUIRED_SUMMARY_KEYS
    assert summary["schema_version"] == "1"
    assert summary["created_at"] == index["created_at"]
    assert summary["package_type"] == expected_package_type
    assert summary["package_name"] == expected_package_name

    task = summary["task"]
    assert set(task) == REQUIRED_SUMMARY_TASK_KEYS
    assert task["task_id"] == expected_task_id
    assert task["name"] == expected_task_name
    assert task["mode"] == expected_mode
    assert task["status"] == expected_status
    assert task["exit_code"] == expected_exit_code
    assert isinstance(task["created_at"], str) and task["created_at"]
    assert isinstance(task["started_at"], str) and task["started_at"]
    assert isinstance(task["finished_at"], str) and task["finished_at"]
    assert task["command_preview"] == expected_command_preview
    assert len(task["command_preview"]) <= 160
    assert task["source_path"] == expected_source_path
    if expect_failure_summary:
        assert isinstance(task["failure_summary"], str) and task["failure_summary"]
        assert len(task["failure_summary"]) <= 1200
    else:
        assert task["failure_summary"] is None

    counts = summary["counts"]
    assert set(counts) == REQUIRED_SUMMARY_COUNT_KEYS
    assert counts["included"] == len(index["included"])
    assert counts["omitted"] == len(index["omitted"])
    assert counts["unavailable"] == len(index["unavailable"])

    assert isinstance(summary["included_artifacts"], list)
    assert len(summary["included_artifacts"]) == counts["included"]
    for item in summary["included_artifacts"]:
        assert set(item) == REQUIRED_SUMMARY_INCLUDED_KEYS
        assert isinstance(item["path"], str) and item["path"]
        assert isinstance(item["category"], str) and item["category"]
        assert isinstance(item["description"], str) and item["description"]

    assert summary["included_artifacts"] == [
        {
            "path": item["package_path"],
            "category": item["category"],
            "description": item["description"],
        }
        for item in index["included"]
    ]
    assert summary["omission_policy"] == OMISSION_POLICY

    serialized = json.dumps(summary, ensure_ascii=False)
    assert '"sha256"' not in serialized
    assert '"size_bytes"' not in serialized


def _assert_index_contract(
    index: dict[str, Any],
    *,
    package_path: Path,
    task_path: Path,
    expected_task_id: str,
    expected_package_type: str,
) -> None:
    assert set(index) == REQUIRED_INDEX_KEYS
    assert index["schema_version"] == "1"
    assert isinstance(index["created_at"], str) and index["created_at"]
    assert index["task_id"] == expected_task_id
    assert index["package_type"] == expected_package_type

    included_package_paths: set[str] = set()
    for item in index["included"]:
        assert set(item) == REQUIRED_INCLUDED_KEYS
        assert item["path"] == item["package_path"] == item["source_path"]
        assert item["package_path"] not in included_package_paths
        included_package_paths.add(item["package_path"])
        assert isinstance(item["category"], str) and item["category"]
        assert isinstance(item["description"], str) and item["description"]

        packaged_file = package_path / item["package_path"]
        source_file = task_path / item["source_path"]
        assert packaged_file.is_file(), item["package_path"]
        assert source_file.is_file(), item["source_path"]
        assert isinstance(item["size_bytes"], int) and item["size_bytes"] > 0
        assert item["size_bytes"] == packaged_file.stat().st_size
        _assert_sha256(item["sha256"])

    package_metadata = index["package_metadata"]
    assert isinstance(package_metadata, list)
    assert len(package_metadata) == 4
    metadata_by_path = {item["package_path"]: item for item in package_metadata}
    assert set(metadata_by_path) == set(EXPECTED_PACKAGE_METADATA_DESCRIPTIONS)

    for package_relative_path, description in EXPECTED_PACKAGE_METADATA_DESCRIPTIONS.items():
        item = metadata_by_path[package_relative_path]
        assert REQUIRED_PACKAGE_METADATA_KEYS <= set(item)
        assert set(item) <= REQUIRED_PACKAGE_METADATA_KEYS | OPTIONAL_PACKAGE_METADATA_KEYS
        assert item["path"] == package_relative_path
        assert item["package_path"] == package_relative_path
        assert item["category"] == "package_metadata"
        assert item["description"] == description

        packaged_file = package_path / package_relative_path
        assert packaged_file.is_file(), package_relative_path
        if package_relative_path == "artifact-index.json":
            assert item["size_bytes"] is None
            assert item["sha256"] is None
            assert item["digest_omitted_reason"] == SELF_REFERENTIAL_DIGEST_REASON
        else:
            assert "digest_omitted_reason" not in item
            assert isinstance(item["size_bytes"], int) and item["size_bytes"] > 0
            assert item["size_bytes"] == packaged_file.stat().st_size
            _assert_sha256(item["sha256"])


def _assert_reason_entries(
    entries: list[dict[str, Any]],
    *,
    expected_by_path: dict[str, tuple[str, str]],
) -> None:
    seen: set[str] = set()
    for item in entries:
        assert set(item) == REQUIRED_REASON_ENTRY_KEYS
        assert item["path"] in expected_by_path
        assert item["path"] not in seen
        seen.add(item["path"])
        expected_category, expected_reason = expected_by_path[item["path"]]
        assert item["category"] == expected_category
        assert item["reason"] == expected_reason
    assert seen == set(expected_by_path)


def _assert_reference_only_json(
    summary: dict[str, Any],
    index: dict[str, Any],
    *,
    forbidden_fragments: tuple[str, ...],
) -> None:
    serialized = json.dumps({"summary": summary, "index": index}, ensure_ascii=False)
    for fragment in [*COMMON_FORBIDDEN_FRAGMENTS, *forbidden_fragments]:
        assert fragment not in serialized


def test_result_package_summary_and_index_match_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "package-contract-result"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(workspace, ["run", command, "--name", "package-contract-result"]).output)
    assert invoke(workspace, ["collect", task_id]).exit_code == 0
    assert invoke(workspace, ["figures", task_id]).exit_code == 0
    assert invoke(workspace, ["report", task_id]).exit_code == 0
    assert invoke(workspace, ["slides", task_id]).exit_code == 0

    task_path = _task_path(workspace, task_id)
    worker_secret = "PACKAGE_CONTRACT_FORBIDDEN_WORKER_LOG_BODY"
    prompt_secret = "PACKAGE_CONTRACT_FORBIDDEN_PROMPT_BODY"
    response_secret = "PACKAGE_CONTRACT_FORBIDDEN_RESPONSE_BODY"
    sandbox_secret = "PACKAGE_CONTRACT_FORBIDDEN_SANDBOX_BODY"
    (task_path / "worker.log").write_text(worker_secret + "\n", encoding="utf-8")
    worker_run_dir = task_path / "intelligence" / "worker_run_contract"
    (worker_run_dir / "sandbox").mkdir(parents=True)
    (worker_run_dir / "sandbox" / "scratch.txt").write_text(sandbox_secret + "\n", encoding="utf-8")
    (worker_run_dir / "ai-provider-prompt.json").write_text(
        json.dumps({"prompt": prompt_secret}) + "\n",
        encoding="utf-8",
    )
    (worker_run_dir / "ai-provider-response.json").write_text(
        json.dumps({"response": response_secret}) + "\n",
        encoding="utf-8",
    )

    package_path = workspace / f"lab-sidecar-package-{task_id}"
    result = invoke(workspace, ["package", task_id, "--output", package_path.as_posix()])
    assert result.exit_code == 0

    summary = _read_json(package_path / "package-summary.json")
    index = _read_json(package_path / "artifact-index.json")
    _assert_summary_contract(
        summary,
        index,
        expected_task_id=task_id,
        expected_package_name=package_path.name,
        expected_package_type="result",
        expected_task_name="package-contract-result",
        expected_mode="run",
        expected_status="completed",
        expected_exit_code=0,
        expected_command_preview=command,
        expected_source_path=None,
        expect_failure_summary=False,
    )
    _assert_index_contract(
        index,
        package_path=package_path,
        task_path=task_path,
        expected_task_id=task_id,
        expected_package_type="result",
    )
    assert summary["counts"] == {"included": 20, "omitted": 9, "unavailable": 0}
    _assert_reason_entries(
        index["omitted"],
        expected_by_path={
            "stdout.log": ("log", "full stdout logs are omitted by default"),
            "stderr.log": ("log", "full stderr logs are omitted by default"),
            "worker.log": ("worker", "worker transcripts and worker logs are omitted by default"),
            "intelligence": ("worker", "worker audit files are omitted by default"),
            "intelligence/worker_run_contract/ai-provider-prompt.json": (
                "worker",
                "worker prompt and response bodies are omitted by default",
            ),
            "intelligence/worker_run_contract/ai-provider-response.json": (
                "worker",
                "worker prompt and response bodies are omitted by default",
            ),
            "intelligence/worker_run_contract/sandbox": ("sandbox", "temporary sandbox files are omitted by default"),
            ".lab-sidecar/index.sqlite": ("index", "local SQLite indexes are omitted by default"),
            "workspace/*": ("workspace", "unrelated workspace files are not copied by default"),
        },
    )
    assert index["unavailable"] == []

    included_paths = {item["package_path"] for item in index["included"]}
    assert {
        "manifest.json",
        "metrics/normalized_metrics.csv",
        "metrics/collection-summary.json",
        "metrics/scenario-summary.json",
        "figures/figure-summary.json",
        "reports/report-summary.json",
        "slides/presentation-draft.pptx",
        "provenance/traceability.json",
    } <= included_paths
    assert {
        "figures/line_train_loss_over_epoch.png",
        "figures/line_train_loss_over_epoch.svg",
        "figures/line_val_accuracy_over_epoch.png",
        "figures/line_val_accuracy_over_epoch.svg",
    } <= included_paths

    package_traceability = _read_json(package_path / "provenance" / "traceability.json")
    assert package_traceability["task_id"] == task_id
    assert package_traceability["task"]["status"] == "completed"
    assert_traceability_is_bounded(package_traceability)

    assert not (package_path / "stdout.log").exists()
    assert not (package_path / "stderr.log").exists()
    assert not (package_path / "worker.log").exists()
    assert not (package_path / "intelligence").exists()
    assert not (package_path / ".lab-sidecar" / "index.sqlite").exists()

    _assert_reference_only_json(
        summary,
        index,
        forbidden_fragments=(
            "Starting synthetic training run",
            worker_secret,
            prompt_secret,
            response_secret,
            sandbox_secret,
        ),
    )


def test_failed_diagnostic_package_summary_and_index_match_public_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "package-contract-failed"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-failure/fail.py'
    task_id = extract_task_id(invoke(workspace, ["run", command, "--name", "package-contract-failed"]).output)

    package_path = workspace / f"lab-sidecar-package-{task_id}"
    result = invoke(workspace, ["package", task_id, "--output", package_path.as_posix()])
    assert result.exit_code == 0

    task_path = _task_path(workspace, task_id)
    summary = _read_json(package_path / "package-summary.json")
    index = _read_json(package_path / "artifact-index.json")
    _assert_summary_contract(
        summary,
        index,
        expected_task_id=task_id,
        expected_package_name=package_path.name,
        expected_package_type="diagnostic",
        expected_task_name="package-contract-failed",
        expected_mode="run",
        expected_status="failed",
        expected_exit_code=1,
        expected_command_preview=command,
        expected_source_path=None,
        expect_failure_summary=True,
    )
    _assert_index_contract(
        index,
        package_path=package_path,
        task_path=task_path,
        expected_task_id=task_id,
        expected_package_type="diagnostic",
    )
    assert summary["counts"] == {"included": 6, "omitted": 4, "unavailable": 10}
    assert "FileNotFoundError" in summary["task"]["failure_summary"]
    assert "Starting failing task" not in summary["task"]["failure_summary"]
    _assert_reason_entries(
        index["omitted"],
        expected_by_path={
            "stdout.log": ("log", "full stdout logs are omitted by default"),
            "stderr.log": ("log", "full stderr logs are omitted by default"),
            ".lab-sidecar/index.sqlite": ("index", "local SQLite indexes are omitted by default"),
            "workspace/*": ("workspace", "unrelated workspace files are not copied by default"),
        },
    )
    _assert_reason_entries(
        index["unavailable"],
        expected_by_path={
            "metrics/normalized_metrics.csv": ("metrics", UNAVAILABLE_REASON),
            "metrics/normalized_metrics.json": ("metrics", UNAVAILABLE_REASON),
            "metrics/collection-summary.json": ("metrics", UNAVAILABLE_REASON),
            "metrics/scenario-summary.json": ("metrics", UNAVAILABLE_REASON),
            "figures/figure-spec.yaml": ("figures", UNAVAILABLE_REASON),
            "figures/figure-summary.json": ("figures", UNAVAILABLE_REASON),
            "reports/report-fragment.md": ("reports", UNAVAILABLE_REASON),
            "reports/report-summary.json": ("reports", UNAVAILABLE_REASON),
            "slides/presentation-draft.pptx": ("slides", UNAVAILABLE_REASON),
            "slides/slides-summary.json": ("slides", UNAVAILABLE_REASON),
        },
    )

    included_paths = {item["package_path"] for item in index["included"]}
    assert included_paths == {
        "manifest.json",
        "reproduce/command.txt",
        "reproduce/env.json",
        "reproduce/git.json",
        "reproduce/dependencies.json",
        "provenance/traceability.json",
    }
    package_traceability = _read_json(package_path / "provenance" / "traceability.json")
    assert package_traceability["task_id"] == task_id
    assert package_traceability["task"]["status"] == "failed"
    assert_traceability_is_bounded(package_traceability)

    assert not (package_path / "stdout.log").exists()
    assert not (package_path / "stderr.log").exists()

    _assert_reference_only_json(
        summary,
        index,
        forbidden_fragments=(
            "Starting failing task",
            "Loading configuration",
            "Opening input file: data/missing.csv",
        ),
    )


def test_ingest_package_summary_and_index_omit_raw_source_refs_and_source_bodies(tmp_path: Path) -> None:
    workspace = tmp_path / "package-contract-ingest"
    workspace.mkdir()
    copy_examples(workspace)
    assert invoke(workspace, ["init"]).exit_code == 0

    task_id = extract_task_id(
        invoke(workspace, ["ingest", "examples/csv-comparison", "--name", "package-contract-ingest"]).output
    )
    assert invoke(workspace, ["collect", task_id]).exit_code == 0

    package_path = workspace / f"lab-sidecar-package-{task_id}"
    result = invoke(workspace, ["package", task_id, "--output", package_path.as_posix()])
    assert result.exit_code == 0

    task_path = _task_path(workspace, task_id)
    summary = _read_json(package_path / "package-summary.json")
    index = _read_json(package_path / "artifact-index.json")
    _assert_summary_contract(
        summary,
        index,
        expected_task_id=task_id,
        expected_package_name=package_path.name,
        expected_package_type="result",
        expected_task_name="package-contract-ingest",
        expected_mode="ingest",
        expected_status="completed",
        expected_exit_code=0,
        expected_command_preview="(none)",
        expected_source_path="examples/csv-comparison",
        expect_failure_summary=False,
    )
    _assert_index_contract(
        index,
        package_path=package_path,
        task_path=task_path,
        expected_task_id=task_id,
        expected_package_type="result",
    )
    assert summary["counts"] == {"included": 6, "omitted": 6, "unavailable": 10}
    _assert_reason_entries(
        index["omitted"],
        expected_by_path={
            "stdout.log": ("log", "full stdout logs are omitted by default"),
            "stderr.log": ("log", "full stderr logs are omitted by default"),
            "raw/source_refs.json": ("raw", "raw source references are omitted by default"),
            ".lab-sidecar/index.sqlite": ("index", "local SQLite indexes are omitted by default"),
            "examples/csv-comparison": (
                "raw_source",
                "raw ingested source files are referenced but not copied by default",
            ),
            "workspace/*": ("workspace", "unrelated workspace files are not copied by default"),
        },
    )
    _assert_reason_entries(
        index["unavailable"],
        expected_by_path={
            "reproduce/command.txt": ("reproduce", UNAVAILABLE_REASON),
            "reproduce/env.json": ("reproduce", UNAVAILABLE_REASON),
            "reproduce/git.json": ("reproduce", UNAVAILABLE_REASON),
            "reproduce/dependencies.json": ("reproduce", UNAVAILABLE_REASON),
            "figures/figure-spec.yaml": ("figures", UNAVAILABLE_REASON),
            "figures/figure-summary.json": ("figures", UNAVAILABLE_REASON),
            "reports/report-fragment.md": ("reports", UNAVAILABLE_REASON),
            "reports/report-summary.json": ("reports", UNAVAILABLE_REASON),
            "slides/presentation-draft.pptx": ("slides", UNAVAILABLE_REASON),
            "slides/slides-summary.json": ("slides", UNAVAILABLE_REASON),
        },
    )

    included_paths = {item["package_path"] for item in index["included"]}
    assert included_paths == {
        "manifest.json",
        "metrics/normalized_metrics.csv",
        "metrics/normalized_metrics.json",
        "metrics/collection-summary.json",
        "metrics/scenario-summary.json",
        "provenance/traceability.json",
    }
    assert not (package_path / "raw" / "source_refs.json").exists()
    assert not (package_path / "examples").exists()

    package_traceability = _read_json(package_path / "provenance" / "traceability.json")
    assert package_traceability["task_id"] == task_id
    assert package_traceability["task"]["status"] == "completed"
    assert_traceability_is_bounded(package_traceability)

    _assert_reference_only_json(
        summary,
        index,
        forbidden_fragments=(
            "epoch,model,seed,val_accuracy,val_loss",
            "1,baseline,42,0.58,1.12",
        ),
    )
