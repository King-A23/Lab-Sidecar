# Alpha3 Sidecar Context Scale Benchmark

Date: 2026-06-19

## Methodology

This benchmark reruns the three large-scale Alpha3 analysis prompts with deterministic fixtures generated only under `/private/tmp`. The raw-agent arm reads generated raw files directly and counts every byte/character read as main-agent context exposure. The Lab-Sidecar arm uses only the local CLI workflow with `<python>` and reads only bounded CLI output plus allowed metadata artifacts.

The token estimate is the deterministic proxy `ceil(context_chars / 4)`. It is not provider billing data.

Sidecar allowed reads were limited to `manifest.json`, collection/figure/report/slides summaries, `provenance/traceability.json`, and package `artifact-index.json` / `package-summary.json`. Full logs, normalized metric bodies, report bodies, PPTX internals, `raw/source_refs.json`, raw source files, and worker prompt/response bodies were not read by the main agent.

## Fixture Generation

| Scenario | Workspace roots | Deterministic scale |
| --- | --- | --- |
| large_training_run | <benchmark-root>/raw-large-training<br><benchmark-root>/sidecar-large-training | rows=60000, stdout_target_bytes=5600000, stderr_warning_lines=700, random_seed=None |
| multi_run_sweep | <benchmark-root>/raw-sweep<br><benchmark-root>/sidecar-sweep | runs=80, configs=20, steps_per_run=1250, metric_rows=100000, intentional_anomalies=['missing_final_metric', 'unstable_seed', 'warning_only', 'incomplete_artifact'] |
| complex_project_pack | <benchmark-root>/raw-project<br><benchmark-root>/sidecar-project | weekly_metric_rows=12000, final_metric_rows=240, error_analysis_rows=480, experiment_notes_bytes=20-100 KB deterministic notes, dataset_notes_bytes=deterministic caveat notes |

## Scenario Results

| Scenario | Raw chars | Sidecar chars | Context reduction | Raw est. tokens | Sidecar est. tokens | Token reduction | Quality delta | Traceability | Package metadata | SQLite-independent check |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| Large Training Run | 10544598 | 164019 | 98.44% | 2636150 | 41005 | 98.44% | 2 | yes | yes | yes |
| Multi-Run Sweep | 13273482 | 198486 | 98.50% | 3318371 | 49622 | 98.50% | 2 | yes | yes | yes |
| Complex Project Pack | 844652 | 162539 | 80.76% | 211163 | 40635 | 80.76% | 2 | yes | yes | yes |

## Raw Vs Sidecar Comparison

| Scenario | Arm | Context chars | Estimated tokens | Quality | Raw log bytes exposed | Raw metric bytes exposed | Raw notes bytes exposed | Deliverables |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Large Training Run | raw_agent | 10544598 | 2636150 | 10 | 5684964 | 4859335 | 0 | raw_analysis_summary.md |
| Large Training Run | lab_sidecar | 164019 | 41005 | 12 | 0 | 0 | 0 | README.md, artifact-index.json, figures/figure-spec.yaml, figures/figure-summary.json, figures/line_train_loss_over_epoch.png, figures/line_train_loss_over_epoch.svg, figures/line_val_accuracy_over_epoch.png, figures/line_val_accuracy_over_epoch.svg, manifest.json, metrics/collection-summary.json, metrics/normalized_metrics.csv, metrics/normalized_metrics.json, package-summary.json, provenance/traceability.json ... (+9 more) |
| Multi-Run Sweep | raw_agent | 13273482 | 3318371 | 10 | 170312 | 13074263 | 0 | raw_analysis_summary.md |
| Multi-Run Sweep | lab_sidecar | 198486 | 49622 | 12 | 0 | 0 | 0 | README.md, artifact-index.json, figures/figure-spec.yaml, figures/figure-summary.json, figures/line_train_loss_over_epoch.png, figures/line_train_loss_over_epoch.svg, figures/line_val_loss_over_epoch.png, figures/line_val_loss_over_epoch.svg, manifest.json, metrics/collection-summary.json, metrics/normalized_metrics.csv, metrics/normalized_metrics.json, package-summary.json, provenance/traceability.json ... (+5 more) |
| Complex Project Pack | raw_agent | 844652 | 211163 | 10 | 0 | 830231 | 14421 | raw_analysis_summary.md |
| Complex Project Pack | lab_sidecar | 162539 | 40635 | 12 | 0 | 0 | 0 | README.md, artifact-index.json, figures/figure-spec.yaml, figures/figure-summary.json, figures/line_train_loss_over_step.png, figures/line_train_loss_over_step.svg, figures/line_val_accuracy_over_step.png, figures/line_val_accuracy_over_step.svg, manifest.json, metrics/collection-summary.json, metrics/normalized_metrics.csv, metrics/normalized_metrics.json, package-summary.json, provenance/traceability.json ... (+5 more) |

## Aggregate Result

| Raw chars | Sidecar chars | Context reduction | Raw est. tokens | Sidecar est. tokens | Token reduction | Raw quality | Sidecar quality | Quality delta | Sidecar violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 24662732 | 525044 | 97.87% | 6165684 | 131262 | 97.87% | 30 | 36 | 6 | 0 |

## Raw Log And Metric Exposure

| Exposure type | Raw bytes | Sidecar bytes | Reduction |
| --- | ---: | ---: | ---: |
| Raw logs | 5855276 | 0 | 100.00% |
| Raw metric rows | 18763829 | 0 | 100.00% |

## Quality Rubric

Each category is scored 0-2. Maximum per arm per scenario is 12.

| Scenario | Arm | Total | Scores |
| --- | --- | ---: | --- |
| Large Training Run | raw_agent | 10 | `{"anomaly_detection": 2, "boundedness": 2, "deliverable_completeness": 1, "metric_correctness": 2, "no_invention": 2, "traceability": 1}` |
| Large Training Run | lab_sidecar | 12 | `{"anomaly_detection": 2, "boundedness": 2, "deliverable_completeness": 2, "metric_correctness": 2, "no_invention": 2, "traceability": 2}` |
| Multi-Run Sweep | raw_agent | 10 | `{"anomaly_detection": 2, "boundedness": 2, "deliverable_completeness": 1, "metric_correctness": 2, "no_invention": 2, "traceability": 1}` |
| Multi-Run Sweep | lab_sidecar | 12 | `{"anomaly_detection": 2, "boundedness": 2, "deliverable_completeness": 2, "metric_correctness": 2, "no_invention": 2, "traceability": 2}` |
| Complex Project Pack | raw_agent | 10 | `{"anomaly_detection": 2, "boundedness": 2, "deliverable_completeness": 1, "metric_correctness": 2, "no_invention": 2, "traceability": 1}` |
| Complex Project Pack | lab_sidecar | 12 | `{"anomaly_detection": 2, "boundedness": 2, "deliverable_completeness": 2, "metric_correctness": 2, "no_invention": 2, "traceability": 2}` |

## Workspaces And Task IDs

Benchmark root: `<benchmark-root>`

| Scenario | Raw workspace | Sidecar workspace | Sidecar task ids | Package |
| --- | --- | --- | --- | --- |
| Large Training Run | <benchmark-root>/raw-large-training | <benchmark-root>/sidecar-large-training | task_20260619_235511_300a3d | <benchmark-root>/package-alpha3-scale-large-training |
| Multi-Run Sweep | <benchmark-root>/raw-sweep | <benchmark-root>/sidecar-sweep | task_20260619_235519_6300dc | <benchmark-root>/package-alpha3-scale-sweep |
| Complex Project Pack | <benchmark-root>/raw-project | <benchmark-root>/sidecar-project | task_20260619_235530_4ca496 | <benchmark-root>/package-alpha3-scale-project |

## Violations And Omissions

| Scenario | Sidecar violation count | Violations |
| --- | ---: | --- |
| Large Training Run | 0 | none |
| Multi-Run Sweep | 0 | none |
| Complex Project Pack | 0 | none |

`slides/slides-summary.json` did not expose complete stdout/stderr bodies. `text_truncations` entries did not contain a long `full` body, and bounded evidence used omitted-body pointers for normalized metrics.

`metrics/collection-summary.json` included `bounded_analysis.best_rows`, `bounded_analysis.checkpoint_summary`, and `bounded_analysis.anomaly_summary` for the relevant scenarios. These summaries supported exact best-checkpoint, top-config/anomaly, and best-row/tradeoff claims without reading full normalized metrics.

SQLite-independent inspection passed for every sidecar run after deleting `.lab-sidecar/index.sqlite` and rerunning `summarize` and `artifacts` from task-local manifests.

## Scenario Notes

### Large Training Run

- `raw_agent`: Raw read confirms 60000 metric rows and a completed run. Best checkpoint is checkpoints/epoch_120_step_060000.pt with val_accuracy=0.904197 at step 60000. Validation accuracy moved from 0.460007 to 0.904197 while validation loss moved from 1.729975 to 0.247182. stderr contains 700 WARN lines and 1 non-fatal diagnostic line. Expected deliverables are metrics, figures, report, slides, traceability, and package metadata.
- `lab_sidecar`: Sidecar bounded evidence confirms 60001 normalized rows and exact best checkpoint checkpoints/epoch_120_step_060000.pt via val_accuracy=0.904197 at row 60001. best_rows selected_fields include step=60000 and checkpoint=checkpoints/epoch_120_step_060000.pt; evidence points to normalized metrics row with body omitted. Report, slide, traceability, and package metadata are present without reading full logs or metrics.

### Multi-Run Sweep

- `raw_agent`: Raw read ranks top configurations by validation accuracy and stability: cfg_19 cfg_19_convnext_tiny_lr0.0051_bs128 mean=0.861950 stability_std=0.000620 duration_ms=242.200; cfg_18 cfg_18_vit_tiny_lr0.0049_bs96 mean=0.855600 stability_std=0.000650 duration_ms=237.400; cfg_17 cfg_17_resnet34_lr0.0047_bs64 mean=0.849250 stability_std=0.000680 duration_ms=232.600. Anomalies are run_000=missing_final_metric; run_001=unstable_seed; run_002=warning_only; run_003=incomplete_artifact. Missing or incomplete artifacts are limited to runs with artifact_present=false.
- `lab_sidecar`: Sidecar bounded evidence ranks top configurations as cfg_19, cfg_18, cfg_17 from best_rows selected_fields on metric val_accuracy=0.86195; stability/duration tradeoff evidence is included in selected fields. anomaly_summary reports 5008 anomaly rows across 12 groups, including run_000 reasons=status=missing_final_metric,error_flag=1,incomplete_flag=1; run_001 reasons=status=unstable_seed,unstable_flag=1,anomaly_code=unstable_seed; run_002 reasons=warning_flag=1,anomaly_code=warning_only; run_003 reasons=status=incomplete_artifact,incomplete_flag=1,artifact_present=false. Evidence points to normalized metrics rows with bodies omitted; raw logs were not read.

### Complex Project Pack

- `raw_agent`: Raw read identifies candidate_e as strongest by test_accuracy=0.814040 and macro_f1=0.796360, with latency tradeoff 90.080ms. Unsupported claims include: Do not claim production readiness; only local deterministic validation was exercised. Do not claim fairness across unsupported demographic groups; subgroup labels are synthetic. Do not claim causal improvement; the benchmark is observational and file-first. Report, slide, package, traceability, and metric artifacts are expected deliverables; external drift and production behavior remain unknown.
- `lab_sidecar`: Sidecar bounded evidence identifies candidate_e as best row for test_accuracy=0.81404 with macro_f1=0.796360 and latency_ms=90.080. anomaly_summary records unsupported-claim caveats (status=unsupported_claim; warning_flag=1), so production readiness, fairness, and causal claims remain unsupported. Report, slides, traceability, and package metadata are present.

## Acceptance Status

Passed.
The benchmark ran all three scenarios, formula/path validation passed, task-local traceability and package metadata were present, SQLite-independent inspection passed, and no sidecar violations were found.

## Conclusion

This scale benchmark demonstrates context quarantine and context reduction after the slides-summary log-body fix and the new `bounded_analysis` summaries. Raw context was 24662732 chars versus 525044 chars for Lab-Sidecar, a 97.87% reduction. Estimated tokens fell from 6165684 to 131262, a 97.87% reduction.

Quality improved by 6 rubric points overall. The improvement is attributable to `bounded_analysis`: the Large Training Run now exposes the exact best checkpoint through `checkpoint_summary`; the sweep exposes bounded top-config and anomaly-run evidence; and the project pack exposes best-row/tradeoff evidence plus unsupported-claim caveats. Raw metric rows and raw logs remained quarantined from sidecar main-agent context, with 100.00% raw-metric exposure reduction and 100.00% raw-log exposure reduction.

The result is still a bounded-evidence tradeoff, not full raw inspection. Sidecar summaries support selected best rows, checkpoints, anomalies, generated artifacts, package metadata, and traceability; they intentionally do not expose every row, every log line, report body, PPTX internals, or raw note body.

## Limitations

- Exact provider token usage was not available locally.
- Token counts use `ceil(chars / 4)` and should be treated as a proxy.
- Quality scores are deterministic rubric scores from this benchmark run, not independent human preference ratings.
- The sidecar arm used local CLI only, not MCP/V2.
- Bounded summaries are only as useful as the metric fields present in collected source files; unsupported claims in prose-only notes still require conservative handling or explicit structured caveat fields.

## Follow-Up Recommendations

- Keep regression coverage for omitting full stdout/stderr bodies from slide summaries.
- Preserve `bounded_analysis` omitted-body evidence pointers so best-row/checkpoint claims remain bounded.
- Add a small benchmark fixture or regression test for sweep-style anomaly summaries over ingested runs.
- Consider a first-class bounded top-k summary for ranking prompts so top-3 or top-5 comparisons do not depend on a structured aggregate row.
