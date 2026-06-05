# Design Goals Completion Plan

Date: 2026-06-05

## Purpose

This document is the execution plan for moving Lab-Sidecar from a public-alpha vertical slice to the full V1 product intent described in `PRODUCT_ITERATION_PLAN.md`.

Current code already has a useful minimum chain:

```text
CLI / runner / collector / figures / report / slides / MCP adapter
```

That is not the same as completing the original design goal:

```text
local long-experiment Sidecar
  -> context quarantine
  -> artifact-first delegation layer
  -> reproducible, inspectable outputs
```

The existing Phase 6 acceptance record is kept as an early high-fidelity validation record. It must not be treated as proof that the complete V1 design goal is done. This plan defines the remaining phases needed before that claim is acceptable.

## Execution Rules

- Keep the product CLI-first, file-first, and local-first.
- Do not add Web UI, FastAPI, remote runner, AI polishing, animation, hosted services, or a generic multi-agent framework.
- Goal-mode manager and subagents are execution coordination roles only. Lab-Sidecar itself should remain a Sidecar / delegation layer, not an autonomous multi-agent system.
- Preserve existing user or agent changes. Always start each phase with `git status --short` and review relevant diffs before editing.
- Each phase must end with a written acceptance record:

```text
docs/design-goals-phase-<n>-acceptance.md
```

Each acceptance record must include:

- changed files
- commands
- workspace paths
- task_id values
- generated artifacts
- test results
- blocking / follow-up / out-of-scope
- final judgment for that phase

Every phase must run:

```powershell
py -3 -m pytest
git status --short
```

Targeted tests and smoke commands are required whenever the phase touches a specific subsystem.

## Phase 1: Design Gap Baseline

### Goal

Produce a code-level gap matrix that maps the current implementation to the V1 design goals in `PRODUCT_ITERATION_PLAN.md`.

This phase should not implement product features unless a tiny documentation correction is needed to keep claims accurate.

### Manager Agent Delegation

- Documentation audit subagent: compare README, release notes, public alpha docs, Phase 6 docs, and product plan for overclaims.
- Code audit subagent: inspect CLI, runner, collector, figure, report, slides, storage, and MCP modules.
- Test audit subagent: inspect tests for coverage of long tasks, context quarantine, explicit config, reproducibility, and artifact provenance.

### Subsystems To Audit

- CLI commands: `run`, `status`, `logs`, `cancel`, `ingest`, `collect`, `figures`, `report`, `slides`, `artifacts`.
- Runner: background worker, PID tracking, refresh, cancel, failure finalization.
- Collectors: candidate scanning, CSV/JSON support, `collect --config` behavior, log parsing status.
- Figures: auto planning, explicit spec behavior, multi-seed and benchmark support.
- Reports/slides: provenance, failure handling, bounded content, non-invented conclusions.
- MCP: response shape, omitted content, stdio smoke coverage, missing cancellation tool.
- Storage: manifest truth source, SQLite index, recoverability, artifact duplicate handling.

### Required Output

Create:

```text
docs/design-goals-gap-matrix.md
```

The matrix must classify each design goal as one of:

- `implemented`
- `minimum-slice`
- `missing`
- `deferred`
- `overclaimed`

The matrix must include evidence links to files or tests.

### Acceptance Commands

```powershell
py -3 -m pytest
git status --short
```

### Blocking Criteria

- Any public doc still claims complete V1 design-goal fulfillment when evidence only supports public-alpha or high-fidelity validation.
- No clear gap matrix exists for the manager agent to use in later phases.

### Follow-Up Criteria

- Gaps that require implementation belong to later phases, not Phase 1.

### Out Of Scope

- Feature implementation.
- New CLI or MCP tools.
- New examples beyond audit fixtures.

## Phase 2: Long Experiment Sidecar Core

### Goal

Make the local long-experiment runner reliable enough to satisfy the "experiment Sidecar" design goal.

The target flow is:

```text
labsidecar run "<command>" --background
  -> status
  -> logs --tail
  -> refresh/recover after terminal close
  -> cancel when needed
  -> completed/failed/cancelled manifest
```

### Manager Agent Delegation

- Runner subagent: harden process lifecycle, status refresh, cancellation, and worker failure handling.
- CLI subagent: improve `status`, `logs`, `cancel`, and add minimal `list` / `open` if implementation remains small.
- Test subagent: create deterministic long-task, worker-exit, cancellation, and recovery tests.
- Acceptance subagent: run clean external workspace smokes and record results.

### Implementation Targets

- Preserve one task directory per run under `.lab-sidecar/tasks/<task_id>/`.
- Ensure `manifest.json` remains the source of truth.
- Ensure SQLite can be deleted and the task remains inspectable from files.
- Make background task refresh robust when:
  - child process is still running
  - child process exited
  - worker process exited but manifest is still `running`
  - task was cancelled
- Keep CLI `run` as a user-explicit local command path. Do not add MCP safety gate behavior to CLI run.

### Public Interface Targets

Harden existing:

- `run --background`
- `status`
- `logs --tail`
- `logs --stream`
- `cancel`

Plan-compatible additions:

- `list`: list recent tasks from manifest/index.
- `open`: print or open the task artifact directory.

If `list` or `open` are added, they must be small CLI wrappers over existing file/index state.

### Required Tests

- Background task returns quickly with status `running`.
- Status refresh eventually moves a completed background task to `completed`.
- Failed background task records exit code and failure summary.
- Cancelled background task records `cancelled`, clears PID fields, and keeps logs.
- Deleting `index.sqlite` does not prevent status/logs/artifacts from working.
- Simulated worker exit does not leave an unrecoverable task forever without diagnostics.

### Acceptance Commands

Use a temporary workspace outside the repo:

```powershell
$workspace = Join-Path $env:TEMP 'lab-sidecar-design-phase2'
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "<long task command>" --background
py -3 -m lab_sidecar.cli.app status <task_id>
py -3 -m lab_sidecar.cli.app logs <task_id> --tail 20
py -3 -m lab_sidecar.cli.app cancel <task_id>
py -3 -m pytest
git status --short
```

### Blocking Criteria

- A background task can remain `running` forever after the process has exited and no diagnostic is recorded.
- Cancellation silently loses logs or leaves stale PID fields.
- Closing the launching terminal prevents later status inspection.

### Follow-Up Criteria

- Sophisticated scheduler, parallel queue, resource limits, or remote execution.

### Out Of Scope

- Remote runner.
- Web monitoring UI.
- Container or OS sandboxing.

## Phase 3: Context Quarantine And Delegation Layer

### Goal

Make MCP and main-agent delegation behavior match the original context quarantine design.

The main agent should be able to delegate work and continue with:

```text
task_id
bounded summary
artifact list
next actions
```

It should not receive full stdout, full stderr, complete metric rows, report bodies, PPT contents, or artifact bodies by default.

### Manager Agent Delegation

- MCP subagent: harden tool response contracts and add missing cancellation if needed.
- Safety subagent: keep MCP workspace and dangerous-command gate conservative without claiming global safety.
- Context-quarantine test subagent: assert omitted defaults and bounded previews.
- Stdio smoke subagent: run real MCP client/server smoke in a clean workspace.

### Implementation Targets

- Keep existing tools:
  - `run_experiment`
  - `inspect_results`
  - `make_figures`
  - `generate_report_fragment`
  - `generate_slides`
- Add `cancel_experiment` if Phase 2 cancellation is stable.
- Keep `run_experiment(background=True)` as the default MCP long-task path.
- Keep `inspect_results` log tails opt-in and bounded.
- Responses must include an `omitted` contract explaining what was not returned.

### Required Tests

- `run_experiment(background=True)` returns `task_id` without full logs.
- `inspect_results` default response omits `log_tail`.
- `inspect_results(include_log_tail=True)` returns bounded tails only.
- Failed task response includes failure summary but not full stderr.
- Report preview is omitted by default and bounded when requested.
- Destructive MCP command remains blocked.
- Workspace-external cwd and sensitive external output paths remain blocked.
- `cancel_experiment` cancels a running task if added.

### Acceptance Commands

```powershell
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-phase3-mcp"
py -3 -m pytest tests\test_mcp_tools.py
py -3 -m pytest
git status --short
```

The acceptance record must include the MCP smoke JSON output and note any host-specific limitations.

### Blocking Criteria

- MCP returns complete logs, complete metrics rows, report bodies, or artifact bodies by default.
- Long MCP task blocks until completion instead of returning a task id.
- MCP safety claims exceed what the code actually enforces.

### Follow-Up Criteria

- Host-specific config testing for individual clients.
- Richer policy configuration.

### Out Of Scope

- Hosted MCP gateway.
- Remote execution.
- Generic agent-to-agent protocol.

## Phase 4: Explicit Metrics And Figure Configuration

### Goal

Make explicit configuration reliable so V1 does not depend only on automatic guessing.

The design target is:

```text
automatic detection helps
explicit config must work
```

### Manager Agent Delegation

- Collector config subagent: implement or harden `collect --config`.
- Figure config subagent: align figure specs with explicit metric mappings and source selection.
- Fixture subagent: add realistic CSV/JSON/log fixtures for non-ML and multi-seed experiments.
- Test subagent: cover bad config, missing columns, units, grouping, and reproducibility.

### Implementation Targets

`collect --config` must support a small stable YAML shape for:

- declared source files or glob patterns inside the workspace or ingested source refs
- metric field mapping
- optional units
- optional group fields
- optional run/seed/model/method aliases

Figure generation must support explicit specs without relying on auto priority lists.

If a config references missing files or fields, commands must fail with clear diagnostics and write summary files where possible.

### Required Tests

- Explicit config maps nonstandard CSV columns to normalized metric names.
- Explicit config selects declared files and ignores unrelated CSV/JSON candidates.
- Missing configured field fails with clear message.
- Units are recorded in collection or figure summary.
- Figure spec can use mapped fields.
- Re-running collect/figures with the same config is stable and does not duplicate manifest artifacts.

### Acceptance Commands

```powershell
py -3 -m lab_sidecar.cli.app collect <task_id> --config metrics.yaml
py -3 -m lab_sidecar.cli.app figures <task_id> --spec figure.yaml
py -3 -m pytest
git status --short
```

### Blocking Criteria

- `collect --config` accepts a path but does not affect collection behavior.
- Explicit config cannot make a real nonstandard experiment collect and plot successfully.
- Config failures do not leave usable diagnostics.

### Follow-Up Criteria

- TensorBoard support.
- Complex log parsing.
- Interactive charting.

### Out Of Scope

- AI-based schema inference.
- Arbitrary notebook parsing.

## Phase 5: Reproducibility And Artifact Completeness

### Goal

Make generated outputs sufficiently reproducible and traceable for course, research, and benchmark use.

### Manager Agent Delegation

- Reproducibility subagent: capture Git, dependency, Python, command, cwd, and selected environment information.
- Artifact protocol subagent: align manifest, summaries, and docs.
- Provenance test subagent: verify every generated report/slide/figure can trace source artifacts.
- Safety subagent: confirm original user files are not overwritten or moved.

### Implementation Targets

Task reproduce data should include:

- command
- working directory
- Python version
- platform
- selected environment variables
- dependency snapshot where practical
- Git commit/status when cwd is inside a Git repository
- input/source file hashes for collected candidate files

Manifest and summary files must allow a user to answer:

- What command or source produced this task?
- What files were collected?
- What generated this figure?
- What did the report or slides cite?
- What was omitted or truncated?

SQLite remains an index only. It must not become the only place where provenance exists.

### Required Tests

- Run task writes reproducibility metadata.
- Ingest task writes source refs and hashes for candidate files.
- Report summary references metrics, collection summary, figure summary, stderr, and manifest.
- Slides summary references manifest, metrics, figures, report, logs, and source refs where available.
- Deleting SQLite does not remove provenance inspectability.
- Re-running report/slides/figures does not duplicate artifact IDs.

### Acceptance Commands

```powershell
py -3 -m lab_sidecar.cli.app run "<command>"
py -3 -m lab_sidecar.cli.app collect <task_id>
py -3 -m lab_sidecar.cli.app figures <task_id>
py -3 -m lab_sidecar.cli.app report <task_id>
py -3 -m lab_sidecar.cli.app slides <task_id>
py -3 -m lab_sidecar.cli.app artifacts <task_id>
py -3 -m pytest
git status --short
```

### Blocking Criteria

- Generated report or slides contain values or claims that cannot be traced to artifacts.
- Reproducibility metadata is absent for run-mode tasks.
- Source files are copied, deleted, moved, or overwritten without explicit user action.

### Follow-Up Criteria

- Lockfile-specific dependency parsers.
- Dataset versioning beyond file hashes.

### Out Of Scope

- Cloud provenance service.
- Team audit system.

## Phase 6: Real V1 Acceptance

### Goal

Run final V1 acceptance after Phases 1-5 are complete.

This phase determines whether Lab-Sidecar can reasonably claim the original V1 design goal:

```text
local-first experiment Sidecar
  + context quarantine
  + artifact-first delegation layer
  + reproducible report artifacts
```

### Manager Agent Delegation

- Scenario subagent: prepare at least 3 real or high-fidelity project workspaces.
- CLI acceptance subagent: run direct CLI flows.
- MCP acceptance subagent: run stdio delegation flows.
- Visual/artifact subagent: inspect reports, figures, PPTX, summaries, and provenance.
- Release judgment subagent: classify blocking / follow-up / out-of-scope and make final recommendation.

### Required Scenarios

At least 3 scenarios must pass, and together they must cover:

- long successful run
- failed run with diagnostic artifacts
- multi-result or multi-seed benchmark
- course/project report or presentation material

At least one scenario must use `run --background`. At least one scenario must use MCP stdio delegation. At least one scenario must use explicit metrics or figure configuration from Phase 4.

### Required CLI Flow

```powershell
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "<real or high-fidelity command>" --background
py -3 -m lab_sidecar.cli.app status <task_id>
py -3 -m lab_sidecar.cli.app logs <task_id> --tail 20
py -3 -m lab_sidecar.cli.app collect <task_id>
py -3 -m lab_sidecar.cli.app figures <task_id>
py -3 -m lab_sidecar.cli.app report <task_id>
py -3 -m lab_sidecar.cli.app slides <task_id>
py -3 -m lab_sidecar.cli.app artifacts <task_id>
```

Adjust only where the scenario is intentionally failed or ingest-based.

### Required MCP Flow

```text
run_experiment(background=True)
inspect_results
make_figures
generate_report_fragment
generate_slides
cancel_experiment, if implemented
```

The MCP acceptance record must prove:

- long task does not block the main agent
- full logs are omitted by default
- artifact bodies are omitted by default
- bounded diagnostics are available on request
- final answer can be composed from summary and artifact list

### Required Final Checks

```powershell
py -3 -m pytest
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-v1-mcp"
git status --short
```

If PPTX files are produced, render or inspect them using the existing visual acceptance checklist.

### Blocking Criteria

- Any scenario cannot produce expected metrics, figures, report, and artifact list unless it is intentionally a failed-run diagnostic scenario.
- Main-agent/MCP flow requires complete logs or artifact bodies to explain the result.
- Failed tasks lose command, cwd, exit code, stderr, or diagnostic summary.
- Original user project files are silently modified, deleted, moved, or polluted with task output.
- Any report, slide, or summary invents unsupported numerical conclusions.
- Public docs still overclaim V1 completion beyond the actual acceptance evidence.

### Follow-Up Criteria

- Host-specific MCP configs.
- Better project grouping and report wording.
- More real malformed-result fixtures.
- Wider chart catalog.

### Out Of Scope

- Web UI.
- FastAPI.
- Remote runner.
- AI polishing or autonomous analysis.
- Animation, GIF, MP4, Manim, Remotion, or PowerPoint native animation.
- Generic multi-agent framework.

## Final V1 Completion Standard

Lab-Sidecar can be called complete for the original V1 design goal only when all of the following are true:

- Phase 1-6 acceptance records exist and have blocking count 0.
- `py -3 -m pytest` passes.
- Clean CLI smoke passes outside the repository.
- MCP stdio smoke passes in a clean workspace.
- At least 3 real or high-fidelity scenarios pass full acceptance.
- Long experiment delegation is proven with `run --background` and MCP background execution.
- Complete logs, metric rows, report bodies, PPT contents, and artifact bodies are not returned to the main agent by default.
- Every generated conclusion can be traced to manifest, metrics, figures, report, slides summary, logs, or source refs.
- The original source project remains unmodified unless the user command itself explicitly writes there.
- README, release notes, public alpha docs, and acceptance records make no claims beyond the evidence.
