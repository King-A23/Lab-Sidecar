# Post-Open-Source Stage 1 Acceptance

Date: 2026-06-17

## Phase Goal

Stage 1 improves CLI-first task navigation and conservative metric comparison. Users can list tasks, inspect a compact status dashboard, summarize a task without opening raw directories or full logs, and compare 2-5 local tasks that have collected metrics.

## Starting State

- `labsidecar list` showed only task id, status, update time, and optional name.
- `labsidecar status <task_id>` showed basic task state but not a compact artifact dashboard.
- There was no `summarize <task_id>` command.
- There was no `compare <task_id...>` command.

## Changed Files

- `lab_sidecar/cli/app.py`
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`
- `docs/post-open-source-stage-1-acceptance.md`

Pre-existing local changes were present in `PRODUCT_ITERATION_PLAN.md`, `docs/post-open-source-product-roadmap.md`, and `docs/post-open-source-stage-1-plan.md`; this Stage 1 work did not revert them.

## CLI Scenarios

- `list` now prints scan-friendly columns: task id, status, created time, finished time, updated time, artifact count, and name.
- `list --status pending|running|completed|failed|cancelled` filters through Typer enum validation.
- `status <task_id>` now shows task identity, mode, command or source path, artifact directory, artifact counts, key artifact paths, failure diagnostics, and next commands.
- `summarize <task_id>` shows bounded task digest information from the manifest and existing summary files.
- `compare <task_id...>` accepts 2-5 tasks, reads `metrics/normalized_metrics.csv`, compares final rows for common numeric fields, lists skipped fields, and avoids statistical interpretation.
- Missing tasks, missing metrics, no common numeric metrics, too few task ids, and too many task ids return clear messages with stable exit codes.

## Workspaces And Task IDs

Manual smoke workspace:

```text
/tmp/lab-sidecar-stage-1-lBAfGn
```

Manual smoke tasks:

```text
task_20260617_212517_c1962f  stage1 simple
task_20260617_212517_892f45  stage1 csv comparison
```

Manual commands run:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run ".venv/bin/python examples/simple-success/train.py --output metrics.csv" --name "stage1 simple"
python -m lab_sidecar.cli.app ingest examples/csv-comparison --name "stage1 csv comparison"
python -m lab_sidecar.cli.app list
python -m lab_sidecar.cli.app collect task_20260617_212517_c1962f
python -m lab_sidecar.cli.app collect task_20260617_212517_892f45
python -m lab_sidecar.cli.app summarize task_20260617_212517_c1962f
python -m lab_sidecar.cli.app compare task_20260617_212517_c1962f task_20260617_212517_892f45
python -m lab_sidecar.cli.app list --status completed
```

Observed compare output included common numeric fields `epoch`, `val_loss`, and `val_accuracy`, plus skipped task-specific fields. No full log bodies, report body, PPT content, or full metrics rows were printed.

## Generated Artifacts

Manual smoke generated task-local artifacts under:

```text
/tmp/lab-sidecar-stage-1-lBAfGn/.lab-sidecar/tasks/task_20260617_212517_c1962f/
/tmp/lab-sidecar-stage-1-lBAfGn/.lab-sidecar/tasks/task_20260617_212517_892f45/
```

Both manual tasks produced:

```text
metrics/normalized_metrics.csv
metrics/normalized_metrics.json
metrics/collection-summary.json
```

## Test Results

Validation was run from the repository root using the existing `.venv` dev environment because the bare system `python` did not have Typer installed.

```text
git diff --check
Result: passed
```

```text
source .venv/bin/activate && python -m pytest tests/test_cli_smoke.py -q
Result: 78 passed in 6.94s
```

```text
source .venv/bin/activate && python -m pytest -q
Result: 123 passed in 8.99s
```

Manual edge checks:

```text
compare task_20260617_212517_c1962f task_missing
Result: exit code 3 with missing task hint.
```

```text
compare with 6 task ids
Result: exit code 2 with "compare supports at most 5 task ids."
```

Focused automated coverage added for:

- empty and filtered task lists
- missing manifests during list
- completed, ingested, failed, and cancelled status dashboards
- summarize before and after generated artifacts
- failed summarize with bounded command and failure text
- compare success for shared numeric metrics
- missing metrics, no common numeric fields, too few ids, and too many ids

## Blocking

No implementation blockers remain.

## Follow-Up

- Consider adding optional machine-readable output in a later stage if users need scripting support.
- Consider improving compare formatting if future examples contain many shared numeric fields.

## Out Of Scope

This stage did not add Web UI, FastAPI, remote execution, cloud sync, statistical significance testing, default AI analysis, generic multi-agent behavior, MCP contract changes, or V2 host behavior changes.

## Final Judgment

Accepted. Stage 1 now lets a user find, summarize, and conservatively compare local tasks from the CLI without opening raw task directories or reading full logs first.
