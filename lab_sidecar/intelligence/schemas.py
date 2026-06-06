from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ProposalType = Literal["metrics", "figure", "report", "slides", "failure_diagnosis", "unknown"]


class ProposalSkeleton(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "2.1"
    proposal_type: ProposalType = "unknown"
    worker_run_id: str | None = None
    task_id: str | None = None
    rationale: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ValidatorCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["passed", "failed", "skipped"]
    message: str | None = None


class ValidatorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.1"
    accepted: bool
    proposal_type: str = "unknown"
    checks: list[ValidatorCheck] = Field(default_factory=list)
    adopted_config_path: str | None = None
    diagnostics: list[str] = Field(default_factory=list)
