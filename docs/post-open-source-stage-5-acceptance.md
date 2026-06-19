# Post-Open-Source Stage 5 Acceptance: Provenance And Traceability

Date: 2026-06-18

## Scope

Stage 5 is implemented as a task-local provenance pass. The repo stays CLI-first, file-first, local-first, and bounded. No Web UI, FastAPI, hosted service, remote runner, cloud sync, generic multi-agent framework, or default AI analysis was added.

Pre-existing local changes were preserved:

- `docs/post-open-source-stage-5-plan.md`
- `docs/post-open-source-product-roadmap.md`

Both documents are included in the final Stage 5 commit so the implementation
record and roadmap index stay together.

## Changed Files

- `lab_sidecar/core/traceability.py`
- `lab_sidecar/core/models.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/figures/service.py`
- `lab_sidecar/reports/service.py`
- `lab_sidecar/slides/service.py`
- `lab_sidecar/storage/package_export.py`
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`
- `docs/post-open-source-stage-5-plan.md`
- `docs/post-open-source-stage-5-acceptance.md`
- `docs/post-open-source-product-roadmap.md`

## Validation

Ran with the repo venv on `PATH`:

```bash
git diff --check
PATH=.venv/bin:$PATH python -m pytest tests/test_cli_smoke.py -q
PATH=.venv/bin:$PATH python -m pytest -q
```

Pre-commit audit fixes were validated with:

```bash
PATH=.venv/bin:$PATH python -m pytest tests/test_cli_smoke.py::test_package_completed_task_exports_allowlisted_artifacts_only tests/test_cli_smoke.py::test_figures_auto_rejects_bar_chart_with_too_many_categories -q
```

Result: 2 passed.

Manual full workflow smoke:

```bash
WORKSPACE=/private/tmp/lab-sidecar-stage-5-zgNNeC
TASK_ID=task_20260618_222513_2fc3fd
PACKAGE=package-stage5
```

Commands exercised in that workspace:

- `init`
- `run "python examples/simple-success/train.py --output metrics.csv"`
- `collect <task_id>`
- `figures <task_id>`
- `report <task_id>`
- `slides <task_id>`
- `package <task_id> --output package-stage5`
- delete `.lab-sidecar/index.sqlite`
- `status <task_id>`
- `summarize <task_id>`
- `artifacts <task_id>`

## Generated Artifacts

Task-local:

- `metrics/normalized_metrics.csv`
- `metrics/normalized_metrics.json`
- `metrics/collection-summary.json`
- `figures/figure-spec.yaml`
- `figures/figure-summary.json`
- `figures/*.png`
- `figures/*.svg`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`
- `provenance/traceability.json`

Package:

- `package-stage5/artifact-index.json`
- `package-stage5/package-summary.json`
- `package-stage5/provenance/traceability.json`

## Traceability Evidence

Manual smoke summary for `task_20260618_222513_2fc3fd`:

- `artifact_count`: 19
- `source_count`: 1
- `claim_trace_count`: 34
- `metric_rows`: 5
- `figure_count`: 2
- `slide_count`: 7

The traceability index records:

- source refs and normalized metrics lineage
- generated artifact hashes and sizes
- figure lineage and figure summary pointers; absent figure specs remain `null`
  rather than pointing to a non-existent `figures/figure-spec.yaml`
- report claim traces for numeric summaries and diagnostics
- slide evidence and bounded diagnostic reasons
- reproduce metadata pointers
- omission notes
- package metadata hashes for `README.md`, `package-summary.json`, and
  `redaction-notes.md`; `artifact-index.json` records a self-referential digest
  omission note

Pre-commit audit fixes:

- no-figure traceability now reports `figure_lineage.spec_path: null` when
  `figures/figure-spec.yaml` was not generated
- package artifact indexes now record hash/size metadata for package README,
  package summary, and redaction notes, plus an explicit self-referential digest
  omission note for `artifact-index.json`

Deleting `.lab-sidecar/index.sqlite` did not block inspection of `status`, `summarize`, or `artifacts`. The task-local `provenance/traceability.json` remained available.

## Omitted-Contract Evidence

Package export and traceability stay conservative:

- full stdout/stderr logs are omitted
- raw source files are not copied by default
- `raw/source_refs.json` is not embedded as a raw dump
- worker prompt/response bodies are omitted
- worker transcript bodies are omitted
- temporary sandbox files are omitted
- `.lab-sidecar/index.sqlite` is omitted
- report bodies and PPT contents are not embedded in traceability
- full metrics row bodies are not embedded in traceability

## Deferred Scope

Not changed in this stage:

- MCP/V2 bounded preview behavior
- plugin packaging/validation
- host-facing tool schemas
- Web UI, FastAPI, hosted service, cloud sync
- statistical significance or model-ranking claims

## Final Judgment

Accepted. Stage 5 provenance and traceability are implemented, packaged, documented, and validated with SQLite-independent task-local inspection.
