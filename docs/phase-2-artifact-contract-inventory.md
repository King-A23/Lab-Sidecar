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

Recommended first schema tests:

- Validate completed `run`, completed `ingest`, failed `run`, cancelled
  background, and running background manifests.
- Assert status and mode enums, required path fields, and artifact item shape.
- Assert artifact IDs are unique after repeated collect/figures/report/slides
  runs.
- Assert the manifest contains references, not full log/raw row/artifact bodies.
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

Recommended first schema tests:

- Validate successful CSV/JSON collection with normalized CSV/JSON outputs.
- Validate no-candidate, bad JSON, empty CSV, and missing-configured-field
  diagnostics without normalized outputs.
- Validate configured include/exclude, `matched_source_fields`, units, groups,
  and mixed-unit diagnostics.
- Validate `bounded_analysis` limits and `body: "omitted"` row evidence.
- Decide whether arbitrary fallback selected fields are public before making
  them stable.

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

- `figures` is a compatibility alias list using `png` and `svg`.
- `generated_figures` is the richer current list using `png_path` and
  `svg_path`.
- `metrics_path` and `source_metrics` duplicate the metrics reference.
- `spec_path` and `spec_input_path` duplicate the input spec reference.
- Report, slide, and traceability readers currently accept
  `generated_figures` first and fall back to `figures`.

Known risks:

- Canonical versus alias policy is not yet explicitly documented in a schema.
- Fallback status-specific fields vary across `not_needed`, `unavailable`,
  `rejected`, and `adopted`.
- Validation check and diagnostic messages are human-readable and may change.
- Fallback metadata references sandbox/audit paths that package and
  traceability omit by default.

Recommended first schema tests:

- Validate deterministic success with both `generated_figures` and alias
  `figures`.
- Validate unsupported explicit chart with fallback off.
- Validate bounded fallback unavailable, rejected, and adopted shapes.
- Assert raw rows, log bodies, worker prompts/responses, and artifact bytes are
  absent from summary, request, validator, and adoption records.
- Keep alias reads accepted while steering new code and docs toward the chosen
  canonical figure list.

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

- Validate completed report with metrics and figures.
- Validate completed report with metrics but no figures.
- Validate failed and cancelled diagnostic reports without metrics.
- Assert claim traces have evidence and log/scenario evidence bodies are
  omitted.
- Assert numeric/display column and stderr-tail bounds.
- Assert report body text is not embedded in the summary.

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

- Backward-compatible aliases are still emitted: `slide_titles`, `metrics`,
  `metrics_table`, and `figures`.
- `generated_from` and `source_artifacts` duplicate the source artifact list.

Internal/unstable fields:

- `project_goal.full`, `full_text_fields`, and non-log truncation `full` values
  are current outputs but should not be included in the first strict public
  schema until their disclosure policy is decided.

Known risks:

- `full_text_fields` currently includes full command, source path, working
  directory, failure summary, and artifact directory. This needs a public versus
  internal decision before schema stabilization.
- `project_goal.full`, non-log text truncation `full` fields, and full caption
  truncations may contain user-authored text.
- Key comparisons are deterministic display aids, not statistical claims.
- The alias fields are useful for compatibility but should not obscure the
  canonical public shape.

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

- Validate completed full-chain traceability.
- Validate failed diagnostic traceability.
- Validate traceability included in package export.
- Validate fallback unavailable, rejected, and adopted figure lineage.
- Validate missing optional artifacts keep lineage `present` flags and paths
  consistent.
- Assert sources stay capped, omitted categories are present, log digest
  omissions are explicit, and claim evidence does not include raw rows or
  bodies.

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

- Validate completed result package summary.
- Validate failed diagnostic package summary.
- Validate ingested task package summary.
- Assert package type, counts, command preview, failure summary bounds, and
  omission policy.
- Cross-check counts against `artifact-index.json`.

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

- Validate completed result package index with included hashes and metadata.
- Validate failed diagnostic index with unavailable metrics/figures/slides and
  included traceability.
- Validate ingested package index omits `raw/source_refs.json` and source
  files.
- Assert omitted files are not copied into the package.
- Assert self-referential artifact-index digest fields are `null` with an
  explicit reason.

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
