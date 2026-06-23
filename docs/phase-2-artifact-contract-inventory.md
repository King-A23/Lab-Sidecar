# Phase 2 Artifact Contract Inventory

Date: 2026-06-23

This inventory records the current task-local public artifact contracts before
Phase 2 schema work starts. It is a documentation and schema-strategy slice
only: no product code, JSON Schema files, or schema tests are added here.

The scope is the existing local workflow:

```text
run / ingest -> collect -> figures -> report -> slides
```

It does not expand collectors, scenario types, MCP or host contracts, Web UI,
FastAPI, remote execution, default AI behavior, or statistical conclusion
claims.

## Stability Labels

- Required/public: fields that should be present in the first versioned schema
  for the artifact when that artifact is generated.
- Optional/public: fields that are legitimate public fields but may be `null`,
  empty, or absent depending on task mode, status, or generation path.
- Compatibility alias: older or duplicate fields that current readers still
  consume and first schema tests should accept.
- Bounded preview: intentionally capped summaries of larger data.
- Internal/unstable: current fields that need a public-versus-internal decision
  before they are treated as stable contract surface.

## Global Findings

- All inventoried JSON artifacts currently use `schema_version: "1"`.
- `manifest.json` is backed by Pydantic models; most other summary artifacts
  are service-layer dictionaries.
- Omission intent is consistent across the pipeline: full logs, raw source
  bodies, full metric rows, worker prompt/response bodies, artifact bytes,
  sandbox files, SQLite, and unrelated workspace files are omitted by default.
- Path style is not fully uniform. Some manifest artifacts are workspace-
  relative paths such as `.lab-sidecar/tasks/<task_id>/...`; other generated
  summaries use task-relative paths such as `reports/report-summary.json`.
- Reason strings and diagnostics are currently human-readable strings, not
  stable enums, unless a future schema explicitly freezes them.

## `manifest.json`

Current producer:

- `lab_sidecar/core/manifest.py` writes `TaskRecord` through
  `write_manifest`.
- Records are created and updated by runner, collector, figure, report, slide,
  traceability, and package paths.
- Model source: `TaskRecord`, `TaskPaths`, and `ArtifactRecord` in
  `lab_sidecar/core/models.py`.

Schema version:

- `schema_version: "1"` from `TaskRecord`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `mode`, `status`,
  `created_at`, `updated_at`, `working_dir`, `paths`, `artifacts`.
- Required path fields: `paths.task_dir`, `paths.stdout`, `paths.stderr`.
- Public enum candidates: `mode` is `run` or `ingest`; `status` is `pending`,
  `running`, `completed`, `failed`, or `cancelled`.
- Public artifact fields: `artifact_id`, `type`, `path`, `description`,
  `source_paths`, `size_bytes`, `sha256`.
- Optional/public task fields: `command`, `source_path`, `exit_code`, `name`,
  `started_at`, `finished_at`, `failure_summary`, `pid`, `worker_pid`.

Bounded/omitted fields:

- The manifest references `stdout.log`, `stderr.log`, raw refs, reproduce
  metadata, and generated artifacts by path; it does not embed log bodies, raw
  source bodies, normalized metric rows, report bodies, PPTX contents, or
  artifact bytes.
- `failure_summary` is derived from a bounded stderr tail for failed run tasks,
  but it is still task-local user text and may contain sensitive content.
- Log artifact hashes may remain `null`; traceability records why full log
  digests are omitted by default.

Alias/compat fields:

- `TaskRecord` and `TaskPaths` allow extra fields for alpha compatibility.
- `ArtifactRecord` forbids extra fields.

Known risks:

- `command`, `working_dir`, `source_path`, and `failure_summary` may contain
  private paths, arguments, or error text. Package export includes the manifest,
  so sharing still requires user review.
- Artifact `type`, `artifact_id`, and path style are not yet schema-enforced.
- Some artifact paths are workspace-relative while others are task-relative.

First schema-style tests:

- First P1 schema-style contract tests are in
  `tests/test_manifest_contract.py`. They use a lightweight in-test helper,
  not a product schema module.

Recommended first schema tests:

- Done in the first P1 schema-style test slice: validate generated completed
  `run`, completed `ingest`, failed `run`, running background, and cancelled
  background manifests.
- Done in the first P1 schema-style test slice: assert status and mode enums,
  required path fields, and artifact item shape.
- Done in the first P1 schema-style test slice: assert artifact IDs are unique
  after repeated collect/figures/report/slides runs.
- Done in the first P1 schema-style test slice: assert the manifest contains
  references, not embedded full stdout/stderr bodies, raw source bodies,
  normalized metric rows, report bodies, PPT contents, or artifact bytes.
- Keep additional task/path properties accepted until a compatibility policy is
  explicitly tightened.

## `metrics/collection-summary.json`

Current producer:

- `MetricsCollectionService._build_summary` in
  `lab_sidecar/collectors/service.py`.

Schema version:

- `schema_version: "1"`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `task_status`, `collected_at`,
  `candidate_count`, `candidates`, `processed_files`, `skipped_files`,
  `warnings`, `diagnostics`, `unit_diagnostics`, `row_count`,
  `detected_fields`, `bounded_analysis`, `output_files`.
- Optional/public: `config_path`, `config`, `units`, `groups`,
  `matched_source_fields`.
- Candidate entries: `source_file`, `origin`, `suffix`, `source_provenance`.
- Processed file entries: `source_file`, `file_type`, `row_count`,
  `source_provenance`, `detected_fields`, `mapped_fields`,
  `matched_source_fields`.
- Diagnostic/skipped entries currently use `source_file`, `reason`, and
  optional `message`.

Bounded/omitted fields:

- `bounded_analysis` is a bounded preview with its own `schema_version: "1"`.
- Current hard limits in code: best rows 6, selected fields per row 14,
  anomaly groups 20, string scalars 180 characters.
- Bounded row evidence points at `metrics/normalized_metrics.csv` with
  `body: "omitted"`.
- `output_files` records generated normalized CSV/JSON paths only when rows
  were collected.
- Bad/empty input summaries keep parse diagnostics and do not write normalized
  metrics outputs.

Alias/compat fields:

- No artifact-level alias fields are established.
- Field-mapping config accepts aliases in user config, but the summary records
  canonical normalized fields and `matched_source_fields`.

Known risks:

- `candidates`, `processed_files`, `detected_fields`, and diagnostics are not
  globally bounded in the collection summary itself.
- `bounded_analysis.selected_fields` can fall back to arbitrary row fields,
  unlike `scenario-summary.json`; bounded free-text leakage is possible until a
  schema or implementation decision narrows it.
- Diagnostic `reason` strings are useful but not yet formally stabilized.
- `config` shape depends on metrics config parsing and is not independently
  versioned.

First schema-style tests:

- First P1 schema-style contract tests are in
  `tests/test_collection_summary_contract.py`. They use a lightweight in-test
  helper, not a product schema module.

Recommended first schema tests:

- Done in the first P1 schema-style test slice: validate successful CSV/JSON
  collection with normalized CSV/JSON outputs.
- Done in the first P1 schema-style test slice: validate no-candidate, bad
  JSON, empty CSV, and missing-configured-field diagnostics without normalized
  outputs.
- Done in the first P1 schema-style test slice: validate configured
  include/exclude, `matched_source_fields`, units, groups, and mixed-unit
  diagnostics.
- Done in the first P1 schema-style test slice: validate `bounded_analysis`
  limits and `body: "omitted"` row evidence.
- Remaining known risk: `bounded_analysis.selected_fields` may still include
  bounded arbitrary row fields; current tests validate hard bounds and no full
  rows/log bodies, but do not freeze an allowlist until product behavior is
  intentionally narrowed.

## `metrics/scenario-summary.json`

Current producer:

- `build_scenario_summary` in
  `lab_sidecar/collectors/scenario_summary.py`, called after successful metrics
  collection.
- Contract docs already exist in
  `docs/experiment-scenario-summary-contract.md` and
  `docs/experiment-scenario-summary-examples.md`.
- First P1 schema-style contract tests are in
  `tests/test_scenario_summary_contract.py`. They use a lightweight in-test
  helper, not a product schema module.

Schema version:

- `schema_version: "1"`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `generated_at`,
  `scenario_type`, `primary_metric`, `groups`, `units`,
  `omitted_unit_count`, `best_rows`, `last_rows`, `seed_aggregates`,
  `evidence`, `omitted`, `warnings`.
- Stable values: `scenario_type` is `training-run` or
  `algorithm-benchmark`; `primary_metric.direction` is `max`, `min`, or
  `null`.
- `primary_metric` fields: `name`, `direction`, `unit`,
  `selection_reason`.
- `groups` fields: `configured`, `primary`, `secondary`, `seed`, `context`,
  `inferred`.

Bounded/omitted fields:

- Current hard limits: best rows 4, last rows 6, seed aggregate items 12,
  selected fields 12, source files 20, metric columns 40, detected/mapped
  source fields 40 each, units 40, string scalars 160 characters.
- Row evidence uses `metrics/normalized_metrics.csv`, row numbers, bounded
  selected scalar fields, and `body: "omitted"`.
- `omitted` explicitly records omitted full stdout/stderr, full metric rows,
  report body, PPT contents, worker prompt/response, and artifact bytes.
- Free-text columns may appear as column names in bounded metadata, but their
  cell values are not copied into `selected_fields`.

Alias/compat fields:

- No artifact-level alias fields are established.

Known risks:

- `selection_reason` values are advisory human-readable hints, not stable
  enums.
- `scenario_type` and primary metric selection are deterministic heuristics,
  not scientific validation.
- `seed_aggregates` are descriptive only and must not be turned into
  significance, superiority, causal, or deployment-readiness claims.

Recommended first schema tests:

- Done in the first P1 schema-style test slice: convert existing scenario
  summary contract examples into checked fixtures.
- Done in the first P1 schema-style test slice: validate generated
  training-run, algorithm-benchmark, missing-primary, and wide/free-text
  summary shapes.
- Done in the first P1 schema-style test slice: assert hard bounds, omission
  fields, evidence `body: "omitted"`, seed aggregate claim limits, and no
  unsupported ranking, significance, superiority, causal, or deployment-ready
  language.
- Done in the first P1 schema-style test slice: assert free-text fields such as
  `notes`, `prompt`, `message`, `error_message`, and `private_comment` do not
  enter `selected_fields`.
- Remaining for later if useful: add dedicated checked fixture coverage for
  bad-input/no-summary alongside the existing CLI smoke coverage.

## `figures/figure-summary.json`

Current producer:

- `FigureGenerationService._build_summary` in
  `lab_sidecar/figures/service.py`.

Schema version:

- `schema_version: "1"`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `task_status`,
  `generated_at`, `metrics_path`, `source_metrics`, `figure_count`,
  `generated_figures`, `unsupported_chart_diagnostics`,
  `skipped_candidates`, `warnings`, `errors`, `fallback`.
- Optional/public: `spec_path`, `spec_input_path`, `units`, `groups`,
  `field_sources`.
- Generated figure fields: `figure_id`, `chart_type`, `png_path`, `svg_path`,
  `source_metrics`, `x`, `y`, `group_by`, `units`, `field_sources`,
  `source`, `worker_run_id`, `validation_status`, `validation_checks`,
  `fallback_lineage`.
- Fallback summary fields: `mode`, `attempted`, `worker_run_id`, `status`,
  `request_path`, `validator_result_path`, `adoption_record_path`,
  `validation_status`, `validation_checks`, `adopted_figures`,
  `adopted_artifact_paths`, `diagnostics`.

Bounded/omitted fields:

- Unsupported chart diagnostics record chart intent, available fields, and
  reasons without metric row bodies.
- Bounded fallback requests include paths, column names, row counts, field
  sources, collection diagnostics, and an explicit omitted contract; they do
  not include raw metric rows, full logs, raw source bodies, report bodies,
  PPTX internals, worker transcripts, or artifact bodies.
- Fallback adoption records official artifacts and validator checks, not worker
  prompt/response bodies.

Alias/compat fields:

- Canonical public figure list for new integrations and docs:
  `generated_figures`. It is the richer current list and uses `png_path` and
  `svg_path`.
- Compatibility alias retained for alpha readers: `figures`. It uses `png` and
  `svg`, should continue to be accepted by readers, and should not be the
  preferred field for new docs or host-facing examples.
- `metrics_path` and `source_metrics` duplicate the metrics reference.
- `spec_path` and `spec_input_path` duplicate the input spec reference.
- Report, slide, and traceability readers currently accept
  `generated_figures` first and fall back to `figures`.

Known risks:

- The canonical versus alias policy is documented here and covered by
  schema-style tests, but not yet exported as a standalone JSON Schema.
- Fallback status-specific fields vary across `not_needed`, `unavailable`,
  `rejected`, and `adopted`.
- Validation check and diagnostic messages are human-readable and may change.
- Fallback metadata references sandbox/audit paths that package and
  traceability omit by default.

Recommended first schema tests:

- First P1 schema-style contract tests are in
  `tests/test_figure_summary_contract.py`. They use a lightweight in-test
  helper, not a product schema module.
- Done in the first P1 schema-style test slice: validate deterministic success
  with both richer canonical `generated_figures` and compatibility alias
  `figures`.
- Done in the first P1 schema-style test slice: validate unsupported explicit
  chart with fallback off.
- Done in the first P1 schema-style test slice: validate bounded fallback
  unavailable, rejected, and adopted shapes.
- Done in the first P1 schema-style test slice: assert raw rows, log bodies,
  worker prompts/responses, and artifact bytes are absent from the summary
  contract and fallback metadata records.
- P1 field-policy decision: `generated_figures` is canonical; `figures` remains
  a compatibility alias for alpha readers and should not be used as the
  preferred field in new integrations.

## `reports/report-summary.json`

Current producer:

- `ReportGenerationService._build_summary` in
  `lab_sidecar/reports/service.py`.

Schema version:

- `schema_version: "1"`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `template`, `generated_at`,
  `report_path`, `summary_path`, `generated_from`, `provenance`, `metrics`,
  `figures`, `failure`, `cancellation`, `reproduce`, `claim_traces`,
  `source_artifacts`.
- `provenance` fields: `task_id`, `status`, `mode`, `command`,
  `source_path`, `working_dir`, `created_at`, `started_at`, `finished_at`,
  `exit_code`.
- Metrics summary fields: `present`, `path`, `collection_summary_path`,
  `scenario_summary_path`, `scenario`, `row_count`, `columns`,
  `displayed_columns`, `omitted_column_count`, `numeric_summaries`,
  `numeric_omitted_count`, `detected_fields`.
- Figure summary fields: `present`, `task_id`, `summary_path`,
  `figure_count`, `items`, `warnings`, `errors`.
- Claim trace fields: `claim_id`, `surface`, `claim_type`, `value`,
  `evidence`, with optional `operation` and `field` for metric summaries.

Bounded/omitted fields:

- Displayed columns are capped at 20.
- Numeric summaries are capped at 8.
- Scenario compact summary keeps at most 3 best rows, 3 last rows, 3 seed
  aggregate items, and 5 warnings.
- Failure and cancellation contexts include a bounded stderr tail of 20 lines.
- Claim evidence for scenario summaries and logs uses `body: "omitted"`.
- The report Markdown body is written to `reports/report-fragment.md`; it is
  not embedded in the summary.

Alias/compat fields:

- `generated_from` and `source_artifacts` currently duplicate the source
  artifact list.
- Figure items accept upstream `generated_figures` or `figures` aliases when
  report summary is built.

Known risks:

- `metrics.columns` and `metrics.processed_files` can copy broad collection
  metadata into the report summary.
- `provenance.command`, failure summaries, and bounded stderr tails may contain
  sensitive user text.
- Claim trace names and evidence shapes are not yet schema-validated.
- It is not yet explicit which compact scenario fields are stable for report
  consumers.

Recommended first schema tests:

- First P1 schema-style contract tests are in
  `tests/test_report_summary_contract.py`. They use a lightweight in-test
  helper, not a product schema module.
- Done in the first P1 schema-style test slice: validate completed reports with
  metrics and figures.
- Done in the first P1 schema-style test slice: validate completed reports with
  metrics but no figures, including display-column and numeric-summary caps.
- Done in the first P1 schema-style test slice: validate failed and cancelled
  diagnostic reports without metrics.
- Done in the first P1 schema-style test slice: assert claim traces have
  evidence and log/scenario evidence bodies are omitted.
- Done in the first P1 schema-style test slice: assert numeric/display-column,
  compact-scenario, and stderr-tail bounds.
- Done in the first P1 schema-style test slice: assert report body text is not
  embedded in the summary.
- Remaining known risk: `metrics.columns`, `metrics.processed_files`, and
  review-required provenance/failure text still copy broad user-local metadata
  into the report summary; current tests freeze boundedness and omission rules
  without narrowing that product surface.

## `slides/slides-summary.json`

Current producer:

- `SlidesGenerationService._build_summary` in
  `lab_sidecar/slides/service.py`.

Schema version:

- `schema_version: "1"`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `task_status`, `template`,
  `font_family`, `font_fallbacks`, `generated_at`, `pptx_path`,
  `summary_path`, `generated_from`, `slide_count`, `included_figures`,
  `included_metrics`, `warnings`, `figure_warnings`,
  `figure_skipped_candidates`, `text_truncations`, `table_truncations`,
  `key_comparisons`, `caption_truncations`, `slide_evidence`,
  `claim_traces`, `qa_checks`, `slides`, `report_excerpt`,
  `source_artifacts`.
- Included figure fields: `figure_id`, `chart_type`, `path`, `x`, `y`,
  `group_by`, `source_metrics`.
- Included metrics fields: `present`, `path`, `scenario_summary_path`,
  `scenario`, `row_count`, `key_columns`, `numeric`.
- Slide fields: `slide_index`, `title`, `purpose`, `source_artifacts`,
  `evidence`, `empty_source_reason`.
- QA check groups: `slide_count`, `empty_slide_check`, `title_check`,
  `artifact_duplicate_check`, `table_overflow_guard`,
  `caption_overflow_guard`.

Bounded/omitted fields:

- Included figures are capped at 4; figure slides show at most 2 figures per
  slide.
- Numeric metric summaries are capped at 6; key columns at 10.
- Report excerpts are capped at 5 cleaned lines.
- Metrics table preview is capped at 8 columns, 6 rows, and 42 characters per
  cell.
- Log tails are capped at 8 lines and 860 characters; truncation records for
  log tails include omission reasons and counts, not full log text.
- Claim evidence for logs and scenario summaries uses `body: "omitted"`.
- PPTX internals and complete artifact bodies are not embedded in the summary.

Alias/compat fields:

- Canonical public fields for new integrations and docs:
  `included_figures`, `included_metrics`, `slides`, `slide_evidence`,
  `claim_traces`, `qa_checks`, `text_truncations`, `table_truncations`,
  `caption_truncations`, `key_comparisons`, `generated_from`, and
  `source_artifacts`.
- Backward-compatible aliases are still emitted for alpha readers:
  `slide_titles`, `metrics`, `metrics_table`, and `figures`. Readers may accept
  them, but new integrations should prefer the canonical public fields above.
- `generated_from` and `source_artifacts` intentionally duplicate the source
  artifact list for now. Both are public/stable and must stay reference-only.

Internal/unstable fields:

- `project_goal.full`, `full_text_fields`, and arbitrary non-log truncation
  `full` values are internal/unstable current outputs. They may be useful for
  local review, but they are excluded from the first strict public schema and
  should not be consumed by host-facing integrations.
- Public consumers should use bounded display/excerpt fields and source
  artifact references instead of any `full` body fields.

Known risks:

- `full_text_fields` currently includes full command, source path, working
  directory, failure summary, and artifact directory. It is explicitly
  internal/unstable for P1 and may be removed, bounded further, or moved behind
  a debug/internal summary later.
- `project_goal.full`, non-log text truncation `full` fields, and full caption
  truncations may contain user-authored text and remain excluded from the first
  strict public schema.
- Key comparisons are deterministic display aids, not statistical claims.
- The alias fields are useful for compatibility, but new docs and
  integrations should prefer the canonical public fields.

Schema-style test coverage added in Phase 2 P1:

- `tests/test_slides_summary_contract.py` now validates generated completed
  `collect -> figures -> report -> slides` summaries against the current
  public/quasi-public contract surface.
- The same contract helper validates completed `collect -> report -> slides`
  summaries without figures and freezes bounded behavior rather than blessing
  any full-body display fields.
- Failed and cancelled diagnostic summaries are covered with explicit checks
  that `slides/slides-summary.json` keeps logs, report content, and PPTX internals
  reference-only or bounded, not embedded.
- The tests freeze `generated_from` and `source_artifacts` as source-artifact
  references only, excluding slides self-references and complete artifact bytes.

Still-open risks after this slice:

- `project_goal.full`, `full_text_fields`, and non-log truncation `full` values
  remain emitted but are intentionally not treated as stable public fields by
  the contract tests.
- Caption truncation `full` text is still present and may include user-authored
  strings; the tests only freeze bounded caption display metadata.
- P1 field-policy decision: `included_figures`, `included_metrics`, `slides`,
  `slide_evidence`, `claim_traces`, `qa_checks`, truncation records, and
  source-artifact references are the canonical public surface; `slide_titles`,
  `metrics`, `metrics_table`, and `figures` remain compatibility aliases; full
  body fields remain internal/unstable.

Recommended first schema tests:

- Validate completed slide summary after collect/figures/report.
- Validate failed and cancelled diagnostic slide summaries.
- Validate metrics table truncation, caption truncation, and log tail omission
  records.
- Validate `zh-project` project metadata without treating full project text as
  stable until the public/internal decision is made.
- Validate alias fields are accepted while canonical fields remain present.
- Assert claim traces and per-slide evidence do not embed full logs, raw rows,
  PPTX internals, or artifact bytes.

## `provenance/traceability.json`

Current producer:

- `refresh_traceability` and `build_traceability_index` in
  `lab_sidecar/core/traceability.py`.

Schema version:

- `schema_version: "1"`.

Public/stable fields:

- Required/public: `schema_version`, `task_id`, `generated_at`, `task`,
  `environment`, `sources`, `artifacts`, `metric_lineage`, `figure_lineage`,
  `report_lineage`, `slide_lineage`, `claim_traces`, `omitted`,
  `traceability_artifact`, `warnings`.
- Task fields: `mode`, `status`, `working_dir`, `manifest_path`,
  `command_path`, `source_path`.
- Environment fields: `python_executable`, `env_path`, `git_path`,
  `dependencies_path`.
- Artifact entries: `artifact_id`, `type`, `path`, `description`,
  `source_paths`, `exists`, `size_bytes`, `sha256`, optional
  `digest_omitted_reason`.
- Lineage presence fields: `metric_lineage.present`,
  `figure_lineage.present`, `report_lineage.present`,
  `slide_lineage.present`.

Bounded/omitted fields:

- Sources are truncated at 200 entries with a warning.
- Log artifact digests are omitted by default and recorded with
  `digest_omitted_reason`.
- Omitted entries cover logs, raw source refs, worker logs/audit directories,
  worker prompt/response bodies, sandbox files, local SQLite index, raw source
  paths, and unrelated workspace files where applicable.
- Claim trace evidence should not include row bodies; existing tests assert
  evidence either lacks `body` or uses `body: "omitted"`.
- `traceability_artifact.self_digest_note` records that the self digest is not
  stored inside the self-referential trace body.

Alias/compat fields:

- Figure lineage accepts upstream `generated_figures` first and falls back to
  `figures`.
- Report lineage accepts `source_artifacts` or `generated_from`.

Known risks:

- Omission categories and reason strings are not yet formal enums.
- Warning/error text is aggregated from other summaries and may vary.
- Claim trace count can grow with report/slide numeric fields.
- Source and artifact path styles inherit the current task-relative versus
  workspace-relative inconsistency.

Recommended first schema tests:

- First P1 schema-style contract tests are now in
  `tests/test_traceability_contract.py`. They use a lightweight in-test helper,
  not a product schema module.
- Done in the traceability contract slice: validate completed full-chain
  traceability after `run -> collect -> figures -> report -> slides`, including
  task/environment/sources/artifacts sections, metric/figure/report/slide
  lineage, artifact hashes, log digest omission reasons, report/slide claim
  trace references, and the omission contract.
- Done in the traceability contract slice: validate failed diagnostic
  traceability with bounded report/slide claim traces and explicit confirmation
  that full logs, report bodies, metric rows, and slide/PPT internals are not
  embedded.
- Done in the traceability contract slice: validate package export preserves a
  stable `provenance/traceability.json` shape and package-copy parity for
  artifact hashes, lineage sections, and omitted categories.
- Done in the traceability contract slice: validate a representative
  missing-artifact case where lineage remains present while an artifact entry
  reports `exists: false` with `digest_omitted_reason: "artifact file is not present"`.
- Done in the traceability contract slice: validate source truncation at 200
  entries, warning text, and raw-source omission behavior for an ingest task
  with many candidate metric files.

Remaining known risks:

- Figure fallback lineage shape is still only covered indirectly by existing
  CLI smoke tests; the schema-style contract test slice does not yet freeze
  unavailable, rejected, and adopted fallback variants in one dedicated helper.
- Omission categories and reason strings remain human-readable strings rather
  than formal enums.
- Traceability warning aggregation still inherits wording from report, figure,
  and slides summaries, so warning text stability remains lower than structural
  field stability.

## `package-summary.json`

Current producer:

- `_package_summary` in `lab_sidecar/storage/package_export.py`, called by
  `export_task_package`.

Schema version:

- `schema_version: "1"` from `PACKAGE_SCHEMA_VERSION`.

Public/stable fields:

- Required/public: `schema_version`, `created_at`, `package_type`,
  `package_name`, `task`, `counts`, `included_artifacts`,
  `omission_policy`.
- `package_type` is `result` for completed tasks and `diagnostic` otherwise.
- Task fields: `task_id`, `name`, `mode`, `status`, `exit_code`,
  `created_at`, `started_at`, `finished_at`, `command_preview`,
  `source_path`, `failure_summary`.
- Counts: `included`, `omitted`, `unavailable`.
- Included artifact entries: `path`, `category`, `description`.

Bounded/omitted fields:

- `command_preview` is capped at 160 characters.
- `failure_summary` is capped at 1200 characters.
- The summary records counts and included artifact descriptions, not artifact
  bytes or hashes.
- `omission_policy` states the allowlist package policy for logs, raw sources,
  local indexes, worker transcripts, sandbox files, and unrelated workspace
  files.

Alias/compat fields:

- No artifact-level alias fields are established.

Known risks:

- The package includes `manifest.json`, which may contain the full command and
  task-local paths even though `package-summary.json` uses a preview.
- Diagnostic package README content can include bounded failure details.
- Counts must stay synchronized with `artifact-index.json`.

Recommended first schema tests:

- First P1 schema-style contract tests are now in
  `tests/test_package_contract.py`. They use a lightweight in-test helper, not
  a product schema module.
- Done in the package contract slice: validate a completed result package
  summary after `run -> collect -> figures -> report -> slides`, including
  `package_type`, task fields, counts, `included_artifacts`, omission policy,
  figure-image inclusion, and traceability inclusion.
- Done in the package contract slice: validate a failed diagnostic package
  summary with `package_type: "diagnostic"`, bounded `failure_summary`,
  unavailable metrics/figures/report/slides artifacts, and traceability still
  present.
- Done in the package contract slice: validate an ingested package summary with
  `command_preview: "(none)"`, `source_path`, raw-source omission behavior, and
  counts synchronized with `artifact-index.json`.
- Done in the package contract slice: assert `package-summary.json` stays
  metadata-only and does not embed hashes, sizes, full logs, worker
  prompt/response bodies, sandbox scratch content, raw source CSV bodies, PPTX
  internals, or artifact bytes.

Remaining known risks:

- `manifest.json`, `README.md`, and included artifacts can still contain local
  commands, paths, bounded diagnostic prose, or user-generated content, so
  package sharing still requires review.
- `command_preview` and `failure_summary` bounds are covered, but README and
  redaction-note prose remain intentionally unfrozen beyond current allowlist
  wording.
- Counts are frozen for representative generated scenarios, not for every
  future scenario-specific included-artifact combination.

## `artifact-index.json`

Current producer:

- `export_task_package` in `lab_sidecar/storage/package_export.py`.

Schema version:

- `schema_version: "1"` from `PACKAGE_SCHEMA_VERSION`.

Public/stable fields:

- Required/public: `schema_version`, `created_at`, `task_id`,
  `package_type`, `included`, `omitted`, `unavailable`,
  `package_metadata`.
- Included entries: `path`, `package_path`, `source_path`, `category`,
  `description`, `size_bytes`, `sha256`.
- Omitted entries: `path`, `category`, `reason`.
- Unavailable entries: `path`, `category`, `reason`.
- Package metadata entries: `path`, `package_path`, `category`,
  `description`, `size_bytes`, `sha256`, optional
  `digest_omitted_reason`.

Bounded/omitted fields:

- Package export is allowlist-based.
- Allowlisted task-local files include manifest, reproduce metadata,
  normalized metrics, collection/scenario summaries, figure spec/summary and
  image outputs, report fragment/summary, slide deck/summary, and traceability
  when present.
- Full logs, raw source refs, raw source files, worker logs/audit files,
  worker prompt/response bodies, sandbox files, local SQLite, and unrelated
  workspace files are omitted by default.
- `artifact-index.json` has no embedded artifact bytes.

Alias/compat fields:

- No artifact-level alias fields are established.

Known risks:

- `artifact-index.json` is self-referential; its package metadata entry has
  `sha256: null`, `size_bytes: null`, and a `digest_omitted_reason`.
- Omitted/unavailable reason strings are not yet formal enums.
- Included artifacts can include files that themselves contain user content,
  so package sharing still requires review.

Recommended first schema tests:

- First P1 schema-style contract tests are now in
  `tests/test_package_contract.py`. They use a lightweight in-test helper, not
  a product schema module.
- Done in the package contract slice: validate a completed result package index
  with stable top-level fields, included artifact hashes and sizes, package
  metadata entries, included-path parity with `package-summary.json`, and
  traceability inclusion.
- Done in the package contract slice: validate a failed diagnostic index with
  unavailable metrics/figures/report/slides artifacts, omitted log/index/workspace
  entries, and included traceability.
- Done in the package contract slice: validate an ingested package index omits
  `raw/source_refs.json` and raw source directories, does not copy source
  bodies into the package, and marks reproduce artifacts unavailable for ingest
  tasks.
- Done in the package contract slice: assert omitted files are not copied into
  the package and that `artifact-index.json` package metadata is
  self-referential with `sha256: null`, `size_bytes: null`, and an explicit
  `digest_omitted_reason`.
- Done in the package contract slice: assert `artifact-index.json` remains
  reference-only and does not embed raw logs, worker prompt/response bodies,
  sandbox scratch files, SQLite bytes, raw source CSV bodies, PPTX internals,
  or artifact bytes.

Remaining known risks:

- Omitted and unavailable reason strings are still human-readable strings, not
  formal enums.
- Included artifact rows validate hash/size presence and path parity, but they
  do not freeze every description string or every future task-specific figure
  file set beyond the representative scenarios covered here.
- `artifact-index.json` does not hash itself by design; callers that need an
  external package digest still have to compute it after package creation.

## Minimal Schema Strategy

1. Keep every listed artifact at `schema_version: "1"` until a breaking change
   is unavoidable.
2. Start with generated-output validation plus small checked-in fixtures. Do
   not depend on repository-local `.lab-sidecar/` state.
3. Validate shape, required fields, path/reference fields, boundedness, and
   omission rules before stabilizing every diagnostic message string.
4. Accept documented compatibility aliases in schemas and tests while choosing
   a canonical write shape for new docs and code.
5. Treat fields identified as internal/unstable in this inventory as excluded
   from the first strict schema until their public contract is decided.
6. Keep fixtures small and omit full logs, raw source bodies, full normalized
   rows, worker prompt/response bodies, PPTX internals, artifact bytes, and
   unrelated workspace files.
7. Recommended first P1 order: scenario summary, manifest, package/index,
   traceability, collection summary, figure summary, report summary, then slide
   summary.
