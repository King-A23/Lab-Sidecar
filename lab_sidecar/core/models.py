from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    type: str
    path: str
    description: str
    source_paths: list[str] = Field(default_factory=list)


class TaskPaths(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_dir: str
    stdout: str
    stderr: str


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1"
    task_id: str
    mode: Literal["run", "ingest"]
    status: TaskStatus
    created_at: str
    updated_at: str
    working_dir: str
    command: str | None = None
    source_path: str | None = None
    exit_code: int | None = None
    paths: TaskPaths
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    name: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    failure_summary: str | None = None
    pid: int | None = None
    worker_pid: int | None = None

    def artifact_count(self) -> int:
        return len(self.artifacts)


class LabConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1"
    state_dir: str = ".lab-sidecar"
    tasks_dir: str = ".lab-sidecar/tasks"


def model_dump_jsonable(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=False)
