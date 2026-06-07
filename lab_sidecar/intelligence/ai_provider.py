from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lab_sidecar.intelligence.ai_policy import AIProviderPolicy
from lab_sidecar.intelligence.heuristic_worker import (
    HeuristicWorker,
    propose_figure,
    propose_figure_from_metrics_proposal,
    propose_metrics,
    write_yaml,
)
from lab_sidecar.intelligence.paths import worker_run_dir
from lab_sidecar.intelligence.worker_invocation import WorkerRequest, WorkerResult, load_worker_input_bundle


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./+=]{4,})['\"]?"),
    re.compile(r"(?i)(bearer)\s+([A-Za-z0-9_\-./+=]{8,})"),
    re.compile(r"\b(sk)-[A-Za-z0-9_\-]{8,}\b"),
]
REDACTION_TEXT = "[REDACTED]"


@dataclass(frozen=True)
class ProviderInput:
    prompt: str
    bundle: dict[str, Any]
    truncated: bool
    max_input_chars: int


@dataclass(frozen=True)
class ProviderResult:
    proposal: dict[str, Any] | None
    response_text: str
    provider_name: str
    model_name: str | None


class AIProviderUnavailable(RuntimeError):
    pass


class AIProvider(Protocol):
    provider_name: str
    model_name: str | None

    def propose(self, provider_input: ProviderInput) -> ProviderResult:
        ...


class FakeAIProvider:
    provider_name = "fake"
    model_name = "fake-deterministic-v1"

    def __init__(
        self,
        root: Path | None = None,
        task_id: str | None = None,
        worker_run_id: str | None = None,
        unavailable: bool = False,
        proposal: dict[str, Any] | None = None,
        available: bool = True,
    ) -> None:
        self.root = root
        self.task_id = task_id
        self.worker_run_id = worker_run_id
        self.unavailable = unavailable or not available
        self.proposal = proposal
        self.last_prompt: str | None = None

    def propose(self, provider_input: ProviderInput) -> ProviderResult:
        self.last_prompt = provider_input.prompt
        if self.unavailable:
            raise AIProviderUnavailable("fake provider unavailable by policy")
        if self.proposal is not None:
            proposal = dict(self.proposal)
            proposal.setdefault("schema_version", "2.1")
            proposal.setdefault("task_id", provider_input.bundle.get("task_id"))
            proposal.setdefault("worker_run_id", provider_input.bundle.get("worker_run_id"))
            return ProviderResult(
                proposal=proposal,
                response_text=json.dumps(
                    {
                        "status": "proposal_created",
                        "proposal_type": proposal.get("proposal_type"),
                        "confidence": proposal.get("confidence"),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                provider_name=self.provider_name,
                model_name=self.model_name,
            )
        if self.root is None or self.task_id is None or self.worker_run_id is None:
            raise AIProviderUnavailable("fake provider has no proposal")

        desired_outputs = provider_input.bundle.get("desired_outputs") or []
        proposal = None
        if "metrics" in desired_outputs or any(output in desired_outputs for output in ["figures", "report", "slides"]):
            proposal = propose_metrics(self.root, self.task_id, self.worker_run_id, provider_input.bundle)
        if proposal is None and ("figures" in desired_outputs or "slides" in desired_outputs):
            proposal = propose_figure(self.root, self.task_id, self.worker_run_id, provider_input.bundle)
        if proposal is None:
            response = {"status": "no_proposal", "reason": "bounded input bundle did not contain enough fields"}
        else:
            response = {
                "status": "proposal_created",
                "proposal_type": proposal.get("proposal_type"),
                "confidence": proposal.get("confidence"),
            }
        return ProviderResult(
            proposal=proposal,
            response_text=json.dumps(response, ensure_ascii=False, sort_keys=True),
            provider_name=self.provider_name,
            model_name=self.model_name,
        )


class RealProviderSmokeStub:
    def __init__(self, policy: AIProviderPolicy) -> None:
        self.provider_name = policy.provider_name or "unknown"
        self.model_name = policy.model_name

    def propose(self, provider_input: ProviderInput) -> ProviderResult:
        raise AIProviderUnavailable("real provider execution is not implemented in local Phase 2.3")


class ProviderBackedWorker:
    worker_type = "provider_backed"

    def __init__(
        self,
        root: Path,
        policy: AIProviderPolicy,
        provider: AIProvider | None = None,
    ) -> None:
        self.root = root
        self.policy = policy
        self.provider = provider

    def run(self, request: WorkerRequest) -> WorkerResult:
        bundle = load_worker_input_bundle(self.root, request)
        provider_result = run_ai_provider(
            root=self.root,
            task_id=request.task_id,
            worker_run_id=request.worker_run_id,
            bundle=bundle,
            policy=self.policy,
            provider=self.provider,
        )
        proposals: list[dict[str, Any]] = []
        proposal_paths: list[str] = []
        diagnostics: list[str] = []
        warnings = list(provider_result.warnings)
        risk_flags = list(provider_result.risk_flags)
        fallback_used = False

        if provider_result.proposal is not None:
            proposals.append(provider_result.proposal)
            proposal_paths.append(_proposal_path(self.root, request.task_id, request.worker_run_id, provider_result.proposal))
            if provider_result.proposal.get("proposal_type") == "metrics" and (
                "figures" in request.desired_outputs or "slides" in request.desired_outputs
            ):
                figure_proposal = propose_figure_from_metrics_proposal(
                    self.root,
                    request.task_id,
                    request.worker_run_id,
                    provider_result.proposal,
                )
                if figure_proposal is not None:
                    proposals.append(figure_proposal)
                    proposal_paths.append(_proposal_path(self.root, request.task_id, request.worker_run_id, figure_proposal))
        else:
            fallback_used = True
            fallback = HeuristicWorker(self.root).run(request)
            proposals.extend(fallback.proposal_list())
            proposal_paths.extend(fallback.proposal_paths)
            warnings.extend(fallback.warnings)
            risk_flags.extend(flag for flag in fallback.risk_flags if flag not in risk_flags)
            diagnostics.extend(fallback.diagnostics)
            if provider_result.used_provider:
                warnings.append("AI provider produced no proposal; heuristic fallback was attempted")
            else:
                warnings.append("AI provider unavailable; heuristic fallback was attempted")

        status = "accepted" if proposals else "unavailable"
        if not proposals and "intelligent_worker_unavailable" not in risk_flags:
            risk_flags.append("intelligent_worker_unavailable")
        return WorkerResult(
            task_id=request.task_id,
            worker_run_id=request.worker_run_id,
            worker_type=self.worker_type,
            status=status,
            proposal=proposals[0] if proposals else None,
            proposals=proposals,
            proposal_path=proposal_paths[0] if proposal_paths else None,
            proposal_paths=proposal_paths,
            summary={
                "headline": "Provider-backed worker produced proposal(s)."
                if proposals
                else "Provider-backed worker produced no proposal.",
                "provider_name": self.provider.provider_name if self.provider else self.policy.provider_name,
                "model_name": self.provider.model_name if self.provider else self.policy.model_name,
                "proposal_count": len(proposals),
                "proposal_types": [proposal.get("proposal_type", "unknown") for proposal in proposals],
                "heuristic_fallback_used": fallback_used,
            },
            diagnostics=diagnostics,
            risk_flags=risk_flags,
            warnings=warnings,
        )


def build_provider_input(bundle: dict[str, Any], policy: AIProviderPolicy) -> ProviderInput:
    safe_bundle = _redact_value(bundle) if policy.redact_secrets else deepcopy(bundle)
    provider_bundle, truncated = _fit_bundle_to_budget(safe_bundle, policy.max_input_chars)
    prompt = _prompt_for_bundle(provider_bundle)
    return ProviderInput(
        prompt=prompt,
        bundle=provider_bundle,
        truncated=truncated,
        max_input_chars=policy.max_input_chars,
    )


def build_provider_prompt(bundle: dict[str, Any], policy: AIProviderPolicy) -> str:
    return build_provider_input(bundle, policy).prompt


def write_prompt_response_audit(
    root: Path,
    task_id: str,
    worker_run_id: str,
    provider_input: ProviderInput,
    result: ProviderResult | None,
    policy: AIProviderPolicy,
) -> None:
    run_dir = worker_run_dir(root, task_id, worker_run_id)
    metadata = {
        "provider_name": result.provider_name if result else policy.provider_name,
        "model_name": result.model_name if result else policy.model_name,
        "max_input_chars": provider_input.max_input_chars,
        "prompt_chars": len(provider_input.prompt),
        "input_truncated": provider_input.truncated,
        "redaction_enabled": policy.redact_secrets,
        "audit_prompt_response": policy.audit_enabled,
    }
    (run_dir / "ai-provider-audit.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not policy.audit_enabled:
        return
    (run_dir / "ai-provider-prompt.json").write_text(provider_input.prompt + "\n", encoding="utf-8")
    response_text = result.response_text if result else ""
    (run_dir / "ai-provider-response.json").write_text(response_text + "\n", encoding="utf-8")
    (run_dir / "prompt.md").write_text(provider_input.prompt + "\n", encoding="utf-8")
    (run_dir / "response.json").write_text(response_text + "\n", encoding="utf-8")


def write_provider_proposal(root: Path, task_id: str, worker_run_id: str, proposal: dict[str, Any]) -> None:
    proposal_type = proposal.get("proposal_type", "unknown")
    suffix = "metrics" if proposal_type == "metrics" else "figure" if proposal_type == "figure" else "ai"
    write_yaml(worker_run_dir(root, task_id, worker_run_id) / f"{suffix}-proposal.yaml", proposal)


def _proposal_path(root: Path, task_id: str, worker_run_id: str, proposal: dict[str, Any]) -> str:
    from lab_sidecar.core.paths import to_manifest_path

    proposal_type = proposal.get("proposal_type", "unknown")
    suffix = "metrics" if proposal_type == "metrics" else "figure" if proposal_type == "figure" else "ai"
    return to_manifest_path(worker_run_dir(root, task_id, worker_run_id) / f"{suffix}-proposal.yaml", root)


@dataclass(frozen=True)
class ProviderRunResult:
    proposal: dict[str, Any] | None
    risk_flags: list[str]
    warnings: list[str]
    used_provider: bool = False


def run_ai_provider(
    root: Path,
    task_id: str,
    worker_run_id: str,
    bundle: dict[str, Any],
    policy: AIProviderPolicy,
    provider: AIProvider | None = None,
) -> ProviderRunResult:
    availability = _provider_available(policy, provider)
    if not availability.available:
        return ProviderRunResult(
            proposal=None,
            risk_flags=["ai_provider_unavailable"],
            warnings=[availability.reason],
        )

    active_provider = provider
    if active_provider is None:
        active_provider = FakeAIProvider(root, task_id, worker_run_id) if policy.fake_provider_enabled else RealProviderSmokeStub(policy)

    provider_input = build_provider_input(bundle, policy)
    result: ProviderResult | None = None
    try:
        result = active_provider.propose(provider_input)
    except AIProviderUnavailable as exc:
        write_prompt_response_audit(root, task_id, worker_run_id, provider_input, None, policy)
        return ProviderRunResult(
            proposal=None,
            risk_flags=["ai_provider_unavailable"],
            warnings=[str(exc)],
        )

    write_prompt_response_audit(root, task_id, worker_run_id, provider_input, result, policy)
    if result.proposal is not None:
        write_provider_proposal(root, task_id, worker_run_id, result.proposal)
    return ProviderRunResult(proposal=result.proposal, risk_flags=[], warnings=[], used_provider=True)


def _provider_available(policy: AIProviderPolicy, provider: AIProvider | None) -> Any:
    from lab_sidecar.intelligence.ai_policy import ProviderAvailability, provider_availability

    if provider is not None and getattr(provider, "provider_name", None) == "fake":
        if policy.fake_provider_unavailable:
            return ProviderAvailability(False, "fake provider configured unavailable")
        return ProviderAvailability(True, "injected fake provider available")
    return provider_availability(policy)


def _bundle_from_prompt(prompt: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(prompt)
    except json.JSONDecodeError:
        return fallback
    bundle = parsed.get("input_bundle") if isinstance(parsed, dict) else None
    return bundle if isinstance(bundle, dict) else fallback


def _prompt_for_bundle(bundle: dict[str, Any]) -> str:
    prompt_envelope = {
        "instruction": (
            "Create one Lab-Sidecar V2 proposal from this bounded input bundle only. "
            "Do not infer from complete logs, complete datasets, or source code."
        ),
        "input_bundle": bundle,
    }
    return json.dumps(prompt_envelope, ensure_ascii=False, sort_keys=True)


def _fit_bundle_to_budget(bundle: dict[str, Any], max_chars: int) -> tuple[dict[str, Any], bool]:
    fitted = deepcopy(bundle)
    if len(_prompt_for_bundle(fitted)) <= max_chars:
        return fitted, False

    omitted = fitted.setdefault("provider_omitted", {})
    if isinstance(fitted.get("logs"), dict):
        fitted["logs"] = {
            "stdout_tail": _trim_lines(fitted["logs"].get("stdout_tail"), 8, 400),
            "stderr_tail": _trim_lines(fitted["logs"].get("stderr_tail"), 8, 400),
        }
        omitted["provider_logs"] = "trimmed_to_provider_budget"
    for key in ["candidate_previews", "data_previews"]:
        if isinstance(fitted.get(key), list):
            fitted[key] = [_trim_preview(preview) for preview in fitted[key][:4] if isinstance(preview, dict)]
            omitted[f"provider_{key}"] = "trimmed_to_provider_budget"
    if len(_prompt_for_bundle(fitted)) <= max_chars:
        return fitted, True

    if isinstance(fitted.get("artifacts"), list):
        fitted["artifacts"] = fitted["artifacts"][:8]
        omitted["provider_artifacts"] = "trimmed_to_provider_budget"
    for key in ["candidate_previews", "data_previews"]:
        if isinstance(fitted.get(key), list):
            fitted[key] = [_drop_preview_samples(preview) for preview in fitted[key][:2] if isinstance(preview, dict)]
            omitted[f"provider_{key}_samples"] = "omitted_to_provider_budget"
    if len(_prompt_for_bundle(fitted)) <= max_chars:
        return fitted, True

    fitted["logs"] = {"stdout_tail": [], "stderr_tail": []}
    fitted["artifacts"] = []
    fitted["user_goal"] = _short_text(fitted.get("user_goal"), 240)
    omitted["provider_logs"] = "omitted_to_provider_budget"
    omitted["provider_artifacts"] = "omitted_to_provider_budget"
    if len(_prompt_for_bundle(fitted)) <= max_chars:
        return fitted, True

    minimal = {
        "schema_version": fitted.get("schema_version"),
        "task_id": fitted.get("task_id"),
        "worker_run_id": fitted.get("worker_run_id"),
        "user_goal": _short_text(fitted.get("user_goal"), 120),
        "desired_outputs": fitted.get("desired_outputs", []),
        "candidate_previews": fitted.get("candidate_previews", [])[:1],
        "data_previews": fitted.get("data_previews", [])[:1],
        "omitted": fitted.get("omitted", {}),
        "provider_omitted": {"provider_input": "reduced_to_minimal_budget"},
    }
    while len(_prompt_for_bundle(minimal)) > max_chars and minimal.get("candidate_previews"):
        minimal["candidate_previews"] = []
    while len(_prompt_for_bundle(minimal)) > max_chars and minimal.get("data_previews"):
        minimal["data_previews"] = []
    return minimal, True


def _trim_preview(preview: dict[str, Any]) -> dict[str, Any]:
    trimmed = dict(preview)
    if isinstance(trimmed.get("row_sample"), list):
        trimmed["row_sample"] = trimmed["row_sample"][:2]
        trimmed["row_sample_count"] = min(int(trimmed.get("row_sample_count") or 0), 2)
    if isinstance(trimmed.get("sample"), list):
        trimmed["sample"] = trimmed["sample"][:2]
    if isinstance(trimmed.get("descriptive_stats"), dict):
        trimmed["descriptive_stats"] = dict(list(trimmed["descriptive_stats"].items())[:8])
    return trimmed


def _drop_preview_samples(preview: dict[str, Any]) -> dict[str, Any]:
    trimmed = _trim_preview(preview)
    trimmed["row_sample"] = []
    if isinstance(trimmed.get("sample"), list):
        trimmed["sample"] = []
    trimmed["sample_omitted"] = "omitted_to_provider_budget"
    return trimmed


def _trim_lines(value: Any, max_lines: int, max_line_chars: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_short_text(line, max_line_chars) for line in value[:max_lines] if isinstance(line, str)]


def _short_text(value: Any, limit: int) -> Any:
    if not isinstance(value, str) or len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_key_value(key, child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_key_value(key: Any, value: Any) -> Any:
    if isinstance(key, str) and re.search(r"(?i)(api[_-]?key|secret|token|password)", key):
        if isinstance(value, (str, int, float, bool)) or value is None:
            return REDACTION_TEXT
    return _redact_value(value)


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}={REDACTION_TEXT}", redacted)
    return redacted
