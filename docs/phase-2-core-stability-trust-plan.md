# Phase 2 Core Stability And Trust Infrastructure Plan

Date: 2026-06-23

This document is the source of truth for the post V1/V1.1 Phase 2 workstream.
It is not the earlier Design Goals Phase 2 or V2 worker Phase 2.x track. This
phase starts after the Experiment Scenario Sidecar V1/V1.1 release and focuses
on making the public alpha reliable, maintainable, and easier to integrate
without expanding the product boundary.

## Phase Objective

Move Lab-Sidecar from "runs and has clear positioning" to "stable enough for
careful public-alpha integration":

- stabilize task-local artifact contracts and their omission rules;
- add engineering quality gates that keep small changes reviewable;
- define a safer CLI run path that can coexist with the current explicit shell
  command behavior;
- harden cross-platform confidence for Python 3.11 and 3.12;
- improve release discipline for the next alpha without claiming stable-release
  readiness.

The main workflow remains:

```text
run / ingest -> collect -> figures -> report -> slides
```

## Explicit Boundaries

In scope:

- Schema and compatibility stabilization for existing task-local JSON/YAML
  artifacts.
- Test and CI quality gates for the existing local CLI, collectors, figures,
  reports, slides, package export, traceability, and host-facing bounded
  contracts.
- A planned additive CLI run safety path for argv or safe-profile execution.
- Cross-platform reliability for local filesystem and subprocess behavior.
- Release readiness discipline for a cautious `v0.1.0-alpha.4` cut.

Out of scope for Phase 2:

- Web UI, FastAPI, hosted service, remote runner, cloud sync, or multi-tenant
  permission system.
- Default AI analysis, autonomous research conclusions, statistical significance
  claims, deployment advice, or model-superiority claims.
- New collector families, new scenario types, TensorBoard/JSONL/MLflow parsing,
  or broad recursive ingestion by default.
- Product runtime multi-agent behavior. Codex agents and subagents may help
  repository work only.
- MCP product expansion. MCP code should be touched only if a Phase 2 task
  explicitly affects an existing host-facing contract.
- Breaking the existing manual CLI `run "<command>"` shell behavior during the
  alpha.4 cycle.

## Prioritized Slices

### P0: Baseline And Contract Inventory

Goal: freeze what exists before changing behavior.

- Record current CI, test, dependency, and run-safety baseline in
  `docs/phase-2-core-stability-trust-acceptance.md`.
- Inventory every public task-local artifact with `schema_version` or public
  integration value.
- Mark each field as required, optional, deprecated alias, bounded preview, or
  internal/unstable.
- Confirm the existing omission contract for logs, raw sources, worker audit
  files, artifact bytes, and full metric rows.

### P1: Schema Stabilization

Goal: make file contracts reviewable and compatibility-tested.

- Add checked JSON Schema or Pydantic-backed schema definitions for public
  artifacts.
- Add small golden fixtures for representative success, failure, diagnostic,
  fallback, package, and messy-folder cases.
- Add schema validation tests that run in CI without depending on generated
  repository-local `.lab-sidecar/` state.
- Preserve alpha compatibility by accepting documented aliases while steering
  new code toward canonical fields.

### P2: Engineering Quality Gates

Goal: prevent low-level regressions before larger stability work.

- Add lint and format checks with `ruff`.
- Add a type-check gate after a baseline pass and targeted annotations for
  high-value modules.
- Add coverage reporting and a ratcheting coverage threshold after baseline
  measurement.
- Keep CI fast enough for pull requests while preserving the existing full
  pytest and package build checks.

### P3: CLI Run Safety Path

Goal: add a safer execution mode without surprising current users.

- Keep current `labsidecar run "<command>"` behavior as the explicit shell mode.
- Add an argv/non-shell execution path, for example `run --no-shell -- <argv>`
  or `run --argv ...`, after CLI ergonomics are designed and tested.
- Add an internal run specification that can represent both legacy shell command
  strings and argv commands.
- Add optional safe profiles for common local experiment commands once the argv
  path exists.
- Document the difference between explicit shell execution, argv execution, and
  MCP/V2 safety gates without claiming OS sandboxing.

### P4: Cross-Platform Reliability

Goal: make the file-first workflow reliable on Linux, macOS, and Windows.

- Add Windows and macOS CI smoke coverage for the CLI workflow and packaging.
- Keep the full Linux matrix for Python 3.11 and 3.12.
- Use `sys.executable`, temp workspaces, and `Path`-based assertions in tests.
- Exercise background run, cancellation, stale-worker recovery, and shell/argv
  quoting behavior on at least one non-Linux runner.
- Verify generated reports, slides, figures, package exports, and traceability
  stay path-portable and do not assume POSIX separators.

### P5: Alpha.4 Release Discipline

Goal: cut alpha.4 only after stability evidence exists.

- Keep `CHANGELOG.md`, release notes, schema docs, and acceptance records in sync.
- Do not tag or publish from intermediate implementation slices.
- Before alpha.4, run full CI, focused contract tests, package build, and a
  clean-worktree check.
- Write a short alpha.4 release readiness or post-release audit with concrete
  commands, dates, commit, and known limits.
- Keep alpha.4 positioned as a local-first public alpha, not a stable release.

## Schema Stabilization Plan

All artifacts below should keep `schema_version: "1"` until a breaking change is
unavoidable. Backward-compatible optional additions are allowed. Breaking
changes require a new schema version, migration guidance, and tests for old and
new fixtures.

| Artifact | Current baseline | Stabilization work |
| --- | --- | --- |
| `manifest.json` | Backed by `TaskRecord` and `ArtifactRecord` Pydantic models. Extra task fields are allowed. `schema_version` is `"1"`. | Define required fields, status enum, artifact id/path rules, and compatibility policy for extra fields. Add fixture tests for run, ingest, failed, cancelled, background, and SQLite-independent inspection. |
| `metrics/collection-summary.json` | Built as a service-layer dict. Records candidates, processed files, skipped files, diagnostics, units, groups, bounded analysis, and output files. | Add a public schema for successful collection and no-metrics diagnostics. Stabilize diagnostic reason strings, bounded analysis shape, unit conflict records, and source path rules. |
| `metrics/scenario-summary.json` | Documented in `experiment-scenario-summary-contract.md`; focused tests cover boundedness, free-text omission, missing primary metric, and descriptive seed aggregates. | Convert the contract into schema tests and golden fixtures for `training-run`, `algorithm-benchmark`, missing-primary, wide-table, multi-source, and bad-input cases. Keep advisory values documented as advisory. |
| `figures/figure-summary.json` | Built as a service-layer dict. Includes canonical figure fields, older aliases, unsupported chart diagnostics, and bounded fallback status records. | Stabilize deterministic, no-figure, unsupported-chart, fallback-unavailable, fallback-rejected, and fallback-adopted shapes. Mark `figures` or `generated_figures` alias policy explicitly and keep worker bodies omitted. |
| `reports/report-summary.json` | Built as a service-layer dict. Includes metrics summaries, compact scenario summary, figure summary, failure/cancellation context, and report claim traces. | Define required claim trace fields, evidence body omission rules, bounded stderr tail policy, scenario-summary reference shape, and failure/cancel diagnostic shape. |
| `slides/slides-summary.json` | Built as a service-layer dict. Includes included metrics/figures, truncation records, key comparisons, QA checks, per-slide evidence, and slide claim traces. | Stabilize truncation fields, QA check names, scenario-summary compact shape, log-body omission, table preview bounds, and project template metadata. Decide which full display fields are public versus internal. |
| `provenance/traceability.json` | Built in `core/traceability.py` with task, environment, sources, artifact hashes, metric/figure/report/slide lineage, claim traces, omitted contract, and source truncation at 200 items. | Add schema tests for completed, failed, package, fallback, and missing-artifact cases. Stabilize omission categories, lineage presence flags, digest omission reasons, and bounded source/claim behavior. |
| `package-summary.json` and `artifact-index.json` | Package export is allowlist-based and includes package metadata, included/unavailable/omitted entries, and a self-referential artifact-index digest note. | Stabilize package types, counts, package metadata entries, omitted/unavailable reason strings, hash/size fields, and failed-task diagnostic labeling. Keep raw sources, full logs, SQLite, worker audits, and sandbox files omitted by default. |

Schema tests should validate generated outputs and checked-in minimal fixtures.
The fixtures should be deliberately small and should not include full logs, raw
source bodies, worker prompt/response bodies, artifact bytes, or repository-local
`.lab-sidecar/` output.

## Engineering Quality Gate Plan

Current baseline:

- `pyproject.toml` has `pytest` in the `dev` extra.
- CI runs pytest and package build on Ubuntu for Python 3.11 and 3.12.
- No `ruff`, type-check, coverage, or cross-platform CI gate is configured yet.

Planned sequence:

1. Add `ruff` to the dev extra and CI with a minimal rule set that catches
   syntax, import, unused-name, and straightforward bug patterns.
2. Add `ruff format --check` only after the repository has a clean formatting
   baseline or after a scoped formatting commit.
3. Add a type-check tool and start with core models, paths, manifest,
   traceability, package export, and service boundaries before requiring strict
   checks across every test helper.
4. Add coverage measurement with `pytest-cov`. First record the baseline without
   a fail-under gate, then set a conservative ratcheting threshold.
5. Keep CI stages visible: lint, typecheck, tests, package build, and optional
   platform smoke. Do not let optional MCP smoke become required unless MCP code
   or packaging metadata is in scope.

Alpha.4 should not require perfect typing or high coverage. It should require
that the configured gates are honest, repeatable, documented, and not bypassed
for release.

## CLI Run Safety Path Plan

Manual CLI `run` is currently a user-explicit local command execution path. It
records command, logs, status, reproduce metadata, and artifacts, but it is not
an OS sandbox. Phase 2 should improve the execution interface without changing
that public truth.

Compatibility rules:

- `labsidecar run "<command>"` remains the legacy explicit shell path for
  alpha.4.
- Existing manifests keep the `command` field.
- Existing tests for shell command behavior must continue to pass.
- New safety behavior must be additive and opt-in until documented and tested.

Implementation plan for a later slice:

- Introduce an internal `RunSpec` concept with `mode: shell | argv`,
  `command_text`, optional `argv`, optional `safe_profile`, and display-friendly
  reproduce fields.
- Add a non-shell execution path using `subprocess.Popen(argv, shell=False)`.
- Route background workers through the same run spec instead of losing argv
  structure through a shell string.
- Add a CLI form such as `run --no-shell -- <program> <arg> ...` or
  `run --argv <program> ...` after validating Typer parsing ergonomics.
- Add safe profiles only after argv mode exists. Initial profiles should be
  narrow, for example Python script/module commands in the workspace, not a
  general policy engine.
- Keep MCP/V2 command safety gates separate from manual CLI shell mode, while
  reusing path-boundary helpers where practical.

Tests for the later implementation should cover:

- legacy shell command still works;
- argv mode preserves spaces and special characters without shell expansion;
- argv mode works for foreground and background tasks;
- cancellation and stale-worker recovery still work;
- reproduce metadata distinguishes shell and argv modes;
- unsafe cwd/path cases are rejected only for the safe profile being tested;
- Windows command invocation does not depend on POSIX shell syntax.

## Cross-Platform Reliability Plan

Current baseline CI is Linux-only. Phase 2 should add platform confidence in
small steps:

- Keep the existing Ubuntu Python 3.11/3.12 full test and build matrix.
- Add Windows and macOS smoke jobs for a focused subset first:
  - `init`, `doctor`, `run`, `collect`, `figures`, `report`, `slides`,
    `package`;
  - background run, status refresh, and cancellation if stable on the runner;
  - schema fixture validation once added.
- Use temporary workspaces outside the repository root and verify no generated
  `.lab-sidecar/` or package folders are left in the checkout.
- Prefer `Path`, `sys.executable`, and manifest-relative path assertions over
  shell-specific path strings.
- Review line endings, file encoding, image rendering, PowerPoint generation,
  process termination, and quoting behavior on each platform.
- Keep optional MCP stdio smoke separate unless MCP behavior is in scope.

## Release Discipline Plan For Alpha.4

Alpha.4 should be a stability and trust release, not a feature expansion
release.

Before alpha.4 can be cut:

- Update `CHANGELOG.md` under an appropriate alpha.4 or Unreleased section.
- Update or add release notes that describe only completed, validated work.
- Run the configured CI gates locally where practical.
- Run focused contract tests for schema, scenario summary, CLI smoke, package,
  traceability, and host-facing bounded responses.
- Run `git diff --check` and confirm generated repository-local artifacts are
  absent.
- Record release readiness or post-release audit evidence with commit, date,
  commands, and known limits.
- Only the maintainer should tag, push, or publish. Planning and implementation
  slices should not create tags.

Alpha.4 messaging should continue to say:

- local-first, file-first, CLI-first;
- MCP/V2 are experimental local integrations;
- CLI run is explicit local command execution, not sandboxing;
- artifacts and logs require human review and redaction before sharing;
- reports and slides are deterministic summaries, not autonomous research
  conclusions.

## Test And Validation Matrix

| Area | Current evidence | Phase 2 target validation |
| --- | --- | --- |
| Scenario summary | `tests/test_scenario_summary.py` and CLI smoke cases cover bounded best rows, missing primary metrics, free-text omission, and descriptive aggregates. | Schema fixtures plus generated-output schema validation for training, benchmark, wide, bad-input, and multi-source cases. |
| CLI lifecycle | `tests/test_cli_smoke.py` covers init, run, background, status, logs, cancel, list, open, ingest, collect, figures, report, slides, package, and SQLite-independent paths. | Keep full CLI smoke passing under quality gates; add platform smoke jobs and argv/safe-run tests after implementation. |
| Host bounded responses | `tests/test_v2_host_integration.py` covers delegate, inspect, preview, cancel, rejected preview paths, body withholding, and scenario compactness. | Keep existing tests passing; add schema checks only for existing bounded response shapes if host contracts are affected. |
| Schemas | Public schema facts exist in docs and tests but not as checked schema files. | Add schema files or Pydantic schema exports plus golden fixture tests. |
| Quality gates | CI runs pytest and package build on Ubuntu 3.11/3.12. | Add ruff, typecheck, coverage reporting, and platform smoke in staged CI jobs. |
| Run safety | Manual CLI run uses explicit shell command behavior. MCP/V2 command paths have separate conservative gates. | Add opt-in argv/non-shell path and safe-profile tests without breaking shell mode. |
| Cross-platform | README includes Windows launcher notes, but CI is Linux-only. | Add Windows/macOS smoke and path/quoting/process checks. |
| Release discipline | Public alpha notes and post-release audits exist for earlier stages. | Add alpha.4 readiness/audit evidence before tag or publish. |

Suggested local validation commands for Phase 2 slices:

```bash
git status --short --branch
git log --oneline -5
find .github/workflows -maxdepth 1 -type f -print
rg -n "ruff|mypy|pyright|coverage|pytest|schema|json schema|run --|shell=True|subprocess|Popen" pyproject.toml .github lab_sidecar tests docs README.md CHANGELOG.md
.venv/bin/python -m pytest tests/test_scenario_summary.py -q
.venv/bin/python -m pytest tests/test_cli_smoke.py -q
.venv/bin/python -m pytest tests/test_v2_host_integration.py -q
git diff --check
```

## Acceptance Criteria

Phase 2 is accepted only when:

- This plan and the acceptance record are current and point to real validation
  evidence.
- Public task-local schemas are documented, tested, and versioned.
- Existing V1/V1.1 scenario-summary boundedness and omission rules still pass.
- Existing local workflow remains `run / ingest -> collect -> figures -> report
  -> slides`.
- CI includes repeatable quality gates for lint, tests, package build, and
  staged type/coverage checks.
- Cross-platform smoke evidence exists for at least Linux, macOS, and Windows.
- The CLI run safety path has an opt-in argv/non-shell mode, or the alpha.4
  release notes explicitly mark it as incomplete and deferred.
- Legacy shell command behavior remains compatible for alpha users.
- Package export and traceability still omit full logs, raw source bodies,
  worker prompt/response bodies, sandbox files, SQLite, and unrelated workspace
  files by default.
- Documentation does not claim a sandbox, hosted service, remote runner, Web UI,
  default AI analysis, or scientific conclusion engine.
- `CHANGELOG.md` and release notes describe only completed work.
- No tag, push, or publish is performed until the maintainer chooses the release
  cut.
