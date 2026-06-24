from __future__ import annotations

import csv
import json
import importlib.util
import math
import sys
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any

import typer

from lab_sidecar.core.config import init_workspace
from lab_sidecar.core.manifest import load_task
from lab_sidecar.core.paths import config_path, resolve_workspace_path, sqlite_path, state_dir
from lab_sidecar.core.validation import (
    TaskValidationService,
    ValidationRequirement,
    ValidationResult,
    ValidationTaskNotFound,
)
from lab_sidecar.core.models import TaskStatus
from lab_sidecar.collectors.service import MetricsCollectionService, MetricsConfigLoadError, NoMetricsFoundError
from lab_sidecar.comparisons.models import (
    ComparisonDuplicateTaskIds,
    ComparisonInvalidId,
    ComparisonMetricsMissing,
    ComparisonNotFound,
    ComparisonOutputError,
    ComparisonTaskNotFound,
    ComparisonValidationRequirement,
    ComparisonValidationResult,
    NoCommonComparisonMetrics,
)
from lab_sidecar.comparisons.package_export import (
    ComparisonPackageExportError,
    export_comparison_package,
)
from lab_sidecar.comparisons.service import (
    ComparisonService,
    comparison_artifact_dir,
    comparison_artifact_presence,
    list_comparison_ids,
    load_comparison_manifest,
)
from lab_sidecar.comparisons.validation import ComparisonValidationService
from lab_sidecar.figures.fallback_worker import FallbackWorkerMode
from lab_sidecar.figures.service import (
    FallbackMode,
    FigureGenerationService,
    FigureSpecLoadError,
    MetricsNotReadyError,
    NoFiguresGeneratedError,
)
from lab_sidecar.reports.service import (
    InvalidReportTemplateError,
    ReportGenerationService,
    ReportMetricsRequiredError,
    ReportWriteError,
)
from lab_sidecar.runner.service import RunnerService, list_task_ids, tail_lines
from lab_sidecar.slides.service import (
    InvalidSlidesTemplateError,
    SlidesArtifactsRequiredError,
    SlidesGenerationService,
    SlidesWriteError,
)
from lab_sidecar.storage.package_export import (
    PackageExportError,
    PackageOutputError,
    PackageVerifyError,
    export_task_package,
    verify_task_package,
)


app = typer.Typer(help="Local-first research sidecar for AI agents and experiment workflows.")


class LogStream(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"
    BOTH = "both"


METRICS_RELATIVE_PATH = Path("metrics") / "normalized_metrics.csv"
COLLECTION_SUMMARY_RELATIVE_PATH = Path("metrics") / "collection-summary.json"
SCENARIO_SUMMARY_RELATIVE_PATH = Path("metrics") / "scenario-summary.json"
FIGURE_SUMMARY_RELATIVE_PATH = Path("figures") / "figure-summary.json"
REPORT_RELATIVE_PATH = Path("reports") / "report-fragment.md"
SLIDES_RELATIVE_PATH = Path("slides") / "presentation-draft.pptx"
COMPARISON_METADATA_COLUMNS = {
    "source_file",
    "source_path",
    "file",
    "path",
    "epoch",
    "step",
    "iter",
    "iteration",
    "checkpoint",
    "ckpt",
    "timestamp",
    "seed",
    "trial",
    "run_id",
    "config_id",
}
COMMAND_PREVIEW_CHARS = 120
FAILURE_SUMMARY_LINES = 8
FAILURE_SUMMARY_LINE_CHARS = 160


def _root() -> Path:
    return Path.cwd().resolve()


def _fail(message: str, code: int = 1) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _echo_next(*commands: str) -> None:
    if not commands:
        return
    typer.echo("Next:")
    for command in commands:
        typer.echo(f"- {command}")


def _json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _artifact_type_counts(record) -> dict[str, int]:
    counts: dict[str, int] = {}
    for artifact in record.artifacts:
        counts[artifact.type] = counts.get(artifact.type, 0) + 1
    return dict(sorted(counts.items()))


def _format_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "(none)"
    return ", ".join(f"{kind}={count}" for kind, count in counts.items())


def _task_path(record, root: Path) -> Path:
    return resolve_workspace_path(record.paths.task_dir, root)


def _task_artifact_path(record, root: Path, relative_path: Path) -> Path:
    return _task_path(record, root) / relative_path


def _artifact_presence(record, root: Path) -> list[tuple[str, str, bool]]:
    task_path = _task_path(record, root)
    items = [
        ("metrics", METRICS_RELATIVE_PATH.as_posix()),
        ("scenario", SCENARIO_SUMMARY_RELATIVE_PATH.as_posix()),
        ("figures", FIGURE_SUMMARY_RELATIVE_PATH.as_posix()),
        ("report", REPORT_RELATIVE_PATH.as_posix()),
        ("slides", SLIDES_RELATIVE_PATH.as_posix()),
    ]
    return [(label, relative, (task_path / relative).exists()) for label, relative in items]


def _status_updated_at(record) -> str:
    return record.finished_at or record.updated_at or record.created_at


def _display_name(record) -> str:
    return record.name or "(unnamed)"


def _preview_text(value: str | None, limit: int = COMMAND_PREVIEW_CHARS) -> str:
    if not value:
        return "(none)"
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _short_failure_summary(record) -> str | None:
    if not record.failure_summary:
        return None
    lines = [line for line in record.failure_summary.splitlines() if line.strip()]
    return "\n".join(
        _preview_text(line, FAILURE_SUMMARY_LINE_CHARS)
        for line in lines[:FAILURE_SUMMARY_LINES]
    )


def _print_key_artifacts(record, root: Path, include_missing: bool = False) -> None:
    key_artifacts = _artifact_presence(record, root)
    if not include_missing and not any(exists for _label, _relative, exists in key_artifacts):
        return
    typer.echo("Key artifacts:")
    for label, relative, exists in key_artifacts:
        if exists:
            typer.echo(f"- {label}: {relative}")
        elif include_missing:
            typer.echo(f"- {label}: (not generated)")


def _print_validation_result(result: ValidationResult) -> None:
    typer.echo(f"Validation for {result.task_id}")
    typer.echo(f"Result: {result.status.value}")
    typer.echo(f"Task status: {result.task_status or '(unknown)'}")
    typer.echo(f"Mode: {result.mode or '(unknown)'}")
    typer.echo(f"Diagnostic mode: {'yes' if result.diagnostic_mode else 'no'}")
    typer.echo("Checks:")
    for check in result.checks:
        suffix = f" ({check.path})" if check.path else ""
        typer.echo(f"[{check.status.value}] {check.name}: {check.message}{suffix}")
        if check.next_action:
            typer.echo(f"  next: {check.next_action}")


def _print_comparison_validation_result(result: ComparisonValidationResult) -> None:
    typer.echo(f"Validation for {result.comparison_id}")
    typer.echo(f"Result: {result.status.value}")
    typer.echo("Checks:")
    for check in result.checks:
        suffix = f" ({check.path})" if check.path else ""
        typer.echo(f"[{check.status.value}] {check.name}: {check.message}{suffix}")
        if check.next_action:
            typer.echo(f"  next: {check.next_action}")


def _comparison_artifact_error(comparison_id: str, exc: Exception) -> None:
    if isinstance(exc, ComparisonInvalidId):
        _fail(
            f"Error: {exc}.\n"
            "Hint: use a saved comparison id such as comparison_YYYYMMDD_HHMMSS_xxxxxx.",
            code=2,
        )
    if isinstance(exc, ComparisonNotFound):
        _fail(
            f"Error: comparison '{comparison_id}' was not found.\n"
            "Hint: run 'labsidecar list-comparisons' to find saved comparison ids.",
            code=3,
        )
    raise exc


def _next_commands_for(record) -> list[str]:
    if record.status == TaskStatus.RUNNING:
        return [
            f"labsidecar status {record.task_id}",
            f"labsidecar logs {record.task_id} --tail 20",
        ]
    if record.status == TaskStatus.FAILED:
        return [
            f"labsidecar logs {record.task_id} --stream stderr --tail 40",
            f"labsidecar summarize {record.task_id}",
            f"labsidecar artifacts {record.task_id}",
        ]
    if record.status == TaskStatus.CANCELLED:
        return [
            f"labsidecar artifacts {record.task_id}",
            f"labsidecar logs {record.task_id} --tail 40",
        ]
    if record.status == TaskStatus.COMPLETED:
        return [
            f"labsidecar summarize {record.task_id}",
            f"labsidecar collect {record.task_id}",
            f"labsidecar figures {record.task_id}",
            f"labsidecar report {record.task_id}",
        ]
    return [
        f"labsidecar status {record.task_id}",
        f"labsidecar logs {record.task_id} --tail 20",
    ]


def _print_task_identity(record) -> None:
    typer.echo(f"Task: {record.task_id}")
    typer.echo(f"Name: {_display_name(record)}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Mode: {record.mode}")
    if record.mode == "ingest":
        typer.echo(f"Source: {record.source_path or '(none)'}")
    else:
        typer.echo(f"Command: {_preview_text(record.command)}")
        typer.echo(f"Working dir: {record.working_dir}")
    typer.echo(f"Artifact dir: {record.paths.task_dir}")


def _print_task_times(record) -> None:
    typer.echo(f"Created: {record.created_at}")
    if record.started_at:
        typer.echo(f"Started: {record.started_at}")
    if record.finished_at:
        typer.echo(f"Finished: {record.finished_at}")
    else:
        typer.echo(f"Updated: {record.updated_at}")


def _print_artifact_summary(record, root: Path) -> None:
    typer.echo(f"Artifacts: {record.artifact_count()}")
    typer.echo(f"Artifact types: {_format_counts(_artifact_type_counts(record))}")
    _print_key_artifacts(record, root)


def _metrics_summary(record, root: Path) -> dict[str, Any]:
    task_path = _task_path(record, root)
    collection_summary_path = task_path / COLLECTION_SUMMARY_RELATIVE_PATH
    scenario_summary_path = task_path / SCENARIO_SUMMARY_RELATIVE_PATH
    metrics_path = task_path / METRICS_RELATIVE_PATH
    data = _json_file(collection_summary_path)
    scenario = _json_file(scenario_summary_path)
    return {
        "summary_path": COLLECTION_SUMMARY_RELATIVE_PATH.as_posix(),
        "summary_exists": collection_summary_path.exists(),
        "scenario_summary_path": SCENARIO_SUMMARY_RELATIVE_PATH.as_posix(),
        "scenario_summary_exists": scenario_summary_path.exists(),
        "scenario": scenario,
        "metrics_path": METRICS_RELATIVE_PATH.as_posix(),
        "metrics_exists": metrics_path.exists(),
        "row_count": data.get("row_count"),
        "detected_fields": data.get("detected_fields") or [],
        "candidate_count": data.get("candidate_count"),
    }


def _figure_summary(record, root: Path) -> dict[str, Any]:
    path = _task_artifact_path(record, root, FIGURE_SUMMARY_RELATIVE_PATH)
    data = _json_file(path)
    return {
        "path": FIGURE_SUMMARY_RELATIVE_PATH.as_posix(),
        "exists": path.exists(),
        "figure_count": data.get("figure_count"),
    }


def _table(rows: list[list[str]]) -> None:
    if not rows:
        return
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row in rows:
        typer.echo("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip())


def _read_metrics_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                return [], []
            rows = [{key: value for key, value in row.items() if key is not None} for row in reader]
            return list(reader.fieldnames), rows
    except OSError as exc:
        raise FileNotFoundError(path) from exc


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _format_number(value: float) -> str:
    return f"{value:.12g}"


def _comparable_numeric_fields(fields: list[str], final_rows: list[dict[str, str]]) -> list[str]:
    comparable: list[str] = []
    for field in fields:
        if field in COMPARISON_METADATA_COLUMNS:
            continue
        values = [row.get(field) for row in final_rows]
        non_empty_values = [value for value in values if str(value or "").strip()]
        if not non_empty_values:
            continue
        if len(non_empty_values) != len(final_rows):
            continue
        if all(_parse_number(value) is not None for value in non_empty_values):
            comparable.append(field)
    return comparable


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Recreate missing files only."),
) -> None:
    """Initialize the current Lab-Sidecar workspace."""
    root = _root()
    try:
        init_workspace(root, force=force)
    except FileExistsError:
        _fail(
            f"Error: {root} is already initialized.\n"
            "Hint: use 'labsidecar init --force' to recreate missing files only.",
            code=2,
        )

    typer.echo("Initialized Lab-Sidecar workspace.")
    typer.echo(f"Root: {root}")
    typer.echo(f"State dir: {state_dir(root).relative_to(root).as_posix()}")
    typer.echo(f"Config: {config_path(root).relative_to(root).as_posix()}")
    typer.echo(f"Index: {sqlite_path(root).relative_to(root).as_posix()}")
    _echo_next("labsidecar run \"<command>\"", "labsidecar ingest <path>", "labsidecar doctor")


@app.command()
def doctor() -> None:
    """Check local Lab-Sidecar prerequisites and workspace state."""
    root = _root()
    has_error = False

    typer.echo("Lab-Sidecar doctor")
    typer.echo(f"Workspace: {root}")

    python_version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info < (3, 11):
        typer.echo(f"[fail] Python: {python_version} (requires 3.11+)")
        has_error = True
    else:
        typer.echo(f"[ok] Python: {python_version}")

    try:
        with tempfile.NamedTemporaryFile(prefix=".lab-sidecar-doctor-", dir=root, delete=True):
            pass
    except OSError as exc:
        typer.echo(f"[fail] Writable workspace: {exc}")
        has_error = True
    else:
        typer.echo("[ok] Writable workspace")

    if config_path(root).is_file() and state_dir(root).is_dir():
        typer.echo(f"[ok] Config: {_relative(config_path(root), root)}")
        typer.echo(f"[ok] Task directory: {_relative(state_dir(root) / 'tasks', root)}")
    else:
        typer.echo("[warn] Workspace config: not initialized")
        typer.echo("Hint: run 'labsidecar init' before creating tasks.")

    if importlib.util.find_spec("mcp") is None:
        typer.echo("[warn] Optional MCP SDK: not installed")
        typer.echo("Hint: install with 'python -m pip install -e \".[mcp]\"' when using MCP.")
    else:
        typer.echo("[ok] Optional MCP SDK: installed")

    if has_error:
        raise typer.Exit(code=1)


@app.command()
def run(
    command: str = typer.Argument(..., help="Command to run."),
    name: str | None = typer.Option(None, "--name", help="Optional task name."),
    cwd: Path | None = typer.Option(None, "--cwd", help="Working directory for the command."),
    background: bool = typer.Option(False, "--background", "--detach", help="Start the task and return immediately."),
) -> None:
    """Run a local command and capture its task artifacts."""
    root = _root()
    service = RunnerService(root)
    try:
        record = service.run(command, name=name, cwd=cwd, background=background)
    except FileNotFoundError:
        _fail("Error: workspace is not initialized.\nHint: run 'labsidecar init' first.", code=2)

    typer.echo(f"Task created: {record.task_id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Command: {record.command}")
    typer.echo(f"Artifacts: {record.paths.task_dir}")
    typer.echo(f"Stdout: {record.paths.stdout}")
    typer.echo(f"Stderr: {record.paths.stderr}")
    if record.status == TaskStatus.COMPLETED:
        _echo_next(
            f"labsidecar collect {record.task_id}",
            f"labsidecar artifacts {record.task_id}",
        )
    elif record.status == TaskStatus.RUNNING:
        _echo_next(
            f"labsidecar status {record.task_id}",
            f"labsidecar logs {record.task_id} --tail 20",
        )
    elif record.status == TaskStatus.FAILED:
        _echo_next(
            f"labsidecar status {record.task_id}",
            f"labsidecar logs {record.task_id} --stream stderr --tail 40",
            f"labsidecar slides {record.task_id}",
        )


@app.command()
def status(task_id: str) -> None:
    """Show a compact task dashboard from manifest.json."""
    root = _root()
    try:
        record = RunnerService(root).refresh(task_id)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )

    _print_task_identity(record)
    typer.echo(f"Exit code: {record.exit_code}")
    _print_task_times(record)
    _print_artifact_summary(record, root)
    failure_summary = _short_failure_summary(record)
    if failure_summary:
        typer.echo("Failure summary:")
        typer.echo(failure_summary)
        typer.echo(f"Diagnostic log: {record.paths.stderr}")
    _echo_next(*_next_commands_for(record))


@app.command()
def cancel(task_id: str) -> None:
    """Cancel a running Lab-Sidecar task."""
    root = _root()
    service = RunnerService(root)
    try:
        record = service.cancel(task_id)
    except FileNotFoundError:
        _fail(f"Error: task '{task_id}' was not found.", code=3)
    except RuntimeError as exc:
        current_status = str(exc)
        _fail(
            f"Error: task '{task_id}' is not running.\nCurrent status: {current_status}",
            code=4,
        )

    typer.echo(f"Cancellation requested: {record.task_id}")
    typer.echo(f"Status: {record.status.value}")


@app.command("list")
def list_tasks(
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum number of task records to show."),
    status_filter: TaskStatus | None = typer.Option(
        None,
        "--status",
        help="Only show tasks with this status: pending, running, completed, failed, or cancelled.",
    ),
) -> None:
    """List recent Lab-Sidecar tasks from manifest files."""
    root = _root()
    task_ids = list_task_ids(root)
    if not task_ids:
        typer.echo("No tasks found.")
        return

    rows: list[list[str]] = [["task_id", "status", "created_at", "finished_at", "updated_at", "artifacts", "name"]]
    service = RunnerService(root)
    for task_id in reversed(task_ids):
        try:
            record = service.refresh(task_id)
        except Exception:
            continue
        if status_filter is not None and record.status != status_filter:
            continue
        rows.append(
            [
                record.task_id,
                record.status.value,
                record.created_at,
                record.finished_at or "(running)",
                _status_updated_at(record),
                str(record.artifact_count()),
                record.name or "",
            ]
        )
        if len(rows) - 1 >= limit:
            break

    if len(rows) == 1:
        typer.echo("No tasks found.")
        return
    _table(rows)


@app.command()
def summarize(task_id: str) -> None:
    """Show a bounded task digest without full logs or full artifact bodies."""
    root = _root()
    try:
        record = RunnerService(root).refresh(task_id)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )

    _print_task_identity(record)
    _print_task_times(record)
    _print_artifact_summary(record, root)

    metrics = _metrics_summary(record, root)
    figures_summary = _figure_summary(record, root)
    typer.echo("Metrics:")
    if metrics["summary_exists"]:
        row_count = metrics["row_count"] if metrics["row_count"] is not None else "(unknown)"
        typer.echo(f"- rows: {row_count}")
        if metrics["detected_fields"]:
            typer.echo(f"- detected fields: {', '.join(str(field) for field in metrics['detected_fields'])}")
        typer.echo(f"- summary: {metrics['summary_path']}")
        if metrics["metrics_exists"]:
            typer.echo(f"- normalized table: {metrics['metrics_path']}")
        else:
            typer.echo("- normalized table: (not generated)")
    else:
        typer.echo("- collection summary: (not generated)")
        typer.echo("- normalized table: (not generated)")
    typer.echo("Scenario:")
    if metrics["scenario_summary_exists"]:
        scenario = metrics["scenario"]
        primary_metric = scenario.get("primary_metric") if isinstance(scenario.get("primary_metric"), dict) else {}
        best_rows = scenario.get("best_rows") if isinstance(scenario.get("best_rows"), list) else []
        seed_aggregates = scenario.get("seed_aggregates") if isinstance(scenario.get("seed_aggregates"), dict) else {}
        typer.echo(f"- type: {scenario.get('scenario_type') or '(unknown)'}")
        typer.echo(f"- primary metric: {primary_metric.get('name') or '(none)'} ({primary_metric.get('direction') or 'unknown'})")
        typer.echo(f"- best rows: {len(best_rows)}")
        typer.echo(f"- seed aggregates: {'present' if seed_aggregates.get('present') else 'not available'}")
        typer.echo(f"- summary: {metrics['scenario_summary_path']}")
    else:
        typer.echo("- scenario summary: (not generated)")

    typer.echo("Figures:")
    if figures_summary["exists"]:
        figure_count = (
            figures_summary["figure_count"]
            if figures_summary["figure_count"] is not None
            else "(unknown)"
        )
        typer.echo(f"- generated figures: {figure_count}")
        typer.echo(f"- summary: {figures_summary['path']}")
    else:
        typer.echo("- summary: (not generated)")

    report_path = _task_artifact_path(record, root, REPORT_RELATIVE_PATH)
    slides_path = _task_artifact_path(record, root, SLIDES_RELATIVE_PATH)
    typer.echo("Report:")
    typer.echo(f"- {REPORT_RELATIVE_PATH.as_posix()}" if report_path.exists() else "- (not generated)")
    typer.echo("Slides:")
    typer.echo(f"- {SLIDES_RELATIVE_PATH.as_posix()}" if slides_path.exists() else "- (not generated)")

    failure_summary = _short_failure_summary(record)
    if failure_summary:
        typer.echo("Failure summary:")
        typer.echo(failure_summary)

    _echo_next(*_next_commands_for(record))


@app.command()
def validate(
    task_id: str = typer.Argument(..., help="Task id to validate."),
    require: list[ValidationRequirement] | None = typer.Option(
        None,
        "--require",
        help="Require an artifact group: metrics, figures, report, slides, or package-ready.",
    ),
) -> None:
    """Check task artifact health without generating new artifacts."""
    root = _root()
    try:
        result = TaskValidationService(root).validate(task_id, requirements=require)
    except ValidationTaskNotFound:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )

    _print_validation_result(result)
    if result.has_failures:
        raise typer.Exit(code=5)


@app.command("package")
def package_task(
    task_id: str = typer.Argument(..., help="Task id to package."),
    output: Path = typer.Option(..., "--output", "-o", help="Destination package directory."),
) -> None:
    """Create a shareable single-task result or diagnostic package."""
    root = _root()
    try:
        record = RunnerService(root).refresh(task_id)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: run 'labsidecar list' to find available task ids.",
            code=3,
        )

    try:
        result = export_task_package(root, record, output)
    except PackageOutputError as exc:
        _fail(
            f"Error: package output path is not usable.\nReason: {exc}",
            code=2,
        )
    except PackageExportError as exc:
        _fail(
            f"Error: package could not be created for task '{task_id}'.\nReason: {exc}",
            code=1,
        )

    typer.echo(f"Package created: {result.path}")
    typer.echo(f"Type: {result.package_type}")
    typer.echo(f"Included files: {result.included_count}")
    typer.echo(f"Omitted by default: {result.omitted_count}")
    typer.echo(f"Unavailable optional files: {result.unavailable_count}")
    typer.echo(f"Digest: {result.digest_path}")


@app.command("package-verify")
def package_verify(
    package_dir: Path = typer.Argument(..., help="Package directory to verify."),
) -> None:
    """Verify a Lab-Sidecar package against its artifact index and digest."""
    try:
        result = verify_task_package(package_dir)
    except PackageVerifyError as exc:
        _fail(f"Error: package could not be verified.\nReason: {exc}", code=2)

    if result.ok:
        typer.echo(f"Package verified: {result.path}")
        typer.echo(f"Checked files: {result.checked_count}")
        return

    typer.echo(f"Package verification failed: {result.path}")
    for error in result.errors:
        typer.echo(f"[fail] {error}")
    raise typer.Exit(code=5)


@app.command()
def compare(
    task_ids: list[str] = typer.Argument(..., help="Two to five task ids to compare."),
    save: bool = typer.Option(False, "--save", help="Write a durable local comparison artifact record."),
    name: str | None = typer.Option(None, "--name", help="Optional saved comparison name."),
    figures: bool = typer.Option(False, "--figures", help="Generate deterministic comparison figures when saving."),
    report: bool = typer.Option(False, "--report", help="Generate a deterministic comparison report when saving."),
) -> None:
    """Compare final rows for shared numeric metrics across 2-5 tasks."""
    root = _root()
    if len(task_ids) < 2:
        _fail("Error: compare requires at least 2 task ids.", code=2)
    if len(task_ids) > 5:
        _fail("Error: compare supports at most 5 task ids.", code=2)
    if len(set(task_ids)) != len(task_ids):
        _fail("Error: compare requires unique task ids; duplicate task ids are not allowed.", code=2)
    if (figures or report or name) and not save:
        _fail("Error: --figures, --report, and --name require --save.", code=2)
    if save:
        service = ComparisonService(root)
        try:
            result = service.create(
                task_ids,
                name=name,
                generate_figures=figures,
                generate_report=report,
            )
        except ComparisonDuplicateTaskIds as exc:
            _fail(f"Error: {exc}.", code=2)
        except ComparisonTaskNotFound as exc:
            _fail(f"Error: {exc}.\nHint: run 'labsidecar list' to find available task ids.", code=3)
        except ComparisonMetricsMissing as exc:
            _fail(
                f"Error: {exc}.\nHint: run 'labsidecar collect <task_id>' before saving a comparison.",
                code=5,
            )
        except NoCommonComparisonMetrics:
            _fail(
                "Error: no common numeric metric fields were found across the selected tasks.\n"
                "Hint: compare tasks after collecting metrics with shared numeric columns.",
                code=5,
            )
        except ComparisonOutputError as exc:
            _fail(f"Error: comparison artifacts could not be written.\nReason: {exc}", code=1)
        typer.echo(f"Comparison created: {result.manifest.comparison_id}")
        typer.echo(f"Artifacts: {result.comparison_dir.relative_to(root).as_posix()}")
        typer.echo(f"Summary: {result.summary_path.relative_to(root).as_posix()}")
        typer.echo(f"Table: {result.table_csv_path.relative_to(root).as_posix()}")
        if result.figure_summary_path is not None:
            typer.echo(f"Figures: {result.figure_summary_path.relative_to(root).as_posix()}")
        if result.report_path is not None:
            typer.echo(f"Report: {result.report_path.relative_to(root).as_posix()}")
        typer.echo(f"Traceability: {result.traceability_path.relative_to(root).as_posix()}")
        _echo_next(
            f"labsidecar validate-comparison {result.manifest.comparison_id}",
            f"labsidecar package-comparison {result.manifest.comparison_id} --output lab-sidecar-comparison-{result.manifest.comparison_id}",
            "labsidecar package-verify <package_dir>",
        )
        return

    records = []
    metrics_by_task: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    missing_metrics: list[str] = []
    for task_id in task_ids:
        try:
            record = RunnerService(root).refresh(task_id)
        except FileNotFoundError:
            _fail(
                f"Error: task '{task_id}' was not found.\n"
                "Hint: run 'labsidecar list' to find available task ids.",
                code=3,
            )
        records.append(record)
        metrics_path = _task_artifact_path(record, root, METRICS_RELATIVE_PATH)
        if not metrics_path.exists():
            missing_metrics.append(record.task_id)
            continue
        fields, rows = _read_metrics_rows(metrics_path)
        if not rows:
            missing_metrics.append(record.task_id)
            continue
        metrics_by_task[record.task_id] = (fields, rows)

    if missing_metrics:
        _fail(
            "Error: metrics are missing for task(s): "
            + ", ".join(missing_metrics)
            + "\nHint: run 'labsidecar collect <task_id>' before comparing.",
            code=5,
        )

    common_fields: set[str] | None = None
    all_fields: dict[str, set[str]] = {}
    final_rows: list[dict[str, str]] = []
    for record in records:
        fields, rows = metrics_by_task[record.task_id]
        field_set = set(fields)
        all_fields[record.task_id] = field_set
        common_fields = field_set if common_fields is None else common_fields & field_set
        final_rows.append(rows[-1])

    ordered_common_fields = [
        field
        for field in metrics_by_task[records[0].task_id][0]
        if common_fields is not None and field in common_fields
    ]
    comparable_fields = _comparable_numeric_fields(ordered_common_fields, final_rows)
    skipped_common_fields = [
        field
        for field in ordered_common_fields
        if field not in comparable_fields and field not in COMPARISON_METADATA_COLUMNS
    ]
    skipped_by_task = {}
    for record in records:
        task_fields = all_fields[record.task_id]
        skipped_by_task[record.task_id] = sorted(
            field
            for field in task_fields
            if common_fields is not None and field not in common_fields
        )

    if not comparable_fields:
        _fail(
            "Error: no common numeric metric fields were found across the selected tasks.\n"
            "Hint: compare tasks after collecting metrics with shared numeric columns.",
            code=5,
        )

    typer.echo(f"Compared tasks: {len(records)}")
    typer.echo(f"Source: {METRICS_RELATIVE_PATH.as_posix()}")
    typer.echo(f"Common numeric fields: {', '.join(comparable_fields)}")
    if skipped_common_fields:
        typer.echo(f"Skipped common non-numeric fields: {', '.join(skipped_common_fields)}")
    skipped_messages = [
        f"{task_id}: {', '.join(fields)}"
        for task_id, fields in skipped_by_task.items()
        if fields
    ]
    if skipped_messages:
        typer.echo("Skipped task-specific fields:")
        for message in skipped_messages:
            typer.echo(f"- {message}")

    rows = [["task_id", "status", "metric", "value", "source"]]
    for record, final_row in zip(records, final_rows, strict=True):
        for field in comparable_fields:
            parsed = _parse_number(final_row.get(field))
            if parsed is None:
                continue
            rows.append(
                [
                    record.task_id,
                    record.status.value,
                    field,
                    _format_number(parsed),
                    METRICS_RELATIVE_PATH.as_posix(),
                ]
            )
    _table(rows)


@app.command("validate-comparison")
def validate_comparison(
    comparison_id: str = typer.Argument(..., help="Saved comparison id to validate."),
    require: list[ComparisonValidationRequirement] | None = typer.Option(
        None,
        "--require",
        help="Require an artifact group: figures, report, or package-ready.",
    ),
) -> None:
    """Check saved comparison artifact health without generating artifacts."""
    root = _root()
    try:
        result = ComparisonValidationService(root).validate(comparison_id, requirements=require)
    except ComparisonInvalidId as exc:
        _fail(f"Error: {exc}.\nHint: use a saved comparison id such as comparison_YYYYMMDD_HHMMSS_xxxxxx.", code=2)
    except ComparisonNotFound:
        _fail(
            f"Error: comparison '{comparison_id}' was not found.\n"
            "Hint: saved comparisons live under .lab-sidecar/comparisons/.",
            code=3,
        )

    _print_comparison_validation_result(result)
    if result.has_failures:
        raise typer.Exit(code=5)


@app.command("package-comparison")
def package_comparison(
    comparison_id: str = typer.Argument(..., help="Saved comparison id to package."),
    output: Path = typer.Option(..., "--output", "-o", help="Destination package directory."),
) -> None:
    """Create a shareable saved-comparison package."""
    root = _root()
    service = ComparisonService(root)
    try:
        manifest = service.load(comparison_id)
    except ComparisonInvalidId as exc:
        _fail(f"Error: {exc}.\nHint: use a saved comparison id such as comparison_YYYYMMDD_HHMMSS_xxxxxx.", code=2)
    except ComparisonNotFound:
        _fail(
            f"Error: comparison '{comparison_id}' was not found.\n"
            "Hint: saved comparisons live under .lab-sidecar/comparisons/.",
            code=3,
        )

    try:
        result = export_comparison_package(root, manifest, output)
    except PackageOutputError as exc:
        _fail(
            f"Error: package output path is not usable.\nReason: {exc}",
            code=2,
        )
    except ComparisonPackageExportError as exc:
        _fail(
            f"Error: package could not be created for comparison '{comparison_id}'.\nReason: {exc}",
            code=1,
        )

    typer.echo(f"Package created: {result.path}")
    typer.echo(f"Type: {result.package_type}")
    typer.echo(f"Included files: {result.included_count}")
    typer.echo(f"Omitted by default: {result.omitted_count}")
    typer.echo(f"Unavailable optional files: {result.unavailable_count}")
    typer.echo(f"Digest: {result.digest_path}")


@app.command("list-comparisons")
def list_comparisons(
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum number of saved comparison records to show."),
) -> None:
    """List recent saved comparison records without reading artifact bodies."""
    root = _root()
    comparison_ids = list_comparison_ids(root)
    if not comparison_ids:
        typer.echo("No comparisons found.")
        return

    rows: list[list[str]] = [
        ["comparison_id", "name", "created_at", "source_tasks", "artifacts", "figures", "report"]
    ]
    warnings: list[str] = []
    for comparison_id in comparison_ids[:limit]:
        try:
            manifest = load_comparison_manifest(root, comparison_id)
            presence = comparison_artifact_presence(root, comparison_id)
        except Exception as exc:
            warnings.append(
                f"skipped damaged comparison manifest {comparison_id}: {_preview_text(str(exc), 180)}"
            )
            continue
        rows.append(
            [
                manifest.comparison_id,
                _preview_text(manifest.name or "", 120),
                manifest.created_at,
                _preview_text(", ".join(manifest.task_ids), 160),
                str(presence.artifact_count),
                str(presence.figure_count),
                "yes" if presence.report_present else "no",
            ]
        )
    if len(rows) == 1:
        typer.echo("No comparisons found.")
    else:
        _table(rows)
    for warning in warnings[:5]:
        typer.echo(f"Warning: {warning}", err=True)
    if len(warnings) > 5:
        typer.echo(f"Warning: omitted {len(warnings) - 5} additional damaged comparison manifest(s).", err=True)


@app.command("open-comparison")
def open_comparison(comparison_id: str) -> None:
    """Print the saved comparison artifact directory path."""
    root = _root()
    try:
        path = comparison_artifact_dir(root, comparison_id)
    except (ComparisonInvalidId, ComparisonNotFound) as exc:
        _comparison_artifact_error(comparison_id, exc)
    typer.echo(path)


@app.command("comparison-artifacts")
def comparison_artifacts(comparison_id: str) -> None:
    """List saved comparison artifacts without printing artifact bodies."""
    root = _root()
    try:
        presence = comparison_artifact_presence(root, comparison_id)
    except (ComparisonInvalidId, ComparisonNotFound) as exc:
        _comparison_artifact_error(comparison_id, exc)

    typer.echo(f"Artifacts for {presence.comparison_id}")
    if not presence.paths:
        typer.echo("(none)")
        return
    for path in presence.paths:
        typer.echo(path)


@app.command("open")
def open_task(task_id: str) -> None:
    """Print the task artifact directory path."""
    root = _root()
    try:
        record = load_task(root, task_id)
    except FileNotFoundError:
        _fail(f"Error: task '{task_id}' was not found.", code=3)

    task_path = resolve_workspace_path(record.paths.task_dir, root)
    typer.echo(task_path)


@app.command()
def ingest(
    path: Path = typer.Argument(..., help="Existing result directory or file to register."),
    name: str | None = typer.Option(None, "--name", help="Optional task name."),
) -> None:
    """Register existing results without executing a command."""
    root = _root()
    service = RunnerService(root)
    try:
        record = service.ingest_source(path, name=name)
    except FileNotFoundError:
        _fail("Error: workspace is not initialized.\nHint: run 'labsidecar init' first.", code=2)
    except ValueError:
        _fail(f"Error: path '{path}' does not exist.", code=2)

    typer.echo(f"Imported as task: {record.task_id}")
    typer.echo(f"Source: {record.source_path}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Artifacts: {record.paths.task_dir}")
    _echo_next(
        f"labsidecar collect {record.task_id}",
        f"labsidecar artifacts {record.task_id}",
    )


@app.command()
def collect(
    task_id: str = typer.Argument(..., help="Task id to collect metrics from."),
    config: Path | None = typer.Option(None, "--config", help="Optional metrics mapping YAML path."),
) -> None:
    """Collect CSV/JSON metrics into normalized task artifacts."""
    root = _root()
    service = MetricsCollectionService(root)
    try:
        result = service.collect(task_id, config_path=config)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )
    except MetricsConfigLoadError as exc:
        _fail(
            f"Error: metrics config is invalid.\nReason: {exc}",
            code=2,
        )
    except NoMetricsFoundError as exc:
        candidate_count = int(exc.summary.get("candidate_count", 0))
        warnings = exc.summary.get("warnings")
        warning_text = ""
        if isinstance(warnings, list) and warnings:
            warning_text = "\nDiagnostics warnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        summary_path = ".lab-sidecar/tasks/<task_id>/metrics/collection-summary.json"
        if candidate_count == 0:
            _fail(
                f"Error: no CSV/JSON metric candidates were found for task '{task_id}'.\n"
                "Hint: ingest a directory or file containing CSV/JSON results, or run a command that writes CSV/JSON output.\n"
                f"Diagnostics: {summary_path}"
                f"{warning_text}",
                code=5,
            )
        _fail(
            f"Error: CSV/JSON candidates were found, but no metrics could be collected for task '{task_id}'.\n"
            "Hint: check parse warnings, empty files, and metric column names in the collection summary.\n"
            f"Diagnostics: {summary_path}"
            f"{warning_text}",
            code=5,
        )

    typer.echo(f"Collected metrics for {result.record.task_id}")
    if result.detected_fields:
        typer.echo(f"Detected fields: {', '.join(result.detected_fields)}")
    else:
        typer.echo("Detected fields: (none)")
    typer.echo(f"Rows: {len(result.rows)}")
    typer.echo(f"Wrote: {result.csv_path.relative_to(root).as_posix()}")
    typer.echo(f"Wrote: {result.json_path.relative_to(root).as_posix()}")
    typer.echo(f"Summary: {result.summary_path.relative_to(root).as_posix()}")
    if result.scenario_summary_path is not None:
        typer.echo(f"Scenario summary: {result.scenario_summary_path.relative_to(root).as_posix()}")
    _echo_next(
        f"labsidecar figures {result.record.task_id}",
        f"labsidecar report {result.record.task_id}",
    )


@app.command()
def figures(
    task_id: str = typer.Argument(..., help="Task id to generate figures for."),
    spec: Path | None = typer.Option(None, "--spec", help="Optional figure spec YAML path."),
    fallback: FallbackMode = typer.Option("off", "--fallback", help="off or bounded."),
    fallback_worker: FallbackWorkerMode = typer.Option(
        "unavailable",
        "--fallback-worker",
        help="Internal Alpha4 fallback worker mode.",
        hidden=True,
    ),
) -> None:
    """Generate static PNG/SVG figures from normalized metrics."""
    root = _root()
    service = FigureGenerationService(root)
    try:
        result = service.generate(task_id, spec_path=spec, fallback_mode=fallback, fallback_worker_mode=fallback_worker)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )
    except MetricsNotReadyError as exc:
        _fail(
            f"Error: metrics are not ready for task '{task_id}'.\n"
            f"Reason: {exc}\n"
            f"Hint: run 'labsidecar collect {task_id}' first.",
            code=5,
        )
    except FigureSpecLoadError as exc:
        _fail(
            f"Error: figure spec is invalid.\nReason: {exc}",
            code=2,
        )
    except NoFiguresGeneratedError as exc:
        messages = [*exc.errors, *exc.warnings]
        warning_text = "\n".join(f"- {message}" for message in messages) or "- no supported chart pattern"
        diagnostics_text = ""
        if exc.unsupported_chart_diagnostics:
            items = []
            for item in exc.unsupported_chart_diagnostics:
                intent = item.get("requested_chart_intent") if isinstance(item, dict) else None
                chart_type = intent.get("chart_type") if isinstance(intent, dict) else None
                x_field = intent.get("x") if isinstance(intent, dict) else None
                y_field = intent.get("y") if isinstance(intent, dict) else None
                reason = item.get("reason") if isinstance(item, dict) else None
                items.append(
                    f"- chart_type={chart_type or '(unknown)'} x={x_field or '(unknown)'} y={y_field or '(unknown)'}: {reason or 'unsupported chart intent'}"
                )
            diagnostics_text = "\nUnsupported chart diagnostics:\n" + "\n".join(items)
        fallback_text = ""
        if exc.fallback:
            fallback_lines = [f"- mode: {exc.fallback.get('mode')}", f"- status: {exc.fallback.get('status')}"]
            if exc.fallback.get("request_path"):
                fallback_lines.append(f"- request: {exc.fallback['request_path']}")
            if exc.fallback.get("validator_result_path"):
                fallback_lines.append(f"- validator: {exc.fallback['validator_result_path']}")
            fallback_text = "\nFallback:\n" + "\n".join(fallback_lines)
        summary_text = ""
        if exc.summary_path is not None:
            summary_text = f"\nSummary: {exc.summary_path.relative_to(root).as_posix()}"
        _fail(
            f"Error: no supported figures could be generated for task '{task_id}'.\n"
            f"Reason: {exc}\n"
            f"Warnings:\n{warning_text}"
            f"{diagnostics_text}"
            f"{fallback_text}"
            f"{summary_text}",
            code=5,
        )

    typer.echo(f"Generated {len(result.generated)} figure(s) for {result.record.task_id}")
    for item in result.generated:
        typer.echo(f"- {item.png_path.relative_to(root).as_posix()}")
        typer.echo(f"- {item.svg_path.relative_to(root).as_posix()}")
    typer.echo(f"Spec: {result.spec_path.relative_to(root).as_posix()}")
    typer.echo(f"Summary: {result.summary_path.relative_to(root).as_posix()}")
    typer.echo(f"Fallback: mode={result.fallback['mode']} status={result.fallback['status']}")
    if result.warnings:
        typer.echo("Warnings:")
        for warning in result.warnings:
            typer.echo(f"- {warning}")
    _echo_next(
        f"labsidecar report {result.record.task_id}",
        f"labsidecar slides {result.record.task_id}",
    )


@app.command()
def report(
    task_id: str = typer.Argument(..., help="Task id to generate a Markdown report for."),
    template: str = typer.Option("zh-lab", "--template", help="zh-lab, zh-summary, or en-paper."),
) -> None:
    """Generate a deterministic Markdown report fragment from task artifacts."""
    root = _root()
    service = ReportGenerationService(root)
    try:
        result = service.generate(task_id, template=template)
    except InvalidReportTemplateError as exc:
        _fail(f"Error: report template is invalid.\nReason: {exc}", code=2)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )
    except ReportMetricsRequiredError:
        _fail(
            f"Error: report generation requires collected metrics for task '{task_id}'.\n"
            f"Hint: run 'labsidecar collect {task_id}' first.",
            code=5,
        )
    except ReportWriteError as exc:
        _fail(f"Error: report could not be written.\nReason: {exc}", code=1)

    typer.echo("Report fragment created:")
    typer.echo(result.report_path.relative_to(root).as_posix())
    typer.echo(f"Summary: {result.summary_path.relative_to(root).as_posix()}")
    typer.echo(f"Template: {result.template}")
    _echo_next(f"labsidecar slides {result.record.task_id}")


@app.command()
def slides(
    task_id: str = typer.Argument(..., help="Task id to generate a static PPTX draft for."),
    template: str = typer.Option("zh-summary", "--template", help="zh-summary, en-summary, or zh-project."),
) -> None:
    """Generate a static editable PPTX draft from task artifacts."""
    root = _root()
    service = SlidesGenerationService(root)
    try:
        result = service.generate(task_id, template=template)
    except InvalidSlidesTemplateError as exc:
        _fail(f"Error: slides template is invalid.\nReason: {exc}", code=2)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )
    except SlidesArtifactsRequiredError:
        _fail(
            f"Error: slides generation requires metrics, figures, or report artifacts for task '{task_id}'.\n"
            f"Hint: run 'labsidecar collect {task_id}', 'labsidecar figures {task_id}', or 'labsidecar report {task_id}' first.",
            code=5,
        )
    except SlidesWriteError as exc:
        _fail(f"Error: slides could not be written.\nReason: {exc}", code=1)

    typer.echo("Presentation draft created:")
    typer.echo(result.pptx_path.relative_to(root).as_posix())
    typer.echo(f"Summary: {result.summary_path.relative_to(root).as_posix()}")
    typer.echo(f"Template: {result.template}")
    typer.echo(f"Slides: {result.summary['slide_count']}")
    _echo_next(
        f"labsidecar artifacts {result.record.task_id}",
        f"labsidecar open {result.record.task_id}",
    )


@app.command()
def logs(
    task_id: str,
    tail: int = typer.Option(100, "--tail", min=0, help="Number of log lines to show."),
    stream: LogStream = typer.Option(LogStream.BOTH, "--stream", help="stdout, stderr, or both."),
) -> None:
    """Print stdout and/or stderr log tails."""
    root = _root()
    try:
        record = load_task(root, task_id)
    except FileNotFoundError:
        _fail(f"Error: task '{task_id}' was not found.", code=3)

    selected = []
    if stream in {LogStream.STDOUT, LogStream.BOTH}:
        selected.append(("stdout", resolve_workspace_path(record.paths.stdout, root)))
    if stream in {LogStream.STDERR, LogStream.BOTH}:
        selected.append(("stderr", resolve_workspace_path(record.paths.stderr, root)))

    for index, (label, path) in enumerate(selected):
        if index:
            typer.echo("")
        typer.echo(f"== {label} (last {tail} lines) ==")
        try:
            lines = tail_lines(path, tail)
        except FileNotFoundError:
            _fail(
                f"Error: log files are not available for task '{task_id}'.\n"
                f"Reason: {path.name} is missing.",
                code=5,
            )
        if lines:
            typer.echo("\n".join(lines))
        else:
            typer.echo("(empty)")


@app.command()
def artifacts(task_id: str) -> None:
    """List artifacts recorded in manifest.json."""
    root = _root()
    try:
        record = load_task(root, task_id)
    except FileNotFoundError:
        _fail(f"Error: no manifest was found for task '{task_id}'.", code=3)

    typer.echo(f"Artifacts for {record.task_id}")
    if not record.artifacts:
        typer.echo("(none)")
        return
    for artifact in record.artifacts:
        typer.echo(f"[{artifact.type}] {artifact.path} - {artifact.description}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
