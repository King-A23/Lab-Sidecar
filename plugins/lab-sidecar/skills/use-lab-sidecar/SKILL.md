---
name: use-lab-sidecar
description: Delegate local experiment runs, research result ingestion, metrics collection, figures, reports, and slides to Lab-Sidecar from Codex while preserving context quarantine.
---

# Use Lab-Sidecar

Use this skill when a Codex task would benefit from moving noisy experiment or artifact work out of the main thread, especially for research-style results that should stay out of the prompt context.

## When To Delegate

Delegate to Lab-Sidecar when the user asks to:

- run or monitor a local experiment command
- ingest existing CSV or JSON experiment results
- collect metrics, generate figures, write report fragments, or draft slides
- keep long logs, raw rows, PPT content, and worker diagnostics out of the main conversation

Keep ordinary source-code edits in Codex unless the main value is a reproducible artifact record.

## Tool Preference

Prefer MCP tools when available:

- `delegate_experiment_artifacts` for the V2 bounded delegation path
- `inspect_sidecar_task` for task status and compact artifact summaries
- `preview_sidecar_artifact` for bounded CSV, Markdown, log, image, and PPTX previews
- `cancel_sidecar_task` for V2 task cancellation

The older MCP tools remain useful for the deterministic V1 path:

- `run_experiment`
- `inspect_results`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`
- `cancel_experiment`

If MCP is not available, use the CLI with the local Python interpreter documented by the repository.

## Context Quarantine Rules

Default responses should stay small:

- task id
- status
- bounded summary
- artifact paths
- next actions
- risk flags
- omitted-content contract

Do not paste complete stdout, complete stderr, full metrics rows, full report bodies, PPT contents, worker prompts, worker responses, or artifact bytes into the main Codex answer. Use `preview_sidecar_artifact` only when the user needs bounded detail.

## Supervisor And Subagents

Codex supervisor agents may spawn subagents for audits, tests, documentation, or implementation slices. Treat those subagents as execution coordination in Codex, not as Lab-Sidecar product architecture. Lab-Sidecar itself remains a local artifact sidecar with deterministic validation and task-local records.
