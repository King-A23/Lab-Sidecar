# Post-Open-Source Stage 3 Acceptance

## Phase Goal

Deepen deterministic `collect --config` so a nested local result directory can be normalized with explicit config, mapped fields can drive figures, and diagnostics remain clear for missing sources, missing fields, and unit conflicts.

## Starting State

Before Stage 3, `collect --config` already supported string/list sources, source objects with `path` or `glob`, field mappings, and top-level or inline units. The gaps were nested ingested source refs, first-class include/exclude source lists, richer alias evidence, stronger unit diagnostics, and figure summaries that did not carry mapped units or config grouping metadata.

## Implemented Scope

- Added `sources.include` and `sources.exclude` config support while preserving old `sources: string`, `sources: [list]`, source object, `source_files`, `fields`, and `units` behavior.
- Kept default auto discovery conservative; recursive matching only runs for explicit configured sources.
- Added recursive candidate refs for ingested directories under `raw/source_refs.json` as `candidate_file_refs`, capped at 1000 files, while preserving top-level `candidate_files` for old auto-discovery behavior.
- Enforced configured source boundaries: sources must stay inside the workspace and, for ingest tasks, inside the ingested source refs.
- Preserved normalized `method` and `seed` through alias mappings and recorded matched source aliases in `matched_source_fields`.
- Recorded structured `diagnostics` and `unit_diagnostics` in `metrics/collection-summary.json`.
- Diagnosed configured unit conflicts and mixed source unit suffixes such as `runtime_ms` plus `runtime_s`.
- Propagated collection-summary `units` and `groups` into figure planning, generated figure specs, figure summaries, and axis labels.
- Added focused CLI smoke tests for nested messy results, include/exclude, missing source diagnostics, missing field diagnostics, unit diagnostics, and explicit mapped-field figures.

## Deferred Scope

Minimal regex log parsing is deferred. The Stage 3 collector remains CSV/JSON-only for metrics. This avoids half-implementing log parsing without the full bounded regex config validation and bad-regex diagnostics called out in the plan.

No unit conversion was implemented. Conflicts are diagnosed rather than silently converted.

## Changed Files

- `lab_sidecar/collectors/config.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/storage/artifact_store.py`
- `lab_sidecar/figures/specs.py`
- `lab_sidecar/figures/render.py`
- `lab_sidecar/figures/service.py`
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`
- `docs/post-open-source-stage-3-acceptance.md`

No `lab_sidecar/mcp` or `lab_sidecar/intelligence` files were changed.

## Config Shape

Backward-compatible shape remains valid:

```yaml
sources:
  - results/run_a.csv
fields:
  epoch: iter
  method: algo
  seed: trial
  accuracy: score_pct
units:
  accuracy: ratio
```

Stage 3 messy-results shape validated by tests and manual smoke:

```yaml
sources:
  include:
    - messy-results/**/*.csv
  exclude:
    - messy-results/debug/*.csv
    - messy-results/scratch/*
fields:
  epoch:
    sources: [epoch, step, iter]
  method:
    sources: [model, method, algo, variant]
  seed:
    sources: [seed, trial, run_id]
  accuracy:
    sources: [val_accuracy, score_pct, acc]
    unit: ratio
  latency_ms:
    sources: [runtime_ms, latency_ms, time_ms]
    unit: ms
groups:
  primary: method
  secondary: seed
```

Explicit figure spec used in smoke:

```yaml
figure_id: messy_accuracy
chart_type: line
title: Messy Accuracy
x: epoch
y: accuracy
group_by: method
```

## CLI Scenarios

Manual happy path:

```bash
tmpdir="$(mktemp -d /tmp/lab-sidecar-stage-3-XXXXXX)"
cp -R examples "$tmpdir/examples"
cd "$tmpdir"
python -m lab_sidecar.cli.app init
mkdir -p messy-results/baseline/seed_{1,2,3} messy-results/candidate/seed_{1,2,3} messy-results/debug messy-results/scratch
# write six nested metrics.csv files plus debug/scratch CSVs, metrics.yaml, and figure.yaml
python -m lab_sidecar.cli.app ingest messy-results --name "stage3 messy results"
python -m lab_sidecar.cli.app collect <task_id> --config metrics.yaml
python -m lab_sidecar.cli.app figures <task_id> --spec figure.yaml
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-messy
python -m lab_sidecar.cli.app summarize <task_id>
```

Manual diagnostic scenarios:

- `collect <task_id> --config bad-metrics.yaml` with a missing configured source and a configured CSV outside the ingested source refs.
- `collect <task_id> --config missing-field.yaml` with `seed: missing_seed`.
- `collect <unit_task_id> --config unit-conflict.yaml` mapping `runtime_ms` and `runtime_s` to `latency_ms`.

## Workspaces And Task IDs

Manual smoke workspace:

- `/tmp/lab-sidecar-stage-3-ZWbcBe`

Manual task ids:

- messy result task: `task_20260618_162446_cd1336`
- unit diagnostic task: `task_20260618_162449_4f52ef`

Messy fixture shape:

```text
messy-results/
  baseline/
    seed_1/metrics.csv
    seed_2/metrics.csv
    seed_3/metrics.csv
  candidate/
    seed_1/metrics.csv
    seed_2/metrics.csv
    seed_3/metrics.csv
  debug/debug_metrics.csv
  scratch/scratch.csv
```

Each nested metrics CSV used source columns `iter,algo,trial,score_pct,runtime_ms`. Debug and scratch CSVs used the same columns but were excluded by config.

## Generated Artifacts

Manual happy path generated:

```text
.lab-sidecar/tasks/task_20260618_162446_cd1336/metrics/collection-summary.json
.lab-sidecar/tasks/task_20260618_162446_cd1336/metrics/normalized_metrics.csv
.lab-sidecar/tasks/task_20260618_162446_cd1336/metrics/normalized_metrics.json
```

Package output included:

```text
package-messy/README.md
package-messy/artifact-index.json
package-messy/figures/figure-spec.yaml
package-messy/figures/figure-summary.json
package-messy/figures/messy_accuracy.png
package-messy/figures/messy_accuracy.svg
package-messy/manifest.json
package-messy/metrics/collection-summary.json
package-messy/metrics/normalized_metrics.csv
package-messy/metrics/normalized_metrics.json
package-messy/package-summary.json
package-messy/redaction-notes.md
package-messy/reports/report-fragment.md
package-messy/reports/report-summary.json
```

Manual happy path summary snapshot:

```json
{
  "candidate_count": 6,
  "figure_group_by": "method",
  "figure_units": {
    "accuracy": "ratio"
  },
  "groups": {
    "primary": "method",
    "secondary": "seed"
  },
  "matched_source_fields": {
    "accuracy": ["score_pct"],
    "epoch": ["iter"],
    "latency_ms": ["runtime_ms"],
    "method": ["algo"],
    "seed": ["trial"]
  },
  "methods": ["baseline", "candidate"],
  "row_count": 12,
  "seeds": ["1", "2", "3"],
  "skipped_reasons": ["configured_source_excluded"],
  "unit_diagnostics": [],
  "units": {
    "accuracy": "ratio",
    "latency_ms": "ms"
  }
}
```

## Diagnostics Evidence

Missing source plus not-in-source-refs diagnostic:

```text
BAD_COLLECT_EXIT=5
Configured source matched no files: messy-results/missing.csv
Configured source is not part of this task source refs: examples/csv-comparison/baseline.csv
```

Persisted diagnostics included:

```json
[
  {
    "reason": "configured_source_missing",
    "source_file": "messy-results/missing.csv"
  },
  {
    "reason": "not_in_source_refs",
    "source_file": "examples/csv-comparison/baseline.csv"
  }
]
```

Missing field diagnostic:

```text
MISSING_FIELD_EXIT=5
Configured field(s) missing in messy-results/baseline/seed_1/metrics.csv: seed from missing_seed
```

Persisted skipped file reason was `missing_configured_field`.

Unit conflict diagnostic:

```json
[
  {
    "field": "latency_ms",
    "message": "Mapped field 'latency_ms' matched source fields with mixed unit suffixes: runtime_ms=ms, runtime_s=s.",
    "reason": "mixed_source_units",
    "source_fields": "runtime_ms, runtime_s"
  }
]
```

## Test Results

Environment note: system Homebrew Python is externally managed, so validation used the repo-local `.venv` after:

```bash
.venv/bin/python -m pip install -e ".[dev]"
```

Validation commands run before this record:

```text
.venv/bin/python -m pytest tests/test_cli_smoke.py -q
85 passed in 8.07s

.venv/bin/python -m pytest -q
130 passed in 10.41s
```

Focused Stage 3 subset during development:

```text
.venv/bin/python -m pytest tests/test_cli_smoke.py -q -k "stage3 or config_maps_nonstandard or explicit_config"
5 passed, 80 deselected
```

Final validation after this document:

```text
git diff --check
passed

PATH=".venv/bin:$PATH" python -m pytest tests/test_cli_smoke.py -q
85 passed in 8.33s

PATH=".venv/bin:$PATH" python -m pytest -q
130 passed in 10.05s
```

## Blocking

None.

## Follow-Up

- Implement explicit bounded regex log parsing in a later stage, with config validation and bad-regex diagnostics.
- Consider richer unit metadata if Lab-Sidecar later adds explicit unit conversion, but do not convert silently.
- Consider increasing or exposing the source-ref cap only if real users hit the 1000 recorded-candidate limit.

## Out Of Scope

No Web UI, FastAPI, hosted service, remote runner, cloud sync, default AI analysis, statistical significance claims, TensorBoard parsing, arbitrary notebook execution, or broad recursive workspace scanning without explicit config was added.

## Final Judgment

Accepted. Stage 3’s selected scope is implemented: explicit messy-result config can normalize a nested multi-method, multi-seed directory; include/exclude prevents unrelated files from being collected; method and seed are preserved; missing sources, missing fields, and unit conflicts are diagnosed and persisted; explicit figure specs work with mapped fields and carry unit metadata; package, summarize, compare-adjacent CLI behavior, and the full test suite pass without touching MCP or intelligence code.
