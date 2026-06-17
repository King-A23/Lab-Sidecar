# Public Alpha Release Notes

Date: 2026-06-08

## Summary

Lab-Sidecar public alpha is a local-first, CLI-first experiment sidecar. It can run or ingest local experiment results, collect CSV/JSON metrics, generate static figures, write deterministic Markdown report fragments, and create editable static PPTX drafts.

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

## Safety Model

CLI `run` is a user-explicit local command execution path. It captures logs and artifacts, but it does not apply the MCP confirmation/blocking policy.

MCP-facing `run_experiment` and
`delegate_experiment_artifacts(command=...)` apply a conservative workspace and
command safety gate:

- workspace-external cwd is blocked
- `.lab-sidecar` cwd is blocked
- destructive command patterns are blocked
- shell chaining and similar higher-risk patterns require confirmation
- workspace-external absolute output/path arguments are blocked

Lab-Sidecar does not claim OS sandboxing, malware detection, container isolation, multi-user policy, or global shell interception.

## MCP Notes

Install optional MCP support:

```bash
python -m pip install -e ".[mcp]"
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
