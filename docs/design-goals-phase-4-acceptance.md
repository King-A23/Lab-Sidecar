# Design Goals Phase 4 Acceptance

Date: 2026-06-05

## Phase Goal

Phase 4 implemented the minimum explicit metrics and figure configuration needed so Lab-Sidecar V1 does not depend only on automatic guessing.

The accepted behavior is:

- `collect --config` can select declared CSV/JSON sources.
- `collect --config` can map nonstandard source fields to normalized metric names.
- Missing configured sources or fields fail with a clear CLI error and persisted `metrics/collection-summary.json` diagnostics.
- Collection summaries record explicit field mappings and units.
- `figures --spec` can plot fields produced by explicit collection mapping.
- Re-running collect and figures with the same config/spec does not duplicate manifest artifact IDs.

## Changed Files

- `lab_sidecar/collectors/config.py`
- `lab_sidecar/collectors/csv_collector.py`
- `lab_sidecar/collectors/json_collector.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/cli/app.py`
- `tests/test_cli_smoke.py`
- `docs/design-goals-phase-4-acceptance.md`

## Workspace Paths

Repository workspace:

- `C:\code\Lab-Sidecar`

External acceptance workspace:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase4`

Task directory:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase4\.lab-sidecar\tasks\task_20260605_182158_3c59f5`

Config/spec inputs:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase4\metrics.yaml`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase4\figure.yaml`

## Task ID Values

- Explicit metrics and figure config smoke: `task_20260605_182158_3c59f5`

## Commands

Phase entrance:

```powershell
git status --short
Get-Content -LiteralPath AGENTS.md
Get-Content -LiteralPath PRODUCT_ITERATION_PLAN.md
Get-Content -LiteralPath docs\design-goals-completion-plan.md
```

Focused tests:

```powershell
py -3 -m pytest tests\test_cli_smoke.py -k "collect_csv_comparison or collect_json_algorithm or figures_with_spec_generates_requested_line_chart"
py -3 -m pytest tests\test_cli_smoke.py -k "collect_with_config or explicit_config"
```

External workspace acceptance:

```powershell
$workspace = Join-Path $env:TEMP 'lab-sidecar-design-phase4'
Remove-Item -LiteralPath $workspace -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $workspace
Push-Location $workspace
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app ingest results
py -3 -m lab_sidecar.cli.app collect task_20260605_182158_3c59f5 --config metrics.yaml
py -3 -m lab_sidecar.cli.app figures task_20260605_182158_3c59f5 --spec figure.yaml
py -3 -m lab_sidecar.cli.app artifacts task_20260605_182158_3c59f5
Pop-Location
```

Required full validation:

```powershell
py -3 -m pytest
git status --short
```

## Generated Artifacts

External acceptance task artifacts:

- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/manifest.json`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/stdout.log`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/stderr.log`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/raw/source_refs.json`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/metrics/normalized_metrics.json`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/metrics/collection-summary.json`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/figures/mapped_accuracy.png`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/figures/mapped_accuracy.svg`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/figures/figure-spec.yaml`
- `.lab-sidecar/tasks/task_20260605_182158_3c59f5/figures/figure-summary.json`

The collection summary recorded:

- `config_path`: `metrics.yaml`
- `candidate_count`: `1`
- selected source: `results/run_a.csv`
- ignored source: `results/unrelated.csv`
- mapped fields: `epoch`, `method`, `seed`, `accuracy`, `latency_ms`
- units: `accuracy=ratio`, `latency_ms=ms`

The figure summary recorded:

- `figure_id`: `mapped_accuracy`
- `chart_type`: `line`
- `x`: `epoch`
- `y`: `accuracy`
- `group_by`: `method`
- generated PNG/SVG paths under task-local `figures/`

## Test Results

- `py -3 -m pytest tests\test_cli_smoke.py -k "collect_csv_comparison or collect_json_algorithm or figures_with_spec_generates_requested_line_chart"`: `3 passed, 62 deselected`
- `py -3 -m pytest tests\test_cli_smoke.py -k "collect_with_config or explicit_config"`: `3 passed, 65 deselected`
- `py -3 -m pytest`: `77 passed`

## Blocking / Follow-Up / Out Of Scope

Blocking:

- None.

Follow-up:

- TensorBoard support remains future work.
- Complex log parsing remains future work.
- Richer config schema validation and documentation can be added later if the config surface grows.

Out of scope for Phase 4:

- AI-based schema inference.
- Arbitrary notebook parsing.
- Web UI, FastAPI, remote runner, hosted services, animation, or generic multi-agent framework.
- MCP changes; Phase 4 did not modify MCP behavior and therefore did not require MCP stdio smoke.
- CLI long-task lifecycle changes; Phase 4 did not modify long-running runner behavior.

## Final Judgment

Phase 4 passes. Explicit metrics configuration now affects collection behavior, can normalize nonstandard CSV fields, can select declared sources, records units, fails with persisted diagnostics for missing fields, and works with explicit figure specs. The repository can proceed to Phase 5: Reproducibility And Artifact Completeness.
