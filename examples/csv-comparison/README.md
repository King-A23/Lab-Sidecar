# csv-comparison

Multi-result CSV fixture for the public alpha comparison demo.

## Files

- `baseline.csv`
- `model_a.csv`
- `model_b.csv`

All three files use the same schema: `epoch`, `model`, `seed`,
`val_accuracy`, and `val_loss`.

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app ingest examples/csv-comparison
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
```

Replace `<printed_task_id>` with the id printed by `ingest`.

Expected result: normalized metrics from the three CSV files, source provenance
in `metrics/collection-summary.json`, comparison figures, a deterministic
report fragment, and a static editable PPTX draft.

Data note: `model_a` has the highest final `val_accuracy` in this fixture
(`0.83`), followed by `model_b` (`0.81`) and `baseline` (`0.77`).
