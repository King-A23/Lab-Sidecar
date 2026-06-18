# Post-Open-Source Stage 4 Plan: Agent-Native Delegation Hardening

Date: 2026-06-18

## 1. Phase Goal

Harden Lab-Sidecar's Agent-native delegation path so Codex/MCP hosts can safely delegate noisy local experiment work, inspect bounded state, preview artifacts, and cancel tasks without polluting the main Agent context.

After Stage 4, a host should be able to use:

```text
delegate_experiment_artifacts
inspect_sidecar_task
preview_sidecar_artifact
cancel_sidecar_task
```

with high confidence that:

- default responses stay bounded
- previews are task-scoped and type-specific
- cancellation and recovery behavior is predictable
- worker audit files remain useful but are not leaked by default
- plugin guidance clearly tells Codex when to delegate

This stage strengthens the existing V2/MCP host path. It does not create a new product surface.

## 2. Product Promise

Stages 1-3 improved CLI navigation, packaging, and messy result adaptation. Stage 4 makes those artifact-first capabilities safer and easier for a main Agent to use.

The user-facing promise is:

> Let the main Agent stay focused while Lab-Sidecar handles noisy local artifact work and returns only task ids, summaries, previews, risk flags, and paths.

## 3. Current Baseline

Current useful surface:

- V2 local host functions exist under `lab_sidecar.intelligence`.
- MCP mirrors V2 tools as a thin adapter.
- `preview_sidecar_artifact` already supports bounded CSV, Markdown, image, PPTX, and log previews.
- Default V1/V2/MCP responses include omitted-content contracts.
- V1 and V2 cancellation tools exist.
- `scripts/mcp_stdio_smoke.py` lists and exercises V1/V2 tools.
- The repo-scoped Codex plugin skill documents context quarantine.

Current hardening opportunities:

- preview contract can be documented and regression-tested more explicitly across Stage 2 package and Stage 3 messy-result artifacts
- cancellation/recovery confidence can be broadened for V1/V2 mirror paths
- worker audit files can be checked for stability, boundedness, and omission from default responses/packages
- plugin guidance can be improved with concrete delegation examples and anti-patterns
- stdio smoke can assert more of the V2 bounded contract after recent artifact changes

## 4. Non-Goals

Do not implement during this stage:

- Web UI
- FastAPI or hosted service
- remote runner
- cloud sync
- generic multi-agent framework
- autonomous research conclusions
- default cloud AI/provider calls
- unbounded artifact reads
- generic file browser behavior
- automatic interception of every command
- changing CLI `run` safety semantics to match MCP

Stage 4 is host-integration hardening, not platform expansion.

## 5. Work Slice A: Bounded Preview Contract

### Target Behavior

`preview_sidecar_artifact` should remain a bounded preview tool, not a file reader.

Supported previews should be explicitly tested for:

- CSV normalized metrics from Stage 3 messy outputs
- Markdown report snippets
- PNG/JPEG image metadata
- PPTX slide count and summary metadata
- stdout/stderr or log tail with line and character caps
- package metadata files if they are registered artifacts in the future

Required rejection behavior:

- task-external path
- workspace-external path
- unregistered task artifact path
- unsupported artifact suffix
- raw source refs or worker prompt/response bodies
- unbounded row/line requests

### Tests

- Preview caps requested CSV rows and log lines.
- Preview never returns complete artifact bodies.
- Preview rejects external and unregistered paths.
- Preview rejects raw/worker audit content.
- Preview handles Stage 3 generated figure/report/slide artifacts without leaking bytes or full text.

## 6. Work Slice B: Cancellation And Recovery Confidence

### Target Behavior

V1/V2 cancellation should be predictable and bounded:

- running tasks can be cancelled through CLI/MCP/V2 where applicable
- completed tasks return a clear not-applicable response
- missing tasks return a bounded error
- cancellation responses do not include full logs
- stale running tasks are refreshed or failed consistently by existing runner logic

### Tests

- `cancel_sidecar_task` cancels a background task and omits log bodies.
- `cancel_sidecar_task` on completed task reports not applicable.
- MCP `cancel_experiment` and V2 `cancel_sidecar_task` stay consistent.
- Inspect after cancellation returns cancelled status and bounded artifacts.

## 7. Work Slice C: Worker Audit Stability

### Target Behavior

Worker files should be useful for local audit while remaining omitted from default host responses.

Verify:

- `input-bundle.json`, proposal, validator result, adoption record, provider audit files, and diagnostics are task-local
- sandbox remains the only worker-writable area
- default responses omit worker prompt/response bodies
- package export from Stage 2 omits worker audit bodies by default
- previews reject worker prompt/response bodies

### Tests

- V2 delegation creates expected audit files for heuristic or fake-provider flows.
- Default delegate/inspect responses omit worker prompt/response content.
- Preview rejects worker prompt/response paths.
- Package output does not include worker audit or sandbox content by default.

## 8. Work Slice D: Plugin And Host Ergonomics

### Target Behavior

Improve host-facing documentation and plugin guidance so Codex knows when and how to delegate.

Update as needed:

- `plugins/lab-sidecar/skills/use-lab-sidecar/SKILL.md`
- `docs/v2-host-integration.md`
- `docs/mcp-host-config.md`
- README Codex/MCP section

Guidance should include:

- when to use Lab-Sidecar
- when not to delegate
- expected default response shape
- bounded preview examples
- cancellation examples
- package/export relationship after Stage 2
- messy result config relationship after Stage 3

### Tests / Validation

- Plugin validation still passes.
- Docs avoid claims of hosted service, OS sandboxing, malware scanning, or generic multi-agent orchestration.

## 9. Work Slice E: Stdio MCP Smoke Hardening

### Target Behavior

The real stdio smoke should continue to prove that MCP hosts can list and call both V1 and V2 tools.

Potential enhancements:

- assert V2 delegate omitted contract includes worker prompt/response omission
- preview a Stage 3-style normalized metrics artifact if practical
- assert preview row/line caps
- assert blocked command remains blocked
- assert cancellation path remains bounded

### Validation

```bash
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-4-mcp-smoke
```

If smoke changes are made, tests or acceptance evidence must record the exact listed tools, task ids, preview type, and omitted contract.

## 10. Implementation Boundaries

Likely files to edit:

- `lab_sidecar/intelligence/tools.py`
- `lab_sidecar/intelligence/preview.py`
- `lab_sidecar/intelligence/bundle.py`
- `lab_sidecar/mcp/tools.py`
- `scripts/mcp_stdio_smoke.py`
- `tests/test_v2_host_integration.py`
- `tests/test_mcp_tools.py`
- `tests/test_v2_intelligence_scaffold.py`
- `tests/test_v2_heuristic_worker.py`
- `tests/test_v2_worker_invocation.py`
- `plugins/lab-sidecar/skills/use-lab-sidecar/SKILL.md`
- `docs/v2-host-integration.md`
- `docs/mcp-host-config.md`
- `README.md`
- `docs/post-open-source-stage-4-acceptance.md`

Avoid touching unless strictly required:

- collector/figure internals from Stage 3
- package export internals from Stage 2
- slide layout/rendering internals
- CLI command behavior outside docs or shared helper compatibility

## 11. Subagent Guidance For Goal Execution

The implementation agent may use Codex supervisor agents and subagents for independent slices. This is execution coordination only, not Lab-Sidecar product architecture.

Good subagent slices:

- **Preview contract reviewer**: inspect preview code and tests for leaks, caps, and unsupported paths.
- **Cancellation/recovery tester**: exercise V1/V2/MCP cancellation paths and propose focused tests.
- **Worker audit reviewer**: inspect audit files, package omissions, and default response omissions.
- **Plugin/docs implementer**: update skill/docs with delegation examples and anti-patterns.
- **Smoke/validation runner**: run MCP stdio smoke, plugin validation, focused tests, and full tests.

Subagents must:

- preserve unrelated local changes
- keep MCP as a thin adapter
- keep V2 local-first and bounded
- not add hosted services, remote runners, Web UI, default AI analysis, or generic multi-agent features
- not commit generated `.lab-sidecar/` tasks or package outputs

The supervisor remains responsible for scope control, integration, final validation, and acceptance evidence.

## 12. Concrete Acceptance Standards

Stage 4 is complete only when all selected implementation slices satisfy these gates:

1. Default V2 and MCP responses omit full command, stdout, stderr, metrics rows, report bodies, PPT content, artifact bodies, full data files, and worker prompt/response bodies.
2. `preview_sidecar_artifact` remains task-artifact scoped and bounded.
3. External, unregistered, unsupported, raw, and worker-audit preview requests are rejected cleanly.
4. Cancellation through V2/MCP is tested for running tasks and completed/not-applicable tasks.
5. Worker audit files remain task-local and are not leaked by default.
6. Stage 1 CLI navigation, Stage 2 package export, and Stage 3 messy-result collection tests do not regress.
7. Plugin skill and host docs explain delegation boundaries and bounded previews.
8. MCP stdio smoke passes if MCP code or smoke behavior is touched.
9. Plugin validation passes if plugin files are touched.
10. `docs/post-open-source-stage-4-acceptance.md` records implementation scope, commands, workspaces, task ids, smoke results, omitted-contract evidence, and final judgment.

## 13. Validation Commands

Run before acceptance:

```bash
git diff --check
python -m pytest tests/test_mcp_tools.py -q
python -m pytest tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py tests/test_v2_heuristic_worker.py tests/test_v2_worker_invocation.py tests/test_v2_ai_provider.py -q
python -m pytest tests/test_cli_smoke.py -q
python -m pytest -q
```

If MCP or smoke behavior is touched:

```bash
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-4-mcp-smoke
```

If plugin files are touched:

```bash
python /Users/anyuchen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
```

Manual host smoke:

```bash
tmpdir="$(mktemp -d /tmp/lab-sidecar-stage-4-XXXXXX)"
cp -R examples "$tmpdir/examples"
cd "$tmpdir"
python -m lab_sidecar.cli.app init
python - <<'PY'
from lab_sidecar.intelligence import (
    delegate_experiment_artifacts,
    inspect_sidecar_task,
    preview_sidecar_artifact,
    cancel_sidecar_task,
)

workspace = "."
result = delegate_experiment_artifacts(
    workspace_path=workspace,
    user_goal="Stage 4 bounded delegation smoke.",
    result_path="examples/csv-comparison",
    desired_outputs=["metrics", "figures", "report", "slides"],
    intelligent_mode="off",
)
print("delegate", result["task_id"], result["status"], result["omitted"])
inspected = inspect_sidecar_task(workspace, result["task_id"])
csv_path = next(a["path"] for a in inspected["artifacts"] if a["artifact_id"] == "metrics_normalized_csv")
preview = preview_sidecar_artifact(workspace, result["task_id"], csv_path, max_rows=1)
print("preview", preview["preview_type"], preview["preview"].get("row_count_returned"))
cancelled = cancel_sidecar_task(workspace, result["task_id"])
print("cancel", cancelled["status"])
PY
```

The acceptance record must include actual outputs and task ids from any manual smoke.

## 14. Acceptance Record Template

Create `docs/post-open-source-stage-4-acceptance.md` with:

```markdown
# Post-Open-Source Stage 4 Acceptance

## Phase Goal

## Starting State

## Implemented Scope

## Deferred Scope

## Changed Files

## Host And MCP Scenarios

## Workspaces And Task IDs

## Preview Contract Evidence

## Cancellation Evidence

## Worker Audit Evidence

## Plugin / Docs Evidence

## Test Results

## Blocking

## Follow-Up

## Out Of Scope

## Final Judgment
```

## 15. Suggested Goal-Mode Objective

Use this objective when starting the implementation goal:

```text
Implement Lab-Sidecar Post-Open-Source Stage 4: Agent-Native Delegation Hardening.

Read docs/post-open-source-stage-4-plan.md first and treat it as the source of truth. Harden the existing V2/MCP host integration so Codex and MCP hosts can delegate noisy local artifact work, inspect bounded state, preview task artifacts, and cancel tasks without polluting the main Agent context. Focus on bounded preview contract coverage, V1/V2/MCP cancellation confidence, worker audit omission/stability, plugin/Codex host ergonomics, stdio smoke confidence, and acceptance evidence.

You may use Codex supervisor agents and subagents for independent slices such as preview contract review, cancellation/recovery testing, worker audit review, plugin/docs updates, and smoke/validation. Subagents are execution coordination only and must not become Lab-Sidecar product architecture. The supervisor remains responsible for integration, preserving boundaries, and writing docs/post-open-source-stage-4-acceptance.md with evidence.

Stay local-first, file-first, CLI-first, and bounded-delegation-first. Do not add Web UI, FastAPI, hosted services, remote runners, cloud sync, generic multi-agent framework behavior, automatic command interception, default AI analysis, or unbounded file/browser behavior. Keep MCP a thin adapter over local contracts. Avoid changing Stage 1 CLI navigation, Stage 2 package export, Stage 3 collector/figure internals, or slide rendering unless existing tests prove a small compatibility change is required. Do not revert unrelated local changes.

Add focused tests, update plugin/docs where needed, run git diff --check, run V2/MCP focused tests, run `python -m pytest tests/test_cli_smoke.py -q`, run `python -m pytest -q`, run MCP stdio smoke if MCP/smoke files are touched, run plugin validation if plugin files are touched, perform a manual host smoke in a temporary workspace, and finish with a clear final judgment in the acceptance document.
```

## 16. Stage 4 Acceptance Checklist

Before marking the goal complete, confirm:

- [ ] Default responses preserve the omitted-content contract
- [ ] Bounded previews are tested for supported artifact types
- [ ] External/unregistered/raw/worker preview requests are rejected
- [ ] V2/MCP cancellation paths are tested
- [ ] Worker audit files remain task-local and omitted by default
- [ ] Plugin/docs describe when to delegate and when not to delegate
- [ ] MCP stdio smoke passes if relevant files changed
- [ ] Plugin validation passes if plugin files changed
- [ ] Stage 1/2/3 behaviors do not regress
- [ ] focused V2/MCP tests pass
- [ ] full test suite passes
- [ ] manual host smoke is recorded in acceptance
