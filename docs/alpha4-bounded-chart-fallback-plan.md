# Alpha4 Bounded Chart Fallback Plan

Date: 2026-06-20

## Purpose

Alpha4 should turn the current Data-to-Chart foundation into a bounded intelligent
fallback path for chart tasks that exceed deterministic figure support.

The product goal is:

```text
deterministic figures first
  -> bounded fallback request when unsupported
  -> worker/subagent proposal or artifact
  -> deterministic validator
  -> adopt only validated outputs as official sidecar artifacts
```

This is a good Alpha4 target because Alpha3/benchmark work already established
bounded summaries, traceability, context reduction measurement, and deterministic
chart scoring. Alpha4 should preserve those boundaries while allowing Lab-Sidecar
to handle more real chart requests without exposing full raw tables to the main
agent.

## Product Boundaries

Alpha4 remains local-first, file-first, CLI-first, and artifact-first.

In scope:

- figure fallback when deterministic auto-planning refuses or cannot express a
  requested chart;
- bounded input bundles for chart planning;
- worker/subagent-produced figure proposals or sandboxed image artifacts;
- deterministic validation of fields, paths, chart intent, visual outputs,
  traceability, and boundedness;
- adoption records for accepted fallback outputs;
- CLI-visible diagnostics for refused, rejected, and adopted fallback attempts;
- benchmark coverage that proves fallback adds chart coverage without raw-table
  exposure.

Out of scope:

- Web UI, hosted service, FastAPI, remote runner, or cloud sync;
- general multi-agent orchestration;
- automatic upload of raw logs, raw metric tables, or source files to an AI
  provider;
- allowing workers to write directly into official `figures/`, `metrics/`,
  `reports/`, `slides/`, or `manifest.json`;
- trusting worker claims, captions, or data transformations without validator
  checks;
- replacing deterministic `line`, `bar`, and `box` generation where those are
  sufficient.

## Architecture

### Runtime Flow

```text
labsidecar figures <task_id>
  -> deterministic figure planner
  -> if supported: render official PNG/SVG as today
  -> if unsupported and fallback enabled:
       build bounded figure request bundle
       create intelligence/<worker_run_id>/sandbox/
       invoke configured chart worker/subagent
       collect proposal/artifact outputs from sandbox
       validate proposal and visual artifacts
       adopt accepted outputs into figures/
       write fallback summary and adoption record
  -> refresh manifest and provenance
```

### Files

Fallback runs should live under:

```text
.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/
  input-bundle.json
  figure-request.json
  worker-instructions.md
  response.json
  proposal.yaml
  validator-result.json
  adoption-record.json
  diagnostics.md
  sandbox/
```

Official adopted outputs still live under:

```text
figures/
  <figure_id>.png
  <figure_id>.svg
  figure-spec.yaml
  figure-summary.json
provenance/
  traceability.json
```

## Key Design Requirements

- The deterministic planner remains the first path.
- Fallback is opt-in at first, for example `labsidecar figures <task_id> --fallback bounded`.
- The fallback bundle must contain only bounded context:
  - task id/status/mode;
  - normalized metric columns;
  - row count;
  - units/groups/field source mappings;
  - small sampled rows or aggregate sketches only when bounded;
  - collection warnings/errors/skipped candidates;
  - explicit user chart request, if provided;
  - artifact paths and hashes, not bodies.
- The bundle must not contain:
  - full raw source files;
  - full `metrics/normalized_metrics.csv` or JSON rows;
  - full stdout/stderr;
  - report bodies;
  - PPTX internals;
  - worker prompt/response bodies in main-agent responses.
- Workers may write only inside their sandbox.
- Validators decide whether a fallback output can be adopted.
- Adoption must copy or render sanitized outputs into official `figures/` and
  record source lineage back to the bounded request, proposal, and relevant
  metric fields.
- Rejected fallback attempts must leave diagnostics but must not modify official
  figures, manifest artifacts, or traceability except for bounded diagnostic
  records.

## Implementation Phases

### Phase 4.1: Fallback Request And Diagnostics

Goal: make unsupported chart needs first-class and inspectable without invoking
workers.

Implementation:

- Add a structured unsupported-chart diagnostic to `figure-summary.json` with
  requested chart intent, available fields, reason, and safe next action.
- Add `figure-request.json` builder from collection/figure summaries and explicit
  user specs.
- Add CLI flag shape, initially non-executing:
  - `--fallback off` default;
  - `--fallback bounded` allowed but returns a clear unavailable-worker diagnostic.
- Ensure diagnostics are bounded and traceable.

Tests:

- Unsupported explicit chart request writes bounded diagnostics.
- `figure-request.json` excludes raw rows and raw files.
- Existing deterministic `line`, `bar`, and `box` behavior is unchanged.

### Phase 4.2: Chart Worker Contract And Sandbox

Goal: define and enforce the worker/subagent contract.

Implementation:

- Add chart-worker invocation under `intelligence/<worker_run_id>/sandbox/`.
- Support a local heuristic/mock worker first for tests.
- Define accepted proposal shape:
  - `proposal_type: figure_fallback`;
  - `figure_id`, `chart_type`, `title`, `x`, `y`, optional `group_by`;
  - `source_metrics_fields`;
  - output paths inside sandbox;
  - explanation of unsupported deterministic path;
  - no raw row payloads.
- Keep AI/provider usage optional and disabled unless explicitly configured.

Tests:

- Worker receives only bounded bundle content.
- Sandbox escape writes/paths are rejected.
- Worker unavailable leaves deterministic diagnostics and no official changes.

### Phase 4.3: Validator And Adoption

Goal: safely adopt only validated fallback outputs.

Implementation:

- Validate field references against normalized metrics columns and configured
  field mappings.
- Validate output paths stay inside sandbox before adoption and official
  `figures/` after adoption.
- Validate PNG/SVG:
  - exists;
  - nonblank;
  - parseable SVG;
  - minimum dimensions;
  - no obvious clipping via tolerant image checks.
- Validate traceability:
  - source metrics path;
  - fields used;
  - field source mappings;
  - worker run id;
  - adoption record.
- Copy accepted outputs into official `figures/`, update `figure-summary.json`,
  `figure-spec.yaml`, manifest artifacts, and `provenance/traceability.json`.
- Rejected outputs stay in sandbox with diagnostics only.

Tests:

- Accepted fallback artifact becomes official figure artifact.
- Rejected malformed image is not adopted.
- Rejected missing-field proposal is not adopted.
- Traceability includes fallback lineage and bounded evidence only.

### Phase 4.4: Data-to-Chart Benchmark Extension

Goal: prove Alpha4 improves chart coverage while preserving boundedness.

Implementation:

- Extend `scripts/data_to_chart_benchmark.py` with unsupported/fallback scenarios:
  - scatter/correlation;
  - heatmap/confusion matrix;
  - histogram/distribution;
  - stacked/category composition or equivalent real chart request.
- Score deterministic-only vs fallback-enabled arms:
  - chart coverage;
  - correct fields;
  - visual validity;
  - traceability;
  - sidecar boundedness;
  - raw vs sidecar context reduction.
- Write:
  - `docs/alpha4-bounded-chart-fallback-benchmark.md`
  - `docs/alpha4-bounded-chart-fallback-benchmark-data.json`

Acceptance:

- Deterministic path continues to pass existing Data-to-Chart benchmark.
- Fallback-enabled path passes added unsupported chart scenarios.
- No sidecar raw metric rows or raw source bodies are exposed.
- Context reduction remains positive on full-scale benchmark fixtures.

### Phase 4.5: Documentation And Operator UX

Goal: make fallback understandable and controllable.

Implementation:

- Update CLI docs with fallback mode and boundedness contract.
- Document when fallback is attempted, skipped, rejected, or adopted.
- Add examples for safe unsupported chart requests.
- Add troubleshooting notes:
  - worker unavailable;
  - unsupported output;
  - missing fields;
  - visual validation failure;
  - bounded context limitations.

## Public Interfaces

Initial CLI shape:

```bash
labsidecar figures <task_id>
labsidecar figures <task_id> --spec figure.yaml
labsidecar figures <task_id> --fallback bounded
labsidecar figures <task_id> --spec figure.yaml --fallback bounded
```

Summary additions:

```json
{
  "fallback": {
    "mode": "off|bounded",
    "attempted": true,
    "worker_run_id": "worker_...",
    "status": "not_needed|unavailable|rejected|adopted",
    "request_path": "intelligence/<worker_run_id>/figure-request.json",
    "validator_result_path": "intelligence/<worker_run_id>/validator-result.json",
    "adoption_record_path": "intelligence/<worker_run_id>/adoption-record.json"
  }
}
```

Adopted figure summary additions:

```json
{
  "figure_id": "fallback_heatmap_confusion_matrix",
  "chart_type": "heatmap",
  "source": "fallback",
  "worker_run_id": "worker_...",
  "x": "predicted_class",
  "y": "true_class",
  "group_by": null,
  "field_sources": {
    "predicted_class": ["raw_pred"],
    "true_class": ["raw_true"]
  },
  "validation": {
    "status": "passed",
    "checks": ["fields", "paths", "visual", "traceability", "boundedness"]
  }
}
```

## Acceptance Criteria

Alpha4 is accepted only if:

- existing deterministic CLI workflows and tests still pass;
- deterministic Data-to-Chart Benchmark remains green;
- fallback can be enabled explicitly and is off by default;
- unsupported chart requests produce bounded diagnostics without fallback;
- fallback worker receives only bounded request bundles;
- sandbox escape attempts are rejected;
- malformed, blank, clipped, missing-field, or path-escaping outputs are not
  adopted;
- valid fallback outputs are adopted into official figures and manifest
  artifacts;
- `provenance/traceability.json` records fallback lineage without raw row bodies;
- benchmark data proves no full raw tables/logs/source files entered sidecar
  main-agent context;
- docs explain limitations and operator controls.

Recommended final validation:

```bash
.venv/bin/python -m pytest
.venv/bin/python scripts/data_to_chart_benchmark.py --scale smoke --benchmark-root /private/tmp/lab-sidecar-data-to-chart-smoke-alpha4
.venv/bin/python scripts/data_to_chart_benchmark.py --scale full --benchmark-root /private/tmp/lab-sidecar-data-to-chart-full-alpha4 --write-docs
.venv/bin/python scripts/alpha4_bounded_chart_fallback_benchmark.py --scale full --write-docs
python -m json.tool docs/alpha4-bounded-chart-fallback-benchmark-data.json >/dev/null
git diff --check
find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha4-*' \) -print
```

## Risks And Defaults

- Risk: fallback becomes a general agent framework.
  - Default: keep fallback scoped to figures and chart artifacts only.
- Risk: worker leaks raw data into responses or summaries.
  - Default: validators and tests search for sentinel raw-only fields; main
    responses use bounded paths and metadata only.
- Risk: worker-generated visuals are pretty but untraceable.
  - Default: adoption requires field, path, source, and visual validation.
- Risk: unsupported chart support weakens deterministic reliability.
  - Default: deterministic planner remains first and fallback is opt-in.
- Risk: AI dependency makes local workflows brittle.
  - Default: local/mock worker first; AI provider optional and explicitly
    configured.

## Recommended First Implementation Goal

```text
Implement Alpha4 Phase 4.1 for Lab-Sidecar. Add bounded unsupported-chart
diagnostics and figure-request bundle generation for `labsidecar figures`, with
`--fallback off|bounded` CLI shape but no real worker adoption yet. Preserve all
existing deterministic figure behavior and finish with tests plus an acceptance
record.
```
