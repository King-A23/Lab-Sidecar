# Public Alpha Demo

Date: 2026-06-08

This is the deterministic public-alpha demo path for Lab-Sidecar. It uses
checked-in examples, disposable workspaces, and task-local artifacts under
`.lab-sidecar/tasks/<TASK_ID>/`.

Lab-Sidecar is the local artifact sidecar in this demo. Codex supervisor agents
may coordinate repository work, but Lab-Sidecar itself remains a CLI/MCP tool
surface with bounded responses and deterministic artifact records.

## Prerequisites

From the repository root:

```bash
python -m pip install -e ".[dev,mcp]"
```

Use `py -3` instead of `python` on Windows if that is your configured launcher.

## Preview Assets

The README previews are generated from the real `examples/csv-comparison`
scenario:

- `docs/assets/demo/csv-comparison-val-accuracy.png`
- `docs/assets/demo/csv-comparison-report-preview.png`

The figure PNG is copied from a Lab-Sidecar task output. The report preview is
a rendered image of the generated `reports/report-fragment.md`. A slide preview
image is not committed because reliable PPTX image export is environment
dependent; the demo still generates `slides/presentation-draft.pptx` and
`slides/slides-summary.json`.

## Demo Workspace

Create a fresh workspace:

```bash
export LABSIDECAR_REPO="$(pwd)"
export LABSIDECAR_DEMO_WS="${TMPDIR:-/tmp}/lab-sidecar-public-alpha-demo-$(date +%Y%m%d%H%M%S)"
mkdir -p "$LABSIDECAR_DEMO_WS"
cp -R "$LABSIDECAR_REPO/examples" "$LABSIDECAR_DEMO_WS/examples"
cd "$LABSIDECAR_DEMO_WS"
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app doctor
```

## Scenario 1: Successful Run

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

Expected files:

- `.lab-sidecar/tasks/$TASK_ID/manifest.json`
- `.lab-sidecar/tasks/$TASK_ID/stdout.log`
- `.lab-sidecar/tasks/$TASK_ID/stderr.log`
- `.lab-sidecar/tasks/$TASK_ID/metrics/normalized_metrics.csv`
- `.lab-sidecar/tasks/$TASK_ID/figures/*.png`
- `.lab-sidecar/tasks/$TASK_ID/reports/report-fragment.md`
- `.lab-sidecar/tasks/$TASK_ID/slides/presentation-draft.pptx`
- `.lab-sidecar/tasks/$TASK_ID/slides/slides-summary.json`

## Scenario 2: Multi-Run CSV Comparison

```bash
python -m lab_sidecar.cli.app ingest examples/csv-comparison
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
```

Expected result: Lab-Sidecar normalizes three source CSV files, records source
provenance, creates comparison figures, writes a deterministic report fragment,
and drafts a static editable PPTX.

## Scenario 3: Course Project Presentation Pack

```bash
python -m lab_sidecar.cli.app ingest examples/project-presentation-pack
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app collect "$TASK_ID"
python -m lab_sidecar.cli.app figures "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID" --template zh-project
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
```

Expected result: Lab-Sidecar creates a compressed project-style static PPTX
draft from metrics, figures, report text, and source artifact metadata. The
deck is editable and deterministic; it is not AI-polished and contains no
animation or video output.

## Scenario 4: Failed Run Diagnosis

```bash
python -m lab_sidecar.cli.app run "python examples/simple-failure/fail.py"
export TASK_ID=<printed_task_id>
python -m lab_sidecar.cli.app status "$TASK_ID"
python -m lab_sidecar.cli.app report "$TASK_ID"
python -m lab_sidecar.cli.app slides "$TASK_ID"
python -m lab_sidecar.cli.app artifacts "$TASK_ID"
```

Expected result: the task status is `failed`, exit code and stderr are
preserved in task-local records, and report/PPTX output contains bounded
diagnostic content.

## Optional MCP Stdio Smoke

Run the real stdio MCP smoke in a separate temporary workspace:

```bash
python "$LABSIDECAR_REPO/scripts/mcp_stdio_smoke.py" --workspace "${TMPDIR:-/tmp}/lab-sidecar-public-alpha-mcp-smoke-$(date +%Y%m%d%H%M%S)"
```

Expected result:

- the client lists and calls the V1 tools
- the server also lists the V2 mirror tools
- `run_experiment(background=True)` returns a `task_id`
- polling `inspect_results` reaches `completed`
- default tool responses return bounded summaries and artifact metadata
- complete command strings, stdout, stderr, metrics rows, report bodies, PPT
  contents, worker transcripts, and artifact bodies are omitted by default

## Boundary Language

Use this wording when explaining the agent boundary:

```text
Codex can use a supervisor/subagent work pattern to coordinate development or
demo preparation. Lab-Sidecar is the local sidecar tool surface that stores
task records and artifacts. It returns task IDs, summaries, risk flags, next
actions, and bounded artifact paths or previews; it does not become the
supervisor agent, and it does not return full task bodies by default.
```

Avoid claiming that public alpha includes browser UI, HTTP service, hosted
execution, remote runners, default AI-generated conclusions, animation/video
output, operating-system isolation, malware scanning, or a hardened remote MCP
service boundary.
