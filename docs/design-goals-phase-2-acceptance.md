# Design Goals Phase 2 Acceptance

Date: 2026-06-05

Phase: Phase 2 - Long Experiment Sidecar Core

## Scope

Hardened the local CLI background runner so the long-experiment sidecar path can be inspected, cancelled, and recovered from stale `running` manifests without adding Web UI, FastAPI, remote runner, MCP changes, AI workflows, animation, hosted services, or a generic multi-agent product architecture.

Phase 2 stayed inside the local CLI/runner/test surface:

- `run --background`
- `status`
- `logs --tail`
- `logs --stream`
- `cancel`
- minimal `list`
- minimal `open`

## Initial Checks

Initial workspace:

```text
C:\code\Lab-Sidecar
```

Initial command:

```powershell
git status --short
```

Result:

```text
(clean)
```

Documents read:

- `AGENTS.md`
- `PRODUCT_ITERATION_PLAN.md`
- `docs/design-goals-completion-plan.md`
- `docs/design-goals-gap-matrix.md`

Relevant code and tests inspected:

- `lab_sidecar/runner/service.py`
- `lab_sidecar/runner/process.py`
- `lab_sidecar/runner/worker.py`
- `lab_sidecar/cli/app.py`
- `lab_sidecar/core/manifest.py`
- `lab_sidecar/storage/sqlite_index.py`
- `tests/test_cli_smoke.py`

## Changed Files

- `lab_sidecar/runner/service.py`
- `lab_sidecar/cli/app.py`
- `tests/test_cli_smoke.py`
- `docs/design-goals-phase-2-acceptance.md`

## Commands

Targeted tests:

```powershell
py -3 -m pytest tests\test_cli_smoke.py -k "background or stale or list_and_open"
```

External workspace cancel smoke:

```powershell
$workspace = Join-Path $env:TEMP 'lab-sidecar-design-phase2'
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run 'py -3 phase2_long_task.py' --background
py -3 -m lab_sidecar.cli.app status <task_id>
py -3 -m lab_sidecar.cli.app logs <task_id> --stream stdout --tail 5
py -3 -m lab_sidecar.cli.app cancel <task_id>
py -3 -m lab_sidecar.cli.app status <task_id>
```

External workspace completed refresh smoke:

```powershell
py -3 -m lab_sidecar.cli.app run 'py -3 phase2_quick_task.py' --background
py -3 -m lab_sidecar.cli.app status <task_id>
py -3 -m lab_sidecar.cli.app logs <task_id> --stream stdout --tail 5
```

Full validation:

```powershell
py -3 -m pytest
git status --short
```

## Workspace Paths

Repository workspace:

```text
C:\code\Lab-Sidecar
```

External Phase 2 CLI smoke workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2
```

External scripts created for smoke validation:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\phase2_long_task.py`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\phase2_quick_task.py`

## Task ID Values

External workspace task ids:

- Cancel smoke: `task_20260605_175146_5e62f6`
- Completed refresh smoke: `task_20260605_175253_ca4404`

Pytest task ids were generated under pytest temporary directories and were not retained as acceptance artifacts.

## Generated Artifacts

External cancel smoke artifacts:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\manifest.json`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\stdout.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\stderr.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\worker.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\worker.err.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\reproduce\command.txt`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175146_5e62f6\reproduce\env.json`

External completed refresh artifacts:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\manifest.json`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\stdout.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\stderr.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\worker.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\worker.err.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\reproduce\command.txt`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase2\.lab-sidecar\tasks\task_20260605_175253_ca4404\reproduce\env.json`

Repository artifact generated:

- `docs/design-goals-phase-2-acceptance.md`

## Implementation Summary

- `RunnerService.refresh` now upserts non-running and still-running manifest state back into SQLite, so deleting `index.sqlite` does not prevent file-based inspection and status refresh can rebuild the index.
- Background worker launch no longer overwrites a task that was already finalized by a fast worker before the parent writes `worker_pid`.
- Stale `running` manifests now converge to `failed` with a diagnostic in `stderr.log` if neither child nor worker process can be verified and the worker did not finalize the manifest.
- `cancel` still preserves logs, appends a cancellation note, marks `cancelled`, clears PID fields, and upserts the manifest/index state.
- Added `list` as a small manifest-backed task listing command.
- Added `open` as a small command that prints the task artifact directory path. It does not launch a system file manager or modify files.

## Test Results

Targeted tests:

```text
6 passed, 59 deselected in 25.26s
```

External cancel smoke result:

```text
Task: task_20260605_175146_5e62f6
Status: running
logs --tail showed phase2-tick output
Cancellation requested: task_20260605_175146_5e62f6
Status: cancelled
```

External completed refresh smoke result:

```text
Task: task_20260605_175253_ca4404
Status: completed
Exit code: 0
logs --tail showed phase2-complete-start and phase2-complete-done
```

Full test suite:

```text
72 passed in 144.61s
```

Pre-acceptance status before writing this record:

```text
 M lab_sidecar/cli/app.py
 M lab_sidecar/runner/service.py
 M tests/test_cli_smoke.py
```

Final `git status --short` before commit:

```text
 M lab_sidecar/cli/app.py
 M lab_sidecar/runner/service.py
 M tests/test_cli_smoke.py
?? docs/design-goals-phase-2-acceptance.md
```

## Blocking

- None for Phase 2.

## Follow-Up

- Phase 3: add and validate MCP cancellation only after this runner/cancel behavior is committed.
- Phase 5: enrich provenance with Git/dependency/source-hash metadata.
- Later product hardening: sophisticated scheduler, queues, resource limits, and remote execution remain out of scope.

## Out Of Scope

- Remote runner.
- Web monitoring UI.
- FastAPI.
- MCP tool changes.
- OS/container sandboxing.
- AI polishing or autonomous analysis.
- Animation, GIF, MP4, Manim/Remotion, or PowerPoint native animation.
- Generic multi-agent product architecture.

## Final Judgment

Phase 2 passes. The local long-experiment sidecar core now has tested coverage for background start, status refresh to completed, background failure finalization, cancellation with PID cleanup, file-first inspection after SQLite deletion, stale worker recovery diagnostics, and small manifest-backed `list` / `open` commands.

Recommendation: proceed to Phase 3 after committing this Phase 2 baseline.
