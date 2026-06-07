# V2 Phase 2.5 Worker Invocation Protocol Acceptance

Date: 2026-06-07

## Phase Goal

Extract the V2 heuristic and fake-provider worker paths into a stable local
worker invocation protocol with structured `WorkerRequest`, `WorkerResult`,
`WorkerInvocation`, and `SidecarWorker` interfaces. Keep
`delegate_experiment_artifacts` as the public entrypoint and keep deterministic
validation as the only gate before official V1 artifact adoption.

## Starting State

- Branch: `codex/v2-intelligent-sidecar-baseline`
- Initial `git status --short`: no output
- Initial `git diff --stat`: no output
- Required planning and V2 intelligence/test files were inspected before
  editing.

## Changed Files

- `lab_sidecar/intelligence/worker_invocation.py`
- `lab_sidecar/intelligence/__init__.py`
- `lab_sidecar/intelligence/tools.py`
- `lab_sidecar/intelligence/heuristic_worker.py`
- `lab_sidecar/intelligence/ai_provider.py`
- `tests/test_v2_worker_invocation.py`
- `docs/v2-phase-2-5-worker-invocation-protocol-acceptance.md`

## Commands

```bash
git status --short
git diff --stat
sed -n '1,240p' docs/v2-phase-2-5-worker-invocation-protocol-plan.md
sed -n '1,620p' docs/v2-development-plan.md
sed -n '1,620p' lab_sidecar/intelligence/tools.py
sed -n '1,260p' lab_sidecar/intelligence/heuristic_worker.py
sed -n '1,620p' lab_sidecar/intelligence/ai_provider.py
sed -n '1,620p' lab_sidecar/intelligence/validator.py
sed -n '1,520p' tests/test_v2_ai_provider.py
sed -n '1,300p' tests/test_v2_heuristic_worker.py
sed -n '1,300p' tests/test_v2_host_integration.py
sed -n '1,320p' tests/test_v2_intelligence_scaffold.py
.venv/bin/python -m pytest tests/test_v2_worker_invocation.py
.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py
SMOKE_WS="/tmp/lab-sidecar-v2-phase-2-5-mcp-$(date +%Y%m%d%H%M%S)" && .venv/bin/python scripts/mcp_stdio_smoke.py --workspace "$SMOKE_WS"
.venv/bin/python -m pytest
```

An additional acceptance evidence workspace was generated with `.venv/bin/python`
to record concrete worker request/result paths and official artifact outputs.

## Workspaces And IDs

MCP stdio smoke:

- Workspace: `/private/tmp/lab-sidecar-v2-phase-2-5-mcp-20260607183858`
- Task ID: `task_20260607_183858_e86bb3`
- Cancel task ID: `task_20260607_183859_0bf355`

Acceptance evidence workspace:

- Workspace: `/tmp/lab-sidecar-v2-phase-2-5-acceptance-20260607183950`
- Heuristic task ID: `task_20260607_183950_b4f442`
- Heuristic worker run ID: `worker_run_20260607_183950_4a5de2`
- Provider-backed task ID: `task_20260607_183950_fe2954`
- Provider-backed worker run ID: `worker_run_20260607_183950_bd782f`

## Generated Worker Request/Result Files

Heuristic run:

- `.lab-sidecar/tasks/task_20260607_183950_b4f442/intelligence/worker_run_20260607_183950_4a5de2/worker-request.json`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/intelligence/worker_run_20260607_183950_4a5de2/worker-result.json`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/intelligence/worker_run_20260607_183950_4a5de2/validator-result.json`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/intelligence/worker_run_20260607_183950_4a5de2/adoption-record.json`

Provider-backed fake-provider run:

- `.lab-sidecar/tasks/task_20260607_183950_fe2954/intelligence/worker_run_20260607_183950_bd782f/worker-request.json`
- `.lab-sidecar/tasks/task_20260607_183950_fe2954/intelligence/worker_run_20260607_183950_bd782f/worker-result.json`
- `.lab-sidecar/tasks/task_20260607_183950_fe2954/intelligence/worker_run_20260607_183950_bd782f/validator-result.json`
- `.lab-sidecar/tasks/task_20260607_183950_fe2954/intelligence/worker_run_20260607_183950_bd782f/adoption-record.json`

## Generated Official Artifacts

Heuristic run:

- `.lab-sidecar/tasks/task_20260607_183950_b4f442/metrics/collection-summary.json`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/metrics/normalized_metrics.json`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/figures/figure-spec.yaml`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/figures/figure-summary.json`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/figures/line_accuracy_over_epoch.png`
- `.lab-sidecar/tasks/task_20260607_183950_b4f442/figures/line_accuracy_over_epoch.svg`

Provider-backed fake-provider run:

- `.lab-sidecar/tasks/task_20260607_183950_fe2954/metrics/collection-summary.json`
- `.lab-sidecar/tasks/task_20260607_183950_fe2954/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/task_20260607_183950_fe2954/metrics/normalized_metrics.json`

## Test Results

- `tests/test_v2_worker_invocation.py`: 5 passed
- `tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py`: 24 passed
- `tests/test_cli_smoke.py tests/test_mcp_tools.py`: 78 passed
- `scripts/mcp_stdio_smoke.py`: passed; final status `completed`, metrics rows `5`, figure count `2`, slide count `7`, cancel status `cancelled`, blocked command status `blocked`
- Full suite: 107 passed

## Blocking Items

None found.

The implemented protocol keeps worker code limited to proposal and audit-file
production. Official metrics, figures, reports, and slides are still written
only after `validate_proposal` accepts a proposal and `adopt_proposal` calls the
V1 services.

Default responses continue to omit full stdout, full stderr, metrics rows,
report bodies, PPT content, worker prompt/response bodies, artifact bodies, and
full data files.

## Follow-Ups

- Consider adding per-attempt metadata if future provider-backed workers need to
  record separate provider and heuristic fallback attempts inside one worker
  result.
- Add real provider adapters only after explicit provider smoke policy is
  approved.
- Consider async worker execution later behind the same request/result files.

## Out Of Scope

- Real cloud provider adapters
- MCP mirroring for V2 tools
- Web UI, FastAPI, hosted execution, remote runners, or generic multi-agent
  orchestration
- Uploading full logs, datasets, prompt/response bodies, report bodies, PPT
  content, worker transcripts, or artifact bodies by default

## Final Judgment

Accepted. Phase 2.5 now has a shared worker invocation lifecycle for heuristic
and fake/provider-backed workers, persists `worker-request.json` and
`worker-result.json`, preserves no-AI and provider-unavailable fallback behavior,
and keeps deterministic validation as the adoption gate for official V1
artifacts.

