# Phase 1 Status

Current phase: Phase 1, CLI Experiment Runner.

## Completed Commands

- `init`
- `run`
- `run --background`
- `run --detach`
- `status`
- `logs`
- `artifacts`
- `cancel`
- `ingest`

## Validation

Primary regression command:

```powershell
py -3 -m pytest
```

Manual smoke coverage:

- workspace initialization
- synchronous success and failure runs
- background long-running task status/logs/cancel
- completed, failed, running, and cancelled status display
- stdout/stderr log reading
- artifact listing
- ingest directory and file tasks
- status/logs/artifacts after deleting `.lab-sidecar/index.sqlite`

## Known Limits

- Phase 1 records task outputs but does not extract metrics.
- `ingest` records source references only; it does not copy source files.
- Directory ingest scans only one level.
- Background task recovery is file-first; if the worker is externally killed, status is conservative and does not infer completion without reliable evidence.

## Phase 2 Prerequisites

- Keep `manifest.json` as the task source of truth.
- Add collectors only after preserving current CLI behavior.
- Continue writing generated artifacts only under `.lab-sidecar/tasks/<task_id>/`.
