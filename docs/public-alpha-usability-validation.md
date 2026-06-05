# Public Alpha Usability Validation

Date: 2026-06-05

Scope: clean install and high-fidelity example validation outside the repository workspace. This is not a real external user project validation because inputs came from `examples/`.

## Environment

- repository: `C:\code\Lab-Sidecar`
- install root: `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-clean-install`
- clean workspace: `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-clean-workspace`
- MCP smoke workspace: `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-clean-mcp-smoke`
- venv python: `C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-clean-install\.venv\Scripts\python.exe`

Initial repository status was clean.

## Clean Install

Commands:

```powershell
py -3 -m venv "$env:TEMP\lab-sidecar-clean-install\.venv"
& "$env:TEMP\lab-sidecar-clean-install\.venv\Scripts\python.exe" -m pip install -e "C:\code\Lab-Sidecar[dev,mcp]"
& "$env:TEMP\lab-sidecar-clean-install\.venv\Scripts\python.exe" -m lab_sidecar.cli.app --help
& "$env:TEMP\lab-sidecar-clean-install\.venv\Scripts\labsidecar.exe" --help
```

Result:

- editable install succeeded
- `mcp==1.27.2` installed
- module entrypoint succeeded
- console script succeeded

## CLI High-Fidelity Examples

The examples directory was copied into:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-clean-workspace\examples
```

### simple-success

Commands:

```powershell
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "<venv-python> examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect task_20260605_135142_494e27
python -m lab_sidecar.cli.app figures task_20260605_135142_494e27
python -m lab_sidecar.cli.app report task_20260605_135142_494e27
python -m lab_sidecar.cli.app slides task_20260605_135142_494e27
python -m lab_sidecar.cli.app artifacts task_20260605_135142_494e27
```

Result:

- task_id: `task_20260605_135142_494e27`
- status: `completed`
- metrics rows: 5
- figures: 2
- report: `reports/report-fragment.md`
- slides: 7
- artifacts listed successfully

### csv-comparison

Commands:

```powershell
python -m lab_sidecar.cli.app ingest examples/csv-comparison
python -m lab_sidecar.cli.app collect task_20260605_135218_9f4a26
python -m lab_sidecar.cli.app figures task_20260605_135218_9f4a26
python -m lab_sidecar.cli.app report task_20260605_135218_9f4a26
python -m lab_sidecar.cli.app slides task_20260605_135218_9f4a26
```

Result:

- task_id: `task_20260605_135218_9f4a26`
- metrics rows: 15
- figures: 2
- slides: 7

### project-presentation-pack

Commands:

```powershell
python -m lab_sidecar.cli.app ingest examples/project-presentation-pack
python -m lab_sidecar.cli.app collect task_20260605_135233_8dabd5
python -m lab_sidecar.cli.app figures task_20260605_135233_8dabd5
python -m lab_sidecar.cli.app report task_20260605_135233_8dabd5
python -m lab_sidecar.cli.app slides task_20260605_135233_8dabd5 --template zh-project
```

Result:

- task_id: `task_20260605_135233_8dabd5`
- metrics rows: 16
- figures: 1
- slides: 7

### simple-failure

Commands:

```powershell
python -m lab_sidecar.cli.app run "<venv-python> examples/simple-failure/fail.py"
python -m lab_sidecar.cli.app report task_20260605_135249_283bbf
python -m lab_sidecar.cli.app slides task_20260605_135249_283bbf
```

Result:

- task_id: `task_20260605_135249_283bbf`
- status: `failed`
- report generated
- diagnostic slides: 5

## MCP Stdio Smoke

Initial run failed because the smoke script refused an existing empty workspace without its marker file. The script was updated to allow existing empty directories while still refusing non-empty unmarked directories.

Command:

```powershell
& "$env:TEMP\lab-sidecar-clean-install\.venv\Scripts\python.exe" C:\code\Lab-Sidecar\scripts\mcp_stdio_smoke.py --workspace "$env:TEMP\lab-sidecar-clean-mcp-smoke"
```

Result:

```json
{
  "workspace": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-clean-mcp-smoke",
  "server_log": "C:\\Users\\anyuc\\AppData\\Local\\Temp\\lab-sidecar-clean-mcp-smoke\\mcp-server.stderr.log",
  "tools": [
    "generate_report_fragment",
    "generate_slides",
    "inspect_results",
    "make_figures",
    "run_experiment"
  ],
  "task_id": "task_20260605_135355_085e3d",
  "run_status": "running",
  "final_status": "completed",
  "metrics_rows": 5,
  "figure_count": 2,
  "slide_count": 7,
  "blocked_command_status": "blocked",
  "artifact_count": 17
}
```

The omitted response contract remained:

```json
{
  "full_stdout": "omitted_by_default",
  "full_stderr": "omitted_by_default",
  "metrics_rows": "omitted_by_default",
  "artifact_bodies": "omitted_by_default"
}
```

## Changes From This Validation

- Improved `collect` failure messages:
  - no CSV/JSON candidates found
  - candidates found but no metrics collected
  - both point to `collection-summary.json`
- Added `docs/public-alpha-quickstart.md`.
- Updated README with shortest smoke commands and doc links.
- Fixed `scripts/mcp_stdio_smoke.py` to accept an existing empty workspace.

## Test Results

Final commands:

```powershell
py -3 -m pytest
git status --short
```

Results:

- `py -3 -m pytest`: 66 passed.
- `git status --short`: showed only this validation's intended working-tree changes before commit.

## Blocking

- None after the smoke script fix.

## Follow-Up

- Run the same validation on a real external course or experiment directory.
- Test concrete host-specific MCP config in actual hosts.
- Add MCP cancellation.
- Improve project figure grouping for mixed metrics.
- Improve long-label wrapping in project comparison slides.

## Out Of Scope

- Web UI, FastAPI, AI polishing, animation/media generation, remote runner, hosted MCP gateway.
- Claiming real external user project validation.
