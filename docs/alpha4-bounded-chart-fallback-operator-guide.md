# Alpha4 Bounded Chart Fallback Operator Guide

Date: 2026-06-20

## Purpose

Alpha4 bounded chart fallback handles explicit chart requests that deterministic
figures cannot express yet. Deterministic `line`, `bar`, and `box` charts remain
the first path. Fallback is opt-in and artifact-scoped.

This feature does not add a Web UI, hosted service, remote runner, cloud sync, or
general multi-agent framework.

## Enablement

Default behavior:

```bash
labsidecar figures <task_id>
labsidecar figures <task_id> --spec figure.yaml
```

Default fallback mode is `off`. Unsupported explicit chart specs write bounded
diagnostics but do not run a worker.

Explicit bounded fallback:

```bash
labsidecar figures <task_id> --spec figure.yaml --fallback bounded
```

In normal operator use, `--fallback bounded` records a bounded request and
diagnostics when no chart worker is configured. Test and benchmark runs use the
hidden internal `--fallback-worker` option to exercise the local mock worker.

## Statuses

Fallback state is recorded in `figures/figure-summary.json`:

| status | attempted | Meaning |
| --- | --- | --- |
| `not_needed` | `false` | Deterministic figures handled the task, or fallback stayed off after unsupported diagnostics. |
| `unavailable` | `true` | A bounded request was recorded, but no chart fallback worker was configured. |
| `rejected` | `true` | A worker output was present but failed deterministic validation. |
| `adopted` | `true` | Validator accepted the sandbox output and Lab-Sidecar copied official PNG/SVG files into `figures/`. |

`not_needed` with `mode=off` is expected for normal deterministic runs. It is
also expected for unsupported chart requests when the user did not opt in to
fallback.

## Files

Unsupported chart diagnostics appear in:

```text
figures/figure-summary.json
provenance/traceability.json
```

Bounded fallback attempts appear under:

```text
.lab-sidecar/tasks/<task_id>/intelligence/<worker_run_id>/
  figure-request.json
  worker-request.json
  worker-result.json
  validator-result.json
  adoption-record.json
  diagnostics.md
  sandbox/
```

`worker-request.json` and `worker-result.json` exist only when a worker was
actually invoked. `adoption-record.json` exists only when validation accepted the
fallback output.

Official adopted outputs remain under:

```text
figures/<figure_id>-fallback.png
figures/<figure_id>-fallback.svg
figures/figure-spec.yaml
figures/figure-summary.json
provenance/traceability.json
manifest.json
```

Workers never write official artifacts directly. Official figure files are
written only by the deterministic renderer or by the validator/adoption path.

## Boundedness Contract

Fallback request and audit files may include:

- task id, status, and mode;
- requested chart intent;
- metric column names and row count;
- units, groups, and field-source mappings;
- collection warnings and skipped-file diagnostics;
- artifact paths, sizes, and hashes;
- validator checks, diagnostics, and adopted official paths.

They must not include:

- full raw source files;
- full `metrics/normalized_metrics.csv` rows;
- full stdout/stderr logs;
- report bodies;
- PPTX internals;
- worker prompt or response bodies;
- sandbox proposal bodies in operator-facing summaries;
- artifact file bodies.

## Troubleshooting

`status=unavailable`:

- No chart fallback worker is configured.
- Inspect `intelligence/<worker_run_id>/figure-request.json` and
  `diagnostics.md`.
- Deterministic chart generation remains usable.

`status=rejected` with field diagnostics:

- The proposal referenced a field not present in bounded metric columns.
- The proposal may have omitted `x`, `y`, `group_by`, or
  `source_metrics_fields`.
- Rejected outputs stay in `sandbox/` and do not create official figure
  artifacts.

`status=rejected` with path diagnostics:

- The worker proposed an absolute path or a path that escapes `sandbox/`.
- Lab-Sidecar rejects these paths before adoption.

`status=rejected` with visual diagnostics:

- The proposed PNG/SVG was missing, unparsable, blank, or below minimum
  dimensions.
- Fix the worker output and rerun fallback.

`status=adopted`:

- Official fallback PNG/SVG files were copied into `figures/`.
- `adoption-record.json`, `figure-summary.json`, manifest artifacts, and
  `provenance/traceability.json` record fallback lineage.
- Re-run `report` or `slides` if downstream artifacts need to include the new
  figure.

Bounded context limitations:

- Fallback workers receive metadata and bounded diagnostics, not full raw
  tables. A worker may need a more explicit figure spec if the available
  bounded context is ambiguous.
- Validation checks fields, paths, source lineage, and basic visual validity. It
  does not certify scientific correctness or visual design quality.
