from __future__ import annotations

import json
import os
import platform
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from lab_sidecar.core.config import load_config
from lab_sidecar.core.manifest import load_task, manifest_path, write_manifest
from lab_sidecar.core.models import TaskPaths, TaskRecord, TaskStatus
from lab_sidecar.core.paths import resolve_workspace_path, task_dir, tasks_dir, to_manifest_path
from lab_sidecar.core.provenance import dependency_snapshot, git_snapshot, python_executable
from lab_sidecar.runner.process import (
    command_popen_kwargs,
    current_python_command,
    probe_process,
    terminate_process_tree,
    worker_popen_kwargs,
)
from lab_sidecar.runner.spec import RunSpec
from lab_sidecar.storage.artifact_store import (
    build_source_refs,
    default_task_artifacts,
    ingest_task_artifacts,
    write_source_refs,
)
from lab_sidecar.storage.sqlite_index import upsert_task


SHELL_RUN_MODE = "shell"
ARGV_RUN_MODE = "argv"


def _coerce_run_spec(command: str | RunSpec) -> RunSpec:
    return RunSpec.from_jsonable(command)


def load_run_spec_json(payload: str) -> RunSpec:
    return RunSpec.from_json(payload)


def dump_run_spec_json(run_spec: str | RunSpec) -> str:
    spec = _coerce_run_spec(run_spec)
    return spec.to_json()


def _run_spec_mode(run_spec: RunSpec) -> str:
    mode = run_spec.mode
    if mode not in {SHELL_RUN_MODE, ARGV_RUN_MODE}:
        raise ValueError(f"unsupported run spec mode: {mode}")
    return mode


def _run_spec_command_text(run_spec: RunSpec) -> str:
    return run_spec.display_command()


def _run_spec_argv(run_spec: RunSpec) -> list[str]:
    return list(run_spec.argv or [])


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def generate_task_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(3)
    return f"task_{stamp}_{suffix}"


def tail_lines(path: Path, count: int) -> list[str]:
    if count <= 0:
        return []
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:]


def summarize_failure(stderr_path: Path, exit_code: int | None) -> str:
    lines = [line for line in stderr_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    tail = lines[-8:]
    if tail:
        return "\n".join(tail)
    return f"Command exited with code {exit_code}"


class RunnerService:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def run(
        self,
        command: str | RunSpec,
        name: str | None = None,
        cwd: Path | None = None,
        background: bool = False,
    ) -> TaskRecord:
        load_config(self.root)
        run_spec = _coerce_run_spec(command)
        record, task_path, run_cwd = self._create_task(run_spec, name, cwd)

        if background:
            return self._start_background_worker(record, task_path, run_cwd, run_spec)

        execute_task(self.root, record.task_id, run_spec, run_cwd)
        return load_task(self.root, record.task_id)

    def refresh(self, task_id: str) -> TaskRecord:
        record = load_task(self.root, task_id)
        if record.status != TaskStatus.RUNNING:
            upsert_task(self.root, record)
            return record

        if record.pid:
            probe = probe_process(record.pid)
            if probe.is_running:
                upsert_task(self.root, record)
                return record
            if probe.exit_code is not None:
                return finalize_task(
                    self.root,
                    record.task_id,
                    probe.exit_code,
                    clear_worker=True,
                )

        if record.worker_pid:
            probe = probe_process(record.worker_pid)
            if probe.is_running:
                upsert_task(self.root, record)
                return record
            refreshed = load_task(self.root, task_id)
            if refreshed.status != TaskStatus.RUNNING:
                upsert_task(self.root, refreshed)
                return refreshed

        return mark_stale_running_task_failed(self.root, task_id)

    def cancel(self, task_id: str) -> TaskRecord:
        record = self.refresh(task_id)
        if record.status != TaskStatus.RUNNING:
            raise RuntimeError(record.status.value)

        stderr_path = resolve_workspace_path(record.paths.stderr, self.root)
        with stderr_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\nLab-Sidecar: cancellation requested at {now_iso()}.\n")

        finished = now_iso()
        target_pid = record.pid or record.worker_pid
        record.status = TaskStatus.CANCELLED
        record.exit_code = None
        record.finished_at = finished
        record.updated_at = finished
        record.pid = None
        record.worker_pid = None
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)

        if target_pid:
            terminate_process_tree(target_pid)

        return record

    def ingest_source(self, source: Path, name: str | None = None) -> TaskRecord:
        load_config(self.root)
        source_path = source.resolve()
        if not source_path.exists():
            raise ValueError(f"path '{source}' does not exist")

        task_id = generate_task_id()
        task_path = task_dir(self.root, task_id)
        task_path.mkdir(parents=True, exist_ok=False)
        for child in ["raw", "metrics", "figures", "reports", "reproduce"]:
            (task_path / child).mkdir(parents=True, exist_ok=True)

        (task_path / "stdout.log").touch()
        (task_path / "stderr.log").touch()
        source_refs_path = task_path / "raw" / "source_refs.json"
        write_source_refs(source_refs_path, build_source_refs(source_path, self.root))

        created = now_iso()
        record = TaskRecord(
            task_id=task_id,
            mode="ingest",
            status=TaskStatus.COMPLETED,
            created_at=created,
            updated_at=created,
            working_dir=".",
            command=None,
            source_path=to_manifest_path(source_path, self.root),
            exit_code=0,
            paths=TaskPaths(
                task_dir=to_manifest_path(task_path, self.root),
                stdout=to_manifest_path(task_path / "stdout.log", self.root),
                stderr=to_manifest_path(task_path / "stderr.log", self.root),
            ),
            artifacts=ingest_task_artifacts(task_path, self.root),
            name=name,
            started_at=created,
            finished_at=created,
        )
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)
        return record

    def _create_task(
        self,
        run_spec: RunSpec,
        name: str | None,
        cwd: Path | None,
    ) -> tuple[TaskRecord, Path, Path]:
        task_id = generate_task_id()
        run_cwd = (cwd or self.root).resolve()
        task_path = task_dir(self.root, task_id)
        task_path.mkdir(parents=True, exist_ok=False)
        for child in ["raw", "metrics", "figures", "reports", "reproduce"]:
            (task_path / child).mkdir(parents=True, exist_ok=True)

        stdout_path = task_path / "stdout.log"
        stderr_path = task_path / "stderr.log"
        stdout_path.touch()
        stderr_path.touch()

        record = self._initial_record(task_id, task_path, run_cwd, run_spec, name)
        write_manifest(manifest_path(self.root, task_id), record)
        upsert_task(self.root, record)

        self._write_reproduce_files(task_path, run_spec, run_cwd)
        return record, task_path, run_cwd

    def _start_background_worker(self, record: TaskRecord, task_path: Path, run_cwd: Path, run_spec: RunSpec) -> TaskRecord:
        started = now_iso()
        record.status = TaskStatus.RUNNING
        record.started_at = started
        record.updated_at = started
        write_manifest(manifest_path(self.root, record.task_id), record)
        upsert_task(self.root, record)

        try:
            worker_log = task_path / "worker.log"
            worker_err = task_path / "worker.err.log"
            with worker_log.open("ab") as worker_stdout, worker_err.open("ab") as worker_stderr:
                process = subprocess.Popen(
                    [
                        *current_python_command(),
                        "-m",
                        "lab_sidecar.runner.worker",
                        "--root",
                        str(self.root),
                        "--task-id",
                        record.task_id,
                        "--run-spec",
                        dump_run_spec_json(run_spec),
                        "--cwd",
                        str(run_cwd),
                    ],
                    cwd=self.root,
                    stdout=worker_stdout,
                    stderr=worker_stderr,
                    close_fds=True,
                    **worker_popen_kwargs(),
                )
        except (OSError, TypeError, ValueError) as exc:
            stderr_path = task_path / "stderr.log"
            stderr_path.write_text(f"command could not be started: {exc}\n", encoding="utf-8")
            record.failure_summary = str(exc)
            record.status = TaskStatus.FAILED
            record.finished_at = now_iso()
            record.updated_at = now_iso()
            write_manifest(manifest_path(self.root, record.task_id), record)
            upsert_task(self.root, record)
            return record
        else:
            current = load_task(self.root, record.task_id)
            if current.status != TaskStatus.RUNNING:
                return current
            current.worker_pid = process.pid
            current.status = TaskStatus.RUNNING
            current.updated_at = now_iso()
            write_manifest(manifest_path(self.root, current.task_id), current)
            upsert_task(self.root, current)
            return current

    def _initial_record(
        self,
        task_id: str,
        task_path: Path,
        run_cwd: Path,
        run_spec: RunSpec,
        name: str | None,
    ) -> TaskRecord:
        created = now_iso()
        command_text = _run_spec_command_text(run_spec)
        paths = TaskPaths(
            task_dir=to_manifest_path(task_path, self.root),
            stdout=to_manifest_path(task_path / "stdout.log", self.root),
            stderr=to_manifest_path(task_path / "stderr.log", self.root),
        )
        return TaskRecord(
            task_id=task_id,
            mode="run",
            status=TaskStatus.PENDING,
            created_at=created,
            updated_at=created,
            working_dir=to_manifest_path(run_cwd, self.root),
            command=command_text,
            run_mode=run_spec.mode,
            argv=list(run_spec.argv) if run_spec.argv is not None else None,
            safe_profile=run_spec.safe_profile,
            source_path=None,
            exit_code=None,
            paths=paths,
            artifacts=default_task_artifacts(task_path, self.root),
            name=name,
        )

    def _write_reproduce_files(self, task_path: Path, run_spec: RunSpec, run_cwd: Path) -> None:
        reproduce_dir = task_path / "reproduce"
        command = _run_spec_command_text(run_spec)
        (reproduce_dir / "command.txt").write_text(command + "\n", encoding="utf-8")
        run_metadata = {
            "schema_version": "1",
            "run_mode": run_spec.mode,
            "command_text": command,
            "argv": list(run_spec.argv) if run_spec.argv is not None else None,
            "safe_profile": run_spec.safe_profile,
            "execution_note": (
                "argv mode executes the recorded argv list with subprocess shell=False; "
                "this is non-shell execution, not OS sandboxing"
            )
            if run_spec.mode == ARGV_RUN_MODE
            else "shell mode executes the recorded command text with subprocess shell=True",
        }
        (reproduce_dir / "run.json").write_text(
            json.dumps(run_metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        git_data = git_snapshot(run_cwd)
        dependency_data = dependency_snapshot()
        env_snapshot = {
            "python_version": sys.version,
            "python_executable": python_executable(),
            "platform": platform.platform(),
            "working_dir": str(run_cwd),
            "git_path": "reproduce/git.json",
            "dependencies_path": "reproduce/dependencies.json",
            "environment": {
                key: value
                for key, value in os.environ.items()
                if key.upper()
                in {
                    "PATH",
                    "PYTHONPATH",
                    "VIRTUAL_ENV",
                    "CONDA_PREFIX",
                    "CONDA_DEFAULT_ENV",
                    "COMSPEC",
                    "SHELL",
                }
            },
        }
        (reproduce_dir / "env.json").write_text(
            json.dumps(env_snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (reproduce_dir / "git.json").write_text(
            json.dumps(git_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (reproduce_dir / "dependencies.json").write_text(
            json.dumps(dependency_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def execute_task(root: Path, task_id: str, command: str | RunSpec, run_cwd: Path) -> TaskRecord:
    root = root.resolve()
    task_path = task_dir(root, task_id)
    stdout_path = task_path / "stdout.log"
    stderr_path = task_path / "stderr.log"
    record = load_task(root, task_id)

    if record.status == TaskStatus.CANCELLED:
        return record

    started = record.started_at or now_iso()
    record.status = TaskStatus.RUNNING
    record.started_at = started
    record.updated_at = started
    write_manifest(manifest_path(root, task_id), record)
    upsert_task(root, record)

    try:
        run_spec = _coerce_run_spec(command)
        with stdout_path.open("ab") as stdout_fh, stderr_path.open("ab") as stderr_fh:
            if _run_spec_mode(run_spec) == ARGV_RUN_MODE:
                argv = _run_spec_argv(run_spec)
                if not argv:
                    raise ValueError("argv mode requires a non-empty argv")
                process = subprocess.Popen(
                    argv,
                    cwd=run_cwd,
                    shell=False,
                    stdout=stdout_fh,
                    stderr=stderr_fh,
                    **command_popen_kwargs(),
                )
            else:
                process = subprocess.Popen(
                    _run_spec_command_text(run_spec),
                    cwd=run_cwd,
                    shell=True,
                    stdout=stdout_fh,
                    stderr=stderr_fh,
                    **command_popen_kwargs(),
                )
            record.pid = process.pid
            record.updated_at = now_iso()
            write_manifest(manifest_path(root, task_id), record)
            upsert_task(root, record)
            exit_code = process.wait()
    except (OSError, TypeError, ValueError) as exc:
        stderr_path.write_text(f"command could not be started: {exc}\n", encoding="utf-8")
        record = load_task(root, task_id)
        record.failure_summary = str(exc)
        record.status = TaskStatus.FAILED
        record.exit_code = None
        record.finished_at = now_iso()
        write_manifest(manifest_path(root, task_id), record)
        upsert_task(root, record)
        return record
    return finalize_task(root, task_id, exit_code, clear_worker=True)


def finalize_task(root: Path, task_id: str, exit_code: int, clear_worker: bool = False) -> TaskRecord:
    record = load_task(root, task_id)
    if record.status == TaskStatus.CANCELLED:
        return record

    stderr_path = resolve_workspace_path(record.paths.stderr, root)
    record.exit_code = exit_code
    if exit_code == 0:
        record.status = TaskStatus.COMPLETED
        record.failure_summary = None
    else:
        record.status = TaskStatus.FAILED
        record.failure_summary = summarize_failure(stderr_path, exit_code)

    finished = now_iso()
    record.finished_at = finished
    record.updated_at = finished
    record.pid = None
    if clear_worker:
        record.worker_pid = None
    write_manifest(manifest_path(root, task_id), record)
    upsert_task(root, record)
    return record


def mark_stale_running_task_failed(root: Path, task_id: str) -> TaskRecord:
    record = load_task(root, task_id)
    if record.status != TaskStatus.RUNNING:
        return record

    task_path = resolve_workspace_path(record.paths.task_dir, root)
    stderr_path = resolve_workspace_path(record.paths.stderr, root)
    worker_err_path = task_path / "worker.err.log"
    worker_tail = _tail_existing_lines(worker_err_path, 8)
    finished = now_iso()
    diagnostic_lines = [
        "",
        f"Lab-Sidecar: background task recovery marked this task failed at {finished}.",
        "Reason: manifest still said running, but no active child or worker process could be verified.",
    ]
    if record.pid is not None:
        diagnostic_lines.append(f"Recorded child pid: {record.pid}")
    if record.worker_pid is not None:
        diagnostic_lines.append(f"Recorded worker pid: {record.worker_pid}")
    if worker_tail:
        diagnostic_lines.append("worker.err.log tail:")
        diagnostic_lines.extend(worker_tail)

    diagnostic = "\n".join(diagnostic_lines).rstrip() + "\n"
    with stderr_path.open("a", encoding="utf-8") as fh:
        fh.write(diagnostic)

    record.status = TaskStatus.FAILED
    record.exit_code = None
    record.failure_summary = "\n".join(line for line in diagnostic_lines if line).strip()
    record.finished_at = finished
    record.updated_at = finished
    record.pid = None
    record.worker_pid = None
    write_manifest(manifest_path(root, task_id), record)
    upsert_task(root, record)
    return record


def _tail_existing_lines(path: Path, count: int) -> list[str]:
    if count <= 0 or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:]


def list_task_ids(root: Path) -> list[str]:
    directory = tasks_dir(root)
    if not directory.exists():
        return []
    task_paths = [path for path in directory.iterdir() if path.is_dir()]
    return [path.name for path in sorted(task_paths, key=_task_recency_key)]


def _task_recency_key(path: Path) -> tuple[int, str]:
    manifest = path / "manifest.json"
    try:
        return (manifest.stat().st_mtime_ns, path.name)
    except OSError:
        return (path.stat().st_mtime_ns, path.name)
