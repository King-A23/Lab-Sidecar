# Comparison Artifact Acceptance

Date: 2026-06-24

## Goal

Harden the saved comparison artifact workflow for a cautious local-first alpha
release candidate without adding a new product surface.

## Scope

- Local saved comparison artifact workflow for already-collected tasks.
- No Web UI, hosted service, remote runner, cloud sync, or MCP/V2 expansion.
- No statistical significance, model superiority, or deployment-readiness
  claims.

The comparison path remains:

```text
existing collected tasks -> compare --save -> comparison artifacts -> validate-comparison -> package-comparison -> package-verify
```

## Design Decision

Saved comparisons are independent records under:

```text
.lab-sidecar/comparisons/<comparison_id>/
```

They are not special tasks. A comparison is a derived cross-task artifact, not a
`run` or `ingest` lifecycle event, and it has no command execution semantics,
stdout, stderr, or task status transitions. Keeping comparisons separate avoids
expanding task modes, avoids making comparisons look like successful runs, and
keeps task validation/package behavior scoped to real task records.

## Artifact Layout

```text
.lab-sidecar/comparisons/<comparison_id>/
  comparison-manifest.json
  comparison-summary.json
  comparison-table.csv
  comparison-table.json
  figures/
    figure-summary.json
    comparison_<metric>.png
    comparison_<metric>.svg
  reports/
    comparison-report-fragment.md
    comparison-report-summary.json
  provenance/
    traceability.json
```

## Bounded Contract

- No full source metric rows are embedded.
- No full stdout/stderr logs are embedded or copied into comparison packages.
- No raw source files are copied into comparison packages.
- No SQLite indexes, worker audit folders, worker prompt/response bodies,
  sandbox files, or unrelated workspace files are copied.
- Reports and `best_by_metric` entries are descriptive only.
- Row selection is `final_row`.
- Only shared finite numeric metric fields are compared.

## Commands Verified

Focused verification performed during this hardening pass:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest tests/test_comparison_artifacts.py -q` | Passed; 12 tests passed. |
| `.venv/bin/python -m pytest tests/test_mcp_tools.py tests/test_v2_host_integration.py -q` | Passed; 32 tests passed. |
| `.venv/bin/python -m pytest tests/test_cli_full_smoke_script.py tests/test_wheel_smoke_script.py tests/test_docs_scope.py -q` | Passed; 8 tests passed. |

The first attempt to run `python -m pytest tests/test_comparison_artifacts.py -q`
with the system Python failed during collection because that interpreter did not
have `PyYAML` installed. The repository virtual environment passed the focused
suite.

Final release re-baseline commands must still be recorded here after they are
run:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q` | Passed; 250 tests passed. |
| `.venv/bin/python -m ruff check .` | Passed. |
| `.venv/bin/python -m build` | Passed; built `lab_sidecar-0.1.0.tar.gz` and `lab_sidecar-0.1.0-py3-none-any.whl`. |
| `.venv/bin/python scripts/cli_full_smoke.py --workspace /tmp/lab-sidecar-cli-full-smoke --repo "$(pwd)"` | Passed; covered success, failed-task diagnostic, ingest, saved comparison, comparison validation, comparison packaging, and package verification flows. |
| `.venv/bin/python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"` | Passed; built a wheel, installed it into an isolated venv, ran installed `labsidecar`, validated artifacts, packaged the task and saved comparison, and verified both packages. |
| `.venv/bin/python -m pytest tests/test_mcp_tools.py tests/test_v2_host_integration.py -q` | Passed; 32 tests passed. |
| `.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-smoke` | Passed. |
| `git diff --check` | Passed. |
| `test ! -e .lab-sidecar` | Passed; the repository root did not contain `.lab-sidecar`. |

## Test Count

Focused comparison artifact suite: 12 tests passed.

Full repository test suite: 250 tests passed.

## Known Limits

- Final-row comparison only.
- Shared finite numeric fields only.
- No statistical significance, p-values, confidence intervals, or model
  superiority conclusions.
- No cross-workspace comparison.
- No MCP tool exposure for comparison artifacts.
- No comparison slide deck in the current scope.

## Release Judgment

Ready for cautious local-first alpha RC.

## Follow-Up Candidates

- List/open saved comparison UX.
- Optional comparison slides.
- Richer deterministic comparison report formatting.

These follow-ups are not part of the current hardening task.
