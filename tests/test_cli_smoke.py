from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import time
from pathlib import Path

import yaml
from pptx import Presentation
from typer.testing import CliRunner

from lab_sidecar.cli.app import app
from lab_sidecar.runner.process import terminate_process_tree


runner = CliRunner()
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_examples(workspace: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "examples", workspace / "examples")


def invoke(workspace: Path, args: list[str]):
    old_cwd = Path.cwd()
    os.chdir(workspace)
    try:
        return runner.invoke(app, args, prog_name="labsidecar", env={}, catch_exceptions=False)
    finally:
        os.chdir(old_cwd)


def extract_task_id(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Task created: "):
            return line.split(": ", 1)[1]
        if line.startswith("Imported as task: "):
            return line.split(": ", 1)[1]
    raise AssertionError(f"No task id in output:\n{output}")


def read_manifest(workspace: Path, task_id: str) -> dict:
    path = workspace / ".lab-sidecar" / "tasks" / task_id / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def assert_non_empty_file(path: Path) -> None:
    assert path.is_file()
    assert path.stat().st_size > 0


def assert_readable_deck(path: Path, min_slides: int = 5, max_slides: int = 8) -> Presentation:
    assert_non_empty_file(path)
    deck = Presentation(path)
    assert min_slides <= len(deck.slides) <= max_slides
    for index, slide in enumerate(deck.slides, start=1):
        text = "\n".join(shape.text for shape in slide.shapes if hasattr(shape, "text"))
        assert text.strip(), f"slide {index} appears blank"
        assert any(shape.has_text_frame and shape.text.strip() for shape in slide.shapes), f"slide {index} has no title/text"
    return deck


def wait_for_output(workspace: Path, task_id: str, needle: str, timeout: float = 10.0) -> None:
    path = workspace / ".lab-sidecar" / "tasks" / task_id / "stdout.log"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and needle in path.read_text(encoding="utf-8", errors="replace"):
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {needle!r} in {path}")


def test_init_creates_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / ".lab-sidecar").is_dir()
    assert (tmp_path / ".lab-sidecar" / "config.yaml").is_file()
    assert (tmp_path / ".lab-sidecar" / "tasks").is_dir()
    assert (tmp_path / ".lab-sidecar" / "index.sqlite").is_file()

    second = invoke(tmp_path, ["init"])
    assert second.exit_code == 2

    forced = invoke(tmp_path, ["init", "--force"])
    assert forced.exit_code == 0


def test_simple_success_task_and_queries(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    result = invoke(tmp_path, ["run", command])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    manifest = read_manifest(tmp_path, task_id)

    assert manifest["schema_version"] == "1"
    assert manifest["task_id"] == task_id
    assert manifest["mode"] == "run"
    assert manifest["status"] == "completed"
    assert manifest["working_dir"] == "."
    assert manifest["command"] == command
    assert manifest["source_path"] is None
    assert manifest["exit_code"] == 0
    assert set(["task_dir", "stdout", "stderr"]).issubset(manifest["paths"])
    assert manifest["artifacts"]
    assert (task_path / "manifest.json").is_file()
    assert (task_path / "stdout.log").is_file()
    assert (task_path / "stderr.log").is_file()
    assert (task_path / "reproduce" / "command.txt").is_file()
    assert (task_path / "reproduce" / "env.json").is_file()

    status = invoke(tmp_path, ["status", task_id])
    assert status.exit_code == 0
    assert "Status: completed" in status.output
    assert "Exit code: 0" in status.output

    logs = invoke(tmp_path, ["logs", task_id, "--tail", "20"])
    assert logs.exit_code == 0
    assert "Best val_accuracy=0.86" in logs.output
    assert "== stderr" in logs.output

    artifacts = invoke(tmp_path, ["artifacts", task_id])
    assert artifacts.exit_code == 0
    assert "[log]" in artifacts.output
    assert "stdout.log" in artifacts.output

    (tmp_path / ".lab-sidecar" / "index.sqlite").unlink()
    assert invoke(tmp_path, ["status", task_id]).exit_code == 0
    assert invoke(tmp_path, ["logs", task_id, "--stream", "stdout", "--tail", "5"]).exit_code == 0
    assert invoke(tmp_path, ["artifacts", task_id]).exit_code == 0


def test_simple_failure_task(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-failure/fail.py'
    result = invoke(tmp_path, ["run", command])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    manifest = read_manifest(tmp_path, task_id)

    assert manifest["status"] == "failed"
    assert manifest["exit_code"] != 0
    assert manifest["failure_summary"]
    assert "FileNotFoundError" in manifest["failure_summary"]
    assert (task_path / "stderr.log").is_file()
    assert "FileNotFoundError" in (task_path / "stderr.log").read_text(encoding="utf-8")

    status = invoke(tmp_path, ["status", task_id])
    assert status.exit_code == 0
    assert "Status: failed" in status.output
    assert "Failure summary:" in status.output

    logs = invoke(tmp_path, ["logs", task_id, "--stream", "stderr", "--tail", "20"])
    assert logs.exit_code == 0
    assert "FileNotFoundError" in logs.output


def test_each_task_has_independent_directory(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    first = extract_task_id(invoke(tmp_path, ["run", command]).output)
    second = extract_task_id(invoke(tmp_path, ["run", command]).output)

    assert first != second
    assert (tmp_path / ".lab-sidecar" / "tasks" / first).is_dir()
    assert (tmp_path / ".lab-sidecar" / "tasks" / second).is_dir()


def test_background_run_status_logs_and_cancel(tmp_path: Path) -> None:
    script = tmp_path / "long_task.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "for i in range(30):",
                "    print(f'tick={i}', flush=True)",
                "    time.sleep(0.5)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0

    command = f'"{sys.executable}" long_task.py'
    result = invoke(tmp_path, ["run", command, "--background"])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    manifest = read_manifest(tmp_path, task_id)
    assert manifest["status"] == "running"
    assert manifest["worker_pid"]

    wait_for_output(tmp_path, task_id, "tick=0")

    status = invoke(tmp_path, ["status", task_id])
    assert status.exit_code == 0
    assert "Status: running" in status.output

    logs = invoke(tmp_path, ["logs", task_id, "--stream", "stdout", "--tail", "5"])
    assert logs.exit_code == 0
    assert "tick=0" in logs.output

    cancel = invoke(tmp_path, ["cancel", task_id])
    assert cancel.exit_code == 0
    assert "Status: cancelled" in cancel.output

    status_after_cancel = invoke(tmp_path, ["status", task_id])
    assert status_after_cancel.exit_code == 0
    assert "Status: cancelled" in status_after_cancel.output
    cancelled_manifest = read_manifest(tmp_path, task_id)
    assert cancelled_manifest["status"] == "cancelled"
    assert cancelled_manifest["pid"] is None
    assert cancelled_manifest["worker_pid"] is None


def test_background_completed_task_refreshes_to_completed(tmp_path: Path) -> None:
    script = tmp_path / "quick_success.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('quick-start', flush=True)",
                "time.sleep(0.2)",
                "print('quick-done', flush=True)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0

    task_id = extract_task_id(invoke(tmp_path, ["run", f'"{sys.executable}" quick_success.py', "--background"]).output)

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        status = invoke(tmp_path, ["status", task_id])
        assert status.exit_code == 0
        if "Status: completed" in status.output:
            break
        time.sleep(0.2)

    assert status is not None
    assert "Status: completed" in status.output
    manifest = read_manifest(tmp_path, task_id)
    assert manifest["status"] == "completed"
    assert manifest["exit_code"] == 0
    assert manifest["pid"] is None
    assert manifest["worker_pid"] is None
    logs = invoke(tmp_path, ["logs", task_id, "--stream", "stdout", "--tail", "5"])
    assert logs.exit_code == 0
    assert "quick-done" in logs.output


def test_background_failed_task_refreshes_to_failed(tmp_path: Path) -> None:
    script = tmp_path / "quick_failure.py"
    script.write_text(
        "\n".join(
            [
                "import sys",
                "print('about to fail', file=sys.stderr, flush=True)",
                "raise RuntimeError('phase2 background failure')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0

    task_id = extract_task_id(invoke(tmp_path, ["run", f'"{sys.executable}" quick_failure.py', "--background"]).output)

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        status = invoke(tmp_path, ["status", task_id])
        assert status.exit_code == 0
        if "Status: failed" in status.output:
            break
        time.sleep(0.2)

    assert status is not None
    assert "Status: failed" in status.output
    assert "phase2 background failure" in status.output
    manifest = read_manifest(tmp_path, task_id)
    assert manifest["status"] == "failed"
    assert manifest["exit_code"] != 0
    assert manifest["pid"] is None
    assert manifest["worker_pid"] is None
    assert "phase2 background failure" in manifest["failure_summary"]


def test_background_completed_task_after_deleting_sqlite_uses_manifest(tmp_path: Path) -> None:
    script = tmp_path / "quick_success.py"
    script.write_text("print('sqlite-free-complete', flush=True)\n", encoding="utf-8")
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["run", f'"{sys.executable}" quick_success.py', "--background"]).output)

    deadline = time.time() + 10
    while time.time() < deadline:
        if read_manifest(tmp_path, task_id)["status"] == "completed":
            break
        time.sleep(0.2)

    index_path = tmp_path / ".lab-sidecar" / "index.sqlite"
    index_path.unlink()
    status = invoke(tmp_path, ["status", task_id])

    assert status.exit_code == 0
    assert "Status: completed" in status.output
    assert invoke(tmp_path, ["logs", task_id, "--tail", "5"]).exit_code == 0
    assert invoke(tmp_path, ["artifacts", task_id]).exit_code == 0
    assert index_path.is_file()


def test_stale_background_worker_is_marked_failed_with_diagnostics(tmp_path: Path) -> None:
    script = tmp_path / "long_task.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('stale-ready', flush=True)",
                "time.sleep(30)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["run", f'"{sys.executable}" long_task.py', "--background"]).output)
    wait_for_output(tmp_path, task_id, "stale-ready")

    manifest = read_manifest(tmp_path, task_id)
    worker_pid = manifest["worker_pid"]
    assert worker_pid
    terminate_process_tree(worker_pid)
    child_pid = manifest["pid"]
    if child_pid:
        terminate_process_tree(child_pid)

    manifest_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "manifest.json"
    manifest["pid"] = None
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        status = invoke(tmp_path, ["status", task_id])
        assert status.exit_code == 0
        if "Status: failed" in status.output:
            break
        time.sleep(0.2)

    assert status is not None
    assert "Status: failed" in status.output
    manifest = read_manifest(tmp_path, task_id)
    assert manifest["status"] == "failed"
    assert manifest["pid"] is None
    assert manifest["worker_pid"] is None
    assert "background task recovery marked this task failed" in manifest["failure_summary"]
    stderr_text = (tmp_path / ".lab-sidecar" / "tasks" / task_id / "stderr.log").read_text(encoding="utf-8")
    assert "background task recovery marked this task failed" in stderr_text


def test_list_and_open_use_manifest_task_state(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(tmp_path, ["run", command, "--name", "list-open-smoke"]).output)

    listed = invoke(tmp_path, ["list"])
    opened = invoke(tmp_path, ["open", task_id])

    assert listed.exit_code == 0
    assert task_id in listed.output
    assert "completed" in listed.output
    assert "list-open-smoke" in listed.output
    assert opened.exit_code == 0
    assert str(tmp_path / ".lab-sidecar" / "tasks" / task_id) in opened.output


def test_cancel_non_running_task_returns_state_error(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(tmp_path, ["run", command]).output)

    result = invoke(tmp_path, ["cancel", task_id])
    assert result.exit_code == 4
    assert "is not running" in result.output
    assert "Current status: completed" in result.output


def test_ingest_existing_directory(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "examples" / "csv-comparison"
    before = sorted(path.name for path in source.iterdir())

    result = invoke(tmp_path, ["ingest", "examples/csv-comparison", "--name", "csv import"])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    manifest = read_manifest(tmp_path, task_id)
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    refs_path = task_path / "raw" / "source_refs.json"
    refs = json.loads(refs_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "1"
    assert manifest["mode"] == "ingest"
    assert manifest["status"] == "completed"
    assert manifest["command"] is None
    assert manifest["source_path"] == "examples/csv-comparison"
    assert manifest["working_dir"] == "."
    assert manifest["exit_code"] == 0
    assert manifest["name"] == "csv import"
    assert (task_path / "stdout.log").is_file()
    assert (task_path / "stderr.log").is_file()
    assert refs_path.is_file()
    assert refs["source_path"] == "examples/csv-comparison"
    assert refs["path_kind"] == "relative"
    assert refs["source_type"] == "directory"
    assert refs["child_count"] == len(before)
    assert "examples/csv-comparison/baseline.csv" in refs["candidate_files"]
    assert sorted(path.name for path in source.iterdir()) == before

    status = invoke(tmp_path, ["status", task_id])
    assert status.exit_code == 0
    assert "Status: completed" in status.output

    artifacts = invoke(tmp_path, ["artifacts", task_id])
    assert artifacts.exit_code == 0
    assert "[raw]" in artifacts.output
    assert "raw/source_refs.json" in artifacts.output

    (tmp_path / ".lab-sidecar" / "index.sqlite").unlink()
    assert invoke(tmp_path, ["status", task_id]).exit_code == 0
    assert invoke(tmp_path, ["artifacts", task_id]).exit_code == 0


def test_ingest_existing_file(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "examples" / "algorithm-benchmark" / "results.json"
    before = source.read_text(encoding="utf-8")

    result = invoke(tmp_path, ["ingest", "examples/algorithm-benchmark/results.json"])

    assert result.exit_code == 0
    task_id = extract_task_id(result.output)
    manifest = read_manifest(tmp_path, task_id)
    refs = json.loads(
        (
            tmp_path
            / ".lab-sidecar"
            / "tasks"
            / task_id
            / "raw"
            / "source_refs.json"
        ).read_text(encoding="utf-8")
    )

    assert manifest["mode"] == "ingest"
    assert manifest["source_path"] == "examples/algorithm-benchmark/results.json"
    assert manifest["exit_code"] == 0
    assert refs["source_type"] == "file"
    assert refs["path_kind"] == "relative"
    assert refs["size_bytes"] == source.stat().st_size
    assert refs["is_candidate"] is True
    assert source.read_text(encoding="utf-8") == before


def test_ingest_missing_path_and_uninitialized_workspace(tmp_path: Path) -> None:
    missing = invoke(tmp_path, ["ingest", "missing-results"])
    assert missing.exit_code == 2
    assert "workspace is not initialized" in missing.output

    assert invoke(tmp_path, ["init"]).exit_code == 0
    missing_after_init = invoke(tmp_path, ["ingest", "missing-results"])
    assert missing_after_init.exit_code == 2
    assert "does not exist" in missing_after_init.output


def test_cli_exit_codes_for_missing_tasks_and_uninitialized_run(tmp_path: Path) -> None:
    run_without_init = invoke(tmp_path, ["run", f'"{sys.executable}" -c "print(1)"'])
    assert run_without_init.exit_code == 2
    assert "workspace is not initialized" in run_without_init.output

    assert invoke(tmp_path, ["init"]).exit_code == 0

    missing_status = invoke(tmp_path, ["status", "task_missing"])
    assert missing_status.exit_code == 3

    missing_logs = invoke(tmp_path, ["logs", "task_missing"])
    assert missing_logs.exit_code == 3

    missing_artifacts = invoke(tmp_path, ["artifacts", "task_missing"])
    assert missing_artifacts.exit_code == 3

    missing_cancel = invoke(tmp_path, ["cancel", "task_missing"])
    assert missing_cancel.exit_code == 3


def test_logs_missing_artifact_returns_exit_code_5(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(tmp_path, ["run", command]).output)

    (tmp_path / ".lab-sidecar" / "tasks" / task_id / "stdout.log").unlink()

    result = invoke(tmp_path, ["logs", task_id, "--stream", "stdout"])
    assert result.exit_code == 5
    assert "log files are not available" in result.output


def test_collect_csv_comparison_ingest_generates_normalized_metrics(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 0
    assert "Collected metrics for" in result.output
    assert "Detected fields:" in result.output

    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    csv_path = task_path / "metrics" / "normalized_metrics.csv"
    json_path = task_path / "metrics" / "normalized_metrics.json"
    summary_path = task_path / "metrics" / "collection-summary.json"

    assert csv_path.is_file()
    assert json_path.is_file()
    assert summary_path.is_file()

    rows = read_csv_rows(csv_path)
    assert rows
    assert {"source_file", "epoch", "model", "seed", "val_accuracy", "val_loss"}.issubset(rows[0])
    assert {Path(row["source_file"]).name for row in rows} == {
        "baseline.csv",
        "model_a.csv",
        "model_b.csv",
    }

    json_rows = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(json_rows) == len(rows)
    assert "source_file" in json_rows[0]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["task_status"] == "completed"
    assert summary["row_count"] == len(rows)
    assert {"epoch", "model", "seed", "val_accuracy", "val_loss"}.issubset(summary["detected_fields"])

    manifest = read_manifest(tmp_path, task_id)
    artifacts = {artifact["artifact_id"]: artifact for artifact in manifest["artifacts"]}
    assert artifacts["metrics_normalized_csv"]["type"] == "table"
    assert artifacts["metrics_normalized_json"]["type"] == "table"
    assert artifacts["metrics_collection_summary"]["type"] == "config"


def test_collect_run_working_dir_output_without_wrapper(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    stale_path = tmp_path / "stale.csv"
    stale_path.write_text("epoch,accuracy\n1,0.01\n", encoding="utf-8")
    old_time = time.time() - 30
    os.utime(stale_path, (old_time, old_time))

    command = f'"{sys.executable}" examples/simple-success/train.py --output metrics.csv'
    task_id = extract_task_id(invoke(tmp_path, ["run", command]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    rows = read_csv_rows(task_path / "metrics" / "normalized_metrics.csv")
    assert rows
    assert {Path(row["source_file"]).name for row in rows} == {"metrics.csv"}
    summary = json.loads((task_path / "metrics" / "collection-summary.json").read_text(encoding="utf-8"))
    assert {
        (Path(candidate["source_file"]).name, candidate["origin"])
        for candidate in summary["candidates"]
    } == {("metrics.csv", "run_working_dir")}


def test_collect_json_algorithm_benchmark_ingest_generates_normalized_metrics(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(
        invoke(tmp_path, ["ingest", "examples/algorithm-benchmark/results.json"]).output
    )

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    rows = read_csv_rows(task_path / "metrics" / "normalized_metrics.csv")

    assert rows
    assert {
        "source_file",
        "benchmark_name",
        "algorithm",
        "input_size",
        "seed",
        "runtime_ms",
        "memory_mb",
    }.issubset(rows[0])
    assert rows[0]["source_file"].endswith("examples/algorithm-benchmark/results.json")

    json_rows = json.loads((task_path / "metrics" / "normalized_metrics.json").read_text(encoding="utf-8"))
    assert len(json_rows) == len(rows)
    assert json_rows[0]["source_file"].endswith("examples/algorithm-benchmark/results.json")

    summary = json.loads((task_path / "metrics" / "collection-summary.json").read_text(encoding="utf-8"))
    assert {"algorithm", "seed", "runtime_ms", "memory_mb"}.issubset(summary["detected_fields"])


def test_network_experiment_csv_collects_metrics_and_generates_bar_figure(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "network-results"
    source.mkdir()
    (source / "all-results.csv").write_text(
        "\n".join(
            [
                "Stage,Scenario,DurationSec,DATA_TIMER,BACKLOG_FACTOR,AvgUtil,DataTimeoutPerMin,Score,BadCrcTotal,WallSeconds",
                "coarse,default flood,120,1500,3,88.02,24.5,87.285,12,120.8",
                "coarse,default flood,120,1500,4,85.15,29,84.28,14,120.7",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "network-results"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    rows = read_csv_rows(task_path / "metrics" / "normalized_metrics.csv")
    assert len(rows) == 2
    assert {"DurationSec", "AvgUtil", "DataTimeoutPerMin", "Score", "BadCrcTotal", "WallSeconds"}.issubset(rows[0])
    summary = json.loads((task_path / "metrics" / "collection-summary.json").read_text(encoding="utf-8"))
    assert {
        "DurationSec",
        "AvgUtil",
        "DataTimeoutPerMin",
        "Score",
        "BadCrcTotal",
        "WallSeconds",
    }.issubset(summary["detected_fields"])

    figure_result = invoke(tmp_path, ["figures", task_id])

    assert figure_result.exit_code == 0
    figures_dir = task_path / "figures"
    assert_non_empty_file(figures_dir / "bar_score_by_data_timer.png")
    assert_non_empty_file(figures_dir / "bar_score_by_data_timer.svg")
    figure_summary = json.loads((figures_dir / "figure-summary.json").read_text(encoding="utf-8"))
    assert figure_summary["generated_figures"][0]["chart_type"] == "bar"
    assert figure_summary["generated_figures"][0]["x"] == "DATA_TIMER"
    assert figure_summary["generated_figures"][0]["y"] == "Score"


def test_collect_missing_task_returns_exit_code_3(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0

    result = invoke(tmp_path, ["collect", "task_missing"])

    assert result.exit_code == 3
    assert "was not found" in result.output


def test_collect_without_supported_metrics_returns_exit_code_5(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "notes-only"
    source.mkdir()
    (source / "notes.txt").write_text("no metrics here\n", encoding="utf-8")
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "notes-only"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 5
    assert "no CSV/JSON metric candidates were found" in result.output
    assert "collection-summary.json" in result.output
    summary_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "metrics" / "collection-summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["candidate_count"] == 0
    assert summary["row_count"] == 0


def test_collect_bad_and_empty_inputs_record_diagnostics_without_outputs(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "bad-inputs"
    source.mkdir()
    (source / "bad.json").write_text('{"epoch": 1, "accuracy": ', encoding="utf-8")
    (source / "empty.csv").write_text("", encoding="utf-8")
    (source / "missing_metric_columns.csv").write_text("name,notes\nalpha,no metric columns\n", encoding="utf-8")
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "bad-inputs"]).output)

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 5
    assert "CSV/JSON candidates were found, but no metrics could be collected" in result.output
    assert "collection-summary.json" in result.output
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    summary_path = task_path / "metrics" / "collection-summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["candidate_count"] == 3
    assert summary["row_count"] == 0
    assert not summary["output_files"]
    skipped = {(Path(item["source_file"]).name, item["reason"]) for item in summary["skipped_files"]}
    assert ("bad.json", "parse_failed") in skipped
    assert ("empty.csv", "no_detected_metrics") in skipped
    assert ("missing_metric_columns.csv", "no_detected_metrics") in skipped
    assert any("Failed to parse bad-inputs/bad.json" in warning for warning in summary["warnings"])
    assert not (task_path / "metrics" / "normalized_metrics.csv").exists()
    assert not (task_path / "metrics" / "normalized_metrics.json").exists()

    manifest = read_manifest(tmp_path, task_id)
    artifacts = {artifact["artifact_id"]: artifact for artifact in manifest["artifacts"]}
    assert "metrics_collection_summary" in artifacts
    assert "metrics_normalized_csv" not in artifacts
    assert "metrics_normalized_json" not in artifacts


def test_collect_repeated_bad_input_does_not_duplicate_summary_artifact(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "bad-json"
    source.mkdir()
    (source / "results.json").write_text("{not valid json", encoding="utf-8")
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "bad-json"]).output)

    assert invoke(tmp_path, ["collect", task_id]).exit_code == 5
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 5

    manifest = read_manifest(tmp_path, task_id)
    artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
    assert artifact_ids.count("metrics_collection_summary") == 1


def test_collect_after_deleting_sqlite_uses_manifest_and_source_refs(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    index_path = tmp_path / ".lab-sidecar" / "index.sqlite"
    index_path.unlink()

    result = invoke(tmp_path, ["collect", task_id])

    assert result.exit_code == 0
    assert index_path.is_file()
    csv_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "metrics" / "normalized_metrics.csv"
    assert csv_path.is_file()
    assert read_csv_rows(csv_path)


def test_figures_csv_comparison_after_collect_generates_png_svg_and_spec(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    assert "Generated" in result.output
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    figures_dir = task_path / "figures"
    png_files = sorted(figures_dir.glob("*.png"))
    svg_files = sorted(figures_dir.glob("*.svg"))

    assert png_files
    assert svg_files
    assert len(png_files) == len(svg_files)
    for path in [*png_files, *svg_files]:
        assert_non_empty_file(path)
        assert path.suffix in {".png", ".svg"}

    spec_path = figures_dir / "figure-spec.yaml"
    summary_path = figures_dir / "figure-summary.json"
    assert_non_empty_file(spec_path)
    assert_non_empty_file(summary_path)

    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert spec["source_metrics"].endswith("metrics/normalized_metrics.csv")
    assert spec["figures"]
    assert all(item["chart_type"] == "line" for item in spec["figures"])
    assert len(spec["figures"]) <= 2

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["figure_count"] == len(png_files)

    manifest = read_manifest(tmp_path, task_id)
    artifact_types = {artifact["artifact_id"]: artifact["type"] for artifact in manifest["artifacts"]}
    assert any(kind == "figure" for kind in artifact_types.values())
    assert artifact_types["figures_spec"] == "config"
    assert artifact_types["figures_summary"] == "config"


def test_figures_algorithm_benchmark_after_collect_generates_bar_chart(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(
        invoke(tmp_path, ["ingest", "examples/algorithm-benchmark/results.json"]).output
    )
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    figures_dir = task_path / "figures"
    assert_non_empty_file(figures_dir / "bar_runtime_ms_by_algorithm.png")
    assert_non_empty_file(figures_dir / "bar_runtime_ms_by_algorithm.svg")
    spec = yaml.safe_load((figures_dir / "figure-spec.yaml").read_text(encoding="utf-8"))
    assert len(spec["figures"]) == 1
    assert spec["figures"][0]["chart_type"] == "bar"
    assert spec["figures"][0]["x"] == "algorithm"
    assert spec["figures"][0]["y"] == "runtime_ms"


def test_figures_before_collect_returns_exit_code_5(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 5
    assert "metrics are not ready" in result.output
    assert "collect" in result.output


def test_figures_missing_task_returns_exit_code_3(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0

    result = invoke(tmp_path, ["figures", "task_missing"])

    assert result.exit_code == 3
    assert "was not found" in result.output


def test_figures_after_deleting_sqlite_uses_manifest_and_metrics(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    index_path = tmp_path / ".lab-sidecar" / "index.sqlite"
    index_path.unlink()

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    assert index_path.is_file()
    figures_dir = tmp_path / ".lab-sidecar" / "tasks" / task_id / "figures"
    assert any(path.suffix == ".png" and path.stat().st_size > 0 for path in figures_dir.iterdir())


def test_figures_with_spec_generates_requested_line_chart(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    spec_path = tmp_path / "figure.yaml"
    spec_path.write_text(
        "\n".join(
            [
                "figure_id: accuracy_curve",
                "chart_type: line",
                "title: Validation Accuracy over Epoch",
                "x: epoch",
                "y: val_accuracy",
                "group_by: source_file",
                "output:",
                "  - figures/accuracy_curve.png",
                "  - figures/accuracy_curve.svg",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["figures", task_id, "--spec", "figure.yaml"])

    assert result.exit_code == 0
    figures_dir = tmp_path / ".lab-sidecar" / "tasks" / task_id / "figures"
    assert_non_empty_file(figures_dir / "accuracy_curve.png")
    assert_non_empty_file(figures_dir / "accuracy_curve.svg")

    generated_spec = yaml.safe_load((figures_dir / "figure-spec.yaml").read_text(encoding="utf-8"))
    assert generated_spec["spec_input_path"] == "figure.yaml"
    assert generated_spec["figures"][0]["figure_id"] == "accuracy_curve"
    assert generated_spec["figures"][0]["group_by"] == "source_file"

    summary = json.loads((figures_dir / "figure-summary.json").read_text(encoding="utf-8"))
    assert summary["metrics_path"].endswith("metrics/normalized_metrics.csv")
    assert summary["spec_path"] == "figure.yaml"
    assert summary["generated_figures"][0]["png_path"].endswith("figures/accuracy_curve.png")
    assert summary["skipped_candidates"] == []
    assert summary["errors"] == []


def test_figures_with_spec_generates_requested_bar_chart(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(
        invoke(tmp_path, ["ingest", "examples/algorithm-benchmark/results.json"]).output
    )
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    spec_path = tmp_path / "bar.yaml"
    spec_path.write_text(
        "\n".join(
            [
                "figure_id: runtime_by_algorithm",
                "chart_type: bar",
                "title: Runtime by Algorithm",
                "x: algorithm",
                "y: runtime_ms",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["figures", task_id, "--spec", "bar.yaml"])

    assert result.exit_code == 0
    figures_dir = tmp_path / ".lab-sidecar" / "tasks" / task_id / "figures"
    assert_non_empty_file(figures_dir / "runtime_by_algorithm.png")
    assert_non_empty_file(figures_dir / "runtime_by_algorithm.svg")
    summary = json.loads((figures_dir / "figure-summary.json").read_text(encoding="utf-8"))
    assert summary["generated_figures"][0]["chart_type"] == "bar"
    assert summary["generated_figures"][0]["x"] == "algorithm"
    assert summary["generated_figures"][0]["y"] == "runtime_ms"


def test_figures_missing_spec_returns_exit_code_2(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id, "--spec", "missing.yaml"])

    assert result.exit_code == 2
    assert "figure spec is invalid" in result.output
    assert "does not exist" in result.output


def test_figures_invalid_spec_yaml_returns_exit_code_2(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    (tmp_path / "bad.yaml").write_text("figure_id: [unterminated\n", encoding="utf-8")

    result = invoke(tmp_path, ["figures", task_id, "--spec", "bad.yaml"])

    assert result.exit_code == 2
    assert "could not be parsed" in result.output


def test_figures_spec_missing_metrics_field_returns_exit_code_5(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    (tmp_path / "missing-field.yaml").write_text(
        "\n".join(
            [
                "figure_id: missing_metric",
                "chart_type: line",
                "title: Missing Metric",
                "x: epoch",
                "y: does_not_exist",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = invoke(tmp_path, ["figures", task_id, "--spec", "missing-field.yaml"])

    assert result.exit_code == 5
    assert "does_not_exist" in result.output
    summary_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "figures" / "figure-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["generated_figures"] == []
    assert summary["errors"]
    assert "does_not_exist" in summary["skipped_candidates"][0]["reason"]


def test_figures_auto_runtime_alias_uses_runtime_ms(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(
        invoke(tmp_path, ["ingest", "examples/algorithm-benchmark/results.json"]).output
    )
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 0
    spec_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "figures" / "figure-spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    assert spec["figures"][0]["y"] == "runtime_ms"


def test_figures_auto_rejects_bar_chart_with_too_many_categories(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    source = tmp_path / "many-categories.csv"
    with source.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["model", "accuracy"])
        writer.writeheader()
        for index in range(13):
            writer.writerow({"model": f"model_{index}", "accuracy": 0.8 + index / 100})
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "many-categories.csv"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["figures", task_id])

    assert result.exit_code == 5
    assert "limit is 12" in result.output
    summary = json.loads(
        (
            tmp_path
            / ".lab-sidecar"
            / "tasks"
            / task_id
            / "figures"
            / "figure-summary.json"
        ).read_text(encoding="utf-8")
    )
    assert summary["generated_figures"] == []
    assert summary["skipped_candidates"]
    assert "limit is 12" in summary["skipped_candidates"][0]["reason"]


def test_figures_repeated_run_does_not_duplicate_manifest_artifacts(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0

    manifest = read_manifest(tmp_path, task_id)
    artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
    assert len(artifact_ids) == len(set(artifact_ids))


def test_figures_with_spec_after_deleting_sqlite_uses_manifest_and_metrics(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    (tmp_path / "figure.yaml").write_text(
        "\n".join(
            [
                "figure_id: accuracy_curve",
                "chart_type: line",
                "title: Validation Accuracy over Epoch",
                "x: epoch",
                "y: val_accuracy",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    index_path = tmp_path / ".lab-sidecar" / "index.sqlite"
    index_path.unlink()

    result = invoke(tmp_path, ["figures", task_id, "--spec", "figure.yaml"])

    assert result.exit_code == 0
    assert index_path.is_file()
    assert_non_empty_file(
        tmp_path
        / ".lab-sidecar"
        / "tasks"
        / task_id
        / "figures"
        / "accuracy_curve.png"
    )


def test_report_completed_ingest_after_collect_and_figures_generates_markdown(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0

    result = invoke(tmp_path, ["report", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    report_path = task_path / "reports" / "report-fragment.md"
    summary_path = task_path / "reports" / "report-summary.json"
    assert_non_empty_file(report_path)
    assert_non_empty_file(summary_path)

    text = report_path.read_text(encoding="utf-8")
    assert task_id in text
    assert "status" in text
    assert "completed" in text
    assert "指标行数" in text
    assert "val_accuracy" in text
    assert "../figures/" in text
    assert "working_dir" in text
    assert "source_path" in text

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["template"] == "zh-lab"
    assert summary["provenance"]["task_id"] == task_id
    assert summary["metrics"]["row_count"] > 0
    assert summary["figures"]["figure_count"] > 0

    manifest = read_manifest(tmp_path, task_id)
    artifacts = {artifact["artifact_id"]: artifact for artifact in manifest["artifacts"]}
    assert artifacts["report_fragment_md"]["type"] == "report"
    assert artifacts["report_fragment_md"]["path"] == "reports/report-fragment.md"
    assert artifacts["report_summary_json"]["type"] == "config"


def test_report_with_metrics_but_no_figures_generates_with_hint(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["report", task_id])

    assert result.exit_code == 0
    report_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "reports" / "report-fragment.md"
    text = report_path.read_text(encoding="utf-8")
    assert "尚未生成图表" in text
    assert f"labsidecar figures {task_id}" in text


def test_report_completed_ingest_without_metrics_returns_exit_code_5(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)

    result = invoke(tmp_path, ["report", task_id])

    assert result.exit_code == 5
    assert "requires collected metrics" in result.output
    assert "collect" in result.output


def test_report_failed_run_generates_failure_report_without_metrics(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-failure/fail.py'
    task_id = extract_task_id(invoke(tmp_path, ["run", command]).output)

    result = invoke(tmp_path, ["report", task_id])

    assert result.exit_code == 0
    report_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "reports" / "report-fragment.md"
    text = report_path.read_text(encoding="utf-8")
    assert "失败" in text
    assert "failure_summary" in text
    assert "FileNotFoundError" in text
    assert "stderr.log 尾部" in text
    assert "reproduce/command.txt" in text
    assert "不写成成功实验结果分析" in text


def test_report_cancelled_task_generates_cancelled_report(tmp_path: Path) -> None:
    script = tmp_path / "cancel_me.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('ready', flush=True)",
                "time.sleep(30)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" cancel_me.py'
    task_id = extract_task_id(invoke(tmp_path, ["run", command, "--background"]).output)
    wait_for_output(tmp_path, task_id, "ready")
    assert invoke(tmp_path, ["cancel", task_id]).exit_code == 0

    result = invoke(tmp_path, ["report", task_id])

    assert result.exit_code == 0
    report_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "reports" / "report-fragment.md"
    text = report_path.read_text(encoding="utf-8")
    assert "取消" in text
    assert "cancelled" in text
    assert "cancellation note" in text
    assert "started_at" in text
    assert "finished_at" in text
    assert "不写成成功实验结果分析" in text


def test_report_invalid_template_returns_exit_code_2(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["report", task_id, "--template", "bad-template"])

    assert result.exit_code == 2
    assert "template is invalid" in result.output


def test_report_missing_task_returns_exit_code_3(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0

    result = invoke(tmp_path, ["report", "task_missing"])

    assert result.exit_code == 3
    assert "was not found" in result.output


def test_report_after_deleting_sqlite_uses_manifest_metrics_and_figures(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    index_path = tmp_path / ".lab-sidecar" / "index.sqlite"
    index_path.unlink()

    result = invoke(tmp_path, ["report", task_id, "--template", "en-paper"])

    assert result.exit_code == 0
    assert index_path.is_file()
    report_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "reports" / "report-fragment.md"
    text = report_path.read_text(encoding="utf-8")
    assert "Experimental Summary Fragment" in text
    assert "../figures/" in text


def test_report_repeated_run_does_not_duplicate_manifest_artifacts(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    assert invoke(tmp_path, ["report", task_id]).exit_code == 0
    assert invoke(tmp_path, ["report", task_id, "--template", "zh-summary"]).exit_code == 0

    manifest = read_manifest(tmp_path, task_id)
    artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
    assert len(artifact_ids) == len(set(artifact_ids))
    assert artifact_ids.count("report_fragment_md") == 1
    assert artifact_ids.count("report_summary_json") == 1


def test_slides_after_collect_figures_report_generates_pptx_and_summary(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    assert invoke(tmp_path, ["report", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    assert "Presentation draft created:" in result.output
    assert "Template: zh-summary" in result.output
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    pptx_path = task_path / "slides" / "presentation-draft.pptx"
    summary_path = task_path / "slides" / "slides-summary.json"
    assert_non_empty_file(pptx_path)
    assert_non_empty_file(summary_path)

    deck = assert_readable_deck(pptx_path)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["template"] == "zh-summary"
    assert summary["slide_count"] == len(deck.slides)
    assert len(summary["slides"]) == len(deck.slides)
    assert all({"slide_index", "title", "purpose", "source_artifacts"}.issubset(slide) for slide in summary["slides"])
    assert summary["included_metrics"]["row_count"] > 0
    assert summary["included_metrics"]["numeric"]
    assert "val_accuracy" in {item["column"] for item in summary["included_metrics"]["numeric"]}
    assert summary["included_figures"]
    assert "warnings" in summary
    assert summary["qa_checks"]["slide_count"]["passed"] is True
    assert summary["qa_checks"]["empty_slide_check"]["passed"] is True
    assert summary["qa_checks"]["title_check"]["passed"] is True
    assert summary["qa_checks"]["artifact_duplicate_check"]["passed"] is True
    assert summary["metrics"]["row_count"] > 0
    assert summary["figures"]
    assert "reports/report-fragment.md" in summary["source_artifacts"]

    manifest = read_manifest(tmp_path, task_id)
    artifacts = {artifact["artifact_id"]: artifact for artifact in manifest["artifacts"]}
    assert artifacts["slides_presentation_draft_pptx"]["type"] == "presentation"
    assert artifacts["slides_presentation_draft_pptx"]["path"] == "slides/presentation-draft.pptx"
    assert artifacts["slides_summary_json"]["type"] == "config"
    assert artifacts["slides_summary_json"]["path"] == "slides/slides-summary.json"


def test_slides_completed_without_artifacts_returns_exit_code_5(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 5
    assert "slides generation requires metrics, figures, or report artifacts" in result.output
    assert "collect" in result.output


def test_slides_failed_task_generates_diagnostic_ppt(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" examples/simple-failure/fail.py'
    task_id = extract_task_id(invoke(tmp_path, ["run", command]).output)

    result = invoke(tmp_path, ["slides", task_id, "--template", "en-summary"])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    pptx_path = task_path / "slides" / "presentation-draft.pptx"
    summary_path = task_path / "slides" / "slides-summary.json"
    assert_non_empty_file(pptx_path)
    assert_non_empty_file(summary_path)
    deck = assert_readable_deck(pptx_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["task_status"] == "failed"
    assert summary["template"] == "en-summary"
    assert "stderr.log" in summary["source_artifacts"]
    assert any("Failure" in slide["title"] or "Failed" in slide["title"] for slide in summary["slides"])
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "FileNotFoundError" in deck_text
    assert "failed" in deck_text


def test_slides_cancelled_task_generates_cancelled_diagnostic_ppt(tmp_path: Path) -> None:
    script = tmp_path / "cancel_me.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "print('ready', flush=True)",
                "time.sleep(30)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0
    command = f'"{sys.executable}" cancel_me.py'
    task_id = extract_task_id(invoke(tmp_path, ["run", command, "--background"]).output)
    wait_for_output(tmp_path, task_id, "ready")
    assert invoke(tmp_path, ["cancel", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    pptx_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "slides" / "presentation-draft.pptx"
    summary_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "slides" / "slides-summary.json"
    deck = assert_readable_deck(pptx_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["task_status"] == "cancelled"
    assert any("取消" in slide["title"] or "Cancellation" in slide["title"] for slide in summary["slides"])
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "cancelled" in deck_text
    assert "cancellation" in deck_text.lower()


def test_slides_with_four_figures_creates_multiple_figure_slides(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id

    for index, (metric, group_by) in enumerate(
        [
            ("val_accuracy", "model"),
            ("val_loss", "model"),
            ("val_accuracy", "seed"),
            ("val_loss", "seed"),
        ],
        start=1,
    ):
        spec_path = tmp_path / f"figure_{index}.yaml"
        spec_path.write_text(
            "\n".join(
                [
                    f"figure_id: multi_{index}",
                    "chart_type: line",
                    f"title: Multi Figure {index}",
                    "x: epoch",
                    f"y: {metric}",
                    f"group_by: {group_by}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        assert invoke(tmp_path, ["figures", task_id, "--spec", str(spec_path)]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    pptx_path = task_path / "slides" / "presentation-draft.pptx"
    deck = assert_readable_deck(pptx_path, min_slides=8, max_slides=9)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    assert len(summary["included_figures"]) == 4
    figure_slides = [slide for slide in summary["slides"] if "figure" in slide["purpose"]]
    assert len(figure_slides) == 2
    assert all(len([source for source in slide["source_artifacts"] if source.endswith(".png")]) <= 2 for slide in figure_slides)
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "figure_id" not in deck_text.lower()
    assert "multi_1" in deck_text
    assert "chart_type" not in deck_text.lower()


def test_slides_repeated_run_does_not_duplicate_manifest_artifacts(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0

    assert invoke(tmp_path, ["slides", task_id]).exit_code == 0
    assert invoke(tmp_path, ["slides", task_id, "--template", "en-summary"]).exit_code == 0

    manifest = read_manifest(tmp_path, task_id)
    artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
    assert len(artifact_ids) == len(set(artifact_ids))
    assert artifact_ids.count("slides_presentation_draft_pptx") == 1
    assert artifact_ids.count("slides_summary_json") == 1


def test_slides_after_deleting_sqlite_uses_manifest_artifacts(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    assert invoke(tmp_path, ["report", task_id]).exit_code == 0
    index_path = tmp_path / ".lab-sidecar" / "index.sqlite"
    index_path.unlink()

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    assert index_path.is_file()
    pptx_path = tmp_path / ".lab-sidecar" / "tasks" / task_id / "slides" / "presentation-draft.pptx"
    assert_readable_deck(pptx_path)


def test_slides_long_command_and_paths_are_truncated_in_summary(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    manifest_path = task_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    long_command = "py -3 train.py " + " ".join(f"--very-long-option-{index}=value-{index}" for index in range(40))
    long_source = str(tmp_path / ("nested-" + "x" * 160) / ("source-" + "y" * 120))
    long_working_dir = str(tmp_path / ("working-" + "z" * 180))
    manifest["command"] = long_command
    manifest["source_path"] = long_source
    manifest["working_dir"] = long_working_dir
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    assert_readable_deck(task_path / "slides" / "presentation-draft.pptx")
    assert summary["full_text_fields"]["command"] == long_command
    assert summary["full_text_fields"]["source_path"] == long_source
    assert summary["full_text_fields"]["working_dir"] == long_working_dir
    truncated_keys = {item["key"] for item in summary["text_truncations"]}
    assert {"command", "source_path", "working_dir"}.issubset(truncated_keys)


def test_slides_failed_task_long_stderr_is_truncated_and_recorded(tmp_path: Path) -> None:
    script = tmp_path / "long_stderr.py"
    script.write_text(
        "\n".join(
            [
                "import sys",
                "for index in range(40):",
                "    print('stderr-line-' + str(index) + '-' + ('x' * 180), file=sys.stderr)",
                "raise SystemExit(1)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["run", f'"{sys.executable}" long_stderr.py']).output)
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    deck = assert_readable_deck(task_path / "slides" / "presentation-draft.pptx")
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "... earlier lines truncated ..." in deck_text
    stderr_truncations = [item for item in summary["text_truncations"] if item["key"] == "stderr_tail"]
    assert stderr_truncations
    assert "stderr-line-0" in stderr_truncations[0]["full"]
    assert "stderr-line-39" in stderr_truncations[0]["full"]


def test_slides_zh_project_template_generates_project_deck(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/project-presentation-pack"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    assert invoke(tmp_path, ["report", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id, "--template", "zh-project"])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    deck = assert_readable_deck(task_path / "slides" / "presentation-draft.pptx", min_slides=7, max_slides=9)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    assert summary["template"] == "zh-project"
    assert summary["font_family"] == "Microsoft YaHei"
    assert "SimSun" in summary["font_fallbacks"]
    assert summary["project_goal"]["present"] is True
    slide_titles = {slide["title"] for slide in summary["slides"]}
    assert {"项目概览与来源", "关键对比与消融", "结论与复现"}.issubset(slide_titles)
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "项目汇报草稿" in deck_text
    assert len(deck.slides) == summary["slide_count"]


def test_slides_caption_missing_fields_uses_unknown_placeholder(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    figure_summary_path = task_path / "figures" / "figure-summary.json"
    figure_summary = json.loads(figure_summary_path.read_text(encoding="utf-8"))
    figure_summary["warnings"] = ["synthetic warning for missing metadata"]
    figure_summary["skipped_candidates"] = [{"figure_id": "missing_meta", "reason": "metadata intentionally absent"}]
    for item in figure_summary["generated_figures"]:
        item.pop("x", None)
        item.pop("y", None)
        item.pop("group_by", None)
        item.pop("source_metrics", None)
    figure_summary_path.write_text(json.dumps(figure_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    deck = assert_readable_deck(task_path / "slides" / "presentation-draft.pptx")
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "x=未自动推断" in deck_text
    assert "y=未自动推断" in deck_text
    assert "group_by=未自动推断" in deck_text
    assert "source=未自动推断" in deck_text
    assert summary["figure_warnings"] == ["synthetic warning for missing metadata"]
    assert summary["figure_skipped_candidates"][0]["figure_id"] == "missing_meta"


def test_slides_metrics_table_truncates_many_rows_and_columns(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    data_dir = tmp_path / "wide-results"
    data_dir.mkdir()
    csv_path = data_dir / "metrics.csv"
    headers = ["model", "variant", "accuracy", "f1", "latency_ms", "loss", "memory_mb", "runtime_s", "extra_a", "extra_b"]
    rows = []
    for index in range(12):
        rows.append(
            {
                "model": f"model_{index}",
                "variant": f"v{index}",
                "accuracy": str(0.70 + index / 100),
                "f1": str(0.60 + index / 100),
                "latency_ms": str(30 + index),
                "loss": str(1.0 - index / 100),
                "memory_mb": str(100 + index),
                "runtime_s": str(5 + index),
                "extra_a": str(index),
                "extra_b": str(index * 2),
            }
        )
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    task_id = extract_task_id(invoke(tmp_path, ["ingest", str(data_dir)]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    deck = assert_readable_deck(task_path / "slides" / "presentation-draft.pptx", min_slides=6, max_slides=8)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    assert summary["metrics_table"]["displayed_row_count"] <= 6
    assert len(summary["metrics_table"]["columns"]) <= 8
    assert summary["metrics_table"]["shown_columns"]
    assert summary["metrics_table"]["hidden_columns"]
    assert "truncated_cells_count" in summary["metrics_table"]
    assert summary["table_truncations"]
    assert summary["table_truncations"][0]["source_metrics"] == "metrics/normalized_metrics.csv"
    assert summary["table_truncations"][0]["shown_columns"]
    assert summary["table_truncations"][0]["hidden_columns"]
    assert "truncated_cells_count" in summary["table_truncations"][0]
    assert summary["qa_checks"]["table_overflow_guard"]["passed"] is True
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "指标表格预览" in deck_text


def test_slides_key_comparison_identifies_best_and_baseline_delta(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    data_dir = tmp_path / "comparison-results"
    data_dir.mkdir()
    csv_path = data_dir / "metrics.csv"
    csv_path.write_text(
        "\n".join(
            [
                "model,accuracy,latency_ms",
                "baseline,0.80,30",
                "candidate_a,0.86,35",
                "candidate_b,0.84,25",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", str(data_dir)]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id, "--template", "zh-project"])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    deck = assert_readable_deck(task_path / "slides" / "presentation-draft.pptx", min_slides=7, max_slides=9)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    comparison = summary["key_comparisons"][0]
    assert comparison["metric"] == "accuracy"
    assert comparison["direction"] == "higher"
    assert comparison["best_item"]["label"] == "candidate_a"
    assert comparison["baseline_item"]["label"] == "baseline"
    assert comparison["delta"] is not None
    deck_text = "\n".join(shape.text for slide in deck.slides for shape in slide.shapes if hasattr(shape, "text"))
    assert "关键对比" in deck_text
    assert "candidate_a" in deck_text


def test_slides_key_comparison_without_baseline_does_not_invent_delta(tmp_path: Path) -> None:
    assert invoke(tmp_path, ["init"]).exit_code == 0
    data_dir = tmp_path / "no-baseline-results"
    data_dir.mkdir()
    (data_dir / "metrics.csv").write_text(
        "\n".join(
            [
                "method,f1,loss",
                "alpha,0.75,0.45",
                "beta,0.82,0.39",
                "gamma,0.79,0.41",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    task_id = extract_task_id(invoke(tmp_path, ["ingest", str(data_dir)]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id, "--template", "zh-project"])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    assert_readable_deck(task_path / "slides" / "presentation-draft.pptx", min_slides=7, max_slides=9)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    comparison = summary["key_comparisons"][0]
    assert comparison["best_item"]["label"] == "beta"
    assert comparison["baseline_item"] is None
    assert comparison["delta"] is None


def test_slides_zh_project_summary_contains_key_comparison_metadata(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/project-presentation-pack"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    assert invoke(tmp_path, ["report", task_id]).exit_code == 0

    result = invoke(tmp_path, ["slides", task_id, "--template", "zh-project"])

    assert result.exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    assert_readable_deck(task_path / "slides" / "presentation-draft.pptx", min_slides=7, max_slides=9)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    assert summary["key_comparisons"]
    comparison = summary["key_comparisons"][0]
    assert comparison["source_metrics"] == "metrics/normalized_metrics.csv"
    assert comparison["best_item"]
    assert any("关键对比" in slide["title"] for slide in summary["slides"])


def test_slides_long_caption_truncation_is_recorded(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/csv-comparison"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0
    task_path = tmp_path / ".lab-sidecar" / "tasks" / task_id
    figure_summary_path = task_path / "figures" / "figure-summary.json"
    figure_summary = json.loads(figure_summary_path.read_text(encoding="utf-8"))
    figure_summary["generated_figures"][0]["figure_id"] = "figure_" + ("very_long_" * 30)
    figure_summary["generated_figures"][0]["group_by"] = "group_" + ("very_long_" * 30)
    figure_summary["generated_figures"][0]["source_metrics"] = "metrics/" + ("very_long_path_" * 30) + "normalized_metrics.csv"
    figure_summary_path.write_text(json.dumps(figure_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    result = invoke(tmp_path, ["slides", task_id])

    assert result.exit_code == 0
    assert_readable_deck(task_path / "slides" / "presentation-draft.pptx", min_slides=6, max_slides=8)
    summary = json.loads((task_path / "slides" / "slides-summary.json").read_text(encoding="utf-8"))
    assert summary["caption_truncations"]
    assert "very_long" in summary["caption_truncations"][0]["full"]
    assert summary["qa_checks"]["caption_overflow_guard"]["passed"] is True


def test_slides_repeated_run_after_table_enhancements_does_not_duplicate_manifest_artifacts(tmp_path: Path) -> None:
    copy_examples(tmp_path)
    assert invoke(tmp_path, ["init"]).exit_code == 0
    task_id = extract_task_id(invoke(tmp_path, ["ingest", "examples/project-presentation-pack"]).output)
    assert invoke(tmp_path, ["collect", task_id]).exit_code == 0
    assert invoke(tmp_path, ["figures", task_id]).exit_code == 0

    assert invoke(tmp_path, ["slides", task_id, "--template", "zh-project"]).exit_code == 0
    assert invoke(tmp_path, ["slides", task_id, "--template", "zh-project"]).exit_code == 0

    manifest = read_manifest(tmp_path, task_id)
    artifact_ids = [artifact["artifact_id"] for artifact in manifest["artifacts"]]
    assert artifact_ids.count("slides_presentation_draft_pptx") == 1
    assert artifact_ids.count("slides_summary_json") == 1
