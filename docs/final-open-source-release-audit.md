# Final Open Source Release Audit

Date: 2026-06-17

## Starting Baseline

- Worktree status at start: clean (`git status --short` returned no output).
- Diff hygiene at start: clean (`git diff --check` returned no output).

## Files Reviewed

- `AGENTS.md`
- `README.md`
- `docs/next-stage-product-growth-plan.md`
- `docs/next-stage-product-growth-acceptance.md`
- `docs/public-alpha-final-acceptance.md`
- `docs/release-checklist.md`
- `docs/mcp-host-config.md`
- `docs/v2-host-integration.md`
- `docs/demo-public-alpha.md`
- `docs/public-alpha-quickstart.md`
- `docs/public-alpha-release-notes.md`
- `pyproject.toml`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `.github/workflows/ci.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `plugins/lab-sidecar/.codex-plugin/plugin.json`
- `plugins/lab-sidecar/.mcp.json`
- `plugins/lab-sidecar/skills/use-lab-sidecar/SKILL.md`
- `examples/csv-comparison/README.md`
- `examples/simple-success/README.md`
- `examples/simple-failure/README.md`
- `examples/project-presentation-pack/README.md`
- `examples/algorithm-benchmark/README.md`
- `docs/assets/demo/csv-comparison-val-accuracy.png`
- `docs/assets/demo/csv-comparison-report-preview.png`

## Changes Made

- Clarified that the public quickstart only requires `.[dev]`; `.[dev,mcp]` is now called out as optional for MCP smoke and plugin checks.
- No architecture changes.
- No MCP code changes.
- No packaging metadata changes were needed.

## Audit Notes

- The public README is credible and aligned with current behavior.
- The demo assets are real, small, committed previews from `examples/csv-comparison`.
- The docs consistently frame Codex subagents as coordination, not as a Lab-Sidecar product feature.
- MCP/V2 docs stay bounded: local, experimental, thin adapter, no OS sandboxing or hosted-service claims.
- Historical docs still contain many negative-scope mentions of Web UI, FastAPI, hosted service, OS sandboxing, and malware detection. These are boundary statements, not product claims.

## Validation Commands And Results

```bash
git diff --check
```

- Passed, no output.

```bash
rg -n "guaranteed|大量star|production-grade|OS sandbox|malware detection|hosted service|Web UI|FastAPI" README.md docs examples plugins
```

- Passed as a review scan. Matches were boundary/negative-scope statements in historical docs, not affirmative public-alpha claims.

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

- Passed.

```bash
.venv/bin/python -m pytest -q
```

- Passed: `117 passed in 9.26s`.

```bash
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py -q
```

- Passed: `86 passed in 7.88s`.

```bash
.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py tests/test_v2_worker_invocation.py -q
```

- Passed: `31 passed in 2.00s`.

```bash
.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-final-mcp-smoke
```

- Passed.
- Tools listed: `cancel_experiment`, `cancel_sidecar_task`, `delegate_experiment_artifacts`, `generate_report_fragment`, `generate_slides`, `inspect_results`, `inspect_sidecar_task`, `make_figures`, `preview_sidecar_artifact`, `run_experiment`.
- V1 task id: `task_20260617_110924_9c130a`.
- V2 task id: `task_20260617_110924_e9a075`.
- Cancel task id: `task_20260617_110924_9940a9`.
- Bounded response contract preserved; full command/stdout/stderr/metrics/artifact bodies were omitted by default.

```bash
.venv/bin/python /Users/anyuchen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
```

- Passed.

```bash
.venv/bin/python -m build
```

- Passed.

## README / Demo Quickstart Result

Quickstart workspace:

```text
/tmp/lab-sidecar-final-quickstart
```

Direct run chain:

- `task_20260617_111002_1b15c8`
- completed
- produced normalized metrics, figures, `reports/report-fragment.md`, `slides/presentation-draft.pptx`, and `slides/slides-summary.json`

Existing-results ingest chain:

- `task_20260617_111005_1e1d16`
- completed
- produced normalized metrics, figures, `reports/report-fragment.md`, and `slides/presentation-draft.pptx`

The quickstart is copy-pasteable after the README clarification that `.[dev]` is enough for the CLI path and `.[dev,mcp]` is optional.

## Known Limits

- CLI `run` is explicit local command execution, not OS isolation.
- MCP safety is conservative workspace/command gating, not sandboxing.
- V2 and MCP default responses stay bounded by design.
- Slide image export is not committed; the repo keeps the PPTX artifact and slide summary instead.
- No commit, push, tag, PyPI publish, or PR was created.

## Final Worktree

Current `git status --short` after the audit pass:

```text
 M README.md
 M docs/demo-public-alpha.md
 M docs/public-alpha-quickstart.md
?? docs/final-open-source-release-audit.md
```

## Final Recommendation

Ready to commit and open source as a cautious public alpha.

The repo is in good shape for publication after the maintainer commits the small README/docs install-note adjustment and performs their normal release operation steps.
