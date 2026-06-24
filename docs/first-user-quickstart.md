# First-User Quickstart

This is the release-wheel path for a first Lab-Sidecar user. It installs a
published GitHub release wheel, uses the matching source archive only for
examples, runs the simple demo, creates deliverable artifacts, and verifies the
shareable package.

Use a version that has a published GitHub release. The examples below use
`0.1.5` because it is the latest published release verified during this
implementation slice. After maintainers publish v0.1.6, replace `0.1.5` with
`0.1.6`.

PyPI is not the default install promise for this public-alpha line unless a
maintainer publishes and announces it separately.

## macOS Or Linux

Create a workspace and virtual environment:

```bash
VERSION=0.1.5
mkdir lab-sidecar-first-run
cd lab-sidecar-first-run
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
```

Download and install the GitHub release wheel:

```bash
curl -L -o "lab_sidecar-${VERSION}-py3-none-any.whl" \
  "https://github.com/King-A23/Lab-Sidecar/releases/download/v${VERSION}/lab_sidecar-${VERSION}-py3-none-any.whl"
python -m pip install "lab_sidecar-${VERSION}-py3-none-any.whl"
```

Download the matching source archive for examples:

```bash
curl -L -o "lab-sidecar-v${VERSION}.tar.gz" \
  "https://github.com/King-A23/Lab-Sidecar/archive/refs/tags/v${VERSION}.tar.gz"
tar -xzf "lab-sidecar-v${VERSION}.tar.gz"
cp -R "Lab-Sidecar-${VERSION}/examples" examples
```

Confirm the installed CLI works:

```bash
labsidecar --help
labsidecar init
labsidecar doctor
```

Run the demo and create artifacts:

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

Replace `<printed_task_id>` with the id printed by `run`, such as
`task_20260625_104500_abc123`.

## Windows PowerShell

Create a workspace and virtual environment:

```powershell
$Version = "0.1.5"
New-Item -ItemType Directory -Path "lab-sidecar-first-run" | Out-Null
Set-Location "lab-sidecar-first-run"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install --upgrade pip
```

Download and install the GitHub release wheel:

```powershell
Invoke-WebRequest `
  -Uri "https://github.com/King-A23/Lab-Sidecar/releases/download/v$Version/lab_sidecar-$Version-py3-none-any.whl" `
  -OutFile "lab_sidecar-$Version-py3-none-any.whl"
py -3 -m pip install "lab_sidecar-$Version-py3-none-any.whl"
```

Download the matching source archive for examples:

```powershell
Invoke-WebRequest `
  -Uri "https://github.com/King-A23/Lab-Sidecar/archive/refs/tags/v$Version.zip" `
  -OutFile "lab-sidecar-v$Version.zip"
Expand-Archive "lab-sidecar-v$Version.zip" -DestinationPath .
Copy-Item -Recurse "Lab-Sidecar-$Version\examples" ".\examples"
```

Run the demo:

```powershell
labsidecar --help
labsidecar init
labsidecar doctor
labsidecar run "py -3 examples/simple-success/train.py --output metrics.csv"
$env:TASK_ID = "<printed_task_id>"
labsidecar collect $env:TASK_ID
labsidecar figures $env:TASK_ID
labsidecar report $env:TASK_ID
labsidecar slides $env:TASK_ID
labsidecar validate $env:TASK_ID
$PackageDir = "lab-sidecar-package-$($env:TASK_ID)"
labsidecar package $env:TASK_ID --output $PackageDir
labsidecar package-verify $PackageDir
labsidecar artifacts $env:TASK_ID
labsidecar open $env:TASK_ID
```

If your shell cannot find `labsidecar`, use
`python -m lab_sidecar.cli.app <command>` on macOS/Linux or
`py -3 -m lab_sidecar.cli.app <command>` on Windows.

## Expected Artifacts

The task artifacts stay under:

```text
.lab-sidecar/tasks/$TASK_ID/
```

Expected task artifact categories:

- `manifest.json`, `stdout.log`, `stderr.log`, and reproduce metadata
- `metrics/normalized_metrics.csv`, `metrics/normalized_metrics.json`, and
  `metrics/collection-summary.json`
- deterministic `figures/*.png`, `figures/*.svg`, `figure-spec.yaml`, and
  `figure-summary.json`
- `reports/report-fragment.md` and `reports/report-summary.json`
- `slides/presentation-draft.pptx` and `slides/slides-summary.json`
- `provenance/traceability.json`

The package directory includes:

- `README.md`
- `manifest.json`
- `package-summary.json`
- `artifact-index.json`
- `artifact-index.sha256`
- `redaction-notes.md`
- allowlisted metrics, figures, report, slides, reproduce, and provenance
  artifacts when present

`package-verify` checks package digests, indexed file hashes and sizes, package
summary parseability, and unexpected files.

## Common Failures

- The wheel URL returns 404: use a version that has a published GitHub release.
- `labsidecar` is not found: activate the virtual environment or use the module
  entrypoint.
- `python` is not found on Windows: use `py -3`.
- `collect` finds no metrics: confirm the command wrote `metrics.csv` inside
  the demo workspace, then inspect
  `.lab-sidecar/tasks/$TASK_ID/metrics/collection-summary.json` if it exists.
- `figures`, `report`, or `slides` says metrics are missing: run
  `labsidecar collect "$TASK_ID"` first.
- `package` refuses the output directory: choose a new path or remove the
  existing empty test output directory.
- `doctor` warns that the optional MCP SDK is not installed: that is fine for
  the CLI quickstart. Install the `mcp` extra only when working on local MCP
  behavior.

## Boundaries

This quickstart does not add or require a Web UI, FastAPI or HTTP service,
hosted service, cloud sync, remote runner, default AI analysis, statistical
significance, model superiority, paper conclusions, deployment advice, or OS
sandboxing. CLI `run` is a user-explicit local command execution path.
