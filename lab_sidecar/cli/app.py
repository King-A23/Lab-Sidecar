from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer

from lab_sidecar.core.config import init_workspace
from lab_sidecar.core.manifest import load_task
from lab_sidecar.core.paths import config_path, resolve_workspace_path, sqlite_path, state_dir
from lab_sidecar.core.models import TaskStatus
from lab_sidecar.collectors.service import MetricsCollectionService, MetricsConfigLoadError, NoMetricsFoundError
from lab_sidecar.figures.service import (
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


app = typer.Typer(help="Local-first experiment runner and artifact sidecar.")


class LogStream(StrEnum):
    STDOUT = "stdout"
    STDERR = "stderr"
    BOTH = "both"


def _root() -> Path:
    return Path.cwd().resolve()


def _fail(message: str, code: int = 1) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(code=code)


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
    typer.echo(f"Logs: {record.paths.stdout}")
    typer.echo(f"Use 'labsidecar status {record.task_id}' to check progress.")


@app.command()
def status(task_id: str) -> None:
    """Show task status from manifest.json."""
    root = _root()
    try:
        record = RunnerService(root).refresh(task_id)
    except FileNotFoundError:
        _fail(
            f"Error: task '{task_id}' was not found.\n"
            "Hint: check whether the task directory still exists under .lab-sidecar/tasks/.",
            code=3,
        )

    typer.echo(f"Task: {record.task_id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Exit code: {record.exit_code}")
    typer.echo(f"Created: {record.created_at}")
    if record.started_at:
        typer.echo(f"Started: {record.started_at}")
    if record.finished_at:
        typer.echo(f"Finished: {record.finished_at}")
    else:
        typer.echo(f"Updated: {record.updated_at}")
    typer.echo(f"Artifacts: {record.artifact_count()}")
    if record.failure_summary:
        typer.echo("Failure summary:")
        typer.echo(record.failure_summary)


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
) -> None:
    """List recent Lab-Sidecar tasks from manifest files."""
    root = _root()
    task_ids = list_task_ids(root)
    if not task_ids:
        typer.echo("No tasks found.")
        return

    for task_id in reversed(task_ids[-limit:]):
        try:
            record = RunnerService(root).refresh(task_id)
        except FileNotFoundError:
            continue
        label = f" - {record.name}" if record.name else ""
        typer.echo(f"{record.task_id}\t{record.status.value}\t{record.updated_at}{label}")


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
    typer.echo(f"Next step: run 'labsidecar artifacts {record.task_id}'")


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


@app.command()
def figures(
    task_id: str = typer.Argument(..., help="Task id to generate figures for."),
    spec: Path | None = typer.Option(None, "--spec", help="Optional figure spec YAML path."),
) -> None:
    """Generate static PNG/SVG figures from normalized metrics."""
    root = _root()
    service = FigureGenerationService(root)
    try:
        result = service.generate(task_id, spec_path=spec)
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
        _fail(
            f"Error: no supported figures could be generated for task '{task_id}'.\n"
            f"Reason: {exc}\n"
            f"Warnings:\n{warning_text}",
            code=5,
        )

    typer.echo(f"Generated {len(result.generated)} figure(s) for {result.record.task_id}")
    for item in result.generated:
        typer.echo(f"- {item.png_path.relative_to(root).as_posix()}")
        typer.echo(f"- {item.svg_path.relative_to(root).as_posix()}")
    typer.echo(f"Spec: {result.spec_path.relative_to(root).as_posix()}")
    typer.echo(f"Summary: {result.summary_path.relative_to(root).as_posix()}")
    if result.warnings:
        typer.echo("Warnings:")
        for warning in result.warnings:
            typer.echo(f"- {warning}")


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
