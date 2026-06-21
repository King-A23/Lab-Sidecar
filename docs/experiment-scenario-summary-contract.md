# Experiment Scenario Summary Contract

`metrics/scenario-summary.json` is a bounded task-local summary produced after
metrics collection.

## Purpose

The file gives a main AI agent enough experiment-level structure to continue
reasoning without reading complete metric tables or logs.

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

## Boundedness Rules

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

## Interpretation Rules

`seed_aggregates` are descriptive aggregates only. They do not prove statistical
significance, research correctness, model superiority, or scientific claims.

Report and slide templates may cite scenario type, primary metric, best rows,
last rows, and aggregate summaries only as recorded artifact evidence.

