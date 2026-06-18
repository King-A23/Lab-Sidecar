---
name: use-lab-sidecar
description: Delegate local experiment runs, research result ingestion, metrics collection, figures, reports, and slides to Lab-Sidecar from Codex while preserving context quarantine.
---

# Use Lab-Sidecar

Use this skill when a Codex task would benefit from moving noisy experiment or artifact work out of the main thread, especially for research-style results that should stay out of the prompt context.

## When To Delegate

Delegate to Lab-Sidecar when the user asks to:

- run or monitor a local experiment command
- ingest existing CSV or JSON experiment results, especially nested or messy result directories
- collect metrics, generate figures, write report fragments, or draft slides
- package a completed or failed task into a shareable local result folder
- keep long logs, raw rows, PPT content, and worker diagnostics out of the main conversation

Keep ordinary source-code edits in Codex unless the main value is a reproducible artifact record.

## When Not To Delegate

Do not use Lab-Sidecar as:

- a general file browser for arbitrary workspace files
- a way to paste full logs, full metrics tables, report bodies, PPT contents, or artifact bytes into the Codex thread
- a replacement for ordinary code editing, unit tests, linting, or repository refactors
- a remote runner, hosted service, Web UI, FastAPI app, cloud sync tool, malware scanner, or OS sandbox
- a bypass for destructive or untrusted shell commands
- a generic multi-agent orchestration layer

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

## Common Tool Patterns

Delegate existing results and inspect bounded state:

```text
delegate_experiment_artifacts(result_path="examples/csv-comparison", desired_outputs=["metrics", "figures", "report", "slides"], intelligent_mode="off")
inspect_sidecar_task(task_id)
```

Preview only the needed bounded detail:

```text
preview_sidecar_artifact(task_id, "metrics/normalized_metrics.csv", max_rows=1)
preview_sidecar_artifact(task_id, "reports/report-fragment.md", max_lines=5)
preview_sidecar_artifact(task_id, "stdout.log", max_lines=20)
```

Use cancellation tools for running tasks. If a task is already completed, failed, cancelled, or missing, expect a bounded not-cancelled response instead of log bodies.

For messy nested result folders, prefer explicit `collect --config` or a host workflow that creates the same config shape. Do not imply broad automatic recursive discovery. For sharing results, use `package <task_id>`; packages are allowlisted exports and omit full logs, raw source refs, worker prompt/response bodies, sandbox files, and unrelated workspace files by default.

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

A concise Codex answer after delegation should look like:

```text
Task task_... completed. Metrics, figures, report, and slides are registered under .lab-sidecar/tasks/task_.../. The default response omitted full logs, rows, report body, PPT contents, and worker prompt/response bodies. Next useful previews: normalized metrics with max_rows=3 or report Markdown with max_lines=10.
```

## Supervisor And Subagents

Codex supervisor agents may spawn subagents for audits, tests, documentation, or implementation slices. Treat those subagents as execution coordination in Codex, not as Lab-Sidecar product architecture. Lab-Sidecar itself remains a local artifact sidecar with deterministic validation and task-local records.
