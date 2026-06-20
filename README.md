# Lab-Sidecar

Lab-Sidecar is a local-first research sidecar for AI agents and experiment workflows. It turns messy experiment outputs into task records, normalized metrics, deterministic figures, Markdown report fragments, and editable PPTX drafts.

It is built for AI agents, students, research beginners, and personal developers who run long local experiments and then need to remember what happened, compare small result files, and package reproducible report or presentation artifacts.

```text
run / ingest -> collect -> figures -> report -> slides
```

## Why This Exists

Agent-heavy and research-heavy workflows often leave behind a mix of terminal logs, CSV files, JSON files, screenshots, and half-written notes. Lab-Sidecar keeps that work file-first: every task gets a directory under `.lab-sidecar/tasks/<task_id>/`, with `manifest.json` as the durable record and generated artifacts beside it.

Today it does five practical things for noisy agent or research runs:

- runs or ingests local experiment results
- collects CSV/JSON metrics into normalized tables
- renders deterministic PNG/SVG figures
- writes deterministic Markdown report fragments
- drafts static editable PowerPoint decks from the recorded artifacts

Reports and slides are template-generated. They do not use AI and they do not claim to infer complex research conclusions.

For AI agents, Lab-Sidecar is the artifact boundary: the agent can ask for a task id, status, compact summaries, artifact paths, and bounded previews instead of pulling full logs, tables, reports, or slide contents into the prompt. For research workflows, the same record is useful after the agent is gone: every run has local files you can inspect, compare, redact, or share.

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
python -m lab_sidecar.cli.app package "$TASK_ID" --output "lab-sidecar-package-$TASK_ID"
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
  figures/*.png
  figures/*.svg
  reports/report-fragment.md
  slides/presentation-draft.pptx
  slides/slides-summary.json
  provenance/traceability.json
```

The task-local `provenance/traceability.json` file is refreshed as metrics, figures, reports, slides, or packages are generated. It records source references, generated artifact hashes/sizes, metric lineage, figure lineage, report claim traces, slide evidence, reproduce metadata pointers, and omission notes without embedding full logs, full metric rows, report bodies, PPTX contents, worker prompt/response bodies, raw source files, or SQLite.

Chart fallback is opt-in. Deterministic `line`, `bar`, and `box` figures are always attempted first. For an explicit unsupported chart spec, `figures --fallback bounded` writes bounded request and validation records under `intelligence/<worker_run_id>/`; official fallback PNG/SVG files are created only after validator acceptance. See [docs/alpha4-bounded-chart-fallback-operator-guide.md](docs/alpha4-bounded-chart-fallback-operator-guide.md).

The `package` command creates a shareable, inspectable single-task folder with `README.md`, `manifest.json`, `package-summary.json`, `artifact-index.json`, `redaction-notes.md`, reproduce metadata, task-local traceability evidence, and generated metrics/figures/report/slides artifacts when present. By default it does not copy full `stdout.log` or `stderr.log`, raw source files, `.lab-sidecar/index.sqlite`, worker prompt/response bodies, temporary sandbox files, or unrelated workspace files. Failed tasks package as diagnostic folders and are labeled as failed-task diagnostics, not successful experiment summaries.

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
| `package <task_id> --output <dir>` | Create a shareable single-task result or diagnostic package from allowlisted artifacts. |
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
```

SQLite is only an index. The task-local `manifest.json`, generated summaries, and `provenance/traceability.json` are the record to inspect or share after redaction. Traceability explains where recorded values came from; it does not add statistical significance, model ranking, or automatic scientific interpretation.

## Codex And MCP

Lab-Sidecar includes an experimental local MCP adapter in `lab_sidecar.mcp`. It exposes thin wrappers over the same local services rather than a separate product surface.

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

- CLI `run` executes the command you provide in your local environment.
- MCP-facing command execution has conservative workspace and command checks, but it is not operating-system isolation, a container runtime, or a malware scanner.
- Generated logs and artifacts may contain local paths, command arguments, environment details, metrics, or snippets of output. Review and redact before sharing.
- Reports and slides are deterministic summaries of recorded artifacts, not autonomous research conclusions.
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

Validate the repo-scoped Codex plugin guidance when plugin files change:

```bash
python /Users/anyuchen/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
```

Build a local package artifact without publishing:

```bash
python -m pip install build
python -m build
```

## Project Docs

- [Public alpha quickstart](docs/public-alpha-quickstart.md)
- [Deterministic public alpha demo](docs/demo-public-alpha.md)
- [Public alpha release notes](docs/public-alpha-release-notes.md)
- [MCP host configuration](docs/mcp-host-config.md)
- [Next-stage acceptance record](docs/next-stage-product-growth-acceptance.md)
- [Changelog](CHANGELOG.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [MIT license](LICENSE)
