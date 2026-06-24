# Recipe Gallery

These recipes use checked-in examples and keep the main Lab-Sidecar path local,
file-first, and CLI-first. They create deterministic artifacts that a human can
inspect, redact, package, and accept or reject.

Every recipe is descriptive only. Lab-Sidecar does not generate AI conclusions,
run statistical significance tests, judge model superiority, write paper
conclusions, or recommend deployment decisions.

## Recipe 1: Local Training Run To Package

User scenario: you have a local training command that writes CSV metrics and
you want a shareable package with metrics, figures, report text, and an editable
deck.

Commands:

```bash
labsidecar init
labsidecar doctor
labsidecar run "python examples/simple-success/train.py --output metrics.csv"
export TASK_ID=<printed_task_id>
labsidecar collect "$TASK_ID"
labsidecar figures "$TASK_ID"
labsidecar report "$TASK_ID"
labsidecar slides "$TASK_ID"
labsidecar validate "$TASK_ID"
labsidecar package "$TASK_ID" --output "lab-sidecar-package-$TASK_ID"
labsidecar package-verify "lab-sidecar-package-$TASK_ID"
```

Expected output:

- task record under `.lab-sidecar/tasks/$TASK_ID/`
- normalized metrics under `metrics/`
- deterministic PNG/SVG figures under `figures/`
- Markdown report fragment under `reports/`
- editable PPTX draft under `slides/`
- task-local traceability under `provenance/`
- verified package directory named `lab-sidecar-package-$TASK_ID`

Next step:

```bash
labsidecar open "$TASK_ID"
labsidecar artifacts "$TASK_ID"
```

Common failures and fixes:

- `collect` cannot find metrics: make sure the command wrote CSV or JSON inside
  the task workspace.
- `figures` says required fields are missing: inspect
  `metrics/collection-summary.json` and use explicit `collect --config` for
  non-standard field names.
- `package-verify` rejects unexpected files: recreate the package in a new
  empty output directory.

This recipe does not infer statistical significance, model superiority, or an
AI-authored conclusion from the final metrics.

## Recipe 2: Ingest Messy CSV Or JSON Results

User scenario: you already have local result files with mixed column names,
nested JSON fields, skipped debug files, or unit diagnostics. You want explicit
collection rather than broad recursive workspace scanning.

Messy CSV commands:

```bash
labsidecar init
labsidecar ingest examples/messy-csv-results
export TASK_ID=<printed_task_id>
labsidecar collect "$TASK_ID" --config examples/messy-csv-results/metrics.yaml
labsidecar figures "$TASK_ID"
labsidecar report "$TASK_ID"
labsidecar slides "$TASK_ID"
labsidecar validate "$TASK_ID"
```

JSON benchmark commands:

```bash
labsidecar ingest examples/json-benchmark-results
export TASK_ID=<printed_task_id>
labsidecar collect "$TASK_ID" --config examples/json-benchmark-results/metrics.yaml
labsidecar figures "$TASK_ID"
labsidecar report "$TASK_ID"
labsidecar slides "$TASK_ID"
labsidecar validate "$TASK_ID"
```

Expected output:

- `metrics/normalized_metrics.csv`
- `metrics/collection-summary.json` with selected sources, skipped files,
  alias matches, warnings, and unit diagnostics
- deterministic figures, report fragment, slide draft, and traceability when
  the collected metrics support them

Next step:

```bash
labsidecar package "$TASK_ID" --output "lab-sidecar-package-$TASK_ID"
labsidecar package-verify "lab-sidecar-package-$TASK_ID"
```

Common failures and fixes:

- A configured source is missing: check the path relative to the current
  workspace and the ingested source root.
- A file is skipped as outside source refs: for ingested tasks, configured
  sources must stay under the ingested source.
- A mapped field is missing: add an alias under the target field in the YAML
  config.
- Unit diagnostics mention `runtime_s` and `runtime_ms`: Lab-Sidecar records
  the conflict but does not automatically convert units.

This recipe does not add TensorBoard, MLflow, JSONL parsing, broad recursive
workspace scanning, statistical significance, or model-superiority judgment.

## Recipe 3: Compare Two Tasks And Package The Comparison

User scenario: you have two to five already-collected local tasks and want a
bounded descriptive comparison package.

Create two collected tasks from the checked-in CSV fixture:

```bash
labsidecar init
labsidecar ingest examples/csv-comparison/baseline.csv --name baseline
export TASK_A=<printed_task_id>
labsidecar collect "$TASK_A"
labsidecar ingest examples/csv-comparison/model_a.csv --name model-a
export TASK_B=<printed_task_id>
labsidecar collect "$TASK_B"
```

Save and package the comparison:

```bash
labsidecar compare "$TASK_A" "$TASK_B" --save --name "baseline-vs-model-a" --figures --report
export COMPARISON_ID=<printed_comparison_id>
labsidecar validate-comparison "$COMPARISON_ID" --require figures --require report --require package-ready
labsidecar package-comparison "$COMPARISON_ID" --output "lab-sidecar-comparison-$COMPARISON_ID"
labsidecar package-verify "lab-sidecar-comparison-$COMPARISON_ID"
```

Expected output:

- saved comparison record under `.lab-sidecar/comparisons/$COMPARISON_ID/`
- `comparison-summary.json`
- `comparison-table.csv` and `comparison-table.json`
- optional comparison figures under `figures/`
- optional comparison report under `reports/`
- comparison traceability under `provenance/`
- verified comparison package directory

Next step:

```bash
labsidecar list-comparisons
labsidecar comparison-artifacts "$COMPARISON_ID"
labsidecar open-comparison "$COMPARISON_ID"
```

Common failures and fixes:

- Metrics are missing: run `labsidecar collect <task_id>` for each source task.
- There are no common numeric fields: compare tasks with shared numeric metric
  columns.
- Too many tasks are supplied: saved comparison supports two to five local
  tasks.
- `validate-comparison` reports stale source metrics: re-run the source task
  collection and save a fresh comparison.

Saved comparisons use final-row shared numeric metrics only. They do not run
statistical tests, infer model superiority, copy full source logs, or copy raw
source files into the comparison package.
