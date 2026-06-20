# Alpha3 Sidecar Context Benchmark

Date: 2026-06-19

## Methodology

This benchmark compares the same bounded analysis prompt with and without Lab-Sidecar across three checked-in fixtures. The raw-agent arm reads raw fixture files directly and writes a bounded summary. The Lab-Sidecar arm uses the local CLI workflow and counts only CLI outputs plus bounded task summaries, package metadata, and `provenance/traceability.json` as main-agent context.

Token counts are estimates, not hosted Codex billing measurements. The deterministic proxy is `ceil(chars / 4)`, recorded in `docs/alpha3-sidecar-context-benchmark-data.json`.

The Lab-Sidecar arm was not allowed to read full stdout/stderr logs, full normalized metrics rows, report bodies, PPTX internals, raw source refs, raw source files, or worker prompt/response bodies. Any such exposure would be recorded as a violation.

## Scenario Results

| Scenario | Raw chars | Sidecar chars | Context reduction | Raw est. tokens | Sidecar est. tokens | Token reduction | Quality delta | Traceability | SQLite-independent check |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Simple Success | 2727 | 109868 | -3928.9% | 682 | 27467 | -3927.42% | 3 | yes | yes |
| CSV Comparison | 1495 | 110846 | -7314.45% | 374 | 27712 | -7309.63% | 3 | yes | yes |
| Project Presentation Pack | 3679 | 135243 | -3576.08% | 920 | 33811 | -3575.11% | 3 | yes | yes |

## Raw Vs Sidecar Comparison

| Scenario | Arm | Context chars | Estimated tokens | Quality | Raw metric row bytes exposed | Deliverables |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Simple Success | raw_agent | 2727 | 682 | 7 | 124 | raw_analysis_summary.md |
| Simple Success | lab_sidecar | 109868 | 27467 | 10 | 0 | metrics/normalized_metrics.csv, metrics/normalized_metrics.json, figures/figure-summary.json, reports/report-fragment.md, slides/presentation-draft.pptx, provenance/traceability.json, package-alpha3-simple/artifact-index.json, package-alpha3-simple/package-summary.json |
| CSV Comparison | raw_agent | 1495 | 374 | 7 | 467 | raw_analysis_summary.md |
| CSV Comparison | lab_sidecar | 110846 | 27712 | 10 | 0 | metrics/normalized_metrics.csv, metrics/normalized_metrics.json, figures/figure-summary.json, reports/report-fragment.md, slides/presentation-draft.pptx, provenance/traceability.json, package-alpha3-csv/artifact-index.json, package-alpha3-csv/package-summary.json |
| Project Presentation Pack | raw_agent | 3679 | 920 | 7 | 1901 | raw_analysis_summary.md |
| Project Presentation Pack | lab_sidecar | 135243 | 33811 | 10 | 0 | metrics/normalized_metrics.csv, metrics/normalized_metrics.json, figures/figure-summary.json, reports/report-fragment.md, slides/presentation-draft.pptx, provenance/traceability.json, package-alpha3-project/artifact-index.json, package-alpha3-project/package-summary.json |

## Aggregate Result

| Raw chars | Sidecar chars | Context reduction | Raw est. tokens | Sidecar est. tokens | Token reduction | Raw quality | Sidecar quality | Quality delta | Sidecar violations |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7901 | 355957 | -4405.21% | 1976 | 88990 | -4403.54% | 21 | 30 | 9 | 0 |

## Quality Rubric

Each category is scored 0-2. Maximum per arm per scenario is 10.

| Scenario | Arm | Total | Scores |
| --- | --- | ---: | --- |
| Simple Success | raw_agent | 7 | `{"boundedness": 1, "deliverable_completeness": 1, "metric_correctness": 2, "no_invention": 2, "traceability": 1}` |
| Simple Success | lab_sidecar | 10 | `{"boundedness": 2, "deliverable_completeness": 2, "metric_correctness": 2, "no_invention": 2, "traceability": 2}` |
| CSV Comparison | raw_agent | 7 | `{"boundedness": 1, "deliverable_completeness": 1, "metric_correctness": 2, "no_invention": 2, "traceability": 1}` |
| CSV Comparison | lab_sidecar | 10 | `{"boundedness": 2, "deliverable_completeness": 2, "metric_correctness": 2, "no_invention": 2, "traceability": 2}` |
| Project Presentation Pack | raw_agent | 7 | `{"boundedness": 1, "deliverable_completeness": 1, "metric_correctness": 2, "no_invention": 2, "traceability": 1}` |
| Project Presentation Pack | lab_sidecar | 10 | `{"boundedness": 2, "deliverable_completeness": 2, "metric_correctness": 2, "no_invention": 2, "traceability": 2}` |

## Workspaces And Task IDs

All workspaces were created under `/private/tmp`; generated `.lab-sidecar` directories and packages are not repository artifacts.

| Scenario | Raw workspace | Sidecar workspace | Sidecar task ids |
| --- | --- | --- | --- |
| Simple Success | <benchmark-root>/raw-simple_success | <benchmark-root>/sidecar-simple_success | task_20260619_185314_ba7ee1 |
| CSV Comparison | <benchmark-root>/raw-csv_comparison | <benchmark-root>/sidecar-csv_comparison | task_20260619_185318_188987 |
| Project Presentation Pack | <benchmark-root>/raw-project_presentation_pack | <benchmark-root>/sidecar-project_presentation_pack | task_20260619_185323_ee26a4 |

Benchmark root: `<benchmark-root>`

## Violations And Omissions

| Scenario | Sidecar violation count | Violations |
| --- | ---: | --- |
| Simple Success | 0 | none |
| CSV Comparison | 0 | none |
| Project Presentation Pack | 0 | none |

The raw-agent arm intentionally exposed raw source tables and JSON as main-agent context. Across the three raw runs, raw metric row exposure was 2492 bytes. Across the Lab-Sidecar runs, raw metric row exposure was 0 bytes.

SQLite-independent inspection passed for every sidecar run after deleting `.lab-sidecar/index.sqlite` and rerunning `summarize` and `artifacts`.

## Acceptance Status

Passed. All three scenarios have raw and sidecar runs, required context and quality fields are present, each sidecar run generated task-local traceability and package metadata, SQLite-independent inspection passed, no sidecar full-artifact-body exposure was recorded, the JSON data file is valid, and no generated `.lab-sidecar` or package directory is in the repository working tree.

## Interpretation

In this local benchmark, the Lab-Sidecar arm improved deliverable completeness and traceability but increased measured context chars because the checked-in fixtures are intentionally tiny while Lab-Sidecar produces rich bounded metadata. This is a useful negative control: for small toy inputs, sidecar metadata can be larger than the raw files.

The alpha3 result supports a narrower context-quarantine claim: Lab-Sidecar keeps raw logs, raw metric rows, report bodies, PPTX internals, and raw source files out of the main-agent context while producing traceable artifacts. It does not prove token savings on tiny fixtures.

## Limitations

- Exact provider token usage was not available locally.
- Token counts use `ceil(chars / 4)` and should be treated as a proxy.
- The raw fixtures are small, so context-reduction percentages are not representative of long-running experiments.
- This benchmark uses local CLI only, not MCP/V2 host calls.
- Quality scores are deterministic rubric scores based on generated artifacts and summaries, not human preference ratings.
