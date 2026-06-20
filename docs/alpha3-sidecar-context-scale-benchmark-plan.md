# Alpha3 Sidecar Context Scale Benchmark Plan

Date: 2026-06-19

## Purpose

The first Alpha3 context benchmark used tiny checked-in fixtures. It verified
context quarantine, provenance, and artifact completeness, but it did not
demonstrate context or token savings because Lab-Sidecar's bounded metadata was
larger than the raw source files.

This follow-up benchmark should use larger, more realistic experiment
workloads. The goal is not to force a positive result. The goal is to make the
raw-agent baseline face the kind of logs, metric tables, and multi-run evidence
that Lab-Sidecar is designed to quarantine, while holding both arms to the same
analysis questions and quality rubric.

## Benchmark Principle

The benchmark is fair only if:

- both arms answer the same analysis prompt;
- the raw arm can inspect raw files directly and must count every raw byte read
  as main-agent context exposure;
- the sidecar arm uses only the local CLI workflow, not MCP/V2;
- the sidecar arm must not read full logs, full normalized metrics, report
  bodies, PPTX internals, source refs, raw source files, or worker
  prompt/response bodies;
- generated temp fixtures, `.lab-sidecar` task directories, and package folders
  stay under `/private/tmp`;
- the final report states negative results plainly if sidecar still does not
  reduce measured context.

## Required Scenarios

Run at least three scenarios. Generate all large fixtures under `/private/tmp`
from deterministic scripts or inline generators. Do not add generated data,
task directories, packages, or large fixture files to the repository.

### 1. Large Training Run

Purpose: simulate one verbose model training run where raw context is dominated
by logs and metric rows.

Recommended generated inputs:

- `train_large.py`: deterministic local generator script.
- `config.json`: model, dataset, seed, optimizer, and schedule metadata.
- `stdout.log`: 5-20 MB of epoch/step logs, periodic validation summaries,
  checkpoint paths, learning-rate changes, memory/GPU-like telemetry, and
  warnings.
- `stderr.log`: 50-500 KB with benign warnings plus at least one non-fatal
  diagnostic.
- `metrics.csv`: 50,000-200,000 rows with columns such as `step`, `epoch`,
  `train_loss`, `val_loss`, `val_accuracy`, `f1`, `lr`, `duration_ms`,
  `gpu_mem_mb`, and `checkpoint`.

Analysis prompt:

```text
Summarize the run outcome, identify the best validation checkpoint, describe
metric trends and notable warnings, list expected deliverables, explain the
evidence behind every claim, and state limits or unknowns without inventing
causal conclusions.
```

Raw-arm expected exposure:

- `config.json`
- enough of `stdout.log` and `stderr.log` to answer warning and run-status
  questions; if full logs are read, count full bytes/chars;
- enough of `metrics.csv` to identify best checkpoint and trends; if the full
  table is read, count full bytes/chars.

Sidecar workflow:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python train_large.py --output metrics.csv --stdout-bytes <n>" --name "alpha3 scale large training"
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-alpha3-scale-large-training
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

### 2. Multi-Run Sweep

Purpose: simulate a hyperparameter or architecture sweep where raw context is
spread across many runs.

Recommended generated inputs:

- `sweep_manifest.json`: 50-200 runs with model, seed, learning rate, batch
  size, dataset slice, and expected artifact names.
- one metrics CSV per run, or one large `sweep_metrics.csv` with 100,000+
  rows;
- per-run logs with warnings, early stops, missing checkpoint notes, or partial
  failures;
- at least 3 intentional anomalies: missing final metric, unstable seed,
  warning-only run, or incomplete artifact.

Analysis prompt:

```text
Rank the top configurations by validation accuracy and stability, identify
outlier or incomplete runs, summarize tradeoffs between quality and runtime,
list generated or missing deliverables, cite evidence for each claim, and state
what cannot be concluded from this sweep.
```

Raw-arm expected exposure:

- the sweep manifest;
- raw metric rows across all candidate runs;
- log excerpts or full logs needed to identify anomalies and incomplete runs.

Sidecar workflow:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app ingest sweep-inputs --name "alpha3 scale multi-run sweep"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-alpha3-scale-sweep
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

### 3. Complex Project Pack

Purpose: simulate a report-and-presentation handoff with multiple evidence
types, not just a single metric table.

Recommended generated inputs:

- `project_goal.md`
- `experiment_notes.md` with 20-100 KB of dated notes;
- `weekly_metrics.csv` with 10,000+ rows;
- `final_metrics.csv` with many model variants and deployment metrics;
- `ablation.json` with nested ablation results;
- `error_analysis.csv` with class-level or subgroup metrics;
- `dataset_notes.md` with caveats, known limitations, and unsupported claims.

Analysis prompt:

```text
Prepare a concise project-readiness summary, identify the strongest supported
claims, identify claims that must not be made, summarize final model quality and
deployment tradeoffs, list report and slide deliverables, cite evidence for each
claim, and state remaining unknowns.
```

Raw-arm expected exposure:

- all source markdown, CSV, and JSON files needed to verify claims and
  limitations;
- record source bytes/chars separately for notes, metrics, ablations, and error
  analysis.

Sidecar workflow:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app ingest project-pack --name "alpha3 scale project pack"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id> --template zh-project
python -m lab_sidecar.cli.app package <task_id> --output package-alpha3-scale-project
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

## Measurement Contract

For every scenario and arm, record:

- `scenario_id`
- `arm`: `raw_agent` or `lab_sidecar`
- `workspace`
- `fixture_generation_commands`
- `task_ids`
- `commands_run`
- `files_read`
- `context_bytes`
- `context_chars`
- `estimated_context_tokens`
- `full_artifact_bodies_exposed`
- `raw_log_bytes_exposed`
- `raw_metric_row_bytes_exposed`
- `raw_notes_bytes_exposed`
- `generated_deliverables`
- `traceability_present`
- `sqlite_independent_check`
- `quality_scores`
- `violations`
- `notes`

Token estimate:

```text
estimated_context_tokens = ceil(context_chars / 4)
```

This is a deterministic proxy, not provider billing.

Aggregate calculations:

```text
context_reduction_pct = 100 * (1 - sidecar_context_chars / raw_context_chars)
token_reduction_pct = 100 * (1 - sidecar_estimated_tokens / raw_estimated_tokens)
quality_delta = sidecar_quality_total - raw_quality_total
raw_log_exposure_reduction_pct = 100 * (1 - sidecar_raw_log_bytes_exposed / raw_raw_log_bytes_exposed)
raw_metric_exposure_reduction_pct = 100 * (1 - sidecar_raw_metric_row_bytes_exposed / raw_raw_metric_row_bytes_exposed)
```

If a denominator is zero, record the reduction as `null` and explain why.

## Sidecar Read Boundary

Allowed sidecar context:

- CLI command output
- `manifest.json`
- `metrics/collection-summary.json`
- `figures/figure-summary.json`
- `reports/report-summary.json`
- `slides/slides-summary.json`
- `provenance/traceability.json`
- package `artifact-index.json`
- package `package-summary.json`

Forbidden sidecar context:

- full `stdout.log`
- full `stderr.log`
- full `metrics/normalized_metrics.csv`
- full `metrics/normalized_metrics.json`
- full `reports/report-fragment.md`
- PPTX internals or XML
- `raw/source_refs.json`
- raw source files
- worker prompt/response bodies

If any forbidden body is read by the main agent, record it as a sidecar
violation with path, bytes, chars, purpose, and reason.

## Quality Rubric

Score each category 0-2. Maximum per arm per scenario is 12.

- `metric_correctness`: key metrics, rankings, and best checkpoints are
  correct.
- `anomaly_detection`: warnings, incomplete runs, and missing artifacts are
  identified accurately.
- `deliverable_completeness`: expected reports, figures, slides, packages, and
  summaries are generated or clearly accounted for.
- `traceability`: claims point to bounded evidence and provenance.
- `boundedness`: the arm respects its context rules.
- `no_invention`: no unsupported significance, causality, deployment, or
  generalization claims are made.

## Required Output Files

Write or update only these files unless the user explicitly asks otherwise:

- `docs/alpha3-sidecar-context-scale-benchmark.md`
- `docs/alpha3-sidecar-context-scale-benchmark-data.json`

The data file should use this top-level shape:

```json
{
  "schema_version": "1",
  "date": "YYYY-MM-DD",
  "package_version": "0.1.0",
  "comparison_base": "v0.1.0-alpha.2",
  "candidate": "local main intended for v0.1.0-alpha.3",
  "benchmark_root": "/private/tmp/...",
  "token_estimate": {
    "method": "ceil(chars / 4)",
    "exact_provider_tokens_available": false
  },
  "fixture_generation": [],
  "scenarios": [],
  "aggregate": {}
}
```

The human report must include:

- title and date;
- methodology;
- fixture-generation summary;
- scenario table;
- raw vs sidecar comparison table;
- aggregate context/token comparison;
- raw log and metric exposure comparison;
- quality rubric table;
- workspaces and task ids;
- violations or omissions;
- conclusion on whether the scale benchmark demonstrates context-quarantine and
  context-reduction value;
- limitations.

## Acceptance Criteria

The scale benchmark passes only if:

- all three scenarios have raw and sidecar runs;
- generated large fixtures stay under `/private/tmp`;
- each run records context chars, estimated tokens, files read, and quality
  scores;
- sidecar reads only allowed bounded artifacts unless a violation is recorded;
- every sidecar run generates task-local `provenance/traceability.json`;
- every sidecar run generates a package with `artifact-index.json` and
  `package-summary.json`;
- SQLite-independent inspection is checked after deleting
  `.lab-sidecar/index.sqlite`;
- `docs/alpha3-sidecar-context-scale-benchmark-data.json` is valid JSON;
- `git diff --check` passes;
- no generated `.lab-sidecar` task directory, package folder, or large fixture
  file exists in the repository working tree;
- the final response reports whether acceptance passed, whether files were
  changed, aggregate context/token results, quality delta, sidecar violation
  count, temp workspace root, validation commands, and follow-up
  recommendations.

## Recommended Validation Commands

```bash
python -m json.tool docs/alpha3-sidecar-context-scale-benchmark-data.json >/dev/null
git diff --check
find . -path ./.git -prune -o \( -name .lab-sidecar -o -name 'package-alpha3-scale-*' \) -print
```

Also run a custom validation script that verifies:

- required top-level JSON keys;
- exactly three scenarios;
- raw and sidecar arms for every scenario;
- token formula consistency;
- aggregate formula consistency;
- sidecar file-read allowlist;
- traceability/package existence in temp workspaces;
- post-delete SQLite-independent `summarize` and `artifacts` success.

## New Agent Goal Prompt

Use the following prompt for a fresh agent:

```text
/goal Strictly read and execute docs/alpha3-sidecar-context-scale-benchmark-plan.md in <repo>.

Run a new large-scale Alpha3 sidecar context benchmark with deterministic large fixtures generated only under /private/tmp. Compare the same three analysis tasks with and without Lab-Sidecar:

1. Large Training Run
2. Multi-Run Sweep
3. Complex Project Pack

Use local CLI execution only, not MCP/V2. Use <python> when invoking Lab-Sidecar. The raw-agent arm may inspect generated raw files directly and must record every file read as main-agent context exposure. The Lab-Sidecar arm must not read full stdout/stderr logs, full normalized metrics, report bodies, PPTX internals/XML, raw/source_refs.json, raw source files, or worker prompt/response bodies. If it does, record a sidecar violation.

Write or update only:

- docs/alpha3-sidecar-context-scale-benchmark.md
- docs/alpha3-sidecar-context-scale-benchmark-data.json

Do not commit, push, tag, publish, or modify product code. Do not add generated fixture files, .lab-sidecar task directories, package folders, or /private/tmp artifacts to the repository. If you discover a product bug, record it in the final report and stop before mixing benchmark documentation with implementation fixes.

Acceptance requires all three scenarios to have raw and sidecar runs, valid JSON data, reproducible aggregate formulas, task-local traceability, package artifact-index/package-summary files, SQLite-independent inspection after deleting .lab-sidecar/index.sqlite, git diff --check passing, and no generated .lab-sidecar/package/large fixture artifacts in the repository working tree.

Final response must report:

- whether benchmark acceptance passed;
- whether files were changed;
- aggregate raw vs sidecar context chars and estimated tokens;
- context/token reduction percentages;
- raw log and raw metric exposure reduction;
- quality delta;
- sidecar violation count;
- temp workspace root(s);
- validation commands run;
- limitations and follow-up recommendations.
```
