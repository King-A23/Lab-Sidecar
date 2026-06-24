# Post-Open-Source Stage 4 Acceptance

Date: 2026-06-18

## Phase Goal

Harden the Agent-native delegation path so Codex/MCP hosts can delegate noisy
local experiment and artifact work while default responses remain bounded,
task-scoped, and useful for follow-up reasoning.

Stage 4 preserves Lab-Sidecar's product boundary: local-first, file-first,
CLI-first, artifact-first, and AI-optional. Subagents were used only for
execution coordination during repository review, not as Lab-Sidecar product
architecture.

## Starting State

Stage 3 had already deepened explicit `collect --config` support for nested
and messy CSV/JSON result directories. V2 host tools and the MCP mirror existed,
including `delegate_experiment_artifacts`, `inspect_sidecar_task`,
`preview_sidecar_artifact`, and `cancel_sidecar_task`.

The Stage 4 audit identified hardening gaps:

- direct V2 cancellation raised on completed or missing tasks instead of
  returning bounded not-applicable responses
- MCP `cancel_experiment` had the same missing/completed-task escape path
- preview rejection for raw and worker-audit content relied too much on
  registration and suffix behavior
- small CSV/Markdown/log previews could return a complete small artifact body
- log preview read the whole log internally before tailing
- package omission inventory did not record `intelligence/` as omitted
  wholesale
- plugin and host docs needed clearer delegation examples, anti-patterns,
  preview examples, cancellation examples, and Stage 2/Stage 3 relationships
- stdio smoke did not exercise V2 cancellation

## Implemented Scope

- Added bounded direct V2 `cancel_sidecar_task` responses for completed,
  failed, cancelled, and missing tasks.
- Added bounded MCP `cancel_experiment` responses for completed and missing
  tasks while preserving CLI cancellation state errors.
- Added explicit preview denial for raw artifacts and worker audit paths under
  `intelligence/`, including provider prompt/response filenames.
- Changed CSV, Markdown, and log previews to avoid returning complete small
  artifact bodies; previews now indicate `withheld_complete_body`.
- Changed log previews to use a bounded deque tail instead of reading the whole
  log into memory.
- Recorded task-local `intelligence/` as an omitted package entry whenever it
  exists; package export remains allowlist-based and does not copy worker audit
  files.
- Extended the real stdio MCP smoke to start a background task and cancel it
  through the V2 `cancel_sidecar_task` mirror.
- Updated host/plugin documentation with when-to-delegate, when-not-to-delegate,
  bounded preview examples, cancellation behavior, package export relationship,
  Stage 3 explicit config guidance, and plugin validation.
- Added regression tests for completed/missing cancellation, inspect-after-V2
  cancellation, raw/worker-audit preview rejection, small artifact body
  withholding, and MCP cancellation consistency.

## Deferred Scope

- No new Web UI, FastAPI app, hosted service, remote runner, cloud sync, or
  generic multi-agent framework.
- No change to CLI `run` safety semantics.
- No OS sandboxing or malware scanning claim.
- No broad recursive workspace discovery in host tools.
- No default cloud AI/provider calls.
- Worker-run-id path-segment validation remains a future hardening item; normal
  generated IDs are safe and worker files remain task-local.

## Changed Files

- `lab_sidecar/intelligence/preview.py`
- `lab_sidecar/intelligence/tools.py`
- `lab_sidecar/mcp/tools.py`
- `lab_sidecar/storage/package_export.py`
- `scripts/mcp_stdio_smoke.py`
- `tests/test_v2_host_integration.py`
- `tests/test_mcp_tools.py`
- `README.md`
- `docs/v2-host-integration.md`
- `docs/mcp-host-config.md`
- `plugins/lab-sidecar/skills/use-lab-sidecar/SKILL.md`
- `docs/post-open-source-stage-4-acceptance.md`

No collector, figure, report, slide, or CLI runner behavior was changed beyond
shared cancellation/package/preview support.

## Host And MCP Scenarios

Direct V2 host tests now cover:

- delegate, inspect, preview, and cancel smoke
- cancellation of running tasks
- completed and missing cancellation as bounded `not_cancelled` responses
- inspect after cancellation without stdout leakage
- CSV, Markdown, image, PPTX, and log previews
- external and unregistered path rejection
- unsupported registered artifact rejection
- explicit raw and worker-audit preview rejection
- small CSV/Markdown/log body withholding
- row and line caps for oversized preview requests

MCP tests now cover:

- V1 `cancel_experiment` running cancellation
- V1 `cancel_experiment` completed/missing not-applicable responses
- V2 `cancel_sidecar_task` completed/missing not-applicable responses
- V2 delegate/inspect/preview bounded context
- command safety gate preservation for V2 delegation

The real stdio smoke now lists and exercises all ten tools:

```text
cancel_experiment
cancel_sidecar_task
delegate_experiment_artifacts
generate_report_fragment
generate_slides
inspect_results
inspect_sidecar_task
make_figures
preview_sidecar_artifact
run_experiment
```

## Workspaces And Task IDs

MCP stdio smoke workspace:

- `/private/tmp/lab-sidecar-stage-4-mcp-smoke`

MCP stdio smoke task ids:

- V1 background run: `task_20260618_164648_6baa8c`
- V2 delegate/preview task: `task_20260618_164649_b14b7d`
- V1 cancellation task: `task_20260618_164649_f3dabd`
- V2 cancellation task: `task_20260618_164650_e21ad9`

Smoke output summary:

```json
{
  "run_status": "running",
  "final_status": "completed",
  "metrics_rows": 5,
  "figure_count": 2,
  "slide_count": 7,
  "v2_status": "completed",
  "v2_preview_type": "csv_rows",
  "cancel_status": "cancelled",
  "v2_cancel_status": "cancelled",
  "blocked_command_status": "blocked",
  "artifact_count": 19
}
```

## Preview Contract Evidence

Implementation evidence:

- `preview_sidecar_artifact` still resolves only registered task artifacts plus
  task stdout/stderr logs.
- Resolved previews must stay inside the task directory.
- Raw artifacts and paths under `intelligence/` are explicitly denied.
- CSV previews cap at 20 rows; Markdown/text/log previews cap at 80 lines.
- CSV, Markdown, and log previews withhold at least one row/line when the
  artifact would otherwise fit entirely in the requested cap.
- Log preview now streams into a fixed-size tail buffer.

Regression evidence:

- `test_preview_returns_bounded_csv_markdown_image_pptx_and_log`
- `test_preview_does_not_return_complete_artifact_bodies_by_default`
- `test_preview_withholds_complete_small_csv_markdown_and_log_bodies`
- `test_preview_rejects_external_and_unregistered_paths`
- `test_preview_rejects_unsupported_registered_artifact`
- `test_preview_explicitly_rejects_registered_raw_and_worker_audit_artifacts`
- `test_preview_rejects_worker_audit_paths_even_when_task_local`
- `test_preview_caps_large_requested_limits`

## Cancellation Evidence

Direct V2:

- running task cancellation returns `status == "cancelled"`
- completed task cancellation returns `status == "not_cancelled"` with
  `risk_flags == ["cancel_sidecar_task_not_applicable"]`
- missing task cancellation returns `status == "not_cancelled"` with
  `risk_flags == ["cancel_sidecar_task_missing"]`
- inspect after cancellation returns cancelled state without log body leakage

MCP:

- V1 `cancel_experiment` cancels running tasks
- V1 `cancel_experiment` returns bounded not-applicable responses for completed
  and missing tasks
- V2 `cancel_sidecar_task` returns bounded not-applicable responses for
  completed and missing tasks
- stdio smoke cancelled `task_20260618_164650_e21ad9` through
  `cancel_sidecar_task`

CLI:

- Existing CLI tests still preserve state-error behavior for non-running tasks.
- Existing stale worker recovery tests still mark stale running tasks failed and
  clear PID fields.

## Worker Audit Evidence

- Worker run directories remain task-local under
  `.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/`.
- Default V2 responses still use the omitted contract with
  `worker_prompt_response: omitted_by_default`.
- Preview rejects registered or unregistered worker-audit paths.
- Package export continues to use an allowlist and does not copy
  `intelligence/`; the package index now records `intelligence/` as omitted
  when present.
- Existing package tests still assert worker logs, provider prompt/response
  bodies, sandbox files, SQLite index, raw source files, and unrelated workspace
  files are not copied.

## Plugin / Docs Evidence

Updated docs and plugin guidance now cover:

- when to delegate and when not to delegate
- canonical default response shape
- bounded preview examples for CSV, Markdown, logs, image metadata, and PPTX
  metadata
- cancellation examples and not-applicable behavior
- `package <task_id>` for shareable task folders
- explicit `collect --config` for nested or messy result directories
- MCP as a thin local adapter, not a hosted product surface
- plugin validation command

Plugin validation:

```text
.venv/bin/python <plugin-creator>/scripts/validate_plugin.py plugins/lab-sidecar
Plugin validation passed: <repo>/plugins/lab-sidecar
```

Note: running the same validator with the system `python` failed because that
interpreter did not have `yaml`; the repository `.venv` validation passed.

## Test Results

Whitespace:

```text
git diff --check
passed
```

Focused host/MCP/package regression:

```text
.venv/bin/python -m pytest tests/test_v2_host_integration.py tests/test_mcp_tools.py tests/test_cli_smoke.py::test_package_completed_task_exports_allowlisted_artifacts_only -q
28 passed in 2.80s
```

Real MCP stdio smoke:

```text
.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-4-mcp-smoke
passed
```

Full test suite:

```text
.venv/bin/python -m pytest -q
137 passed in 11.31s
```

## Blocking

None.

## Follow-Up

- Add worker-run-id path-segment validation around helper/public worker-run
  paths.
- Consider recording additional individual worker audit filenames in package
  omission inventory, even though `intelligence/` is already omitted wholesale
  and not copied.
- Add a future Stage 5 provenance pass that ties report and slide claims to
  source artifact hashes and rows.

## Out Of Scope

- hosted execution or remote runner behavior
- Web UI or FastAPI
- generic multi-agent product features
- broad arbitrary file preview or export
- default AI analysis or cloud provider calls
- OS-level sandboxing or malware scanning

## Final Judgment

Stage 4 passes.

The Agent-native delegation path is harder to misuse: defaults stay bounded,
previews are task-artifact scoped and explicitly deny raw/worker audit content,
cancellation is predictable across direct V2 and MCP paths, worker audit files
remain local and omitted by default, plugin/host guidance is concrete, and the
real stdio MCP smoke plus full repository tests pass.
