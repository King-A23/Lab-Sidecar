# Current Scope

Lab-Sidecar is a CLI-first, file-first, local-first artifact sidecar for local experiment runs and imported result files.

## Main Path

The current product path is:

```text
run / ingest -> collect -> figures -> report -> slides
```

Release hardening and shareable evidence build on that path:

```text
run / ingest -> collect -> figures -> report -> slides -> package / traceability / validate
run / ingest -> collect -> compare --save -> validate-comparison -> package-comparison -> package-verify
```

Packages and task-local traceability build on that path after artifacts exist.
Saved comparison artifacts build on already-collected local tasks.
The artifact contract is summarized here; details live in
[artifact-protocol.md](artifact-protocol.md).

## Supported Today

- User-explicit local CLI `run` for commands the user chooses to execute.
- `ingest` for existing local result files or directories.
- CSV/JSON metric discovery, collection, normalization, and bounded scenario summaries.
- Bounded descriptive saved comparisons for 2-5 already-collected local tasks.
- Deterministic static PNG/SVG figures for supported chart shapes.
- Deterministic Markdown report fragments from recorded artifacts.
- Static editable PPTX drafts from metrics, figures, reports, and diagnostic records.
- Shareable task packages built from an allowlist of generated artifacts.
- `validate` checks for task artifact health without generating artifacts.
- `package-verify` checks package digests, indexed file hashes and sizes, and unexpected files.
- Task-local `provenance/traceability.json` that records artifact evidence, source references, and omission notes without embedding full bodies.

## Not Supported

Lab-Sidecar does not currently provide or claim:

- Web UI.
- FastAPI or any HTTP service.
- Hosted service behavior, cloud sync, or multi-tenant service features.
- Remote runner or remote execution.
- A general multi-agent framework.
- OS sandboxing for CLI `run`; CLI `run` is user-explicit local command execution.
- Default AI analysis, AI chart recommendation, or AI report writing.
- Statistical significance, model superiority, paper conclusions, deployment recommendations, or autonomous experiment interpretation.
- Cross-workspace comparison or general experiment tracking dashboards.
- Default recursive scanning of an entire workspace.
- JSONL, TensorBoard, full MLflow tracking-store parsing, complex chart systems, animation, video, or interactive chart output.
- Moving, deleting, or rewriting user source files as a side effect of collection or rendering.

## MCP And V2 Boundary

MCP and V2 host integration are optional, local, experimental, and thin adapters over the same task services used by the CLI.

They may return task ids, compact summaries, bounded previews, risk flags, next actions, and artifact metadata. They are not the main product surface, not a hosted service, not a remote runner, not a Web UI, not a FastAPI app, and not a general multi-agent framework. MCP-facing command paths have conservative workspace and command guardrails, but those guardrails are not operating-system isolation, a container runtime, or malware detection.

## Development Principles

- Strengthen the CLI and artifact quality before expanding integrations.
- Preserve the `run / ingest -> collect -> figures -> report -> slides` path.
- Keep business logic in reusable local services and keep CLI, MCP, and host-facing layers thin.
- Treat MCP changes cautiously and avoid schema changes unless explicitly required.
- Defer Web, remote, hosted, cloud sync, and general agent-framework work.
- Keep public claims cautious: deterministic artifacts and bounded descriptive summaries, not autonomous research conclusions.
