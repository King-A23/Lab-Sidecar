# Clean Release Verification v0.1.0

Date: 2026-06-24

## Release Judgment

Ready for maintainer tag review.

This record verifies the committed state after a clean-room release check. The
verification pass found one release reproducibility blocker first: `python -m
build` was not available after `python -m pip install -e ".[dev]"`. The minimal
fix was committed as `b66e9d8 build: include package builder in dev extras`, and
the full clean verification matrix was rerun from that committed HEAD.

No push, tag, PyPI publish, or GitHub release was performed.

## Git State

- Branch: `main`
- Clean verification HEAD: `b66e9d8d6c2402b8f9d2e9196b9db04ce556f8c1`
- Version from `pyproject.toml`: `0.1.0`
- Working tree before clean verification: clean.
- Repository root `.lab-sidecar/`: absent.
- Final release documentation was added after the full clean matrix as a
  docs-only commit. Per the release procedure, the final docs commit requires
  focused docs scope and git hygiene checks rather than a full matrix rerun.
- Target release tags `v0.1.0` and `v0.1.0-rc.1`: not created.
- Existing local alpha tags observed: `v0.1.0-alpha.1`, `v0.1.0-alpha.2`,
  `v0.1.0-alpha.3`.

## Clean Verification Method

- Method: `git worktree add /tmp/lab-sidecar-clean-verify HEAD`
- Clean workspace: `/tmp/lab-sidecar-clean-verify`
- Virtual environment: `/tmp/lab-sidecar-clean-verify/.venv-release-verify`
- Python: `Python 3.12.13`
- Package install path: isolated release verification venv, not system Python.

## Commands And Results

| Command | Result |
| --- | --- |
| `python -m pip install -U pip` | Passed in the clean venv; pip upgraded to `26.1.2`. |
| `python -m pip install -e ".[dev]"` | Passed; installed `lab-sidecar-0.1.0` and dev tooling, including `build-1.5.0`. |
| `python -m pytest -q` | Passed; `252 passed in 69.40s`. |
| `python -m ruff check .` | Passed; all checks passed. |
| `python -m build` | Passed; built `lab_sidecar-0.1.0.tar.gz` and `lab_sidecar-0.1.0-py3-none-any.whl`. |
| `python scripts/cli_full_smoke.py --workspace /tmp/lab-sidecar-clean-cli-smoke --repo "$(pwd)"` | Passed; covered success run, failed-task diagnostic package, ingest, saved comparison, validation, package, `package-comparison`, and `package-verify`. |
| `python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-clean-wheel-smoke --repo "$(pwd)"` | Passed; built a wheel, installed it into an isolated venv, ran installed CLI entry points, validated task and comparison artifacts, and verified both packages. |
| `python -m pip install -e ".[dev,mcp]"` | Passed; optional MCP dependency installed in the clean venv. |
| `python -m pytest tests/test_mcp_tools.py tests/test_v2_host_integration.py -q` | Passed; `32 passed in 2.53s`. |
| `python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-clean-mcp-smoke` | Passed; optional local MCP stdio smoke completed. |
| `python` sdist/wheel inspection script | Passed; expected package contents were present. |
| `rg` release scope scan over `README.md`, `docs`, and `CHANGELOG.md` | Reviewed; matches were boundary, not positive Web/FastAPI/hosted/remote/default-AI/statistical claims. Historical docs retain older evidence paths. |
| `rg` absolute-path and secret-like scan | Reviewed; release-facing docs did not contain new user-home absolute paths or real secrets. Test fixture `SECRET` strings and historical validation paths were expected. |
| `git diff --check` | Passed. |
| `test ! -e .lab-sidecar` | Passed in the clean repo root. |

Post-documentation focused checks on the original repository:

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_docs_scope.py -q` | Passed; `4 passed`. |
| `git diff --check` | Passed. |
| `git status --short` | Clean after committing the verification docs. |
| `test ! -e .lab-sidecar` | Passed in the repository root. |

## Artifacts Inspected

- sdist: `lab_sidecar-0.1.0.tar.gz`
- wheel: `lab_sidecar-0.1.0-py3-none-any.whl`
- sdist contents confirmed: `lab_sidecar`, `tests`, `examples`, `docs`,
  `scripts`, `README.md`, `CHANGELOG.md`, and `pyproject.toml`.
- wheel contents confirmed: `lab_sidecar` and `entry_points.txt`.
- wheel entry points:
  - `lab-sidecar = lab_sidecar.cli.app:main`
  - `labsidecar = lab_sidecar.cli.app:main`
- Installed CLI path observed during wheel smoke:
  `/tmp/lab-sidecar-clean-wheel-smoke/venv/bin/labsidecar`
- `dist/` was generated only inside the clean verification workspace and was not
  committed.

## Scope Confirmation

- No Web UI.
- No FastAPI or HTTP service.
- No hosted service or cloud sync.
- No remote runner.
- No MCP/V2 promotion to the primary product surface.
- No MCP/V2 schema expansion.
- No default AI analysis.
- No statistical significance, p-values, confidence intervals, research
  conclusion, deployment-readiness, or model superiority claims.

## Known Limits

- CSV/JSON metric inputs only.
- No TensorBoard, MLflow tracking-store, or JSONL ingestion.
- CLI `run` is user-explicit local command execution and is not sandboxed.
- Saved comparison is descriptive final-row comparison only.
- MCP/V2 is an optional, experimental, bounded local adapter.
- Offline wheelhouse completeness remains a maintainer responsibility for
  offline release smoke.
- System Python may be externally managed under PEP 668; release checks should
  run in a venv or CI-managed Python.

## Maintainer Next Actions

- Review the local commits and this verification record.
- Choose either `v0.1.0-rc.1` or `v0.1.0` for the next tag.
- Optionally create a GitHub release draft from
  `docs/github-release-draft-v0.1.0.md`.
- Do not publish to PyPI without explicit maintainer approval.

## Prepared Tag Commands

Release verification commands to run immediately before tagging:

```bash
git status --short
python -m pytest -q
python -m ruff check .
python -m build
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-tag-wheel-smoke --repo "$(pwd)"
test ! -e .lab-sidecar
```

Option A, RC tag:

```bash
git tag -a v0.1.0-rc.1 -m "Lab-Sidecar v0.1.0-rc.1"
git push origin v0.1.0-rc.1
```

Option B, final alpha tag:

```bash
git tag -a v0.1.0 -m "Lab-Sidecar v0.1.0"
git push origin v0.1.0
```

These tag commands were prepared only; they were not executed.
