# Post-Open-Source Stage 2 Plan: Deliverable Result Packages

Date: 2026-06-17

## 1. Phase Goal

Add a local CLI packaging path that turns one Lab-Sidecar task into a shareable, inspectable result package.

After Stage 2, a user should be able to run:

```bash
labsidecar package <task_id> --output <dir>
```

and hand the resulting folder to another person or Agent. The recipient should understand:

- what task was run or ingested
- which artifacts are included
- how to reproduce or inspect the run
- which files were intentionally omitted
- whether the package represents a successful result or a failure diagnostic

This stage is local-first, file-first, and CLI-first. It must not add Web UI, FastAPI, remote runners, cloud sync, hosted services, or default AI behavior.

## 2. Product Promise

Stage 1 made tasks easier to find, summarize, and compare. Stage 2 makes a task easier to deliver.

The package should feel like a small, self-contained artifact folder, not a hidden implementation dump. It should be readable by a human and safe enough to hand to a classmate, advisor, reviewer, or main Agent without accidentally including full logs or unrelated raw inputs by default.

## 3. Current Baseline

Current useful surface:

- task-local manifests and artifacts live under `.lab-sidecar/tasks/<task_id>/`
- `artifacts <task_id>` lists manifest artifacts
- `open <task_id>` prints the artifact directory
- `summarize <task_id>` provides a bounded task digest after Stage 1
- reports, figures, metrics, slides, and reproduce metadata are already task-local

Current gaps:

- there is no single command to create a shareable package
- task-local directories include internal working files that are not always suitable for sharing
- there is no package-level README or artifact index
- stdout/stderr and raw source refs need an explicit default omission policy
- failed tasks need a diagnostic package shape rather than being treated as successful experiment packages

## 4. Non-Goals

Do not implement during this stage:

- remote upload or sharing
- cloud sync
- Web UI
- FastAPI or hosted service
- multi-task package groups
- statistical interpretation
- AI-written conclusions
- raw source file copying by default
- full stdout/stderr copying by default
- changing existing task artifact layout
- changing existing `run -> collect -> figures -> report -> slides` behavior

Multi-task packages can be considered later after single-task packaging is stable.

## 5. Expected CLI

Minimum command:

```bash
labsidecar package <task_id> --output <dir>
```

Suggested options:

```bash
labsidecar package <task_id> --output <dir>
labsidecar package <task_id> --output <dir> --zip
labsidecar package <task_id> --output <dir> --include-logs
```

Accepted Stage 2 minimum:

- `--output <dir>` is required or defaults to a clear generated directory under the current workspace
- `--zip` is optional but useful if it stays simple
- `--include-logs` may be deferred if the omission policy is documented clearly

If `--include-logs` is implemented, it must be explicit and tested.

## 6. Package Shape

Recommended folder layout:

```text
lab-sidecar-package-<task_id>/
  README.md
  manifest.json
  package-summary.json
  artifact-index.json
  redaction-notes.md
  reproduce/
  metrics/
  figures/
  reports/
  slides/
```

Default includes:

- `manifest.json`
- `reproduce/command.txt`
- `reproduce/env.json`
- `reproduce/git.json` when present
- `reproduce/dependencies.json` when present
- `metrics/normalized_metrics.csv` when present
- `metrics/normalized_metrics.json` when present
- `metrics/collection-summary.json` when present
- generated figure PNG/SVG files when present
- `figures/figure-spec.yaml` and `figures/figure-summary.json` when present
- `reports/report-fragment.md` and `reports/report-summary.json` when present
- `slides/presentation-draft.pptx` and `slides/slides-summary.json` when present

Default omissions:

- full `stdout.log`
- full `stderr.log`
- raw source files
- `.lab-sidecar/index.sqlite`
- worker prompt/response bodies
- temporary sandbox files
- unrelated workspace files

`redaction-notes.md` should explain the omission policy plainly.

## 7. Successful Task Package

For a completed task, the package README should include:

- task id
- task name when present
- task status
- command preview or source path
- included artifact summary
- reproduce entrypoints
- omission notes

It should not write new research conclusions. It may point to existing report and slide artifacts.

## 8. Failed Task Diagnostic Package

For a failed task, the package should still be useful.

Default includes:

- manifest
- reproduce metadata
- failure summary from manifest
- report/slides diagnostic artifacts when present
- stderr path reference or bounded diagnostic note

Default behavior should not copy full stderr unless a future explicit flag allows it.

The README must clearly mark the package as a failed-task diagnostic package, not a successful experiment summary.

## 9. Implementation Boundaries

Likely files to edit:

- `lab_sidecar/cli/app.py`
- `lab_sidecar/` package/export helper module if useful
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`
- `docs/post-open-source-stage-2-acceptance.md`

Recommended helper location if the logic grows beyond a few functions:

- `lab_sidecar/storage/package_export.py`

Avoid touching:

- `lab_sidecar/mcp/`
- `lab_sidecar/intelligence/`
- report/slides rendering internals
- SQLite schema unless strictly necessary

## 10. Subagent Guidance For Goal Execution

The implementation agent may use Codex supervisor agents and subagents to parallelize work. This is execution coordination only. It is not Lab-Sidecar product architecture.

Good subagent slices:

- **Package design reviewer**: review package structure, omission policy, and overclaim risk.
- **CLI/test implementer**: implement the command and focused CLI tests.
- **Docs implementer**: update README, CLI spec, and package user-facing language.
- **Validation runner**: run focused tests, full tests, manual smoke, and inspect generated package contents.

Subagents must follow repository boundaries:

- do not revert unrelated local changes
- do not modify MCP or intelligence code unless the supervisor explicitly determines it is required
- do not add Web UI, FastAPI, remote runner, hosted service, or default AI behavior
- do not commit generated `.lab-sidecar/` task directories or package output folders
- do not turn subagent usage into a Lab-Sidecar runtime feature

The supervisor remains responsible for final decisions, integration, acceptance evidence, and final judgment.

## 11. Concrete Acceptance Standards

Stage 2 is complete only when all of the following are true:

1. `labsidecar package <task_id> --output <dir>` creates a shareable package directory.
2. Successful tasks include manifest, reproduce metadata, generated metrics, figures, report, slides, and package summaries when those artifacts exist.
3. Failed tasks can produce diagnostic packages without being described as successful experiment results.
4. Package output includes `README.md`, `package-summary.json`, `artifact-index.json`, and `redaction-notes.md`.
5. Full stdout/stderr and raw source files are omitted by default.
6. Missing optional artifacts are recorded as omitted or unavailable rather than causing package failure.
7. Missing task returns exit code 3.
8. Invalid output path or write failure returns a clear error.
9. README and CLI spec document the new command and omission policy.
10. Focused tests and full test suite pass.
11. `docs/post-open-source-stage-2-acceptance.md` records commands, workspace, task ids, package paths, validation results, and final judgment.

## 12. Validation Commands

Run before acceptance:

```bash
git diff --check
python -m pytest tests/test_cli_smoke.py -q
python -m pytest -q
```

If packaging implementation touches MCP/V2 response helpers, also run:

```bash
python -m pytest tests/test_mcp_tools.py -q
python -m pytest tests/test_v2_host_integration.py tests/test_v2_worker_invocation.py -q
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-2-mcp-smoke
```

Manual smoke:

```bash
tmpdir="$(mktemp -d /tmp/lab-sidecar-stage-2-XXXXXX)"
cp -R examples "$tmpdir/examples"
cd "$tmpdir"
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv" --name "stage2 simple"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-success
find package-success -maxdepth 3 -type f | sort
```

Failed-task smoke:

```bash
python -m lab_sidecar.cli.app run "python examples/simple-failure/fail.py" --name "stage2 failure"
python -m lab_sidecar.cli.app report <failed_task_id>
python -m lab_sidecar.cli.app slides <failed_task_id>
python -m lab_sidecar.cli.app package <failed_task_id> --output package-failure
find package-failure -maxdepth 3 -type f | sort
```

Repository hygiene:

```bash
find . -path '*/.lab-sidecar/*' -print | head -n 20
find . -name 'lab-sidecar-package-*' -o -name 'package-success' -o -name 'package-failure'
```

Generated package folders from manual smoke should stay in temporary workspaces, not the repository.

## 13. Acceptance Record Template

Create `docs/post-open-source-stage-2-acceptance.md` with:

```markdown
# Post-Open-Source Stage 2 Acceptance

## Phase Goal

## Starting State

## Changed Files

## CLI Scenarios

## Workspaces And Task IDs

## Package Outputs

## Omission Policy Verification

## Test Results

## Blocking

## Follow-Up

## Out Of Scope

## Final Judgment
```

## 14. Suggested Goal-Mode Objective

Use this objective when starting the implementation goal:

```text
Implement Lab-Sidecar Post-Open-Source Stage 2: Deliverable Result Packages.

Read docs/post-open-source-stage-2-plan.md first and treat it as the source of truth. Add a local CLI packaging path so a user can run `labsidecar package <task_id> --output <dir>` and receive a shareable, inspectable result package for one Lab-Sidecar task. The package must include README.md, manifest.json, package-summary.json, artifact-index.json, redaction-notes.md, reproduce metadata, and generated metrics/figures/report/slides artifacts when present. Full stdout/stderr, raw source files, SQLite indexes, worker transcripts, sandbox files, and unrelated workspace files must be omitted by default. Failed tasks must package as diagnostic packages, not successful experiment summaries.

You may use Codex supervisor agents and subagents for independent implementation slices, such as package design review, CLI/test implementation, documentation updates, and validation. Subagents are execution coordination only and must not become Lab-Sidecar product architecture. The supervisor remains responsible for integrating changes, preserving repository boundaries, and writing docs/post-open-source-stage-2-acceptance.md with evidence.

Stay local-first, file-first, and CLI-first. Do not add Web UI, FastAPI, remote runners, cloud sync, hosted services, default AI behavior, multi-task package groups, statistical interpretation, or generic multi-agent features. Avoid lab_sidecar/mcp and lab_sidecar/intelligence unless existing tests prove a small shared helper change is required. Do not revert unrelated local changes.

Add focused tests, update README.md and docs/cli-spec.md, run git diff --check, run `python -m pytest tests/test_cli_smoke.py -q`, run `python -m pytest -q`, perform manual success and failure package smokes in a temporary workspace, verify omitted files are not packaged by default, and finish with a clear final judgment in the acceptance document.
```

## 15. Stage 2 Acceptance Checklist

Before marking the goal complete, confirm:

- [ ] `package` creates a package directory for a completed task
- [ ] `package` creates a diagnostic package for a failed task
- [ ] package includes README, manifest, package summary, artifact index, and redaction notes
- [ ] generated metrics, figures, reports, slides, and reproduce metadata are included when present
- [ ] full stdout/stderr are omitted by default
- [ ] raw source files are omitted by default
- [ ] missing optional artifacts do not fail the package command
- [ ] missing task and invalid output errors are clear
- [ ] README and CLI spec document the command
- [ ] `tests/test_cli_smoke.py` passes
- [ ] full test suite passes
- [ ] manual package smokes are recorded in the acceptance doc
