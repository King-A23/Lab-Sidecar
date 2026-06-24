from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "artifact_contract" / "v1"
EXPECTED_FIXTURES = {
    "manifest.json",
    "metrics/collection-summary.json",
    "provenance/traceability.json",
    "package-summary.json",
    "artifact-index.json",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
PRIVATE_PATH_PATTERNS = (
    "/Users/",
    "/home/",
    "C:\\",
    "\\Users\\",
    "/private/tmp/",
)
FORBIDDEN_BODY_FRAGMENTS = (
    "Starting synthetic training run",
    "Best val_accuracy",
    "epoch,train_loss,val_accuracy",
    "raw source body",
    "stdout body",
    "stderr body",
    "worker prompt body",
    "worker response body",
    "ppt/presentation.xml",
    "<p:sld",
)


def _read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"))


def _walk_values(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_values(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
        return
    yield value


def _assert_sha256(value: str) -> None:
    assert SHA256_RE.fullmatch(value), value


def test_artifact_contract_golden_fixture_set_is_small_and_explicit() -> None:
    fixture_paths = {
        path.relative_to(FIXTURE_ROOT).as_posix()
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file()
    }

    assert fixture_paths == EXPECTED_FIXTURES
    for path in fixture_paths:
        assert (FIXTURE_ROOT / path).stat().st_size < 12_000


def test_artifact_contract_golden_fixtures_are_sanitized_reference_json() -> None:
    combined = "\n".join((FIXTURE_ROOT / path).read_text(encoding="utf-8") for path in sorted(EXPECTED_FIXTURES))

    for pattern in PRIVATE_PATH_PATTERNS:
        assert pattern not in combined
    for fragment in FORBIDDEN_BODY_FRAGMENTS:
        assert fragment not in combined

    for path in EXPECTED_FIXTURES:
        payload = _read_json(path)
        for value in _walk_values(payload):
            if not isinstance(value, str):
                continue
            assert "\n" not in value
            assert not value.startswith("/")
            assert not re.match(r"^[A-Za-z]:\\", value)


def test_artifact_contract_golden_fixtures_pin_schema_versions_and_run_mode() -> None:
    manifest = _read_json("manifest.json")
    collection = _read_json("metrics/collection-summary.json")
    traceability = _read_json("provenance/traceability.json")
    package_summary = _read_json("package-summary.json")
    artifact_index = _read_json("artifact-index.json")

    for payload in [manifest, collection, traceability, package_summary, artifact_index]:
        assert payload["schema_version"] == "1"
        if "task_id" in payload:
            assert payload["task_id"] == "task_fixture_20260625_000000"

    assert manifest["run_mode"] == "argv"
    assert manifest["argv"] == [
        "python",
        "examples/simple-success/train.py",
        "--output",
        "metrics.csv",
    ]
    assert traceability["task"]["run_mode"] == "argv"
    assert traceability["task"]["argv"] == manifest["argv"]
    assert package_summary["task"]["run_mode"] == "argv"
    assert package_summary["task"]["argv_count"] == len(manifest["argv"])
    assert package_summary["task"]["run_spec_path"] == "reproduce/run.json"
    assert "argv" not in package_summary["task"]
    assert artifact_index["task_id"] == manifest["task_id"]


def test_artifact_contract_golden_fixtures_pin_hash_size_and_omission_contracts() -> None:
    manifest = _read_json("manifest.json")
    collection = _read_json("metrics/collection-summary.json")
    traceability = _read_json("provenance/traceability.json")
    package_summary = _read_json("package-summary.json")
    artifact_index = _read_json("artifact-index.json")

    for artifact in manifest["artifacts"]:
        assert isinstance(artifact["size_bytes"], int) or artifact["size_bytes"] is None
        if artifact["sha256"] is not None:
            _assert_sha256(artifact["sha256"])

    for candidate in collection["candidates"]:
        provenance = candidate["source_provenance"]
        assert isinstance(provenance["size_bytes"], int)
        _assert_sha256(provenance["sha256"])
    for processed in collection["processed_files"]:
        provenance = processed["source_provenance"]
        assert isinstance(provenance["size_bytes"], int)
        _assert_sha256(provenance["sha256"])
    assert collection["bounded_analysis"]["best_rows"][0]["evidence"]["body"] == "omitted"

    for source in traceability["sources"]:
        assert isinstance(source["size_bytes"], int)
        _assert_sha256(source["sha256"])
    for artifact in traceability["artifacts"]:
        assert isinstance(artifact["size_bytes"], int) or artifact["size_bytes"] is None
        if artifact["sha256"] is not None:
            _assert_sha256(artifact["sha256"])
        if artifact["type"] == "log":
            assert artifact["digest_omitted_reason"]

    included_paths = {item["path"] for item in package_summary["included_artifacts"]}
    assert {
        "manifest.json",
        "metrics/collection-summary.json",
        "reproduce/run.json",
        "provenance/traceability.json",
    } <= included_paths
    assert "full logs, raw source files, local indexes, worker transcripts" in package_summary["omission_policy"]

    for item in artifact_index["included"]:
        assert isinstance(item["size_bytes"], int)
        _assert_sha256(item["sha256"])
    metadata_by_path = {item["package_path"]: item for item in artifact_index["package_metadata"]}
    for path, item in metadata_by_path.items():
        if path == "artifact-index.json":
            assert item["size_bytes"] is None
            assert item["sha256"] is None
            assert item["digest_omitted_reason"].startswith("artifact-index.json is self-referential")
            continue
        assert isinstance(item["size_bytes"], int)
        _assert_sha256(item["sha256"])

    omitted_paths = {item["path"] for item in artifact_index["omitted"]}
    traceability_omitted_paths = {item["path"] for item in traceability["omitted"]}
    for required_path in [
        "stdout.log",
        "stderr.log",
        ".lab-sidecar/index.sqlite",
    ]:
        assert required_path in omitted_paths
        assert required_path in traceability_omitted_paths
    assert "raw/source_refs.json" in omitted_paths
    assert "intelligence" in traceability_omitted_paths
