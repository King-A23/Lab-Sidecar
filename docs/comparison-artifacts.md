# Comparison Artifacts

Lab-Sidecar comparison artifacts are a bounded, deterministic local workflow
for comparing two to five already-collected tasks. They extend the CLI-first,
file-first, local-first artifact path without changing task execution
semantics.

## Current Goal

The comparison workflow takes 2-5 local task ids that already have collected
metrics and creates an inspectable comparison record under `.lab-sidecar/`.
The first implementation compares shared numeric metrics using each task's
final normalized metrics row, records evidence paths and row numbers, and can
write deterministic tables, summaries, figures, reports, traceability metadata,
and a packageable comparison folder.

The workflow is intended for local descriptive comparison after:

```text
run / ingest -> collect
```

It is designed to compose with the existing artifact workflow:

```text
run / ingest -> collect -> compare --save -> validate-comparison -> package-comparison -> package-verify
```

## Non-Goals

Comparison artifacts do not add or claim:

- statistical significance tests, p-values, or confidence intervals
- automatic scientific conclusions or model superiority claims
- deployment recommendations
- cross-workspace comparisons
- remote runners
- Web UI, FastAPI, or any HTTP service
- MCP/V2 schema expansion
- default AI analysis
- full log reads or full log embedding
- copying raw source files into comparison packages
- recursive workspace scanning

Reports and slides generated from comparison artifacts are deterministic
templates. They remain descriptive only.

## Inputs

The required inputs are:

- 2-5 task ids in the current workspace
- each task must have `metrics/normalized_metrics.csv`
- each metrics file must contain at least one row

The comparison may read bounded task-local metadata:

- `manifest.json`
- `metrics/normalized_metrics.csv`
- `metrics/scenario-summary.json`
- `metrics/collection-summary.json`
- existing artifact metadata

The first implementation compares shared numeric fields only. Metadata and
identity fields such as `source_file`, `source_path`, `file`, `path`, `epoch`,
`step`, `iter`, `iteration`, `checkpoint`, `ckpt`, `timestamp`, `seed`,
`trial`, `run_id`, and `config_id` are not treated as comparison metrics. Row
selection is `final_row`. Future work may add a descriptive `best_row` option,
but it must remain bounded and non-interpretive.

## Outputs

A saved comparison writes:

```text
.lab-sidecar/comparisons/<comparison_id>/
  comparison-manifest.json
  comparison-summary.json
  comparison-table.csv
  comparison-table.json
  figures/
    comparison_<metric>.png
    comparison_<metric>.svg
    figure-summary.json
  reports/
    comparison-report-fragment.md
    comparison-report-summary.json
  provenance/
    traceability.json
```

Static PPTX comparison decks are deferred. They can be added later as
`slides/comparison-presentation-draft.pptx` and `slides/slides-summary.json`
if they can reuse the same bounded evidence contract without broadening the
active scope.

## Bounded Contract

Comparison summaries and traceability records must not embed complete source
metric rows, full stdout/stderr logs, report bodies, PPTX contents, raw source
files, worker prompt/response bodies, SQLite indexes, or unrelated workspace
files.

The comparison summary records:

- `schema_version`
- `comparison_id`
- `created_at`
- `name`
- `task_ids`
- source task metadata
- source metric artifact paths, sizes, and hashes
- common numeric fields
- skipped fields and reasons
- `row_selection`
- bounded metric values from selected rows
- descriptive `best_by_metric` entries
- warnings and omissions
- evidence paths

`best_by_metric` is descriptive sorting only. It must not claim statistical
significance, causal improvement, model superiority, or deployment readiness.

Packages copy comparison outputs and required comparison metadata only. They do
not copy source task logs, source task raw files, source tasks' full normalized
metrics tables, SQLite, worker audit folders, worker prompt/response bodies,
sandbox files, or unrelated workspace files.

## Artifact Layout Decision

Comparison artifacts use independent records under:

```text
.lab-sidecar/comparisons/<comparison_id>/
```

This is smaller and safer than representing a comparison as a special task.
Current task records model `run` and `ingest` lifecycle semantics, including
stdout/stderr paths, runner status handling, SQLite task rows, package type
logic, and task validation assumptions. A comparison is a derived cross-task
artifact, not an executed or ingested experiment. Keeping it separate avoids
expanding `TaskRecord.mode`, avoids making comparisons look like successful
runs, and preserves the existing task path.

The tradeoff is that comparison validation and packaging need small
comparison-specific commands:

```text
labsidecar list-comparisons
labsidecar open-comparison <comparison_id>
labsidecar comparison-artifacts <comparison_id>
labsidecar validate-comparison <comparison_id>
labsidecar package-comparison <comparison_id> --output <dir>
```

`labsidecar package-verify <package_dir>` remains reusable because package
verification checks the package artifact index rather than task semantics.

The discovery commands are read-only navigation helpers for existing saved
comparison records. They do not create artifacts, do not refresh manifests, do
not read full comparison tables, do not read report bodies, do not read source
task logs, and are not exposed through MCP/V2. They preserve the current
comparison scope: descriptive `final_row` shared finite numeric metrics only,
with no statistical significance testing and no model superiority claims.

## Example

Create two collected tasks, then save and package a comparison:

```bash
python -m lab_sidecar.cli.app init

python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv" --name baseline
export TASK_ID_A=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID_A"

python -m lab_sidecar.cli.app ingest examples/csv-comparison --name model-a
export TASK_ID_B=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID_B"

python -m lab_sidecar.cli.app compare "$TASK_ID_A" "$TASK_ID_B" --save --name "baseline-vs-model-a" --figures --report
export COMPARISON_ID=<printed_comparison_id>

python -m lab_sidecar.cli.app list-comparisons
python -m lab_sidecar.cli.app comparison-artifacts "$COMPARISON_ID"
python -m lab_sidecar.cli.app open-comparison "$COMPARISON_ID"
python -m lab_sidecar.cli.app validate-comparison "$COMPARISON_ID" --require figures --require report --require package-ready
python -m lab_sidecar.cli.app package-comparison "$COMPARISON_ID" --output "lab-sidecar-comparison-$COMPARISON_ID"
python -m lab_sidecar.cli.app package-verify "lab-sidecar-comparison-$COMPARISON_ID"
```

The resulting comparison folder is:

```text
.lab-sidecar/comparisons/$COMPARISON_ID/
  comparison-manifest.json
  comparison-summary.json
  comparison-table.csv
  comparison-table.json
  figures/
    figure-summary.json
    comparison_<metric>.png
    comparison_<metric>.svg
  reports/
    comparison-report-fragment.md
    comparison-report-summary.json
  provenance/
    traceability.json
```

If the selected tasks do not share numeric final-row metrics, the command
fails with an actionable message instead of writing a partial comparison.
