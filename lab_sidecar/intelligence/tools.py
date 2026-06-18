from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lab_sidecar.collectors.service import MetricsCollectionService, NoMetricsFoundError
from lab_sidecar.core.manifest import load_task
from lab_sidecar.core.models import TaskRecord, TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path, to_manifest_path
from lab_sidecar.figures.service import FigureGenerationService, MetricsNotReadyError, NoFiguresGeneratedError
from lab_sidecar.intelligence.adoption import adopt_proposal
from lab_sidecar.intelligence.ai_policy import AIProviderPolicy, load_ai_provider_policy, provider_availability
from lab_sidecar.intelligence.ai_provider import AIProvider, ProviderBackedWorker
from lab_sidecar.intelligence.bundle import build_input_bundle, omitted_contract
from lab_sidecar.intelligence.heuristic_worker import HeuristicWorker
from lab_sidecar.intelligence.paths import create_worker_run_dirs, generate_worker_run_id, sandbox_dir, worker_run_dir
from lab_sidecar.intelligence.preview import ArtifactPreviewError, preview_artifact
from lab_sidecar.intelligence.validator import unavailable_worker_result, validate_proposal
from lab_sidecar.intelligence.worker_invocation import (
    SidecarWorker,
    WorkerInvocation,
    WorkerRequest,
    WorkerResult,
    write_worker_result,
)
from lab_sidecar.mcp.responses import artifact_list, compact_task_outputs, task_summary
from lab_sidecar.reports.service import ReportGenerationService, ReportMetricsRequiredError
from lab_sidecar.runner.service import RunnerService
from lab_sidecar.slides.service import SlidesGenerationService


SUPPORTED_OUTPUTS = {"metrics", "figures", "report", "slides"}


def delegate_experiment_artifacts(
    workspace_path: str | Path,
    user_goal: str,
    command: str | None = None,
    result_path: str | Path | None = None,
    desired_outputs: list[str] | None = None,
    intelligent_mode: str = "auto",
    context_budget: dict[str, Any] | None = None,
    ai_provider: AIProvider | None = None,
    ai_policy: AIProviderPolicy | None = None,
) -> dict[str, Any]:
    root = Path(workspace_path).resolve()
    desired = _normalize_desired_outputs(desired_outputs)
    if not command and not result_path:
        raise ValueError("command or result_path is required")
    if intelligent_mode not in {"auto", "off"}:
        raise ValueError("intelligent_mode must be 'auto' or 'off'")

    record, warnings = _run_v1_fallback(root, command, result_path, desired)
    risk_flags: list[str] = []
    worker_run_id = None

    if intelligent_mode == "auto":
        (
            worker_run_id,
            heuristic_status,
            heuristic_warnings,
            heuristic_risk_flags,
            worker_type,
            worker_status,
        ) = _run_worker_invocation(
            root=root,
            record=record,
            user_goal=user_goal,
            desired_outputs=desired,
            context_budget=context_budget,
            ai_provider=ai_provider,
            ai_policy=ai_policy,
        )
        warnings.extend(heuristic_warnings)
        risk_flags.extend(heuristic_risk_flags)
        if heuristic_status == "accepted":
            record = load_task(root, record.task_id)
    else:
        heuristic_status = None
        worker_type = None
        worker_status = None
        risk_flags.append("intelligent_mode_off")

    return _tool_response(
        root=root,
        record=load_task(root, record.task_id),
        status="completed" if record.status == TaskStatus.COMPLETED else record.status.value,
        summary_headline=_summary_headline(intelligent_mode, desired, heuristic_status),
        warnings=warnings,
        risk_flags=risk_flags,
        worker_run_id=worker_run_id,
        intelligence_status=heuristic_status,
        worker_type=worker_type,
        worker_status=worker_status,
        next_actions=_next_actions(record.task_id, desired, risk_flags),
    )


def inspect_sidecar_task(
    workspace_path: str | Path,
    task_id: str,
) -> dict[str, Any]:
    root = Path(workspace_path).resolve()
    record = RunnerService(root).refresh(task_id)
    return _tool_response(
        root=root,
        record=record,
        status=record.status.value,
        summary_headline=f"Task {task_id} is {record.status.value}.",
        warnings=[],
        risk_flags=[],
        worker_run_id=None,
        intelligence_status=None,
        worker_type=None,
        worker_status=None,
        next_actions=_next_actions(task_id, [], []),
    )


def cancel_sidecar_task(
    workspace_path: str | Path,
    task_id: str,
) -> dict[str, Any]:
    root = Path(workspace_path).resolve()
    try:
        record = RunnerService(root).cancel(task_id)
    except FileNotFoundError as exc:
        return _cancel_not_applicable_response(
            task_id=task_id,
            headline=f"Task {task_id} could not be cancelled because it was not found.",
            warning=str(exc),
            current_status=None,
            risk_flag="cancel_sidecar_task_missing",
        )
    except RuntimeError as exc:
        current_status = str(exc)
        return _cancel_not_applicable_response(
            task_id=task_id,
            headline=f"Task {task_id} is not running; cancellation is not applicable.",
            warning=f"Current status: {current_status}",
            current_status=current_status,
            risk_flag="cancel_sidecar_task_not_applicable",
        )
    return _tool_response(
        root=root,
        record=record,
        status=record.status.value,
        summary_headline=f"Task {task_id} cancellation requested.",
        warnings=[],
        risk_flags=[],
        worker_run_id=None,
        intelligence_status=None,
        worker_type=None,
        worker_status=None,
        next_actions=[f"inspect_sidecar_task {task_id}"],
    )


def preview_sidecar_artifact(
    workspace_path: str | Path,
    task_id: str,
    artifact_path: str,
    max_rows: int = 20,
    max_lines: int = 40,
) -> dict[str, Any]:
    root = Path(workspace_path).resolve()
    try:
        return preview_artifact(
            root=root,
            task_id=task_id,
            artifact_path=artifact_path,
            max_rows=max_rows,
            max_lines=max_lines,
        )
    except ArtifactPreviewError as exc:
        return {
            "schema_version": "2.1",
            "task_id": task_id,
            "status": "rejected",
            "summary": {"headline": str(exc)},
            "artifacts": [],
            "warnings": [str(exc)],
            "next_actions": ["Choose a registered task artifact and request a bounded preview."],
            "risk_flags": ["artifact_preview_rejected"],
            "omitted": {
                **omitted_contract(),
                "complete_artifact": "omitted_by_default",
                "unbounded_preview": "omitted_by_default",
            },
        }


def _run_v1_fallback(
    root: Path,
    command: str | None,
    result_path: str | Path | None,
    desired_outputs: list[str],
) -> tuple[TaskRecord, list[str]]:
    runner = RunnerService(root)
    if command:
        record = runner.run(command, background=False)
    else:
        record = runner.ingest_source(resolve_workspace_path(str(result_path), root))

    warnings: list[str] = []
    if record.status == TaskStatus.COMPLETED:
        record, output_warnings = _generate_requested_outputs(root, record.task_id, desired_outputs)
        warnings.extend(output_warnings)
    return record, warnings


def _generate_requested_outputs(root: Path, task_id: str, desired_outputs: list[str]) -> tuple[TaskRecord, list[str]]:
    warnings: list[str] = []
    if "metrics" in desired_outputs or any(output in desired_outputs for output in ["figures", "report", "slides"]):
        try:
            MetricsCollectionService(root).collect(task_id)
        except NoMetricsFoundError as exc:
            warnings.append(str(exc))

    if "figures" in desired_outputs or "slides" in desired_outputs:
        try:
            FigureGenerationService(root).generate(task_id)
        except (MetricsNotReadyError, NoFiguresGeneratedError) as exc:
            warnings.append(str(exc))

    if "report" in desired_outputs or "slides" in desired_outputs:
        try:
            ReportGenerationService(root).generate(task_id)
        except ReportMetricsRequiredError as exc:
            warnings.append(str(exc))

    if "slides" in desired_outputs:
        try:
            SlidesGenerationService(root).generate(task_id)
        except Exception as exc:
            warnings.append(f"slides generation skipped: {exc}")

    return load_task(root, task_id), warnings


def _run_worker_invocation(
    root: Path,
    record: TaskRecord,
    user_goal: str,
    desired_outputs: list[str],
    context_budget: dict[str, Any] | None,
    ai_provider: AIProvider | None = None,
    ai_policy: AIProviderPolicy | None = None,
) -> tuple[str, str, list[str], list[str], str, str]:
    worker_run_id = generate_worker_run_id()
    run_dir = create_worker_run_dirs(root, record.task_id, worker_run_id)
    bundle = build_input_bundle(
        root=root,
        record=load_task(root, record.task_id),
        worker_run_id=worker_run_id,
        user_goal=user_goal,
        desired_outputs=desired_outputs,
        context_budget=context_budget,
    )
    _write_input_bundle(run_dir, bundle)
    worker, worker_type, policy_summary = _select_worker(root, ai_provider, ai_policy)
    request = WorkerRequest(
        task_id=record.task_id,
        worker_run_id=worker_run_id,
        worker_type=worker_type,
        user_goal=user_goal,
        desired_outputs=desired_outputs,
        input_bundle_path=to_manifest_path(run_dir / "input-bundle.json", root),
        sandbox_path=to_manifest_path(sandbox_dir(root, record.task_id, worker_run_id), root),
        context_budget=bundle.get("context_budget", {}),
        policy=policy_summary,
    )
    worker_result = WorkerInvocation(root=root, worker=worker).run(request)
    final_status, response_status, warnings, risk_flags = _validate_and_adopt_worker_result(
        root=root,
        record=record,
        user_goal=user_goal,
        desired_outputs=desired_outputs,
        context_budget=context_budget,
        run_dir=run_dir,
        worker_result=worker_result,
    )
    return worker_run_id, response_status, warnings, risk_flags, worker_type, final_status


def _select_worker(
    root: Path,
    ai_provider: AIProvider | None,
    ai_policy: AIProviderPolicy | None,
) -> tuple[SidecarWorker, str, dict[str, Any]]:
    policy = ai_policy or load_ai_provider_policy(root)
    policy_summary = _policy_summary(policy)
    if ai_provider is not None or policy.fake_provider_enabled or policy.real_provider_enabled:
        policy_summary["selection"] = "provider_backed"
        return ProviderBackedWorker(root=root, policy=policy, provider=ai_provider), "provider_backed", policy_summary

    availability = provider_availability(policy)
    initial_warnings: list[str] = []
    initial_risk_flags: list[str] = []
    if not availability.available:
        initial_warnings.append(availability.reason)
        initial_risk_flags.append("ai_provider_unavailable")
    policy_summary["selection"] = "heuristic"
    policy_summary["provider_availability"] = availability.reason
    return HeuristicWorker(root, initial_warnings=initial_warnings, initial_risk_flags=initial_risk_flags), "heuristic", policy_summary


def _validate_and_adopt_worker_result(
    root: Path,
    record: TaskRecord,
    user_goal: str,
    desired_outputs: list[str],
    context_budget: dict[str, Any] | None,
    run_dir: Path,
    worker_result: WorkerResult,
) -> tuple[str, str, list[str], list[str]]:
    warnings: list[str] = list(worker_result.warnings)
    risk_flags: list[str] = list(worker_result.risk_flags)
    accepted_any = False
    rejected_any = False
    accepted_types: set[str] = set()
    diagnostics: list[str] = list(worker_result.diagnostics)
    proposals = worker_result.proposal_list()

    for proposal in proposals:
        proposal_type = proposal.get("proposal_type")
        if isinstance(proposal_type, str) and proposal_type in accepted_types:
            continue
        validation = validate_proposal(root, record.task_id, worker_result.worker_run_id, proposal)
        diagnostics.extend(validation.diagnostics)
        if validation.accepted:
            adopt_proposal(root, record.task_id, worker_result.worker_run_id, proposal, validation)
            accepted_any = True
            if isinstance(proposal_type, str):
                accepted_types.add(proposal_type)
            bundle = build_input_bundle(
                root=root,
                record=load_task(root, record.task_id),
                worker_run_id=worker_result.worker_run_id,
                user_goal=user_goal,
                desired_outputs=desired_outputs,
                context_budget=context_budget,
            )
            _write_input_bundle(run_dir, bundle)
        else:
            rejected_any = True
            warnings.append(
                f"{worker_result.worker_type} {proposal_type or 'unknown'} proposal rejected; "
                "official artifacts were not generated from it"
            )

    if not proposals:
        unavailable_worker_result(root, record.task_id, worker_result.worker_run_id)
        if "intelligent_worker_unavailable" not in risk_flags:
            risk_flags.append("intelligent_worker_unavailable")
        warnings.append("intelligent worker produced no proposal; V1 deterministic fallback outputs were preserved")
        final_result = worker_result.model_copy(
            update={
                "status": "unavailable",
                "warnings": _dedupe(warnings),
                "risk_flags": _dedupe(risk_flags),
                "diagnostics": _dedupe(diagnostics),
            }
        )
        write_worker_result(root, final_result)
        return "unavailable", "worker_unavailable_fallback", _dedupe(warnings), _dedupe(risk_flags)

    if accepted_any:
        final_result = worker_result.model_copy(
            update={
                "status": "accepted",
                "warnings": _dedupe(warnings),
                "risk_flags": _dedupe(risk_flags),
                "diagnostics": _dedupe(diagnostics),
            }
        )
        write_worker_result(root, final_result)
        return "accepted", "accepted", _dedupe(warnings), _dedupe(risk_flags)

    if rejected_any:
        risk_flags.append("worker_proposal_rejected")
        if worker_result.worker_type == "heuristic":
            risk_flags.append("heuristic_proposal_rejected")
        final_result = worker_result.model_copy(
            update={
                "status": "rejected",
                "warnings": _dedupe(warnings),
                "risk_flags": _dedupe(risk_flags),
                "diagnostics": _dedupe(diagnostics),
            }
        )
        write_worker_result(root, final_result)
        return "rejected", "rejected_fallback", _dedupe(warnings), _dedupe(risk_flags)

    return "unavailable", "worker_unavailable_fallback", _dedupe(warnings), _dedupe(risk_flags)


def _tool_response(
    root: Path,
    record: TaskRecord,
    status: str,
    summary_headline: str,
    warnings: list[str],
    risk_flags: list[str],
    worker_run_id: str | None,
    intelligence_status: str | None,
    worker_type: str | None,
    worker_status: str | None,
    next_actions: list[str],
) -> dict[str, Any]:
    summary = {
        "headline": summary_headline,
        "task": task_summary(root, record),
        "outputs": compact_task_outputs(root, record),
    }
    if worker_run_id:
        summary["intelligence"] = {
            "worker_run_id": worker_run_id,
            "path": to_manifest_path(worker_run_dir(root, record.task_id, worker_run_id), root),
            "status": intelligence_status or "unknown",
            "worker_type": worker_type or "unknown",
            "worker_status": worker_status or "unknown",
        }
    return {
        "schema_version": "2.1",
        "task_id": record.task_id,
        "status": status,
        "summary": summary,
        "artifacts": artifact_list(record),
        "warnings": warnings[:10],
        "next_actions": next_actions,
        "risk_flags": risk_flags,
        "omitted": omitted_contract(),
    }


def _cancel_not_applicable_response(
    task_id: str,
    headline: str,
    warning: str,
    current_status: str | None,
    risk_flag: str,
) -> dict[str, Any]:
    summary: dict[str, Any] = {"headline": headline}
    if current_status is not None:
        summary["current_status"] = current_status
    return {
        "schema_version": "2.1",
        "task_id": task_id,
        "status": "not_cancelled",
        "summary": summary,
        "artifacts": [],
        "warnings": [warning],
        "next_actions": [f"inspect_sidecar_task {task_id}"] if current_status is not None else [],
        "risk_flags": [risk_flag],
        "omitted": omitted_contract(),
    }


def _normalize_desired_outputs(desired_outputs: list[str] | None) -> list[str]:
    if not desired_outputs:
        return ["metrics"]
    normalized = []
    for item in desired_outputs:
        if item not in SUPPORTED_OUTPUTS:
            raise ValueError(f"unsupported desired output: {item}")
        if item not in normalized:
            normalized.append(item)
    return normalized


def _summary_headline(intelligent_mode: str, desired_outputs: list[str], heuristic_status: str | None) -> str:
    outputs = ", ".join(desired_outputs) if desired_outputs else "requested outputs"
    if intelligent_mode == "off":
        return f"V1 deterministic fallback completed for {outputs}; intelligent mode was off."
    if heuristic_status == "accepted":
        return f"Worker adopted accepted proposal(s) for {outputs}; official artifacts were generated by V1 services."
    if heuristic_status == "rejected_fallback":
        return f"V1 deterministic fallback completed for {outputs}; worker proposal was rejected."
    return f"V1 deterministic fallback completed for {outputs}; intelligent worker was unavailable."


def _next_actions(task_id: str, desired_outputs: list[str], risk_flags: list[str]) -> list[str]:
    actions = [f"inspect_sidecar_task {task_id}"]
    if "intelligent_worker_unavailable" in risk_flags:
        actions.append("Review validator diagnostics in the task intelligence directory.")
    if "heuristic_proposal_rejected" in risk_flags or "worker_proposal_rejected" in risk_flags:
        actions.append("Review rejected heuristic proposal and validator diagnostics before writing manual config.")
    if "figures" in desired_outputs:
        actions.append("Review deterministic figure outputs before using them in downstream materials.")
    return actions


def _write_input_bundle(run_dir: Path, bundle: dict[str, Any]) -> None:
    (run_dir / "input-bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _policy_summary(policy: AIProviderPolicy) -> dict[str, Any]:
    return {
        "provider_name": policy.provider_name,
        "model_name": policy.model_name,
        "max_input_chars": policy.max_input_chars,
        "redact_secrets": policy.redact_secrets,
        "cloud_upload_allowed": policy.cloud_upload_allowed,
        "audit_prompt_response": policy.audit_prompt_response,
        "fake_provider_enabled": policy.fake_provider_enabled,
        "fake_provider_unavailable": policy.fake_provider_unavailable,
        "real_provider_enabled": policy.real_provider_enabled,
    }


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
