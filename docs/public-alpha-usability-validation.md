# Public Alpha Usability Validation

Date: 2026-06-05

Scope: clean install and high-fidelity example validation outside the repository workspace. The first validation used `examples/`; a later validation in this document used a real local project directory under `C:\code`. This still is not broad external user acceptance testing.

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

## Real Local Project Directory Validation

Selected source directory:

```text
C:\code\CN-Lab1-Windows-VS2017\docs\测试记录\参数优化-DATA_TIMER-MAX_PHL_BACKLOG
```

Reason:

- It is outside the Lab-Sidecar repository.
- It contains real course/network lab experiment output, including `all-results.csv`.
- The metrics are not ML-shaped; columns include `Score`, `AvgUtil`, `DataTimeoutPerMin`, `DATA_TIMER`, `BACKLOG_FACTOR`, and `BadCrcTotal`.

Workspace:

```text
C:\Users\anyuc\AppData\Local\Temp\lab-sidecar-cnlab-validation-3
```

The validation used `ingest`; no `.lab-sidecar` directory was written into the selected source project.

Initial findings:

- `collect` initially failed because metric field detection favored ML-style fields and did not recognize system/network experiment fields.
- After metric collection was fixed, `figures` initially failed because auto bar chart selection did not recognize system/network category and metric columns.

Minimal fixes:

- Extended metric detection for generic experiment fields such as score, utilization, timeout, duration, packet, and error counts.
- Added aliases for real observed fields including `AvgUtil`, `AUtil`, `BUtil`, `DurationSec`, `WallSeconds`, `DataTimeoutPerMin`, `AckTimeoutTotal`, `SendAckTotal`, `SendNakTotal`, and `BadCrcTotal`.
- Extended auto figure selection to use categories such as `DATA_TIMER`, `BACKLOG_FACTOR`, `Stage`, and `Scenario`, and metrics such as `Score`, `AvgUtil`, `DataTimeoutPerMin`, `BadCrcTotal`, and `WallSeconds`.

Final commands:

```powershell
$workspace = Join-Path $env:TEMP 'lab-sidecar-cnlab-validation-3'
$source = 'C:\code\CN-Lab1-Windows-VS2017\docs\测试记录\参数优化-DATA_TIMER-MAX_PHL_BACKLOG'
Push-Location $workspace
py -3 -m lab_sidecar.cli.app init
py -3 -m lab_sidecar.cli.app ingest $source
py -3 -m lab_sidecar.cli.app collect task_20260605_141018_6170ec
py -3 -m lab_sidecar.cli.app figures task_20260605_141018_6170ec
py -3 -m lab_sidecar.cli.app report task_20260605_141018_6170ec
py -3 -m lab_sidecar.cli.app slides task_20260605_141018_6170ec --template zh-project
py -3 -m lab_sidecar.cli.app artifacts task_20260605_141018_6170ec
Pop-Location
```

Result:

- task_id: `task_20260605_141018_6170ec`
- candidate files: 1
- metrics rows: 25
- detected fields: `DurationSec`, `AUtil`, `BUtil`, `AvgUtil`, `SendAckTotal`, `AckTimeoutTotal`, `DataTimeoutTotal`, `DataTimeoutPerMin`, `SendNakTotal`, `BadCrcTotal`, `Score`, `WallSeconds`
- figures: 1
  - `figures/bar_score_by_data_timer.png`
  - `figures/bar_score_by_data_timer.svg`
  - x: `DATA_TIMER`
  - y: `Score`
- report: `reports/report-fragment.md`
- slides: `slides/presentation-draft.pptx`
- zh-project slide count: 7
- artifact list succeeded

Remaining limitations from this real directory:

- `ingest` records candidates from the selected source directory. Nested experiment outputs still need either selecting the result folder directly or future explicit recursive/source declaration support.
- Slides key comparison grouped by `source_file`, which is not ideal for this one-file dataset; future project comparison should use a domain column such as `DATA_TIMER`, `Stage`, or a declared grouping field when available.
- Dense system experiment tables are safely truncated in slides, but the table prioritization is still generic.

## Changes From This Validation

- Improved `collect` failure messages:
  - no CSV/JSON candidates found
  - candidates found but no metrics collected
  - both point to `collection-summary.json`
- Added `docs/public-alpha-quickstart.md`.
- Updated README with shortest smoke commands and doc links.
- Fixed `scripts/mcp_stdio_smoke.py` to accept an existing empty workspace.
- Extended collector and figure auto-selection for real system/network experiment metrics found in `C:\code\CN-Lab1-Windows-VS2017`.

## Test Results

Final commands:

```powershell
py -3 -m pytest
git status --short
```

Results:

- `py -3 -m pytest`: 66 passed.
- `git status --short`: showed only this validation's intended working-tree changes before commit.

After the real local project directory hardening, `py -3 -m pytest` passed again with 67 tests.

## Blocking

- None after the smoke script fix and the real local directory metric/figure hardening.

## Follow-Up

- Repeat validation on external user-owned projects, not only local repositories already present under `C:\code`.
- Test concrete host-specific MCP config in actual hosts.
- Add MCP cancellation.
- Improve project figure grouping for mixed metrics.
- Improve long-label wrapping in project comparison slides.
- Improve declared grouping support for dense system experiment comparisons.

## Out Of Scope

- Web UI, FastAPI, AI polishing, animation/media generation, remote runner, hosted MCP gateway.
- Claiming real external user project validation.
