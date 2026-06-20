# Alpha4 Phase 4.4 Benchmark Extension Acceptance

Date: 2026-06-20

## Phase Goal

Extend Data-to-Chart benchmark coverage with fallback-only unsupported chart
requests and prove that bounded fallback improves chart coverage without exposing
raw tables, full normalized metrics, logs, raw source bodies, or worker
prompt/response bodies.

## Starting State

Phase 4.3 was accepted with validator-gated fallback adoption. The worktree
already contained earlier Alpha3/Data-to-Chart, Alpha4 Phase 4.1, Phase 4.2, and
Phase 4.3 changes. Phase 4.4 started with:

```bash
git status --short
git diff --stat
```

`lab_sidecar/mcp` remained out of scope and was not edited.

## Phase Plan

- Add a separate Alpha4 fallback benchmark runner instead of changing the
  deterministic benchmark contract.
- Include fallback-only scenarios for scatter/correlation, heatmap/confusion
  matrix, histogram/distribution, and stacked/category composition.
- For each scenario, run a deterministic-only arm with fallback off and a
  fallback-enabled arm with `--fallback bounded --fallback-worker mock`.
- Score coverage lift, validator/adoption records, official artifacts,
  traceability lineage, visual validity, boundedness, and context reduction.
- Generate the required benchmark Markdown and JSON records under `docs/`.
- Do not change fallback defaults, MCP behavior, hosted behavior, remote
  execution, Web UI, or product architecture.

## Changed Files

- `scripts/alpha4_bounded_chart_fallback_benchmark.py`
- `tests/test_data_to_chart_benchmark.py`
- `docs/alpha4-bounded-chart-fallback-benchmark.md`
- `docs/alpha4-bounded-chart-fallback-benchmark-data.json`
- `docs/alpha4-phase-4-4-benchmark-extension-acceptance.md`

## Key Implementation

- Added `scripts/alpha4_bounded_chart_fallback_benchmark.py`.
- The benchmark creates deterministic fixtures under `/private/tmp` and runs:
  - fallback off: deterministic unsupported chart diagnostic path;
  - fallback bounded mock: validated sandbox output and official adoption path.
- The sidecar scoring context is limited to bounded summaries and audit records:
  collection summary, figure summary, traceability, figure request,
  validator result, and adoption record.
- The benchmark intentionally does not read raw source files, full normalized
  metric rows, full logs, worker prompt/response bodies, or sandbox proposal
  bodies in the sidecar arm.
- Added pytest smoke coverage for the new benchmark runner.
- Generated:
  - `docs/alpha4-bounded-chart-fallback-benchmark.md`
  - `docs/alpha4-bounded-chart-fallback-benchmark-data.json`

## Benchmark Results

Full fallback benchmark command:

```bash
.venv/bin/python scripts/alpha4_bounded_chart_fallback_benchmark.py --scale full --benchmark-root /private/tmp/lab-sidecar-alpha4-fallback-benchmark-full-supervisor --write-docs
```

Full benchmark aggregate:

- scenarios: `4`
- deterministic covered: `0`
- fallback covered: `4`
- coverage delta: `4`
- score: `44/44`
- context reduction: `98.56%`
- sidecar raw metric row exposure: `0`
- sidecar violation count: `0`

Fallback-only scenarios:

- `scatter_correlation`: scatter `epoch` / `val_accuracy` / `model`
- `heatmap_confusion_matrix`: heatmap `predicted_class` / `true_class`
- `histogram_distribution`: histogram `latency_ms` / `latency_ms` / `service`
- `stacked_category_composition`: stacked bar `category` / `share` / `segment`

Representative full-run worker run IDs:

- `worker_run_20260620_121738_d903c8`
- `worker_run_20260620_121741_f8939e`
- `worker_run_20260620_121745_271e66`
- `worker_run_20260620_121748_c09a3e`

## Validation Commands

```bash
.venv/bin/python scripts/alpha4_bounded_chart_fallback_benchmark.py --scale smoke --benchmark-root /private/tmp/lab-sidecar-alpha4-fallback-benchmark-smoke-supervisor
.venv/bin/python -m pytest tests/test_data_to_chart_benchmark.py
.venv/bin/python scripts/alpha4_bounded_chart_fallback_benchmark.py --scale full --benchmark-root /private/tmp/lab-sidecar-alpha4-fallback-benchmark-full-supervisor --write-docs
python -m json.tool docs/alpha4-bounded-chart-fallback-benchmark-data.json >/dev/null
```

Results:

- Fallback benchmark smoke: passed, `4/4`, score `44/44`.
- Focused benchmark pytest: passed, `5 passed`.
- Fallback benchmark full with docs: passed and wrote required docs.
- Benchmark data JSON validation: passed.

## Boundedness Checks

The benchmark fixtures include raw-only sentinel values containing:

```text
ALPHA4_FALLBACK_RAW_SENTINEL_DO_NOT_EXPOSE
```

The sidecar scoring context checks for sentinel exposure, raw metric row
exposure, worker prompt body keys, and worker response body keys. The full run
recorded:

- `sidecar_raw_metric_row_bytes_exposed=0`
- `sidecar_violation_count=0`

## Risks And Follow-Up

- The benchmark uses the local mock fallback worker to exercise validator and
  adoption mechanics; it does not evaluate external AI provider quality.
- Visual validation checks parseability, dimensions, and nonblank output, not
  chart-design quality.
- Phase 4.5 should update operator-facing docs and troubleshooting guidance for
  fallback statuses and default-off behavior.

## Final Judgment

Phase 4.4 passes supervisor acceptance. Fallback-only benchmark coverage is now
documented and measured: deterministic-only coverage stays at zero for the
unsupported scenarios, bounded fallback adopts four validated official figures,
and the benchmark records zero raw metric row exposure and zero boundedness
violations.
