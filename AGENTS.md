# Repository Guidelines

## Project Structure & Module Organization

Lab-Sidecar is currently in Phase 0: planning, specifications, and examples. The main roadmap is `PRODUCT_ITERATION_PLAN.md`. Supporting design documents live in `docs/`, including CLI behavior, artifact protocol, chart guidelines, architecture, and use cases. Minimal fixtures live in `examples/`:

- `examples/simple-success/` for successful experiment runs.
- `examples/simple-failure/` for error and stderr handling.
- `examples/csv-comparison/` for multi-run metric comparison.
- `examples/algorithm-benchmark/` for JSON result parsing.
- `examples/project-presentation-pack/` for report and presentation material preparation.

When implementation begins, source modules should follow the planned `lab_sidecar/` layout: `core/`, `runner/`, `collectors/`, `figures/`, `reports/`, `cli/`, with later `api/` and `mcp/` adapters.

## Build, Test, and Development Commands

There is no build system yet. Use the examples to validate assumptions:

```bash
python examples/simple-success/train.py --output metrics.csv
python examples/simple-failure/fail.py
```

Planned V1 commands are documented in `docs/cli-spec.md`, for example:

```bash
labsidecar init
labsidecar run "python train.py --config configs/exp.yaml"
labsidecar collect <task_id>
labsidecar figures <task_id>
labsidecar report <task_id>
```

## Coding Style & Naming Conventions

Use Python 3.11+ for implementation. Prefer Typer for CLI, Pydantic for schemas, YAML for user-facing config, pandas for data handling, and matplotlib for first-pass figures. Keep CLI/API/MCP layers thin; business logic belongs in the core library. Use snake_case for Python modules and functions, PascalCase for data models, and kebab-case for documentation filenames when practical.

## Testing Guidelines

No test suite exists yet. When code is added, use `pytest` with tests under `tests/` and fixtures based on `examples/`. Name tests `test_<behavior>.py`. Cover task lifecycle, artifact creation, CSV/JSON collection, chart rendering, and report generation. Do not commit generated caches such as `__pycache__/`.

## Commit & Pull Request Guidelines

This directory is not currently a Git repository, so there is no local commit history to follow. Use Conventional Commits once Git is initialized, for example `docs: add artifact protocol` or `feat: add CLI task runner`. Pull requests should include a short summary, changed docs or examples, validation commands, and screenshots only when UI or chart output changes.

## Agent-Specific Instructions

Prioritize CLI-first, file-first work. Do not introduce Web UI, FastAPI, MCP, or AI-dependent workflows before the local `run -> collect -> figures -> report` path is stable.
