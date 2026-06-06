# V2 Host Integration

Lab-Sidecar V2 host integration is local-first and Codex-plugin-like first.
The host contract is a small set of Python-callable tools that a Codex agent
can delegate to while keeping large task details in `.lab-sidecar/tasks/`.

This document covers host setup, smoke checks, common failures, safety
boundaries, and the current MCP mirroring decision for Phase 2.4.

## Supported Host Shape

The primary V2 host path is local plugin-like use from the same workspace:

```python
from lab_sidecar.intelligence import (
    cancel_sidecar_task,
    delegate_experiment_artifacts,
    inspect_sidecar_task,
    preview_sidecar_artifact,
)

result = delegate_experiment_artifacts(
    workspace_path=".",
    user_goal="Generate metrics, figures, report, and slides.",
    result_path="examples/csv-comparison",
    desired_outputs=["metrics", "figures", "report", "slides"],
    intelligent_mode="off",
)
task_id = result["task_id"]
status = inspect_sidecar_task(".", task_id)
preview = preview_sidecar_artifact(".", task_id, status["artifacts"][0]["path"])
```

The host should treat these functions as tool contracts, not as a general
library API for reading arbitrary files. Default responses should stay small:

- `task_id`
- `status`
- bounded `summary`
- artifact metadata and paths
- `next_actions`
- `risk_flags`
- `omitted`

The host should not expect full stdout, stderr, datasets, report bodies, PPTX
contents, prompt or response transcripts, or artifact bodies in default tool
responses.

## Phase 2.4 Preview Contract

`preview_sidecar_artifact` is the V2 path for asking for more
artifact detail. It must be a bounded preview tool, not a generic file reader.

Supported preview shapes:

- first N CSV rows
- first N Markdown lines
- image dimensions and metadata
- PPTX slide count and summary metadata
- bounded stdout, stderr, or log tail

Required rejection or omission cases:

- paths outside the task artifact boundary
- unsupported artifact types
- complete artifact bodies
- unbounded row, line, byte, or slide reads
- raw worker prompt or response content

Host smoke should verify delegate, inspect, preview, and cancel without
simulating previews through plain file reads.

## Local Plugin-Like Smoke

Install the package in editable mode from the repository root:

```bash
python -m pip install -e .
```

Run the current local host smoke with deterministic behavior:

```bash
python - <<'PY'
from pathlib import Path
from lab_sidecar.intelligence import (
    cancel_sidecar_task,
    delegate_experiment_artifacts,
    inspect_sidecar_task,
    preview_sidecar_artifact,
)

workspace = Path(".").resolve()
result = delegate_experiment_artifacts(
    workspace_path=workspace,
    user_goal="Smoke local V2 host delegation.",
    result_path="examples/csv-comparison",
    desired_outputs=["metrics", "figures", "report", "slides"],
    intelligent_mode="off",
)
print("delegate:", result["task_id"], result["status"])
print("omitted:", sorted(result.get("omitted", {}).keys()))
print("artifacts:", len(result.get("artifacts", [])))

inspected = inspect_sidecar_task(workspace, result["task_id"])
print("inspect:", inspected["task_id"], inspected["status"])
if inspected["artifacts"]:
    preview = preview_sidecar_artifact(workspace, result["task_id"], inspected["artifacts"][0]["path"])
    print("preview:", preview.get("preview_type") or preview.get("status"))

cancelled = cancel_sidecar_task(workspace, result["task_id"])
print("cancel:", cancelled["status"])
PY
```

Expected outcome:

- delegation returns a `task_id`
- default response contains summaries and artifact metadata, not artifact bodies
- inspect returns the same task id and bounded task state
- preview returns a bounded type-specific response or a bounded rejection for
  unsupported artifacts
- cancel returns a bounded response; completed tasks may report that
  cancellation is not applicable

Targeted tests cover:

- CSV preview returns at most the requested row limit
- Markdown preview returns at most the requested line limit
- image preview returns metadata rather than bytes
- PPTX preview returns slide count and summary metadata rather than slide XML
- log preview returns only the requested tail
- external paths and unsupported artifact types are rejected

## Codex MCP Configuration

Existing MCP host configuration remains V1-oriented and is documented in
`docs/mcp-host-config.md`. A generic stdio host shape is:

```json
{
  "mcpServers": {
    "lab-sidecar": {
      "command": "python",
      "args": ["-m", "lab_sidecar.mcp.server"],
      "cwd": "/absolute/path/to/Lab-Sidecar"
    }
  }
}
```

Install the optional MCP dependency before launching a stdio host:

```bash
python -m pip install -e ".[mcp]"
python -m lab_sidecar.mcp.server
```

Run the current V1 MCP stdio smoke:

```bash
python scripts/mcp_stdio_smoke.py --workspace "${TMPDIR:-/tmp}/lab-sidecar-v2-host-mcp"
```

This smoke should continue to list and call the existing MCP tools:

- `run_experiment`
- `inspect_results`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

For Phase 2.4, this smoke is a regression guard for existing MCP behavior. It
is not evidence that V2 tool contracts have been mirrored to MCP.

## MCP Mirroring Decision

Do not mirror the V2 tools to MCP yet.

Deferral rationale:

- Phase 2.4 stabilizes the local plugin-like contracts first, including
  bounded preview.
- Mirroring in the same phase would expand the MCP adapter before the local V2
  contract has had separate host use.
- The existing MCP server is a V1 thin adapter. Adding V2 behavior before the
  contracts settle risks turning MCP into a parallel product surface instead of
  a mirror.
- No confirmed Codex plugin registration details are required for the local
  plugin-like path, so Codex workflow hardening can proceed without MCP changes.

Revisit MCP mirroring when:

- `delegate_experiment_artifacts`, `inspect_sidecar_task`,
  `cancel_sidecar_task`, and `preview_sidecar_artifact` all have stable bounded
  response contracts.
- Preview rejection rules are covered by tests.
- A stdio adapter can call the same local functions without changing behavior,
  broadening file access, or returning larger default payloads.

## Common Failure Modes

Missing optional MCP SDK:

- Symptom: `python -m lab_sidecar.mcp.server` fails to import MCP packages.
- Fix: run `python -m pip install -e ".[mcp]"`.

Wrong host working directory:

- Symptom: host cannot find examples, task manifests, or `.lab-sidecar`.
- Fix: set MCP `cwd` or local smoke workspace to the intended repository or
  project root.

Workspace-external paths:

- Symptom: MCP command execution or future preview requests are rejected.
- Fix: use paths inside the configured workspace and task artifact boundary.

Oversized or missing previews:

- Symptom: default host response omits logs, rows, report text, or PPTX
  internals.
- Fix: use `preview_sidecar_artifact` after Phase 2.4 implements it; do not
  replace it with generic file reads.

AI provider unavailable:

- Symptom: intelligent mode cannot use an AI provider.
- Expected behavior: fall back to deterministic or heuristic behavior and
  return a risk flag such as `ai_provider_unavailable`.

Worker unavailable or validator rejection:

- Symptom: no intelligent proposal is adopted.
- Expected behavior: preserve diagnostics in task-local files, return bounded
  summaries and next actions, and avoid generating official artifacts from a
  rejected proposal.

Command or sandbox failure:

- Symptom: delegated command exits non-zero or is blocked by host policy.
- Expected behavior: record command, exit code, bounded logs, and diagnostics;
  keep default host responses small.

## Safety Boundaries

Host integrations must preserve these boundaries:

- local filesystem only; no hosted service, Web UI, FastAPI, or remote runner
- configured workspace root is the execution and artifact boundary
- task-local files are the audit source of truth
- default tool responses are summaries, metadata, next actions, risk flags, and
  omission records
- preview is bounded and type-specific
- MCP, if mirrored later, remains a thin adapter over the same local contracts
- CLI remains a separate user-explicit local execution path

Do not treat Lab-Sidecar V2 as a general file browser, shell proxy, data export
service, prompt transcript reader, or PPTX unpacking API.

## Suggested Phase 2.4 Acceptance Record Points

The Phase 2.4 acceptance document should record:

- exact local plugin-like smoke command and output summary
- whether `preview_sidecar_artifact` exists and which preview types passed
- external path and unsupported artifact rejection evidence
- evidence that default responses omit artifact bodies and large logs
- exact MCP stdio smoke command and output summary for existing V1 tools
- explicit note that V2 MCP mirroring was deferred, with the rationale above
- final `git status --short`, including any pre-existing unrelated changes
