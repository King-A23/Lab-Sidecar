# V2 Host Integration

Lab-Sidecar V2 host integration is local-first and Codex-plugin-like first.
It is aimed at AI agents that need to delegate local experiment scenarios while
keeping logs, full metric rows, worker audit files, and generated artifact
bodies out of the main context. The host contract is a small set of
Python-callable tools that a Codex agent can delegate to while keeping large
task details in `.lab-sidecar/tasks/`.

This document covers host setup, smoke checks, common failures, safety
boundaries, and the thin MCP mirror for the V2 host tools.

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
- bounded `summary.outputs.scenario` when `metrics/scenario-summary.json` exists
- artifact metadata and paths
- `next_actions`
- `risk_flags`
- `omitted`

The host should not expect complete command strings, full stdout, stderr,
datasets, report bodies, PPTX contents, prompt or response transcripts, or
artifact bodies in default tool responses.

Human experiment owners remain responsible for interpreting, redacting,
accepting, and making final decisions from the local artifacts. V2 responses are
bounded descriptive evidence for a host agent, not autonomous experiment
judgments.

Canonical response shape:

```json
{
  "schema_version": "2.1",
  "task_id": "task_...",
  "status": "completed",
  "summary": {"headline": "...", "task": {}, "outputs": {"scenario": {"present": true}}},
  "artifacts": [{"artifact_id": "metrics_normalized_csv", "path": "metrics/normalized_metrics.csv"}],
  "warnings": [],
  "next_actions": ["inspect_sidecar_task task_..."],
  "risk_flags": [],
  "omitted": {
    "full_stdout": "omitted_by_default",
    "metrics_rows": "omitted_by_default",
    "worker_prompt_response": "omitted_by_default",
    "artifact_bodies": "omitted_by_default"
  }
}
```

`summary.outputs.scenario` is descriptive. It may include the scenario type,
primary metric, bounded best/last row references, seed aggregates, evidence
paths, and omission notes. It must not include complete metric rows, full logs,
report bodies, PPTX contents, worker prompts/responses, or statistical
significance claims.

## Stage 4 Preview Contract

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
- raw source references and worker prompt or response content

Copyable examples:

```python
preview_sidecar_artifact(".", task_id, "metrics/normalized_metrics.csv", max_rows=1)
preview_sidecar_artifact(".", task_id, "reports/report-fragment.md", max_lines=5)
preview_sidecar_artifact(".", task_id, "stdout.log", max_lines=20)
preview_sidecar_artifact(".", task_id, "figures/val_accuracy.png")
preview_sidecar_artifact(".", task_id, "slides/presentation-draft.pptx")
```

CSV, Markdown, and log previews may return fewer rows or lines than requested
to avoid returning a complete artifact body. Image previews return metadata,
not bytes. PPTX previews return slide count and title metadata, not slide XML
or embedded media. Requests for workspace-external paths, unregistered files,
`raw/source_refs.json`, or `intelligence/**` worker audit files should return a
bounded rejection.

Host smoke should verify delegate, inspect, preview, and cancel without
simulating previews through plain file reads.

## When To Delegate

Delegate to Lab-Sidecar when the main host would otherwise need to run a local
experiment, ingest CSV/JSON results, collect metrics, generate figures, draft a
report or slide deck, package a task, or monitor/cancel a long local task while
keeping noisy logs and rows out of the main context.

Do not delegate ordinary source-code edits, unit-test runs whose main value is
repository feedback, arbitrary file browsing, full artifact dumps, destructive
or untrusted shell work, remote execution, hosted services, cloud sync, generic
multi-agent orchestration, or requests that require complete logs/rows/report
bodies in the host response.

For nested or messy result directories, use explicit `collect --config`
semantics rather than broad automatic discovery. Stage 3 configs can declare
`sources.include`, `sources.exclude`, field alias lists, units, and groups.
For handoff, use `package <task_id>`; package exports are allowlisted and omit
full logs, raw source refs, worker prompt/response bodies, sandbox files, and
unrelated workspace files by default.

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
- raw and worker audit paths are rejected
- completed or missing task cancellation returns a bounded not-cancelled
  response

## Codex MCP Configuration

MCP host configuration is documented in `docs/mcp-host-config.md`. A generic
stdio host shape is:

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

Run the MCP stdio smoke:

```bash
python scripts/mcp_stdio_smoke.py --workspace "${TMPDIR:-/tmp}/lab-sidecar-v2-host-mcp"
```

This smoke lists and exercises the deterministic V1 tools:

- `run_experiment`
- `inspect_results`
- `cancel_experiment`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

The smoke also lists and exercises the V2 mirror tools for delegate, inspect,
preview, and cancellation:

- `delegate_experiment_artifacts`
- `inspect_sidecar_task`
- `cancel_sidecar_task`
- `preview_sidecar_artifact`

## MCP Mirroring Decision

The V2 tools are now mirrored to MCP as a thin adapter over the same local
functions:

- `LabSidecarMCPTools.delegate_experiment_artifacts`
- `LabSidecarMCPTools.inspect_sidecar_task`
- `LabSidecarMCPTools.cancel_sidecar_task`
- `LabSidecarMCPTools.preview_sidecar_artifact`

Mirroring constraints:

- MCP remains an adapter, not a separate product surface.
- Command delegation still passes through the MCP command safety gate.
- `result_path` must stay inside the configured workspace and outside
  `.lab-sidecar`.
- Default responses preserve the V2 omitted-content contract.
- Preview remains bounded and task-artifact scoped.

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
- Fix: use `preview_sidecar_artifact`; do not replace it with generic file
  reads.

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
- MCP remains a thin adapter over the same local contracts
- CLI remains a separate user-explicit local execution path

MCP/V2 and other agent-triggered command paths are higher risk than manual CLI
use. Route them through bounded delegation, the configured workspace boundary,
the conservative command safety gate, and explicit host command policy or
confirmation. These are guardrails only; they are not OS isolation, a container
runtime, a malware detector, or proof that delegated shell work is safe.

Do not treat Lab-Sidecar V2 as a general file browser, shell proxy, data export
service, prompt transcript reader, PPTX unpacking API, or generic multi-agent
framework.

## Suggested Phase 2.4 Acceptance Record Points

The Phase 2.4 acceptance document should record:

- exact local plugin-like smoke command and output summary
- whether `preview_sidecar_artifact` exists and which preview types passed
- external path and unsupported artifact rejection evidence
- evidence that default responses omit artifact bodies and large logs
- exact MCP stdio smoke command and output summary for V1 tools
- targeted test evidence that V2 MCP mirror tools preserve bounded responses
- final `git status --short`, including any pre-existing unrelated changes
