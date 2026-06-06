from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lab_sidecar.core.paths import task_dir, to_manifest_path
from lab_sidecar.intelligence.paths import sandbox_dir, worker_run_dir
from lab_sidecar.intelligence.sandbox import is_official_artifact_path, is_path_within
from lab_sidecar.intelligence.schemas import ProposalSkeleton, ValidatorCheck, ValidatorResult


PATH_FIELD_HINTS = ("path", "paths", "file", "files", "dir", "directory", "output", "outputs")
SOURCE_PATH_KEYS = {"source_file", "source_files", "source_metrics", "source_path", "source_paths"}
OUTPUT_PATH_KEYS = {"output", "outputs", "output_path", "output_paths", "png", "svg"}
SUPPORTED_CHART_TYPES = {"line", "bar"}


def validate_proposal(
    root: Path,
    task_id: str,
    worker_run_id: str,
    proposal: dict[str, Any] | ProposalSkeleton,
) -> ValidatorResult:
    proposal_data = proposal.model_dump(mode="json") if isinstance(proposal, ProposalSkeleton) else proposal
    parsed = ProposalSkeleton.model_validate(proposal_data)
    task_path = task_dir(root, task_id)
    sandbox_path = sandbox_dir(root, task_id, worker_run_id)
    bundle = _load_input_bundle(root, task_id, worker_run_id)

    diagnostics: list[str] = []
    checks = [
        _check_identity(task_id, worker_run_id, parsed),
        _check_source_paths(root, task_path, sandbox_path, proposal_data, bundle, diagnostics),
        _check_fields(parsed.proposal_type, proposal_data, bundle, diagnostics),
        _check_chart_types(parsed.proposal_type, proposal_data, diagnostics),
        _check_output_paths(root, task_path, sandbox_path, parsed.proposal_type, proposal_data, diagnostics),
        _check_numeric_claims(proposal_data, bundle, diagnostics),
        _check_artifact_citations(root, proposal_data, bundle, diagnostics),
        _check_sandbox_paths(root, task_path, sandbox_path, proposal_data, diagnostics),
    ]
    accepted = all(check.status in {"passed", "skipped"} for check in checks)
    result = ValidatorResult(
        accepted=accepted,
        proposal_type=parsed.proposal_type,
        checks=checks,
        diagnostics=diagnostics,
    )
    write_validator_outputs(root, task_id, worker_run_id, result)
    return result


def write_validator_outputs(root: Path, task_id: str, worker_run_id: str, result: ValidatorResult) -> None:
    run_dir = worker_run_dir(root, task_id, worker_run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "validator-result.json").write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_diagnostics(root, task_id, worker_run_id, result.diagnostics)


def write_diagnostics(root: Path, task_id: str, worker_run_id: str, diagnostics: list[str]) -> None:
    run_dir = worker_run_dir(root, task_id, worker_run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Lab-Sidecar Intelligence Diagnostics", ""]
    if diagnostics:
        lines.extend(f"- {item}" for item in diagnostics)
    else:
        lines.append("- No validator diagnostics recorded.")
    (run_dir / "diagnostics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def unavailable_worker_result(root: Path, task_id: str, worker_run_id: str) -> ValidatorResult:
    result = ValidatorResult(
        accepted=False,
        proposal_type="unknown",
        checks=[
            ValidatorCheck(
                name="worker_available",
                status="failed",
                message="No Phase 2.1 worker is configured; V1 deterministic fallback remains available.",
            )
        ],
        diagnostics=["intelligent_worker_unavailable: no non-AI or AI worker is implemented in Phase 2.1."],
    )
    write_validator_outputs(root, task_id, worker_run_id, result)
    return result


def _load_input_bundle(root: Path, task_id: str, worker_run_id: str) -> dict[str, Any]:
    path = worker_run_dir(root, task_id, worker_run_id) / "input-bundle.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _check_identity(task_id: str, worker_run_id: str, proposal: ProposalSkeleton) -> ValidatorCheck:
    problems = []
    if proposal.task_id is not None and proposal.task_id != task_id:
        problems.append(f"task_id mismatch: {proposal.task_id}")
    if proposal.worker_run_id is not None and proposal.worker_run_id != worker_run_id:
        problems.append(f"worker_run_id mismatch: {proposal.worker_run_id}")
    if problems:
        return ValidatorCheck(name="proposal_identity", status="failed", message="; ".join(problems))
    return ValidatorCheck(name="proposal_identity", status="passed")


def _check_source_paths(
    root: Path,
    task_path: Path,
    sandbox_path: Path,
    proposal: dict[str, Any],
    bundle: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    allowed = set(_bundle_paths(bundle))
    raw_paths = _source_path_values(proposal)
    if not raw_paths:
        return ValidatorCheck(name="source_paths_within_scope", status="passed", message="no source paths declared")

    failures: list[str] = []
    for raw in raw_paths:
        if raw not in allowed:
            failures.append(f"source path outside bounded input bundle: {raw}")

    if failures:
        diagnostics.extend(failures)
        return ValidatorCheck(name="source_paths_within_scope", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="source_paths_within_scope", status="passed")


def _check_fields(
    proposal_type: str,
    proposal: dict[str, Any],
    bundle: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    if proposal_type == "metrics":
        required = ["source_files", "field_mappings"]
        missing = [field for field in required if field not in proposal]
        if missing:
            diagnostics.extend(f"missing field: {field}" for field in missing)
            return ValidatorCheck(name="fields_exist", status="failed", message=f"missing field: {', '.join(missing)}")
        known_by_path = _bundle_columns_by_path(bundle)
        failures: list[str] = []
        for source in proposal.get("source_files", []):
            if not isinstance(source, dict):
                continue
            path = source.get("path")
            source_columns = set(known_by_path.get(path, [])) if isinstance(path, str) else set()
            for mapping in proposal.get("field_mappings", []):
                for field in _mapping_sources(mapping):
                    if field not in source_columns:
                        failures.append(f"missing field: {field}")
        if failures:
            diagnostics.extend(sorted(set(failures)))
            return ValidatorCheck(name="fields_exist", status="failed", message="; ".join(sorted(set(failures))))
        return ValidatorCheck(name="fields_exist", status="passed")

    if proposal_type == "figure":
        figures = proposal.get("figures")
        if not isinstance(figures, list) or not figures:
            diagnostics.append("missing field: figures")
            return ValidatorCheck(name="fields_exist", status="failed", message="missing field: figures")
        columns = set(_figure_source_columns(proposal, bundle))
        failures: list[str] = []
        required = ["figure_id", "chart_type", "title", "x", "y"]
        for figure in figures:
            if not isinstance(figure, dict):
                failures.append("missing field: figure object")
                continue
            for field in required:
                if field not in figure:
                    failures.append(f"missing field: {field}")
            for field_name in ["x", "y", "group_by"]:
                value = figure.get(field_name)
                if isinstance(value, str) and value not in columns:
                    failures.append(f"missing field: {value}")
        if failures:
            diagnostics.extend(sorted(set(failures)))
            return ValidatorCheck(name="fields_exist", status="failed", message="; ".join(sorted(set(failures))))
        return ValidatorCheck(name="fields_exist", status="passed")

    return ValidatorCheck(name="fields_exist", status="skipped", message=f"not applicable to {proposal_type}")


def _check_chart_types(proposal_type: str, proposal: dict[str, Any], diagnostics: list[str]) -> ValidatorCheck:
    if proposal_type != "figure":
        return ValidatorCheck(name="supported_chart_types", status="skipped", message="not a figure proposal")
    failures = []
    for figure in proposal.get("figures", []):
        chart_type = figure.get("chart_type") if isinstance(figure, dict) else None
        if chart_type not in SUPPORTED_CHART_TYPES:
            failures.append(f"unsupported chart type: {chart_type}")
    if failures:
        diagnostics.extend(failures)
        return ValidatorCheck(name="supported_chart_types", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="supported_chart_types", status="passed")


def _check_output_paths(
    root: Path,
    task_path: Path,
    sandbox_path: Path,
    proposal_type: str,
    proposal: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    if proposal_type != "figure":
        return ValidatorCheck(name="output_paths", status="skipped", message="not a figure proposal")
    failures: list[str] = []
    for raw in _figure_output_paths(proposal):
        path = Path(raw)
        if path.is_absolute():
            failures.append(f"output path must be relative: {raw}")
            continue
        candidate = (task_path / path).resolve()
        figures_dir = (task_path / "figures").resolve()
        if not is_path_within(candidate, figures_dir):
            failures.append(f"output path must stay in task figures directory: {raw}")
            continue
        sandbox_candidate = (sandbox_path / raw).resolve()
        if is_path_within(sandbox_candidate, sandbox_path):
            continue
        failures.append(f"path escapes sandbox: {raw}")
    if failures:
        diagnostics.extend(failures)
        return ValidatorCheck(name="output_paths", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="output_paths", status="passed")


def _check_numeric_claims(proposal: dict[str, Any], bundle: dict[str, Any], diagnostics: list[str]) -> ValidatorCheck:
    claims = proposal.get("numeric_claims")
    if claims is None:
        claims = []
        for figure in proposal.get("figures", []) if isinstance(proposal.get("figures"), list) else []:
            if isinstance(figure, dict):
                claims.extend(figure.get("numeric_claims") or [])
    if not claims:
        return ValidatorCheck(name="numeric_claims", status="passed", message="no numeric claims declared")

    stats_fields = set()
    for preview in _all_previews(bundle):
        stats = preview.get("descriptive_stats")
        if isinstance(stats, dict):
            stats_fields.update(stats.keys())
    failures = []
    for claim in claims:
        field = claim.get("field") if isinstance(claim, dict) else None
        if field not in stats_fields:
            failures.append(f"numeric claim absent from bundle stats: {field}")
    if failures:
        diagnostics.extend(failures)
        return ValidatorCheck(name="numeric_claims", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="numeric_claims", status="passed")


def _check_artifact_citations(
    root: Path,
    proposal: dict[str, Any],
    bundle: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    citations = proposal.get("artifact_citations") or []
    if not citations:
        return ValidatorCheck(name="artifact_citations", status="passed", message="no artifact citations declared")
    allowed = set(_bundle_paths(bundle))
    failures = []
    for citation in citations:
        if not isinstance(citation, str):
            failures.append(f"artifact citation must be a string: {citation}")
            continue
        if citation in allowed:
            continue
        if not (root / citation).exists():
            failures.append(f"artifact citation does not exist: {citation}")
    if failures:
        diagnostics.extend(failures)
        return ValidatorCheck(name="artifact_citations", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="artifact_citations", status="passed")


def _check_sandbox_paths(
    root: Path,
    task_path: Path,
    sandbox_path: Path,
    proposal: dict[str, Any],
    diagnostics: list[str],
) -> ValidatorCheck:
    allowed_non_sandbox = set(_source_path_values(proposal))
    for raw in _figure_output_paths(proposal):
        path = Path(raw)
        if not path.is_absolute() and is_path_within((task_path / path).resolve(), (task_path / "figures").resolve()):
            allowed_non_sandbox.add(raw)
    path_values = [
        raw
        for raw in _iter_path_values(proposal)
        if raw not in allowed_non_sandbox and _looks_like_path(raw)
    ]
    if not path_values:
        return ValidatorCheck(name="sandbox_paths_only", status="passed", message="no sandbox-only paths declared")

    failures: list[str] = []
    for raw in path_values:
        path = Path(raw)
        candidate = path if path.is_absolute() else sandbox_path / path
        resolved = candidate.resolve()
        if not is_path_within(resolved, sandbox_path):
            failures.append(f"path escapes sandbox: {raw}")
            continue
        if is_official_artifact_path(resolved, task_path):
            failures.append(f"path targets official artifact area: {to_manifest_path(resolved, root)}")

    if failures:
        diagnostics.extend(failures)
        return ValidatorCheck(name="sandbox_paths_only", status="failed", message="; ".join(failures))
    return ValidatorCheck(name="sandbox_paths_only", status="passed")


def _all_previews(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for key in ["candidate_previews", "data_previews"]:
        value = bundle.get(key)
        if isinstance(value, list):
            previews.extend(item for item in value if isinstance(item, dict))
    return previews


def _bundle_paths(bundle: dict[str, Any]) -> list[str]:
    paths = []
    for preview in _all_previews(bundle):
        path = preview.get("path")
        if isinstance(path, str):
            paths.append(path)
    for artifact in bundle.get("artifacts", []) if isinstance(bundle.get("artifacts"), list) else []:
        path = artifact.get("path") if isinstance(artifact, dict) else None
        if isinstance(path, str):
            paths.append(path)
    return paths


def _bundle_columns_by_path(bundle: dict[str, Any]) -> dict[str, list[str]]:
    columns: dict[str, list[str]] = {}
    for preview in _all_previews(bundle):
        path = preview.get("path")
        if not isinstance(path, str):
            continue
        value = preview.get("columns") or preview.get("keys") or []
        columns[path] = [item for item in value if isinstance(item, str)]
    return columns


def _figure_source_columns(proposal: dict[str, Any], bundle: dict[str, Any]) -> list[str]:
    source_metrics = proposal.get("source_metrics")
    if isinstance(source_metrics, str):
        return _bundle_columns_by_path(bundle).get(source_metrics, [])
    columns = proposal.get("source_metrics_fields")
    if isinstance(columns, list):
        return [item for item in columns if isinstance(item, str)]
    return []


def _mapping_sources(mapping: Any) -> list[str]:
    if not isinstance(mapping, dict):
        return []
    sources = mapping.get("sources", mapping.get("source", mapping.get("field")))
    if isinstance(sources, str):
        return [sources]
    if isinstance(sources, list):
        return [source for source in sources if isinstance(source, str)]
    return []


def _figure_output_paths(proposal: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for figure in proposal.get("figures", []):
        if not isinstance(figure, dict):
            continue
        output = figure.get("output")
        if isinstance(output, dict):
            paths.extend(item for item in [output.get("png"), output.get("svg")] if isinstance(item, str))
        elif isinstance(output, list):
            paths.extend(item for item in output if isinstance(item, str))
        output_path = figure.get("output_path")
        if isinstance(output_path, str):
            paths.append(output_path)
    return paths


def _source_path_values(proposal: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    source_metrics = proposal.get("source_metrics")
    if isinstance(source_metrics, str):
        paths.append(source_metrics)
    for key in ["source_file", "source_path"]:
        value = proposal.get(key)
        if isinstance(value, str):
            paths.append(value)
    for key in ["source_files", "source_paths"]:
        value = proposal.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    paths.append(item)
                elif isinstance(item, dict) and isinstance(item.get("path"), str):
                    paths.append(item["path"])
    for figure in proposal.get("figures", []) if isinstance(proposal.get("figures"), list) else []:
        if isinstance(figure, dict) and isinstance(figure.get("source_metrics"), str):
            paths.append(figure["source_metrics"])
    return paths


def _iter_keyed_path_values(value: Any, matching_keys: set[str], key_hint: str | None = None) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            child_hint = lowered if lowered in matching_keys else key_hint
            values.extend(_iter_keyed_path_values(child, matching_keys, child_hint))
    elif isinstance(value, list):
        for child in value:
            values.extend(_iter_keyed_path_values(child, matching_keys, key_hint))
    elif isinstance(value, str) and key_hint:
        values.append(value)
    return values


def _iter_path_values(value: Any, key_hint: str | None = None) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            child_hint = lowered if any(hint in lowered for hint in PATH_FIELD_HINTS) else key_hint
            values.extend(_iter_path_values(child, child_hint))
    elif isinstance(value, list):
        for child in value:
            values.extend(_iter_path_values(child, key_hint))
    elif isinstance(value, str) and key_hint:
        values.append(value)
    return values


def _looks_like_path(value: str) -> bool:
    path = Path(value)
    return (
        path.is_absolute()
        or "/" in value
        or "\\" in value
        or value.startswith(".")
        or bool(path.suffix)
    )
