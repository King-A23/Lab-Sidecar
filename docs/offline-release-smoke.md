# Offline Release Smoke

Lab-Sidecar itself is CLI-first, file-first, and local-first. Release smoke
builds and installs packages, so the smoke environment still needs build and
runtime dependency wheels from either PyPI or a maintainer-prepared wheelhouse.

## Online Mode

In an environment with PyPI access, install the build frontend and run the
normal release checks:

```bash
python -m pip install build
python -m build
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"
```

`scripts/wheel_smoke.py` builds a wheel from the current repository, installs
that wheel into an isolated venv, copies `examples/` into a disposable
workspace, and runs the installed `labsidecar` console script through the
artifact workflow.

## Offline Mode

Prepare a wheelhouse from an online machine:

```bash
python -m pip download -d /tmp/lab-sidecar-wheelhouse \
  build hatchling \
  matplotlib pandas Pillow pydantic python-pptx pyyaml typer
```

Move the wheelhouse to the offline release-smoke machine, then run:

```bash
PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/lab-sidecar-wheelhouse \
python -m pip install build

PIP_NO_INDEX=1 PIP_FIND_LINKS=/tmp/lab-sidecar-wheelhouse \
python scripts/wheel_smoke.py --workspace /tmp/lab-sidecar-wheel-smoke --repo "$(pwd)"
```

Do not commit the wheelhouse, vendor third-party wheels into the repository, or
relax runtime dependency specs to work around a missing offline dependency.
If a dependency wheel is missing, record the failed command and add the missing
wheel to the external wheelhouse before rerunning the smoke.
