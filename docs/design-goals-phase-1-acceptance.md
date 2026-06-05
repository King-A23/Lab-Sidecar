# Design Goals Phase 1 Acceptance

Date: 2026-06-05

Phase: Phase 1 - Design Gap Baseline

## Scope

Produce a code-level gap baseline for Lab-Sidecar's current public-alpha implementation against the full V1 design goals in `PRODUCT_ITERATION_PLAN.md` and `docs/design-goals-completion-plan.md`.

This phase did not implement product features.

## Initial Checks

Initial workspace:

```text
C:\code\Lab-Sidecar
```

Initial command:

```powershell
git status --short
```

Result:

```text
(clean)
```

Documents read:

- `AGENTS.md`
- `PRODUCT_ITERATION_PLAN.md`
- `docs/design-goals-completion-plan.md`

Audited areas:

- CLI command surface
- runner/background lifecycle
- collector scanning and config behavior
- figure generation and explicit specs
- report and slides provenance/failure handling
- storage, manifest, SQLite fallback, duplicate artifacts
- MCP response shape, stdio smoke coverage, safety, and missing cancellation
- README, release notes, public-alpha docs, and Phase 6 acceptance wording
- tests covering long/background tasks, context quarantine, explicit config, provenance, duplicates, no-invention, and failure handling

## Changed Files

- `docs/design-goals-gap-matrix.md`
- `docs/design-goals-phase-1-acceptance.md`
- `docs/phase-6-real-product-acceptance.md`

## Commands

Audit commands:

```powershell
git status --short
rg --files
rg -n -- "V1|complete|completed|public alpha|alpha|design goal|Context Quarantine|Delegation|MCP|ready|readiness|acceptance|Phase 6|full|完整|完成|可用|production" README.md docs PRODUCT_ITERATION_PLAN.md
rg -n -- "def test_" tests\test_cli_smoke.py tests\test_mcp_tools.py
rg -n -- "collect.*--config|--config|metrics\.yaml|metric.*mapping|units|source_files|glob" tests lab_sidecar docs scripts
rg -n -- "include_log_tail|log_tail|omitted|full_stdout|full_stderr|preview|cancel_experiment|stdio|mcp_stdio|MCP" tests scripts lab_sidecar
rg -n -- "source_refs|hash|sha256|dependency|python_version|platform|env\.json|command\.txt|provenance|reproduce" tests lab_sidecar
```

Required validation commands:

```powershell
py -3 -m pytest
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-phase1-mcp"
git status --short
```

The MCP stdio smoke is included because the Phase 1 audit covered MCP response shape and stdio evidence, even though Phase 1 did not change MCP code.

## Workspace Paths

Repository:

```text
C:\code\Lab-Sidecar
```

Phase 1 docs:

```text
C:\code\Lab-Sidecar\docs\design-goals-gap-matrix.md
C:\code\Lab-Sidecar\docs\design-goals-phase-1-acceptance.md
```

MCP smoke workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase1-mcp
```

## Task IDs

No Lab-Sidecar CLI task was created inside the repository workspace by Phase 1 documentation work.

The MCP stdio smoke created this temporary task in the external smoke workspace:

- `task_20260605_172244_a5fbad`

## Generated Artifacts

Phase 1 repository artifacts:

- `docs/design-goals-gap-matrix.md`
- `docs/design-goals-phase-1-acceptance.md`

No repository `.lab-sidecar` task artifacts were generated.

The MCP smoke generated temporary artifacts only under the external smoke workspace:

- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase1-mcp\.lab-sidecar\tasks\task_20260605_172244_a5fbad\manifest.json`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase1-mcp\.lab-sidecar\tasks\task_20260605_172244_a5fbad\metrics\normalized_metrics.csv`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase1-mcp\.lab-sidecar\tasks\task_20260605_172244_a5fbad\figures\`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase1-mcp\.lab-sidecar\tasks\task_20260605_172244_a5fbad\reports\report-fragment.md`
- `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-design-phase1-mcp\.lab-sidecar\tasks\task_20260605_172244_a5fbad\slides\presentation-draft.pptx`

## Test Results

Real stdio MCP smoke:

```powershell
py -3 scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-design-phase1-mcp"
```

Result:

```json
{
  "workspace": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-design-phase1-mcp",
  "task_id": "task_20260605_172244_a5fbad",
  "run_status": "running",
  "final_status": "completed",
  "metrics_rows": 5,
  "figure_count": 2,
  "slide_count": 7,
  "blocked_command_status": "blocked",
  "artifact_count": 17,
  "omitted_contract": {
    "full_stdout": "omitted_by_default",
    "full_stderr": "omitted_by_default",
    "metrics_rows": "omitted_by_default",
    "artifact_bodies": "omitted_by_default"
  }
}
```

Full test suite:

```powershell
py -3 -m pytest
```

Result:

- 67 passed in 152.68s.

Final status before commit:

```powershell
git status --short
```

Result:

```text
 M docs/phase-6-real-product-acceptance.md
?? docs/design-goals-gap-matrix.md
?? docs/design-goals-phase-1-acceptance.md
```

## Blocking

- None for Phase 1.

## Follow-Up

Implementation follow-ups are intentionally assigned to later phases:

- Phase 2: background task completion/failure refresh, stale worker recovery, cancellation robustness, external long-task smoke.
- Phase 3: MCP context quarantine hardening and `cancel_experiment` after runner cancellation is stable.
- Phase 4: explicit `collect --config`, metric mappings, source selection, units, and explicit config diagnostics.
- Phase 5: Git/dependency/source-hash provenance and stronger generated-claim traceability.
- Phase 6: final V1 acceptance after Phases 2-5 have blocking count 0.

## Out Of Scope

- Feature implementation.
- New CLI commands or MCP tools.
- Web UI, FastAPI, remote runner, hosted service, AI polishing, animation, or generic multi-agent framework.
- New examples beyond audit evidence.

## Final Judgment

Phase 1 passes. The required gap matrix exists, public documentation overclaim risk was scoped with a Phase 6 note, `py -3 -m pytest` passed, real stdio MCP smoke passed, and final pre-commit `git status --short` contains only the intended Phase 1 documentation changes.

Recommendation: proceed to Phase 2 after committing this Phase 1 baseline. Phase 2 should not start before the Phase 1 commit is complete.
