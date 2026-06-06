# V2 Phase 2.4 Acceptance

## Phase Goal

Harden the local Codex-plugin-like V2 tool contract, add bounded artifact preview, document host setup and smoke paths, preserve existing MCP behavior, and defer MCP mirroring until it can remain a thin adapter over the stable local V2 contract.

## Starting State

- Phase 2.1 was accepted in `docs/v2-phase-2-1-non-ai-scaffold-acceptance.md`.
- Phase 2.2 was accepted in `docs/v2-phase-2-2-heuristic-worker-acceptance.md`.
- Phase 2.3 was accepted for its implemented optional-provider subset in `docs/v2-phase-2-3-optional-ai-provider-acceptance.md`; real provider adapter execution and real-key smoke remain follow-up work.
- Start command: `git status --short`.
- Starting status preserved existing external state: `docs/v2-development-plan.md` untracked and `lab_sidecar/runner/process.py` modified outside the V2 intelligence scope.
- Current diff was reviewed before Phase 2.4 edits.
- Unique phase executed: Phase 2.4 Codex Plugin / Host Integration Hardening only.

## Changed Files

- `docs/mcp-host-config.md`
- `docs/v2-host-integration.md`
- `lab_sidecar/intelligence/__init__.py`
- `lab_sidecar/intelligence/preview.py`
- `lab_sidecar/intelligence/tools.py`
- `tests/test_v2_host_integration.py`
- `docs/v2-phase-2-4-codex-host-hardening-acceptance.md`

Previously changed V2 files from Phases 2.1 through 2.3 remain present.

Existing unrelated working-tree state preserved:

- `docs/v2-development-plan.md` remains untracked.
- Prior acceptance docs remain untracked until the eventual commit/stage step.
- `lab_sidecar/runner/process.py` remains modified outside the Phase 2.4 write scope.

## Commands

- `git status --short`
- `git diff --stat`
- `.venv/bin/python -m compileall lab_sidecar/intelligence`
- `.venv/bin/python -m pytest tests/test_v2_host_integration.py`
- `.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_intelligence_scaffold.py`
- `.venv/bin/python -m pytest tests/test_mcp_tools.py`
- `.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-v2-phase-2-4-mcp`
- `.venv/bin/python -m pytest`
- `git status --short`

`py` is unavailable on this macOS workspace, so `.venv/bin/python` with Python 3.12.13 was used for acceptance testing. `/tmp/lab-sidecar-v2-phase-2-4-mcp` was used instead of `$TMPDIR`.

## Workspaces And IDs

Local V2 host smoke:

- Workspace: `/var/folders/n8/27vxlzfd6_l57knsz60pmz4c0000gn/T/lab-sidecar-v2-phase-2-4-4b_vk0o9`
- Delegate task ID: `task_20260606_165716_491a84`
- Cancel task ID: `task_20260606_165716_4f7849`

MCP stdio smoke:

- Workspace: `/private/tmp/lab-sidecar-v2-phase-2-4-mcp`
- Main task ID: `task_20260606_165654_9cccd9`
- Cancel task ID: `task_20260606_165655_98f7ae`

## Generated Artifacts

Local V2 host smoke generated:

- Official metrics, figures, report, and slides artifacts under `.lab-sidecar/tasks/task_20260606_165716_491a84/`
- Bounded preview responses for:
  - CSV: `csv_rows`
  - Markdown: `markdown_lines`
  - PPTX: `pptx_metadata`
  - Log: `log_tail`
  - Image: `image_metadata`
- External preview rejection: `status=rejected`, `risk_flags=["artifact_preview_rejected"]`

MCP stdio smoke generated:

- Official V1 MCP smoke artifacts under `/private/tmp/lab-sidecar-v2-phase-2-4-mcp/.lab-sidecar/tasks/task_20260606_165654_9cccd9/`
- `metrics_rows=5`
- `figure_count=2`
- `slide_count=7`
- cancellation smoke status `cancelled`
- destructive command status `blocked`

## Test Results

- `.venv/bin/python -m compileall lab_sidecar/intelligence`: passed.
- `.venv/bin/python -m pytest tests/test_v2_host_integration.py`: passed, `5 passed`.
- `.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_intelligence_scaffold.py`: passed, `19 passed`.
- `.venv/bin/python -m pytest tests/test_mcp_tools.py`: passed, `9 passed`.
- `.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-v2-phase-2-4-mcp`: passed.
- `.venv/bin/python -m pytest`: passed, `102 passed`.

Final status check:

```text
 M docs/mcp-host-config.md
 M lab_sidecar/runner/process.py
?? docs/v2-development-plan.md
?? docs/v2-host-integration.md
?? docs/v2-phase-2-1-non-ai-scaffold-acceptance.md
?? docs/v2-phase-2-2-heuristic-worker-acceptance.md
?? docs/v2-phase-2-3-optional-ai-provider-acceptance.md
?? lab_sidecar/intelligence/
?? tests/test_v2_ai_provider.py
?? tests/test_v2_heuristic_worker.py
?? tests/test_v2_host_integration.py
?? tests/test_v2_intelligence_scaffold.py
```

## Blocking

- No Phase 2.4 blockers remain.
- `preview_sidecar_artifact` rejects external and unregistered paths.
- Preview is type-specific and bounded; it is not a generic file reader.
- Default host-facing responses continue to omit full logs, complete datasets, report bodies, PPT content, prompt/response content, and artifact bodies.
- Existing MCP tests and stdio smoke pass.
- V2 MCP mirroring was deferred to avoid creating an incomplete or parallel MCP product surface before the local V2 contract has separate host use.

## Follow-Up

- Add a thin MCP mirror for V2 local tools only after the local V2 contract is stable in real Codex host use.
- If MCP mirroring is added, the adapter should call the same local `delegate_experiment_artifacts`, `inspect_sidecar_task`, `cancel_sidecar_task`, and `preview_sidecar_artifact` functions.
- Future host packaging should follow confirmed Codex plugin registration documentation when available.
- Real provider execution remains out of scope until an explicit provider adapter and smoke policy are approved.

## Out Of Scope

- MCP mirroring of V2 tools in this phase.
- Real Codex plugin packaging or marketplace registration.
- Real cloud provider adapter implementation.
- Web UI, FastAPI, remote runner, hosted service, generic multi-agent framework, animation/video workflows, or OS/container sandboxing.

## Final Judgment

Phase 2.4 passes for Codex-plugin-like host integration hardening. Local tools now include bounded preview, host-facing responses remain quarantined, host setup and smoke documentation exists, and existing MCP behavior remains protected by tests and stdio smoke. V2.1, V2.2, and V2.4 are acceptable; V2.3 is acceptable only for the implemented provider abstraction, fake-provider, policy, audit, and fallback subset. The overall V2.1 through V2.4 gate should not be marked fully complete until the real provider adapter and safe real-provider smoke requirement is either implemented or explicitly re-scoped in the plan.
