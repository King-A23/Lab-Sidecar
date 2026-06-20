# Alpha4 Phase 4.5 Docs And Operator UX Acceptance

Date: 2026-06-20

## Phase Goal

Document the bounded chart fallback operator experience: default-off behavior,
explicit enablement, fallback statuses, audit artifacts, limitations, and
troubleshooting. Keep the product local-first, file-first, CLI-first, and
artifact-first.

## Starting State

Phase 4.4 was accepted with fallback-only benchmark docs and data. Phase 4.5
started with:

```bash
git status --short
git diff --stat
```

The implementation already had fallback CLI behavior and tests; this phase was
documentation and operator UX only.

## Phase Plan

- Update CLI docs for `--fallback off|bounded`, default `off`.
- Explain fallback statuses: `not_needed`, `unavailable`, `rejected`,
  `adopted`, plus `attempted=true/false`.
- Explain which fallback audit files appear under
  `intelligence/<worker_run_id>/`.
- Explain that official fallback artifacts are written only after validator
  acceptance.
- Document boundedness exclusions: raw tables, full normalized metrics, full
  logs, raw source bodies, report bodies, PPTX internals, worker prompt/response
  bodies, sandbox proposal bodies, and artifact bodies.
- Add troubleshooting for worker unavailable, missing fields, sandbox path
  rejection, visual validation rejection, adopted outputs, and bounded context
  limits.
- Do not change MCP behavior, product code, hosted behavior, remote execution,
  Web UI, or fallback defaults.

## Changed Files

- `README.md`
- `docs/cli-spec.md`
- `docs/artifact-protocol.md`
- `docs/public-alpha-quickstart.md`
- `docs/alpha4-bounded-chart-fallback-operator-guide.md`
- `docs/alpha4-phase-4-5-docs-operator-ux-acceptance.md`

## Key Documentation Updates

- `README.md` now states chart fallback is opt-in, deterministic charts are
  attempted first, and fallback is artifact-scoped rather than a hosted or
  general multi-agent system.
- `docs/cli-spec.md` documents:
  - `--fallback off|bounded`;
  - success/failure output shape;
  - fallback statuses and `attempted`;
  - fallback audit files;
  - bounded request contents;
  - common fallback troubleshooting cases.
- `docs/artifact-protocol.md` documents:
  - `intelligence/<worker_run_id>/`;
  - worker sandbox boundaries;
  - validator/adoption-only official artifact writes;
  - fallback boundedness exclusions.
- `docs/public-alpha-quickstart.md` points unsupported chart users to explicit
  bounded fallback and the operator guide.
- `docs/alpha4-bounded-chart-fallback-operator-guide.md` provides a focused
  operator reference for enablement, statuses, files, boundedness, and
  troubleshooting.

## Validation Commands

```bash
rg -n -- '--fallback off|--fallback bounded|not_needed|unavailable|rejected|adopted|figure-request.json|adoption-record.json|worker prompt' README.md docs/cli-spec.md docs/artifact-protocol.md docs/public-alpha-quickstart.md docs/alpha4-bounded-chart-fallback-operator-guide.md
.venv/bin/python -m pytest tests/test_cli_smoke.py -k 'figures_fallback or unsupported_explicit_chart or supported_deterministic_spec_does_not_create_fallback_worker_run'
.venv/bin/python -m pytest tests/test_data_to_chart_benchmark.py
.venv/bin/python -m pytest
.venv/bin/python scripts/data_to_chart_benchmark.py --scale smoke --benchmark-root /private/tmp/lab-sidecar-data-to-chart-smoke-alpha4-phase45-supervisor
.venv/bin/python scripts/alpha4_bounded_chart_fallback_benchmark.py --scale smoke --benchmark-root /private/tmp/lab-sidecar-alpha4-fallback-benchmark-smoke-phase45-supervisor
python -m json.tool docs/alpha4-bounded-chart-fallback-benchmark-data.json >/dev/null
git diff --check
find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha4-*' \) -print
```

## Boundedness And Boundaries

The docs explicitly state:

- fallback is default-off and must be enabled with `--fallback bounded`;
- deterministic `line`, `bar`, and `box` remain the first path;
- rejected worker outputs remain in sandbox diagnostics and do not create
  official artifacts;
- official fallback figures are copied only after validator acceptance;
- fallback audit files must not embed raw rows, full metrics, logs, raw source
  bodies, report bodies, PPTX internals, worker prompt/response bodies, sandbox
  proposal bodies, or artifact bodies;
- Alpha4 does not introduce Web UI, FastAPI, hosted service, remote runner,
  cloud sync, or a general multi-agent product architecture.

## Risks And Follow-Up

- The operator docs describe the local/mock fallback worker and validator path.
  Real provider quality and configuration remain out of scope.
- Future docs should be revisited if a non-mock chart worker becomes a supported
  public operator surface.

## Final Judgment

Phase 4.5 passes when the validation commands above pass. The requested operator
docs now explain fallback enablement, statuses, limitations, audit artifacts,
troubleshooting, and boundedness without widening the product scope.
