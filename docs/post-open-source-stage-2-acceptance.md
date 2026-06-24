# Post-Open-Source Stage 2 Acceptance: Deliverable Result Packages

Date: 2026-06-17

## Scope

Implemented the Stage 2 local CLI packaging path:

```bash
labsidecar package <task_id> --output <dir>
```

The command creates one shareable, inspectable package directory for one Lab-Sidecar task. It stays local-first, file-first, and CLI-first. No Web UI, FastAPI service, remote runner, cloud sync, hosted service, default AI behavior, multi-task package grouping, statistical interpretation, or generic multi-agent runtime feature was added.

## Implementation Evidence

Changed implementation files:

- `lab_sidecar/cli/app.py`
- `lab_sidecar/storage/package_export.py`
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`

The package exporter uses an explicit allowlist. It includes the package README, copied `manifest.json`, `package-summary.json`, `artifact-index.json`, `redaction-notes.md`, reproduce metadata when present, generated normalized metrics when present, generated figure PNG/SVG and figure metadata when present, generated report artifacts when present, and generated slide artifacts when present.

Default omissions are recorded in `artifact-index.json` and `redaction-notes.md`. Full `stdout.log`, full `stderr.log`, raw source refs, raw source files, local SQLite indexes, worker logs/transcripts, worker prompt/response audit bodies, sandbox directories, and unrelated workspace files are not copied by default.

Failed tasks are exported as diagnostic packages. The README title and body label them as failed-task diagnostic packages rather than successful experiment summaries, and the bounded failure summary is included from the manifest.

## Automated Validation

Environment:

- Repository: `<repo>`
- Python: repo `.venv`, Python 3.12.13

Commands:

```bash
git diff --check
source .venv/bin/activate && python -m pytest tests/test_cli_smoke.py -q
source .venv/bin/activate && python -m pytest -q
```

Results:

- `git diff --check`: passed
- `python -m pytest tests/test_cli_smoke.py -q`: passed, 82 tests
- `python -m pytest -q`: passed, 127 tests

Focused coverage added:

- completed run task package includes required package metadata and generated metrics/figures/report/slides artifacts
- package omits full stdout/stderr, local SQLite index, worker log, worker prompt/response bodies, sandbox files, unrelated workspace files, and loose run output by default
- failed task package is diagnostic and includes bounded failure summary without full logs
- ingested task package omits `raw/source_refs.json` and raw source files by default
- missing task returns exit code 3
- invalid output file and non-empty output directory return clear output path errors
- missing optional artifacts are recorded as unavailable

## Manual Smoke Evidence

Temporary workspace:

```text
/tmp/lab-sidecar-stage2-smoke-sPwpol
```

Success task:

```text
task_20260617_223638_29c406
```

Success package:

```text
/tmp/lab-sidecar-stage2-smoke-sPwpol/lab-sidecar-package-task_20260617_223638_29c406
```

Success package command output:

```text
Package created: /private/tmp/lab-sidecar-stage2-smoke-sPwpol/lab-sidecar-package-task_20260617_223638_29c406
Type: result
Included files: 18
Omitted by default: 4
Unavailable optional files: 0
```

Success package files inspected:

```text
README.md
artifact-index.json
figures/figure-spec.yaml
figures/figure-summary.json
figures/line_train_loss_over_epoch.png
figures/line_train_loss_over_epoch.svg
figures/line_val_accuracy_over_epoch.png
figures/line_val_accuracy_over_epoch.svg
manifest.json
metrics/collection-summary.json
metrics/normalized_metrics.csv
metrics/normalized_metrics.json
package-summary.json
redaction-notes.md
reports/report-fragment.md
reports/report-summary.json
reproduce/command.txt
reproduce/dependencies.json
reproduce/env.json
reproduce/git.json
slides/presentation-draft.pptx
slides/slides-summary.json
```

Default omission inspection for success package:

```text
absent stdout.log
absent stderr.log
absent raw/source_refs.json
absent .lab-sidecar/index.sqlite
absent examples
absent metrics.csv
absent worker.log
absent intelligence
```

Failure task:

```text
task_20260617_223641_4dfae9
```

Failure package:

```text
/tmp/lab-sidecar-stage2-smoke-sPwpol/lab-sidecar-package-task_20260617_223641_4dfae9
```

Failure package command output:

```text
Package created: /private/tmp/lab-sidecar-stage2-smoke-sPwpol/lab-sidecar-package-task_20260617_223641_4dfae9
Type: diagnostic
Included files: 5
Omitted by default: 4
Unavailable optional files: 9
```

Failure README inspection confirmed:

- title is `Failed Task Diagnostic Package`
- body states it is not a successful experiment summary
- status is `failed`
- bounded failure summary includes `FileNotFoundError`
- full stderr/stdout logs are not copied

Failure `artifact-index.json` inspection confirmed:

```text
package_type: diagnostic
unavailable includes:
- metrics/normalized_metrics.csv
- metrics/normalized_metrics.json
- metrics/collection-summary.json
- figures/figure-spec.yaml
- figures/figure-summary.json
omitted includes:
- stdout.log
- stderr.log
- .lab-sidecar/index.sqlite
- workspace/*
```

## Acceptance Checklist

1. `labsidecar package <task_id> --output <dir>` creates a shareable package directory: pass.
2. Successful tasks include manifest, reproduce metadata, generated metrics, figures, report, slides, and package summaries when present: pass.
3. Failed tasks produce diagnostic packages without successful-summary wording: pass.
4. Package output includes `README.md`, `package-summary.json`, `artifact-index.json`, and `redaction-notes.md`: pass.
5. Full stdout/stderr and raw source files are omitted by default: pass.
6. Missing optional artifacts are recorded as unavailable rather than causing package failure: pass.
7. Missing task returns exit code 3: pass.
8. Invalid output path or write failure returns a clear error: pass for invalid file path and non-empty directory.
9. README and CLI spec document the command and omission policy: pass.
10. Focused tests and full test suite pass: pass.
11. Acceptance evidence records commands, workspace, task ids, package paths, validation results, and final judgment: pass.

## Final Judgment

Stage 2 passes. The implemented packaging path delivers one local single-task result or diagnostic package using an explicit allowlist, records unavailable and omitted files, avoids copying full logs or raw workspace content by default, and preserves the existing `run -> collect -> figures -> report -> slides` workflow.
