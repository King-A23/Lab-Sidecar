# project-presentation-pack

Course project presentation fixture for the public alpha demo.

## Files

- `weekly_metrics.csv`: weekly model metrics for trend-style artifacts.
- `final_metrics.csv`: final model comparison metrics.
- `ablation.json`: ablation results with accuracy and latency values.
- `project_goal.md`: project goal and presentation background.

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app ingest examples/project-presentation-pack
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID" --template zh-project
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
```

Replace `<printed_task_id>` with the id printed by `ingest`.

Expected result: normalized metrics from the CSV and JSON files, deterministic
figures, `reports/report-fragment.md`, `slides/presentation-draft.pptx`, and
`slides/slides-summary.json`.

Data note: `transformer_small_aug` has the highest final accuracy (`0.884`).
The ablation data shows augmentation as the largest single accuracy gain, and
the quantized variant reduces latency while staying above the original
`transformer_small` baseline accuracy.
