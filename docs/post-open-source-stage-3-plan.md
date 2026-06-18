# Post-Open-Source Stage 3 Plan: Messy Result Adaptation

Date: 2026-06-17

## 1. Phase Goal

Deepen Lab-Sidecar's ability to normalize messy, real-world local result directories without weakening the current deterministic artifact pipeline.

After Stage 3, a user should be able to ingest a non-demo result directory, provide a small metrics config when needed, and reliably get:

- `metrics/normalized_metrics.csv`
- `metrics/collection-summary.json`
- usable figure specs and figures
- clear diagnostics for missing files, missing fields, unsupported sources, unit conflicts, and non-comparable columns

This stage builds on the existing `collect --config` implementation. It is not a rewrite.

## 2. Product Promise

Stage 1 made tasks easier to find and compare. Stage 2 made tasks easier to package and share. Stage 3 makes Lab-Sidecar more useful on real experiment outputs that are not shaped like the demo fixtures.

The goal is not to support every arbitrary data format. The goal is to give common messy inputs a clear deterministic path:

- if Lab-Sidecar can parse the inputs, normalize them
- if it cannot parse them safely, explain what the user should configure or fix
- if the input is ambiguous, prefer explicit config and diagnostics over guessing

## 3. Current Baseline

Current collector/config behavior:

- `collect` auto-discovers CSV/JSON candidates from task directories, source refs, and conservative run working-directory top-level files.
- `collect --config` supports explicit sources, including source objects with `path` or `glob`.
- Config field mappings can map nonstandard source columns to normalized target names.
- Config supports units and records them in `collection-summary.json`.
- Missing configured fields fail with persisted diagnostics.
- Explicit figure specs can use mapped fields.
- Source refs include hashes and top-level candidate files for ingested sources.

Current gaps:

- `source_refs.json` only records top-level children for ingested directories; nested real result directories are weakly represented.
- Config source selection does not yet support explicit `include` / `exclude` lists as first-class config fields.
- Field aliases are useful but not documented as a stable config capability for messy inputs.
- Unit conflicts across files are not yet diagnosed strongly.
- Multi-seed / model / method normalization is mostly structural, not accepted against richer messy fixtures.
- Minimal log parsing is not implemented even though `.log` and `.txt` may appear in source refs.
- Figure planning does not yet consume units or config grouping metadata for better labels.

## 4. Non-Goals

Do not implement during this stage:

- Web UI
- FastAPI or hosted service
- remote runner
- cloud sync
- default AI analysis
- automatic scientific conclusions
- statistical significance testing
- TensorBoard event parsing
- arbitrary binary format parsing
- general notebook execution
- recursive auto-scan of entire workspaces without explicit config
- changing existing task artifact layout
- changing existing `run -> collect -> figures -> report -> slides -> package` behavior

Recursive or broad discovery is allowed only when the user explicitly declares sources in config.

## 5. Target Metrics Config Shape

Stage 3 should keep the current config shape compatible and add only conservative extensions.

Supported baseline:

```yaml
sources:
  - results/**/*.csv
fields:
  epoch: iter
  method: algo
  seed: trial
  accuracy: score_pct
units:
  accuracy: ratio
```

Recommended Stage 3 extensions:

```yaml
sources:
  include:
    - results/**/*.csv
    - logs/train.log
  exclude:
    - results/**/debug*.csv
    - results/**/scratch/*
fields:
  epoch:
    sources: [epoch, step, iter]
  method:
    sources: [model, method, algo, variant]
  seed:
    sources: [seed, trial, run_id]
  accuracy:
    sources: [val_accuracy, score_pct, acc]
    unit: ratio
  latency_ms:
    sources: [runtime_ms, latency_ms, time_ms]
    unit: ms
groups:
  primary: method
  secondary: seed
logs:
  patterns:
    - file: logs/train.log
      fields:
        epoch: "epoch=(?P<epoch>\\d+)"
        accuracy: "val_accuracy=(?P<accuracy>[0-9.]+)"
```

The implementation may choose a smaller first slice, but must preserve compatibility with existing string/list source entries and existing `fields` / `units` behavior.

## 6. Work Slice A: Source Selection And Source Refs

### Target Behavior

Improve messy source selection while preserving safe defaults.

Stage 3 should support:

- explicit recursive source globs in config
- optional include/exclude config source lists
- nested ingested directory source refs sufficient for explicit config validation
- clear diagnostics for configured sources outside the workspace or outside the ingested source refs

### Implementation Notes

- Keep auto discovery conservative.
- Do not recursively scan large workspaces unless config asks for it.
- If source refs become recursive, cap or summarize safely to avoid huge `source_refs.json` files.
- Preserve hashes for candidate files that are recorded.

### Tests

- Config include selects nested CSV files under an ingested directory.
- Config exclude omits debug/scratch files.
- Config source outside workspace is rejected with diagnostics.
- Config source not in ingested source refs is rejected for ingest tasks.
- Missing configured source writes `collection-summary.json` with actionable warnings.

## 7. Work Slice B: Field Aliases And Normalization

### Target Behavior

Make explicit field mapping more ergonomic for common messy outputs.

Stage 3 should support:

- multiple source aliases per target field
- stable normalized target fields for `epoch`, `step`, `method`, `model`, `variant`, `seed`, `accuracy`, `loss`, `f1`, `runtime_ms`, `latency_ms`, `memory_mb`
- summary output that records which source field actually matched

### Implementation Notes

- Preserve current `fields: target: source` behavior.
- Prefer exact source field names over fuzzy inference when config is provided.
- If more than one alias exists in a row, record deterministic precedence.
- Do not silently create numeric values from non-numeric strings beyond current CSV/JSON behavior unless explicitly tested.

### Tests

- Aliases map `algo` to `method`, `trial` to `seed`, and `score_pct` to `accuracy`.
- Row-level mapped source fields are summarized or file-level matched aliases are recorded.
- Missing all aliases for a target fails with `missing_configured_field`.
- Repeated collection is stable and does not duplicate artifacts.

## 8. Work Slice C: Unit Diagnostics

### Target Behavior

Make unit handling more trustworthy.

Stage 3 should detect and report:

- configured units per normalized field
- conflicting configured units for the same normalized field
- obvious mixed-unit source names when mapped to one target, for example `runtime_s` and `runtime_ms`

### Implementation Notes

- Keep unit conversion out of scope unless explicitly implemented with tests.
- Prefer refusal or warnings over silent conversion.
- Record unit diagnostics in `collection-summary.json`.

### Tests

- Consistent units are recorded in summary.
- Conflicting units fail or warn with clear diagnostics.
- Mixed source aliases such as `runtime_s` and `runtime_ms` mapped to `runtime_ms` are flagged unless the config explicitly resolves them.

## 9. Work Slice D: Multi-Seed / Method Acceptance

### Target Behavior

Make a realistic multi-seed, multi-method result directory work end to end.

The accepted path should be:

```text
ingest messy-results
  -> collect --config metrics.yaml
  -> figures --spec figure.yaml or auto figures
  -> report
  -> package
```

### Implementation Notes

- The normalized metrics table should keep `method` and `seed` fields when configured.
- Auto figures may remain simple, but explicit figure specs must work cleanly with mapped fields.
- Do not claim statistical significance or model superiority.

### Tests

- Fixture with at least 2 methods and 3 seeds normalizes correctly.
- Figure spec can plot mapped `accuracy` by `epoch`, grouped by `method`.
- `compare` from Stage 1 can compare packaged or collected tasks without regression.

## 10. Work Slice E: Minimal Log Parsing

### Target Behavior

Add a small, explicit log parsing path only if it can stay deterministic and bounded.

Recommended first slice:

- parse configured log files only
- regex patterns must be declared in config
- named capture groups produce normalized fields
- each matching log line becomes one row

Example:

```yaml
sources:
  include:
    - logs/train.log
logs:
  patterns:
    - file: logs/train.log
      fields:
        epoch: "epoch=(?P<epoch>\\d+)"
        loss: "loss=(?P<loss>[0-9.]+)"
        accuracy: "val_accuracy=(?P<accuracy>[0-9.]+)"
```

### Non-Goals For Logs

- no arbitrary natural-language log understanding
- no AI log interpretation
- no full stderr parsing by default
- no recursive log scanning without config

### Tests

- Configured log parser extracts epoch/loss/accuracy rows.
- Bad regex fails at config load or collection time with clear diagnostics.
- Log source outside task scope is rejected.
- Log parsing does not read or return full logs in CLI output.

If log parsing is too large for one implementation pass, the Stage 3 implementation may defer it, but the acceptance document must record the deferral and why.

## 11. Work Slice F: Figure Spec Alignment

### Target Behavior

Make figures better reflect normalized config output.

Possible improvements:

- figure summaries include units when known
- figure labels use normalized friendly labels and units
- explicit figure specs fail clearly when referencing unmapped or missing fields
- auto figure planning prefers configured group fields when available

### Tests

- Explicit spec using mapped fields works.
- Missing mapped field fails with exit code 5 and persisted figure summary diagnostics where applicable.
- Figure summary records units when metrics summary has them.

## 12. Implementation Boundaries

Likely files to edit:

- `lab_sidecar/collectors/config.py`
- `lab_sidecar/collectors/service.py`
- `lab_sidecar/collectors/scan.py`
- `lab_sidecar/storage/artifact_store.py`
- `lab_sidecar/figures/specs.py`
- `lab_sidecar/figures/service.py`
- `tests/test_cli_smoke.py`
- `README.md`
- `docs/cli-spec.md`
- `docs/post-open-source-stage-3-acceptance.md`

Optional new helper modules:

- `lab_sidecar/collectors/log_collector.py`
- `lab_sidecar/collectors/source_selection.py`

Avoid touching unless strictly required:

- `lab_sidecar/mcp/`
- `lab_sidecar/intelligence/`
- slides rendering internals
- package export internals
- runner process lifecycle

## 13. Subagent Guidance For Goal Execution

The implementation agent may use Codex supervisor agents and subagents to parallelize independent work. This is execution coordination only, not Lab-Sidecar product architecture.

Good subagent slices:

- **Collector config reviewer**: inspect config shape compatibility and source selection risk.
- **Fixture/test designer**: create messy result fixtures inside tests or small examples and specify expected normalized rows.
- **Collector implementer**: implement source include/exclude, nested refs, alias diagnostics, or log collector.
- **Figure alignment implementer**: update figure summary/unit behavior if selected.
- **Docs/validation runner**: update docs, run tests, run manual smoke, and inspect summaries.

Subagents must:

- preserve unrelated local changes
- keep auto discovery conservative
- avoid touching MCP/intelligence unless the supervisor explicitly proves it is needed
- avoid committing generated `.lab-sidecar/` task directories
- avoid turning subagent usage into a Lab-Sidecar runtime feature

The supervisor remains responsible for final integration, scope control, validation, and acceptance evidence.

## 14. Concrete Acceptance Standards

Stage 3 is complete only when all selected implementation slices satisfy these gates:

1. Existing `collect --config` behavior remains backward compatible.
2. At least one nested/messy result directory fixture is normalized through explicit config.
3. Include/exclude or equivalent source selection prevents unrelated files from being collected.
4. Missing configured sources and fields produce clear CLI errors and persisted `collection-summary.json` diagnostics.
5. Multi-method and multi-seed fields are preserved in `metrics/normalized_metrics.csv`.
6. Units are recorded and unit conflicts are diagnosed.
7. Explicit figure specs work with mapped fields after collection.
8. No command claims statistical significance or scientific conclusions.
9. Existing Stage 1 `summarize` / `compare` and Stage 2 `package` behavior does not regress.
10. README and CLI spec document the supported messy-result config shape.
11. `docs/post-open-source-stage-3-acceptance.md` records implementation scope, commands, workspaces, task ids, generated artifacts, test results, deferred items, and final judgment.

If minimal log parsing is included, it must also satisfy:

12. Configured log parsing is explicit, regex-based, bounded, and tested.
13. Bad regex or unsupported log config fails clearly.
14. Logs are not scanned recursively or returned in full by default.

## 15. Validation Commands

Run before acceptance:

```bash
git diff --check
python -m pytest tests/test_cli_smoke.py -q
python -m pytest -q
```

If implementation touches package behavior, run focused package tests or the full CLI smoke tests that cover Stage 2 package export.

If implementation touches MCP/V2 response helpers, also run:

```bash
python -m pytest tests/test_mcp_tools.py -q
python -m pytest tests/test_v2_host_integration.py tests/test_v2_worker_invocation.py -q
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-stage-3-mcp-smoke
```

Manual smoke:

```bash
tmpdir="$(mktemp -d /tmp/lab-sidecar-stage-3-XXXXXX)"
cp -R examples "$tmpdir/examples"
cd "$tmpdir"
python -m lab_sidecar.cli.app init
mkdir -p messy-results/baseline messy-results/candidate messy-results/debug
# create or copy messy CSV/JSON/log files plus metrics.yaml and figure.yaml
python -m lab_sidecar.cli.app ingest messy-results --name "stage3 messy results"
python -m lab_sidecar.cli.app collect <task_id> --config metrics.yaml
python -m lab_sidecar.cli.app figures <task_id> --spec figure.yaml
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-messy
python -m lab_sidecar.cli.app summarize <task_id>
find .lab-sidecar/tasks/<task_id>/metrics -maxdepth 1 -type f | sort
find package-messy -maxdepth 3 -type f | sort
```

The acceptance document must include the actual fixture shape used for this smoke, not just the command template.

## 16. Acceptance Record Template

Create `docs/post-open-source-stage-3-acceptance.md` with:

```markdown
# Post-Open-Source Stage 3 Acceptance

## Phase Goal

## Starting State

## Implemented Scope

## Deferred Scope

## Changed Files

## Config Shape

## CLI Scenarios

## Workspaces And Task IDs

## Generated Artifacts

## Diagnostics Evidence

## Test Results

## Blocking

## Follow-Up

## Out Of Scope

## Final Judgment
```

## 17. Suggested Goal-Mode Objective

Use this objective when starting the implementation goal:

```text
Implement Lab-Sidecar Post-Open-Source Stage 3: Messy Result Adaptation.

Read docs/post-open-source-stage-3-plan.md first and treat it as the source of truth. Deepen the existing deterministic `collect --config` path so Lab-Sidecar can normalize at least one realistic nested/messy result directory with explicit config, preserve method/seed fields, diagnose missing sources/fields and unit conflicts, and keep explicit figure specs aligned with mapped fields. Maintain backward compatibility with current string/list `sources`, `fields`, and `units` config behavior.

You may use Codex supervisor agents and subagents for independent slices such as collector config review, fixture/test design, collector implementation, figure alignment, docs, and validation. Subagents are execution coordination only and must not become Lab-Sidecar product architecture. The supervisor remains responsible for integrating changes, preserving boundaries, and writing docs/post-open-source-stage-3-acceptance.md with evidence.

Stay local-first, file-first, CLI-first, deterministic, and cautious. Do not add Web UI, FastAPI, remote runners, cloud sync, hosted services, default AI analysis, statistical significance claims, TensorBoard parsing, arbitrary notebook execution, or broad recursive workspace scanning without explicit config. Avoid lab_sidecar/mcp and lab_sidecar/intelligence unless existing tests prove a small shared helper change is required. Do not revert unrelated local changes.

Add focused tests, update README.md and docs/cli-spec.md, run git diff --check, run `python -m pytest tests/test_cli_smoke.py -q`, run `python -m pytest -q`, perform a manual messy-results smoke in a temporary workspace, verify diagnostics and package output, and finish with a clear final judgment in the acceptance document. If minimal regex log parsing is too large for this pass, explicitly defer it in the acceptance record rather than half-implementing it.
```

## 18. Stage 3 Acceptance Checklist

Before marking the goal complete, confirm:

- [ ] Existing config behavior still passes current tests
- [ ] Nested or messy configured sources collect successfully
- [ ] Include/exclude or equivalent source selection is tested
- [ ] Missing source and missing field diagnostics are persisted
- [ ] Multi-method and multi-seed rows normalize correctly
- [ ] Units are recorded and conflicts are diagnosed
- [ ] Figure specs work with mapped fields
- [ ] Stage 1 summarize/compare behavior still works
- [ ] Stage 2 package behavior still works
- [ ] README and CLI spec document the supported config shape
- [ ] `tests/test_cli_smoke.py` passes
- [ ] full test suite passes
- [ ] manual messy-results smoke is recorded in acceptance
