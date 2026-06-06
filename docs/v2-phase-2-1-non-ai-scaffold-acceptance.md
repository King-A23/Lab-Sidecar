# V2 Phase 2.1 Acceptance

## Phase Goal

Implement the Non-AI Scaffold for Lab-Sidecar V2: task-local intelligence run directories, bounded input bundles, sandbox directory creation, proposal schema skeletons, validator skeleton, and local plugin-like tool functions. Proposals remain non-authoritative and cannot modify official artifacts in this phase.

## Starting State

- Start command: `git status --short`
- Starting status showed `?? docs/v2-development-plan.md`.
- `docs/v2-development-plan.md` was treated as an existing user/agent-provided input and was not modified during this phase.
- Current diff was reviewed before implementation. `lab_sidecar/runner/process.py` contains an existing unrelated process-probe change and was preserved without being treated as Phase 2.1 scaffold work.
- Unique phase executed: Phase 2.1 Non-AI Scaffold only.

## Changed Files

- `lab_sidecar/intelligence/__init__.py`
- `lab_sidecar/intelligence/bundle.py`
- `lab_sidecar/intelligence/paths.py`
- `lab_sidecar/intelligence/sandbox.py`
- `lab_sidecar/intelligence/schemas.py`
- `lab_sidecar/intelligence/tools.py`
- `lab_sidecar/intelligence/validator.py`
- `tests/test_v2_intelligence_scaffold.py`
- `docs/v2-phase-2-1-non-ai-scaffold-acceptance.md`

Existing unrelated working-tree state preserved:

- `docs/v2-development-plan.md` remains untracked.
- `lab_sidecar/runner/process.py` remains modified outside the Phase 2.1 write scope.

## Commands

- `git status --short`
- `sed -n '1,260p' docs/v2-development-plan.md`
- `sed -n '220,720p' docs/v2-development-plan.md`
- `sed -n '1,320p' docs/v2-intelligent-sidecar-design.md`
- `sed -n '320,760p' docs/v2-intelligent-sidecar-design.md`
- `git diff`
- `git diff --stat`
- `py -3 -m pytest tests/test_v2_intelligence_scaffold.py`
- `.venv/bin/python -m pytest tests/test_v2_intelligence_scaffold.py`
- `.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py`
- `.venv/bin/python -m pytest`
- `git status --short`

`py` is unavailable on this macOS workspace, so `.venv/bin/python` with Python 3.12.13 was used for acceptance testing.

## Workspaces And IDs

- Repository workspace: `/Users/anyuchen/Projects/personal/Lab-Sidecar`
- Acceptance smoke workspace: `/var/folders/n8/27vxlzfd6_l57knsz60pmz4c0000gn/T/lab-sidecar-v2-phase-2-1-ybvuicwi`
- Acceptance smoke task ID: `task_20260606_162808_204dde`
- Acceptance smoke worker run ID: `worker_run_20260606_162808_37cdb8`

## Generated Artifacts

Acceptance smoke intelligence files:

- `.lab-sidecar/tasks/task_20260606_162808_204dde/intelligence/worker_run_20260606_162808_37cdb8/input-bundle.json`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/intelligence/worker_run_20260606_162808_37cdb8/validator-result.json`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/intelligence/worker_run_20260606_162808_37cdb8/diagnostics.md`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/intelligence/worker_run_20260606_162808_37cdb8/sandbox/`

Acceptance smoke official V1 artifacts from deterministic fallback:

- `.lab-sidecar/tasks/task_20260606_162808_204dde/metrics/collection-summary.json`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/metrics/normalized_metrics.json`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/reproduce/command.txt`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/reproduce/dependencies.json`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/reproduce/env.json`
- `.lab-sidecar/tasks/task_20260606_162808_204dde/reproduce/git.json`

## Test Results

- `py -3 -m pytest tests/test_v2_intelligence_scaffold.py`: failed because `py` command is not installed.
- `.venv/bin/python -m pytest tests/test_v2_intelligence_scaffold.py`: passed, `5 passed`.
- `.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py`: passed, `78 passed`.
- `.venv/bin/python -m pytest`: passed, `83 passed`.

Final status check:

```text
 M lab_sidecar/runner/process.py
?? docs/v2-development-plan.md
?? lab_sidecar/intelligence/
?? tests/test_v2_intelligence_scaffold.py
```

## Blocking

- No Phase 2.1 blockers remain.
- V1 CLI and MCP smoke tests passed.
- Default plugin-like responses omit full stdout/stderr, metrics rows, report body, PPT content, worker prompt/response, artifact bodies, and full data files.
- Sandbox escape proposal validation rejects outside/official paths and writes diagnostics without modifying official artifact directories.

## Follow-Up

- Phase 2.2 should replace the Phase 2.1 worker-unavailable placeholder with the non-AI heuristic worker.
- Phase 2.2 should expand deterministic validation to fields, chart types, source paths, and adoption records before official artifact generation from proposals.
- Later phases should add bounded artifact preview and optional AI provider policy without weakening the Phase 2.1 omitted-content contract.

## Out Of Scope

- Heuristic proposal generation and proposal adoption.
- AI provider abstraction, prompts, responses, provider audit, or real-provider smoke.
- `preview_sidecar_artifact` and host/MCP contract hardening.
- Web UI, FastAPI, remote runner, hosted service, generic multi-agent framework, animation/video workflows, or OS/container sandboxing.

## Final Judgment

Phase 2.1 passes. The scaffold creates task-local intelligence workspaces and bounded records, keeps worker writable paths isolated to `sandbox/`, exposes the required local tool functions, falls back to V1 deterministic behavior when intelligent mode is off or the worker is unavailable, and does not allow proposals to affect official artifacts.
