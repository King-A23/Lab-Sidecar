# Release Hardening Acceptance

Date: 2026-06-23

## Current Release Candidate Judgment

Lab-Sidecar is ready for a cautious local-first alpha release candidate after
maintainer review of this record and the associated working tree changes.

This judgment is based on a real package build, installed-wheel workflow smoke,
package verification, repository hygiene checks, package-content inspection, and
the final release validation matrix below. No tag, push, PyPI upload, or
release publication was performed by this acceptance pass.

## Positioning Confirmation

- CLI-first: the primary product surface remains the local `labsidecar` CLI.
- File-first: task state and generated evidence remain inspectable local files
  under `.lab-sidecar/`.
- Local-first: Lab-Sidecar does not require a hosted service for its core
  artifact workflow.
- MCP optional local adapter: MCP/V2 remains experimental, local, optional, and
  bounded; it is not the main product surface.

Primary path:

```text
run / ingest -> collect -> figures -> report -> slides -> validate -> package -> package-verify / traceability
run / ingest -> collect -> compare --save -> validate-comparison -> package-comparison -> package-verify
```

The saved comparison workflow has a dedicated acceptance record:
[comparison-artifact-acceptance.md](comparison-artifact-acceptance.md).

## Verification Commands And Results

Commands were run from the repository root. Because the system Homebrew Python
is externally managed, package-installing release commands were rerun with a
disposable or repository virtual environment Python on `PATH`.

| Command | Result |
| --- | --- |
| `PATH=/tmp/lab-sidecar-rc-closure-venv/bin:$PATH python -m pip install -U pip` | Passed; upgraded pip in the disposable release venv. |
| `PATH=/tmp/lab-sidecar-rc-closure-venv/bin:$PATH python -m pip install build` | Passed; installed `build` and its direct dependencies in the disposable release venv. |
| `.venv/bin/python -m build` | Passed; built `lab_sidecar-0.1.0.tar.gz` and `lab_sidecar-0.1.0-py3-none-any.whl`. |
| `.venv/bin/python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"` | Passed; built a wheel, installed it into an isolated venv, ran installed `labsidecar`, validated artifacts, packaged the task and saved comparison, and verified both packages. |
| `.venv/bin/python -m pytest -q` | Passed; 252 tests passed. |
| `.venv/bin/python -m ruff check .` | Passed. |
| `.venv/bin/python scripts/cli_full_smoke.py --workspace /tmp/lab-sidecar-cli-full-smoke --repo "$(pwd)"` | Passed; covered success, failed-task diagnostic, ingest, saved comparison, comparison validation, comparison packaging, and package verification flows. |
| `.venv/bin/python -m pytest tests/test_mcp_tools.py tests/test_v2_host_integration.py -q` | Passed; 32 tests passed. |
| `.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-smoke` | Passed; optional MCP stdio smoke completed. |
| `.venv/bin/python -m pytest tests/test_docs_scope.py tests/test_wheel_smoke_script.py -q` | Passed; focused docs and wheel-smoke tests passed. |
| `.venv/bin/python -m pytest tests/test_comparison_artifacts.py tests/test_package_verify.py tests/test_validate_command.py -q` | Passed; focused comparison, package verification, and validation tests passed. |
| `git diff --check` | Passed. |
| `test ! -e .lab-sidecar` | Passed; the repository root did not contain `.lab-sidecar`. |

Package-content inspection:

| Artifact | Result |
| --- | --- |
| `dist/lab_sidecar-0.1.0.tar.gz` | Contains `lab_sidecar/`, `tests/`, `examples/`, `docs/`, `scripts/`, `README.md`, `CHANGELOG.md`, `pyproject.toml`, `docs/offline-release-smoke.md`, and `docs/release-hardening-acceptance.md`. |
| `dist/lab_sidecar-0.1.0-py3-none-any.whl` | Contains `lab_sidecar/` and console script metadata for `labsidecar` and `lab-sidecar`; does not include `examples/`, `docs/`, or `scripts/`, as expected for the runtime wheel. |

## v0.1.2 Contract Stabilization Addendum

Date: 2026-06-24

This addendum records the pending v0.1.2 artifact-contract stabilization pass.
It does not change the release publication status: no tag, push, PyPI upload,
or GitHub release was performed.

| Check | Result |
| --- | --- |
| Final diff review | Passed after follow-up fixes; review found a comparison figure alias validation gap, which was closed by sharing the comparison figure entry resolver with validation and adding focused tests. |
| `.venv/bin/python -m pytest tests/test_comparison_artifacts.py` | Passed; 23 tests passed after the comparison validation fix. |
| `.venv/bin/python -m pytest` | Passed; 273 tests passed in 65.58 seconds. |
| Disposable real-path smoke in `/tmp/lab-sidecar-real-smoke.PYmI1M/workspace` | Passed after installing `.[dev]` in a temporary venv; covered `init`, `doctor`, `run`, `collect`, `figures`, `report`, `slides`, `validate`, `package`, and `package-verify`. |
| Ingest smoke using `examples/csv-comparison` | Passed; covered `ingest`, `collect`, `figures`, `report`, `slides`, and `validate`. |
| Saved-comparison smoke | Passed; covered `compare --save --figures --report`, `validate-comparison --require figures --require report --require package-ready`, `package-comparison`, and `package-verify`. |
| Repository root artifact check | Passed; the smoke did not create `.lab-sidecar` or `*.egg-info` in the repository root. |

The only smoke failure was an expected environment precheck before editable
installation: invoking the CLI without dependencies failed with
`ModuleNotFoundError: No module named 'typer'`. The same workflow passed after
installing the package with `python -m pip install -e ".[dev]"` in the
temporary venv.

## Failed Or Not-Run Commands

| Command | Reason | Impact | Required follow-up |
| --- | --- | --- | --- |
| `python -m pip install -U pip` with the system `python` | Failed with `externally-managed-environment` from PEP 668 on Homebrew Python. | Does not indicate a Lab-Sidecar packaging failure; release package checks need a virtual environment or CI-managed Python. | Run release build/install checks from a venv or CI Python, as done above. |
| `PATH=/tmp/lab-sidecar-rc-closure-venv/bin:$PATH python -m pytest tests/test_docs_scope.py tests/test_wheel_smoke_script.py -q` before installing dev dependencies | Failed with `No module named pytest`. | The disposable build venv intentionally only had build tooling; not a product or package failure. | Use the repository dev venv or install `.[dev]` before running tests. The same focused tests passed with `PATH=.venv/bin:$PATH`. |

## Non-Goals Confirmed

- No Web UI.
- No FastAPI or HTTP service.
- No hosted service or cloud sync.
- No remote runner.
- No general multi-agent framework.
- No default AI analysis.
- No TensorBoard, MLflow, JSONL, animation, video, or complex chart system.
- No MCP/V2 schema expansion.
- MCP/V2 omitted-content metadata keys were aligned to the public boundary
  names without expanding the tool surface or returning additional artifact
  bodies.
- No PyPI publish, tag, push, or GitHub release.

## Release Decision

Ready for cautious local-first alpha release candidate.

## Next Action

Maintainer review, then either tag `v0.1.0`, create a `v0.1.0-rc.1` release
candidate, or draft the release notes without publishing. Do not publish to
PyPI until explicitly approved by the maintainer.
