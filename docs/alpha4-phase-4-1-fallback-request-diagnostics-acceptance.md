# Alpha4 Phase 4.1 Fallback Request Diagnostics Acceptance

Date: 2026-06-20

## Phase Goal

Implement bounded unsupported-chart diagnostics and figure-request bundle generation
for `labsidecar figures`, with CLI flag shape `--fallback off|bounded` defaulting
to `off`. In `bounded` mode, create a task-local intelligence worker run directory,
write `figure-request.json`, record unavailable-worker diagnostics, and avoid any
real worker invocation or fallback artifact adoption.

## Starting State

- The repository worktree was already dirty with prior boundedness and
  Data-to-Chart changes.
- Existing deterministic line/bar/box behavior and benchmark coverage were
  already present.
- `lab_sidecar/mcp` was intentionally left untouched.

## Changed Files

- `lab_sidecar/cli/app.py`
- `lab_sidecar/core/traceability.py`
- `lab_sidecar/figures/service.py`
- `lab_sidecar/figures/specs.py`
- `lab_sidecar/intelligence/__init__.py`
- `tests/test_cli_smoke.py`

## Commands

Read / repo-state commands:

```bash
git status --short
git diff --stat
sed -n '1,220p' AGENTS.md
sed -n '1,260p' docs/alpha4-bounded-chart-fallback-plan.md
sed -n '1,260p' docs/v2-intelligent-sidecar-design.md
sed -n '1,260p' docs/v2-development-plan.md
```

Validation commands:

```bash
python -m py_compile lab_sidecar/figures/service.py lab_sidecar/figures/specs.py lab_sidecar/cli/app.py lab_sidecar/core/traceability.py
.venv/bin/python -m pytest tests/test_cli_smoke.py -k 'unsupported_explicit_chart or supported_deterministic_spec_does_not_create_fallback_worker_run'
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_data_to_chart_benchmark.py
.venv/bin/python -m pytest
git diff --check
find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha4-*' \) -print
```

## Artifacts / Worker Run IDs

No repository-local `.lab-sidecar` or `package-alpha4-*` artifacts were left behind
by the validation commands run from the repository root.

Ad hoc temporary validation outside the repo root produced a representative fallback
worker run:

- Task ID: `task_20260620_105233_2ac5a0`
- Worker run ID: `worker_run_20260620_105233_3c907f`

Representative generated files for that temporary validation run:

- `intelligence/worker_run_20260620_105233_3c907f/figure-request.json`
- `intelligence/worker_run_20260620_105233_3c907f/validator-result.json`
- `intelligence/worker_run_20260620_105233_3c907f/diagnostics.md`
- `intelligence/worker_run_20260620_105233_3c907f/sandbox/`

## Key Implementation

- Added `--fallback off|bounded` to `labsidecar figures`, default `off`.
- Changed explicit figure handling so unsupported chart types like `scatter` and
  `heatmap` are treated as unsupported chart intent instead of failing as an
  opaque YAML validation error.
- Extended `figure-summary.json` with:
  - `unsupported_chart_diagnostics`
  - `fallback`
- In `--fallback bounded` mode, when the chart intent is unsupported:
  - create `intelligence/<worker_run_id>/sandbox/`
  - write bounded `figure-request.json`
  - write `validator-result.json` with unavailable-worker status
  - write `diagnostics.md`
  - record fallback status `unavailable`
- No worker request/result invocation path was added for Phase 4.1 figures.
- No fallback PNG/SVG adoption into official `figures/`, manifest artifacts, or
  provenance adoption records was added.
- Extended figure traceability lineage with bounded fallback metadata.
- Reworked `lab_sidecar.intelligence.__init__` to use lazy exports and avoid the
  import cycle introduced by figure-side use of intelligence path helpers.

## Boundedness Checks

Focused tests asserted that:

- unsupported summary/request/traceability output does not include raw CSV row
  bodies or raw row sentinels;
- `figure-request.json` includes only bounded metadata:
  task id/status/mode, requested chart intent, metric columns, row count,
  units/groups/field source mappings when available, warnings/errors/skipped
  candidates, safe artifact hashes/paths, and collection diagnostics;
- `figure-request.json` does not embed prompt/response payload bodies;
- deterministic supported charts still generate official figures and do not create
  fallback worker runs.

## Test Results

- `python -m py_compile ...`: passed
- `.venv/bin/python -m pytest tests/test_cli_smoke.py -k 'unsupported_explicit_chart or supported_deterministic_spec_does_not_create_fallback_worker_run'`: passed (`3 passed`)
- `.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_data_to_chart_benchmark.py`: passed (`94 passed in 21.59s`)
- `.venv/bin/python -m pytest`: passed (`146 passed in 23.75s`)
- `git diff --check`: passed
- `find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha4-*' \) -print`: no matching paths under the repository root

## Supervisor Re-Validation

Supervisor re-validation was run after execution-agent handoff:

```bash
.venv/bin/python -m pytest tests/test_cli_smoke.py -k 'unsupported_explicit_chart or supported_deterministic_spec_does_not_create_fallback_worker_run'
.venv/bin/python -m pytest
.venv/bin/python scripts/data_to_chart_benchmark.py --scale smoke --benchmark-root /private/tmp/lab-sidecar-data-to-chart-smoke-alpha4-phase41-supervisor
git diff --check
find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha4-*' \) -print
```

Results:

- Focused fallback pytest: passed (`3 passed, 87 deselected`).
- Full pytest: passed (`146 passed in 24.54s`).
- Deterministic Data-to-Chart smoke: passed (`7/7` scenarios, score `49/49`,
  `sidecar_raw_metric_row_bytes_exposed=0`, `sidecar_violation_count=0`).
- `git diff --check`: passed.
- Repo-local generated artifact check: no matching paths.

Additional supervisor manual boundedness smoke used a temporary workspace:

- Task ID: `task_20260620_105832_1c9295`
- Worker run ID: `worker_run_20260620_105833_31b484`
- Request path: `intelligence/worker_run_20260620_105833_31b484/figure-request.json`

The manual smoke confirmed `figure-request.json`, `figure-summary.json`, and
`provenance/traceability.json` did not expose the
`ALPHA4_RAW_ROW_SENTINEL_DO_NOT_EXPOSE` row values or full CSV rows, and no
official fallback PNG/SVG files were created.

## Risks

- `figure-request.json` currently records bounded request diagnostics only. Phase
  4.2 still needs a formal figure-worker request/response contract.
- Fallback lineage is recorded in figure summary / traceability, but official
  fallback artifact adoption remains intentionally out of scope until later
  phases.
- The lazy `lab_sidecar.intelligence` package export avoids the new import cycle,
  but future package-level imports should keep that constraint in mind.

## Final Judgment

Phase 4.1 is accepted.

The requested bounded unsupported-chart diagnostics, bounded `figure-request.json`
generation, fallback CLI shape, unavailable-worker recording, and focused tests are
implemented. Deterministic line/bar/box behavior remains unchanged. `lab_sidecar/mcp`
was untouched, and no Web UI, FastAPI service, remote runner, or hosted behavior
was introduced.
