# Supervisor Agent Execution Plan

Date: 2026-06-08

## Purpose

This plan describes how a Codex supervisor can coordinate the public-alpha
demo and acceptance documentation work for Lab-Sidecar.

It is an execution coordination plan, not Lab-Sidecar product architecture.
Codex supervisor agents may spawn subagents to inspect files, draft docs, or
validate acceptance evidence. Lab-Sidecar itself exposes bounded local sidecar
tools, task records, summaries, and artifacts. It is not a general multi-agent
orchestration framework.

## Scope

Owned documentation for this slice:

- `docs/supervisor-agent-execution-plan.md`
- `docs/demo-public-alpha.md`
- `docs/public-alpha-final-acceptance.md`
- `examples/*/README.md` refreshes

Allowed work:

- consolidate existing public-alpha and V2 host acceptance evidence
- document a deterministic demo path using existing examples
- clarify the supervisor-agent versus sidecar-tool boundary
- update example README files so they describe current alpha behavior

Disallowed work:

- Python source changes
- test changes
- Web UI, FastAPI, remote runner, hosted service, animation, or new AI workflow
- claims that Lab-Sidecar launches Codex subagents or controls host agents
- claims that CLI `run` has MCP safety gates
- claims that MCP or V2 tools return full logs, datasets, reports, PPT content,
  worker transcripts, or artifact bodies by default

## Boundary Model

| Layer | May Do | Must Not Be Claimed |
| --- | --- | --- |
| Codex supervisor | Coordinate work and optionally spawn Codex subagents | A Lab-Sidecar runtime component |
| Codex subagent | Inspect or edit assigned files under supervisor direction | A product feature exposed to users |
| Lab-Sidecar CLI | Run or ingest local work and create task-local artifacts | Global shell sandbox or malware defense |
| Lab-Sidecar MCP adapter | Expose bounded V1 tools through local stdio MCP | Full artifact export service |
| Lab-Sidecar V2 local tools | Delegate artifact work through bounded request/result files and previews | Generic file browser or multi-agent protocol |

## Execution Order

1. Start with `git status --short` and treat existing changes as external work
   unless this slice created them.
2. Read current public-alpha, MCP, V2 host, and acceptance docs before writing.
3. Add the supervisor execution plan with explicit ownership and boundaries.
4. Add the public-alpha demo script with deterministic commands and expected
   artifact classes, using `TASK_ID` placeholders for dynamic IDs.
5. Add the final acceptance consolidation document. Cite prior acceptance
   records rather than inventing new test evidence.
6. Refresh example READMEs to describe their current role in the public-alpha
   demo and their expected outputs.
7. Run documentation validation commands and record the results in the final
   response.

## Subagent Packet Template

When a Codex supervisor delegates a slice, each subagent packet should include:

- exact file ownership
- read-only context documents
- disallowed areas such as Python source and tests
- required safety boundary wording
- expected final handoff: changed files, commands, validation result, blockers

The packet should not ask a subagent to read generated task bodies, full logs,
full datasets, report bodies, PPT internals, prompt/response transcripts, or
artifact bodies unless the work explicitly requires a bounded preview.

## Demo Acceptance Matrix

| Scenario | Example | Product Path | Expected Artifact Classes |
| --- | --- | --- | --- |
| Successful run | `examples/simple-success` | `run -> collect -> figures -> report -> slides` | manifest, logs, metrics, figures, report, PPTX |
| Failed run | `examples/simple-failure` | `run -> report -> slides` | manifest, logs, diagnostic report, diagnostic PPTX |
| Multi-run comparison | `examples/csv-comparison` | `ingest -> collect -> figures -> report -> slides` | normalized metrics, comparison figures, report, PPTX |
| JSON benchmark | `examples/algorithm-benchmark` | `ingest -> collect -> figures -> report -> slides` | normalized metrics, runtime figures, report, PPTX |
| Course presentation pack | `examples/project-presentation-pack` | `ingest -> collect -> figures -> report -> slides --template zh-project` | metrics, figures, report, project-style PPTX |
| MCP smoke | generated temp workspace | stdio MCP smoke script | bounded tool responses and task artifacts |

## Stop Conditions

Stop and report a blocker if:

- a required source fact conflicts across existing docs
- the demo would require code or test changes
- a command would need to delete or overwrite user source files
- a doc would need to claim an unimplemented feature
- concurrent edits touch the same owned docs in a way that cannot be merged
  safely

## Final Handoff

The final handoff should list:

- changed files
- commands run
- whether tests were skipped because the slice is docs-only
- any follow-up items that remain outside this documentation slice
