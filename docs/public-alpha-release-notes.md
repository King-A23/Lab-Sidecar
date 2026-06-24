# Public Alpha Release Notes

Date: 2026-06-08

## Current v0.1.x Release Line

These notes include historical public-alpha checkpoints. For the current
package version and release-line changes, prefer [CHANGELOG.md](../CHANGELOG.md)
and the version-specific acceptance records.

The v0.1.5 release-trust slice documents GitHub release wheel/sdist
installation and adds local release verification scripts. The implementation
slice does not create a v0.1.5 tag, create a GitHub release, or publish to
PyPI; those remain maintainer-operated release steps.

## Summary

Lab-Sidecar public alpha is a local-first, CLI-first research sidecar for AI agents and experiment workflows. It can run or ingest local experiment results, collect CSV/JSON metrics, generate static figures, write deterministic Markdown report fragments, and create editable static PPTX drafts.

This alpha intentionally does not include Web UI, FastAPI, remote runners, AI-generated analysis, animation, GIF, MP4, Manim, Remotion, or hosted services.

## What Works

- CLI workflow: `init -> run/ingest -> collect -> figures -> report -> slides`.
- Direct run collection: `collect` can pick up run working-directory top-level CSV/JSON files created after task start.
- Metrics collection from CSV and JSON with source provenance in `collection-summary.json`.
- Static PNG/SVG figures and deterministic Markdown reports.
- Static editable PPTX decks with bounded text, metrics table previews, figure captions, QA checks, and source artifact metadata.
- Failed-task diagnostic reports and decks preserve stderr, exit code, command, and failure summary.
- Experimental MCP-facing adapter with deterministic V1 tools:
  - `run_experiment`
  - `inspect_results`
  - `cancel_experiment`
  - `make_figures`
  - `generate_report_fragment`
  - `generate_slides`
- Thin V2 MCP mirror over the bounded local host tools:
  - `delegate_experiment_artifacts`
  - `inspect_sidecar_task`
  - `preview_sidecar_artifact`
  - `cancel_sidecar_task`
- Repo-scoped Codex plugin scaffold under `plugins/lab-sidecar/`, with a usage
  skill and MCP configuration.
- MIT license and open-source contribution, security, changelog, release, and
  CI metadata.
- Real stdio MCP smoke completed with pinned `mcp==1.27.2`.

## Capability Boundary Snapshot

| Area | Supported in this alpha | Outside this alpha |
| --- | --- | --- |
| Metrics | CSV/JSON metric collection and normalized task-local outputs. | TensorBoard event parsing, JSONL stream parsing, full MLflow parsing, or broad recursive ingestion by default. |
| Figures | Deterministic static `line`, `bar`, and `box` PNG/SVG charts. | Complex scientific plots, interactive figures, statistical-significance chart systems, animation, or video. |
| Report artifacts | Deterministic Markdown report fragments and editable static PPTX drafts. | Automatic research conclusions, paper conclusions, deployment advice, or default AI analysis. |
| Execution model | Local CLI `run`/`ingest`/`collect` and local artifact records. | Hosted services, remote runners, cloud sync, multi-tenant permissions, Web UI, or FastAPI. |
| Agent integration | Experimental local MCP/V2 bounded delegation and artifact metadata. | A security sandbox, malware detector, shell interception layer, or general multi-agent framework. |
| Default responses | Bounded scenario summaries, artifact paths, and bounded previews. | Full logs, full metric rows, report bodies, PPT contents, prompt/response bodies, data files, or artifact bytes by default. |

## Safety Model

Manual CLI `run` is a user-explicit local command execution path. It records the command, logs, status, and artifacts, but it is not an OS sandbox; the command can do whatever the user's environment permits.

MCP-facing `run_experiment` and
`delegate_experiment_artifacts(command=...)` apply a conservative workspace and
command safety gate and should be treated as higher-risk agent-triggered paths:

- workspace-external cwd is blocked
- `.lab-sidecar` cwd is blocked
- destructive command patterns are blocked
- shell chaining and similar higher-risk patterns require confirmation
- workspace-external absolute output/path arguments are blocked

These MCP/V2 checks are guardrails, not isolation. Lab-Sidecar does not claim OS sandboxing, malware detection, container isolation, multi-user policy, or global shell interception. The human experiment owner remains responsible for interpretation, redaction, acceptance, and final decisions.

## MCP Notes

Install optional MCP support:

```bash
python -m pip install -e ".[dev,mcp]"
```

Run the stdio smoke:

```bash
python scripts/mcp_stdio_smoke.py --workspace "${TMPDIR:-/tmp}/lab-sidecar-mcp-stdio-smoke"
```

Tool responses return bounded summaries and artifact paths by default. They do
not return complete command strings, stdout, stderr, metrics rows, report
Markdown, worker prompt/response bodies, artifact bodies, or PPT contents.

## Validation

- `py -3 -m pytest`: passed during public-alpha readiness.
- `py -3 -m pytest tests/test_mcp_tools.py`: passed.
- `py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-mcp-stdio-smoke"`: passed.
- Phase 4.1 visual acceptance covered project presentation, simple success, CSV comparison, and failure diagnosis samples.
- Phase 6 acceptance covered success, failure, multi-result comparison, and course project presentation scenarios.

## Known Limits

- MCP is still an experimental local adapter; host-specific config has only a generic stdio example.
- V2 MCP tools are a thin mirror over local host contracts, not a separate product surface or hosted service.
- CLI dangerous-command prompting is not implemented.
- `collect` only scans the run working directory top level, not recursively.
- Bad-input coverage exists for malformed JSON, empty CSV, and missing metric columns, but broader real-world malformed fixtures remain follow-up.
- Project-style figure grouping can still show `(missing)` labels in mixed metric tables.
- Long labels in project comparison cards may be truncated.

## Public Alpha Judgment

Recommended for a cautious public alpha after final commit organization.
Blocking issues are currently none; follow-up work should stay focused on host
setup validation, policy configuration, and broader malformed fixture coverage.

## Post-Stage 5 Release Audit

Date: 2026-06-19

At the time of this 2026-06-19 audit, the package version remained `0.1.0` in
`pyproject.toml`. No release tag or PyPI publish step had been performed in
that repository state.

Stage 1 through Stage 5 are now committed on `main`:

- Stage 1: task navigation and bounded comparison
- Stage 2: deliverable task packages
- Stage 3: messy result adaptation through explicit collection config
- Stage 4: Agent-native bounded delegation hardening
- Stage 5: task-local provenance and traceability

Stage 5 adds `provenance/traceability.json` as a task-local audit index. It
records source references, generated artifact hashes and sizes, metric lineage,
figure lineage, report claim traces, slide evidence, reproduce metadata
pointers, package traceability evidence, and omission notes. It does not embed
full logs, full metric row bodies, report bodies, PPTX contents, worker
prompt/response bodies, raw source files, SQLite, or unrelated workspace files.

Install from a clone with:

```bash
python -m pip install -e ".[dev]"
```

Install optional MCP support with:

```bash
python -m pip install -e ".[dev,mcp]"
```

Stage 5 validation evidence:

- `git diff --check`: passed
- `PATH=.venv/bin:$PATH python -m pytest tests/test_cli_smoke.py -q`: 85 passed
- `PATH=.venv/bin:$PATH python -m pytest -q`: 137 passed
- Manual full workflow smoke passed in a disposable local workspace with task
  `task_20260618_222513_2fc3fd`
- SQLite-independent inspection passed after deleting `.lab-sidecar/index.sqlite`

Additional release limits after Stage 5:

- No V2/MCP schema changes were made for traceability preview.
- Traceability is evidence metadata, not statistical significance, model
  ranking, or autonomous scientific interpretation.
- Package export remains allowlist-based and still omits raw sources, full
  logs, worker audit bodies, sandbox files, SQLite, and unrelated workspace
  files by default.
- `artifact-index.json` records a self-referential digest omission note for
  itself; hash that file externally after package creation if a package-level
  external digest is required.

Post-Stage 5 judgment: ready for a cautious local-first alpha release cut once
the maintainer chooses a tag and publish path.

## Experiment Scenario Sidecar V1 Release Notes

Date: 2026-06-22

Lab-Sidecar now positions the main caller as a local AI agent that delegates
experiment-result handling while the human remains the experiment owner and
final decision maker. The CLI path stays unchanged:
`run/ingest -> collect -> figures -> report -> slides`.

`collect` writes a bounded `metrics/scenario-summary.json` for the canonical
`training-run` and `algorithm-benchmark` scenarios. The summary records
scenario type, primary metric, groups, bounded best/last row evidence,
descriptive seed aggregates when a seed field exists, source evidence, explicit
omissions, and warnings. It does not embed full logs, full metric rows, report
bodies, PPTX contents, worker prompts/responses, or artifact bytes.

Reports, slides, CLI `summarize`, package export, traceability, and bounded
host/delegate responses can refer to the scenario summary. Seed aggregates are
descriptive only; Lab-Sidecar does not infer statistical significance,
scientific conclusions, deployment readiness, or autonomous model superiority.

Pre-release canonical smoke validation ran in disposable workspace
`/private/tmp/lab-sidecar-v1-canonical-smoke-8J83RJ`:

- `training-run`: task `task_20260622_094912_b6dd4d`, generated
  `metrics/scenario-summary.json`, figures, report, slides, and traceability.
- `algorithm-benchmark`: task `task_20260622_095301_233f4f`, generated
  `metrics/scenario-summary.json` with `runtime_ms` as the minimizing primary
  metric and descriptive seed aggregates, plus figures, report, slides, and
  traceability.

Focused validation passed:

- `.venv/bin/python -m pytest tests/test_scenario_summary.py -q`: 8 passed.
- `.venv/bin/python -m pytest tests/test_cli_smoke.py::test_summarize_before_and_after_artifacts_stays_bounded tests/test_cli_smoke.py::test_algorithm_benchmark_scenario_summary_from_ingest_config -q`:
  2 passed.

Additional limits remain unchanged: no Web UI, FastAPI, remote runner, hosted
service, cloud sync, generic multi-agent framework, default AI analysis, or
statistical research-claim engine.

## Release Hardening Notes

Date: 2026-06-23

Release hardening keeps the same cautious local-first alpha scope and adds
verification surfaces for existing artifacts:

- `validate <task_id>` checks task artifact health without generating new
  artifacts.
- `package-verify <package_dir>` checks `artifact-index.sha256`,
  `artifact-index.json`, indexed file hashes and sizes, and unexpected package
  files.
- Explicit figure specs now document both the legacy single-spec YAML shape and
  the multi-figure `figures:` shape for deterministic `line`, `bar`, and `box`
  charts.
- `scripts/cli_full_smoke.py` is the optional release CLI full smoke from a
  repository checkout.
- `scripts/wheel_smoke.py` builds a wheel, installs it into an isolated venv,
  and runs the installed CLI path in a disposable workspace.

The scope remains unchanged: no Web UI, FastAPI/HTTP service, hosted service,
cloud sync, remote runner, default AI analysis, general multi-agent framework,
or MCP/V2 schema expansion.

## v0.1.2 Contract Stabilization Notes

Date: 2026-06-24

v0.1.2 keeps Lab-Sidecar in the same cautious local-first alpha scope and
focuses on artifact-contract stability:

- Task artifact registration is consolidated through a shared manifest helper
  for metrics, figures, reports, and slides.
- `manifest.json` remains the task-local source of truth; SQLite remains a
  rebuildable index and query accelerator.
- Saved-comparison packages include generated comparison figure images declared
  by `figures/figure-summary.json`, not arbitrary image files placed under the
  comparison artifact directory.
- Comparison behavior remains descriptive only: 2-5 collected local tasks,
  shared numeric final-row metrics, and no statistical significance or model
  superiority claims.
- MCP/V2 wording is clarified as a local, experimental, bounded adapter over
  existing artifact services, not a hosted service, remote runner, Web/API
  layer, or general agent framework.

No Web UI, FastAPI/HTTP service, hosted service, remote runner, cloud sync,
advanced analytics, default AI-authored conclusions, DAG scheduler, or general
agent-framework behavior is part of this release.
