# Post-Open-Source Stage 1 Plan: Task Navigation And Comparison

Date: 2026-06-17

## 1. Phase Goal

Improve Lab-Sidecar's day-to-day task navigation after open-source release.

The user should be able to inspect a busy workspace, find the right task, understand its artifact state, and compare small experiment results without opening raw task directories or full logs first.

This stage is intentionally CLI-first and file-first. It should not add Web UI, FastAPI, remote execution, cloud sync, or a new product surface.

## 1.1 Product Promise

After Stage 1, a user should be able to run:

```bash
labsidecar list
labsidecar summarize <task_id>
labsidecar compare <task_id_a> <task_id_b>
```

and understand:

- which tasks exist
- which tasks succeeded or failed
- what artifacts are ready
- where to inspect the files
- whether two small result tasks share comparable metrics

without reading full stdout/stderr or manually navigating `.lab-sidecar/tasks/`.

## 2. Current Baseline

Current useful surface:

- `list --limit` lists recent tasks from manifests.
- `open <task_id>` prints the task artifact directory.
- `status <task_id>` refreshes status and prints basic task state.
- `logs <task_id>` prints bounded stdout/stderr tails.
- `artifacts <task_id>` lists manifest artifacts.
- `collect`, `figures`, `report`, and `slides` already print next-step hints.

Current gaps:

- `list` has no status filter, artifact summary, created/finished columns, or richer scan-friendly layout.
- `status` does not yet act as a compact task dashboard.
- There is no `summarize <task_id>` command for a clean task-level digest.
- There is no `compare <task_id...>` command for small cross-task metric comparison.
- Users still need to know where normalized metrics and summaries live before comparing runs.

## 3. Non-Goals

Do not implement during this stage:

- packaging / zip export
- recursive real-world result discovery beyond current collection behavior
- new AI provider behavior
- report or slide template redesign
- MCP contract changes unless required by CLI behavior
- Web UI or API
- statistical significance testing
- automatic scientific interpretation
- multi-workspace aggregation
- changing artifact directory layout
- changing existing `run -> collect -> figures -> report -> slides` behavior

## 4. Work Slice A: Stronger `list`

### Target Behavior

Extend `labsidecar list` into a scan-friendly task index.

Suggested options:

```bash
labsidecar list --limit 20
labsidecar list --status completed
labsidecar list --status failed --limit 10
```

Accepted option set:

- `--limit <N>`: already exists and should keep working
- `--status <status>`: optional filter over `pending`, `running`, `completed`, `failed`, `cancelled`

Suggested output columns:

```text
task_id                         status      updated_at              artifacts  name
task_20260617_111002_1b15c8     completed   2026-06-17T11:10:04    17         simple success
task_20260617_111005_1e1d16     failed      2026-06-17T11:12:45    8          failure smoke
```

### Implementation Notes

- Keep data source manifest-first.
- Use `RunnerService.refresh()` when safe so stale running tasks are updated.
- Preserve deterministic ordering by recency.
- Keep output human-readable. JSON output is not required in this stage.

### Tests

- Empty workspace still prints `No tasks found.`
- `--limit` keeps deterministic ordering.
- `--status completed` filters completed tasks.
- `--status failed` filters failed tasks.
- Invalid `--status` fails through Typer enum validation.
- Missing or stale task manifests do not crash the list command.

## 5. Work Slice B: Dashboard-Like `status`

### Target Behavior

Make `labsidecar status <task_id>` answer:

- What happened?
- Where are the artifacts?
- What should I do next?
- If it failed, where is the useful diagnostic entrypoint?

Suggested additions:

- task name, mode, working dir or source path
- artifact type counts
- key artifact paths when present:
  - `metrics/normalized_metrics.csv`
  - `figures/figure-summary.json`
  - `reports/report-fragment.md`
  - `slides/presentation-draft.pptx`
- concise failure summary for failed tasks

### Tests

- Completed run status includes task dir, artifact count, and next commands.
- Ingested task status includes source path.
- Failed task status includes failure summary and stderr log hint.
- Running task status keeps bounded output and does not print full logs.
- Cancelled task status offers artifacts/logs inspection rather than collect.
- Missing task exits with code 3.

## 6. Work Slice C: New `summarize`

### Target Behavior

Add a compact task digest:

```bash
labsidecar summarize <task_id>
```

It should return bounded information only:

- task id, name, status, mode
- source path or command preview
- artifact index
- metrics row count when `metrics/collection-summary.json` exists
- generated figure count when `figures/figure-summary.json` exists
- report and slides paths when present
- next likely commands

It must not print:

- full stdout
- full stderr
- full normalized metrics rows
- report body
- PPT contents

### Implementation Notes

- Prefer reading existing summary files instead of recomputing.
- If a summary file is missing, show `(not generated)` rather than failing.
- Treat this as the CLI equivalent of a bounded Agent preview.
- Reuse small local helper functions from `lab_sidecar/cli/app.py` or add a thin CLI helper module only if that reduces duplication.
- Keep command previews bounded. Do not print arbitrarily long command strings.

### Tests

- Before `collect`, summarize reports missing metrics cleanly.
- After full `collect -> figures -> report -> slides`, summarize lists the major artifacts.
- Failed task summarize does not present the run as successful.
- Output does not include full log bodies.
- Long commands are capped or previewed, not printed in full.

## 7. Work Slice D: New `compare`

### Target Behavior

Add a small cross-task comparison command:

```bash
labsidecar compare <task_id> <task_id> [task_id...]
```

Initial scope:

- support 2-5 tasks
- read `metrics/normalized_metrics.csv`
- compare shared numeric metric fields
- show final row per task by stable row order
- show artifact path references
- fail gracefully when metrics are missing

Suggested output:

```text
Compared tasks: 3

| task_id | status | metric | value | source |
| --- | --- | --- | --- | --- |
| task_a | completed | val_accuracy | 0.86 | metrics/normalized_metrics.csv |
| task_b | completed | val_accuracy | 0.89 | metrics/normalized_metrics.csv |
```

### First-Pass Rules

- Do not infer scientific conclusions.
- Do not claim significance.
- Do not aggregate mean/std unless the input clearly contains seed-like grouping and the implementation has tests for it.
- If fields differ, list common fields and skipped fields.
- If no common numeric fields exist, exit with a clear message and code 5.
- Exclude metadata columns such as `source_file` from numeric comparison.
- Treat numeric parsing conservatively. A column is comparable only when every non-empty compared value parses as a number.
- Keep output table small. The first version may show only shared numeric fields and one final row per task.

### Tests

- Compares two completed tasks with shared metrics.
- Handles one task without metrics with exit code 5 and a clear hint.
- Handles no common numeric fields with exit code 5.
- Rejects fewer than 2 task ids with code 2 or Typer validation.
- Rejects more than 5 task ids with a clear error.
- Does not include full metrics rows beyond the selected comparison rows.

## 8. Implementation Boundaries

### Likely Files To Edit

- `lab_sidecar/cli/app.py`
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`
- `docs/post-open-source-stage-1-acceptance.md`

Optional helper module if `app.py` becomes hard to scan:

- `lab_sidecar/cli/summaries.py`

Avoid touching:

- `lab_sidecar/mcp/`
- `lab_sidecar/intelligence/`
- report/slides rendering internals
- storage schema, unless strictly necessary

## 9. Concrete Acceptance Standards

Stage 1 is complete only when all of the following are true:

1. `labsidecar list` remains compatible with current usage and gains status filtering.
2. `labsidecar status <task_id>` shows task identity, artifact directory, artifact count, and useful next actions.
3. `labsidecar summarize <task_id>` exists and returns bounded task digest information.
4. `labsidecar compare <task_id...>` exists and compares 2-5 completed metric-bearing tasks.
5. Missing metrics, missing tasks, non-comparable metrics, and too many task IDs fail with clear messages.
6. No command prints complete stdout, stderr, report body, PPT content, or full metrics rows by default.
7. Existing `run -> collect -> figures -> report -> slides` tests still pass.
8. Documentation names the new commands without overclaiming statistical or research interpretation.
9. `docs/post-open-source-stage-1-acceptance.md` records the actual validation evidence.

## 10. Documentation Updates

Update:

- `README.md` CLI command table
- `docs/public-alpha-quickstart.md` or a post-open-source quickstart note if needed
- `docs/cli-spec.md` with `summarize` and `compare`
- `docs/post-open-source-stage-1-acceptance.md` after implementation

Keep public claims cautious. The new commands help navigate and compare local artifacts; they do not turn Lab-Sidecar into an experiment tracking platform or statistical analysis system.

## 11. Validation Commands

Run before acceptance:

```bash
git diff --check
python -m pytest tests/test_cli_smoke.py -q
python -m pytest -q
```

If implementation touches MCP/V2 response helpers, also run:

```bash
python -m pytest tests/test_mcp_tools.py -q
python -m pytest tests/test_v2_host_integration.py tests/test_v2_worker_invocation.py -q
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-1-mcp-smoke
```

Also run a manual CLI smoke in a temporary workspace and record the task ids:

```bash
tmpdir="$(mktemp -d /tmp/lab-sidecar-stage-1-XXXXXX)"
cp -R examples "$tmpdir/examples"
cd "$tmpdir"
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv" --name "stage1 simple"
python -m lab_sidecar.cli.app ingest examples/csv-comparison --name "stage1 csv comparison"
python -m lab_sidecar.cli.app list
python -m lab_sidecar.cli.app collect <task_id_a>
python -m lab_sidecar.cli.app collect <task_id_b>
python -m lab_sidecar.cli.app summarize <task_id_a>
python -m lab_sidecar.cli.app compare <task_id_a> <task_id_b>
```

## 12. Acceptance Record Template

Create `docs/post-open-source-stage-1-acceptance.md` with:

```markdown
# Post-Open-Source Stage 1 Acceptance

## Phase Goal

## Starting State

## Changed Files

## CLI Scenarios

## Workspaces And Task IDs

## Generated Artifacts

## Test Results

## Blocking

## Follow-Up

## Out Of Scope

## Final Judgment
```

Stage 1 is accepted only when the CLI can help a user find, summarize, and compare local tasks without reading raw logs or manually opening task directories first.

## 13. Suggested Goal-Mode Objective

Use this objective when starting the implementation goal:

```text
Implement Lab-Sidecar Post-Open-Source Stage 1: Task Navigation And Comparison.

Read docs/post-open-source-stage-1-plan.md first and treat it as the source of truth. Improve the CLI so users can find, summarize, and compare local tasks without opening raw task directories or full logs. Implement stronger list/status behavior, add bounded summarize, add conservative compare for 2-5 metric-bearing tasks, update README and docs/cli-spec.md, add focused tests, run the required validation commands, and finish by writing docs/post-open-source-stage-1-acceptance.md with evidence.

Stay inside the existing local-first, file-first, CLI-first product boundary. Do not add Web UI, FastAPI, remote runner, cloud sync, statistical significance claims, default AI analysis, or generic multi-agent behavior. Avoid lab_sidecar/mcp and lab_sidecar/intelligence unless an existing test proves a small shared helper change is required.
```

## 14. Stage 1 Acceptance Checklist

Before marking the goal complete, confirm:

- [ ] `list` supports the new filtering and layout contract
- [ ] `status` shows artifact directory, artifact count, and next actions
- [ ] `summarize` exists and remains bounded
- [ ] `compare` exists and works for 2-5 tasks with shared numeric metrics
- [ ] Missing task and missing metrics behavior is explicit and stable
- [ ] The CLI does not leak full logs or report bodies by default
- [ ] `tests/test_cli_smoke.py` passes
- [ ] `python -m pytest -q` passes
- [ ] README and CLI spec mention the new commands
- [ ] `docs/post-open-source-stage-1-acceptance.md` captures task ids, workspaces, commands, and final judgment
