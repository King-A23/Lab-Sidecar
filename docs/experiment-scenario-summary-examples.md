# Experiment Scenario Summary Examples

These examples show the bounded shape of `metrics/scenario-summary.json`.
They are contract examples, not full output dumps. Raw rows, logs, report
bodies, slide contents, worker prompts/responses, and artifact bytes remain
omitted by default.

## Training Run

```json
{
  "schema_version": "1",
  "task_id": "task_example_training",
  "generated_at": "2026-06-22T10:00:00+08:00",
  "scenario_type": "training-run",
  "primary_metric": {
    "name": "val_accuracy",
    "direction": "max",
    "unit": "ratio",
    "selection_reason": "higher_is_better_name_hint"
  },
  "groups": {
    "configured": {},
    "primary": null,
    "secondary": null,
    "seed": null,
    "context": [],
    "inferred": []
  },
  "units": {
    "val_accuracy": "ratio"
  },
  "omitted_unit_count": 0,
  "best_rows": [
    {
      "metric": "val_accuracy",
      "direction": "max",
      "selection_reason": "higher_is_better_name_hint",
      "value": 0.86,
      "row_number": 5,
      "selected_fields": {
        "epoch": "5",
        "val_accuracy": "0.86"
      },
      "omitted_field_count": 3,
      "evidence": {
        "artifact_id": "metrics_normalized_csv",
        "path": "metrics/normalized_metrics.csv",
        "row_number": 5,
        "body": "omitted"
      }
    }
  ],
  "last_rows": [
    {
      "group": {},
      "row_number": 5,
      "checkpoint_field": "epoch",
      "selected_fields": {
        "epoch": "5",
        "val_accuracy": "0.86"
      },
      "evidence": {
        "artifact_id": "metrics_normalized_csv",
        "path": "metrics/normalized_metrics.csv",
        "row_number": 5,
        "body": "omitted"
      }
    }
  ],
  "seed_aggregates": {
    "present": false,
    "reason": "seed aggregates require a primary group, seed field, and primary metric",
    "items": []
  },
  "evidence": {
    "metrics": {
      "artifact_id": "metrics_normalized_csv",
      "path": "metrics/normalized_metrics.csv",
      "row_count": 5,
      "columns": ["source_file", "epoch", "train_loss", "val_loss", "val_accuracy"],
      "omitted_column_count": 0,
      "body": "omitted"
    },
    "collection_summary": {
      "artifact_id": "metrics_collection_summary",
      "path": "metrics/collection-summary.json",
      "candidate_count": 1,
      "processed_file_count": 1
    },
    "source_files": [
      {
        "source_file": "metrics.csv",
        "file_type": "csv",
        "row_count": 5,
        "detected_fields": ["epoch", "train_loss", "val_loss", "val_accuracy"],
        "omitted_detected_field_count": 0,
        "mapped_fields": [],
        "omitted_mapped_field_count": 0
      }
    ],
    "omitted_source_file_count": 0
  },
  "omitted": {
    "full_stdout": "omitted_by_default",
    "full_stderr": "omitted_by_default",
    "full_metric_rows": "omitted_by_default",
    "report_body": "omitted_by_default",
    "ppt_contents": "omitted_by_default",
    "worker_prompt_response": "omitted_by_default",
    "artifact_bytes": "omitted_by_default"
  },
  "warnings": [
    "scenario summary is descriptive and deterministic; it does not infer statistical significance or scientific conclusions"
  ]
}
```

## Algorithm Benchmark

```json
{
  "schema_version": "1",
  "task_id": "task_example_benchmark",
  "generated_at": "2026-06-22T10:05:00+08:00",
  "scenario_type": "algorithm-benchmark",
  "primary_metric": {
    "name": "runtime_ms",
    "direction": "min",
    "unit": "ms",
    "selection_reason": "lower_is_better_name_hint"
  },
  "groups": {
    "configured": {
      "primary": "algorithm",
      "secondary": "seed"
    },
    "primary": "algorithm",
    "secondary": "seed",
    "seed": "seed",
    "context": ["input_size"],
    "inferred": ["algorithm", "seed", "input_size"]
  },
  "units": {
    "runtime_ms": "ms",
    "memory_mb": "MB"
  },
  "omitted_unit_count": 0,
  "best_rows": [
    {
      "metric": "runtime_ms",
      "direction": "min",
      "selection_reason": "lower_is_better_name_hint",
      "value": 39.9,
      "row_number": 3,
      "selected_fields": {
        "algorithm": "candidate",
        "seed": "2",
        "input_size": "100",
        "runtime_ms": "39.9"
      },
      "omitted_field_count": 2,
      "evidence": {
        "artifact_id": "metrics_normalized_csv",
        "path": "metrics/normalized_metrics.csv",
        "row_number": 3,
        "body": "omitted"
      }
    }
  ],
  "last_rows": [
    {
      "group": {
        "algorithm": "candidate",
        "input_size": "100"
      },
      "row_number": 3,
      "checkpoint_field": null,
      "selected_fields": {
        "algorithm": "candidate",
        "seed": "2",
        "input_size": "100",
        "runtime_ms": "39.9"
      },
      "evidence": {
        "artifact_id": "metrics_normalized_csv",
        "path": "metrics/normalized_metrics.csv",
        "row_number": 3,
        "body": "omitted"
      }
    }
  ],
  "seed_aggregates": {
    "present": true,
    "metric": "runtime_ms",
    "direction": "min",
    "group_by": ["algorithm", "input_size"],
    "seed_field": "seed",
    "aggregation_scope": "last_row_per_group_seed",
    "items": [
      {
        "group": {
          "algorithm": "candidate",
          "input_size": "100"
        },
        "metric": "runtime_ms",
        "direction": "min",
        "row_count": 2,
        "seed_count": 2,
        "mean": 40.8,
        "min": 39.9,
        "max": 41.7,
        "evidence": {
          "artifact_id": "metrics_normalized_csv",
          "path": "metrics/normalized_metrics.csv",
          "row_numbers": [2, 3],
          "body": "omitted"
        }
      }
    ],
    "omitted_group_count": 0,
    "claim_limit": "descriptive aggregate only; no statistical significance is inferred"
  },
  "evidence": {
    "metrics": {
      "artifact_id": "metrics_normalized_csv",
      "path": "metrics/normalized_metrics.csv",
      "row_count": 3,
      "columns": ["source_file", "algorithm", "seed", "input_size", "runtime_ms", "memory_mb"],
      "omitted_column_count": 0,
      "body": "omitted"
    },
    "collection_summary": {
      "artifact_id": "metrics_collection_summary",
      "path": "metrics/collection-summary.json",
      "candidate_count": 1,
      "processed_file_count": 1
    },
    "source_files": [
      {
        "source_file": "nested-results/results.json",
        "file_type": "json",
        "row_count": 3,
        "detected_fields": ["algorithm", "seed", "input_size", "runtime_ms", "memory_mb"],
        "omitted_detected_field_count": 0,
        "mapped_fields": ["algorithm", "seed", "input_size", "runtime_ms", "memory_mb"],
        "omitted_mapped_field_count": 0
      }
    ],
    "omitted_source_file_count": 0
  },
  "omitted": {
    "full_stdout": "omitted_by_default",
    "full_stderr": "omitted_by_default",
    "full_metric_rows": "omitted_by_default",
    "report_body": "omitted_by_default",
    "ppt_contents": "omitted_by_default",
    "worker_prompt_response": "omitted_by_default",
    "artifact_bytes": "omitted_by_default"
  },
  "warnings": [
    "scenario summary is descriptive and deterministic; it does not infer statistical significance or scientific conclusions"
  ]
}
```
