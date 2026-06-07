# V2 Phase 2.5 Worker Invocation Protocol Plan

Date: 2026-06-06

## Purpose

Phase 2.5 turns the current V2 worker flow into a stable, subagent-like
invocation protocol.

The goal is to make Lab-Sidecar feel like the Codex main agent is delegating to
a child worker:

```text
main agent intent
  -> delegate_experiment_artifacts
  -> worker request
  -> bounded input bundle
  -> isolated worker run
  -> proposal result
  -> deterministic validator
  -> official V1 adoption
  -> minimal response
```

This is a product protocol, not a dependency on Codex host subagent internals.
Lab-Sidecar must remain local-first, file-first, deterministic at the trust
boundary, and usable without an AI provider.

## Phase Goal

Extract a decision-complete worker invocation layer from the current
`delegate_experiment_artifacts` implementation so heuristic workers, fake AI
providers, future real providers, and future Codex-host adapters all use the
same request/result lifecycle.

After this phase, callers should not need to know whether a proposal came from
heuristics, a fake provider, or a future provider adapter. They should only see
the worker run metadata, validation result, adopted official artifacts, bounded
summary, risk flags, next actions, and omitted-content contract.

## Implementation Targets

- Add a worker invocation protocol under `lab_sidecar/intelligence/` with
  structured request and result models:
  - `WorkerRequest`
  - `WorkerResult`
  - `WorkerInvocation`
  - `SidecarWorker` protocol
- Keep `delegate_experiment_artifacts` as the public local tool entrypoint.
  It should build a `WorkerRequest`, invoke one configured worker through the
  protocol, validate the returned proposal, and adopt only accepted proposals.
- Preserve task-local worker run directories:

```text
.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/
  input-bundle.json
  worker-request.json
  worker-result.json
  validator-result.json
  diagnostics.md
  sandbox/
```

- Treat all workers as proposal producers only. No worker may directly write to
  official artifact directories or mutate `manifest.json`.
- Make the heuristic worker implement `SidecarWorker` instead of being called
  through ad hoc helper flow.
- Wrap fake AI provider behavior behind the same protocol. The fake provider
  may still be used for deterministic tests, but its output must become a
  `WorkerResult` before validation and adoption.
- Add a worker selection function with this default precedence:
  - `intelligent_mode="off"`: skip worker and use V1 deterministic fallback.
  - explicit `ai_provider` argument: invoke provider-backed worker if policy
    allows it.
  - configured fake provider: invoke fake provider worker.
  - otherwise: invoke heuristic worker.
  - unavailable worker/provider: return a bounded fallback result with clear
    risk flags.
- Record the selected worker type and worker status in task-local audit files
  and in the minimal tool response.
- Keep default responses quarantined. They must not include full logs, full
  datasets, prompt/response bodies, worker transcripts, report bodies, PPT
  content, or artifact bodies.
- Do not add MCP mirroring, real provider implementation, Codex plugin
  marketplace packaging, Web UI, FastAPI, hosted execution, remote runner, or a
  generic multi-agent framework in this phase.

## Suggested Interfaces

`WorkerRequest` should include:

- `schema_version`
- `task_id`
- `worker_run_id`
- `worker_type`
- `user_goal`
- `desired_outputs`
- `input_bundle_path`
- `sandbox_path`
- bounded `context_budget`
- policy summary safe to persist locally

`WorkerResult` should include:

- `schema_version`
- `task_id`
- `worker_run_id`
- `worker_type`
- `status`: `accepted`, `rejected`, `unavailable`, or `skipped`
- `proposal`
- `proposal_path`
- `summary`
- `diagnostics`
- `risk_flags`
- `omitted`

`SidecarWorker` should expose one method:

```python
def run(self, request: WorkerRequest) -> WorkerResult:
    ...
```

The protocol must stay synchronous in this phase. Background or async worker
execution can be a later extension behind the same request/result files.

## Required Tests

- `delegate_experiment_artifacts` creates `worker-request.json` and
  `worker-result.json` for a normal heuristic run.
- A heuristic worker run goes through the new protocol and still produces
  official metrics, figures, report, or slides only after validator approval.
- A fake AI provider run goes through the same protocol and still respects
  budget, redaction, audit retention, and fallback behavior.
- `intelligent_mode="off"` skips the worker protocol and still returns the V1
  deterministic fallback summary.
- An unavailable provider or worker returns `risk_flags` without crashing and
  does not prevent deterministic fallback.
- Rejected proposals are recorded in `worker-result.json` and
  `validator-result.json`, but official artifacts are not generated from them.
- Default responses omit full logs, full datasets, prompt/response bodies,
  worker transcripts, report bodies, PPT content, and artifact bodies.
- Existing V1 CLI tests, existing MCP tests, V2 provider tests, V2 heuristic
  tests, and V2 host integration tests still pass.

## Acceptance Commands

```bash
py -3 -m pytest tests/test_v2_worker_invocation.py
py -3 -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py
py -3 -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py
py -3 scripts/mcp_stdio_smoke.py --workspace "$TMPDIR/lab-sidecar-v2-phase-2-5-mcp"
py -3 -m pytest
git status --short
```

If the current platform does not provide `py` or `$TMPDIR`, use the active
Python 3.11+ interpreter and a platform-appropriate temporary workspace, then
record the exact commands in the acceptance document.

## Acceptance Record

Finish this phase by writing:

```text
docs/v2-phase-2-5-worker-invocation-protocol-acceptance.md
```

The acceptance record must include:

- phase goal
- starting state
- changed files
- commands
- workspaces and IDs
- generated worker request/result files
- generated official artifacts
- test results
- blocking items
- follow-ups
- out-of-scope items
- final judgment

## Blocking Criteria

- Worker implementations can bypass the protocol and directly write official
  artifacts.
- Official artifacts can be created from an unvalidated proposal.
- A provider-backed worker can receive full logs, full datasets, user source
  code, or unredacted secrets outside explicit bounded policy.
- Default responses include worker transcripts, prompt/response bodies, full
  logs, full datasets, report bodies, PPT content, or artifact bodies.
- The protocol depends on Codex host subagent internals or requires AI for
  normal workflows.
- Existing V1 CLI or MCP tests regress.

## Follow-Up

- Add real provider adapters only after this invocation protocol is stable and
  the real-provider smoke policy is explicitly approved.
- Add a thin MCP mirror for V2 local tools only after real host usage confirms
  the local V2 contract.
- Consider async/background worker invocation later, behind the same
  request/result files.
- Consider a Codex-host subagent adapter later as one implementation of
  `SidecarWorker`, not as the core product architecture.

## Final Judgment

Phase 2.5 should be accepted only when the worker invocation protocol is the
single path for heuristic and fake-provider proposals, all proposal adoption
still passes through deterministic validation, default context quarantine
remains intact, and existing V1/V2 smoke coverage still passes.
