# Design Goals Gap Matrix

Date: 2026-06-05

Scope: Phase 1 code, test, and public-documentation audit against `PRODUCT_ITERATION_PLAN.md` and `docs/design-goals-completion-plan.md`. This matrix treats the current implementation as a public-alpha vertical slice unless code and tests prove a stronger claim.

Classification key:

- `implemented`: current code and tests cover the expected V1 slice for this goal.
- `minimum-slice`: a useful slice exists, but the V1 design goal is not fully proven.
- `missing`: expected V1 behavior is absent or only a placeholder.
- `deferred`: explicitly outside the current local-first V1 completion path.
- `overclaimed`: documentation or acceptance wording can be read as stronger than the code/test evidence.

## Summary Judgment

Current Lab-Sidecar has a working local CLI chain:

```text
init -> run/ingest -> collect -> figures -> report -> slides
```

It also has an MCP-facing adapter and a real stdio smoke script. That is enough for a cautious public alpha, but not enough to claim the full original V1 design goal:

```text
local long-experiment Sidecar
  -> context quarantine
  -> artifact-first delegation layer
  -> reproducible, inspectable outputs
```

The main gaps are long/background task recovery, explicit collection config, MCP cancellation, fuller provenance, and final V1 acceptance evidence.

## Product Boundary Matrix

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| Local-first, CLI-first workflow | `implemented` | CLI commands are Typer commands in `lab_sidecar/cli/app.py:52`, `lab_sidecar/cli/app.py:74`, `lab_sidecar/cli/app.py:166`, `lab_sidecar/cli/app.py:210`, `lab_sidecar/cli/app.py:260`, `lab_sidecar/cli/app.py:293`; smoke tests drive CLI directly in `tests/test_cli_smoke.py:96`, `tests/test_cli_smoke.py:371`, `tests/test_cli_smoke.py:615`, `tests/test_cli_smoke.py:946`, `tests/test_cli_smoke.py:1119`. | Keep as core product boundary. Do not add Web UI, FastAPI, hosted service, or remote runner during design-goal completion. |
| File-first artifact protocol with manifest as source of truth | `minimum-slice` | Task directories and `manifest.json` are created in `lab_sidecar/runner/service.py:171`; default artifacts are registered in `lab_sidecar/storage/artifact_store.py:12`; tests delete SQLite and still use status/logs/artifacts in `tests/test_cli_smoke.py:139`, collect in `tests/test_cli_smoke.py:599`, figures in `tests/test_cli_smoke.py:701`, report in `tests/test_cli_smoke.py:1084`, and slides in `tests/test_cli_smoke.py:1302`. | Current commands can recover from missing SQLite for tested paths. There is no broader rebuild/list acceptance yet, so keep as Phase 2/5 hardening. |
| No Web UI, FastAPI, remote runner, AI-dependent workflow, hosted service, or generic multi-agent product | `implemented` | Current CLI entrypoints are local package commands in `lab_sidecar/cli/app.py:34`; public README excludes Web UI/FastAPI/AI/animation at `README.md:175`; release notes exclude remote runners, AI analysis, animation, hosted services at `docs/public-alpha-release-notes.md:7`. | Maintain this as a boundary. Goal-mode subagents are execution coordination only, not product architecture. |
| Static slides / presentation material | `minimum-slice` | Slides are implemented as a static PPTX CLI command in `lab_sidecar/cli/app.py:293`; summary and QA checks are written in `lab_sidecar/slides/service.py:592`; tests cover PPTX and summary generation in `tests/test_cli_smoke.py:1119`. | Static PPTX is stronger than the original V1 core but still not a full presentation/animation extension. Animation remains out of scope. |
| Animation, GIF, MP4, Manim/Remotion, native PowerPoint animation | `deferred` | README states the current slides command does not create animation/video/GIF at `README.md:145`; release notes exclude these at `docs/public-alpha-release-notes.md:9`. | Do not implement in design-goal completion phases. |

## Runner, Task Lifecycle, And Storage

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| Initialize workspace and create one independent task directory per task | `implemented` | Workspace initialization command is in `lab_sidecar/cli/app.py:52`; task directory creation uses `exist_ok=False` in `lab_sidecar/runner/service.py:179`; tests assert independent task dirs in `tests/test_cli_smoke.py:174`. | No Phase 1 blocker. |
| Foreground command execution captures stdout/stderr, exit code, status, and failure summary | `implemented` | `execute_task` captures stdout/stderr and waits for exit in `lab_sidecar/runner/service.py:299`; `finalize_task` sets completed/failed status and failure summary in `lab_sidecar/runner/service.py:344`; tests cover success in `tests/test_cli_smoke.py:96` and failure in `tests/test_cli_smoke.py:145`. | No Phase 1 blocker. |
| Background long-task sidecar with `run --background -> status -> logs --tail -> cancel` | `minimum-slice` | CLI exposes `--background` in `lab_sidecar/cli/app.py:74`; background worker launch is in `lab_sidecar/runner/service.py:196`; smoke test covers running status, logs, and cancellation in `tests/test_cli_smoke.py:187`. | Needs Phase 2 hardening for completed background refresh, failed background refresh, worker-exit recovery, and terminal-close recovery evidence. |
| Refresh/recover a task after worker or terminal exit | `minimum-slice` | `status` calls `RunnerService.refresh` in `lab_sidecar/cli/app.py:96`; refresh probes child and worker PIDs in `lab_sidecar/runner/service.py:78`. | If worker PID is gone but manifest is still `running`, refresh returns the record unchanged at `lab_sidecar/runner/service.py:103`. This is a Phase 2 blocking-risk item. |
| Cancel running tasks while preserving logs and clearing PID fields | `minimum-slice` | Cancellation terminates PID, appends cancellation note, and clears PID fields in `lab_sidecar/runner/service.py:105`; CLI test asserts cancelled status and cleared PIDs in `tests/test_cli_smoke.py:222`. | CLI cancellation has a useful slice. MCP cancellation is missing and Phase 3 should add it after Phase 2 hardening. |
| Import/ingest existing experiment directories or files | `implemented` | `ingest_source` records existing source refs without copying source files in `lab_sidecar/runner/service.py:129`; tests cover directory ingest at `tests/test_cli_smoke.py:248` and file ingest at `tests/test_cli_smoke.py:295`. | No Phase 1 blocker. |
| Artifact duplicate handling for repeated generation | `implemented` | Current services upsert by artifact id in `lab_sidecar/collectors/service.py:266`, `lab_sidecar/figures/service.py:318`, `lab_sidecar/reports/service.py:332`, and `lab_sidecar/slides/service.py:698`; repeated-run tests cover collect at `tests/test_cli_smoke.py:584`, figures at `tests/test_cli_smoke.py:897`, report at `tests/test_cli_smoke.py:1103`, and slides at `tests/test_cli_smoke.py:1285` and `tests/test_cli_smoke.py:1600`. | Keep the upsert pattern when adding future artifacts. |
| `list` and `open` task commands from the product plan | `missing` | The CLI command set in `lab_sidecar/cli/app.py:52` through `lab_sidecar/cli/app.py:365` has no `list` or `open` command; only a helper `list_task_ids` exists in `lab_sidecar/runner/service.py:368`. | Phase 2 may add small wrappers if still useful, but they are not required for Phase 1. |

## Collection And Metrics

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| CSV metrics extraction | `implemented` | Collection service dispatches CSV files in `lab_sidecar/collectors/service.py:135`; CSV comparison test checks normalized metrics and summary in `tests/test_cli_smoke.py:371`. | No Phase 1 blocker. |
| JSON metrics extraction | `implemented` | Collection service dispatches JSON files in `lab_sidecar/collectors/service.py:140`; JSON benchmark test exists in `tests/test_cli_smoke.py:441`. | No Phase 1 blocker. |
| Run working-directory output discovery | `minimum-slice` | Scanner checks only run working-directory top-level files created after task start in `lab_sidecar/collectors/scan.py:74`; test verifies stale top-level CSV is ignored and new `metrics.csv` is collected in `tests/test_cli_smoke.py:416`. | Current behavior is intentionally conservative. Nested output discovery remains a follow-up unless explicit config selects files. |
| Bad CSV/JSON diagnostics without false outputs | `implemented` | Service writes collection summary even when no rows are collected in `lab_sidecar/collectors/service.py:91`; test covers bad JSON, empty CSV, and missing metric columns in `tests/test_cli_smoke.py:548`. | No Phase 1 blocker. |
| Explicit metrics configuration with `collect --config` | `missing` | CLI accepts `--config` and passes it to the service in `lab_sidecar/cli/app.py:166`; service only records `config_path` in the summary at `lab_sidecar/collectors/service.py:100` and `lab_sidecar/collectors/service.py:162`; there is no config parser or mapping branch in `lab_sidecar/collectors/service.py:48`. | Phase 4 must implement declared source files/globs, field mappings, units, aliases, and config diagnostics. |
| Simple log parsing for metrics | `missing` | Candidate scanner only supports `.csv` and `.json` in `lab_sidecar/collectors/scan.py:13`; collection service only dispatches `.csv` and `.json` in `lab_sidecar/collectors/service.py:135`. | Keep out of Phase 1. Phase 4 can decide whether a minimal regex log collector is required for V1. |
| Multi-seed mean/variance collection and plotting | `minimum-slice` | CSV comparison rows include `seed` and grouping evidence in `tests/test_cli_smoke.py:391`; auto figure generation supports grouped line plots in `lab_sidecar/figures/specs.py:247`. | There is no dedicated mean/variance aggregation acceptance. Treat as a Phase 4 figure-config and reproducibility follow-up. |

## Figures

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| Auto-generate static PNG/SVG figures | `implemented` | Auto planning selects line/bar specs in `lab_sidecar/figures/specs.py:172`; tests check PNG/SVG generation and saved spec in `tests/test_cli_smoke.py:615` and bar charts in `tests/test_cli_smoke.py:658`. | No Phase 1 blocker for first-pass static figures. |
| Explicit figure spec via YAML | `minimum-slice` | Spec parser requires `figure_id`, `chart_type`, `title`, `x`, and `y` in `lab_sidecar/figures/specs.py:208`; tests cover explicit line and bar specs in `tests/test_cli_smoke.py:717` and `tests/test_cli_smoke.py:761`. | Useful for current metrics columns. Phase 4 must align it with explicit collection mappings and units. |
| Figure quality refusal for bad specs or unreadable charts | `minimum-slice` | Missing metrics fields and quality refusals are handled in `lab_sidecar/figures/specs.py:188` and `lab_sidecar/figures/specs.py:364`; tests cover missing spec fields in `tests/test_cli_smoke.py:821` and too many categories in `tests/test_cli_smoke.py:867`. | Current guardrails are narrow. More chart-quality acceptance belongs in Phase 4/6. |
| Figure configuration is saved and reproducible | `minimum-slice` | Figure service writes `figure-spec.yaml` and `figure-summary.json` in `lab_sidecar/figures/service.py:71`; tests assert saved spec and summary in `tests/test_cli_smoke.py:637`. | Reproducibility is structural, not yet content-hash or deterministic-render verified. |

## Reports And Slides

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| Deterministic Markdown report fragment | `implemented` | Report command calls deterministic service in `lab_sidecar/cli/app.py:260`; report summary includes provenance, metrics, figures, failure/cancellation, and source artifacts in `lab_sidecar/reports/service.py:95`; test covers completed report generation in `tests/test_cli_smoke.py:946`. | No Phase 1 blocker for template-based Markdown. |
| Failed and cancelled tasks do not become success reports | `implemented` | Failure/cancelled templates branch on status in `lab_sidecar/reports/templates.py:156` and `lab_sidecar/reports/templates.py:226`; tests cover failed and cancelled reports in `tests/test_cli_smoke.py:1012` and `tests/test_cli_smoke.py:1031`. | Keep this invariant when adding richer reports. |
| Report conclusions do not invent unsupported values | `minimum-slice` | Templates state reports summarize existing artifacts and mark unknown content at `lab_sidecar/reports/templates.py:67`; tests assert failure reports are not success summaries in `tests/test_cli_smoke.py:1012`. | There is no general claim verifier that every numeric conclusion maps to an artifact row. Phase 5/6 must strengthen provenance acceptance. |
| Static PPTX deck generation with source metadata and QA checks | `minimum-slice` | Slides summary records source artifacts, truncations, QA checks, and included metrics/figures in `lab_sidecar/slides/service.py:592`; tests cover generated PPTX and summary in `tests/test_cli_smoke.py:1119`. | Good product-alpha slice. Full V1 claim still needs final provenance and real-scenario acceptance after Phases 2-5. |
| Slides failure/cancellation handling | `implemented` | Diagnostic context is detected in `lab_sidecar/slides/service.py:197`; tests cover failed decks at `tests/test_cli_smoke.py:1178` and cancelled decks at `tests/test_cli_smoke.py:1203`. | No Phase 1 blocker. |
| Slides no-invention for baseline deltas | `minimum-slice` | Tests assert missing baseline keeps `baseline_item` and `delta` null in `tests/test_cli_smoke.py:1524`. | This covers one deterministic inference path, not all possible slide claims. |

## MCP And Context Quarantine

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| MCP-facing adapter as thin layer over core services | `implemented` | MCP tools call runner/collector/figure/report/slides services in `lab_sidecar/mcp/tools.py:47`, `lab_sidecar/mcp/tools.py:76`, `lab_sidecar/mcp/tools.py:108`, `lab_sidecar/mcp/tools.py:136`, `lab_sidecar/mcp/tools.py:178`; server registers tools in `lab_sidecar/mcp/server.py:23`. | Keep MCP thin; do not add product-level multi-agent orchestration. |
| Context quarantine: omit full logs, metric rows, report bodies, artifact bodies by default | `minimum-slice` | Default omitted contract is defined in `lab_sidecar/mcp/responses.py:11`; `inspect_results` omits log tails unless requested in `lab_sidecar/mcp/tools.py:63`; tests assert omitted stdout/log tail/report preview at `tests/test_mcp_tools.py:69` and omitted stderr at `tests/test_mcp_tools.py:104`. | Strong adapter-level slice. Phase 3 should add bounded preview tests and final stdio acceptance after any response changes. |
| MCP background long task returns `task_id` without blocking main agent | `minimum-slice` | `run_experiment` defaults `background=True` in `lab_sidecar/mcp/tools.py:29`; test asserts running status and no log body in `tests/test_mcp_tools.py:117`; stdio smoke script calls `run_experiment` with `background=True` in `scripts/mcp_stdio_smoke.py:45`. | Phase 3 should keep this as the default and run real stdio smoke in a clean workspace. |
| MCP safety gate for workspace and dangerous commands | `minimum-slice` | `run_experiment` calls `assess_run_command` before running in `lab_sidecar/mcp/tools.py:37`; tests cover destructive commands, shell chaining confirmation, external cwd, and external absolute paths in `tests/test_mcp_tools.py:21`, `tests/test_mcp_tools.py:32`, `tests/test_mcp_tools.py:47`, and `tests/test_mcp_tools.py:56`. | This is not an OS sandbox and must not be documented as one. |
| Real stdio MCP smoke coverage | `minimum-slice` | Stdio smoke script exists and calls all five tools in `scripts/mcp_stdio_smoke.py:23`; public-alpha readiness records a passing smoke in `docs/public-alpha-readiness-acceptance.md:75`. | Phase 3 and Phase 6 design-goal acceptance must run this again in phase-specific clean workspaces. |
| MCP cancellation tool | `missing` | Server registers only `run_experiment`, `inspect_results`, `make_figures`, `generate_report_fragment`, and `generate_slides` in `lab_sidecar/mcp/server.py:23`; release notes list no MCP cancellation tool and mark it a known limit in `docs/public-alpha-release-notes.md:67`. | Add `cancel_experiment` in Phase 3 after Phase 2 cancellation/recovery is hardened. |

## Reproducibility And Provenance

| Design goal | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| Run tasks capture command, Python version, platform, selected environment | `minimum-slice` | Reproduce files are written in `lab_sidecar/runner/service.py:271`; tests assert `reproduce/command.txt` and `reproduce/env.json` exist in `tests/test_cli_smoke.py:121`. | Add explicit assertions for Python/platform/env contents and include dependency/Git metadata in Phase 5. |
| Ingest records source references without modifying source files | `minimum-slice` | `build_source_refs` records paths, size, modified time, candidate files in `lab_sidecar/storage/artifact_store.py:86`; tests assert source refs and source preservation in `tests/test_cli_smoke.py:248` and `tests/test_cli_smoke.py:295`. | Source file hashes are missing. Phase 5 should add hashes for collected/input files where practical. |
| Report and slides cite source artifacts | `minimum-slice` | Report source artifacts are collected in `lab_sidecar/reports/service.py:235`; slides source artifacts are collected in `lab_sidecar/slides/service.py:570`; tests assert report/slides source artifact fields in `tests/test_cli_smoke.py:946` and `tests/test_cli_smoke.py:1119`. | Good structural provenance. Phase 5 must prove every generated conclusion can trace to artifacts. |
| Git commit/status and dependency snapshot | `missing` | Reproduce env currently includes Python version, platform, working dir, and selected environment only in `lab_sidecar/runner/service.py:274`; tests only assert file existence at `tests/test_cli_smoke.py:121`. | Phase 5 should capture Git metadata and a practical dependency snapshot. |
| Input/source file hashes | `missing` | `build_source_refs` records size and modified time but no hash fields in `lab_sidecar/storage/artifact_store.py:86`; no tests assert hashes. | Phase 5 should add hashes for source refs and collected candidates. |

## Public Documentation And Acceptance Claims

| Design goal / claim area | Classification | Evidence | Gap / recommendation |
| --- | --- | --- | --- |
| README scope accuracy | `implemented` | README calls the project a local-first CLI runner in `README.md:3`; current scope excludes Web UI/FastAPI/AI/animation at `README.md:175`; MCP safety boundary is scoped to MCP-facing run in `README.md:161`. | No blocking Phase 1 overclaim found. |
| Public-alpha release notes scope accuracy | `implemented` | Release notes explicitly call the current state public alpha at `docs/public-alpha-release-notes.md:7`; known limits include no MCP cancellation and no CLI dangerous-command prompting at `docs/public-alpha-release-notes.md:65`. | No blocking Phase 1 overclaim found. |
| Phase 6 real product acceptance as proof of complete V1 design goal | `overclaimed` | Phase 6 final judgment says local-first workflow, MCP isolation, reproducible/traceable artifacts, and safety defaults are demonstrated at `docs/phase-6-real-product-acceptance.md:324`; code/test evidence above still leaves background recovery, explicit collect config, MCP cancellation, Git/dependency/hash provenance, and final design-goal acceptance gaps. | Treat Phase 6 record as high-fidelity public-alpha validation only. Do not use it as proof of full V1 completion. |
| Public-alpha readiness final judgment | `implemented` | Readiness acceptance recommends cautious public alpha and lists follow-ups at `docs/public-alpha-readiness-acceptance.md:271`. | No blocking Phase 1 overclaim found. |

## Phase Recommendations

- Phase 2 should focus on background task completion/failure refresh, stale worker recovery, cancellation robustness, and external-workspace long-task smoke.
- Phase 3 should harden MCP context quarantine contracts and add MCP cancellation if Phase 2 is stable.
- Phase 4 should implement explicit `collect --config`, align figure specs with mapped fields/units, and add config failure diagnostics.
- Phase 5 should add Git/dependency/source-hash provenance and stronger report/slides traceability checks.
- Phase 6 should rerun final V1 acceptance only after Phases 2-5 have blocking count 0.
