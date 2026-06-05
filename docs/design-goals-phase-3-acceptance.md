# Design Goals Phase 3 Acceptance

Date: 2026-06-05

Phase: Phase 3 - Context Quarantine And Delegation Layer

## Scope

Hardened the local MCP-facing delegation layer so main-agent callers receive bounded summaries, artifact paths, explicit omitted contracts, and cancellation control for background experiments.

This phase did not add Web UI, FastAPI, remote execution, hosted MCP gateway, AI polishing, animation, or a generic multi-agent product architecture. MCP remains a thin local adapter over existing runner/collector/figure/report/slides services.

## Initial Checks

Initial workspace:

```text
C:\code\Lab-Sidecar
```

Initial command:

```powershell
git status --short
```

Result:

```text
(clean)
```

Documents and code inspected:

- `AGENTS.md`
- `docs/design-goals-completion-plan.md`
- `docs/design-goals-gap-matrix.md`
- `README.md`
- `docs/public-alpha-release-notes.md`
- `docs/mcp-host-config.md`
- `lab_sidecar/mcp/tools.py`
- `lab_sidecar/mcp/responses.py`
- `lab_sidecar/mcp/server.py`
- `tests/test_mcp_tools.py`
- `scripts/mcp_stdio_smoke.py`

## Changed Files

- `lab_sidecar/mcp/tools.py`
- `lab_sidecar/mcp/server.py`
- `tests/test_mcp_tools.py`
- `scripts/mcp_stdio_smoke.py`
- `docs/design-goals-phase-3-acceptance.md`

## Commands

Targeted MCP tests:

```powershell
py -3 -m pytest tests\test_mcp_tools.py
```

Real stdio MCP smoke:

```powershell
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-phase3-mcp"
```

Full validation:

```powershell
py -3 -m pytest
git status --short
```

## Workspace Paths

Repository workspace:

```text
C:\code\Lab-Sidecar
```

External MCP smoke workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp
```

MCP server log:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\mcp-server.stderr.log
```

## Task ID Values

Real stdio MCP smoke task ids:

- Completed background run: `task_20260605_180201_bb72ff`
- Cancelled background run: `task_20260605_180214_fdb6bd`

Pytest also generated temporary task ids under pytest-managed workspaces; those are not retained as acceptance artifacts.

## Generated Artifacts

External completed MCP smoke artifacts:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\manifest.json`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\stdout.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\stderr.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\metrics\normalized_metrics.csv`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\figures\figure-summary.json`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\reports\report-fragment.md`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\slides\presentation-draft.pptx`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180201_bb72ff\slides\slides-summary.json`

External cancelled MCP smoke artifacts:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180214_fdb6bd\manifest.json`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180214_fdb6bd\stdout.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180214_fdb6bd\stderr.log`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180214_fdb6bd\reproduce\command.txt`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase3-mcp\.lab-sidecar\tasks\task_20260605_180214_fdb6bd\reproduce\env.json`

Repository artifact generated:

- `docs/design-goals-phase-3-acceptance.md`

## Implementation Summary

- Added `LabSidecarMCPTools.cancel_experiment`, backed by the existing local `RunnerService.cancel`.
- Registered `cancel_experiment` in the stdio MCP server.
- `inspect_results` now explicitly marks `log_tail` as `omitted_by_default` unless `include_log_tail=True`; when requested, it marks `bounded_tail_returned`.
- Existing default omitted contract remains: full stdout, full stderr, metric rows, and artifact bodies are omitted by default.
- Report Markdown remains omitted by default; requested previews are bounded to 2000 characters.
- Updated `scripts/mcp_stdio_smoke.py` to expect 6 tools and verify cancellation through a real stdio client/server flow.

## Test Results

Targeted MCP tests:

```text
9 passed in 21.84s
```

Real stdio MCP smoke output:

```json
{
  "workspace": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-design-phase3-mcp",
  "server_log": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-design-phase3-mcp\\mcp-server.stderr.log",
  "tools": [
    "cancel_experiment",
    "generate_report_fragment",
    "generate_slides",
    "inspect_results",
    "make_figures",
    "run_experiment"
  ],
  "task_id": "task_20260605_180201_bb72ff",
  "run_status": "running",
  "final_status": "completed",
  "metrics_rows": 5,
  "figure_count": 2,
  "report_path": ".lab-sidecar/tasks/task_20260605_180201_bb72ff/reports/report-fragment.md",
  "slide_count": 7,
  "cancel_task_id": "task_20260605_180214_fdb6bd",
  "cancel_status": "cancelled",
  "blocked_command_status": "blocked",
  "omitted_contract": {
    "full_stdout": "omitted_by_default",
    "full_stderr": "omitted_by_default",
    "metrics_rows": "omitted_by_default",
    "artifact_bodies": "omitted_by_default"
  },
  "artifact_count": 17
}
```

Full test suite:

```text
74 passed in 145.03s
```

Final `git status --short` before commit:

```text
 M lab_sidecar/mcp/server.py
 M lab_sidecar/mcp/tools.py
 M scripts/mcp_stdio_smoke.py
 M tests/test_mcp_tools.py
?? docs/design-goals-phase-3-acceptance.md
```

## Blocking

- None for Phase 3.

## Follow-Up

- Host-specific MCP configuration remains a follow-up; this phase validates the stdio server/client contract in a clean local workspace.
- Richer MCP policy configuration remains follow-up.
- Phase 4 should implement explicit metrics configuration; Phase 3 did not touch collector config behavior.
- Phase 5 should improve reproducibility/provenance completeness; Phase 3 did not add Git/dependency/source-hash capture.

## Out Of Scope

- Hosted MCP gateway.
- Remote execution.
- Generic agent-to-agent protocol.
- Web UI or FastAPI.
- AI polishing or autonomous analysis.
- Animation, GIF, MP4, Manim/Remotion, or PowerPoint native animation.
- Returning complete logs, complete metrics rows, complete report Markdown, artifact bodies, or PPT contents by default.

## Final Judgment

Phase 3 passes. The MCP-facing adapter now exposes cancellation, preserves `run_experiment(background=True)` as the default long-task path, keeps full logs/metric rows/report bodies/artifact bodies omitted by default, provides bounded log tails and report previews only on request, and passes both targeted tests and real stdio smoke in a clean workspace.

Recommendation: proceed to Phase 4 after committing this Phase 3 baseline.

