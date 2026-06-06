from __future__ import annotations

import csv
import json
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.intelligence import delegate_experiment_artifacts
from lab_sidecar.intelligence.ai_policy import AIProviderPolicy, real_provider_smoke_skip_reason
from lab_sidecar.intelligence.ai_provider import (
    FakeAIProvider,
    build_provider_input,
)
from lab_sidecar.intelligence.paths import worker_run_dir


def write_nonstandard_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["iter", "variant", "acc", "err", "api_key"])
        writer.writeheader()
        writer.writerows(
            [
                {"iter": 1, "variant": "baseline", "acc": 0.62, "err": 0.9, "api_key": "sk-testsecret0000"},
                {"iter": 2, "variant": "baseline", "acc": 0.68, "err": 0.72, "api_key": "sk-testsecret0000"},
                {"iter": 1, "variant": "candidate", "acc": 0.66, "err": 0.82, "api_key": "sk-testsecret0000"},
                {"iter": 2, "variant": "candidate", "acc": 0.75, "err": 0.61, "api_key": "sk-testsecret0000"},
            ]
        )


def fake_metrics_proposal(task_id: str | None = None, worker_run_id: str | None = None) -> dict:
    proposal = {
        "schema_version": "2.1",
        "proposal_type": "metrics",
        "source_files": [
            {
                "path": "results/trial_output.csv",
                "columns": ["iter", "variant", "acc", "err", "api_key"],
            }
        ],
        "field_mappings": [
            {"target": "epoch", "sources": ["iter"]},
            {"target": "model", "sources": ["variant"]},
            {"target": "accuracy", "sources": ["acc"]},
            {"target": "loss", "sources": ["err"]},
        ],
        "rationale": "Fake provider mapped bounded candidate fields.",
        "confidence": 0.9,
    }
    if task_id:
        proposal["task_id"] = task_id
    if worker_run_id:
        proposal["worker_run_id"] = worker_run_id
    return proposal


def enabled_fake_policy(audit_retention: bool = False, max_input_chars: int = 4000) -> AIProviderPolicy:
    return AIProviderPolicy(
        provider_name="fake",
        model_name="fake-deterministic-v1",
        max_input_chars=max_input_chars,
        redact_secrets=True,
        cloud_upload_allowed=False,
        audit_prompt_response=audit_retention,
        fake_provider_enabled=True,
    )


def test_fake_provider_success_still_validates_and_adopts_official_metrics(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)
    provider = FakeAIProvider(proposal=fake_metrics_proposal())

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Use fake AI provider to propose metrics.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=provider,
        ai_policy=enabled_fake_policy(audit_retention=True),
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)
    adoption = json.loads((run_dir / "adoption-record.json").read_text(encoding="utf-8"))
    validator = json.loads((run_dir / "validator-result.json").read_text(encoding="utf-8"))

    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert result["risk_flags"] == []
    assert validator["accepted"] is True
    assert adoption["adoptions"][0]["proposal_type"] == "metrics"
    assert (tmp_path / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv").is_file()
    assert (run_dir / "ai-provider-prompt.json").is_file()
    assert (run_dir / "ai-provider-response.json").is_file()
    assert (run_dir / "ai-provider-audit.json").is_file()


def test_fake_provider_unavailable_falls_back_to_heuristic_without_crashing(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Provider unavailable should fall back.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=FakeAIProvider(proposal=fake_metrics_proposal(), available=False),
        ai_policy=enabled_fake_policy(),
    )

    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert "ai_provider_unavailable" in result["risk_flags"]
    assert (tmp_path / ".lab-sidecar" / "tasks" / result["task_id"] / "metrics" / "normalized_metrics.csv").is_file()


def test_budget_truncation_and_redaction_apply_before_provider_input(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)
    provider = FakeAIProvider(proposal=fake_metrics_proposal())

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Secret token=abc123 and sk-testsecret0000 should be redacted before provider input.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=provider,
        ai_policy=enabled_fake_policy(max_input_chars=1000),
    )

    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert provider.last_prompt is not None
    assert len(provider.last_prompt) <= 1000
    assert "abc123" not in provider.last_prompt
    assert "sk-testsecret0000" not in provider.last_prompt
    assert "[REDACTED]" in provider.last_prompt


def test_audit_artifacts_only_written_when_policy_allows(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    first = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="No audit.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=FakeAIProvider(proposal=fake_metrics_proposal()),
        ai_policy=enabled_fake_policy(audit_retention=False),
    )
    first_dir = worker_run_dir(tmp_path, first["task_id"], first["summary"]["intelligence"]["worker_run_id"])

    second = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="With audit.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=FakeAIProvider(proposal=fake_metrics_proposal()),
        ai_policy=enabled_fake_policy(audit_retention=True),
    )
    second_dir = worker_run_dir(tmp_path, second["task_id"], second["summary"]["intelligence"]["worker_run_id"])

    assert (first_dir / "ai-provider-audit.json").is_file()
    assert not (first_dir / "ai-provider-prompt.json").exists()
    assert not (first_dir / "ai-provider-response.json").exists()
    assert (second_dir / "ai-provider-prompt.json").is_file()
    assert (second_dir / "ai-provider-response.json").is_file()


def test_default_response_omits_prompt_and_response_text(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Audit exists but response must omit prompt text.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=FakeAIProvider(proposal=fake_metrics_proposal()),
        ai_policy=enabled_fake_policy(audit_retention=True),
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["omitted"]["worker_prompt_response"] == "omitted_by_default"
    assert "Return one Lab-Sidecar V2 proposal" not in serialized
    assert "Fake provider mapped bounded candidate fields" not in serialized


def test_no_key_environment_falls_back_successfully(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LAB_SIDECAR_AI_KEY", raising=False)
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)
    config = tmp_path / ".lab-sidecar" / "config.yaml"
    config.write_text(
        "\n".join(
            [
                "schema_version: '1'",
                "ai_provider:",
                "  enabled: true",
                "  provider: openai",
                "  key_env: LAB_SIDECAR_AI_KEY",
                "  cloud_upload_allowed: true",
                "  audit:",
                "    prompt_response: true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Missing real provider key should not break heuristic fallback.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
    )

    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert result["risk_flags"] == ["ai_provider_unavailable"]
    assert (tmp_path / ".lab-sidecar" / "tasks" / result["task_id"] / "metrics" / "normalized_metrics.csv").is_file()


def test_build_provider_prompt_uses_bounded_bundle_only() -> None:
    bundle = {
        "logs": {"stdout_tail": ["hello"], "stderr_tail": ["token=abc123"]},
        "data_previews": [{"row_sample": [{"metric": "acc"}]}],
        "omitted": {"full_stdout": "omitted_by_default", "full_data_files": "omitted_by_default"},
    }
    prompt = build_provider_input(bundle, enabled_fake_policy(max_input_chars=1000)).prompt

    assert "full_stdout" in prompt
    assert "full_data_files" in prompt
    assert "abc123" not in prompt
    assert len(prompt) <= 1000


def test_real_provider_smoke_skips_without_explicit_safe_configuration(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    init_workspace(tmp_path)

    reason = real_provider_smoke_skip_reason(tmp_path)

    assert reason is not None
    assert "explicitly enable a real provider" in reason
