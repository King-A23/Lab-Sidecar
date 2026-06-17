# simple-failure

Minimal failed-run fixture for public alpha diagnostics.

## Files

- `fail.py`: deterministic script that exits with code `1`.
- `stderr-example.log`: expected stderr content for manual comparison.

## Direct Run

From this directory:

```bash
python fail.py
```

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app run "python examples/simple-failure/fail.py"
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app status "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
```

Replace `<printed_task_id>` with the id printed by `run`.

Expected result: task status `failed`, exit code `1`, preserved stderr, a
bounded failure summary in `manifest.json`, and diagnostic report/PPTX artifacts
under `.lab-sidecar/tasks/$TASK_ID/`.
