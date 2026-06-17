# Next Stage Product Growth Acceptance

Date: 2026-06-08

## Summary

Lab-Sidecar now has a stronger cautious public-alpha surface:

- README rewritten as a standard open-source landing page with value prop,
  target users, 10-minute quickstart, real demo previews, CLI table, MCP
  context-quarantine language, limits, install/development, and project links.
- CLI onboarding improved with `doctor`, clearer task artifact paths, next-step
  guidance, and deterministic recent-task ordering for `list`.
- Demo docs and example docs now use copy-pasteable `$TASK_ID` flows.
- Two committed demo preview assets were generated from real Lab-Sidecar
  `examples/csv-comparison` outputs.
- MCP/V2 bounded-response contract now omits complete command strings by
  default and redacts/caps command previews.
- Packaging metadata, CI package build check, and GitHub issue/PR templates
  were added or tightened.

## Changed Files

Primary changed or added files for this pass:

- `README.md`
- `.github/workflows/ci.yml`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `pyproject.toml`
- `docs/demo-public-alpha.md`
- `docs/public-alpha-quickstart.md`
- `docs/public-alpha-release-notes.md`
- `docs/mcp-host-config.md`
- `docs/v2-host-integration.md`
- `docs/assets/demo/csv-comparison-val-accuracy.png`
- `docs/assets/demo/csv-comparison-report-preview.png`
- `examples/algorithm-benchmark/README.md`
- `examples/csv-comparison/README.md`
- `examples/project-presentation-pack/README.md`
- `examples/simple-failure/README.md`
- `examples/simple-success/README.md`
- `lab_sidecar/cli/app.py`
- `lab_sidecar/runner/service.py`
- `lab_sidecar/mcp/responses.py`
- `lab_sidecar/mcp/tools.py`
- `lab_sidecar/intelligence/bundle.py`
- `tests/test_cli_smoke.py`
- `tests/test_mcp_tools.py`
- `tests/test_v2_intelligence_scaffold.py`

The worktree already contained additional public-alpha/MCP/plugin changes before
this pass, including `plugins/`, `.agents/`, `docs/release-checklist.md`, and
V2 MCP files. They were preserved and validated rather than reverted.

## Demo Workspaces And Task IDs

Primary deterministic demo workspace:

```text
/tmp/lab-sidecar-next-stage-demo
```

Scenario 1, `examples/simple-success` run chain:

```text
task_id: task_20260608_132834_153843
artifacts:
- .lab-sidecar/tasks/task_20260608_132834_153843/metrics/normalized_metrics.csv
- .lab-sidecar/tasks/task_20260608_132834_153843/figures/line_val_accuracy_over_epoch.png
- .lab-sidecar/tasks/task_20260608_132834_153843/reports/report-fragment.md
- .lab-sidecar/tasks/task_20260608_132834_153843/slides/presentation-draft.pptx
```

Scenario 2, `examples/csv-comparison` ingest chain:

```text
task_id: task_20260608_132836_f1dbb1
artifacts:
- .lab-sidecar/tasks/task_20260608_132836_f1dbb1/metrics/normalized_metrics.csv
- .lab-sidecar/tasks/task_20260608_132836_f1dbb1/figures/line_val_accuracy_over_epoch.png
- .lab-sidecar/tasks/task_20260608_132836_f1dbb1/reports/report-fragment.md
- .lab-sidecar/tasks/task_20260608_132836_f1dbb1/slides/presentation-draft.pptx
```

MCP stdio validation workspace:

```text
/tmp/lab-sidecar-next-stage-mcp-smoke
task_id: task_20260608_134009_6c96ba
v2_task_id: task_20260608_134010_30ba54
cancel_task_id: task_20260608_134010_7f47a7
```

## Committed Demo Assets

Generated from the `task_20260608_132836_f1dbb1` CSV comparison task:

```text
docs/assets/demo/csv-comparison-val-accuracy.png
size: 129866 bytes
sha256: ccf5029b4622d06f4b258e43bac5267ac70e2b958044762f50cced5c000e77bc

docs/assets/demo/csv-comparison-report-preview.png
size: 79085 bytes
sha256: 31987cfcbff2eb67b970692e381a62de03e3b8837d8dade2836f3f947e94ee14
```

Slide preview image export was not committed because reliable PPTX raster export
was not available in this environment (`soffice`, `libreoffice`, `convert`, and
`magick` were unavailable). The demo still produces the real PPTX and
`slides-summary.json`.

## Validation Commands

Required validation:

```text
git diff --check
result: passed, no output
```

```text
rg -n "guaranteed|大量star|production-grade|OS sandbox|malware detection|hosted service|Web UI|FastAPI" README.md docs examples plugins
result: completed with matches
interpretation: reviewed matches are boundary/negative-scope language in plans,
acceptance records, release notes, and architecture docs. No positive product
claim for guaranteed stars, production-grade security, OS sandboxing, malware
detection, Web UI, FastAPI, or hosted service was found in the new public README
or demo docs.
```

```text
.venv/bin/python -m pytest -q
result: 117 passed in 10.35s
```

```text
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py -q
result: 86 passed in 8.90s
```

```text
.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py tests/test_v2_worker_invocation.py -q
result: 31 passed in 2.11s
```

```text
.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-next-stage-mcp-smoke
result: passed
listed tools:
- cancel_experiment
- cancel_sidecar_task
- delegate_experiment_artifacts
- generate_report_fragment
- generate_slides
- inspect_results
- inspect_sidecar_task
- make_figures
- preview_sidecar_artifact
- run_experiment
final_status: completed
metrics_rows: 5
figure_count: 2
slide_count: 7
v2_preview_type: csv_rows
blocked_command_status: blocked
omitted_contract includes full_command/full_stdout/full_stderr/metrics_rows/artifact_bodies
```

```text
.venv/bin/python $CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
result: Plugin validation passed: plugins/lab-sidecar
```

```text
git status --short
result: dirty worktree with expected modified/untracked public-alpha files; no commit, push, tag, or PR was created.
```

Additional packaging validation:

```text
.venv/bin/python -m build
initial result: failed because build was not installed in .venv
.venv/bin/python -m pip install build
result: installed build-1.5.0 and pyproject_hooks-1.2.0
.venv/bin/python -m build
result: successfully built lab_sidecar-0.1.0.tar.gz and lab_sidecar-0.1.0-py3-none-any.whl
```

Generated `dist/` artifacts are ignored by `.gitignore` and are not shown in
`git status --short`.

Repository hygiene checks:

```text
find . -path '*/.lab-sidecar/*' -print | head -n 50
result: no output
```

## CLI Usability Changes

- `init` now prints likely next commands.
- New `doctor` command checks Python version, writable workspace, initialized
  config/task directory, and optional MCP SDK presence.
- `run` prints task id, status, command, artifact directory, stdout path,
  stderr path, and next commands based on status.
- `status`, `ingest`, `collect`, `figures`, `report`, and `slides` print
  clearer next-step guidance.
- `list --limit` uses deterministic manifest recency ordering.
- `open <task_id>` remains a non-GUI path printer and is covered for missing
  tasks.

Tests added or extended in `tests/test_cli_smoke.py` cover `doctor`, next-step
output contracts, empty/limited `list`, and missing-task `open`.

## MCP And V2 Bounded Behavior

- `task_summary()` now returns a redacted and capped command preview instead of
  the full command string.
- V1 and V2 omitted contracts now include `full_command`.
- Regression tests cover long command suffixes and secret-like command
  arguments for MCP and V2 input bundles/responses.
- The stdio smoke confirms both V1 deterministic tools and V2 mirror tools are
  listed and usable.

## README Before/After

Before this pass, the README mostly read as an implementation inventory: command
lists, template internals, phase notes, and MCP details appeared before a clear
public value story. It did not show real preview assets and did not clearly name
students, research beginners, or personal developers as primary users.

After this pass, the README leads with a one-sentence value proposition,
explains why the tool exists, shows real generated artifact previews, provides a
10-minute quickstart, lists CLI commands in a table, explains artifact layout,
documents Codex/MCP context quarantine, states safety limits, and links to
project docs.

## Known Limits

- The worktree is intentionally not committed, pushed, tagged, or released.
- GitHub private vulnerability reporting still needs to be enabled or replaced
  with a maintainer-approved private contact before a broader announcement.
- Slide preview images are not committed because local PPTX raster export was
  not available; the PPTX artifact itself is generated and validated.
- CLI `run` is user-explicit local command execution; it is not isolation.
- MCP safety gates are conservative workspace/command checks, not a hardened
  remote boundary.
- `collect` scans the task directory and run working-directory top level; it
  does not recursively scan arbitrary project trees.
- Existing historical docs still contain many negative-scope mentions of Web UI,
  FastAPI, hosted services, OS sandboxing, and malware detection. The required
  grep was reviewed and those hits are not affirmative product claims.
- Build artifacts in `dist/` were generated locally for validation and are
  ignored by git.

## Final Recommendation

Ready after small release-operations follow-ups: review and stage the intended
public-alpha files, enable GitHub private vulnerability reporting or document a
private security contact, and then commit/tag/publish only when explicitly
requested.

No code, README, demo, CLI, MCP/V2 bounded-response, plugin, or validation
blocker remains for a cautious public open-source alpha.
