# Changelog

All notable user-facing changes should be recorded here. This project has not published a stable release yet; entries describe the current public-alpha baseline and pending changes.

## [0.1.3] - Pending

### Added

- Added small checked-in real-ish fixtures for messy CSV collection and JSON
  benchmark collection, each with explicit `collect --config` examples.
- Added focused regression coverage for messy CSV and JSON benchmark ingest
  paths through deterministic figures, reports, slides, validation, and
  packaging where applicable.

### Changed

- `metrics/collection-summary.json` now includes bounded `source_selection`
  evidence for configured source include/exclude handling, selected files,
  skipped configured sources, and next-action guidance.
- Collector diagnostics keep existing reason strings while adding bounded
  messages for empty/header-only CSV inputs and files with no detected metric
  fields.
- Automatic figure planning now tries deterministic box/bar defaults when a
  detected line-chart axis cannot produce any usable line figure.

### Documentation

- Documented the v0.1.3 real sample robustness plan and acceptance record.
- Updated public docs to point users at explicit config for representative
  messy local CSV/JSON samples without expanding the supported product scope.

### Validation

- No Web UI, FastAPI/HTTP service, hosted service, remote runner, cloud sync,
  advanced analytics, statistical significance, AI-authored conclusions, DAG
  scheduler, or MCP/V2 product-surface expansion was added.

## [0.1.2] - 2026-06-24

### Changed

- Consolidated task artifact registration through a shared manifest helper for
  collected metrics, figures, report fragments, and slide drafts while keeping
  the existing task artifact layout and CLI workflow unchanged.
- Hardened saved-comparison artifact discovery and packaging so comparison
  packages include generated figure images declared by `figure-summary.json`
  instead of arbitrary image files placed under the comparison `figures/`
  directory.
- Clarified comparison CLI recovery guidance when a comparison id is missing,
  without removing or renaming any existing commands.

### Documentation

- Tightened the artifact protocol wording around `manifest.json` as the
  task-local source of truth and SQLite as a rebuildable index.
- Clarified MCP/V2 host-integration boundaries as local, experimental, bounded
  adapters over CLI artifact services, without expanding the MCP/V2 product
  surface.

### Validation

- Added manifest/index projection coverage and comparison package allowlist
  coverage for the v0.1.2 artifact contract stabilization pass.
- No Web UI, FastAPI/HTTP service, hosted service, remote runner, cloud sync,
  advanced analytics, statistical significance, AI-authored conclusions, DAG
  scheduler, or general agent-framework behavior was added.

## [0.1.1] - 2026-06-24

### Added

- v0.1.1 post-RC artifact UX polish for the local CLI artifact workflow:
  saved comparison discovery, validation diagnostics, package verification
  diagnostics, deterministic comparison report formatting, and smoke
  assertions without expanding MCP/V2, Web/API, remote, cloud, AI, or
  statistical-claim scope.
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
- `validate <task_id>` for task artifact health checks without generating new
  artifacts.
- `package-verify <package_dir>` and `artifact-index.sha256` for package
  integrity checks.
- Saved comparison artifacts with `compare --save`, deterministic comparison
  tables, bounded summaries, optional figures/reports, comparison traceability,
  `validate-comparison`, and `package-comparison`.
- Read-only saved comparison discovery commands:
  `list-comparisons`, `open-comparison`, and `comparison-artifacts`, without
  changing the final-row descriptive comparison scope or exposing MCP/V2 tools.
- Explicit multi-figure YAML specs under `figures:` while preserving the
  legacy single-spec YAML shape.
- `scripts/cli_full_smoke.py` and `scripts/wheel_smoke.py` for release-oriented
  local and wheel-install smoke validation from a repository checkout.
- `docs/release-hardening-acceptance.md` as the release-candidate closure
  record for build, installed-wheel smoke, package verification, and local-first
  scope confirmation.

### Documentation

- Documented the post-RC artifact UX polish as CLI-first, file-first,
  local-first quality work, including read-only comparison discovery commands,
  descriptive final-row comparison limits, validation/package diagnostics, and
  deterministic comparison report formatting.
- Clarified that public claims should stay CLI-first, file-first, and local-first.
- Reworked the README into a public landing page with quickstart, artifact previews, CLI table, MCP boundary, limits, and project links.
- Clarified that MCP remains experimental and local, including the V2 mirror.
- Clarified that Codex supervisor agents or subagents are development coordination, not Lab-Sidecar product architecture.
- Added Experiment Scenario Sidecar V1 release notes and canonical scenario
  smoke evidence.
- Added a capability boundary matrix and tightened agent safety wording for
  manual CLI `run` versus MCP/V2 bounded delegation, including human-owner
  review, redaction, interpretation, and final-decision responsibilities.
- Added the Phase 2 Core Stability and Trust source-of-truth plan and baseline
  acceptance scaffold.
- Added current-scope, figure-spec, artifact-protocol, and release-checklist
  coverage for validate, package verification, multi-figure specs, and wheel
  smoke validation.
- Added comparison artifact documentation covering bounded descriptive
  comparisons, non-goals, artifact layout, validation, packaging, and package
  verification.
- Documented online and offline wheelhouse release-smoke paths for environments
  with or without direct PyPI access.
- Release candidate notes now emphasize the local-first alpha CLI artifact
  workflow, `validate`, `package`, `package-verify`, traceability, and bounded
  optional MCP adapter limits.

### Release Candidate

- Hardened saved comparison release readiness with duplicate-task rejection,
  comparison id/path validation, non-finite and metadata-field exclusion
  coverage, stricter comparison validation/package consistency checks, smoke
  summary re-baselining, and a dedicated comparison acceptance record.
- Closed the build and installed-wheel smoke blocker in a venv-backed release
  validation environment: `scripts/wheel_smoke.py` builds the release wheel,
  installs it into an isolated venv, and runs the installed `labsidecar`
  workflow through `package-verify`.
- Aligned MCP/V2 omitted-content metadata keys with the public bounded-response
  contract without expanding the tool surface or returning additional artifact
  bodies.
- Prepared the package metadata for v0.1.1 release finalization; no tag, main
  push, release, or PyPI publish was performed during finalization.

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
