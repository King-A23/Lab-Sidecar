# Phase 6 Real Product Acceptance

Date: 2026-06-04 19:35 +08:00

Scope: Phase 6 real product effect, safety, usability, reproducibility, and context-isolation convergence. This phase does not expand feature scope beyond validating the current CLI-first and MCP-facing local workflow.

Design-goals note, added during Phase 1 gap baseline on 2026-06-05: this record is an early high-fidelity public-alpha validation record. It is not final proof that the complete V1 design goal in `PRODUCT_ITERATION_PLAN.md` is finished. The controlling completion plan and remaining gaps are tracked in `docs/design-goals-completion-plan.md` and `docs/design-goals-gap-matrix.md`.

Temporary acceptance workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase6-acceptance
```

## Git State At Acceptance

Current worktree contains uncommitted Phase 4.1, Phase 4.2, Phase 5, and Phase 6 changes. The work was not committed during acceptance.

## Test Result

```powershell
py -3 -m pytest
```

Result:

- 64 passed.

## CLI Acceptance Coverage

### simple-success

- Scenario: successful experiment
- Input: `examples/simple-success/train.py`
- Command:

```powershell
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv" --name "phase6 simple success direct"
py -3 -m lab_sidecar.cli.app collect task_20260604_192539_647f36
py -3 -m lab_sidecar.cli.app figures task_20260604_192539_647f36
py -3 -m lab_sidecar.cli.app report task_20260604_192539_647f36
py -3 -m lab_sidecar.cli.app slides task_20260604_192539_647f36
py -3 -m lab_sidecar.cli.app slides task_20260604_192539_647f36
```

- task_id: `task_20260604_192539_647f36`
- status: `completed`
- exit_code: 0
- task directory:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase6-acceptance\.lab-sidecar\tasks\task_20260604_192539_647f36
```

- metrics rows: 5
- metrics candidate provenance: `run_working_dir:metrics.csv`
- figures: 2
- report template: `zh-lab`
- slides: 7
- repeated slides run: no duplicate artifact IDs
- artifact count: 17

### csv-comparison

- Scenario: multi-result comparison
- Input: `examples/csv-comparison`
- Command:

```powershell
py -3 -m lab_sidecar.cli.app ingest examples/csv-comparison --name "phase6 csv comparison"
py -3 -m lab_sidecar.cli.app collect task_20260604_192601_ad0827
py -3 -m lab_sidecar.cli.app figures task_20260604_192601_ad0827
py -3 -m lab_sidecar.cli.app report task_20260604_192601_ad0827
py -3 -m lab_sidecar.cli.app slides task_20260604_192601_ad0827
```

- task_id: `task_20260604_192601_ad0827`
- status: `completed`
- exit_code: 0
- task directory:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase6-acceptance\.lab-sidecar\tasks\task_20260604_192601_ad0827
```

- metrics rows: 15
- metrics candidate provenance:
  - `source_refs:examples/csv-comparison/baseline.csv`
  - `source_refs:examples/csv-comparison/model_a.csv`
  - `source_refs:examples/csv-comparison/model_b.csv`
- figures: 2
- report template: `zh-lab`
- slides: 7
- artifact count: 16

### project-presentation-pack

- Scenario: course project presentation
- Input: `examples/project-presentation-pack`
- Command:

```powershell
py -3 -m lab_sidecar.cli.app ingest examples/project-presentation-pack --name "phase6 project presentation pack"
py -3 -m lab_sidecar.cli.app collect task_20260604_192617_b65149
py -3 -m lab_sidecar.cli.app figures task_20260604_192617_b65149
py -3 -m lab_sidecar.cli.app report task_20260604_192617_b65149
py -3 -m lab_sidecar.cli.app slides task_20260604_192617_b65149 --template zh-project
```

- task_id: `task_20260604_192617_b65149`
- status: `completed`
- exit_code: 0
- task directory:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase6-acceptance\.lab-sidecar\tasks\task_20260604_192617_b65149
```

- metrics rows: 16
- metrics candidate provenance:
  - `source_refs:examples/project-presentation-pack/ablation.json`
  - `source_refs:examples/project-presentation-pack/final_metrics.csv`
  - `source_refs:examples/project-presentation-pack/weekly_metrics.csv`
- figures: 1
- report template: `zh-lab`
- slides: 7
- artifact count: 14

### simple-failure

- Scenario: failed experiment diagnosis
- Input: `examples/simple-failure/fail.py`
- Command:

```powershell
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-failure/fail.py" --name "phase6 simple failure"
py -3 -m lab_sidecar.cli.app slides task_20260604_192631_799cd8
py -3 -m lab_sidecar.cli.app report task_20260604_192631_799cd8
```

- task_id: `task_20260604_192631_799cd8`
- status: `failed`
- exit_code: 1
- task directory:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-phase6-acceptance\.lab-sidecar\tasks\task_20260604_192631_799cd8
```

- report template: `zh-lab`
- slides: 5
- failure summary includes `FileNotFoundError`
- artifact count: 8

## Key Artifacts

For each completed task:

- `manifest.json`
- `metrics/normalized_metrics.csv`
- `metrics/normalized_metrics.json`
- `metrics/collection-summary.json`
- `figures/figure-spec.yaml`
- `figures/figure-summary.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

For the failed task:

- `manifest.json`
- `stdout.log`
- `stderr.log`
- `reproduce/command.txt`
- `reproduce/env.json`
- `reports/report-fragment.md`
- `reports/report-summary.json`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

Artifact audit result:

- no duplicate artifact IDs in all 4 task manifests
- no missing artifact paths in all 4 task manifests
- report and slide artifacts include source artifact references

## MCP / Main Agent Context Isolation

Initial Phase 6 validation used `LabSidecarMCPTools` because the optional MCP SDK was not installed at that time. Public alpha readiness on 2026-06-05 added `.[mcp]`, pinned `mcp==1.27.2`, and completed a real stdio MCP client/server smoke with `scripts/mcp_stdio_smoke.py`.

Real stdio smoke result:

- workspace: `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-mcp-stdio-smoke`
- tools listed and called: `run_experiment`, `inspect_results`, `make_figures`, `generate_report_fragment`, `generate_slides`
- task_id: `task_20260605_014548_a77a2c`
- `run_experiment(background=True)` returned `running`
- final status after `inspect_results` polling: `completed`
- metrics rows: 5
- figures: 2
- slides: 7
- destructive command smoke: `blocked`
- artifact count: 17

For all four acceptance tasks:

- `inspect_results` returned task status, compact summary, and artifact list.
- `log_tail` was absent by default.
- `omitted` included:

```json
{
  "full_stdout": "omitted_by_default",
  "full_stderr": "omitted_by_default",
  "metrics_rows": "omitted_by_default",
  "artifact_bodies": "omitted_by_default"
}
```

Observed MCP artifact counts:

- simple-success: 17
- csv-comparison: 16
- project-presentation-pack: 14
- simple-failure: 8

Failure MCP inspection:

- failed task returned status `failed`
- failure summary included `FileNotFoundError`
- full stderr was not returned by default

Dangerous command smoke:

```text
Remove-Item -Recurse .
```

Result:

- `blocked`
- reason: `blocked pattern: \bremove-item\b`

## PPTX Render And Visual Acceptance

Rendering tools:

- LibreOffice: `C:\Program Files\LibreOffice\program\soffice.com`
- Poppler: `pdftoppm`

Render command pattern:

```powershell
& "C:\Program Files\LibreOffice\program\soffice.com" --headless --convert-to pdf --outdir <render_dir> <presentation-draft.pptx>
pdftoppm -jpeg -r 120 <presentation-draft.pdf> <render_dir>\slide
```

LibreOffice emitted `Could not find platform independent libraries <prefix>` after conversions, but all PDFs and JPGs were generated.

Rendered outputs:

| Scenario | PDF | JPG count | Summary slide_count | Contact sheet |
| --- | --- | ---: | ---: | --- |
| simple-success | yes | 7 | 7 | `rendered-simple-success/contact-sheet.jpg` |
| csv-comparison | yes | 7 | 7 | `rendered-csv-comparison/contact-sheet.jpg` |
| project-presentation-pack | yes | 7 | 7 | `rendered-project-presentation-pack/contact-sheet.jpg` |
| simple-failure | yes | 5 | 5 | `rendered-simple-failure/contact-sheet.jpg` |

Visual acceptance observations:

- no blank pages
- slide titles are readable
- Chinese text rendered without obvious garbling
- tables do not visibly overflow slide bounds
- figures are visible and not clipped in a blocking way
- captions and footers do not visibly overlap with main content
- failed task deck clearly shows `failed`, exit code, and stderr summary
- project deck uses bounded labels; long label truncation remains a follow-up, not a blocking defect

All `slides-summary.json` QA checks passed for all four decks:

- `slide_count`
- `empty_slide_check`
- `title_check`
- `artifact_duplicate_check`
- `table_overflow_guard`
- `caption_overflow_guard`

## Safety And Reliability Checks

- CLI generated files under `.lab-sidecar/tasks/<task_id>/`.
- `ingest` preserved source example directories and used source references.
- `run` created a new task directory instead of reusing an old task directory.
- `collect` recorded source provenance in `collection-summary.json`.
- bad JSON, empty CSV, and missing metric columns now record diagnostics in `collection-summary.json` without writing normalized metrics outputs.
- `figures`, `report`, and `slides` recorded source artifacts in manifests or summary files.
- repeated `slides` did not duplicate manifest artifacts.
- failed task preserved exit code, stderr, command, and failure summary.
- MCP-facing command execution blocks destructive command patterns.
- MCP-facing cwd outside workspace is covered by tests.
- MCP-facing workspace-external absolute output/path arguments are covered by tests.
- The safety gate applies to MCP-facing `run_experiment`; CLI `run` remains a user-explicit local command execution path.
- complete logs and artifact bodies are omitted by default from MCP-facing responses.

## Blocking

- None.

## Follow-Up

- Test concrete host configuration files in individual hosts such as Claude Desktop or Codex; only a generic stdio shape is documented now.
- Add `cancel_experiment` or an equivalent MCP cancellation tool.
- Add policy configuration for allowed command prefixes and confirmation behavior.
- Improve project figure grouping to avoid `(missing)` labels in mixed metrics.
- Improve long variant/card text wrapping in project comparison slides.
- Add more real-world malformed-result fixtures beyond the current bad JSON, empty CSV, and missing metric column regression tests.

## Out Of Scope

- Web UI, FastAPI, remote execution, multi-user permissions.
- AI automatic analysis, report polishing, or conclusion generation.
- Animation, video, GIF, Manim, Remotion, and PowerPoint native animation.
- Returning full logs, complete metrics rows, complete report Markdown, or PPT contents through MCP responses.
- Publishing packaging or GitHub release work.

## Final Judgment

Phase 6 real product acceptance passes with blocking 0.

Lab-Sidecar now demonstrates the intended local-first product workflow across success, failure, multi-result comparison, and course project presentation scenarios. CLI direct usage works, MCP-facing summary isolation is verified at both the tool-adapter layer and real stdio MCP client/server layer, artifacts are reproducible and traceable, PPTX outputs render to PDF/JPG, and safety defaults are conservative for command execution through the MCP-facing adapter.

The project is suitable for a cautious public alpha after final release hygiene and commit organization. Host-specific MCP setup, cancellation, richer policy configuration, and broader malformed real-world fixtures remain follow-up work rather than blocking issues.
