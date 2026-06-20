# Data-to-Chart Benchmark

Date: 2026-06-20

## Methodology

This benchmark generates deterministic fixtures under `/private/tmp`, runs the local Lab-Sidecar CLI path, and scores generated `PNG/SVG` figures plus `figures/figure-summary.json` without reading full normalized metrics or raw source files in the sidecar arm.

Token counts use the deterministic proxy `ceil(chars / 4)`.

## Scenario Results

| Scenario | Expected | Generated | Axes | Score | Passed | Context reduction |
| --- | --- | --- | --- | ---: | --- | ---: |
| training_curve | line epoch/accuracy/split | line | epoch / accuracy / split | 7/7 | yes | 98.62% |
| multi_run_sweep | line step/val_accuracy/config_id | line | step / val_accuracy / config_id | 7/7 | yes | 99.52% |
| ablation | bar variant/accuracy/null | bar | variant / accuracy / null | 7/7 | yes | 20.92% |
| error_analysis | bar class/error_rate/split | bar | class / error_rate / split | 7/7 | yes | 50.52% |
| time_series | line timestamp/throughput_rps/service | line | timestamp / throughput_rps / service | 7/7 | yes | 98.98% |
| categorical_comparison | bar model/accuracy/dataset | bar | model / accuracy / dataset | 7/7 | yes | 44.74% |
| multi_seed_distribution | box method/accuracy/null | box | method / accuracy / null | 7/7 | yes | 98.63% |

## Aggregate

| Raw chars | Sidecar chars | Context reduction | Raw est. tokens | Sidecar est. tokens | Token reduction | Score | Violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7792146 | 120369 | 98.46% | 1948039 | 30094 | 98.46% | 49/49 | 0 |

## Acceptance Status

Passed.

Sidecar context was limited to CLI output, collection summary, figure summary, and task-local traceability. Full normalized metric rows and raw source files were not read by the benchmark sidecar arm.

## Limitations

- Token counts are a character-based proxy, not provider billing data.
- Visual validation is deterministic and catches blank or obviously clipped figures; it is not a human design review.
- The benchmark exercises local CLI behavior only, not MCP or hosted workflows.
