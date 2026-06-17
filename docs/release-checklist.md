# Release Checklist

Use this checklist for cautious public-alpha releases. It is intentionally biased toward local CLI behavior and artifact reproducibility.

## Scope Gate

- Confirm the release is still CLI-first, file-first, and local-first.
- Confirm the release does not introduce Web UI, FastAPI, remote runner, hosted service, or broad multi-agent framework behavior unless explicitly scoped and tested.
- Confirm MCP claims say "experimental local adapter" and do not imply a hardened remote service boundary.
- Confirm Codex supervisor agents or subagents are described only as development coordination, not Lab-Sidecar product architecture.
- Confirm generated artifacts stay under `.lab-sidecar/` and user source files are not modified, moved, deleted, or repaired.

## Repository Gate

- Confirm the `LICENSE` file and package license metadata match the intended release license.
- Update `CHANGELOG.md`.
- Update release notes such as `docs/public-alpha-release-notes.md` when user-visible behavior changes.
- Check `README.md`, `CONTRIBUTING.md`, and `SECURITY.md` for stale commands or overstated claims.
- Confirm `pyproject.toml` version, dependencies, optional extras, classifiers, and README metadata are accurate.
- Confirm no generated caches, `.lab-sidecar/` task output, build artifacts, local virtualenvs, or private data are staged.

## Quality Gate

From a clean environment or disposable workspace:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

Run a CLI smoke path:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

For public alpha, also validate an ingest path:

```bash
python -m lab_sidecar.cli.app ingest examples/csv-comparison
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
```

If MCP packaging or MCP behavior changed:

```bash
python -m pip install -e ".[dev,mcp]"
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke
```

## Safety And Privacy Gate

- Verify docs distinguish CLI `run` from MCP-facing `run_experiment` safety behavior.
- Verify no docs claim OS sandboxing, malware detection, shell interception, container isolation, or multi-user policy.
- Inspect generated logs and summaries for accidental secrets before publishing screenshots or examples.
- Verify host-facing responses remain bounded by default and do not include full stdout, stderr, metrics rows, report bodies, PPTX contents, or arbitrary artifact bodies.
- Record any security-relevant change in `CHANGELOG.md` and release notes.

## Packaging Gate

- Build the distribution in a clean checkout if publishing packages is in scope.
- Inspect package contents for missing docs or accidental local files.
- Verify the console script works after install:

```bash
labsidecar --help
```

- Verify the module entrypoint works:

```bash
python -m lab_sidecar.cli.app --help
```

## Release Notes

Release notes should include:

- Version and date.
- Supported install command.
- Main workflow summary.
- Validation commands and results.
- Known limitations.
- Security model notes.
- Breaking changes, if any.
- Upgrade notes, if any.

## Post-Release

- Tag the release only after checks pass.
- Archive the exact validation commands and results in docs or the release description.
- Open follow-up issues for deferred work instead of broadening the release scope at the last minute.
