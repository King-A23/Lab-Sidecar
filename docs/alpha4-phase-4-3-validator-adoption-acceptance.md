# Alpha4 Phase 4.3 Validator And Adoption Acceptance

Date: 2026-06-20

## Phase Goal

Implement deterministic validation and adoption for bounded chart fallback
outputs. Valid fallback PNG/SVG artifacts may be copied from the worker sandbox
into official `figures/` only after validator acceptance. Rejected fallback
outputs remain under `intelligence/<worker_run_id>/sandbox/` and must not create
official figure artifacts, adoption records, or manifest figure records.

## Starting State

The worktree already contained accepted Alpha4 Phase 4.1 and 4.2 changes plus
unreported Phase 4.3 edits from a prior worker. Supervisor validation started by
checking:

```bash
git status --short
git diff --stat
git diff --stat -- lab_sidecar/mcp tests docs lab_sidecar/figures lab_sidecar/core lab_sidecar/cli
```

`lab_sidecar/mcp` had no Phase 4.3 diff and remained out of scope.

## Phase Plan

- Validate the existing unreported Phase 4.3 implementation before trusting it.
- Keep edits scoped to figure fallback worker contracts, figure generation
  adoption, traceability, CLI fallback flags, tests, and this acceptance record.
- Do not change MCP behavior, add Web UI/FastAPI/remote execution/hosted
  service behavior, or turn fallback into a general multi-agent framework.
- Preserve deterministic `line`, `bar`, and `box` generation as the first path.
- Accept only sandbox outputs that pass deterministic field, path, visual, and
  boundedness checks.

## Changed Files

- `lab_sidecar/figures/fallback_worker.py`
- `lab_sidecar/figures/service.py`
- `lab_sidecar/core/traceability.py`
- `lab_sidecar/cli/app.py`
- `tests/test_cli_smoke.py`
- `docs/alpha4-phase-4-3-validator-adoption-acceptance.md`

## Key Implementation

- Added validator checks for proposal identity, bounded metric fields,
  source-metrics traceability, sandbox-relative paths, parseable nonblank
  minimum-size PNG/SVG outputs, and the omitted-data contract.
- Added local mock worker rejection modes for malformed PNG, tiny image,
  missing field, and path traversal.
- Adopted accepted sandbox PNG/SVG files into official `figures/` with
  `*-fallback.png` and `*-fallback.svg` names only after validator acceptance.
- Wrote `adoption-record.json` only for accepted outputs.
- Recorded fallback lineage in `figure-summary.json`,
  `figure-spec.yaml`, manifest figure artifacts, and
  `provenance/traceability.json`.
- Kept rejected fallback output and diagnostics under
  `intelligence/<worker_run_id>/` without official figure pollution.

## Validation Commands

```bash
.venv/bin/python -m pytest tests/test_cli_smoke.py -k 'figures_fallback or unsupported_explicit_chart or supported_deterministic_spec_does_not_create_fallback_worker_run'
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_data_to_chart_benchmark.py
.venv/bin/python -m pytest
```

Results:

- Focused fallback tests: passed, `8 passed, 87 deselected`.
- CLI plus deterministic Data-to-Chart pytest: passed, `99 passed`.
- Full pytest: passed, `151 passed`.

## Workspaces And IDs

Supervisor manual accepted-fallback smoke:

- Workspace:
  `/private/tmp/lab-sidecar-alpha4-phase43-smoke`
- Task id:
  `task_20260620_120538_34d467`
- Worker run id:
  `worker_run_20260620_120539_901b29`

Generated official artifacts:

- `.lab-sidecar/tasks/task_20260620_120538_34d467/figures/alpha4_phase43_heatmap-fallback.png`
- `.lab-sidecar/tasks/task_20260620_120538_34d467/figures/alpha4_phase43_heatmap-fallback.svg`
- `.lab-sidecar/tasks/task_20260620_120538_34d467/intelligence/worker_run_20260620_120539_901b29/adoption-record.json`

## Boundedness Checks

The manual smoke created raw-only sentinel values in an unselected CSV column:

```text
ALPHA4_PHASE43_RAW_SENTINEL_ROW_001
ALPHA4_PHASE43_RAW_SENTINEL_ROW_002
ALPHA4_PHASE43_RAW_SENTINEL_ROW_003
```

Supervisor checked the serialized `figure-request.json`, `validator-result.json`,
`adoption-record.json`, `figure-summary.json`, and `traceability.json` for:

- raw sentinel values;
- raw row text such as `1,0.70`;
- worker prompt/response body keys.

No sentinel, raw row body, prompt body, or response body was present.

## Rejection Coverage

Tests verified that these rejected cases do not create official fallback figures,
adoption records, or manifest figure artifacts:

- malformed PNG;
- tiny PNG/SVG;
- missing metric field;
- sandbox-escaping output paths.

Tests also verified supported deterministic specs do not create fallback worker
runs even when `--fallback bounded` is supplied.

## Risks And Follow-Up

- The current real worker remains a local/mock test worker; production AI or
  external provider use remains out of scope.
- The validator checks basic visual validity and dimensions, not full semantic
  chart correctness.
- Phase 4.4 should extend the Data-to-Chart benchmark with fallback-only
  scenarios and coverage scoring.

## Final Judgment

Phase 4.3 passes supervisor acceptance. Validator-gated fallback adoption is
implemented for bounded chart fallback outputs, rejected outputs do not pollute
official artifacts, deterministic chart behavior remains intact, and bounded
traceability records fallback lineage without raw metric row exposure.
