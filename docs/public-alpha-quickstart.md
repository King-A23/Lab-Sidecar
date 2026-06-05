# Public Alpha Quickstart

This quickstart is the 10-minute local path for Lab-Sidecar public alpha. It uses the built-in examples and does not require Web UI, FastAPI, AI services, animation, or a remote runner.

## Install

From the repository root:

```powershell
py -3 -m pip install -e ".[dev,mcp]"
```

If the `labsidecar` console script is not on `PATH`, use:

```powershell
py -3 -m lab_sidecar.cli.app --help
```

## Run The First Experiment

Create or choose a workspace, then copy or place the examples there:

```powershell
mkdir "$env:TEMP\lab-sidecar-alpha-workspace"
Copy-Item -Recurse C:\code\Lab-Sidecar\examples "$env:TEMP\lab-sidecar-alpha-workspace\examples"
cd "$env:TEMP\lab-sidecar-alpha-workspace"
```

Run the CLI chain:

```powershell
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv"
py -3 -m lab_sidecar.cli.app collect <task_id>
py -3 -m lab_sidecar.cli.app figures <task_id>
py -3 -m lab_sidecar.cli.app report <task_id>
py -3 -m lab_sidecar.cli.app slides <task_id>
py -3 -m lab_sidecar.cli.app artifacts <task_id>
```

Replace `<task_id>` with the id printed by `run`, for example `task_20260605_135142_494e27`.

Expected outputs are under:

```text
.lab-sidecar/tasks/<task_id>/
```

Key files:

- `metrics/normalized_metrics.csv`
- `figures/*.png` and `figures/*.svg`
- `reports/report-fragment.md`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

## Ingest Existing Results

For existing CSV/JSON result directories:

```powershell
py -3 -m lab_sidecar.cli.app ingest examples/csv-comparison
py -3 -m lab_sidecar.cli.app collect <task_id>
py -3 -m lab_sidecar.cli.app figures <task_id>
py -3 -m lab_sidecar.cli.app report <task_id>
py -3 -m lab_sidecar.cli.app slides <task_id>
```

For a project presentation-style example:

```powershell
py -3 -m lab_sidecar.cli.app ingest examples/project-presentation-pack
py -3 -m lab_sidecar.cli.app collect <task_id>
py -3 -m lab_sidecar.cli.app figures <task_id>
py -3 -m lab_sidecar.cli.app report <task_id>
py -3 -m lab_sidecar.cli.app slides <task_id> --template zh-project
```

## MCP Smoke

MCP support is experimental and local-first. Run the real stdio smoke with:

```powershell
py -3 C:\code\Lab-Sidecar\scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-alpha-mcp-smoke"
```

The smoke lists and calls:

- `run_experiment`
- `inspect_results`
- `make_figures`
- `generate_report_fragment`
- `generate_slides`

It uses `run_experiment(background=True)`, so the run tool returns a `task_id` first, then `inspect_results` is polled.

## Safety Boundary

CLI `run` is a user-explicit local command execution path. It captures logs and artifacts, but it does not apply the MCP confirmation/blocking policy.

MCP-facing `run_experiment` applies the workspace and dangerous-command safety gate. It blocks workspace-external cwd, `.lab-sidecar` cwd, destructive command patterns, and workspace-external absolute output/path arguments. It does not provide OS sandboxing, malware detection, container isolation, or global shell interception.

## Troubleshooting

If `collect` fails, open:

```text
.lab-sidecar/tasks/<task_id>/metrics/collection-summary.json
```

Common cases:

- No CSV/JSON candidates were found.
- CSV/JSON candidates existed, but files were empty, malformed, or did not contain recognized metric columns.
- The command wrote output outside the workspace or in a nested directory that `collect` does not scan.
