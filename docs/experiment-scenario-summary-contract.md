# Experiment Scenario Summary Contract

`metrics/scenario-summary.json` is a bounded task-local summary produced after
metrics collection.

## Purpose

The file gives a main AI agent enough experiment-level structure to continue
reasoning without reading complete metric tables or logs.

Small bounded JSON examples for `training-run` and `algorithm-benchmark` are in
[experiment-scenario-summary-examples.md](experiment-scenario-summary-examples.md).

## Shape

Required top-level fields:

- `schema_version`: currently `1`.
- `task_id`.
- `generated_at`.
- `scenario_type`: `training-run` or `algorithm-benchmark`.
- `primary_metric`: `name`, `direction`, `unit`, and `selection_reason`.
- `groups`: configured and inferred grouping fields.
- `units`.
- `best_rows`: bounded best-row references.
- `last_rows`: bounded final/checkpoint row references.
- `seed_aggregates`: descriptive per-group aggregates when a seed field exists.
- `evidence`: source files, normalized metrics path, and collection summary path.
- `omitted`: explicit omitted-content contract.
- `warnings`.

Stable values:

- `scenario_type`: `training-run` or `algorithm-benchmark`.
- `primary_metric.direction`: `max`, `min`, or `null` when no primary metric
  is detected.

Advisory values:

- `primary_metric.selection_reason` and row-level `selection_reason` explain
  deterministic name-hint selection. They are human-readable hints, not stable
  enums for downstream branching.
- `groups.configured` records user configuration metadata. It is not evidence
  that a grouping is scientifically valid.

## Boundedness Rules

Hard limits for schema version `1`:

- `best_rows`: at most 4.
- `last_rows`: at most 6.
- `seed_aggregates.items`: at most 12.
- row `selected_fields`: at most 12 scalar fields.
- `evidence.source_files`: at most 20.
- `evidence.metrics.columns`: at most 40, with `omitted_column_count`.
- each source file's `detected_fields` and `mapped_fields`: at most 40 each,
  with omitted counts.
- `units`: at most 40 entries, with `omitted_unit_count`.
- string scalar values: at most 160 characters.

The summary must not include:

- complete stdout or stderr
- complete metric rows
- full normalized JSON rows
- report bodies
- PPTX contents
- worker prompts or responses
- artifact bytes

Row evidence must use `metrics/normalized_metrics.csv`, row numbers, selected
bounded scalar fields, and `body: omitted`.

`selected_fields` is an allowlisted scalar preview of identity, checkpoint,
status, anomaly, primary metric, and known metric fields. It must not fall back
to arbitrary row columns. Free-text columns such as `notes`, `prompt`,
`message`, `error_message`, and `private_comment` may appear as column names in
bounded metadata, but their cell contents must not be copied into
`selected_fields`.

When a messy local folder contains wide tables, many files, empty files,
malformed files, non-primary numeric measurements, or mixed parseable and
non-parseable metric strings, the summary should stay bounded. Missing primary
metrics are reported as warnings and `primary_metric.name: null`; they must not
be converted into unsupported ranking, superiority, or scientific claims.

## Interpretation Rules

`seed_aggregates` are descriptive aggregates only. They do not prove statistical
significance, research correctness, model superiority, causal effects,
deployment readiness, or scientific claims.

Report and slide templates may cite scenario type, primary metric, best rows,
last rows, and aggregate summaries only as recorded artifact evidence.
