# Public Alpha Final Acceptance

Date: 2026-06-08

## Scope

This is the final acceptance consolidation for the cautious public-alpha
release-preparation pass. It covers implementation, tests, documentation,
Codex plugin scaffolding, release metadata, and MCP mirror validation. It does
not supersede the historical phase acceptance records listed below.

This record accepts the public-alpha demo and documentation package only when
the docs remain truthful about current behavior: Lab-Sidecar is a local-first
sidecar that exposes bounded tools and task artifacts. Codex supervisor agents
may spawn subagents to coordinate work, but that is a Codex execution pattern,
not a Lab-Sidecar product capability.

## Evidence Used

| Evidence | What It Supports |
| --- | --- |
| `docs/phase-6-real-product-acceptance.md` | CLI success, failure, comparison, project presentation, artifact provenance, visual PPTX acceptance |
| `docs/public-alpha-readiness-acceptance.md` | Public-alpha readiness, MCP stdio smoke, safety model clarification |
| `docs/public-alpha-release-notes.md` | Current feature list, safety notes, known limits |
| `docs/public-alpha-quickstart.md` | 10-minute local quickstart |
| `docs/mcp-host-config.md` | V1 MCP stdio host setup and safety boundary |
| `docs/v2-host-integration.md` | V2 local host contract, bounded previews, and thin MCP mirroring |
| `docs/v2-phase-2-5-worker-invocation-protocol-acceptance.md` | Worker request/result protocol and deterministic adoption gate |
| `docs/demo-public-alpha.md` | Deterministic demo script for this final documentation package |
| `examples/*/README.md` | Fixture-level demo expectations |

## Accepted Public Alpha Surface

Accepted as current public-alpha capability:

- CLI workflow: `init -> run/ingest -> collect -> figures -> report -> slides`
- successful command capture with task-local manifest, logs, metrics, figures,
  report fragments, and static PPTX drafts
- failed command diagnostics with preserved exit code, stderr, report fragment,
  and diagnostic PPTX draft
- existing-result ingestion for CSV and JSON examples
- deterministic chart, report, and slide generation from collected artifacts
- experimental V1 MCP stdio adapter with bounded default responses
- thin V2 MCP mirror for delegation, inspection, cancellation, and bounded
  artifact previews
- V2 local host tools for bounded delegation, inspection, cancellation, and
  artifact previews
- V2 worker request/result audit files with deterministic validation before
  official V1 artifact adoption

## Accepted Demo Scenarios

| Scenario | Fixture | Expected Public-Alpha Result |
| --- | --- | --- |
| Successful run | `examples/simple-success` | completed task with metrics, figures, report, and PPTX |
| Failed run | `examples/simple-failure` | failed task with preserved diagnostics and diagnostic artifacts |
| Multi-run comparison | `examples/csv-comparison` | normalized metrics from three CSV files and comparison artifacts |
| JSON benchmark | `examples/algorithm-benchmark` | normalized benchmark metrics and runtime-oriented artifacts |
| Project presentation pack | `examples/project-presentation-pack` | project-style report and static PPTX draft using `zh-project` |
| MCP smoke | temp workspace | bounded stdio tool responses and generated task artifacts |

## Safety And Truthfulness Criteria

The public-alpha docs pass this final documentation gate only if they state:

- CLI `run` is a user-explicit local command execution path.
- MCP-facing `run_experiment` has workspace and command safety gates.
- Lab-Sidecar does not claim OS sandboxing, malware detection, container
  isolation, multi-user policy, or global shell interception.
- Default tool responses omit full stdout, full stderr, full metrics rows,
  report bodies, PPT contents, worker transcripts, and artifact bodies.
- V2 worker paths produce proposals and audit files; official artifacts are
  created only through deterministic validation and V1 services.
- V2 MCP mirroring remains a thin adapter over the same local V2 host
  contracts, not a separate product surface.
- Codex supervisor/subagent execution is coordination outside Lab-Sidecar, not
  a sidecar runtime feature.

## Validation Commands

This record consolidates docs, packaging, plugin scaffold, MCP mirror, and test
evidence for the final public-alpha preparation pass.

Required local checks for the final pass:

```bash
git diff --check
rg -n "future in Lab-Sidecar|reports/project-summary|presentation-bullets" examples
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py
.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py tests/test_v2_worker_invocation.py
.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke
.venv/bin/python $CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
git status --short
```

The stale-example command should return no matches after the README refresh,
because those phrases would indicate stale fixture documentation. Older
planning docs may still mention proposed artifact names as historical design
context.

## Final Pass Results

Final implementation pass results in
the repository root:

- `git diff --check`: passed.
- `rg -n "future in Lab-Sidecar|reports/project-summary|presentation-bullets" examples`: no matches.
- `.venv/bin/python -m pytest -q`: `112 passed`.
- `.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py -q`: `82 passed`.
- `.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py tests/test_v2_worker_invocation.py -q`: `30 passed`.
- `.venv/bin/python $CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar`: passed.
- `.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke`: passed.

Final MCP stdio smoke evidence:

- workspace: `/private/tmp/lab-sidecar-mcp-stdio-smoke`
- listed tools: `cancel_experiment`, `cancel_sidecar_task`,
  `delegate_experiment_artifacts`, `generate_report_fragment`,
  `generate_slides`, `inspect_results`, `inspect_sidecar_task`,
  `make_figures`, `preview_sidecar_artifact`, `run_experiment`
- V1 task id: `task_20260608_130048_53f7ca`
- V1 result: background run reached `completed`, 5 metric rows, 2 figures,
  7-slide deck, all slide QA checks true
- V2 task id: `task_20260608_130049_0e180b`
- V2 result: `delegate_experiment_artifacts` completed and
  `preview_sidecar_artifact` returned a bounded `csv_rows` preview
- cancellation task id: `task_20260608_130049_4c2573`
- cancellation result: `cancelled`
- destructive command result: `blocked`

Additional spot-check run during the demo documentation slice:

- command path: `ingest -> collect -> figures -> report -> slides -> artifacts`
  for `examples/algorithm-benchmark`
- workspace: `/tmp/lab-sidecar-docs-algorithm-syl5BC`
- task id: `task_20260608_125020_4b7216`
- result: 18 normalized rows, 1 runtime figure, report fragment generated,
  static PPTX generated with 7 slides

The spot-check validates the refreshed `algorithm-benchmark` README claim. It
is not a replacement for the broader implementation acceptance records above.

## Blocking

No blocking issues are known for cautious public-alpha release preparation.

## Follow-Up

Follow-up work remains outside this documentation slice:

- host-specific MCP setup validation for concrete hosts
- configurable command policy
- broader malformed real-world fixtures
- real provider adapter and explicitly approved real-provider smoke
- broader real-user validation outside maintainer-run examples and smokes

## Out Of Scope

This final acceptance does not include:

- a new implementation acceptance run
- packaging publication
- Web UI, FastAPI, remote runners, or hosted service
- AI-generated conclusions as a default feature
- animation, video, GIF, Manim, Remotion, or native PowerPoint animation

## Final Judgment

Accepted for cautious public-alpha release preparation. Package publication and
host-specific MCP setup remain separate release operations.
