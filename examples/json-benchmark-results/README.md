# json-benchmark-results

Small real-ish JSON benchmark fixture for explicit `collect --config`
diagnostics.

## Files

- `results.json`: benchmark records with nested `metrics` fields for multiple
  methods, input cases, and seeds.
- `extra/skipped-records.json`: a JSON list containing one valid object and one
  non-object item. Collection records a bounded warning for the skipped
  non-object item.
- `debug/debug.json`: matched by the include patterns but excluded by config.
- `metrics.yaml`: explicit source, alias, unit, and group config.

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app ingest examples/json-benchmark-results
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID" --config examples/json-benchmark-results/metrics.yaml
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app validate "$TASK_ID"
```

Expected result: normalized benchmark metrics include `method`, `case`,
`seed`, `accuracy`, `runtime_ms`, `error_rate`, `status`, `warning_flag`, and
`artifact_present`. Failed or partial benchmark records remain descriptive
diagnostic rows; Lab-Sidecar does not infer statistical significance or model
superiority.
