# Alpha4 Phase 4.2 Chart Worker Contract And Sandbox Acceptance

Date: 2026-06-20

## Phase Goal

Define and enforce the chart fallback worker contract and sandbox behavior for
unsupported figure requests. This phase adds a local/mock chart fallback worker
for tests, keeps worker writes under `intelligence/<worker_run_id>/sandbox/`, and
does not adopt fallback outputs into official figures.

## Starting State

- Phase 4.1 was accepted with bounded unsupported-chart diagnostics,
  `figure-request.json`, and unavailable-worker status.
- The worktree already contained Alpha3/Data-to-Chart and Phase 4.1 changes.
- `lab_sidecar/mcp` remained out of scope and was not edited.

## Changed Files

- `lab_sidecar/cli/app.py`
- `lab_sidecar/figures/fallback_worker.py`
- `lab_sidecar/figures/service.py`
- `tests/test_cli_smoke.py`

## Key Implementation

- Added a figures-scoped fallback worker contract in
  `lab_sidecar/figures/fallback_worker.py`.
- Contract proposal type is `figure_fallback` with task/worker identity,
  requested chart fields, `source_metrics_fields`, sandbox output paths,
  deterministic refusal reason, diagnostics, and omitted-content metadata.
- Added a hidden internal CLI option, `--fallback-worker
  unavailable|mock|mock-escape`, for tests only. Default remains `unavailable`.
- In `--fallback bounded --fallback-worker mock`, the mock worker writes:
  - `worker-request.json`
  - `worker-result.json`
  - `sandbox/mock-worker-observed-request.json`
  - `sandbox/figure-fallback-proposal.json`
  - sandbox PNG/SVG placeholder artifacts
  - `validator-result.json`
  - `diagnostics.md`
- In `mock-escape`, sandbox-escaping output paths are rejected and no official
  figure files are created.
- No fallback output is adopted into official `figures/`, `manifest.json`, or
  adoption records in this phase.

## Boundedness Checks

Tests verify that fallback worker inputs and outputs do not include raw row
sentinels, full CSV row bodies, prompt/response bodies, report bodies, PPTX
internals, or artifact bodies. The mock worker receives only the bounded
`figure-request.json` content and writes only sandbox-scoped proposal/artifact
files.

## Validation Commands

```bash
.venv/bin/python -m pytest tests/test_cli_smoke.py -k 'unsupported_explicit_chart or fallback_mock_worker or supported_deterministic_spec_does_not_create_fallback_worker_run'
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_data_to_chart_benchmark.py
.venv/bin/python -m pytest
.venv/bin/python scripts/data_to_chart_benchmark.py --scale smoke --benchmark-root /private/tmp/lab-sidecar-data-to-chart-smoke-alpha4-phase42-supervisor
git diff --check
find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha4-*' \) -print
```

## Test Results

- Focused Phase 4.2 pytest: passed (`5 passed, 87 deselected`).
- CLI and Data-to-Chart pytest: passed (`96 passed in 21.02s`).
- Full pytest: passed (`148 passed in 24.23s`).
- Deterministic Data-to-Chart smoke: passed (`7/7` scenarios, score `49/49`,
  `sidecar_raw_metric_row_bytes_exposed=0`, `sidecar_violation_count=0`).
- `git diff --check`: passed.
- Repo-local generated artifact check: no matching paths.

## Workspaces And IDs

Focused pytest used temporary pytest workspaces. Representative fallback records
were created under those temporary task directories only; no repository-local
`.lab-sidecar` directory was intentionally kept.

The deterministic benchmark smoke used:

- Benchmark root:
  `/private/tmp/lab-sidecar-data-to-chart-smoke-alpha4-phase42-supervisor`

## Risks

- Phase 4.2 validates only the worker contract and sandbox locality. It does not
  yet perform visual validation or official artifact adoption.
- `proposal_created` means the sandbox proposal contract passed; official
  adoption remains out of scope until Phase 4.3.

## Out Of Scope

- No Web UI, FastAPI, hosted service, remote runner, cloud provider, or general
  multi-agent orchestration was introduced.
- No MCP behavior was changed.
- No fallback worker output is copied into official `figures/`.

## Final Judgment

Phase 4.2 implementation is ready for supervisor validation. The local/mock
worker contract exists, sandbox escaping is rejected, worker-unavailable remains
the default, and deterministic figures still bypass fallback.
