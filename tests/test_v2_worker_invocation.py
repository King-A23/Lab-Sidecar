from __future__ import annotations

import csv
import json
from pathlib import Path

from lab_sidecar.core.config import init_workspace
from lab_sidecar.intelligence import delegate_experiment_artifacts
from lab_sidecar.intelligence.ai_policy import AIProviderPolicy
from lab_sidecar.intelligence.ai_provider import FakeAIProvider
from lab_sidecar.intelligence.paths import worker_run_dir


def write_nonstandard_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["iter", "variant", "acc", "err", "api_key"])
        writer.writeheader()
        writer.writerows(
            [
                {"iter": 1, "variant": "baseline", "acc": 0.62, "err": 0.9, "api_key": "sk-secret0000"},
                {"iter": 2, "variant": "baseline", "acc": 0.68, "err": 0.72, "api_key": "sk-secret0000"},
                {"iter": 1, "variant": "candidate", "acc": 0.66, "err": 0.82, "api_key": "sk-secret0000"},
                {"iter": 2, "variant": "candidate", "acc": 0.75, "err": 0.61, "api_key": "sk-secret0000"},
            ]
        )


def enabled_fake_policy(audit_retention: bool = False) -> AIProviderPolicy:
    return AIProviderPolicy(
        provider_name="fake",
        model_name="fake-deterministic-v1",
        redact_secrets=True,
        cloud_upload_allowed=False,
        audit_prompt_response=audit_retention,
        fake_provider_enabled=True,
    )


def fake_metrics_proposal() -> dict:
    return {
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


def rejected_figure_proposal() -> dict:
    return {
        "schema_version": "2.1",
        "proposal_type": "figure",
        "source_metrics": "metrics/missing.csv",
        "source_metrics_fields": ["epoch", "accuracy"],
        "figures": [
            {
                "figure_id": "bad_missing",
                "chart_type": "line",
                "title": "Bad Missing Field",
                "x": "epoch",
                "y": "does_not_exist",
                "output": {"png": "figures/bad_missing.png", "svg": "figures/bad_missing.svg"},
            }
        ],
    }


def test_heuristic_worker_invocation_persists_request_result_and_adopts_after_validation(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Use the shared worker protocol to collect metrics.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)
    request = json.loads((run_dir / "worker-request.json").read_text(encoding="utf-8"))
    worker_result = json.loads((run_dir / "worker-result.json").read_text(encoding="utf-8"))
    validator = json.loads((run_dir / "validator-result.json").read_text(encoding="utf-8"))

    assert request["worker_type"] == "heuristic"
    assert request["input_bundle_path"].endswith("input-bundle.json")
    assert request["sandbox_path"].endswith("sandbox")
    assert worker_result["worker_type"] == "heuristic"
    assert worker_result["status"] == "accepted"
    assert worker_result["proposals"][0]["proposal_type"] == "metrics"
    assert validator["accepted"] is True
    assert (run_dir / "adoption-record.json").is_file()
    assert (tmp_path / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv").is_file()


def test_fake_provider_worker_uses_same_protocol_and_quarantines_prompt_response(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)
    provider = FakeAIProvider(proposal=fake_metrics_proposal())

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Use fake provider through WorkerInvocation.",
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
    request = json.loads((run_dir / "worker-request.json").read_text(encoding="utf-8"))
    worker_result_text = (run_dir / "worker-result.json").read_text(encoding="utf-8")
    worker_result = json.loads(worker_result_text)
    response_text = json.dumps(result, ensure_ascii=False)

    assert request["worker_type"] == "provider_backed"
    assert worker_result["worker_type"] == "provider_backed"
    assert worker_result["status"] == "accepted"
    assert worker_result["proposals"][0]["proposal_type"] == "metrics"
    assert (run_dir / "ai-provider-prompt.json").is_file()
    assert (run_dir / "ai-provider-response.json").is_file()
    assert "Create one Lab-Sidecar V2 proposal" not in worker_result_text
    assert "Create one Lab-Sidecar V2 proposal" not in response_text
    assert "Fake provider mapped bounded candidate fields" not in response_text


def test_intelligent_mode_off_skips_worker_invocation_files(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Skip intelligent worker.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="off",
    )

    task_path = tmp_path / ".lab-sidecar" / "tasks" / result["task_id"]
    assert result["risk_flags"] == ["intelligent_mode_off"]
    assert "intelligence" not in result["summary"]
    assert not (task_path / "intelligence").exists()


def test_provider_unavailable_falls_back_with_worker_result_risk_flag(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Unavailable provider should not block heuristic fallback.",
        result_path=source,
        desired_outputs=["metrics"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=FakeAIProvider(proposal=fake_metrics_proposal(), available=False),
        ai_policy=enabled_fake_policy(),
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)
    worker_result = json.loads((run_dir / "worker-result.json").read_text(encoding="utf-8"))

    assert result["summary"]["intelligence"]["status"] == "accepted"
    assert "ai_provider_unavailable" in result["risk_flags"]
    assert worker_result["worker_type"] == "provider_backed"
    assert worker_result["status"] == "accepted"
    assert worker_result["summary"]["heuristic_fallback_used"] is True
    assert "ai_provider_unavailable" in worker_result["risk_flags"]
    assert (tmp_path / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv").is_file()


def test_rejected_worker_proposal_is_recorded_without_official_adoption(tmp_path: Path) -> None:
    init_workspace(tmp_path)
    source = tmp_path / "results" / "trial_output.csv"
    write_nonstandard_csv(source)

    result = delegate_experiment_artifacts(
        workspace_path=tmp_path,
        user_goal="Reject invalid provider figure proposal.",
        result_path=source,
        desired_outputs=["figures"],
        intelligent_mode="auto",
        context_budget={"preview_rows": 4},
        ai_provider=FakeAIProvider(proposal=rejected_figure_proposal()),
        ai_policy=enabled_fake_policy(),
    )

    task_id = result["task_id"]
    worker_run_id = result["summary"]["intelligence"]["worker_run_id"]
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    run_dir = worker_run_dir(tmp_path, task_id, worker_run_id)
    worker_result = json.loads((run_dir / "worker-result.json").read_text(encoding="utf-8"))
    validator = json.loads((run_dir / "validator-result.json").read_text(encoding="utf-8"))

    assert result["summary"]["intelligence"]["status"] == "rejected_fallback"
    assert result["summary"]["intelligence"]["worker_status"] == "rejected"
    assert "worker_proposal_rejected" in result["risk_flags"]
    assert worker_result["status"] == "rejected"
    assert worker_result["proposals"][0]["proposal_type"] == "figure"
    assert validator["accepted"] is False
    assert not (run_dir / "adoption-record.json").exists()
    assert not (task_path / "figures" / "bad_missing.png").exists()
    assert not list((task_path / "figures").glob("*.png"))

