# Experiment Scenario Summary Audit

Audit date: 2026-06-21

Audited commit: `ef4e161 feat: add experiment scenario summaries`

## Objective

This audit reviews whether the new `metrics/scenario-summary.json` surface
fits Lab-Sidecar's product boundary: a local-first, file-first, CLI-first,
artifact-first sidecar for experiment scenarios where the primary caller is a
local AI agent and the human experiment owner remains responsible for goals,
tradeoffs, interpretation, redaction, and final acceptance.

The audit does not propose new product scope. It specifically avoids Web UI,
FastAPI, remote runner, hosted service, cloud sync, a generic multi-agent
framework, default AI analysis, statistical significance claims, and automatic
scientific conclusions.

## Read-Only Checks

Required repository checks were run before editing this document:

```text
git status --short --branch
```

Observed:

```text
## main...origin/main [ahead 1]
```

```text
git show --stat --oneline HEAD
```

Observed:

```text
ef4e161 feat: add experiment scenario summaries
21 files changed, 1334 insertions(+), 25 deletions(-)
```

Additional read-only inspection used `rg` and `sed` across README,
`PRODUCT_ITERATION_PLAN.md`, `docs/experiment-scenario-summary-contract.md`,
`lab_sidecar/collectors/scenario_summary.py`,
`lab_sidecar/mcp/responses.py`, `lab_sidecar/intelligence/bundle.py`, CLI
summarize, report/slides services, and scenario/V2 tests.

## Overall Verdict

The commit is directionally aligned with "experiment scenario local AI agent
sidecar" positioning. It adds a deterministic artifact that can help an agent
continue from bounded evidence instead of reading full logs or metric tables.
The implementation does not embed full stdout, stderr, full metric rows,
report bodies, PPTX contents, worker prompt/response bodies, or artifact bytes
inside `scenario-summary.json`.

The schema is not too large for narrow training or benchmark metrics, but it is
larger than the current contract makes obvious. It includes top-level evidence,
source file metadata, column lists, best rows, last rows, seed aggregates,
groups, units, warnings, and omissions. The largest remaining risk is not full
row leakage; it is bounded snippets of arbitrary user text through
`selected_fields`, plus wide-table growth through unbounded column and
detected-field lists.

The bigger product risk is semantic amplification: fields named `best_rows`,
`primary_metric`, and `seed_aggregates` are useful for agents, but they can be
read as experiment conclusions unless every consuming surface keeps the
"descriptive only, no significance, no scientific claim" boundary visible.
The current report and CLI surfaces are cautious. V2 compact responses expose
more of the compact scenario structure and should get stronger negative tests.
Slides already contain rule-based `best` and `delta` language from their own
key-comparison logic; scenario summary does not create that behavior, but it
can make the surrounding deck feel more conclusive.

## Positioning Review

### README

Status: pass.

The README now leads with Lab-Sidecar as a local-first AI agent sidecar for
experiment scenarios. It explicitly says the primary caller is an AI agent in a
local workspace and the human owner inspects, redacts, packages, and uses the
artifacts. It also preserves local-first, file-first, CLI-first, artifact-first,
AI-optional boundaries:

- The main workflow remains `run / ingest -> collect -> figures -> report ->
  slides`.
- Reports and slides are deterministic and do not use AI.
- Default MCP/V2 responses are described as bounded.
- Safety limits explicitly rule out browser app, HTTP service, remote runner,
  cloud sync, and default AI analysis.

One minor documentation tension remains: the README says the summary includes
"bounded best-row, checkpoint, and anomaly metadata" near the collection config
section. That sentence appears to describe `collection-summary.json`
`bounded_analysis`, not the new scenario summary. It is not a product-scope
problem, but it can blur which artifact owns which bounded analysis contract.

### PRODUCT_ITERATION_PLAN

Status: pass.

The product plan is consistent with the README: main AI agent as primary
caller, human owner as experiment decision-maker and final reviewer, bounded
summary and traceable artifacts as the output boundary. It also retains the
warning that Lab-Sidecar is not a general AI chat assistant or generic
multi-agent framework.

## Contract Review

Status: partial pass.

`docs/experiment-scenario-summary-contract.md` is concise and points in the
right direction. It defines required top-level fields, omitted content, row
evidence shape, and the no-statistical-significance boundary for seed
aggregates.

Gaps:

- The contract does not state numeric limits such as `MAX_BEST_ROWS = 4`,
  `MAX_LAST_ROWS = 6`, `MAX_SEED_AGGREGATES = 12`,
  `MAX_SELECTED_FIELDS = 12`, `MAX_SOURCE_FILES = 20`, and
  `MAX_STRING_CHARS = 160`.
- It does not state that `selected_fields` may contain bounded scalar snippets
  from arbitrary remaining row columns after priority identity and metric
  fields are selected.
- It does not define whether `evidence.metrics.columns`,
  `source_files[].detected_fields`, `source_files[].mapped_fields`, and `units`
  are bounded by count or character length. In code, source file count is
  bounded, but per-file field lists and the top-level metrics column list are
  not.
- It does not define stable enum-like values for `scenario_type`,
  `direction`, or `selection_reason`. The current values are readable, but
  agents and downstream tests may begin depending on implementation-hint
  strings such as `higher_is_better_name_hint`.
- It says reports/slides may cite best rows and aggregate summaries as recorded
  evidence, while current templates mostly cite scenario type, primary metric,
  and aggregate availability. The contract is broader than current rendering
  behavior.

Recommended contract change: keep the schema as `1`, but document explicit
limits, advisory fields, and interpretation boundaries before adding any more
fields.

## Collector Review

Status: bounded with medium-risk edges.

`lab_sidecar/collectors/scenario_summary.py` has meaningful boundedness
controls:

- `best_rows` capped at 4.
- `last_rows` capped at 6.
- `seed_aggregates.items` capped at 12.
- `selected_fields` capped at 12 fields per row.
- source file entries capped at 20.
- string scalar values capped at 160 characters.
- row evidence points to `metrics/normalized_metrics.csv` row numbers with
  `body: omitted`.
- omitted contract explicitly lists stdout, stderr, full metric rows, report
  body, PPT contents, worker prompt/response, and artifact bytes.

No full logs or full metric rows are copied into the scenario summary.

Risks:

- `selected_fields` intentionally falls back to arbitrary non-empty row fields
  after priority fields. This prevents full row exposure, but still allows up
  to 12 snippets of arbitrary user text at 160 characters each. A column such
  as `notes`, `prompt`, `error_message`, or `private_comment` can be exposed in
  selected best/last rows if not enough priority fields fill the cap.
- `evidence.metrics.columns` includes all normalized columns with no count
  limit. A very wide CSV can make the summary large.
- `source_files[].detected_fields` and `source_files[].mapped_fields` are not
  count-limited per file. Source file entries are capped, but each entry can
  still carry many field names.
- `units` is copied from config without an explicit count or string bound.
- `groups.configured` is copied from config. This is probably small today, but
  the contract should still state it is metadata, not evidence.
- `selected_fields` is computed twice when calculating `omitted_field_count`;
  that is not a correctness issue, but it increases the chance future changes
  accidentally diverge if selection becomes nontrivial.

Schema size judgment: acceptable for V1 if treated as a compact artifact, but
not yet strict enough for a durable agent contract in wide-table or
free-text-heavy workspaces.

## Consumer Surface Review

### CLI Summarize

Status: pass.

The CLI `summarize` command prints scenario type, primary metric, best-row
count, seed aggregate availability, and the summary path. It does not print
best row contents, selected fields, row bodies, or aggregate values.

### MCP / V2 Compact Responses

Status: partial pass.

`lab_sidecar/mcp/responses.py` compacts scenario summaries before returning
them through V2/MCP surfaces. It includes:

- scenario type
- primary metric
- groups
- first 3 best rows
- first 3 last rows
- first 3 seed aggregate items
- warnings
- omitted contract

This is still bounded, but it is the most agent-facing surface and the one most
likely to be interpreted as a result ranking. It should be tested against long
free-text row fields and wide schemas, not only for presence of the scenario
object.

### V2 Input Bundle

Status: partial pass.

`lab_sidecar/intelligence/bundle.py` includes `compact_task_outputs`, so the
worker bundle gets the same compact scenario object described above. It also
adds a JSON preview entry for `metrics/scenario-summary.json`, but dictionary
JSON previews are shallow: nested objects become key lists, and lists become
counts. That means the scenario summary is not fully duplicated through
`data_previews`.

The broader V2 bundle still previews normalized metrics CSV rows separately.
That is existing V2 behavior rather than a scenario-summary-specific leak, but
it reinforces why the scenario summary contract should remain stricter than a
general preview surface.

### Reports

Status: pass.

Report templates are cautious. They cite scenario summary path, scenario type,
primary metric, and aggregate availability. They explicitly state deterministic
generation, no AI use, unsupported inference as unknown, and no statistical
significance from scenario summaries.

Report claim traces cite the scenario summary artifact with `body: omitted`.

### Slides

Status: partial pass.

Slides cite scenario type, primary metric, and "no significance inferred" on
the metrics slide. Slide claim traces cite `metrics_scenario_summary` with
`body: omitted`.

The main concern is not direct scenario summary leakage. It is that slides also
have independent key-comparison slides that use rule-based `best`, `delta`,
`top_items`, and "best item" language from normalized metrics. That behavior
predates and sits beside scenario summary, but together these surfaces can
encourage agents or humans to treat descriptive ranking as a scientific
conclusion. The no-significance/no-scientific-claim caveat should remain close
to any automatic ranking language.

## Test Coverage Review

Status: useful but incomplete.

Covered:

- `tests/test_scenario_summary.py` covers a training-run summary, primary
  metric selection, best row row number, checkpoint field, omitted full metric
  rows, 160-character truncation behavior, and warning text mentioning
  statistical significance.
- `tests/test_scenario_summary.py` covers an algorithm-benchmark with seed
  aggregates and the descriptive aggregate claim limit.
- `tests/test_cli_smoke.py` covers algorithm-benchmark generation from ingest
  config and asserts the scenario summary does not embed the source JSON key
  `"runs"`.
- `tests/test_cli_smoke.py` covers CLI summarize showing the scenario summary
  path and scenario metadata.
- `tests/test_v2_host_integration.py` covers V2 delegate and inspect responses
  exposing compact scenario presence, type, and primary metric.

Gaps:

- No test creates a very wide CSV to prove `scenario-summary.json` remains
  acceptably small or records omitted column/field counts for field lists.
- No test proves `selected_fields` cannot include sensitive arbitrary text
  snippets beyond bounded truncation. The current test proves truncation, but
  also confirms that a truncated `notes` value is still present.
- No test asserts `MAX_BEST_ROWS`, `MAX_LAST_ROWS`, `MAX_SEED_AGGREGATES`,
  `MAX_SOURCE_FILES`, and `MAX_SELECTED_FIELDS` from generated artifacts.
- No V2 test serializes compact responses with long text fields and checks for
  absence of raw notes, prompts, or long error text.
- No report/slides tests assert that scenario-derived language avoids
  superiority, causal, deployment-readiness, or statistical significance
  claims.
- No contract/schema test validates required keys, enum values, advisory
  fields, and omitted fields against the documentation.

## Risk Register

| Risk | Severity | Current state | Suggested next step |
| --- | --- | --- | --- |
| Agents over-read `best_rows` and `primary_metric` as scientific conclusions | Medium | Warnings and report language help; V2 compact responses still expose ranking evidence | Add stronger no-significance/no-scientific-claim language to the contract and V2 docs/tests |
| Arbitrary free-text snippets leak through `selected_fields` | Medium | Bounded to 12 fields and 160 chars, but fallback can include non-priority text | Consider allowlisting selected fields or excluding text-heavy names such as notes/prompt/message by default |
| Wide table metadata makes summary too large | Medium | Row bodies bounded, but columns and per-file field lists are not count-limited | Add field-list limits or omitted counts to contract and tests |
| Contract underspecifies limits and stable values | Medium | Code has limits; docs only state qualitative boundedness | Document exact caps and define which strings are stable vs advisory |
| Slides amplify automatic ranking language | Low to Medium | Scenario summary is cautious; slides key-comparison uses best/delta language | Keep caveats adjacent to ranking surfaces and test for no significance/superiority claims |
| Duplicate bounded-analysis concepts confuse artifact ownership | Low | `collection-summary.json` has `bounded_analysis`; new file has scenario summary | Clarify artifact responsibilities in README or contract |

## Recommended Next Steps

1. Update `docs/experiment-scenario-summary-contract.md` to document exact
   limits, stable values, advisory values, selected-field behavior, and
   no-significance/no-scientific-claim boundaries.
2. Add tests for wide CSVs, many source files, many columns, long free-text
   cells, V2 compact response serialization, and report/slides claim wording.
3. Consider narrowing `selected_fields` to an allowlist plus the selected
   metric, or explicitly excluding common free-text columns by name. If
   arbitrary fallback fields remain, call that out in the contract.
4. Consider adding explicit omitted counts for `evidence.metrics.columns`,
   `source_files[].detected_fields`, `source_files[].mapped_fields`, and
   `units` if the schema is meant to stay compact across wide benchmarks.
5. Keep scenario summary as descriptive evidence only. Do not add automatic
   hypothesis testing, causal language, deployment-readiness labels, or AI
   analysis by default.

## Audit Conclusion

The scenario summary is a reasonable V1 artifact for an experiment-focused
local AI agent sidecar, provided it is treated as bounded descriptive evidence
and not as an interpretation engine. The implementation already avoids the
highest-risk leaks: full logs, full rows, report bodies, PPTX contents, worker
prompt/response bodies, and artifact bytes.

Before treating `metrics/scenario-summary.json` as a stable agent contract, the
project should tighten the documented schema limits and add negative tests for
wide tables, arbitrary text snippets, and V2 compact response leakage. The
commit does not require product-code rollback, but it should be followed by a
small contract-and-test hardening pass before expanding the schema.
