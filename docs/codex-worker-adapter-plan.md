# Codex Worker Adapter Plan

Date: 2026-06-08

## Purpose

This document defines the cautious path for adding a Codex-worker adapter to
Lab-Sidecar without turning the product into a generic multi-agent framework.

Codex supervisor agents and subagents are host execution coordination. A
supervisor may spawn subagents to audit, test, summarize, or implement bounded
repository slices. Lab-Sidecar's product boundary is narrower: it exposes local
tools, task records, bounded previews, worker request/result files, and
deterministically validated artifacts.

## Current Implementation

Current V2 worker execution uses:

- `WorkerRequest`
- `WorkerResult`
- `SidecarWorker`
- `WorkerInvocation`

The implemented workers are heuristic and provider-backed proposal producers.
They write task-local records under:

```text
.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/
```

Official artifacts are created only after deterministic validation and adoption
through existing V1 services.

## Minimal Future Adapter

A future Codex adapter should implement `SidecarWorker` and preserve this I/O
boundary:

- input: `WorkerRequest`, `input-bundle.json`, and `sandbox_path`
- writable area: only `sandbox_path`
- output: `WorkerResult`
- persistent records: `worker-request.json`, `worker-result.json`, diagnostics,
  and any sandbox outputs
- trust boundary: deterministic validator and adoption service

It must not require the main Codex conversation to ingest full logs, complete
datasets, report bodies, PPT contents, worker prompts, or worker transcripts.

## Non-Goals

The adapter must not claim:

- OS sandboxing, container isolation, malware detection, or shell interception
- arbitrary host subagent control from inside Lab-Sidecar
- a general agent-to-agent protocol
- remote runner or hosted service behavior
- default cloud upload of complete logs, datasets, reports, or PPTX contents

## Acceptance Criteria

Before this adapter is considered implemented:

- A fake or local test adapter can produce a `WorkerResult` through the same
  `WorkerInvocation` path.
- The main tool response still returns only bounded summaries and omitted
  records.
- Worker prompt/response or child-agent transcript bodies are never returned by
  default.
- Any proposed metrics or figure change is rejected unless the deterministic
  validator approves it.
- Cancellation, failure, and unavailable-worker behavior are recorded in
  task-local diagnostics.

Until those criteria are met, Codex subagents should be described only as a
supervisor execution pattern outside Lab-Sidecar product architecture.
