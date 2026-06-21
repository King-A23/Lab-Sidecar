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
