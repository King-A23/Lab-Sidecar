# Design Goals Phase 5 Acceptance

Date: 2026-06-05

## Phase Goal

Phase 5 improved reproducibility and artifact completeness so generated outputs can be traced to task records, collected sources, figure summaries, report summaries, slide summaries, logs, and reproduce metadata.

The accepted behavior is:

- Run-mode tasks write `reproduce/command.txt`, `reproduce/env.json`, `reproduce/git.json`, and `reproduce/dependencies.json`.
- `reproduce/env.json` records Python version, Python executable, platform, working directory, selected environment variables, and links to Git/dependency snapshots.
- `reproduce/git.json` records whether the task cwd is in a Git repository; repository cwd snapshots include commit/status via `lab_sidecar.core.provenance.git_snapshot`.
- Ingest source refs and collection summaries record `sha256` and `size_bytes` for source files.
- Report summaries and slide summaries expose `generated_from` / `source_artifacts` pointing back to manifest, metrics, collection summary, figures, logs, report, and reproduce metadata.
- Manifest artifact source paths for report and slides include those traceability inputs.
- SQLite remains an index; all provenance is inspectable from task-local files.

## Changed Files

- `lab_sidecar/core/provenance.py`
- `lab_sidecar/runner/service.py`
- `lab_sidecar/storage/artifact_store.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/reports/service.py`
- `lab_sidecar/slides/service.py`
- `tests/test_cli_smoke.py`
- `docs/design-goals-phase-5-acceptance.md`

## Workspace Paths

Repository workspace:

- `C:\code\Lab-Sidecar`

External acceptance workspace:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase5`

Task directory:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase5\.lab-sidecar\tasks\task_20260605_183028_329388`

## Task ID Values

- CLI reproducibility/provenance smoke: `task_20260605_183028_329388`

## Commands

Phase entrance:

```powershell
git status --short
Get-Content -LiteralPath docs\design-goals-completion-plan.md
rg -n "reproduce|env.json|command.txt|git|dependency|hash|source_refs|summary|source_paths|artifacts" lab_sidecar tests docs -g "*.py" -g "*.md"
```

Focused tests:

```powershell
py -3 -m pytest tests\test_cli_smoke.py -k "simple_success_task_and_queries or ingest_existing_directory or ingest_existing_file or collect_csv_comparison_ingest_generates_normalized_metrics or report_completed_ingest_after_collect_and_figures_generates_markdown or slides_after_collect_figures_report_generates_pptx_and_summary"
```

External workspace acceptance:

```powershell
$workspace = Join-Path $env:TEMP 'lab-sidecar-design-phase5'
Remove-Item -LiteralPath $workspace -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $workspace
Copy-Item -Recurse -LiteralPath 'C:\code\Lab-Sidecar\examples' -Destination (Join-Path $workspace 'examples')
Push-Location $workspace
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv"
py -3 -m lab_sidecar.cli.app collect task_20260605_183028_329388
py -3 -m lab_sidecar.cli.app figures task_20260605_183028_329388
py -3 -m lab_sidecar.cli.app report task_20260605_183028_329388
py -3 -m lab_sidecar.cli.app slides task_20260605_183028_329388
py -3 -m lab_sidecar.cli.app artifacts task_20260605_183028_329388
Pop-Location
```

Required full validation:

```powershell
py -3 -m pytest
git status --short
```

## Generated Artifacts

External acceptance task artifacts:

- `.lab-sidecar/tasks/task_20260605_183028_329388/manifest.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/stdout.log`
- `.lab-sidecar/tasks/task_20260605_183028_329388/stderr.log`
- `.lab-sidecar/tasks/task_20260605_183028_329388/reproduce/command.txt`
- `.lab-sidecar/tasks/task_20260605_183028_329388/reproduce/env.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/reproduce/git.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/reproduce/dependencies.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/task_20260605_183028_329388/metrics/normalized_metrics.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/metrics/collection-summary.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/figures/line_val_accuracy_over_epoch.png`
- `.lab-sidecar/tasks/task_20260605_183028_329388/figures/line_val_accuracy_over_epoch.svg`
- `.lab-sidecar/tasks/task_20260605_183028_329388/figures/line_train_loss_over_epoch.png`
- `.lab-sidecar/tasks/task_20260605_183028_329388/figures/line_train_loss_over_epoch.svg`
- `.lab-sidecar/tasks/task_20260605_183028_329388/figures/figure-spec.yaml`
- `.lab-sidecar/tasks/task_20260605_183028_329388/figures/figure-summary.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/reports/report-fragment.md`
- `.lab-sidecar/tasks/task_20260605_183028_329388/reports/report-summary.json`
- `.lab-sidecar/tasks/task_20260605_183028_329388/slides/presentation-draft.pptx`
- `.lab-sidecar/tasks/task_20260605_183028_329388/slides/slides-summary.json`

Key provenance evidence:

- `metrics/collection-summary.json` records `metrics.csv` with `size_bytes=128` and `sha256=afd106c8d0a215e7ad04f09ff55c35f724bfff92972067735c1a3df0503d02c1`.
- `reports/report-summary.json` records `generated_from` with `manifest.json`, `metrics/normalized_metrics.csv`, `metrics/collection-summary.json`, `figures/figure-summary.json`, `stdout.log`, `stderr.log`, and reproduce files.
- `slides/slides-summary.json` records `generated_from` with manifest, metrics, collection summary, figure summary, report, logs, reproduce files, and included PNG figures.
- `manifest.json` records report and slides artifact `source_paths` that point to the same task-local provenance files.

## Test Results

- Focused Phase 5 tests: `6 passed, 62 deselected`
- `py -3 -m pytest`: `78 passed`

## Blocking / Follow-Up / Out Of Scope

Blocking:

- None.

Follow-up:

- Lockfile-specific dependency parsers remain future work.
- Dataset/version provenance beyond file hashes remains future work.
- External acceptance workspace was not inside a Git repository, so its `reproduce/git.json` correctly recorded `is_repository=false`; direct repository test coverage verifies the Git repository branch records commit/status.

Out of scope for Phase 5:

- Cloud provenance service.
- Team audit system.
- Web UI, FastAPI, remote runner, hosted service, animation, or generic multi-agent framework.
- MCP changes; Phase 5 did not modify MCP behavior and therefore did not require MCP stdio smoke.
- CLI long-task lifecycle changes; Phase 5 did not modify background runner behavior.

## Final Judgment

Phase 5 passes. Run tasks, collected inputs, reports, slides, and manifests now contain enough task-local provenance for a user to trace commands, runtime context, dependencies, Git state where available, collected file hashes, generated figures, report inputs, and slide inputs. The repository can proceed to Phase 6: Real V1 Acceptance.
