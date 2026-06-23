# Changelog

All notable user-facing changes should be recorded here. This project has not published a stable release yet; entries describe the current public-alpha baseline and pending changes.

## [Unreleased]

### Added

- Contributor guide, security policy, changelog, and release checklist for open-source readiness.
- MIT license file and package metadata for public open-source release preparation.
- Package metadata now points at the public README and marks the project as alpha.
- `doctor`, `list`, and `open` CLI ergonomics for public-alpha onboarding.
- Real demo preview assets generated from `examples/csv-comparison`.
- Repo-scoped Codex plugin scaffold with a Lab-Sidecar usage skill and MCP configuration.
- Thin MCP mirror for V2 bounded host tools:
  `delegate_experiment_artifacts`, `inspect_sidecar_task`,
  `preview_sidecar_artifact`, and `cancel_sidecar_task`.
- Bounded `metrics/scenario-summary.json` records for canonical
  `training-run` and `algorithm-benchmark` scenarios.

### Documentation

- Clarified that public claims should stay CLI-first, file-first, and local-first.
- Reworked the README into a public landing page with quickstart, artifact previews, CLI table, MCP boundary, limits, and project links.
- Clarified that MCP remains experimental and local, including the V2 mirror.
- Clarified that Codex supervisor agents or subagents are development coordination, not Lab-Sidecar product architecture.
- Added Experiment Scenario Sidecar V1 release notes and canonical scenario
  smoke evidence.
- Added a capability boundary matrix and tightened agent safety wording for
  manual CLI `run` versus MCP/V2 bounded delegation, including human-owner
  review, redaction, interpretation, and final-decision responsibilities.

## [0.1.0] - Pending Public Alpha

### Added

- Local CLI workflow for `init`, `run`, `status`, `logs`, `artifacts`, `cancel`, `ingest`, `collect`, `figures`, `report`, and `slides`.
- File-backed task records under `.lab-sidecar/`, with `manifest.json` as the task-local source of truth.
- CSV and JSON metric collection with normalized metrics outputs and collection summaries.
- Deterministic static figure rendering.
- Deterministic Markdown report fragments.
- Editable static PPTX draft generation with summary metadata, bounded text handling, and QA checks.
- Failure diagnostics for command runs, including exit code, stderr/stdout logs, and task status.
- Experimental local MCP adapter exposing the V1 tool surface through the optional `mcp` extra.
- MCP cancellation support through `cancel_experiment`.
- V2 local worker and host-integration scaffolding for bounded, artifact-oriented delegation experiments.

### Known Limitations

- No Web UI, FastAPI app, remote runner, hosted service, or default AI-generated analysis.
- No animation, GIF, MP4, Manim, Remotion, or native PowerPoint animation output.
- CLI `run` is user-explicit local command execution and does not provide OS sandboxing.
- MCP support is experimental and local; host-specific configuration remains limited.
- Bad-input handling covers initial malformed CSV/JSON cases, but broader real-world fixtures remain follow-up work.
