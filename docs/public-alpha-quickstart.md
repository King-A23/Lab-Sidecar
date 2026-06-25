# Public Alpha Quickstart

This is the compact local path for Lab-Sidecar public alpha. For the fully
copyable first-user install flow, start with
[first-user-quickstart.md](first-user-quickstart.md). For scenario-specific
commands, use [recipes.md](recipes.md).

Lab-Sidecar is CLI-first, file-first, and local-first. This quickstart does not
require a browser app, HTTP service, hosted service, AI services, animation, or
a remote runner.

## Install

For released v0.1.x artifacts, install the GitHub release wheel in a virtual
environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install lab_sidecar-<version>-py3-none-any.whl
labsidecar --help
```

The wheel is the install-smoked release artifact. Use the matching source
archive or a clone for `examples/` and docs. PyPI is not the default install
promise for this public-alpha line unless a maintainer publishes and announces
it separately.

For development from a clone:

```bash
python -m pip install -e ".[dev]"
```

If the `labsidecar` console script is not on `PATH`, use:

```bash
python -m lab_sidecar.cli.app --help
```

On Windows PowerShell, use `py -3` instead of `python` if that is your
configured launcher. If you plan to run the optional MCP smoke, install
`.[dev,mcp]` from a clone instead of `.[dev]`.

## Create A Workspace

From a source checkout or extracted source archive:

```bash
export LABSIDECAR_REPO="$(pwd)"
export LABSIDECAR_WS="${TMPDIR:-/tmp}/lab-sidecar-alpha-workspace"
rm -rf "$LABSIDECAR_WS"
mkdir -p "$LABSIDECAR_WS"
cp -R "$LABSIDECAR_REPO/examples" "$LABSIDECAR_WS/examples"
cd "$LABSIDECAR_WS"
labsidecar init
labsidecar doctor
```

PowerShell equivalent:

```powershell
$env:LABSIDECAR_REPO = (Get-Location).Path
$env:LABSIDECAR_WS = Join-Path $env:TEMP "lab-sidecar-alpha-workspace"
Remove-Item -Recurse -Force $env:LABSIDECAR_WS -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $env:LABSIDECAR_WS | Out-Null
Copy-Item -Recurse "$env:LABSIDECAR_REPO\examples" "$env:LABSIDECAR_WS\examples"
Set-Location $env:LABSIDECAR_WS
labsidecar init
labsidecar doctor
```

## Run The First Experiment

```bash
labsidecar run "python examples/simple-success/train.py --output metrics.csv"
export TASK_ID=<printed_task_id>
labsidecar collect "$TASK_ID"
labsidecar figures "$TASK_ID"
labsidecar report "$TASK_ID"
labsidecar slides "$TASK_ID"
labsidecar validate "$TASK_ID"
labsidecar package "$TASK_ID" --output "lab-sidecar-package-$TASK_ID"
labsidecar package-verify "lab-sidecar-package-$TASK_ID"
labsidecar artifacts "$TASK_ID"
labsidecar open "$TASK_ID"
```

PowerShell:

```powershell
labsidecar run "py -3 examples/simple-success/train.py --output metrics.csv"
$env:TASK_ID = "<printed_task_id>"
labsidecar collect $env:TASK_ID
labsidecar figures $env:TASK_ID
labsidecar report $env:TASK_ID
labsidecar slides $env:TASK_ID
labsidecar validate $env:TASK_ID
$PACKAGE_DIR = "lab-sidecar-package-$($env:TASK_ID)"
labsidecar package $env:TASK_ID --output $PACKAGE_DIR
labsidecar package-verify $PACKAGE_DIR
labsidecar artifacts $env:TASK_ID
labsidecar open $env:TASK_ID
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
- `provenance/traceability.json`

The package directory includes `package-summary.json`, `artifact-index.json`,
`artifact-index.sha256`, and `redaction-notes.md`. `package-verify` checks the
package index digest, indexed file hashes and sizes, and rejects unexpected
files.

## Existing Results And Comparisons

For existing CSV/JSON result directories and saved comparison packages, use the
recipe gallery:

```text
docs/recipes.md
```

Saved comparison artifacts live under
`.lab-sidecar/comparisons/$COMPARISON_ID/`. They are descriptive only: no
statistical significance, model superiority, remote execution, Web UI, MCP
schema expansion, or default AI analysis is added.

## MCP Smoke

MCP support is experimental and local-first. Run the real stdio smoke only when
MCP behavior or packaging metadata is in scope:

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
- CSV/JSON candidates existed, but files were empty, malformed, or did not
  contain recognized metric columns.
- The command wrote output outside the workspace or in a nested directory that
  `collect` does not scan.

If `figures` reports an unsupported chart type, deterministic figures may still
be working as intended. Lab-Sidecar supports deterministic `line`, `bar`, and
`box` charts first. To record a bounded fallback request for an explicit
unsupported chart spec, run:

```bash
labsidecar figures "$TASK_ID" --spec figure.yaml --fallback bounded
```

Fallback is default-off. See
`docs/alpha4-bounded-chart-fallback-operator-guide.md` for status meanings
(`not_needed`, `unavailable`, `rejected`, `adopted`) and troubleshooting.

Explicit figure specs can be a legacy single YAML object or a multi-figure
`figures:` YAML file. See `docs/figure-specs.md` for copyable examples.
