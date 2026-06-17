# Contributing

Thanks for helping make Lab-Sidecar more useful. The project is still in a public-alpha posture, so contributions should favor small, reviewable improvements over broad rewrites.

## Project Direction

Lab-Sidecar is CLI-first, file-first, and local-first. The stable product path is:

```text
run/ingest -> collect -> figures -> report -> slides
```

Please keep changes aligned with that path unless an issue or maintainer explicitly scopes something else. MCP support is an experimental local adapter over existing services. Do not describe MCP, Codex host tooling, or supervisor/subagent execution coordination as the core Lab-Sidecar architecture.

Out of scope for ordinary contributions:

- Web UI or FastAPI surfaces.
- Remote runners or hosted services.
- AI-generated analysis as a default workflow.
- Animation, video, GIF, Manim, or Remotion output.
- Broad multi-agent framework abstractions.

## Development Setup

Use Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
```

Install the optional MCP dependency only when MCP behavior is part of the change:

```bash
python -m pip install -e ".[dev,mcp]"
```

## Local Checks

Run the test suite before opening a pull request:

```bash
python -m pytest
```

For CLI-facing changes, also run a short smoke flow in a disposable workspace:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
```

For MCP-facing changes, run:

```bash
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke
```

## Coding Guidelines

- Keep CLI, MCP, and host-facing adapters thin.
- Put reusable behavior in the core service modules.
- Prefer deterministic output and explicit provenance over hidden inference.
- Preserve user source files. Generated artifacts should live under `.lab-sidecar/`.
- Keep bounded summaries bounded; avoid returning full logs, metrics rows, report bodies, or binary artifacts through host-facing responses by default.
- Add tests when changing behavior. Update docs when changing user-visible commands, artifact formats, safety boundaries, or public-alpha limits.

## Documentation Guidelines

Use cautious language. It is fine to say that Lab-Sidecar can run local commands, collect local CSV/JSON metrics, render static figures, write deterministic report fragments, and create editable static PPTX drafts. Avoid claims about sandboxing, malware detection, remote execution, autonomous research conclusions, or production-grade hosted operation unless those claims are backed by implementation and tests.

## Pull Request Checklist

- The change is scoped and reviewable.
- Tests or docs checks were run and listed in the PR.
- User-facing docs were updated when behavior changed.
- No generated `.lab-sidecar/` task output, caches, or local environment files were committed.
- Security and safety wording distinguishes CLI local command execution from the experimental MCP safety gate.
- Public product claims remain CLI-first, file-first, and local-first.

## Commit Style

Use Conventional Commits where practical:

```text
docs: add release checklist
feat: add collector diagnostics
fix: preserve manifest artifact order
test: cover malformed json collection
```
