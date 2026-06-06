# MCP Host Configuration

Lab-Sidecar's MCP entrypoint is experimental and local-first. It exposes the same thin adapter tested by `LabSidecarMCPTools`; it does not add remote execution, a Web UI, FastAPI, or AI analysis.

Install the optional SDK dependency before starting the stdio server:

```powershell
py -3 -m pip install -e .[mcp]
```

Run the server from the workspace that Lab-Sidecar should manage:

```powershell
py -3 -m lab_sidecar.mcp.server
```

Generic stdio host configuration shape:

```json
{
  "mcpServers": {
    "lab-sidecar": {
      "command": "py",
      "args": ["-3", "-m", "lab_sidecar.mcp.server"],
      "cwd": "C:\\code\\Lab-Sidecar"
    }
  }
}
```

The `cwd` is the configured workspace root. MCP-facing `run_experiment` blocks workspace-external working directories, blocks destructive command patterns, and requires confirmation for higher-risk shell patterns. The CLI `run` command is separate: it is a user-explicit local command execution path and does not use the MCP confirmation/blocking policy.

Run the real stdio client smoke after installing `.[mcp]`:

```powershell
py -3 scripts/mcp_stdio_smoke.py --workspace "$env:TEMP\\lab-sidecar-mcp-stdio-smoke"
```

The smoke checks that a real MCP client can list and call these tools:

- `run_experiment`
- `inspect_results`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

Tool responses return bounded summaries and artifact paths by default. They do not return complete stdout, stderr, metrics rows, report Markdown, artifact bodies, or PPT contents.

For V2 Codex-plugin-like host setup, smoke guidance, safety boundaries, and the
current decision to defer MCP mirroring of V2 tools, see
`docs/v2-host-integration.md`. The stdio smoke above remains the regression
guard for the existing V1 MCP tool surface.
