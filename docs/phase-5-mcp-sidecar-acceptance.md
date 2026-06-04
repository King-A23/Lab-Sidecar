# Phase 5 MCP Sidecar Acceptance

Date: 2026-06-04 19:22 +08:00

Scope: Phase 5 minimal MCP-facing integration. MCP remains an adapter layer over the existing core services. This phase does not add Web UI, FastAPI, remote execution, AI analysis, animation, GIF, MP4, Manim, or Remotion.

## Decision

Phase 5 is implemented as an experimental local MCP-facing tool adapter under `lab_sidecar/mcp/`.

Initial Phase 5 acceptance on 2026-06-04 did not have the optional Python MCP SDK installed:

```text
mcp=False
fastmcp=False
modelcontextprotocol=False
```

Because of that, the accepted smoke path is an equivalent local tool-layer invocation using `LabSidecarMCPTools`. The optional stdio server entrypoint `py -3 -m lab_sidecar.mcp.server` is present and will require the optional `mcp` package at runtime.

Public alpha readiness on 2026-06-05 added `.[mcp]`, pinned `mcp==1.27.2`, and completed a real stdio MCP client/server smoke. The real smoke uses `run_experiment(background=True)` so command execution returns a `task_id`, then polls `inspect_results` before invoking the remaining tools. This verifies stdio transport and the tool contract without changing the MCP layer into a runner implementation.

## Implemented Tools

- `run_experiment`
- `inspect_results`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

## Design Boundaries

- Tools call existing services directly:
  - `RunnerService`
  - `MetricsCollectionService`
  - `FigureGenerationService`
  - `ReportGenerationService`
  - `SlidesGenerationService`
- Tools do not shell out to the Typer CLI.
- Tools do not return complete stdout or stderr by default.
- Tools do not return complete metrics rows, report Markdown, artifact bodies, or PPT content by default.
- `run_experiment` is the only command-execution tool and has a conservative safety gate.
- The safety gate applies to MCP-facing `run_experiment`; the CLI `run` command remains a user-explicit local command execution path.
- Workspace paths are resolved under the configured workspace; workspace-external cwd is blocked.
- `.lab-sidecar` is not allowed as run cwd.
- Destructive command patterns are blocked.
- Shell chaining and similar higher-risk patterns require confirmation.
- Workspace-external absolute paths in sensitive command arguments such as `--output` are blocked.

## Files Changed

- `lab_sidecar/mcp/__init__.py`
- `lab_sidecar/mcp/safety.py`
- `lab_sidecar/mcp/responses.py`
- `lab_sidecar/mcp/tools.py`
- `lab_sidecar/mcp/server.py`
- `pyproject.toml`
- `scripts/mcp_stdio_smoke.py`
- `tests/test_mcp_tools.py`
- `README.md`
- `docs/mcp-host-config.md`
- `PRODUCT_ITERATION_PLAN.md`
- `docs/phase-5-mcp-sidecar-acceptance.md`

## Commands

```powershell
py -3 -m pytest tests/test_mcp_tools.py
py -3 -m pytest
```

Results:

- `tests/test_mcp_tools.py`: 7 passed.
- Full suite: 64 passed.

Public alpha readiness MCP SDK install:

```powershell
py -3 -m pip install -e .[mcp]
```

Result:

- Installed editable `lab-sidecar==0.1.0`.
- Installed pinned `mcp==1.27.2`.
- Pulled MCP SDK dependencies including `anyio==4.13.0`, `httpx==0.28.1`, `starlette==1.2.1`, and `uvicorn==0.49.0`.

Real stdio MCP client smoke:

```powershell
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-mcp-stdio-smoke"
```

Result:

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

The smoke also verified the omitted response contract:

```json
{
  "full_stdout": "omitted_by_default",
  "full_stderr": "omitted_by_default",
  "metrics_rows": "omitted_by_default",
  "artifact_bodies": "omitted_by_default"
}
```

MCP SDK detection:

```powershell
@'
import importlib.util
for name in ['mcp','fastmcp','modelcontextprotocol']:
    print(f'{name}={bool(importlib.util.find_spec(name))}')
'@ | py -3 -
```

Result:

```text
mcp=False
fastmcp=False
modelcontextprotocol=False
```

Equivalent local MCP smoke workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase5-smoke
```

Smoke results:

- success task_id: `task_20260604_192140_1475df`
- success status: `completed`
- inspect metrics rows: 5
- generated figures: 2
- report path: `.lab-sidecar/tasks/task_20260604_192140_1475df/reports/report-fragment.md`
- generated slides: 7
- slide QA checks: `slide_count`, `empty_slide_check`, `title_check`, `artifact_duplicate_check`, `table_overflow_guard`, and `caption_overflow_guard` all passed.
- destructive command smoke: `Remove-Item -Recurse .` returned `blocked`.
- failure task_id: `task_20260604_192144_bbf432`
- failure status: `failed`
- failure summary included `FileNotFoundError`.
- omitted contract included:

```json
{
  "artifact_bodies": "omitted_by_default",
  "full_stderr": "omitted_by_default",
  "full_stdout": "omitted_by_default",
  "metrics_rows": "omitted_by_default"
}
```

## Acceptance Checks

- `run_experiment` returns `task_id`.
- Background long-task test returns `running` without log body.
- `inspect_results` returns summary and artifact list, not full stdout/stderr by default.
- `make_figures` reuses collected metrics and existing figure service.
- `generate_report_fragment` reuses existing report service and omits full Markdown unless bounded preview is requested.
- `generate_slides` reuses existing slides service and returns slide count plus QA summary.
- Real stdio MCP client can list and call all 5 tools.
- Real stdio smoke returns `task_id` from `run_experiment(background=True)` and completes through `inspect_results`.
- Failed task returns failure summary and artifact paths without full stderr.
- Destructive command patterns are blocked.
- Shell chaining requires confirmation.
- Workspace-external cwd is blocked.
- Workspace-external absolute output/path arguments are blocked.
- Full pytest passes.

## Blocking

- None for the Phase 5 minimal MCP-facing adapter.

## Follow-Up

- Consider `cancel_experiment` in Phase 5.1.
- Add policy configuration for allowed command prefixes and confirmation behavior.
- Add lightweight audit records for blocked or confirmed command attempts.
- Add host-specific screenshots or final JSON snippets only after testing each host, not just the generic stdio shape.

## Out Of Scope

- Web UI, FastAPI, remote runner, multi-user permissions, AI automatic analysis.
- Returning complete logs, complete CSV rows, complete Markdown, or PPT contents through MCP responses.
- Animation or media artifact generation.
- Replacing existing CLI/core services.

## Phase Judgment

Phase 5 minimal MCP-facing integration passes with blocking 0. The adapter provides the planned tool contract, verifies context-isolation behavior locally, and has a real stdio MCP client/server smoke with pinned `mcp==1.27.2`. The stdio smoke validates tool transport and bounded responses; it does not broaden Lab-Sidecar into a remote runner or hosted service.
