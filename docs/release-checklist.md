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

## Required Local Checks

From a clean environment or disposable workspace:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m pip install build
python -m build
python scripts/release_check.py --version <version>
python scripts/release_check.py --version <version> --tag v<version> --require-clean-git
python -m lab_sidecar.cli.app --help
python scripts/cli_full_smoke.py --workspace /tmp/lab-sidecar-cli-full-smoke --repo "$(pwd)"
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"
python scripts/release_asset_smoke.py --wheel dist/lab_sidecar-<version>-py3-none-any.whl --version <version> --workspace /tmp/lab-sidecar-release-asset-smoke --repo "$(pwd)"
git diff --check
test ! -e .lab-sidecar
```

The smoke scripts are intended to run from a repository checkout. `scripts/`
is packaged in sdists for release validation from source, but the wheel smoke
installs the built wheel into an isolated venv before exercising the installed
CLI.

`scripts/release_check.py` is a pre-tag local verifier. It checks version
consistency across `pyproject.toml`, `lab_sidecar/__init__.py`, and
`CHANGELOG.md`, confirms unstaged, staged, and committed whitespace checks,
rejects root `.lab-sidecar/` state, verifies target-version wheel/sdist names
and distribution metadata under `dist/`, rejects stale Lab-Sidecar artifacts
from older versions, and reports SHA-256 digests. It does not create tags,
releases, uploads, or publishes. Use `--require-clean-git` after committing
release-candidate changes and before creating a tag.

`scripts/release_asset_smoke.py` verifies a supplied wheel artifact, such as a
wheel downloaded from a GitHub release or a local `dist/` wheel. Local wheel
paths are the normal release check; HTTP(S) wheel URLs are manual release
verification inputs and should not be required by the default test suite. Pass
`--version <version>` so the smoke confirms the installed package metadata is
the expected release version.

Release smoke can run in either online or offline dependency mode:

- Online mode uses normal pip index access to install the build backend and
  runtime dependencies.
- Offline mode uses a maintainer-prepared wheelhouse and pip environment
  variables. Do not vendor third-party wheels into this repository or commit a
  wheelhouse.

Prepare a wheelhouse from an online environment:

```bash
python -m pip download -d /tmp/lab-sidecar-wheelhouse \
  build hatchling \
  matplotlib pandas Pillow pydantic python-pptx pyyaml typer
```

Use the wheelhouse in an offline release-smoke environment:

```bash
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/lab-sidecar-wheelhouse \
python -m pip install build

PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/lab-sidecar-wheelhouse \
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"
```

See [offline-release-smoke.md](offline-release-smoke.md) for the concise
offline release-smoke operator notes.

Manual quick CLI path when debugging a failure:

```bash
python -m lab_sidecar.cli.app init
python -m lab_sidecar.cli.app run "python examples/simple-success/train.py --output metrics.csv"
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app validate <task_id>
python -m lab_sidecar.cli.app package <task_id> --output /tmp/lab-sidecar-package-<task_id>
python -m lab_sidecar.cli.app package-verify /tmp/lab-sidecar-package-<task_id>
python -m lab_sidecar.cli.app artifacts <task_id>
```

Manual ingest path when debugging collector or figure regressions:

```bash
python -m lab_sidecar.cli.app ingest examples/csv-comparison
python -m lab_sidecar.cli.app collect <task_id>
python -m lab_sidecar.cli.app figures <task_id>
python -m lab_sidecar.cli.app report <task_id>
python -m lab_sidecar.cli.app slides <task_id>
python -m lab_sidecar.cli.app validate <task_id>
```

## Optional MCP Checks

Run these only when MCP behavior, MCP packaging, or an explicit release gate is
in scope:

```bash
python -m pip install -e ".[dev,mcp]"
python -m pytest tests/test_mcp_tools.py tests/test_v2_host_integration.py -q
python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-mcp-stdio-smoke
```

## Safety And Privacy Gate

- Verify docs distinguish CLI `run` from MCP-facing `run_experiment` safety behavior.
- Verify no docs claim OS sandboxing, malware detection, shell interception, container isolation, or multi-user policy.
- Inspect generated logs and summaries for accidental secrets before publishing screenshots or examples.
- Verify host-facing responses remain bounded by default and do not include full stdout, stderr, metrics rows, report bodies, PPTX contents, or arbitrary artifact bodies.
- Record any security-relevant change in `CHANGELOG.md` and release notes.

## Packaging Gate

- Build the distribution in a clean checkout.
- Inspect package contents for missing docs, scripts, or accidental local files.
- Verify the wheel smoke passed from an isolated venv:

```bash
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"
```

- Verify the pre-release metadata and dist artifact gate:

```bash
python scripts/release_check.py --version <version>
python scripts/release_check.py --version <version> --tag v<version> --require-clean-git
```

- Verify the exact wheel artifact users will install:

```bash
python scripts/release_asset_smoke.py \
  --wheel dist/lab_sidecar-<version>-py3-none-any.whl \
  --version <version> \
  --workspace /tmp/lab-sidecar-release-asset-smoke \
  --repo "$(pwd)"
```

- Verify the console script works after install:

```bash
labsidecar --help
labsidecar validate --help
labsidecar package-verify --help
```

- Verify the module entrypoint works:

```bash
python -m lab_sidecar.cli.app --help
```

- Confirm packages include `artifact-index.json` and `artifact-index.sha256`,
  and that `package-verify` passes.

## Release Notes

Release notes should include:

- Version and date.
- Supported install command.
- GitHub release wheel/sdist install verification path.
- Main workflow summary.
- Validation commands and results.
- Known limitations.
- Security model notes.
- Breaking changes, if any.
- Upgrade notes, if any.

The current release hardening acceptance record is
[v0.1.6-first-user-onboarding-acceptance.md](v0.1.6-first-user-onboarding-acceptance.md)
for the v0.1.6 onboarding line. It records the real published v0.1.5 GitHub
release wheel smoke separately from local v0.1.6 build and wheel smoke
validation. The v0.1.5 install-trust record remains in
[v0.1.5-install-release-trust-acceptance.md](v0.1.5-install-release-trust-acceptance.md).
Older release hardening evidence remains in
[release-hardening-acceptance.md](release-hardening-acceptance.md).

## Post-Release

- Tag the release only after checks pass.
- Archive the exact validation commands and results in docs or the release description.
- Open follow-up issues for deferred work instead of broadening the release scope at the last minute.
