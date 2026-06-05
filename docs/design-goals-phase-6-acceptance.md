# Design Goals Phase 6 Acceptance

Date: 2026-06-05

## Phase Goal

Phase 6 performed the final V1 acceptance pass after Phases 1-5. The acceptance target was the original V1 product goal:

```text
local-first experiment Sidecar
  + context quarantine
  + artifact-first delegation layer
  + reproducible report artifacts
```

This phase did not add Web UI, FastAPI, remote runners, hosted services, AI polishing, animation, or a generic multi-agent framework. The only code changes were minimal reliability fixes found during the final MCP stdio smoke:

- `git_snapshot()` now avoids invoking `git` when no parent `.git` marker exists, preventing a clean non-repository stdio workspace from hanging on host-specific Git prompts.
- Dependency provenance now records a bounded list of key Lab-Sidecar runtime packages instead of enumerating every installed distribution.
- `scripts/mcp_stdio_smoke.py` now records a progress JSONL trace and gives cold-start `run_experiment` calls a 60 second timeout.

## Changed Files

- `lab_sidecar/core/provenance.py`
- `scripts/mcp_stdio_smoke.py`
- `docs/design-goals-phase-6-acceptance.md`

## Workspace Paths

Repository workspace:

- `C:\code\Lab-Sidecar`

External CLI acceptance workspace:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-v1-cli`

External MCP stdio acceptance workspace:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-v1-mcp`

PPTX render / visual acceptance workspace:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-v1-render`

## Task ID Values

CLI scenarios:

- Long successful background run: `task_20260605_183634_fe3047`
- Failed run diagnostic scenario: `task_20260605_183723_5490bf`
- Explicit multi-result config scenario: `task_20260605_183804_752960`
- Course/project presentation scenario: `task_20260605_183842_6e4e99`
- Cancelled long task scenario: `task_20260605_183922_6fb24b`

MCP stdio scenarios:

- Earlier rendered MCP deck: `task_20260605_190417_1569a6`
- Earlier MCP cancellation task: `task_20260605_190423_cf289a`
- Final required MCP smoke completed task: `task_20260605_191203_f266a6`
- Final required MCP smoke cancellation task: `task_20260605_191207_27b108`

## Commands

Phase entrance and governing-doc review:

```powershell
git status --short
Get-Content -Raw AGENTS.md
Get-Content -Raw PRODUCT_ITERATION_PLAN.md
Get-Content -Raw docs\design-goals-completion-plan.md
git diff -- lab_sidecar/core/provenance.py scripts/mcp_stdio_smoke.py
```

Representative external CLI acceptance flow:

```powershell
$workspace = Join-Path $env:TEMP 'lab-sidecar-design-v1-cli'
Push-Location $workspace
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv" --background
py -3 -m lab_sidecar.cli.app status task_20260605_183634_fe3047
py -3 -m lab_sidecar.cli.app logs task_20260605_183634_fe3047 --tail 20
py -3 -m lab_sidecar.cli.app collect task_20260605_183634_fe3047
py -3 -m lab_sidecar.cli.app figures task_20260605_183634_fe3047
py -3 -m lab_sidecar.cli.app report task_20260605_183634_fe3047
py -3 -m lab_sidecar.cli.app slides task_20260605_183634_fe3047
py -3 -m lab_sidecar.cli.app artifacts task_20260605_183634_fe3047
Pop-Location
```

Failure, explicit-config, project, and cancellation flows:

```powershell
Push-Location $env:TEMP\lab-sidecar-design-v1-cli
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-failure/fail.py"
py -3 -m lab_sidecar.cli.app status task_20260605_183723_5490bf
py -3 -m lab_sidecar.cli.app logs task_20260605_183723_5490bf --stream stderr --tail 20
py -3 -m lab_sidecar.cli.app report task_20260605_183723_5490bf
py -3 -m lab_sidecar.cli.app slides task_20260605_183723_5490bf --template en-summary
py -3 -m lab_sidecar.cli.app artifacts task_20260605_183723_5490bf

py -3 -m lab_sidecar.cli.app ingest examples/csv-comparison
py -3 -m lab_sidecar.cli.app collect task_20260605_183804_752960 --config explicit-metrics.yaml
py -3 -m lab_sidecar.cli.app figures task_20260605_183804_752960 --spec explicit-figure.yaml
py -3 -m lab_sidecar.cli.app report task_20260605_183804_752960 --template en-paper
py -3 -m lab_sidecar.cli.app slides task_20260605_183804_752960 --template zh-summary
py -3 -m lab_sidecar.cli.app artifacts task_20260605_183804_752960

py -3 -m lab_sidecar.cli.app ingest examples/project-presentation-pack
py -3 -m lab_sidecar.cli.app collect task_20260605_183842_6e4e99
py -3 -m lab_sidecar.cli.app figures task_20260605_183842_6e4e99
py -3 -m lab_sidecar.cli.app report task_20260605_183842_6e4e99 --template zh-summary
py -3 -m lab_sidecar.cli.app slides task_20260605_183842_6e4e99 --template zh-project
py -3 -m lab_sidecar.cli.app artifacts task_20260605_183842_6e4e99

py -3 -m lab_sidecar.cli.app run "<long task command>" --background
py -3 -m lab_sidecar.cli.app status task_20260605_183922_6fb24b
py -3 -m lab_sidecar.cli.app logs task_20260605_183922_6fb24b --tail 20
py -3 -m lab_sidecar.cli.app cancel task_20260605_183922_6fb24b
py -3 -m lab_sidecar.cli.app status task_20260605_183922_6fb24b
py -3 -m lab_sidecar.cli.app report task_20260605_183922_6fb24b
py -3 -m lab_sidecar.cli.app slides task_20260605_183922_6fb24b
py -3 -m lab_sidecar.cli.app artifacts task_20260605_183922_6fb24b
Pop-Location
```

Required MCP stdio acceptance:

```powershell
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-v1-mcp"
```

Final validation:

```powershell
py -3 -m pytest
git status --short
```

Public-doc overclaim audit:

```powershell
rg -n "complete V1|full V1|V1 complete|design goal|public-alpha|public alpha|Phase 6|Phase 6" README.md docs -g "*.md"
```

PPTX visual acceptance:

```powershell
soffice.com --headless --convert-to pdf --outdir <render-dir> <task>\slides\presentation-draft.pptx
pdftoppm.exe -jpeg -r 120 <render-dir>\presentation-draft.pdf <render-dir>\slide
```

## Generated Artifacts

Successful background run, `task_20260605_183634_fe3047`:

- `.lab-sidecar/tasks/task_20260605_183634_fe3047/manifest.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/stdout.log`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/stderr.log`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/metrics/collection-summary.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/figures/line_accuracy_over_epoch.png`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/figures/line_accuracy_over_epoch.svg`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/figures/line_loss_over_epoch.png`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/figures/line_loss_over_epoch.svg`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/figures/figure-summary.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/reports/report-fragment.md`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/reports/report-summary.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/reproduce/command.txt`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/reproduce/env.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/reproduce/git.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/reproduce/dependencies.json`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/slides/presentation-draft.pptx`
- `.lab-sidecar/tasks/task_20260605_183634_fe3047/slides/slides-summary.json`

Failed diagnostic run, `task_20260605_183723_5490bf`:

- `manifest.json`
- `stderr.log`
- `stdout.log`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

Explicit multi-result config, `task_20260605_183804_752960`:

- `raw/source_refs.json`
- `metrics/normalized_metrics.csv`
- `metrics/collection-summary.json`
- `figures/explicit_accuracy_by_model.png`
- `figures/explicit_accuracy_by_model.svg`
- `figures/figure-spec.yaml`
- `figures/figure-summary.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

Course/project presentation, `task_20260605_183842_6e4e99`:

- `raw/source_refs.json`
- `metrics/normalized_metrics.csv`
- `metrics/collection-summary.json`
- `figures/bar_accuracy_by_model.png`
- `figures/bar_accuracy_by_model.svg`
- `figures/figure-summary.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

Cancelled long task, `task_20260605_183922_6fb24b`:

- `manifest.json`
- `stdout.log`
- `stderr.log`
- `worker.log`
- `worker.err.log`
- `reproduce/command.txt`
- `reproduce/env.json`
- `reproduce/git.json`
- `reproduce/dependencies.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

Final MCP stdio task, `task_20260605_191203_f266a6`:

- `manifest.json`
- `stdout.log`
- `stderr.log`
- `worker.log`
- `worker.err.log`
- `metrics/normalized_metrics.csv`
- `metrics/collection-summary.json`
- `figures/line_train_loss_over_epoch.png`
- `figures/line_train_loss_over_epoch.svg`
- `figures/line_val_accuracy_over_epoch.png`
- `figures/line_val_accuracy_over_epoch.svg`
- `figures/figure-summary.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `reproduce/command.txt`
- `reproduce/env.json`
- `reproduce/git.json`
- `reproduce/dependencies.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

MCP smoke diagnostics:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-v1-mcp\mcp-server.stderr.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-v1-mcp\mcp-smoke-progress.jsonl`

PPTX visual acceptance rendered six decks to PDF/JPEG:

- background run: 7 rendered slide JPEGs
- failed run: 5 rendered slide JPEGs
- explicit multi-result run: 7 rendered slide JPEGs
- course/project run: 7 rendered slide JPEGs
- cancelled run: 5 rendered slide JPEGs
- MCP run: 7 rendered slide JPEGs

## Scenario Results

Long successful run:

- Used `run --background`, `status`, `logs --tail`, `collect`, `figures`, `report`, `slides`, and `artifacts`.
- Final status: `completed`.
- Collection result: 5 normalized metric rows.
- Figure result: 2 generated figure pairs.
- Slide result: 7-slide editable PPTX.

Failed run diagnostic:

- Final status: `failed`.
- Exit code and stderr were retained.
- Failure summary contained the expected `FileNotFoundError`.
- Report and 5-slide diagnostic deck were generated without rewriting the failed task as a success.

Explicit multi-result config:

- Used `ingest`, `collect --config explicit-metrics.yaml`, and `figures --spec explicit-figure.yaml`.
- Collection result: 15 normalized metric rows.
- Explicit config selected 3 declared CSV sources and recorded units.
- Figure result: 1 explicit accuracy-by-model figure pair.
- Slide result: 7-slide editable PPTX.

Course/project presentation:

- Used `examples/project-presentation-pack`.
- Collection result: 16 normalized metric rows.
- Report and slides cited the project goal and generated source artifacts.
- Slide result: 7-slide `zh-project` PPTX.

Cancelled long task:

- Used `run --background`, `status`, `logs --tail`, `cancel`, `status`, `report`, `slides`, and `artifacts`.
- Final status: `cancelled`.
- Logs, command, cwd, and reproducibility files were preserved.
- Report and 5-slide cancellation diagnostic deck were generated.

MCP stdio delegation:

- Real stdio client/server smoke listed tools: `cancel_experiment`, `generate_report_fragment`, `generate_slides`, `inspect_results`, `make_figures`, and `run_experiment`.
- `run_experiment(background=True)` returned while the task was still `running`, proving the long task did not block until completion.
- Final completed task: `task_20260605_191203_f266a6`.
- Metrics rows: 5.
- Figure count: 2.
- Slide count: 7.
- Cancellation task: `task_20260605_191207_27b108`, final status `cancelled`.
- Destructive command attempt status: `blocked`.
- Omitted contract reported `full_stdout`, `full_stderr`, `metrics_rows`, and `artifact_bodies` as `omitted_by_default`.

## Visual And Artifact Inspection

PPTX render and structure checks passed for all six accepted decks:

- Rendered page counts matched `slides-summary.json`.
- No blank slides were detected.
- Slide QA checks passed for title presence, artifact duplicate checks, table overflow guards, and caption overflow guards.
- Generated/source artifact counts were present in summaries.

The final MCP smoke also returned slide QA checks with all values `true`:

- `slide_count`
- `empty_slide_check`
- `title_check`
- `artifact_duplicate_check`
- `table_overflow_guard`
- `caption_overflow_guard`

## Public Documentation Claim Audit

README, release notes, public alpha docs, and prior Phase 6/public-alpha notes were checked for overclaims. The remaining "complete V1" wording appears only in controlling design-goal planning and acceptance records. Public-facing public-alpha records continue to describe earlier validation as public-alpha or high-fidelity validation, not proof of complete V1 design-goal completion.

## Test Results

Required full test suite:

```text
py -3 -m pytest
78 passed in 62.47s
```

Required MCP stdio smoke:

```text
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-v1-mcp"
task_id=task_20260605_191203_f266a6
run_status=running
final_status=completed
metrics_rows=5
figure_count=2
slide_count=7
cancel_task_id=task_20260605_191207_27b108
cancel_status=cancelled
blocked_command_status=blocked
artifact_count=19
```

Final `git status --short` was run after changes and recorded in the command log for this phase.

## Blocking / Follow-Up / Out Of Scope

Blocking:

- None.

Follow-up:

- Host-specific MCP client configuration examples remain future work.
- Richer chart catalog remains future work.
- Lockfile-specific dependency parsers remain future work.
- More malformed CSV/JSON/log fixtures remain future work.
- Better project grouping and report wording remain future work.

Out of scope for Phase 6:

- Web UI.
- FastAPI.
- Remote runner.
- AI polishing or autonomous analysis.
- Animation, GIF, MP4, Manim, Remotion, or PowerPoint native animation.
- Hosted service.
- Generic multi-agent framework.

## Final Judgment

Phase 6 passes with blocking count 0. Lab-Sidecar now has acceptance evidence for the original V1 design goal: local-first long-experiment Sidecar behavior, context-quarantined MCP delegation, artifact-first outputs, reproducible report and slide artifacts, external CLI validation, real MCP stdio smoke, and rendered/inspected presentation outputs. The complete V1 design-goal acceptance can be recorded.
