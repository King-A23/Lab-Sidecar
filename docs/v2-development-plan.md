# Lab-Sidecar V2 Development Plan

Date: 2026-06-06

## Purpose

This document is the executable development plan for implementing the V2 rollout in
`docs/v2-intelligent-sidecar-design.md`.

V2 keeps the V1 local artifact pipeline:

```text
run / ingest -> collect -> figures -> report -> slides -> artifacts
```

and adds a Codex-plugin-first planning layer:

```text
Codex main agent
  -> Lab-Sidecar plugin-like tool
  -> task-local intelligence workspace
  -> worker proposal
  -> deterministic validator
  -> V1 core services write trusted artifacts
  -> minimal context returns to Codex
```

The plan is split into phases 2.1 through 2.5. Each phase is designed to be run
as an independent goal-mode task with a small blast radius, explicit acceptance
evidence, and a written phase record.

## Execution Rules

- Keep Lab-Sidecar local-first, file-first, and Codex-plugin-first.
- Do not add Web UI, FastAPI, remote runners, hosted services, animation/video
  workflows, or a generic multi-agent framework.
- Goal-mode managers and subagents are execution coordination only. They are not
  product architecture.
- Preserve all user or other-agent changes. Start every phase by running:

```bash
git status --short
```

- Before editing, read the current diff and the relevant source documents:

```bash
git diff --stat
git diff
sed -n '1,220p' docs/v2-intelligent-sidecar-design.md
sed -n '220,720p' docs/v2-intelligent-sidecar-design.md
```

- End every phase with targeted tests, the full test suite, a clean status
  check, and a written acceptance record:

```bash
py -3 -m pytest <targeted-tests>
py -3 -m pytest
git status --short
```

- If `py` is unavailable on the current platform, use the active Python 3.11+
  interpreter and record the exact command in the acceptance document.
- Do not mark a phase accepted until its acceptance document exists and includes
  changed files, commands, workspaces, task IDs, worker run IDs when applicable,
  generated artifacts, test results, blocking items, follow-ups, out-of-scope
  items, and final judgment.

Phase acceptance records:

```text
docs/v2-phase-2-1-non-ai-scaffold-acceptance.md
docs/v2-phase-2-2-heuristic-worker-acceptance.md
docs/v2-phase-2-3-optional-ai-provider-acceptance.md
docs/v2-phase-2-4-codex-host-hardening-acceptance.md
docs/v2-phase-2-5-worker-invocation-protocol-acceptance.md
```

Recommended acceptance record shape:

```markdown
# V2 Phase <n> Acceptance

## Phase Goal

## Starting State

## Changed Files

## Commands

## Workspaces And IDs

## Generated Artifacts

## Test Results

## Blocking

## Follow-Up

## Out Of Scope

## Final Judgment
```

## Phase 2.1: Non-AI Scaffold

Goal-mode objective:

```text
Implement V2 Phase 2.1 Non-AI Scaffold for Lab-Sidecar. Add the task-local
intelligence scaffold, sandbox creation, bounded input bundle builders, proposal
schema skeletons, validator skeleton, and plugin-like local tool functions,
without changing the trusted V1 CLI/MCP artifact pipeline. Finish by writing
docs/v2-phase-2-1-non-ai-scaffold-acceptance.md with evidence and tests.
```

### Goal

Create the V2 intelligence scaffold without making AI or worker planning a
requirement for existing workflows.

The phase must not change the behavior of V1 CLI commands, existing MCP tools,
collectors, figure generation, reports, or slides except for narrowly necessary
shared helper additions.

### Implementation Targets

- Add a `lab_sidecar/intelligence/` subsystem for input bundles, task-local
  sandbox setup, proposal schema skeletons, validator skeleton, and local
  plugin-like tool contracts.
- Create each worker run under:

```text
.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/
  input-bundle.json
  validator-result.json
  diagnostics.md
  sandbox/
```

- Treat `sandbox/` as the only worker-writable directory.
- Make the plugin-like local tool layer expose:
  - `delegate_experiment_artifacts`
  - `inspect_sidecar_task`
  - `cancel_sidecar_task`
- Support `intelligent_mode="off"` and unavailable-worker fallback to the V1
  deterministic path.
- Keep proposals non-authoritative in this phase. The validator skeleton may
  record accepted/rejected states, but proposals must not alter official
  metrics, figures, reports, slides, or manifest artifacts yet.
- Return minimal context by default: task ID, status, bounded summary, artifact
  metadata, next actions, risk flags, and omitted contract.
- Never return complete stdout/stderr, complete metric rows, report bodies, PPT
  content, worker prompts/responses, artifact bodies, or full data files by
  default.

### Required Tests

- Intelligence directory and `input-bundle.json` are created for a delegated
  task.
- `delegate_experiment_artifacts` returns a V1 fallback summary when
  `intelligent_mode="off"`.
- Worker-unavailable fallback returns a clear risk flag and still leaves V1
  deterministic workflows usable.
- Default responses omit full logs, metric rows, report body, PPT content, and
  artifact bodies.
- A sandbox escape proposal is rejected and records diagnostics without
  modifying official artifact directories.
- Existing CLI and MCP smoke tests still pass.

### Acceptance Commands

```bash
py -3 -m pytest tests/test_v2_intelligence_scaffold.py
py -3 -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py
py -3 -m pytest
git status --short
```

### Blocking Criteria

- Any V1 CLI or existing MCP test regresses.
- Any worker path can write outside `intelligence/<worker_run_id>/sandbox/`.
- Default plugin-like responses include full logs, metrics rows, report body,
  PPT content, prompt/response content, or artifact bodies.
- Proposals can affect official artifacts before deterministic validation and
  adoption are implemented.

## Phase 2.2: Heuristic Worker

Goal-mode objective:

```text
Implement V2 Phase 2.2 Heuristic Worker for Lab-Sidecar. Add a non-AI worker
that uses bounded input bundles to propose metrics mappings and figure specs,
validate those proposals, adopt only accepted proposals into existing V1 config
shapes, and preserve V1 fallback behavior. Finish by writing
docs/v2-phase-2-2-heuristic-worker-acceptance.md with evidence and tests.
```

### Goal

Implement a non-AI worker that can improve non-standard artifact handling using
bounded heuristics, while keeping deterministic validators and V1 services as
the only source of trusted official outputs.

### Implementation Targets

- Build heuristic proposals only from bounded input bundle content: source
  paths, hashes, file sizes, column names, inferred types, null counts, small
  row samples, descriptive stats, bounded log tails, and existing collection
  errors.
- Generate metrics proposals that can be converted into the existing explicit
  metrics config shape.
- Generate figure proposals that can be converted into the existing explicit
  figure spec shape.
- Validate source paths, field existence, supported chart types, output paths,
  numeric claims, artifact citations, and sandbox boundaries.
- Adopt only accepted proposals. Adoption writes an `adoption-record.json` and
  then calls V1 services to create official metrics, figures, reports, and
  slides.
- Preserve rejected proposals, validator diagnostics, and next actions. Rejected
  proposals must not be used by official artifact generation.
- Keep no-AI behavior fully functional.

### Required Tests

- A non-standard CSV can produce a heuristic metrics proposal and official
  `metrics/normalized_metrics.csv`.
- A valid figure proposal produces at least one official PNG/SVG figure and a
  figure summary.
- A proposal referencing a missing field is rejected, diagnostics name the
  missing field, and official figures are not generated from that proposal.
- Heuristic mode works without any AI provider configuration.
- Existing V1 fallback behavior remains unchanged when heuristic planning is
  disabled or rejected.

### Acceptance Commands

```bash
py -3 -m pytest tests/test_v2_heuristic_worker.py
py -3 -m pytest tests/test_v2_intelligence_scaffold.py
py -3 -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py
py -3 -m pytest
git status --short
```

### Blocking Criteria

- The heuristic worker reads full datasets or full logs by default.
- Adoption occurs without validator approval.
- Validator approval can be bypassed by malformed paths, missing fields,
  unsupported chart types, or sandbox escape attempts.
- Official artifacts contain unsupported numeric claims or claims absent from
  collected metrics and summaries.

## Phase 2.3: Optional AI Provider

Goal-mode objective:

```text
Implement V2 Phase 2.3 Optional AI Provider for Lab-Sidecar. Add an optional AI
provider abstraction, fake provider tests, bounded prompt/response audit files,
configured real-provider smoke support when a valid key is present, and fallback
behavior when AI is unavailable. Finish by writing
docs/v2-phase-2-3-optional-ai-provider-acceptance.md with evidence and tests.
```

### Goal

Add an optional AI worker provider without making AI required for any user
workflow.

User-selected policy: when workspace configuration explicitly allows AI use and
a valid provider key is present, the real provider smoke may run. If no key or
configuration is present, the system must fall back to the heuristic worker or
V1 deterministic path.

### Implementation Targets

- Add a provider abstraction with at least a fake provider for deterministic
  tests.
- Do not upload complete logs, complete datasets, or user source code by
  default.
- Require explicit workspace configuration for real provider use, even when an
  environment key exists.
- Enforce max input budget, redaction policy, cloud-upload policy, and audit
  retention policy before every provider call.
- Record prompt and response audit artifacts under the task-local
  `intelligence/<worker_run_id>/` directory when audit retention is enabled.
- Keep prompt and response content out of default plugin-like responses.
- On provider unavailable, invalid configuration, or missing key, return a
  clear fallback summary and risk flags such as
  `risk_flags=["ai_provider_unavailable"]`.
- Preserve heuristic worker and V1 deterministic fallback paths.

### Required Tests

- Fake provider success produces a proposal that still goes through validator
  and adoption rules.
- Fake provider unavailable path falls back without crashing.
- Budget truncation and redaction are applied before provider input is written
  or sent.
- Prompt/response audit artifacts are written only when policy allows.
- Default responses omit prompt and response text.
- No-key environment falls back successfully.
- Real provider smoke runs only when explicit workspace configuration and a
  valid key are present; otherwise the acceptance record states why it was
  skipped.

### Acceptance Commands

```bash
py -3 -m pytest tests/test_v2_ai_provider.py
py -3 -m pytest tests/test_v2_heuristic_worker.py
py -3 -m pytest tests/test_v2_intelligence_scaffold.py
py -3 -m pytest
git status --short
```

If explicit AI configuration and a valid key are present, also run the real
provider smoke chosen by the implementation and record the exact command and
redaction/audit evidence in the acceptance document.

### Blocking Criteria

- Any workflow becomes unusable solely because no AI provider is configured.
- A provider call can receive complete logs, complete datasets, or user source
  code without explicit bounded input configuration.
- Prompt or response bodies appear in default plugin-like responses.
- AI output can create official artifacts without deterministic validation.

## Phase 2.4: Codex Plugin / Host Integration Hardening

Goal-mode objective:

```text
Implement V2 Phase 2.4 Codex Plugin / Host Integration Hardening for
Lab-Sidecar. Stabilize the local Codex-plugin-like tool contract, add bounded
artifact preview, harden delegate/inspect/cancel responses, document host setup
and smoke paths, and mirror contracts to MCP only if doing so preserves the
Codex-first behavior. Finish by writing
docs/v2-phase-2-4-codex-host-hardening-acceptance.md with evidence and tests.
```

### Goal

Make V2 usable from Codex host workflows while keeping the local
plugin-like contract as the primary interface and MCP as an optional thin
adapter.

### Implementation Targets

- Stabilize the local plugin-like contracts before changing host adapters.
- Do not depend on unconfirmed Codex plugin registration details. Implement
  only packaging, manifest, marketplace, or MCP configuration shapes that are
  confirmed by current official Codex documentation.
- Add `preview_sidecar_artifact` as a bounded preview tool, not a generic file
  reader.
- Supported preview types:
  - first N rows of CSV
  - first N lines of Markdown
  - image dimensions and metadata
  - PPTX slide count and summary metadata
  - bounded stdout/stderr/log tail
- Reject or omit previews for external paths, unsupported artifact types,
  complete artifact bodies, and unbounded reads.
- Harden `delegate_experiment_artifacts`, `inspect_sidecar_task`,
  `cancel_sidecar_task`, and `preview_sidecar_artifact` response contracts:
  bounded summary, artifact metadata, next actions, risk flags, and omitted
  contract.
- Mirror V2 contracts to MCP only when the MCP adapter can remain thin and does
  not weaken the Codex-first behavior. If MCP mirroring is deferred, record the
  reason in the phase acceptance document.
- Write host setup and smoke documentation for local plugin-like use, Codex MCP
  configuration, and any confirmed plugin packaging path.

### Required Tests

- Host-facing smoke completes delegate -> inspect -> preview -> complete or
  cancel.
- Preview rejects external paths and unsupported artifact reads.
- Preview returns bounded CSV rows, Markdown lines, image metadata, PPTX summary
  metadata, and bounded log tails.
- Default response contracts remain small and do not include artifact bodies.
- If MCP mirrors V2 tools, a stdio smoke covers the mirrored contracts.
- If MCP mirroring is deferred, existing MCP tests and stdio smoke still pass.

### Acceptance Commands

```bash
py -3 -m pytest tests/test_v2_host_integration.py
py -3 -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_intelligence_scaffold.py
py -3 -m pytest tests/test_mcp_tools.py
py -3 scripts/mcp_stdio_smoke.py --workspace "$TMPDIR/lab-sidecar-v2-phase-2-4-mcp"
py -3 -m pytest
git status --short
```

If the current platform does not provide `$TMPDIR` or `py`, use equivalent
platform-specific paths and Python commands, then record the exact commands.

### Blocking Criteria

- `preview_sidecar_artifact` can read arbitrary workspace files.
- Host-facing responses return unbounded logs, datasets, report bodies, PPT
  content, prompt/response content, or artifact bodies by default.
- MCP mirroring changes core behavior or turns MCP into a separate product
  implementation instead of a thin adapter.
- Host documentation omits setup, smoke commands, common failure modes, or
  safety boundaries.

## Phase 2.5: Worker Invocation Protocol

Detailed plan:

```text
docs/v2-phase-2-5-worker-invocation-protocol-plan.md
```

Goal-mode objective:

```text
Implement V2 Phase 2.5 Worker Invocation Protocol for Lab-Sidecar. Extract the
current heuristic and fake-provider worker paths into a stable subagent-like
request/result lifecycle with WorkerRequest, WorkerResult, WorkerInvocation, and
SidecarWorker interfaces. Keep delegate_experiment_artifacts as the public local
tool entrypoint, preserve deterministic validation before adoption, and finish
by writing docs/v2-phase-2-5-worker-invocation-protocol-acceptance.md with
evidence and tests.
```

### Goal

Make the worker flow behave like a subagent delegation protocol without making
Lab-Sidecar depend on Codex host subagent internals or become a generic
multi-agent framework.

### Implementation Targets

- Add structured worker request/result models and a `SidecarWorker` protocol
  under `lab_sidecar/intelligence/`.
- Make heuristic and fake-provider paths use the same worker invocation layer.
- Keep workers as proposal producers only; deterministic validators remain the
  only gate into official V1 artifact generation.
- Persist `worker-request.json` and `worker-result.json` under each
  task-local `intelligence/<worker_run_id>/` directory.
- Preserve minimal context responses and omitted-content defaults.
- Do not add MCP mirroring, real provider adapters, Web UI, FastAPI, hosted
  execution, remote runners, or generic multi-agent orchestration in this
  phase.

### Required Tests

- Heuristic worker runs through the protocol and still adopts only
  validator-approved proposals.
- Fake-provider worker runs through the same protocol and preserves budget,
  redaction, audit, and fallback behavior.
- `intelligent_mode="off"` skips the worker and returns the V1 fallback summary.
- Worker/provider unavailable paths return risk flags without crashing.
- Rejected proposals are recorded but not adopted.
- Existing V1 CLI, MCP, and V2 host/provider/heuristic tests still pass.

### Acceptance Commands

```bash
py -3 -m pytest tests/test_v2_worker_invocation.py
py -3 -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py
py -3 -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py
py -3 scripts/mcp_stdio_smoke.py --workspace "$TMPDIR/lab-sidecar-v2-phase-2-5-mcp"
py -3 -m pytest
git status --short
```

### Blocking Criteria

- Worker implementations can bypass the protocol and directly write official
  artifacts.
- Official artifacts can be created from unvalidated proposals.
- Default responses include worker transcripts, prompt/response bodies, full
  logs, full datasets, report bodies, PPT content, or artifact bodies.
- The protocol requires AI or Codex host subagent internals for normal
  workflows.
- Existing V1 CLI or MCP tests regress.

## Final V2.1-2.4 Acceptance Gate

After Phase 2.4, the final phase record must judge whether V2.1 through V2.4
are ready for the next V2 stage.

The judgment can pass only if:

- V1 CLI and MCP behavior still pass existing tests.
- Delegation can create task-local intelligence records without context leaks.
- Heuristic worker output can be validated and adopted into official artifacts.
- AI provider usage is optional, bounded, audited when enabled, and safe to skip
  when unavailable.
- Host-facing tools satisfy the minimal context and omitted-content contract.
- Every phase has a written acceptance record with commands, task IDs, worker
  run IDs where applicable, artifacts, tests, blocking items, follow-ups,
  out-of-scope items, and final judgment.

## Out Of Scope For These Phases

- Web UI, FastAPI, hosted services, remote runners, and multi-user permissions.
- Generic autonomous research assistant behavior.
- Generic multi-agent orchestration.
- Animation, GIF, MP4, Manim, Remotion, or native PowerPoint animation.
- Default upload of full logs, full datasets, user source code, report bodies,
  PPT content, worker transcripts, or artifact bodies to cloud AI services.
- OS-level sandboxing, containers, Docker, WSL, or malware-protection claims.

## Assumptions And Defaults

- This plan controls execution for V2 phases 2.1 through 2.5.
- The design source of truth remains `docs/v2-intelligent-sidecar-design.md`.
- The new implementation should prefer existing V1 service APIs and artifact
  formats over new parallel behavior.
- AI provider policy is "available key may be used only with explicit workspace
  configuration." Key presence alone is not sufficient.
- Codex integration is local plugin-like first. Confirmed plugin packaging and
  MCP host configuration may be documented or implemented when current official
  Codex docs support them.
- If a future Codex plugin registration format conflicts with this plan, keep
  the local tool contract stable and update host packaging separately.
