from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lab_sidecar.core.models import ArtifactRecord


class ComparisonStatus(StrEnum):
    COMPLETED = "completed"


class ComparisonManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str = "1"
    comparison_id: str
    status: ComparisonStatus = ComparisonStatus.COMPLETED
    created_at: str
    updated_at: str
    name: str | None = None
    task_ids: list[str]
    row_selection: str = "final_row"
    paths: dict[str, str]
    source_tasks: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def artifact_count(self) -> int:
        return len(self.artifacts)


@dataclass(frozen=True)
class ComparisonBuildResult:
    manifest: ComparisonManifest
    comparison_dir: Path
    summary_path: Path
    table_csv_path: Path
    table_json_path: Path
    figure_summary_path: Path | None = None
    report_path: Path | None = None
    report_summary_path: Path | None = None
    traceability_path: Path | None = None


class ComparisonError(RuntimeError):
    """Base class for comparison workflow errors."""


class ComparisonTaskNotFound(ComparisonError, FileNotFoundError):
    """Raised when a source task cannot be found."""


class ComparisonInvalidId(ComparisonError, ValueError):
    """Raised when a saved comparison id is malformed."""


class ComparisonDuplicateTaskIds(ComparisonError, ValueError):
    """Raised when a comparison request repeats a task id."""


class ComparisonMetricsMissing(ComparisonError):
    """Raised when a source task has no collected normalized metrics."""


class NoCommonComparisonMetrics(ComparisonError):
    """Raised when selected tasks have no shared numeric metrics."""


class ComparisonOutputError(ComparisonError):
    """Raised when comparison artifacts cannot be written."""


class ComparisonValidationStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class ComparisonValidationRequirement(StrEnum):
    FIGURES = "figures"
    REPORT = "report"
    PACKAGE_READY = "package-ready"


@dataclass(frozen=True)
class ComparisonValidationCheck:
    name: str
    status: ComparisonValidationStatus
    message: str
    path: str | None = None
    next_action: str | None = None


@dataclass(frozen=True)
class ComparisonValidationResult:
    comparison_id: str
    checks: list[ComparisonValidationCheck] = field(default_factory=list)

    @property
    def status(self) -> ComparisonValidationStatus:
        statuses = {check.status for check in self.checks}
        if ComparisonValidationStatus.FAIL in statuses:
            return ComparisonValidationStatus.FAIL
        if ComparisonValidationStatus.WARN in statuses:
            return ComparisonValidationStatus.WARN
        return ComparisonValidationStatus.OK

    @property
    def has_failures(self) -> bool:
        return self.status == ComparisonValidationStatus.FAIL


class ComparisonNotFound(FileNotFoundError):
    """Raised when a saved comparison record cannot be found."""
