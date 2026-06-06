# Lab-Sidecar V2 Intelligent Sidecar Design

Date: 2026-06-05

## 1. Purpose

Lab-Sidecar V2 is a Codex-plugin-first intelligent sidecar for agent runtime use.

The primary user is not a human manually operating every CLI step. The primary caller is a main Codex agent that is already working on a user task and needs to delegate noisy, long-running, artifact-heavy work without polluting its own context.

V2 extends the V1 local-first artifact pipeline with an isolated intelligent worker:

```text
Codex main agent
  -> Lab-Sidecar plugin tool
  -> task-local sandbox
  -> intelligent worker plans and probes
  -> deterministic validator
  -> V1 core services generate official artifacts
  -> minimal context returns to Codex
```

The product remains a local experiment sidecar and artifact delegation layer. V2 must not become a generic multi-agent orchestration system.

## 2. Product Positioning

V1 proved the deterministic local pipeline:

```text
run / ingest -> collect -> figures -> report -> slides -> artifacts
```

V2 changes the planning layer, not the product identity.

The intelligent worker becomes the main planning path for non-trivial artifact generation:

- schema resolution for non-standard CSV/JSON/log outputs
- figure planning for benchmark, comparison, and project data
- failure diagnosis from bounded stderr/log summaries
- report and slide structure planning from existing artifacts

The worker does not directly produce trusted final outputs. Official metrics, figures, reports, and slides are still written by Lab-Sidecar core services after deterministic validation.

## 3. Design Principles

### 3.1 Codex Plugin First

V2 is designed primarily for use by a running Codex main agent.

The main agent should call Lab-Sidecar when:

- a local experiment may run for a long time
- stdout/stderr is large or noisy
- result files have unknown or non-standard schemas
- charts, report fragments, or PPT drafts are needed
- a task requires artifact traceability rather than conversational analysis

CLI remains available for debugging, manual acceptance, and fallback. MCP compatibility can be designed later, but it must not weaken the Codex plugin experience.

### 3.2 On-Demand Delegation

The plugin should not automatically intercept every command or file operation. The main agent decides when delegation is appropriate.

This keeps the boundary explicit:

- Codex understands the user's natural-language intent.
- Lab-Sidecar handles isolated artifact work.
- The user sees final answers composed from concise summaries and artifact paths.

### 3.3 Minimal Context Return

The plugin response should be small enough for a main agent to continue reasoning without reading raw execution traces.

Default responses include:

- `task_id`
- `status`
- bounded `summary`
- `artifacts`
- `next_actions`
- `risk_flags`
- `omitted`

Default responses must not include:

- complete stdout or stderr
- complete metric rows
- report body
- PPT content
- worker prompt or full response
- artifact bodies
- full data files

Detailed records are written to task-local files and can be requested later only through bounded preview tools.

### 3.4 Isolated But Practical

The V2 worker may read, write, and run commands inside its task-local sandbox. It must not read or write outside that sandbox.

This is a product-level task sandbox, not an OS security sandbox. V2 should not claim malware protection, container isolation, or global shell interception.

### 3.5 AI Optional

V2 can use an AI provider when configured, but AI must remain an enhancement.

If no AI provider is configured:

- V1 deterministic commands continue to work.
- plugin tools return a clear fallback summary.
- no user workflow becomes unusable solely because AI is unavailable.

## 4. Non-Goals

V2 does not include:

- Web UI
- FastAPI backend
- remote runner
- hosted service
- animation, GIF, MP4, Manim, or Remotion
- autonomous research assistant behavior
- general multi-agent framework
- arbitrary agent-to-agent protocol
- default upload of full logs or full datasets to cloud AI services

## 5. Architecture

### 5.1 Runtime Flow

```text
Codex main agent
  -> delegate_experiment_artifacts
  -> create or locate Lab-Sidecar task
  -> build bounded input bundle
  -> create task-local sandbox
  -> run intelligent worker
  -> write proposal artifacts
  -> run deterministic validator
  -> adopt valid proposal
  -> call V1 collect / figures / report / slides services
  -> write official artifacts
  -> return minimal response
```

### 5.2 Task Directory Layout

Each V2 task keeps V1 artifact structure and adds an `intelligence/` area:

```text
.lab-sidecar/tasks/<task_id>/
  manifest.json
  stdout.log
  stderr.log
  metrics/
  figures/
  reports/
  slides/
  reproduce/
  intelligence/
    <worker_run_id>/
      input-bundle.json
      prompt.md
      response.json
      proposal.yaml
      validator-result.json
      adoption-record.json
      diagnostics.md
      sandbox/
```

`sandbox/` is the only writable area for the worker.

Official artifact directories remain owned by deterministic Lab-Sidecar services:

- `metrics/`
- `figures/`
- `reports/`
- `slides/`
- `reproduce/`
- `manifest.json`

### 5.3 Component Responsibilities

Main Codex agent:

- understands the user's goal
- decides whether to delegate
- passes bounded task intent to the plugin
- uses returned summaries and artifact paths to answer the user

Lab-Sidecar plugin tool layer:

- exposes high-level delegation tools
- enforces workspace and task boundaries
- creates or inspects tasks
- returns minimal context only

Intelligent worker:

- receives a bounded input bundle
- probes data inside sandbox
- writes proposal artifacts
- may run local helper commands inside sandbox
- cannot write official artifacts directly

Deterministic validator:

- checks proposal references and safety boundaries
- rejects unsupported claims and out-of-scope paths
- records validation results
- authorizes adoption into the official V1 pipeline

V1 core services:

- collect normalized metrics
- render figures
- generate Markdown reports
- generate static editable PPTX drafts
- record provenance and artifact metadata

## 6. Public Plugin Interfaces

V2 should expose a small set of high-level plugin tools for Codex. Exact transport can be Codex plugin tooling first; MCP can mirror these contracts later.

### 6.1 `delegate_experiment_artifacts`

Primary entrypoint for main-agent delegation.

Input:

```json
{
  "workspace_path": "C:/path/to/project",
  "user_goal": "Generate report and PPT artifacts for this experiment.",
  "command": "optional local command",
  "result_path": "optional existing result path",
  "desired_outputs": ["metrics", "figures", "report", "slides"],
  "intelligent_mode": "auto",
  "context_budget": {
    "summary_tokens": 800,
    "preview_rows": 20,
    "log_tail_lines": 80
  }
}
```

Rules:

- `command` and `result_path` are mutually optional, but at least one task source must exist.
- `intelligent_mode` supports `auto` and `off`.
- `auto` enables worker planning when AI/provider and sandbox policy are available.
- `off` runs the V1 deterministic path.

Default output:

```json
{
  "task_id": "task_...",
  "status": "completed",
  "summary": {
    "headline": "Artifacts generated from 3 CSV sources.",
    "metrics_rows": 15,
    "figure_count": 2,
    "report_generated": true,
    "slides_generated": true
  },
  "artifacts": [
    {
      "type": "figure",
      "path": ".lab-sidecar/tasks/task_.../figures/example.png",
      "description": "Validation accuracy by model"
    }
  ],
  "next_actions": [
    "Open the PPTX draft for manual editing.",
    "Review validator diagnostics if a chart looks unexpected."
  ],
  "risk_flags": [],
  "omitted": {
    "full_stdout": "omitted_by_default",
    "full_stderr": "omitted_by_default",
    "metrics_rows": "omitted_by_default",
    "report_body": "omitted_by_default",
    "ppt_content": "omitted_by_default",
    "worker_prompt_response": "omitted_by_default",
    "artifact_bodies": "omitted_by_default"
  }
}
```

### 6.2 `inspect_sidecar_task`

Returns task status, bounded summaries, artifact metadata, and next actions.

It must not return full logs, full metric rows, or artifact bodies by default.

### 6.3 `cancel_sidecar_task`

Cancels a running task when cancellation is supported for that task type.

It must preserve logs, diagnostics, manifest state, and any completed artifact metadata.

### 6.4 `preview_sidecar_artifact`

Returns a bounded preview of a single artifact.

Examples:

- first N rows of a CSV
- first N lines of Markdown
- dimensions and metadata for an image
- slide count and summary metadata for PPTX
- bounded log tail

It must not be a generic file-reading tool.

### 6.5 Future: `accept_or_reject_sidecar_proposal`

Manual proposal gating is not the V2 default. The default is automatic adoption after validator approval.

This tool may be added later if a workspace policy requires human confirmation before adopting worker proposals.

## 7. CLI Compatibility

Existing CLI commands continue to exist:

```powershell
labsidecar collect <task_id>
labsidecar figures <task_id>
labsidecar report <task_id>
labsidecar slides <task_id>
```

V2 may add debug switches:

```powershell
labsidecar collect <task_id> --intelligent
labsidecar collect <task_id> --no-intelligent
labsidecar figures <task_id> --intelligent
labsidecar figures <task_id> --no-intelligent
```

CLI remains a local user-explicit command path. It should not silently apply Codex plugin policy unless the user opts into V2 intelligent behavior.

## 8. Worker Input Bundles

The input bundle is the only information the worker should receive.

### 8.1 CSV and JSON Inputs

For tabular data, include:

- source artifact path
- file hash and size
- detected encoding where available
- column names
- inferred types
- null counts
- small row sample
- bounded descriptive stats
- existing collection errors

Do not include full data by default.

### 8.2 Logs and Failures

For logs, include:

- command
- exit code
- task status
- failure summary
- bounded stdout tail
- bounded stderr tail
- known artifact paths
- environment/provenance summary

Do not include complete stdout or stderr by default.

### 8.3 Report and Slides Planning

For reports and slides, include:

- manifest summary
- collection summary
- figure summary
- report summary if present
- slide summary if present
- available artifact list
- user goal
- template/language preference when known

Do not include full report body or PPT content by default.

## 9. Worker Outputs

The worker writes proposals into its `intelligence/<worker_run_id>/` directory.

Supported proposal types:

- `metrics-proposal.yaml`
- `figure-proposal.yaml`
- `report-plan.yaml`
- `slides-plan.yaml`
- `failure-diagnosis.md`

A proposal is not trusted until validated.

### 9.1 Metrics Proposal

Contains:

- selected source files
- field mappings
- units
- group fields
- seed/model/method aliases
- confidence and rationale

### 9.2 Figure Proposal

Contains:

- figure IDs
- chart types
- x/y/group fields
- source metrics
- titles and units
- expected output formats
- skipped candidate rationale

### 9.3 Report Plan

Contains:

- report sections
- artifact citations
- allowed numeric claims
- unknowns to mark as not inferred
- failure-diagnostic sections when relevant

### 9.4 Slides Plan

Contains:

- slide list
- per-slide purpose
- cited artifact paths
- included figures/tables
- text budget hints
- overflow/truncation expectations

## 10. Deterministic Validator

The validator is the hard trust boundary between worker output and official artifacts.

It must reject proposals that:

- reference files outside allowed task/workspace scope
- reference columns or fields that do not exist
- use unsupported chart types
- contain numeric claims absent from metrics or summaries
- cite non-existent artifacts
- require reading full logs or full datasets without explicit permission
- attempt to write official artifact directories directly
- include paths that escape `sandbox/`
- ask the main agent to treat unverified analysis as fact

Validator output:

```json
{
  "accepted": true,
  "proposal_type": "figure",
  "checks": [
    {
      "name": "source_paths_within_scope",
      "status": "passed"
    },
    {
      "name": "fields_exist",
      "status": "passed"
    }
  ],
  "adopted_config_path": ".lab-sidecar/tasks/task_.../figures/figure-spec.yaml",
  "diagnostics": []
}
```

If validation fails, official artifact generation must not use that proposal.

## 11. Sandbox Policy

### 11.1 Directory Boundary

Each worker run gets:

```text
.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/sandbox/
```

Allowed:

- read copied or sampled input files inside sandbox
- write temporary scripts and outputs inside sandbox
- run bounded local commands inside sandbox
- produce proposal artifacts outside sandbox only through Lab-Sidecar-controlled write APIs

Blocked:

- reading arbitrary workspace files
- writing user project files
- writing official task artifact directories
- resolving symlinks outside sandbox
- absolute output paths outside sandbox

### 11.2 Command Execution

Worker command execution should be narrow:

- default working directory is sandbox
- bounded timeout
- bounded stdout/stderr capture
- no shell destructive commands by default
- no inherited broad environment by default
- selected environment variables only

This is not a replacement for OS sandboxing. If future work adds Docker, WSL, or OS-level isolation, it should be a sandbox provider behind the same policy contract.

## 12. AI Provider Policy

AI providers are optional.

Provider configuration should include:

- provider name
- model name
- max input budget
- redaction policy
- whether cloud upload is allowed
- audit retention policy

Default cloud policy:

- do not upload complete logs
- do not upload complete datasets
- do not upload user source code unless explicitly included in the bounded input bundle
- record prompt and response in local audit artifacts when enabled

If cloud upload is disabled or no provider is configured, the worker should either:

- skip intelligent planning and run V1 deterministic flow, or
- run a non-AI heuristic worker if available.

## 13. Context Quarantine For Codex

The central V2 promise is that the main Codex agent receives enough information to help the user without absorbing noisy task internals.

Default plugin response:

```text
task_id
status
bounded summary
artifact list
next actions
risk flags
omitted contract
```

The main agent should not need:

- full stdout/stderr
- complete metrics
- raw worker transcript
- full report body
- PPT internals
- copied data samples

When the main agent asks for more, `preview_sidecar_artifact` must apply bounded preview rules and record what was omitted.

## 14. Failure Modes

Worker unavailable:

- fall back to V1 deterministic path
- return `risk_flags=["intelligent_worker_unavailable"]`

AI provider unavailable:

- fall back to V1 deterministic path or heuristic worker
- return `risk_flags=["ai_provider_unavailable"]`

Validator rejects proposal:

- preserve proposal and validator diagnostics
- do not generate official artifacts from rejected proposal
- return next actions explaining whether manual config is needed

Sandbox command fails:

- record command, bounded logs, exit code, and diagnostics
- keep official artifact directories unchanged

Official artifact generation fails after proposal adoption:

- preserve adopted config and core service diagnostics
- return artifact generation failure summary
- do not hide the accepted worker proposal

## 15. Acceptance Scenarios

### 15.1 Codex Plugin Delegation

Given a non-standard CSV experiment directory, the main Codex agent calls `delegate_experiment_artifacts`.

Expected:

- worker creates a metrics proposal
- validator accepts field mappings
- official metrics, figures, report, and slides are generated
- plugin response returns only minimal context and artifact paths
- full audit bundle remains in task-local files

### 15.2 Context Quarantine

Given a task with large stdout/stderr, the plugin response omits complete logs.

Expected:

- `omitted.full_stdout=omitted_by_default`
- `omitted.full_stderr=omitted_by_default`
- bounded log preview is available only through `preview_sidecar_artifact`

### 15.3 Sandbox Boundary

Given a worker proposal or command that attempts to read or write outside sandbox, the sandbox policy rejects it.

Expected:

- no user project files are modified
- official task artifacts are unchanged
- diagnostics are recorded under `intelligence/<worker_run_id>/`

### 15.4 Validator Rejection

Given a figure proposal referencing a missing field, validator rejects it.

Expected:

- official figure generation does not use the proposal
- diagnostics identify the missing field
- main agent receives a concise failure summary and next actions

### 15.5 AI Fallback

Given no AI provider configuration, V2 plugin tools still complete deterministic paths when possible.

Expected:

- no crash due to missing AI
- V1 outputs remain available
- response includes a risk flag or note that intelligent planning was skipped

## 16. Rollout Plan

Phase V2.0: Design and contracts

- write this design
- define plugin tool contracts
- define task-local intelligence artifact protocol
- define sandbox and validator invariants

Phase V2.1: Non-AI scaffold

- implement task-local sandbox creation
- implement input bundle builders
- implement proposal file schema
- implement validator skeleton
- expose plugin-like local tool functions for Codex testing

Phase V2.2: Heuristic worker

- implement non-AI schema and figure proposal heuristics
- validate and adopt proposals
- keep V1 fallback unchanged

Phase V2.3: AI worker provider

- add optional AI provider interface
- enforce bounded input bundle
- record prompt/response audit artifacts
- run real Codex-plugin acceptance scenarios

Phase V2.4: Host integration hardening

- add bounded artifact preview
- improve cancellation and inspection paths
- mirror contracts to MCP only if it does not weaken Codex plugin behavior

## 17. Open Follow-Ups

- Exact Codex plugin tool registration format.
- Whether cloud AI providers are allowed by default or must be opt-in per workspace.
- Concrete prompt templates for each worker role.
- Formal YAML schemas for each proposal type.
- Optional sandbox provider interface for future OS/container isolation.
- Policy for retaining or redacting prompt/response audit files in sensitive projects.

## 18. Final Judgment

This V2 design keeps Lab-Sidecar's V1 strengths while addressing the main limitation of deterministic-only artifact generation. Codex can delegate complex, context-heavy work to Lab-Sidecar; the intelligent worker can plan and probe inside a confined task sandbox; deterministic validators and core services remain responsible for trusted artifacts; and the main agent receives only the minimal context needed to continue helping the user.
