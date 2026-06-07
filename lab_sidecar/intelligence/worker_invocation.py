from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from lab_sidecar.core.paths import resolve_workspace_path
from lab_sidecar.intelligence.bundle import omitted_contract
from lab_sidecar.intelligence.paths import worker_run_dir


WorkerStatus = Literal["accepted", "rejected", "unavailable", "skipped"]


class WorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.1"
    task_id: str
    worker_run_id: str
    worker_type: str
    user_goal: str
    desired_outputs: list[str] = Field(default_factory=list)
    input_bundle_path: str
    sandbox_path: str
    context_budget: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))


class WorkerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.1"
    task_id: str
    worker_run_id: str
    worker_type: str
    status: WorkerStatus
    proposal: dict[str, Any] | None = None
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    proposal_path: str | None = None
    proposal_paths: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    omitted: dict[str, str] = Field(default_factory=omitted_contract)

    def proposal_list(self) -> list[dict[str, Any]]:
        if self.proposals:
            return self.proposals
        if self.proposal:
            return [self.proposal]
        return []


class SidecarWorker(Protocol):
    worker_type: str

    def run(self, request: WorkerRequest) -> WorkerResult:
        ...


@dataclass(frozen=True)
class WorkerInvocation:
    root: Path
    worker: SidecarWorker | None

    def run(self, request: WorkerRequest) -> WorkerResult:
        write_worker_request(self.root, request)
        if self.worker is None:
            result = WorkerResult(
                task_id=request.task_id,
                worker_run_id=request.worker_run_id,
                worker_type=request.worker_type,
                status="unavailable",
                summary={"headline": "No worker was available; V1 deterministic fallback remains available."},
                diagnostics=["intelligent_worker_unavailable: no worker was selected."],
                risk_flags=["intelligent_worker_unavailable"],
            )
        else:
            result = self.worker.run(request)
        result = normalize_worker_result(request, result)
        write_worker_result(self.root, result)
        return result


def normalize_worker_result(request: WorkerRequest, result: WorkerResult) -> WorkerResult:
    proposals = result.proposal_list()
    proposal = result.proposal or (proposals[0] if proposals else None)
    proposal_paths = result.proposal_paths
    proposal_path = result.proposal_path or (proposal_paths[0] if proposal_paths else None)
    return result.model_copy(
        update={
            "schema_version": "2.1",
            "task_id": request.task_id,
            "worker_run_id": request.worker_run_id,
            "worker_type": request.worker_type,
            "proposal": proposal,
            "proposals": proposals,
            "proposal_path": proposal_path,
            "proposal_paths": proposal_paths,
            "omitted": result.omitted or omitted_contract(),
        }
    )


def worker_request_path(root: Path, task_id: str, worker_run_id: str) -> Path:
    return worker_run_dir(root, task_id, worker_run_id) / "worker-request.json"


def worker_result_path(root: Path, task_id: str, worker_run_id: str) -> Path:
    return worker_run_dir(root, task_id, worker_run_id) / "worker-result.json"


def write_worker_request(root: Path, request: WorkerRequest) -> None:
    path = worker_request_path(root, request.task_id, request.worker_run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(request.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_worker_result(root: Path, result: WorkerResult) -> None:
    path = worker_result_path(root, result.task_id, result.worker_run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_worker_input_bundle(root: Path, request: WorkerRequest) -> dict[str, Any]:
    path = resolve_workspace_path(request.input_bundle_path, root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}

