# Next Stage Product Growth Plan

Date: 2026-06-08

## Objective

Move Lab-Sidecar from "cautious public-alpha release-prepared" to a project
that a stranger can understand, install, try, trust, and plausibly star or use.

This plan is intentionally heavier than a release-readiness pass. It asks a
Codex supervisor agent to improve real usefulness, onboarding, README quality,
demo credibility, CLI ergonomics, tests, and release polish while preserving
the product boundary:

```text
local-first experiment sidecar
  -> run / ingest
  -> collect
  -> figures
  -> report
  -> slides
  -> bounded Codex/MCP delegation
```

The goal is to maximize open-source appeal and actual user value. It must not
claim or guarantee stars, adoption, production hardening, hosted execution, or
features that are not implemented.

## Non-Negotiable Boundaries

- Do not add Web UI, FastAPI, hosted service, remote runner, cloud sync, or a
  generic multi-agent framework.
- Do not make AI analysis, AI report writing, or cloud provider calls a default
  workflow.
- Do not publish to PyPI, push to GitHub, tag a release, or open a pull request
  unless the user explicitly asks.
- Do not commit generated `.lab-sidecar/` task directories, caches, virtualenvs,
  or private local paths.
- Do not overclaim OS sandboxing, malware detection, global shell interception,
  autonomous research conclusions, or guaranteed GitHub stars.
- Keep Codex subagents as supervisor execution coordination. Lab-Sidecar itself
  remains a sidecar tool surface with task-local artifacts and bounded
  responses.

## Definition Of Done

The next-stage pass is complete only when:

- A new user can clone, install, and run a polished demo in 10 minutes on
  macOS/Linux, with Windows guidance included.
- The README is standard, credible, and compelling: clear value proposition,
  quick demo, screenshots or real artifact previews, install, CLI, Codex/MCP,
  limitations, and contribution guidance.
- The product has at least one "wow, this is useful" deterministic demo path
  using committed examples and small committed preview assets.
- CLI output and docs guide the user to the next command and artifact paths
  without requiring them to read internals.
- V2 MCP/Codex integration remains bounded and tested.
- Full tests, targeted tests, MCP stdio smoke, plugin validation, and docs
  whitespace checks pass.
- A final acceptance document records exact commands, task ids, demo artifacts,
  screenshots/assets, known limits, and release recommendation.

## Workstreams

### 1. Baseline And Independent Review

Start by recording:

```bash
git status --short
git diff --stat
git diff --check
.venv/bin/python -m pytest -q
```

Spawn read-only reviewers for:

- README/product appeal and overclaim risk.
- CLI workflow friction and missing ergonomic commands.
- MCP/V2 bounded-response risk.
- Packaging/open-source completeness.
- Demo artifact credibility and asset size risk.

Do not edit until the supervisor has a concise map of current risks.

### 2. Product Usefulness And CLI Ergonomics

Improve the local CLI experience without expanding the product boundary.

Required investigation:

- Inspect `lab_sidecar/cli/app.py`, current command outputs, and tests.
- Run a clean demo workspace and note every confusing step.
- Check whether `list`, `open`, or equivalent task navigation commands exist.

Implementation targets, if absent or weak:

- Add a small `list` command to show recent tasks from file/index state.
- Add a small `open` command that prints the task artifact directory path; an
  optional reveal/open-in-file-manager behavior is allowed only if
  cross-platform and tested.
- Improve command completion messages to include the `task_id`, next likely
  commands, and key artifact paths.
- Add a `doctor` or `check` command only if it remains small and clearly useful
  for verifying Python version, writable workspace, optional MCP dependency,
  and `.lab-sidecar` config.

Testing requirements:

- Add focused CLI tests for every new command or changed output contract.
- Preserve all existing CLI smoke tests.
- Do not make tests depend on OS-specific GUI open behavior.

### 3. Demo That Sells The Product

Create a deterministic, public-facing demo package from real outputs.

Required demo path:

- Use `examples/simple-success` for run -> metrics -> figures -> report ->
  slides.
- Use `examples/csv-comparison` or `examples/project-presentation-pack` for a
  richer multi-file result demo.
- Keep generated task directories out of the repository.

Committed demo assets:

- Add at most 3 lightweight assets under `docs/assets/demo/`.
- Assets must be generated from real Lab-Sidecar example outputs, not stock
  images.
- Prefer one figure PNG, one report excerpt screenshot or rendered Markdown
  preview, and one slide preview image if practical.
- If slide image export is too brittle, commit only figure/report preview
  assets and document the limitation.

Documentation requirements:

- Add or update a demo doc with exact commands, expected files, and artifact
  preview paths.
- The README should show the demo in a visually scannable way without hiding
  known limits.

### 4. README Rewrite For Open-Source Appeal

Rewrite README as the primary public landing page.

Required structure:

- One-sentence value proposition.
- Short "Why this exists" section focused on noisy long experiments and report
  artifact preparation.
- 10-minute quickstart.
- Demo preview using real committed assets.
- CLI command table.
- Codex/MCP integration section explaining bounded context quarantine.
- Artifact layout section.
- Safety and limits section.
- Install and development instructions.
- Links to demo, release notes, contribution guide, security policy, and final
  acceptance record.

Tone requirements:

- Attractive and concrete, not hype-driven.
- Mention students, research beginners, and personal developers as primary
  users.
- Say what the tool does today before discussing future directions.
- Do not promise adoption, stars, production-grade security, remote execution,
  or AI insight.

### 5. Packaging, CI, And Release Polish

Audit packaging as if a stranger will install it.

Targets:

- Ensure `pyproject.toml`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  `SECURITY.md`, and CI agree.
- Confirm package metadata uses `README.md`, MIT license metadata, useful
  classifiers, and correct optional extras.
- Consider adding a minimal build check:

```bash
.venv/bin/python -m pip install build
.venv/bin/python -m build
```

Only add build tooling if it does not create noisy committed artifacts. Do not
publish packages.

### 6. Codex Plugin And MCP Usability

Keep the repo-scoped Codex plugin scaffold useful but modest.

Targets:

- Validate `plugins/lab-sidecar`.
- Ensure the bundled skill explains when to delegate to Lab-Sidecar.
- Ensure MCP docs list both V1 deterministic tools and V2 mirror tools.
- Add an install/use note for the repo marketplace without implying every user
  must install the plugin.

Tests:

- Existing `tests/test_mcp_tools.py` must continue proving bounded V1/V2 MCP
  behavior.
- `scripts/mcp_stdio_smoke.py` must continue listing V1 and V2 tools and
  smoke-checking V2 preview.

### 7. Final Acceptance

Create or update a final next-stage acceptance record, for example:

```text
docs/next-stage-product-growth-acceptance.md
```

It must include:

- changed files
- commands run
- demo workspace paths
- task ids
- committed demo assets
- test results
- README before/after summary
- known limits
- final recommendation: ready to open source, ready after follow-ups, or blocked

## Required Validation Commands

Run these before final handoff:

```bash
git diff --check
rg -n "guaranteed|大量star|production-grade|OS sandbox|malware detection|hosted service|Web UI|FastAPI" README.md docs examples plugins
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_cli_smoke.py tests/test_mcp_tools.py -q
.venv/bin/python -m pytest tests/test_v2_ai_provider.py tests/test_v2_heuristic_worker.py tests/test_v2_host_integration.py tests/test_v2_intelligence_scaffold.py tests/test_v2_worker_invocation.py -q
.venv/bin/python scripts/mcp_stdio_smoke.py --workspace /tmp/lab-sidecar-next-stage-mcp-smoke
.venv/bin/python $CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/lab-sidecar
git status --short
```

If a command is skipped, the acceptance record must explain why.

## Suggested Supervisor Goal

Use the prompt below to start the next agent. The supervisor may spawn subagents
for independent review, docs, CLI, demo assets, MCP, and validation slices.

```text
You are the supervisor agent for the next Lab-Sidecar product-growth pass.
Start in the Lab-Sidecar repository root.

Read docs/next-stage-product-growth-plan.md first and follow it as the source
of truth. Your goal is to make Lab-Sidecar genuinely useful and attractive for
a cautious public open-source alpha: improve real CLI usability, create a
credible deterministic demo with small real artifact preview assets, rewrite
the README into a standard and compelling open-source landing page, preserve
bounded Codex/MCP context quarantine, and finish with complete validation and a
next-stage acceptance record.

Use subagents for independent read-only audits and disjoint implementation
slices where helpful. Do not duplicate work between agents. Preserve concurrent
changes and do not revert user edits.

Hard boundaries:
- Do not add Web UI, FastAPI, hosted service, remote runner, cloud sync, or a
  generic multi-agent framework.
- Do not make AI analysis or cloud provider calls a default workflow.
- Do not publish to PyPI, push, tag, open a PR, or commit unless explicitly
  instructed.
- Do not commit generated .lab-sidecar task directories, caches, virtualenvs,
  or private local paths.
- Do not claim guaranteed stars, production-grade security, OS sandboxing,
  malware detection, or autonomous research conclusions.
- Codex subagents are supervisor execution coordination only; Lab-Sidecar
  remains a local sidecar tool with bounded responses and deterministic
  artifact records.

Required finish:
- README is polished and compelling but truthful.
- Demo docs/assets are generated from real Lab-Sidecar examples.
- Any CLI improvements are tested.
- MCP/V2 bounded-response behavior still passes.
- Run the validation commands listed in docs/next-stage-product-growth-plan.md.
- Write docs/next-stage-product-growth-acceptance.md with exact commands,
  task ids, demo artifacts/assets, test results, known limits, and final
  release recommendation.
```
