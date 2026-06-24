# Repository Guidelines

## Project Structure & Module Organization

Lab-Sidecar is a local-first, file-first Python package for running or ingesting local experiment results, collecting metrics, and generating reproducible report and presentation artifacts. The primary path remains CLI-first: `run/ingest -> collect -> figures -> report -> slides`.

Core source lives under `lab_sidecar/`:

- `core/` for task manifests, paths, configuration, and provenance.
- `runner/` for local process execution and task lifecycle behavior.
- `collectors/` for CSV/JSON discovery, parsing, and normalization.
- `figures/` for deterministic chart specs and rendering.
- `reports/` and `slides/` for deterministic Markdown and PPTX artifacts.
- `storage/` for the local SQLite index and artifact store helpers.
- `cli/` for the Typer command surface.
- `mcp/` for the experimental local MCP adapter over existing services.
- `intelligence/` for V2 local worker and host-integration scaffolding.

Supporting design and acceptance records live in `docs/`. Example fixtures live in `examples/` and should stay small enough for repository tests and manual smoke runs.

## Build, Test, and Development Commands

Install the package in editable mode:

```bash
python -m pip install -e ".[dev]"
```

Install the optional MCP SDK only when working on MCP-facing behavior:

```bash
python -m pip install -e ".[dev,mcp]"
```

Run the test suite:

```bash
python -m pytest
```

Useful CLI smoke commands:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
```

Run the optional stdio MCP smoke only when MCP behavior or packaging metadata is in scope:

```bash
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke
```

## Coding Style & Naming Conventions

Use Python 3.11+. Keep CLI, MCP, and host-facing layers thin; business logic belongs in reusable services under `core`, `runner`, `collectors`, `figures`, `reports`, `slides`, and `storage`. Prefer Typer for CLI, Pydantic for schemas, YAML for user-facing config, pandas for data handling, matplotlib for figures, and python-pptx for static decks.

Use snake_case for Python modules and functions, PascalCase for data models, and kebab-case for documentation filenames when practical. Keep generated user artifacts under `.lab-sidecar/`; do not modify, delete, or move user source files as a side effect of collection or rendering.

## Testing Guidelines

Use `pytest` with tests under `tests/`, backed by fixtures from `examples/` when practical. Name tests `test_<behavior>.py`. Cover task lifecycle, artifact creation, CSV/JSON collection, chart rendering, report and slide generation, bounded previews, failure diagnostics, and provenance. Do not commit generated caches such as `__pycache__/`, local `.lab-sidecar/` task output, or temporary presentation/rendering artifacts.

## Commit & Pull Request Guidelines

Use Conventional Commits, for example `docs: add release checklist` or `feat: add collector diagnostics`. Pull requests should include a concise summary, changed docs or examples, validation commands, and screenshots only when UI, chart, or slide output changes. Keep unrelated formatting and refactors out of feature or docs-readiness changes.

## Scope Boundaries

All coding agents must treat [docs/current-scope.md](docs/current-scope.md) as
the current development boundary. Historical roadmap documents are useful
context, but they are not permission to expand the active alpha scope.

Keep public claims cautious: Lab-Sidecar is CLI-first, file-first, and local-first. The MCP adapter is experimental and local; it does not turn Lab-Sidecar into a hosted service, remote runner, Web UI, FastAPI app, or general multi-agent framework. CLI `run` is a user-explicit local command execution path, while MCP-facing `run_experiment` has a separate conservative workspace and command safety gate.

Codex supervisor agents and subagents may be used to coordinate repository work, audits, or implementation slices. They are execution coordination for development, not Lab-Sidecar product architecture.

## Agent-Specific Instructions

Read the relevant docs and tests before editing. Do not revert concurrent changes made by others. Keep edits scoped to the requested slice, preserve the local `run/ingest -> collect -> figures -> report -> slides` path, and avoid touching `lab_sidecar/mcp` code or MCP tests unless MCP behavior is explicitly in scope. Do not add Web UI, FastAPI/HTTP service, hosted service behavior, cloud sync, remote runner behavior, or general multi-agent framework behavior unless the user explicitly changes the current scope.
