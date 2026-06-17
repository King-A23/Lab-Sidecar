# Public Alpha Quickstart

This is the 10-minute local path for Lab-Sidecar public alpha. It uses built-in
examples and does not require a browser app, HTTP service, AI services,
animation, or a remote runner.

## Install

From the repository root:

```bash
python -m pip install -e ".[dev]"
```

If the `labsidecar` console script is not on `PATH`, use:

```bash
python -m lab_sidecar.cli.app --help
```

On Windows PowerShell, use `py -3` instead of `python` if that is your
configured launcher.

If you plan to run the optional MCP smoke, install `.[dev,mcp]` instead of
`.[dev]`.

## Create A Workspace

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

PowerShell equivalent:

```powershell
$env:LABSIDECAR_REPO = (Get-Location).Path
$env:LABSIDECAR_WS = Join-Path $env:TEMP "lab-sidecar-alpha-workspace"
Remove-Item -Recurse -Force $env:LABSIDECAR_WS -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $env:LABSIDECAR_WS | Out-Null
Copy-Item -Recurse "$env:LABSIDECAR_REPO\examples" "$env:LABSIDECAR_WS\examples"
Set-Location $env:LABSIDECAR_WS
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app doctor
```

## Run The First Experiment

```bash
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
python -m lab_sidecar.cli.app open "$TASK_ID"
```

PowerShell:

```powershell
py -3 -m lab_sidecar.cli.app run "py -3 examples/simple-success/train.py --output metrics.csv"
$env:TASK_ID = "<printed_task_id>"
py -3 -m lab_sidecar.cli.app collect $env:TASK_ID
py -3 -m lab_sidecar.cli.app figures $env:TASK_ID
py -3 -m lab_sidecar.cli.app report $env:TASK_ID
py -3 -m lab_sidecar.cli.app slides $env:TASK_ID
py -3 -m lab_sidecar.cli.app artifacts $env:TASK_ID
py -3 -m lab_sidecar.cli.app open $env:TASK_ID
```

Replace `<printed_task_id>` with the id printed by `run`, for example
`task_20260608_132834_153843`.

Expected files are under:

```text
.lab-sidecar/tasks/$TASK_ID/
```

Key files:

- `metrics/normalized_metrics.csv`
- `figures/*.png` and `figures/*.svg`
- `reports/report-fragment.md`
- `slides/presentation-draft.pptx`
- `slides/slides-summary.json`

## Ingest Existing Results

For existing CSV/JSON result directories:

```bash
python -m lab_sidecar.cli.app ingest examples/csv-comparison
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
```

For a project presentation-style example:

```bash
python -m lab_sidecar.cli.app ingest examples/project-presentation-pack
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID" --template zh-project
```

Use `python -m lab_sidecar.cli.app list` to find recent tasks, and
`python -m lab_sidecar.cli.app open "$TASK_ID"` to print the artifact directory.

## MCP Smoke

MCP support is experimental and local-first. Run the real stdio smoke with:

```bash
python "$LABSIDECAR_REPO/scripts/mcp_stdio_smoke.py" --workspace "${TMPDIR:-/tmp}/lab-sidecar-alpha-mcp-smoke"
```

The smoke lists and calls deterministic V1 tools and verifies the V2 bounded
mirror tools are registered. It uses `run_experiment(background=True)`, so the
run tool returns a `task_id` first, then `inspect_results` is polled.

## Safety Boundary

CLI `run` is a user-explicit local command execution path. It captures logs and
artifacts, but it does not apply the MCP confirmation/blocking policy.

MCP-facing command execution applies the workspace and dangerous-command safety
gate. It blocks workspace-external cwd, `.lab-sidecar` cwd, destructive command
patterns, and workspace-external absolute output/path arguments. It does not
provide operating-system isolation, malware scanning, container isolation, or
global shell interception.

## Troubleshooting

If `collect` fails, open:

```text
.lab-sidecar/tasks/$TASK_ID/metrics/collection-summary.json
```

Common cases:

- No CSV/JSON candidates were found.
- CSV/JSON candidates existed, but files were empty, malformed, or did not contain recognized metric columns.
- The command wrote output outside the workspace or in a nested directory that `collect` does not scan.
