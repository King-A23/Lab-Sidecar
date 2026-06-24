# Lab-Sidecar v0.1.0 cautious local-first alpha

## Summary

Lab-Sidecar v0.1.0 is a cautious local-first alpha for a CLI-first,
file-first, local-first experiment artifact sidecar. It helps turn local runs
or ingested result folders into task-local artifacts, CSV/JSON metrics,
deterministic figures, Markdown report fragments, editable PPTX drafts,
validation records, packages, package verification evidence, and traceability
metadata.

The main path is:

```text
run / ingest -> collect -> figures -> report -> slides -> validate -> package -> package-verify / traceability
```

## Highlights

- Local task artifacts under `.lab-sidecar/`.
- CSV/JSON metrics collection with deterministic normalized outputs.
- Static PNG/SVG figures, Markdown report fragments, and editable PPTX drafts.
- `validate` for task artifact health checks.
- `package` and `package-verify` for inspectable task result or diagnostic
  packages.
- Traceability records that connect generated claims and artifacts back to
  bounded local evidence.
- Saved comparison artifacts for already-collected local tasks.
- Optional bounded local MCP/V2 adapter for host integrations.

## Install

From a checked-out source tree:

```bash
python -m pip install -e ".[dev]"
```

Optional local MCP support:

```bash
python -m pip install -e ".[dev,mcp]"
```

Use a virtual environment or CI-managed Python for release checks. Some system
Python installs are externally managed under PEP 668.

## Quickstart

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app validate <task_id>
python -m lab_sidecar.cli.app package <task_id> --output lab-sidecar-package-<task_id>
python -m lab_sidecar.cli.app package-verify lab-sidecar-package-<task_id>
```

## Saved Comparison Workflow

Saved comparisons are local derived artifacts for two to five already-collected
tasks. They use shared finite numeric final-row metrics and preserve comparison
tables, figures, report fragments, traceability, and package verification
evidence.

```bash
python -m lab_sidecar.cli.app compare <task_id_a> <task_id_b> --save --figures --report
python -m lab_sidecar.cli.app validate-comparison <comparison_id>
python -m lab_sidecar.cli.app package-comparison <comparison_id> --output lab-sidecar-comparison-<comparison_id>
python -m lab_sidecar.cli.app package-verify lab-sidecar-comparison-<comparison_id>
```

Comparison output is descriptive final-row evidence only. It does not claim
statistical significance, p-values, confidence intervals, scientific
conclusions, deployment readiness, or model superiority.

## Validation Evidence

The clean release verification pass used a fresh git worktree and isolated venv
from committed HEAD.

- `python -m pip install -e ".[dev]"`: passed.
- `python -m pytest -q`: `252 passed`.
- `python -m ruff check .`: passed.
- `python -m build`: passed.
- `python scripts/cli_full_smoke.py --workspace /tmp/lab-sidecar-clean-cli-smoke --repo "$(pwd)"`: passed.
- `python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-clean-wheel-smoke --repo "$(pwd)"`: passed.
- sdist/wheel inspection: passed.
- Optional MCP/V2 focused tests: `32 passed`.
- Optional MCP stdio smoke: passed.
- `git diff --check`: passed.
- Repository root `.lab-sidecar/`: absent.

Release verification record:
`docs/release-verification-v0.1.0.md`.

## Boundaries And Non-Goals

- No Web UI.
- No FastAPI or HTTP service.
- No hosted service or cloud sync.
- No remote runner.
- No default AI analysis.
- No MCP/V2 promotion to the main product surface.
- No MCP/V2 schema expansion.
- No general multi-agent framework.
- No statistical significance, p-values, confidence intervals, scientific
  conclusions, deployment-readiness claims, or model superiority claims.
- CLI `run` executes user-provided local commands and is not sandboxed.

## Known Limits

- CSV/JSON metrics only.
- No TensorBoard, MLflow tracking-store, or JSONL ingestion.
- Saved comparison is descriptive final-row comparison only.
- MCP/V2 is optional, local, experimental, and bounded.
- Offline wheel smoke depends on a complete maintainer-prepared wheelhouse.
- Use a venv or CI-managed Python for release checks on externally managed
  Python installations.

## Maintainer Notes

- Review the local commits and clean verification record before tagging.
- Choose `v0.1.0-rc.1` for an RC or `v0.1.0` for the final alpha tag.
- Do not publish to PyPI without explicit maintainer approval.
- No push, tag, publish, or GitHub release was performed by the verification
  pass.
