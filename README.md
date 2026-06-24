# Lab-Sidecar

Lab-Sidecar is a CLI-first, file-first, local-first artifact sidecar for local experiment runs and imported result files. It records task and comparison artifacts under `.lab-sidecar/`, collects CSV/JSON metrics, renders deterministic figures, writes Markdown report fragments, drafts editable PPTX files, and packages local evidence for sharing after review.

The primary path is local CLI use by a human experiment owner, student, research beginner, or personal developer who wants reproducible artifacts they can inspect, redact, package, and use in reports or presentations.

```text
run / ingest -> collect -> figures -> report -> slides
```

## Why This Exists

Local experiment workflows often leave behind a mix of terminal logs, CSV files, JSON files, screenshots, and half-written notes. Lab-Sidecar keeps that work file-first: every task gets a directory under `.lab-sidecar/tasks/<task_id>/`, with `manifest.json` as the durable record and generated artifacts beside it.

Today it does seven practical things for local experiment artifacts:

- runs or ingests local experiment results
- collects CSV/JSON metrics into normalized tables
- writes bounded `metrics/scenario-summary.json` records for training and benchmark-style scenarios
- saves bounded descriptive comparisons across 2-5 collected local tasks
- renders deterministic PNG/SVG figures
- writes deterministic Markdown report fragments
- drafts static editable PowerPoint decks from the recorded artifacts

Reports and slides are template-generated. They do not use AI and they do not claim to infer complex research conclusions.

Optional local MCP/V2 integrations can act as an advanced adapter for agents that need task ids, compact summaries, artifact paths, and bounded previews. They are not the main product surface and do not turn Lab-Sidecar into a hosted service, remote runner, Web UI, FastAPI app, or general multi-agent framework.

For the human experiment owner, every run remains local files you can inspect, compare, redact, package, or share.

## Capability Boundary Matrix

| Area | Supported today | Not supported or not claimed |
| --- | --- | --- |
| Metrics input | Local CSV and JSON metric files, normalized into task-local CSV/JSON outputs. | TensorBoard event parsing, JSONL stream parsing, full MLflow tracking-store parsing, or broad recursive workspace ingestion by default. |
| Comparisons | Bounded saved comparison artifacts for 2-5 already-collected local tasks, using shared numeric final-row metrics with provenance. | Statistical significance tests, model superiority claims, cross-workspace comparison, or broad tracking dashboards. |
| Figures | Deterministic static PNG/SVG `line`, `bar`, and `box` charts, with opt-in bounded fallback diagnostics for unsupported explicit specs. | Complex scientific plotting systems, interactive charts, statistical-significance charting, animation, video, or automatic visual interpretation. |
| Reports and slides | Deterministic Markdown report fragments and editable static PPTX drafts from recorded artifacts. | Automatic research conclusions, paper-ready scientific claims, deployment recommendations, or default AI-authored analysis. |
| Local execution and ingestion | User-explicit local CLI `run`, `ingest`, `collect`, and task-local artifact records under `.lab-sidecar/`. | Hosted service behavior, remote runners, cloud sync, multi-tenant authorization, Web UI, or FastAPI app. |
| Optional local agent adapter | Experimental local MCP/V2 bounded delegation that returns task ids, compact summaries, risk flags, next actions, and artifact metadata. | A primary product surface, hosted service, remote runner, security sandbox, container runtime, malware detector, shell interception layer, or general multi-agent framework. |
| Context boundary | Bounded `metrics/scenario-summary.json`, artifact paths, and type-specific previews. | Complete logs, complete metric rows, full report bodies, PPT contents, worker prompt/response bodies, full data files, or artifact bytes by default. |
| Human ownership | Local artifacts that a human experiment owner can inspect, redact, package, and accept or reject. | Delegated final judgment, automatic redaction, autonomous experiment interpretation, or final decision-making. |

## Demo Preview

These previews are committed from a real `examples/csv-comparison` Lab-Sidecar run. They are not stock images.

![Validation accuracy comparison](docs/assets/demo/csv-comparison-val-accuracy.png)

![Report preview generated from csv-comparison](docs/assets/demo/csv-comparison-report-preview.png)

The full demo recipe is in [docs/demo-public-alpha.md](docs/demo-public-alpha.md).

## 10-Minute Quickstart

Install from a clone:

```bash
python -m pip install -e ".[dev]"
```

If you also want the optional MCP smoke and plugin checks, install
`.[dev,mcp]` instead.

On Windows, use `py -3` instead of `python` if that is your configured launcher.

Create a clean demo workspace from the repository root:

```bash
export LABSIDECAR_REPO="$(pwd)"
export LABSIDECAR_WS="${TMPDIR:-/tmp}/lab-sidecar-alpha-workspace"
rm -rf "$LABSIDECAR_WS"
mkdir -p "$LABSIDECAR_WS"
cp -R "$LABSIDECAR_REPO/examples" "$LABSIDECAR_WS/examples"
cd "$LABSIDECAR_WS"
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app doctor
```

Run the deterministic training fixture:

```bash
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app list
python -m lab_sidecar.cli.app summarize "$TASK_ID"
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app validate "$TASK_ID"
python -m lab_sidecar.cli.app package "$TASK_ID" --output "lab-sidecar-package-$TASK_ID"
python -m lab_sidecar.cli.app package-verify "lab-sidecar-package-$TASK_ID"
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
python -m lab_sidecar.cli.app open "$TASK_ID"
```

The `run` command prints the task id, artifact directory, log paths, and next likely commands. A task id looks like `task_20260608_132834_153843`.

Expected files:

```text
.lab-sidecar/tasks/$TASK_ID/
  manifest.json
  stdout.log
  stderr.log
  metrics/normalized_metrics.csv
  metrics/scenario-summary.json
  figures/*.png
  figures/*.svg
  reports/report-fragment.md
  slides/presentation-draft.pptx
  slides/slides-summary.json
  provenance/traceability.json
```

The task-local `provenance/traceability.json` file is refreshed as metrics, figures, reports, slides, or packages are generated. It records source references, generated artifact hashes/sizes, metric lineage, figure lineage, report claim traces, slide evidence, reproduce metadata pointers, and omission notes without embedding full logs, full metric rows, report bodies, PPTX contents, worker prompt/response bodies, raw source files, or SQLite.

Chart fallback is opt-in. Deterministic `line`, `bar`, and `box` figures are always attempted first. Explicit figure specs support both the legacy single-spec YAML shape and the current multi-figure `figures:` YAML shape; see [docs/figure-specs.md](docs/figure-specs.md). For an explicit unsupported chart spec, `figures --fallback bounded` writes bounded request and validation records under `intelligence/<worker_run_id>/`; official fallback PNG/SVG files are created only after validator acceptance. See [docs/alpha4-bounded-chart-fallback-operator-guide.md](docs/alpha4-bounded-chart-fallback-operator-guide.md).

The `validate` command checks a task's artifact health without generating new
artifacts. Its diagnostics call out missing or malformed metrics, summaries,
reports, slides, and traceability with paths and next actions. The `package`
command creates a shareable, inspectable single-task
folder with `README.md`, `manifest.json`, `package-summary.json`,
`artifact-index.json`, `artifact-index.sha256`, `redaction-notes.md`,
reproduce metadata, task-local traceability evidence, and generated
metrics/figures/report/slides artifacts when present. `package-verify` checks
the package index digest, package summary parseability, indexed file hashes and
sizes, and rejects unexpected files. By default packages do not copy full
`stdout.log` or `stderr.log`, raw source files, `.lab-sidecar/index.sqlite`,
worker prompt/response bodies, temporary sandbox files, or unrelated workspace
files. Failed tasks package as diagnostic folders and are labeled as
failed-task diagnostics, not successful experiment summaries.

For an existing-results path, try:

```bash
python -m lab_sidecar.cli.app ingest examples/csv-comparison
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
```

For nested or messy result directories, keep discovery explicit with
`collect --config`. The older config shapes still work, including
`sources: results.csv`, `sources: [results/*.csv]`, `fields: {accuracy:
score_pct}`, and top-level `units`. Stage 3 also supports include/exclude
source lists and field alias lists:

```yaml
sources:
  include:
    - messy-results/**/*.csv
  exclude:
    - messy-results/**/debug*.csv
    - messy-results/**/scratch/*
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
```

Configured sources must stay inside the local workspace and, for ingested
tasks, inside the ingested source refs. Missing sources, missing mapped
fields, unsupported file types, excluded files, and unit conflicts are recorded
in `metrics/collection-summary.json`. Lab-Sidecar does not recursively scan
entire workspaces by default and does not convert units automatically.
The same summary also includes bounded best-row, checkpoint, and anomaly
metadata so agents can answer common ranking or incomplete-run questions without
reading full normalized metric tables.

To compare a small set of collected local tasks, pass two to five task ids:

```bash
python -m lab_sidecar.cli.app compare <task_id_a> <task_id_b>
```

`compare` reads each task's `metrics/normalized_metrics.csv`, uses the final row from each file, and reports shared numeric fields only. It does not claim statistical significance or infer research conclusions.

To save that comparison as local artifacts:

```bash
python -m lab_sidecar.cli.app compare <task_id_a> <task_id_b> --save --name "baseline-vs-model-a" --figures --report
export COMPARISON_ID=<printed_comparison_id>
python -m lab_sidecar.cli.app list-comparisons
python -m lab_sidecar.cli.app comparison-artifacts "$COMPARISON_ID"
python -m lab_sidecar.cli.app open-comparison "$COMPARISON_ID"
python -m lab_sidecar.cli.app validate-comparison "$COMPARISON_ID" --require figures --require report --require package-ready
python -m lab_sidecar.cli.app package-comparison "$COMPARISON_ID" --output "lab-sidecar-comparison-$COMPARISON_ID"
python -m lab_sidecar.cli.app package-verify "lab-sidecar-comparison-$COMPARISON_ID"
```

Saved comparison artifacts are descriptive only. They do not run statistical
tests, infer model superiority, copy source task logs, or copy source raw files.
`list-comparisons`, `comparison-artifacts`, and `open-comparison` are read-only
navigation commands for existing saved comparison records. They do not generate
artifacts and are not exposed through MCP/V2.
`validate-comparison` reports missing figures, reports, traceability, stale
source metrics, and package-readiness issues with bounded next actions. The
deterministic comparison report includes source tasks, final-row selection,
bounded table preview, evidence paths, warnings, omissions, and this limitation:
This comparison is descriptive only; no statistical significance or model
superiority is inferred.

## CLI Commands

Both `labsidecar` and `lab-sidecar` console scripts point at the same CLI after installation. The module entrypoint always works from an editable checkout:

| Command | Purpose |
| --- | --- |
| `init` | Create `.lab-sidecar/` config, task directory, and local index. |
| `doctor` | Check Python version, writable workspace, config, task directory, and optional MCP SDK. |
| `run "<command>"` | Execute a user-provided local command and capture task logs/artifacts. |
| `run "<command>" --background` | Start a long task and return a task id immediately. |
| `ingest <path>` | Register an existing file or directory without running a command. |
| `status <task_id>` | Refresh and print status, exit code, timestamps, artifact count, and next steps. |
| `list --limit 20 [--status completed]` | Show recent tasks from task manifests with scan-friendly status, timestamp, artifact, and name columns. |
| `summarize <task_id>` | Print a bounded task digest with major artifact paths and summary counts, without full logs or artifact bodies. |
| `compare <task_id> <task_id> [...]` | Compare final-row shared numeric metrics for 2-5 collected local tasks. |
| `compare <task_id> <task_id> [...] --save [--figures] [--report]` | Save a bounded local comparison artifact under `.lab-sidecar/comparisons/`. |
| `list-comparisons --limit 20` | Show recent saved comparisons without reading table, report, or log bodies. |
| `open-comparison <comparison_id>` | Print the absolute saved comparison artifact directory path. |
| `comparison-artifacts <comparison_id>` | List existing saved comparison artifact paths without printing artifact bodies. |
| `validate-comparison <comparison_id>` | Check saved comparison artifact health without generating artifacts. |
| `package-comparison <comparison_id> --output <dir>` | Create a shareable saved-comparison package from allowlisted comparison artifacts. |
| `validate <task_id>` | Check task artifact health without generating new artifacts. |
| `package <task_id> --output <dir>` | Create a shareable single-task result or diagnostic package from allowlisted artifacts. |
| `package-verify <package_dir>` | Verify a package against `artifact-index.json`, `artifact-index.sha256`, hashes, and file set. |
| `open <task_id>` | Print the absolute task artifact directory path. |
| `logs <task_id> --tail 20` | Print bounded stdout/stderr tails. |
| `artifacts <task_id>` | List artifacts recorded in `manifest.json`. |
| `cancel <task_id>` | Cancel a running task started by Lab-Sidecar. |
| `collect <task_id>` | Normalize CSV/JSON metrics into task-local tables. |
| `figures <task_id>` | Generate static PNG/SVG figures; `--fallback bounded` is opt-in for unsupported explicit chart specs. |
| `report <task_id>` | Generate a deterministic Markdown report fragment. |
| `slides <task_id>` | Generate a static editable PPTX draft. |

Use `python -m lab_sidecar.cli.app <command>` if your shell cannot find the console script.

## Artifact Layout

Lab-Sidecar keeps generated artifacts under `.lab-sidecar/` and does not move, delete, or rewrite user source files during collection, figure rendering, report generation, or slide generation.

```text
.lab-sidecar/
  config.yaml
  index.sqlite
  tasks/
    task_YYYYMMDD_HHMMSS_xxxxxx/
      manifest.json
      stdout.log
      stderr.log
      raw/
      metrics/
      figures/
      reports/
      slides/
      provenance/
      reproduce/
  comparisons/
    comparison_YYYYMMDD_HHMMSS_xxxxxx/
      comparison-manifest.json
      comparison-summary.json
      comparison-table.csv
      comparison-table.json
      figures/
      reports/
      provenance/
```

SQLite is only an index. The task-local `manifest.json`, saved comparison
manifest, generated summaries, and `provenance/traceability.json` files are the
records to inspect or share after redaction. Traceability explains where
recorded values came from; it does not add statistical significance, model
superiority, or automatic scientific interpretation.

## Codex And MCP

Lab-Sidecar includes an advanced optional local MCP adapter in `lab_sidecar.mcp`. It is experimental and exposes thin wrappers over the same local services rather than a separate product surface.

V1 deterministic tools:

- `run_experiment`
- `inspect_results`
- `cancel_experiment`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

V2 bounded delegation tools:

- `delegate_experiment_artifacts`
- `inspect_sidecar_task`
- `preview_sidecar_artifact`
- `cancel_sidecar_task`

Default MCP/V2 responses return task ids, compact summaries, risk flags, next actions, and artifact metadata. Complete command strings, stdout/stderr, metrics rows, report bodies, PPT contents, worker prompt/response bodies, full data files, and artifact bytes are omitted by default. Use `preview_sidecar_artifact` for bounded detail.

`preview_sidecar_artifact` is task-artifact scoped. It supports bounded CSV rows, Markdown lines, log tails, image metadata, and PPTX metadata. It rejects workspace-external, unregistered, raw, unsupported, and worker-audit paths. If the goal is to share results, use `package <task_id>`; if results are nested or messy, use explicit `collect --config` rather than broad automatic discovery.

The optional stdio server entrypoint is:

```bash
python -m lab_sidecar.mcp.server
```

Host setup is in [docs/mcp-host-config.md](docs/mcp-host-config.md). A repo-scoped Codex plugin scaffold lives in [plugins/lab-sidecar](plugins/lab-sidecar/); it is optional guidance for Codex hosts, not required for normal CLI use.

## Safety And Limits

- Manual CLI `run` executes the local command the user explicitly provides. Lab-Sidecar records the command, logs, status, and artifacts, but it is not an OS sandbox and the command can do whatever the user's environment permits.
- MCP/V2 and other agent-triggered command paths are higher risk than manual CLI use. MCP-hosted command delegation goes through bounded delegation, configured workspace boundaries, and the conservative command safety gate. Direct Python host integrations around `delegate_experiment_artifacts(command=...)` must keep explicit command policy or confirmation in front of that call.
- Those MCP/V2 guardrails are not operating-system isolation, a container runtime, a malware detector, or a guarantee that a command is safe.
- Generated logs and artifacts may contain local paths, command arguments, environment details, metrics, or snippets of output. Review and redact before sharing.
- The human experiment owner remains responsible for interpretation, redaction, acceptance, and final decisions.
- Reports and slides are deterministic summaries of recorded artifacts, not autonomous research conclusions, paper conclusions, or deployment advice.
- Bounded chart fallback is local and artifact-scoped. It is not a hosted service, remote runner, browser UI, or general multi-agent framework.
- The current project does not include a browser app, HTTP service, remote runner, cloud sync, animation/video export, or default AI analysis.

## Install And Development

Editable install:

```bash
python -m pip install -e ".[dev]"
```

Optional MCP SDK:

```bash
python -m pip install -e ".[dev,mcp]"
```

Run tests:

```bash
python -m pytest
```

Run the MCP stdio smoke when MCP behavior is in scope:

```bash
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke
```

Validate the repo-scoped Codex plugin guidance with the local Codex
plugin-creator validator when plugin files change.

Build a local package artifact without publishing:

```bash
python -m pip install build
python -m build
```

Run release-oriented smokes from a repository checkout:

```bash
python scripts/cli_full_smoke.py --workspace /tmp/lab-sidecar-cli-full-smoke --repo "$(pwd)"
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"
```

## Project Docs

- [Current scope](docs/current-scope.md)
- [Artifact protocol](docs/artifact-protocol.md)
- [Comparison artifacts](docs/comparison-artifacts.md)
- [Figure specs](docs/figure-specs.md)
- [Public alpha quickstart](docs/public-alpha-quickstart.md)
- [Deterministic public alpha demo](docs/demo-public-alpha.md)
- [Public alpha release notes](docs/public-alpha-release-notes.md)
- [Release checklist](docs/release-checklist.md)
- [MCP host configuration](docs/mcp-host-config.md)
- [Next-stage acceptance record](docs/next-stage-product-growth-acceptance.md)
- [Changelog](CHANGELOG.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [MIT license](LICENSE)
