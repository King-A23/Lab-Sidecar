# algorithm-benchmark

JSON benchmark fixture for algorithm comparison demos.

## Files

- `results.json`: sorting benchmark results for `quick_sort`, `merge_sort`,
  and `heap_sort` across two input sizes and three seeds.

## Lab-Sidecar Demo Flow

From a repository root or copied demo workspace root:

```bash
python -m lab_sidecar.cli.app ingest examples/algorithm-benchmark
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
```

Replace `<printed_task_id>` with the id printed by `ingest`.

Expected result: a normalized benchmark table containing `algorithm`,
`input_size`, `seed`, `runtime_ms`, and `memory_mb`, plus at least one
runtime-oriented figure, a report fragment, and a static editable PPTX draft
when the standard alpha pipeline is run.

Data note: in the checked-in data, `quick_sort` has the lowest runtime,
`merge_sort` is second, and `heap_sort` uses less memory than `merge_sort`.
