# Post-Open-Source Stage 5 Plan: Provenance And Traceability

Date: 2026-06-18

## 1. Phase Goal

Make Lab-Sidecar's generated artifacts easier to trust, audit, and reproduce.

After Stage 5, a user should be able to inspect a completed task and answer:

- which source files contributed to the normalized metrics
- which hashes identify those source files and generated artifacts
- which metrics rows, columns, figure specs, and source artifacts support report and slide statements
- which Git commit, dependency snapshot, Python executable, and local task files were used
- whether a generated report or slide deck contains unsupported or untraceable numeric claims

The short goal:

> Every important generated claim should point back to task-local evidence.

This stage closes the trust gap left by the public alpha. It should not make Lab-Sidecar more interpretive; it should make Lab-Sidecar more inspectable.

## 2. Product Promise

Stages 1-4 improved navigation, packaging, messy-result adaptation, and bounded Agent delegation. Stage 5 turns those artifacts into a stronger audit trail.

The user-facing promise is:

> A Lab-Sidecar task is not just a folder of outputs; it is a traceable local artifact record.

The product should stay conservative. If a value, comparison, or conclusion cannot be tied to source evidence, the generated summaries should mark it as unknown, omitted, or unsupported rather than filling it in.

## 3. Current Baseline

Useful existing surface:

- `lab_sidecar.core.provenance` already provides `file_sha256`, `file_provenance`, `git_snapshot`, and `dependency_snapshot`.
- `raw/source_refs.json` records source metadata and hashes for ingested files and candidate files.
- `metrics/collection-summary.json` records processed files, source provenance, matched aliases, units, groups, diagnostics, and output files.
- `figures/figure-spec.yaml` and `figures/figure-summary.json` record source metrics, figure specs, units, groups, warnings, and skipped candidates.
- `reports/report-summary.json` records source artifacts, metrics summaries, figure summaries, provenance, and bounded failure/cancellation context.
- `slides/slides-summary.json` records source artifacts, included metrics, included figures, slide records, QA checks, truncations, comparisons, and report excerpts.
- Stage 2 package export includes hashes for copied package files.
- Stage 4 preview and MCP responses already avoid returning full artifact bodies by default.

Current gaps:

- Generated task artifacts in `manifest.json` do not have their own stable provenance digest metadata.
- There is no single task-level provenance index that connects source refs, normalized rows, figure specs, reports, slides, and packages.
- Report numeric summaries are structurally sourced but do not yet expose claim-level source pointers.
- Slide records identify included artifacts but do not consistently express per-slide source evidence and claim support.
- Package export includes copied-file hashes, but not a dedicated traceability index explaining upstream source-to-artifact relationships.
- No-invention tests cover selected cases, but not a broad report/slides claim trace contract.
- Reproducibility remains split across `reproduce/`, source refs, collection summaries, figure summaries, report summaries, slide summaries, and package indexes.

## 4. Non-Goals

Do not implement during this stage:

- Web UI
- FastAPI or hosted service
- remote runner
- cloud sync
- generic multi-agent framework behavior
- default cloud AI/provider calls
- automatic scientific interpretation
- statistical significance testing
- model ranking or autonomous research conclusions
- copying raw source files into packages by default
- returning full logs, full metrics tables, report bodies, slide contents, or artifact bytes in MCP/V2 defaults
- a new database-backed provenance system
- changing the task artifact directory layout in a breaking way

Stage 5 is traceability hardening, not a new analysis product.

## 5. Target Traceability Contract

Stage 5 should introduce or strengthen a stable local contract around traceability.

Recommended new task artifact:

```text
.lab-sidecar/tasks/<task_id>/provenance/traceability.json
```

Recommended shape:

```json
{
  "schema_version": "1",
  "task_id": "task_...",
  "generated_at": "2026-06-18T...",
  "task": {
    "mode": "run",
    "status": "completed",
    "working_dir": "...",
    "command_path": "reproduce/command.txt"
  },
  "environment": {
    "python_executable": "...",
    "git": "reproduce/git.json",
    "dependencies": "reproduce/dependencies.json"
  },
  "sources": [
    {
      "path": "results/seed_1/metrics.csv",
      "sha256": "...",
      "size_bytes": 1234,
      "role": "metrics_source"
    }
  ],
  "artifacts": [
    {
      "artifact_id": "metrics_normalized_csv",
      "path": "metrics/normalized_metrics.csv",
      "sha256": "...",
      "size_bytes": 1234,
      "source_paths": ["results/seed_1/metrics.csv"]
    }
  ],
  "metric_lineage": {
    "row_count": 18,
    "columns": ["epoch", "method", "seed", "accuracy"],
    "source_files": ["results/seed_1/metrics.csv"]
  },
  "claim_traces": [
    {
      "claim_id": "report.metric.accuracy.max",
      "surface": "report",
      "claim_type": "numeric_summary",
      "value": 0.91,
      "field": "accuracy",
      "evidence": [
        {
          "artifact_id": "metrics_normalized_csv",
          "path": "metrics/normalized_metrics.csv",
          "rows": [17],
          "columns": ["accuracy"]
        }
      ]
    }
  ],
  "warnings": []
}
```

The implementation may use a smaller first schema, but it must be task-local, deterministic, documented, and covered by tests.

## 6. Work Slice A: Artifact Hashes And Manifest Provenance

### Target Behavior

Generated artifacts should be identifiable by content hash and size.

Stage 5 should add digest metadata for important task artifacts:

- normalized metrics CSV/JSON
- collection summary
- figure spec and figure summary
- generated figure PNG/SVG files
- report fragment and report summary
- slides PPTX and slides summary
- package summary and artifact index when exporting
- traceability index itself, if practical without self-referential churn

### Implementation Notes

- Prefer using existing `file_provenance(path)` rather than duplicating hashing logic.
- Preserve backward compatibility for `ArtifactRecord`; if adding fields, use Pydantic-compatible optional fields or store digest metadata in summaries/indexes instead of breaking old manifests.
- Avoid expensive unbounded directory hashing.
- Hash files after they are fully written.
- Keep paths portable and task-relative where possible.

### Tests

- Generated metrics, figures, report, and slides summaries include hashes or point to a traceability index that includes hashes.
- Re-running deterministic generation updates hashes consistently without duplicating artifacts.
- Deleting `.lab-sidecar/index.sqlite` does not remove task-local provenance inspectability.

## 7. Work Slice B: Task-Level Traceability Index

### Target Behavior

Add one task-local traceability artifact that connects:

- source refs
- processed metric files
- normalized metrics artifacts
- figure specs and generated figures
- report summary and report fragment
- slide summary and PPTX
- reproduce metadata
- omitted or unavailable evidence

The index should answer "where did this output come from?" without requiring SQLite.

### Implementation Notes

- Recommended helper module: `lab_sidecar/core/traceability.py` or `lab_sidecar/storage/traceability.py`.
- Generate or refresh the index after `collect`, `figures`, `report`, `slides`, and possibly `package`.
- Register the index as a task artifact, for example:

```text
artifact_id: provenance_traceability_json
type: provenance
path: provenance/traceability.json
```

- The index should not copy full rows, full logs, report bodies, slide XML, worker prompt/response bodies, or raw source files.
- It may include row numbers, column names, artifact ids, hashes, counts, and bounded warnings.

### Tests

- Traceability index exists after a full `run -> collect -> figures -> report -> slides` workflow.
- Index records source refs, normalized metrics, figures, report, slides, and reproduce metadata.
- Index remains valid enough to inspect after SQLite deletion.
- Index does not include full stdout/stderr, full metrics row bodies, report body, PPT contents, or worker prompt/response bodies.

## 8. Work Slice C: Report Claim Tracing

### Target Behavior

`reports/report-summary.json` should expose claim traces for numeric summaries and generated statements.

Initial accepted claim types:

- numeric summary claims for `mean`, `min`, and `max`
- metrics row count
- detected fields and omitted numeric fields
- figure count and figure references
- failure/cancellation diagnostic status

### Implementation Notes

- Do not try to parse arbitrary Markdown after rendering.
- Build traces from the same structured data used to render the report.
- Prefer deterministic `claim_id` values.
- Evidence should point to artifact ids/paths, row ranges or row selectors, and column names.
- If exact row positions are too large or ambiguous, include source artifact, field, summary operation, and row count as a first slice.

### Tests

- Completed report summaries include claim traces for numeric summaries shown in the report.
- Failed and cancelled reports include diagnostic claim traces and do not present success metrics as conclusions.
- Reports with missing metrics fail or mark unknown as before.
- Report body still avoids unsupported scientific conclusions.

## 9. Work Slice D: Slide Source And Claim Tracing

### Target Behavior

`slides/slides-summary.json` should make per-slide evidence explicit.

Each slide record should identify:

- source artifacts used by the slide
- metric fields or summary values used
- figure ids or paths shown
- report excerpt source when used
- truncation/omission notes when content was shortened
- unsupported or unknown values when evidence is absent

### Implementation Notes

- Build traces while constructing existing `SlideRecord` objects.
- Do not inspect PPTX XML to infer sources after the fact.
- Keep `slides-summary.json` bounded; source pointers are enough.
- Preserve current slide QA checks and no-invention behavior.

### Tests

- Every generated slide has at least one source/evidence entry or an explicit diagnostic/empty-source reason.
- Figure slides point to figure artifact ids and hashes through the traceability index or summary.
- Metrics table slides identify the metrics artifact, shown columns, hidden columns, and displayed row count.
- Missing baseline/comparison values remain `null` or unknown rather than invented.

## 10. Work Slice E: Package Traceability Evidence

### Target Behavior

Stage 2 packages should carry enough provenance for a recipient to audit included files without the original workspace.

Package output should include or reference:

- copied file hashes
- task traceability index when present
- source-to-artifact lineage for included artifacts
- omitted provenance notes for raw sources, logs, worker audit files, sandbox files, and SQLite
- package creation metadata

Recommended package file:

```text
traceability.json
```

or include the task-local file at:

```text
provenance/traceability.json
```

### Implementation Notes

- Keep package allowlist behavior from Stage 2.
- Do not copy raw source files by default.
- It is acceptable for package traceability to reference raw source paths and hashes without including raw source contents.
- If traceability is missing, package should record it as unavailable rather than failing.

### Tests

- Package includes traceability evidence when generated.
- Package artifact index records hash/size for included traceability files.
- Package still omits full logs, raw source files, worker audit bodies, sandbox files, SQLite, and unrelated workspace files.
- Failed-task diagnostic packages include diagnostic provenance without claiming success.

## 11. Work Slice F: V2/MCP Bounded Provenance Access

### Target Behavior

Agent hosts should be able to discover traceability evidence without pulling full artifacts into context.

Potential first slice:

- `inspect_sidecar_task` includes the traceability artifact id/path when present.
- `preview_sidecar_artifact` supports bounded metadata preview for `provenance/traceability.json`.
- Default V2/MCP responses continue to omit full logs, full tables, report bodies, PPT contents, worker audit bodies, and artifact bodies.

### Implementation Notes

- Keep MCP a thin adapter over local V2/helper contracts.
- Do not add a generic file browser.
- JSON previews should be bounded summaries, not full JSON dumps.
- This slice may be deferred if Stage 5 stays CLI/package/report/slides only, but the acceptance document must say so.

### Tests

- V2 inspect lists provenance traceability artifacts without returning the full index body.
- Preview of traceability JSON returns bounded top-level metadata and selected counts only.
- MCP stdio smoke still passes if MCP or preview behavior changes.

## 12. Work Slice G: No-Invention Regression Suite

### Target Behavior

Add focused tests that prove Lab-Sidecar stays conservative.

Scenarios:

- missing baseline comparison
- missing numeric field
- conflicting units
- failed task report/slides
- cancelled task report/slides
- messy multi-seed result where only configured fields may appear in claims
- package export with omitted raw and worker audit files

### Tests

- Report and slides do not invent a winner, significance, or unsupported causal explanation.
- Claim traces only reference existing artifacts and known fields.
- Unknown values remain unknown/null.
- Full logs and raw rows are not copied into summaries, previews, or package indexes.

## 13. Implementation Boundaries

Likely files to edit:

- `lab_sidecar/core/provenance.py`
- `lab_sidecar/core/models.py`
- `lab_sidecar/core/traceability.py` or `lab_sidecar/storage/traceability.py`
- `lab_sidecar/storage/artifact_store.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/figures/service.py`
- `lab_sidecar/reports/service.py`
- `lab_sidecar/reports/templates.py`
- `lab_sidecar/slides/service.py`
- `lab_sidecar/storage/package_export.py`
- `lab_sidecar/cli/app.py`
- `lab_sidecar/intelligence/preview.py` if bounded traceability preview is implemented
- `lab_sidecar/intelligence/tools.py` if V2 inspect summaries change
- `lab_sidecar/mcp/tools.py` only if MCP mirroring changes
- `tests/test_cli_smoke.py`
- `tests/test_v2_host_integration.py` if V2 preview/inspect changes
- `tests/test_mcp_tools.py` if MCP changes
- `README.md`
- `docs/cli-spec.md`
- `docs/v2-host-integration.md` if V2 traceability exposure changes
- `docs/post-open-source-stage-5-acceptance.md`

Avoid touching unless strictly required:

- runner command execution semantics
- MCP command safety gate
- Stage 3 collector config syntax
- slide visual layout
- plugin skill behavior, unless host provenance guidance changes

## 14. Subagent Guidance For Goal Execution

The implementation agent may use Codex supervisor agents and subagents for independent slices. This is execution coordination only, not Lab-Sidecar product architecture.

Good subagent slices:

- **Traceability schema reviewer**: inspect existing summaries and propose the smallest durable schema.
- **Artifact hash implementer**: add hash/size metadata and tests around generated artifacts.
- **Report claim tracer**: add report-summary claim traces and no-invention tests.
- **Slides evidence tracer**: add per-slide evidence and summary tests.
- **Package provenance reviewer**: verify package inclusion/omission and traceability export behavior.
- **V2/MCP contract reviewer**: check bounded traceability preview and omitted contracts if host tools change.
- **Validation runner**: run focused tests, full tests, manual smoke, and inspect generated traceability files.

Subagents must:

- preserve unrelated local changes
- keep Lab-Sidecar local-first, file-first, CLI-first, artifact-first, and AI-optional
- keep MCP a thin local adapter
- avoid hosted services, remote runners, Web UI, cloud sync, default AI analysis, and generic multi-agent features
- avoid copying raw source files, full logs, worker audit bodies, or generated `.lab-sidecar/` task outputs into the repository

The supervisor remains responsible for reading required instructions, integrating changes, resolving conflicts, running final validation, and writing `docs/post-open-source-stage-5-acceptance.md`.

## 15. Concrete Acceptance Standards

Stage 5 is complete only when all selected implementation slices satisfy these gates:

1. A task-local traceability artifact exists or equivalent traceability metadata is documented and registered.
2. Important generated artifacts have hash/size provenance in summaries, manifests, package indexes, or the traceability artifact.
3. Source refs and collection summaries connect processed source files to normalized metrics.
4. Report summaries expose claim traces for displayed numeric summaries and diagnostic statements.
5. Slide summaries expose per-slide source evidence or explicit unknown/diagnostic reasons.
6. Package export includes traceability evidence when available while preserving Stage 2 omissions.
7. Default CLI summaries, V2 responses, and MCP responses do not include full logs, full raw rows, report bodies, PPT contents, worker prompt/response bodies, or artifact bytes.
8. Deleting `.lab-sidecar/index.sqlite` does not prevent inspection of core task-local provenance files.
9. No-invention regression tests cover missing values, failed/cancelled tasks, and unsupported comparisons.
10. Stage 1 navigation, Stage 2 package export, Stage 3 messy-result collection, and Stage 4 bounded host delegation tests do not regress.
11. README and CLI spec document the provenance/traceability contract without overclaiming scientific interpretation.
12. `docs/post-open-source-stage-5-acceptance.md` records implementation scope, changed files, commands, workspace, task ids, generated artifacts, traceability evidence, omitted-contract evidence, and final judgment.

## 16. Validation Commands

Run before acceptance:

```bash
git diff --check
python -m pytest tests/test_cli_smoke.py -q
python -m pytest -q
```

If V2/MCP preview or inspect behavior changes, also run:

```bash
python -m pytest tests/test_v2_host_integration.py tests/test_mcp_tools.py -q
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-5-mcp-smoke
```

If plugin guidance changes, also run:

```bash
python /Users/anyuchen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
```

Manual full workflow smoke:

```bash
tmpdir="$(mktemp -d /tmp/lab-sidecar-stage-5-XXXXXX)"
cp -R examples "$tmpdir/examples"
cd "$tmpdir"
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv" --name "stage5 provenance"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-stage5
find ".lab-sidecar/tasks/<task_id>" -maxdepth 3 -type f | sort
find package-stage5 -maxdepth 3 -type f | sort
```

Manual checks should inspect:

- `.lab-sidecar/tasks/<task_id>/provenance/traceability.json` if implemented
- `metrics/collection-summary.json`
- `figures/figure-summary.json`
- `reports/report-summary.json`
- `slides/slides-summary.json`
- `package-stage5/artifact-index.json`
- `package-stage5/package-summary.json`

SQLite independence smoke:

```bash
rm .lab-sidecar/index.sqlite
python -m lab_sidecar.cli.app status <task_id>
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

## 17. Recommended Stage 5 Agent Prompt

```text
Implement Lab-Sidecar Post-Open-Source Stage 5: Provenance And Traceability.

Read docs/post-open-source-stage-5-plan.md first and treat it as the source of truth. Strengthen task-local provenance so important generated artifacts, report claims, slide evidence, and package contents can be traced back to source files, normalized metrics, figure specs, hashes, and reproduce metadata without relying on SQLite.

You are encouraged to use Codex supervisor agents and subagents when it helps parallelize independent work. Suitable subagent slices include traceability schema review, artifact hash implementation, report claim tracing, slide evidence tracing, package provenance review, V2/MCP bounded contract review, and validation. Subagents are execution coordination only; they are not Lab-Sidecar product architecture and must not introduce runtime multi-agent behavior. The supervisor remains responsible for reading all required instructions, integrating changes, preserving repository boundaries, resolving conflicts, running final validation, and writing docs/post-open-source-stage-5-acceptance.md with evidence.

Stay local-first, file-first, CLI-first, artifact-first, AI-optional, and bounded-delegation-first. Do not add Web UI, FastAPI, hosted services, remote runners, cloud sync, generic multi-agent framework behavior, automatic command interception, default AI analysis, statistical significance claims, model ranking, or unbounded artifact/file reading. Keep MCP a thin adapter over local contracts. Do not copy raw source files, full logs, worker audit bodies, sandbox files, SQLite, or unrelated workspace files into packages by default. Do not revert unrelated local changes.

Add focused tests, update README/docs where needed, run git diff --check, run tests/test_cli_smoke.py -q, run the full test suite, run V2/MCP focused tests and stdio smoke if V2/MCP behavior changes, run plugin validation if plugin files change, perform a manual full workflow smoke in a temporary workspace, verify SQLite-independent task-local provenance, and finish with a clear final judgment in docs/post-open-source-stage-5-acceptance.md.
```
