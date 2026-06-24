# messy-csv-results

Small real-ish CSV fixture for explicit `collect --config` diagnostics.

## Files

- `runs/baseline/seed_1/history.csv`: validation accuracy/loss with
  `val_accuracy`, `val_loss`, `trial`, and `runtime_ms`.
- `runs/baseline/seed_2/history.csv`: the same shape with alias columns
  `acc`, `loss`, `seed`, and `latency_ms`.
- `runs/candidate-a/run_101/metrics.csv`: alias columns `iter`, `algo`,
  `run_id`, `score_pct`, and `time_ms`.
- `runs/candidate-b/run_201/metrics.csv`: seconds-style runtime in
  `runtime_s`; the config maps it to `latency_ms` but records a unit
  diagnostic instead of converting units.
- `runs/candidate-b/run_202/partial.csv`: intentionally missing mapped fields
  so collection can skip it with a bounded diagnostic.
- `debug/` and `scratch/`: files matched by the include patterns but excluded
  by config.
- `notes/readme.txt`: unsupported configured source used to exercise
  diagnostics.
- `metrics.yaml`: explicit source, alias, unit, and group config.

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app ingest examples/messy-csv-results
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID" --config examples/messy-csv-results/metrics.yaml
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app validate "$TASK_ID"
python -m lab_sidecar.cli.app package "$TASK_ID" --output "lab-sidecar-package-$TASK_ID"
python -m lab_sidecar.cli.app package-verify "lab-sidecar-package-$TASK_ID"
```

Expected result: normalized metrics preserve `method`, `seed`, `epoch`,
`accuracy`, `loss`, and `latency_ms`; `collection-summary.json` records
include/exclude evidence, matched aliases, skipped files, and unit diagnostics.

The data is illustrative only. Lab-Sidecar does not infer statistical
significance or model superiority from this fixture.
