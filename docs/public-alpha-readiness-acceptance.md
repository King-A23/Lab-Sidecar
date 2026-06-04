# Public Alpha Readiness Acceptance

Date: 2026-06-05

Scope: Execute `docs/public-alpha-readiness-plan.md` conservatively. No Web UI, FastAPI, AI polishing, animation, remote runner, or broad refactor was added.

## Initial Audit

Read:

- `AGENTS.md`
- `docs/public-alpha-readiness-plan.md`

Initial status:

```text
 M PRODUCT_ITERATION_PLAN.md
 M README.md
 M lab_sidecar/cli/app.py
 M lab_sidecar/collectors/scan.py
 M lab_sidecar/slides/service.py
 M tests/test_cli_smoke.py
?? docs/phase-4-2-direct-run-collect-acceptance.md
?? docs/phase-4-real-sample-visual-acceptance.md
?? docs/phase-5-mcp-sidecar-acceptance.md
?? docs/phase-6-real-product-acceptance.md
?? docs/public-alpha-readiness-plan.md
?? docs/real-sample-visual-acceptance-checklist.md
?? lab_sidecar/mcp/
?? tests/test_mcp_tools.py
```

Existing worktree changes were treated as prior work and were not reverted.

## Priority 1: Release Baseline

Status: completed for readiness documentation; final commit organization remains a git hygiene step.

Changed files:

- `docs/public-alpha-readiness-acceptance.md`
- `docs/public-alpha-release-notes.md`

Validation:

- `py -3 -m pytest`: 64 passed before readiness edits.
- Final test command is recorded below.

Blocking:

- None for readiness content.

Follow-up:

- Split final commits by phase/readiness scope if this work is committed.

Out of scope:

- Publishing a GitHub release or packaging upload.

## Priority 2: MCP SDK Real Validation

Status: completed.

Changed files:

- `pyproject.toml`
- `scripts/mcp_stdio_smoke.py`
- `docs/mcp-host-config.md`
- `README.md`
- `PRODUCT_ITERATION_PLAN.md`
- `docs/phase-5-mcp-sidecar-acceptance.md`
- `docs/phase-6-real-product-acceptance.md`

Commands:

```powershell
py -3 -m pip install -e .[mcp]
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-mcp-stdio-smoke"
```

Install result:

- Editable `lab-sidecar==0.1.0` installed.
- Pinned `mcp==1.27.2` installed.
- MCP dependencies installed, including `anyio==4.13.0`, `httpx==0.28.1`, `starlette==1.2.1`, and `uvicorn==0.49.0`.

Smoke result:

```json
{
  "workspace": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-mcp-stdio-smoke",
  "server_log": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-mcp-stdio-smoke\\mcp-server.stderr.log",
  "tools": [
    "generate_report_fragment",
    "generate_slides",
    "inspect_results",
    "make_figures",
    "run_experiment"
  ],
  "task_id": "task_20260605_014548_a77a2c",
  "run_status": "running",
  "final_status": "completed",
  "metrics_rows": 5,
  "figure_count": 2,
  "report_path": ".lab-sidecar/tasks/task_20260605_014548_a77a2c/reports/report-fragment.md",
  "slide_count": 7,
  "blocked_command_status": "blocked",
  "artifact_count": 17
}
```

Omitted response contract verified:

```json
{
  "full_stdout": "omitted_by_default",
  "full_stderr": "omitted_by_default",
  "metrics_rows": "omitted_by_default",
  "artifact_bodies": "omitted_by_default"
}
```

Limitation:

- The smoke uses `run_experiment(background=True)` and polls `inspect_results`. This matches the long-task contract and avoids making the stdio tool call wait for the command body.
- A direct blocking `run_experiment(background=False)` stdio call was observed to stall until client timeout on Windows, even though the task eventually completed. Public alpha should prefer background mode for MCP command execution.

Blocking:

- None for real stdio smoke.

Follow-up:

- Test concrete host configs in specific hosts such as Claude Desktop or Codex.
- Consider `cancel_experiment`.

Out of scope:

- Remote runner, Web UI, FastAPI, hosted MCP gateway, or returning full artifact bodies through MCP.

## Priority 3: Safety Model Clarification

Status: completed.

Changed files:

- `README.md`
- `docs/mcp-host-config.md`
- `docs/public-alpha-release-notes.md`
- `docs/phase-5-mcp-sidecar-acceptance.md`
- `docs/phase-6-real-product-acceptance.md`

Clarified model:

- CLI `run` is a user-explicit local command execution path.
- MCP-facing `run_experiment` applies workspace and dangerous-command safety gates.
- Lab-Sidecar does not claim global command sandboxing, OS isolation, malware detection, or shell interception.

Validation:

```powershell
py -3 -m pytest tests/test_mcp_tools.py
```

Result:

- 7 passed.

Blocking:

- None.

Follow-up:

- Consider a future CLI prompt/confirmation policy, but do not imply it exists today.

Out of scope:

- OS sandboxing, containerization, malware detection, multi-user policy, or global shell interception.

## Priority 4: Artifact Protocol Alignment

Status: completed.

Changed files:

- `docs/artifact-protocol.md`

Updates:

- Added current `presentation` artifact type.
- Documented `slides/presentation-draft.pptx` and `slides/slides-summary.json`.
- Documented presentation provenance expectations and MCP response boundary.
- Added `media` / `animation` as deferred protocol reservations, not implemented features.

Blocking:

- None.

Follow-up:

- Keep future media protocol design-only until actual generation exists.

Out of scope:

- Implementing GIF, MP4, Manim, Remotion, native PowerPoint animation, or media rendering.

## Priority 5: Bad Input And Real Sample Hardening

Status: completed for focused alpha hardening.

Changed files:

- `tests/test_cli_smoke.py`
- `docs/phase-6-real-product-acceptance.md`
- `docs/public-alpha-release-notes.md`

Added coverage:

- malformed JSON
- empty CSV
- CSV missing metric columns
- repeated bad input collection without duplicate manifest summary artifacts

Validation:

```powershell
py -3 -m pytest tests/test_cli_smoke.py::test_collect_bad_and_empty_inputs_record_diagnostics_without_outputs tests/test_cli_smoke.py::test_collect_repeated_bad_input_does_not_duplicate_summary_artifact
```

Result:

- 2 passed.

Observed behavior:

- `collection-summary.json` is written even when collection fails.
- Bad JSON records `parse_failed`.
- Empty CSV and missing metric columns record `no_detected_metrics`.
- No normalized metrics CSV/JSON outputs are written when no rows are collected.
- Repeated failed collection does not duplicate `metrics_collection_summary` in manifest.

Blocking:

- None for public alpha.

Follow-up:

- Add broader real-world malformed fixtures after alpha.
- Improve CLI wording to distinguish "no candidates" from "candidates found but none collectible".

Out of scope:

- Automatically modifying, deleting, moving, or repairing user source files.

## Final Validation

Final commands:

```powershell
py -3 -m pytest
git status --short
```

Results:

- `py -3 -m pytest`: 66 passed.
- Final `git status --short` still showed uncommitted readiness and prior phase changes before commit organization.

## Public Alpha Judgment

Recommended for cautious public alpha if final `py -3 -m pytest` remains green and the worktree is organized into reviewable commits.

Must-fix-before-alpha:

- None currently identified.

Follow-up after alpha:

- Host-specific MCP config validation.
- MCP cancellation tool.
- CLI dangerous-command prompt/confirmation policy if desired.
- Broader malformed-result fixtures.
- Better project figure grouping for mixed metrics.
- Better long-label wrapping in project comparison slides.
