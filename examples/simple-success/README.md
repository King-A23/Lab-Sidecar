# simple-success

Minimal successful run fixture for the public alpha demo.

## Files

- `train.py`: deterministic dependency-free training stand-in. It prints short
  logs and writes `metrics.csv`.
- `metrics.csv`: checked-in deterministic output for ingest/collect scenarios
  that do not need to rerun the script.

## Direct Run

From this directory:

```bash
python train.py --output metrics.csv
```

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
```

Replace `<printed_task_id>` with the id printed by `run`.

Expected result: a completed task with 5 metric rows, task-local logs,
normalized metrics, figures, a deterministic report fragment, and a static
editable PPTX draft under `.lab-sidecar/tasks/$TASK_ID/`.
