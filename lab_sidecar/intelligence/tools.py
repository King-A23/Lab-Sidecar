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
from lab_sidecar.intelligence.ai_policy import AIProviderPolicy, load_ai_provider_policy
from lab_sidecar.intelligence.ai_provider import AIProvider, run_ai_provider
from lab_sidecar.intelligence.bundle import build_input_bundle, omitted_contract
from lab_sidecar.intelligence.heuristic_worker import propose_figure, propose_metrics
from lab_sidecar.intelligence.paths import create_worker_run_dirs, generate_worker_run_id, worker_run_dir
from lab_sidecar.intelligence.preview import ArtifactPreviewError, preview_artifact
from lab_sidecar.intelligence.validator import unavailable_worker_result, validate_proposal
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
        worker_run_id, heuristic_status, heuristic_warnings, heuristic_risk_flags = _run_heuristic_worker(
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
        next_actions=_next_actions(task_id, [], []),
    )


def cancel_sidecar_task(
    workspace_path: str | Path,
    task_id: str,
) -> dict[str, Any]:
    root = Path(workspace_path).resolve()
    record = RunnerService(root).cancel(task_id)
    return _tool_response(
        root=root,
        record=record,
        status=record.status.value,
        summary_headline=f"Task {task_id} cancellation requested.",
        warnings=[],
        risk_flags=[],
        worker_run_id=None,
        intelligence_status=None,
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


def _run_heuristic_worker(
    root: Path,
    record: TaskRecord,
    user_goal: str,
    desired_outputs: list[str],
    context_budget: dict[str, Any] | None,
    ai_provider: AIProvider | None = None,
    ai_policy: AIProviderPolicy | None = None,
) -> tuple[str, str, list[str], list[str]]:
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
    (run_dir / "input-bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    warnings: list[str] = []
    risk_flags: list[str] = []
    accepted_any = False
    rejected_any = False
    accepted_types: set[str] = set()

    ai_result = run_ai_provider(
        root=root,
        task_id=record.task_id,
        worker_run_id=worker_run_id,
        bundle=bundle,
        policy=ai_policy or load_ai_provider_policy(root),
        provider=ai_provider,
    )
    warnings.extend(ai_result.warnings)
    risk_flags.extend(ai_result.risk_flags)
    if ai_result.proposal:
        validation = validate_proposal(root, record.task_id, worker_run_id, ai_result.proposal)
        if validation.accepted:
            adopt_proposal(root, record.task_id, worker_run_id, ai_result.proposal, validation)
            accepted_any = True
            proposal_type = ai_result.proposal.get("proposal_type")
            if isinstance(proposal_type, str):
                accepted_types.add(proposal_type)
            bundle = build_input_bundle(
                root=root,
                record=load_task(root, record.task_id),
                worker_run_id=worker_run_id,
                user_goal=user_goal,
                desired_outputs=desired_outputs,
                context_budget=context_budget,
            )
            (run_dir / "input-bundle.json").write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        else:
            rejected_any = True
            warnings.append("AI provider proposal rejected; heuristic fallback remains available")

    if "metrics" not in accepted_types and (
        "metrics" in desired_outputs or any(output in desired_outputs for output in ["figures", "report", "slides"])
    ):
        proposal = propose_metrics(root, record.task_id, worker_run_id, bundle)
        if proposal:
            validation = validate_proposal(root, record.task_id, worker_run_id, proposal)
            if validation.accepted:
                adopt_proposal(root, record.task_id, worker_run_id, proposal, validation)
                accepted_any = True
                bundle = build_input_bundle(
                    root=root,
                    record=load_task(root, record.task_id),
                    worker_run_id=worker_run_id,
                    user_goal=user_goal,
                    desired_outputs=desired_outputs,
                    context_budget=context_budget,
                )
                (run_dir / "input-bundle.json").write_text(
                    json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                rejected_any = True
                warnings.append("heuristic metrics proposal rejected; V1 fallback outputs were preserved")

    if "figure" not in accepted_types and ("figures" in desired_outputs or "slides" in desired_outputs):
        proposal = propose_figure(root, record.task_id, worker_run_id, bundle)
        if proposal:
            validation = validate_proposal(root, record.task_id, worker_run_id, proposal)
            if validation.accepted:
                adopt_proposal(root, record.task_id, worker_run_id, proposal, validation)
                accepted_any = True
            else:
                rejected_any = True
                warnings.append("heuristic figure proposal rejected; official figures were not generated from it")

    if accepted_any:
        return worker_run_id, "accepted", warnings, risk_flags
    if rejected_any:
        risk_flags.append("heuristic_proposal_rejected")
        return worker_run_id, "rejected_fallback", warnings, risk_flags

    unavailable_worker_result(root, record.task_id, worker_run_id)
    risk_flags.append("intelligent_worker_unavailable")
    warnings.append("heuristic worker produced no proposal; V1 deterministic fallback outputs were preserved")
    return worker_run_id, "worker_unavailable_fallback", warnings, risk_flags


def _tool_response(
    root: Path,
    record: TaskRecord,
    status: str,
    summary_headline: str,
    warnings: list[str],
    risk_flags: list[str],
    worker_run_id: str | None,
    intelligence_status: str | None,
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
        return f"Heuristic worker adopted accepted proposal(s) for {outputs}; official artifacts were generated by V1 services."
    if heuristic_status == "rejected_fallback":
        return f"V1 deterministic fallback completed for {outputs}; heuristic proposal was rejected."
    return f"V1 deterministic fallback completed for {outputs}; intelligent worker was unavailable."


def _next_actions(task_id: str, desired_outputs: list[str], risk_flags: list[str]) -> list[str]:
    actions = [f"inspect_sidecar_task {task_id}"]
    if "intelligent_worker_unavailable" in risk_flags:
        actions.append("Review validator diagnostics in the task intelligence directory.")
    if "heuristic_proposal_rejected" in risk_flags:
        actions.append("Review rejected heuristic proposal and validator diagnostics before writing manual config.")
    if "figures" in desired_outputs:
        actions.append("Review deterministic figure outputs before using them in downstream materials.")
    return actions
