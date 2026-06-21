# Experiment Scenario Sidecar V1 Plan

Date: 2026-06-21

## Goal

Reposition Lab-Sidecar as a local AI agent sidecar for experiment scenarios and
add a bounded scenario-summary contract that agent-facing tools can use without
reading full logs, metric rows, reports, slides, or worker audit bodies.

The primary caller is a main AI agent. The human user remains the experiment
owner and final decision maker.

## Implementation Slices

1. Add `metrics/scenario-summary.json` for collected metrics.
   - First canonical scenarios: `training-run` and `algorithm-benchmark`.
   - Include primary metric, groups, best rows, last rows, seed aggregates,
     evidence, omissions, and warnings.
   - Keep all row evidence bounded to row numbers, selected fields, and paths.

2. Wire the summary into existing surfaces.
   - `collect` writes and registers the artifact.
   - `summarize` prints a compact scenario block.
   - V2 delegate/inspect expose `summary.outputs.scenario`.
   - Report and slide summaries include scenario evidence without overclaiming.

3. Keep artifact and provenance systems aligned.
   - Package export includes the summary.
   - Traceability records the scenario summary path, scenario type, and primary
     metric.

4. Update positioning docs.
   - README first screen uses AI-agent primary caller language.
   - Product and V2 docs keep students/research beginners as the human audience.

## Boundaries

- No Web UI, FastAPI, remote runner, hosted service, or cloud sync.
- No generic multi-agent framework.
- No default AI analysis or cloud provider calls.
- No TensorBoard, JSONL, or log collector expansion in this slice.
- No statistical significance or autonomous scientific conclusion claims.
- Avoid MCP code unless the shared compact response helper requires it.

## Validation

Run:

```bash
python -m pytest tests/test_scenario_summary.py
python -m pytest tests/test_cli_smoke.py
python -m pytest tests/test_v2_host_integration.py tests/test_v2_heuristic_worker.py
python -m pytest
```

Run MCP stdio smoke only if `lab_sidecar/mcp` code changes.

