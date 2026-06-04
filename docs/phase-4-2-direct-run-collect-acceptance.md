# Phase 4.2 Direct Run Collect Acceptance

Date: 2026-06-04 19:09 +08:00

Scope: Phase 4.2 assessment and minimal product usability convergence. This phase does not add animation, GIF, MP4, Manim, Remotion, Web UI, FastAPI, MCP, or AI-dependent workflows.

## Decision

Phase 4.2 animation artifacts are deferred. The current product risk is not lack of animation; it is that the documented CLI-first path could not collect a CSV produced directly by:

```powershell
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv"
```

The minimal accepted Phase 4.2 work is therefore:

- keep Phase 4.1 static PPTX behavior intact
- avoid adding media or animation artifact types before the artifact protocol is designed
- make the direct `run -> collect -> figures -> report -> slides` path work without a wrapper command
- preserve conservative scanning so old workspace files are not silently mixed into a task

## Implementation Summary

Changed scanner behavior for run-mode tasks:

- `collect` still scans task directory top-level files.
- `collect` still scans `ingest` source references.
- `collect` now also scans the run working directory top level for CSV/JSON files created after task start.
- This scan is non-recursive.
- This scan is limited to workspace-internal working directories.
- This scan skips `.lab-sidecar`.
- `collection-summary.json` records these candidates with origin `run_working_dir`.

Changed tests:

- Added a regression test for direct run output collection without a wrapper command.
- The test creates a stale root-level CSV before the run and verifies it is not collected.

## Files Changed

- `lab_sidecar/collectors/scan.py`
- `tests/test_cli_smoke.py`
- `docs/phase-4-2-direct-run-collect-acceptance.md`

This Phase 4.2 work is in addition to the pre-existing Phase 4.1 working tree changes recorded in `docs/phase-4-real-sample-visual-acceptance.md`.

## Commands

```powershell
git status --short
git diff --stat
py -3 -m pytest
```

Result:

- `py -3 -m pytest`: 57 passed.

Targeted regression:

```powershell
py -3 -m pytest tests/test_cli_smoke.py::test_collect_run_working_dir_output_without_wrapper tests/test_cli_smoke.py::test_collect_csv_comparison_ingest_generates_normalized_metrics tests/test_cli_smoke.py::test_collect_without_supported_metrics_returns_exit_code_5
```

Result:

- 3 passed.

Direct CLI smoke workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase42-direct-2ff92260b61e49b69fc02d7007d3b593
```

Direct CLI smoke commands:

```powershell
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv"
py -3 -m lab_sidecar.cli.app collect task_20260604_190915_c35ea0
py -3 -m lab_sidecar.cli.app figures task_20260604_190915_c35ea0
py -3 -m lab_sidecar.cli.app report task_20260604_190915_c35ea0
py -3 -m lab_sidecar.cli.app slides task_20260604_190915_c35ea0
```

Direct CLI smoke result:

- task_id: `task_20260604_190915_c35ea0`
- `collect`: succeeded, 5 rows.
- candidate provenance: `run_working_dir:metrics.csv`
- `figures`: generated 2 PNG/SVG figure pairs.
- `report`: generated `reports/report-fragment.md` and `reports/report-summary.json`.
- `slides`: generated 7-slide `zh-summary` deck.
- slides QA checks: `slide_count`, `empty_slide_check`, `title_check`, `artifact_duplicate_check`, `table_overflow_guard`, and `caption_overflow_guard` all passed.

## Artifacts

Task directory:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase42-direct-2ff92260b61e49b69fc02d7007d3b593\.lab-sidecar\tasks\task_20260604_190915_c35ea0
```

Key artifacts:

- `metrics/normalized_metrics.csv`
- `metrics/normalized_metrics.json`
- `metrics/collection-summary.json`
- `figures/figure-spec.yaml`
- `figures/figure-summary.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

## Acceptance Checks

- Direct `run -> collect` works without a wrapper command.
- Candidate provenance is recorded as `run_working_dir`.
- Stale workspace root CSV files are not collected by the regression test.
- The scanner remains non-recursive.
- Existing ingest collection behavior remains covered.
- Existing Phase 4.1 slides test suite still passes.
- No animation/media/MCP/Web/API/AI workflow was introduced.

## Blocking

- None.

## Follow-Up

- Align `docs/artifact-protocol.md` with the already implemented `presentation` artifact type and any future `media` or `animation` type before implementing animation output.
- Consider a future explicit output declaration such as `run --outputs metrics.csv` for safer multi-output or nested-output workflows.
- Improve `project-presentation-pack` figure grouping to avoid `(missing)` labels in mixed metric tables.
- Improve key comparison card wrapping for very long variant labels.
- Unify Phase 4 documentation wording around required sample count; Phase 4.1 used 4 samples, while older planning text says at least one.

## Out Of Scope

- GIF, MP4, Manim, Remotion, HTML Canvas, and PowerPoint native animation.
- Web UI, FastAPI, MCP, and AI report polishing.
- Recursive workspace scanning or copying user source files.
- Phase 5 MCP tool implementation.
- Phase 6 real product acceptance.

## Phase Judgment

Phase 4.2 minimal acceptance passes. Animation is explicitly deferred because the media artifact protocol and animation acceptance checklist are not yet defined, and the higher-priority product risk was the documented CLI direct path. Blocking is 0.

The project may proceed to Phase 5 MCP Sidecar Integration, with the caveat that Phase 4.1 and Phase 4.2 changes are still uncommitted in the current working tree.
