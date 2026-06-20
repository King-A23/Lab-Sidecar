# Alpha4 Bounded Chart Fallback Benchmark

Date: 2026-06-20

## Methodology

This benchmark creates fallback-only chart requests that deterministic `line`, `bar`, and `box` planning intentionally does not cover. Each scenario is run twice: first with fallback off to confirm deterministic refusal, then with `--fallback bounded --fallback-worker mock` to validate and adopt a sandboxed fallback artifact.

The sidecar arm reads only bounded task-local summaries, fallback request metadata, validator results, adoption records, and traceability. It does not read full raw source files, full normalized metric rows, full logs, worker prompt/response bodies, or sandbox proposal bodies.

Token counts use the deterministic proxy `ceil(chars / 4)`.

## Scenario Results

| Scenario | Unsupported request | Deterministic covered | Fallback covered | Score | Passed | Context reduction |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| scatter_correlation | scatter epoch/val_accuracy/model | 0 | 1 | 11/11 | yes | 96.88% |
| heatmap_confusion_matrix | heatmap predicted_class/true_class/null | 0 | 1 | 11/11 | yes | 39.09% |
| histogram_distribution | histogram latency_ms/latency_ms/service | 0 | 1 | 11/11 | yes | 98.99% |
| stacked_category_composition | stacked_bar category/share/segment | 0 | 1 | 11/11 | yes | 99.32% |

## Aggregate

| Scenarios | Deterministic covered | Fallback covered | Coverage delta | Raw chars | Sidecar chars | Context reduction | Score | Violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 0 | 4 | 4 | 11175245 | 160489 | 98.56% | 44/44 | 0 |

## Boundedness

- Sidecar raw metric row exposure: `0` bytes.
- Sidecar violation count: `0`.
- Fallback request, validator, adoption, summary, and traceability records are included as bounded evidence.
- Worker prompt/response bodies and sandbox proposal bodies are not included in the sidecar context arm.

## Acceptance Status

Passed.

## Limitations

- The benchmark uses the local mock chart fallback worker to exercise validator and adoption mechanics; it does not evaluate an AI provider.
- Visual validation checks parseability, size, and nonblank output. It does not grade chart design quality.
- The benchmark exercises local CLI behavior only, not MCP or hosted workflows.
