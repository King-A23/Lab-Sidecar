# Alpha3 Sidecar Context Benchmark Agent Goal

You are the implementation/verification agent for the Alpha3 Sidecar Context
Benchmark in the Lab-Sidecar repository.

Repository:

```text
<repo>
```

## Goal

Strictly execute and verify the Alpha3 A/B context benchmark comparing the same
analysis tasks with and without Lab-Sidecar, then ensure the benchmark results
are written to:

- `docs/alpha3-sidecar-context-benchmark.md`
- `docs/alpha3-sidecar-context-benchmark-data.json`

The benchmark must determine whether Lab-Sidecar reduces main-agent context
load while preserving or improving artifact quality, traceability, and delivery
completeness.

## Important Starting State

The repository may already contain uncommitted benchmark result files:

- `docs/alpha3-sidecar-context-benchmark.md`
- `docs/alpha3-sidecar-context-benchmark-data.json`

Do not assume they are correct. Audit them against this goal. If they are
correct, preserve them and report that they pass. If they are incomplete or
wrong, rerun the benchmark and update only those benchmark files.

Do not commit, push, tag, publish, or modify product code unless the user later
explicitly asks. If you discover a product bug, record it in your final report
and stop before mixing benchmark documentation with implementation fixes.

## Subagent Permission

You may call Codex supervisor agents and subagents when useful. Suitable
subagent slices:

- raw-arm measurement audit
- sidecar-arm measurement audit
- benchmark data schema validation
- quality rubric review
- final report/readability review

Subagents are execution coordination only. They are not Lab-Sidecar product
architecture. The supervisor remains responsible for integrating conclusions,
checking the final files, preserving repository boundaries, and reporting final
status.

## Required Scenarios

Run or verify three scenarios:

1. `examples/simple-success`
2. `examples/csv-comparison`
3. `examples/project-presentation-pack`

For each scenario, create or verify two fresh temp-workspace runs under
`/private/tmp`:

- raw agent baseline
- Lab-Sidecar workflow

Generated `.lab-sidecar` task directories and package folders must stay under
`/private/tmp` and must not be added to the repository.

## Raw Agent Baseline Rules

The raw arm may inspect raw fixture files directly and must not run Lab-Sidecar
commands.

Record every raw file read as main-agent context exposure:

- path
- bytes
- chars
- purpose

The raw arm must produce a bounded analysis summary answering:

```text
Summarize what happened, identify the key metrics/results, list generated or
expected deliverables, explain what evidence supports the claims, and state any
limits or unknowns without inventing conclusions.
```

Required raw files:

- simple success:
  - `examples/simple-success/README.md`
  - `examples/simple-success/metrics.csv`
  - optional but recommended: `examples/simple-success/train.py`
- CSV comparison:
  - `examples/csv-comparison/README.md`
  - `examples/csv-comparison/baseline.csv`
  - `examples/csv-comparison/model_a.csv`
  - `examples/csv-comparison/model_b.csv`
- project presentation pack:
  - `examples/project-presentation-pack/README.md`
  - `examples/project-presentation-pack/project_goal.md`
  - `examples/project-presentation-pack/weekly_metrics.csv`
  - `examples/project-presentation-pack/final_metrics.csv`
  - `examples/project-presentation-pack/ablation.json`

## Lab-Sidecar Workflow Rules

Use local CLI execution only, not MCP/V2.

Use the repository venv when needed:

```bash
<python>
```

Run sidecar workflows in copied temp workspaces with `examples/` copied in.

Do not read or count these full artifact bodies in the sidecar arm:

- full `stdout.log`
- full `stderr.log`
- full `metrics/normalized_metrics.csv`
- full `metrics/normalized_metrics.json`
- full `reports/report-fragment.md`
- PPTX internals or XML
- `raw/source_refs.json`
- raw source files
- worker prompt/response bodies

If any are read, record it as a sidecar violation.

Allowed bounded sidecar context:

- CLI command output
- `manifest.json`
- `metrics/collection-summary.json`
- `figures/figure-summary.json`
- `reports/report-summary.json`
- `slides/slides-summary.json`
- `provenance/traceability.json`
- package `artifact-index.json`
- package `package-summary.json`

### Simple Success Sidecar Commands

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv" --name "alpha3 simple success"
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-alpha3-simple
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

### CSV Comparison Sidecar Commands

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app ingest examples/csv-comparison --name "alpha3 csv comparison"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app package <task_id> --output package-alpha3-csv
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

### Project Presentation Pack Sidecar Commands

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app ingest examples/project-presentation-pack --name "alpha3 project pack"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id> --template zh-project
python -m lab_sidecar.cli.app package <task_id> --output package-alpha3-project
python -m lab_sidecar.cli.app summarize <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

## Measurement Contract

For each scenario and arm, collect:

- `scenario_id`
- `arm`: `raw_agent` or `lab_sidecar`
- `workspace`
- `task_ids`
- `commands_run`
- `files_read`
- `context_bytes`
- `context_chars`
- `estimated_context_tokens`
- `full_artifact_bodies_exposed`
- `raw_log_bytes_exposed`
- `raw_metric_row_bytes_exposed`
- `generated_deliverables`
- `traceability_present`
- `sqlite_independent_check`
- `quality_scores`
- `violations`
- `notes`

Token estimate:

```text
estimated_context_tokens = ceil(context_chars / 4)
```

This is a proxy, not vendor billing.

Quality score each category 0-2:

- `metric_correctness`
- `deliverable_completeness`
- `traceability`
- `boundedness`
- `no_invention`

Maximum score per arm per scenario: 10.

## Required Data File

Write `docs/alpha3-sidecar-context-benchmark-data.json` with this top-level
shape:

```json
{
  "schema_version": "1",
  "date": "2026-06-19",
  "package_version": "0.1.0",
  "comparison_base": "v0.1.0-alpha.2",
  "candidate": "local main intended for v0.1.0-alpha.3",
  "token_estimate": {
    "method": "ceil(chars / 4)",
    "exact_provider_tokens_available": false
  },
  "scenarios": [],
  "aggregate": {}
}
```

Required aggregate calculations:

```text
context_reduction_pct = 100 * (1 - sidecar_context_chars / raw_context_chars)
token_reduction_pct = 100 * (1 - sidecar_estimated_tokens / raw_estimated_tokens)
quality_delta = sidecar_quality_total - raw_quality_total
```

Compute per scenario and overall.

## Required Human Report

Write `docs/alpha3-sidecar-context-benchmark.md` with:

- title and date
- methodology
- scenario table
- raw vs sidecar comparison table
- aggregate context/token comparison
- quality rubric table
- workspaces and task ids
- violations or omissions
- conclusion on whether alpha3 demonstrates context-quarantine value
- limitations

The report must explicitly state that token counts are estimates unless exact
provider usage is available.

If the benchmark shows Lab-Sidecar does not reduce context on the tiny checked-in
fixtures, state that clearly. Do not force a positive conclusion. It is valid to
conclude that Lab-Sidecar improves provenance/quality while not proving token
savings on small fixtures.

## Acceptance Criteria

The benchmark passes only if:

- all three scenarios have raw and sidecar runs
- each run records context chars, estimated tokens, files read, and quality
  scores
- every sidecar run generates task-local `provenance/traceability.json`
- every sidecar run generates a package with `artifact-index.json` and
  `package-summary.json`
- SQLite-independent inspection is checked after deleting `.lab-sidecar/index.sqlite`
- sidecar arm records any full artifact body exposure as a violation
- `docs/alpha3-sidecar-context-benchmark-data.json` is valid JSON
- `git diff --check` passes
- no generated `.lab-sidecar` task directory or package folder exists in the
  repository working tree
- final response reports whether files were changed and whether acceptance
  passed

## Final Response Requirements

Do not commit.
Do not push.
Do not tag.
Do not publish.

Final response must include:

- benchmark files written or verified
- aggregate context/token results
- quality delta
- sidecar violation count
- temp workspace root(s)
- validation commands run
- any limitations or follow-up recommendations
