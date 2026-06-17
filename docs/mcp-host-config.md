# MCP Host Configuration

Lab-Sidecar's MCP entrypoint is experimental and local-first. It exposes the same thin adapter tested by `LabSidecarMCPTools`; it does not add remote execution, a Web UI, FastAPI, or AI analysis.

Install the optional SDK dependency before starting the stdio server:

```bash
python -m pip install -e ".[mcp]"
```

Run the server from the workspace that Lab-Sidecar should manage:

```bash
python -m lab_sidecar.mcp.server
```

Generic stdio host configuration shape:

```json
{
  "mcpServers": {
    "lab-sidecar": {
      "command": "python",
      "args": ["-m", "lab_sidecar.mcp.server"],
      "cwd": "/absolute/path/to/workspace"
    }
  }
}
```

The `cwd` is the configured workspace root. MCP-facing `run_experiment` blocks workspace-external working directories, blocks destructive command patterns, and requires confirmation for higher-risk shell patterns. The CLI `run` command is separate: it is a user-explicit local command execution path and does not use the MCP confirmation/blocking policy.

Run the real stdio client smoke after installing `.[mcp]`:

```bash
python scripts/mcp_stdio_smoke.py --workspace "${TMPDIR:-/tmp}/lab-sidecar-mcp-stdio-smoke"
```

The smoke checks that a real MCP client can list and call the deterministic V1
tools:

- `run_experiment`
- `inspect_results`
- `cancel_experiment`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

The stdio server also exposes the V2 bounded delegation mirror:

- `delegate_experiment_artifacts`
- `inspect_sidecar_task`
- `preview_sidecar_artifact`
- `cancel_sidecar_task`

Tool responses return bounded summaries and artifact paths by default. They do
not return complete command strings, stdout, stderr, metrics rows, report
Markdown, worker prompt/response bodies, artifact bodies, or PPT contents. Use
`preview_sidecar_artifact` for bounded CSV, Markdown, log, image, and PPTX
previews.

For V2 Codex-plugin-like host setup, smoke guidance, safety boundaries, and MCP
mirroring details, see `docs/v2-host-integration.md`.
