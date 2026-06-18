# MCP Host Configuration

Lab-Sidecar's MCP entrypoint is experimental and local-first. It is meant for AI-agent and research workflows that need a thin adapter over task-local artifacts; it exposes the same thin adapter tested by `LabSidecarMCPTools` and does not add remote execution, a Web UI, FastAPI, or AI analysis.

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

The same smoke also lists and exercises the V2 bounded delegation mirror:

- `delegate_experiment_artifacts`
- `inspect_sidecar_task`
- `preview_sidecar_artifact`
- `cancel_sidecar_task`

Tool responses return bounded summaries and artifact paths by default. They do
not return complete command strings, stdout, stderr, metrics rows, report
Markdown, worker prompt/response bodies, artifact bodies, or PPT contents. Use
`preview_sidecar_artifact` for bounded CSV, Markdown, log, image, and PPTX
previews. Preview requests must reference registered task artifacts; external,
unregistered, raw, unsupported, and worker-audit paths are rejected with bounded
responses.

Example preview and cancellation calls through an MCP host:

```json
{"tool": "preview_sidecar_artifact", "arguments": {"task_id": "task_...", "artifact_path": "metrics/normalized_metrics.csv", "max_rows": 1}}
{"tool": "preview_sidecar_artifact", "arguments": {"task_id": "task_...", "artifact_path": "reports/report-fragment.md", "max_lines": 5}}
{"tool": "cancel_sidecar_task", "arguments": {"task_id": "task_..."}}
```

Use `package <task_id>` from the CLI when the goal is a shareable task folder,
not a host response. Use explicit `collect --config` for nested or messy result
directories; the MCP adapter should not be treated as broad recursive file
discovery.

If the repo-scoped Codex plugin guidance changes, validate the plugin scaffold:

```bash
python /Users/anyuchen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
```

For V2 Codex-plugin-like host setup, smoke guidance, safety boundaries, and MCP
mirroring details, see `docs/v2-host-integration.md`.
