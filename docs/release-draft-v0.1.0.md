# Lab-Sidecar v0.1.0 cautious local-first alpha

## Summary

Lab-Sidecar v0.1.0 is a CLI-first, file-first, local-first experiment artifact sidecar for local runs and imported result files. The main workflow remains `run / ingest -> collect -> figures -> report -> slides`, with release hardening around `validate`, `package`, `package-verify`, traceability, and saved comparison artifacts. The optional MCP/V2 adapter remains local, bounded, experimental, and secondary to the CLI.

## Highlights

- Task-local artifact workflow under `.lab-sidecar/`.
- Deterministic CSV/JSON metric collection and bounded scenario summaries.
- Deterministic static figures, Markdown report fragments, and editable PPTX drafts.
- `validate <task_id>` for artifact health checks without generating artifacts.
- `package <task_id>` plus `package-verify <package_dir>` for inspectable package evidence.
- Task-local and comparison-local traceability records.
- Saved comparison workflow for already-collected local tasks.
- Release-oriented CLI smoke and installed-wheel smoke coverage.
- Optional bounded MCP/V2 adapter for local host integrations.

## Install From Source

```bash
python -m pip install -e ".[dev]"
```

Optional MCP support:

```bash
python -m pip install -e ".[dev,mcp]"
```

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

## Comparison Example

```bash
python -m lab_sidecar.cli.app compare <task_id_a> <task_id_b> --save --figures --report
python -m lab_sidecar.cli.app validate-comparison <comparison_id>
python -m lab_sidecar.cli.app package-comparison <comparison_id> --output lab-sidecar-comparison-<comparison_id>
python -m lab_sidecar.cli.app package-verify lab-sidecar-comparison-<comparison_id>
```

Saved comparisons are descriptive derived artifacts for two to five already-collected local tasks. They use shared finite numeric final-row metrics and do not claim statistical significance or model superiority.

## Validation Evidence

- `python -m pytest -q`: 250 passed.
- `python -m ruff check .`: passed.
- `python -m build`: passed.
- `python scripts/cli_full_smoke.py --workspace <workspace> --repo <repo>`: passed.
- `python scripts/wheel_smoke.py --workspace <workspace> --repo <repo>`: passed.
- `python -m pytest tests/test_mcp_tools.py tests/test_v2_host_integration.py -q`: 32 passed.
- `python scripts/mcp_stdio_smoke.py --workspace <workspace>`: passed.
- `git diff --check`: passed.
- Repository root `.lab-sidecar/`: absent.

## Boundaries

- No Web UI.
- No FastAPI or HTTP service.
- No hosted service or cloud sync.
- No remote runner.
- No general multi-agent framework.
- No sandbox or security guarantee for user-provided local commands.
- No default AI analysis.
- No statistical significance, p-values, confidence intervals, or model superiority claims.

## Known Limits

- CSV/JSON metric inputs only.
- No TensorBoard, MLflow tracking-store, or JSONL ingestion.
- CLI `run` is user-explicit local command execution and is not sandboxed.
- Comparison is final-row descriptive only.
- MCP/V2 adapter is optional, local, experimental, and bounded.
- Offline wheel smoke requires a complete maintainer-prepared wheelhouse.

## Maintainer Actions

- Review the local staged commits and release hardening records.
- Choose `v0.1.0` or `v0.1.0-rc.1` after review.
- Do not publish to PyPI without explicit maintainer approval.
