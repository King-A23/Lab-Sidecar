# Experiment Scenario Sidecar V1 Acceptance

Date: 2026-06-21

## Phase Goal

Implement a bounded experiment scenario summary and align product positioning
around Lab-Sidecar as a local AI agent sidecar for experiment scenarios.

## Changed Files

- `README.md`
- `PRODUCT_ITERATION_PLAN.md`
- `docs/v2-host-integration.md`
- `docs/v2-intelligent-sidecar-design.md`
- `docs/experiment-scenario-sidecar-v1-plan.md`
- `docs/experiment-scenario-summary-contract.md`
- `docs/experiment-scenario-fixtures.md`
- `docs/experiment-scenario-sidecar-v1-acceptance.md`
- `lab_sidecar/collectors/scenario_summary.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/cli/app.py`
- `lab_sidecar/mcp/responses.py`
- `lab_sidecar/intelligence/bundle.py`
- `lab_sidecar/reports/service.py`
- `lab_sidecar/reports/templates.py`
- `lab_sidecar/slides/service.py`
- `lab_sidecar/core/traceability.py`
- `lab_sidecar/storage/package_export.py`
- `tests/test_scenario_summary.py`
- `tests/test_cli_smoke.py`
- `tests/test_v2_host_integration.py`

## Commands

```bash
python -m pytest tests/test_scenario_summary.py -q
```

- System `python` failed before collection because it lacked `pydantic`.

```bash
.venv/bin/python -m pytest tests/test_scenario_summary.py -q
```

- Passed: `2 passed in 0.06s`.

```bash
.venv/bin/python -m pytest tests/test_cli_smoke.py -q
```

- Passed: `96 passed in 9.98s`.

```bash
.venv/bin/python -m pytest tests/test_v2_host_integration.py tests/test_v2_heuristic_worker.py -q
```

- Passed: `17 passed in 1.56s`.

```bash
.venv/bin/python -m pytest -q
```

- Passed: `155 passed in 41.66s`.

```bash
.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-scenario-sidecar-mcp-smoke
```

- Passed.

```bash
git diff --check
```

- Passed, no output.

## Workspaces And IDs

- MCP stdio smoke workspace: `/private/tmp/lab-sidecar-scenario-sidecar-mcp-smoke`
- MCP V1 task: `task_20260621_172227_a99fd5`
- MCP V2 delegate task: `task_20260621_172228_6c8af3`
- MCP V1 cancellation task: `task_20260621_172228_2f84e3`
- MCP V2 cancellation task: `task_20260621_172229_6da905`

## Generated Artifacts

Expected:

- `metrics/scenario-summary.json`
- updated report summaries
- updated slide summaries
- package and traceability references

Implemented:

- `collect` writes and registers `metrics/scenario-summary.json`.
- `summarize` prints a bounded Scenario block.
- V2 delegate/inspect expose `summary.outputs.scenario`.
- Reports and slides include scenario evidence and no-significance wording.
- Package export includes `metrics/scenario-summary.json`.
- Traceability records `scenario_summary_path`, `scenario_type`,
  `primary_metric`, and a descriptive claim limit.

## Test Results

All focused and full validation passed with `.venv/bin/python`.

MCP stdio smoke listed these tools:

```text
cancel_experiment
cancel_sidecar_task
delegate_experiment_artifacts
generate_report_fragment
generate_slides
inspect_results
inspect_sidecar_task
make_figures
preview_sidecar_artifact
run_experiment
```

Smoke summary:

```text
run_status=running
final_status=completed
metrics_rows=5
figure_count=2
slide_count=7
v2_status=completed
v2_preview_type=csv_rows
cancel_status=cancelled
v2_cancel_status=cancelled
blocked_command_status=blocked
artifact_count=21
```

## Pre-Release Canonical Scenario Smoke

Date: 2026-06-22

Workspace: `/private/tmp/lab-sidecar-v1-canonical-smoke-8J83RJ`

The workspace was disposable and outside the repository. Generated
`.lab-sidecar` artifacts were not added to the repo.

### Training Run

Commands:

```bash
.venv/bin/python -m lab_sidecar.cli.app init
.venv/bin/python -m lab_sidecar.cli.app run ".venv/bin/python examples/simple-success/train.py --output metrics.csv" --name canonical-training-run
.venv/bin/python -m lab_sidecar.cli.app collect task_20260622_094912_b6dd4d
.venv/bin/python -m lab_sidecar.cli.app summarize task_20260622_094912_b6dd4d
.venv/bin/python -m lab_sidecar.cli.app figures task_20260622_094912_b6dd4d
.venv/bin/python -m lab_sidecar.cli.app report task_20260622_094912_b6dd4d
.venv/bin/python -m lab_sidecar.cli.app slides task_20260622_094912_b6dd4d
.venv/bin/python -m lab_sidecar.cli.app artifacts task_20260622_094912_b6dd4d
```

Result:

- Task id: `task_20260622_094912_b6dd4d`
- Scenario: `training-run`
- Primary metric: `val_accuracy` with direction `max`
- Metrics rows: `5`
- Bounded evidence: `best_rows=3`, `last_rows=1`
- Key artifacts:
  - `metrics/scenario-summary.json`
  - `metrics/normalized_metrics.csv`
  - `figures/figure-summary.json`
  - `reports/report-fragment.md`
  - `reports/report-summary.json`
  - `slides/presentation-draft.pptx`
  - `slides/slides-summary.json`
  - `provenance/traceability.json`

### Algorithm Benchmark

Commands:

```bash
.venv/bin/python -m lab_sidecar.cli.app ingest examples/algorithm-benchmark --name canonical-algorithm-benchmark
.venv/bin/python -m lab_sidecar.cli.app collect task_20260622_095301_233f4f --config algorithm-benchmark.yaml
.venv/bin/python -m lab_sidecar.cli.app summarize task_20260622_095301_233f4f
.venv/bin/python -m lab_sidecar.cli.app figures task_20260622_095301_233f4f
.venv/bin/python -m lab_sidecar.cli.app report task_20260622_095301_233f4f
.venv/bin/python -m lab_sidecar.cli.app slides task_20260622_095301_233f4f
.venv/bin/python -m lab_sidecar.cli.app artifacts task_20260622_095301_233f4f
```

Config used:

```yaml
sources:
  - examples/algorithm-benchmark/results.json
fields:
  algorithm: algorithm
  seed: seed
  input_size: input_size
  runtime_ms:
    source: runtime_ms
    unit: ms
  memory_mb:
    source: memory_mb
    unit: MB
groups:
  primary: algorithm
  secondary: seed
```

Result:

- Task id: `task_20260622_095301_233f4f`
- Scenario: `algorithm-benchmark`
- Primary metric: `runtime_ms` with direction `min` and unit `ms`
- Metrics rows: `18`
- Seed aggregates: present, `6` bounded items, claim limit
  `descriptive aggregate only; no statistical significance is inferred`
- Bounded evidence: `best_rows=2`, `last_rows=6`
- Key artifacts:
  - `metrics/scenario-summary.json`
  - `metrics/normalized_metrics.csv`
  - `figures/bar_runtime_ms_by_algorithm.png`
  - `figures/bar_runtime_ms_by_algorithm.svg`
  - `reports/report-fragment.md`
  - `reports/report-summary.json`
  - `slides/presentation-draft.pptx`
  - `slides/slides-summary.json`
  - `provenance/traceability.json`

Focused validation commands:

```bash
.venv/bin/python -m pytest tests/test_scenario_summary.py -q
.venv/bin/python -m pytest tests/test_cli_smoke.py::test_summarize_before_and_after_artifacts_stays_bounded tests/test_cli_smoke.py::test_algorithm_benchmark_scenario_summary_from_ingest_config -q
```

Results:

- `8 passed in 0.05s`
- `2 passed in 8.73s`

## Known Limits

- Scenario summary is descriptive only.
- Schema version `1` has explicit hard caps for best rows, last rows, seed
  aggregates, source files, field lists, units, selected fields, and string
  scalar length.
- `selected_fields` is an allowlisted scalar preview and does not copy
  arbitrary free-text cell contents such as notes, prompts, error messages, or
  private comments.
- No TensorBoard, JSONL, or log collector expansion in this slice.
- No statistical significance or autonomous scientific conclusions.

## Final Judgment

Accepted.

Experiment Scenario Sidecar V1 is implemented as a bounded scenario-summary
contract and wired into collector, CLI summarize, V2 compact outputs, reports,
slides, package export, traceability, docs, and tests. The project positioning
now treats the main AI agent as the primary caller and the human as the
experiment owner/final decision maker.
