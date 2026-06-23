# Experiment Scenario Fixtures

## Training Run

Fixture:

```text
examples/simple-success/train.py
examples/simple-success/metrics.csv
```

CLI flow:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
```

Expected scenario summary:

- `scenario_type: training-run`
- `primary_metric.name: val_accuracy`
- `best_rows` references `metrics/normalized_metrics.csv`
- full rows and logs omitted

Bounded contract example:

- [Training run JSON example](experiment-scenario-summary-examples.md#training-run)

## Algorithm Benchmark

Fixture:

```text
examples/algorithm-benchmark/results.json
```

Use explicit config for stable field/group semantics:

```yaml
sources:
  - examples/algorithm-benchmark/results.json
fields:
  algorithm: algorithm
  seed: seed
  input_size: input_size
  runtime_ms:
    source: runtime_ms
    unit: ms
  memory_mb:
    source: memory_mb
    unit: MB
groups:
  primary: algorithm
  secondary: seed
```

Expected scenario summary:

- `scenario_type: algorithm-benchmark`
- `primary_metric.name: runtime_ms`
- `primary_metric.direction: min`
- `seed_aggregates.present: true`
- `claim_limit` says no statistical significance is inferred

Bounded contract example:

- [Algorithm benchmark JSON example](experiment-scenario-summary-examples.md#algorithm-benchmark)

## Messy Folder Reliability

Messy local folders should still resolve to the existing `training-run` or
`algorithm-benchmark` summaries. Use `collect --config` for nested JSON,
nonstandard field names, include/exclude source lists, and alias lists.

Reliability expectations:

- wide tables and many source files are summarized with explicit omitted
  counts;
- empty or malformed metric files are reported through bounded collection
  diagnostics instead of crashing;
- missing primary metrics produce warnings and `primary_metric.name: null`;
- mixed numeric strings are used when parseable and skipped when not parseable;
- free-text columns such as notes, prompts, error messages, and private
  comments are not copied into scenario row previews or V2 compact scenario
  outputs.

## V2 Delegate Example

```text
delegate_experiment_artifacts(
  workspace_path=".",
  user_goal="Collect benchmark metrics and return a bounded scenario summary.",
  result_path="examples/algorithm-benchmark",
  desired_outputs=["metrics"],
  intelligent_mode="off"
)
inspect_sidecar_task(".", task_id)
```

The default response should include `summary.outputs.scenario` when collection
produces `metrics/scenario-summary.json`.
