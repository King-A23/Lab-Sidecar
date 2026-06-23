# Security Policy

## Supported Versions

Lab-Sidecar has not published a stable release line yet. During public alpha, security fixes are expected to target the latest development branch and the next alpha release notes.

| Version | Supported |
| --- | --- |
| 0.1.x public alpha | Best effort |
| Earlier snapshots | No |

## Reporting a Vulnerability

If GitHub private vulnerability reporting is enabled for
`King-A23/Lab-Sidecar`, please use that channel. If no private channel is
available, open a minimal public issue that describes the affected area without
exploit details, secrets, or sensitive logs, and ask for a private follow-up
path.

Please include:

- Affected version or commit.
- Operating system and Python version.
- Minimal reproduction steps.
- Expected impact.
- Whether local files, command execution, logs, generated artifacts, or MCP-facing tools are involved.

Do not include credentials, private datasets, full `.lab-sidecar/` task directories, or complete stdout/stderr logs unless a maintainer explicitly asks for a redacted sample.

## Security Model

Lab-Sidecar is local-first and file-first. It is designed to create task records and artifacts under `.lab-sidecar/`; it is not a sandbox, container runtime, malware detector, multi-user policy engine, remote runner, cloud sync system, or hosted execution service.

Important boundaries:

- Manual CLI `run` executes the local command the user explicitly provides. Lab-Sidecar records the command, status, logs, and artifacts, but it is not OS-level isolation; that command can read or write whatever the user's environment permits.
- MCP/V2 and other agent-triggered command paths are higher risk than manual CLI use. They must stay behind bounded delegation, a configured workspace boundary, the conservative command safety gate, and explicit command policies or confirmations supplied by the host.
- The MCP/V2 workspace and command gates are guardrails, not a container, sandbox, malware detector, or proof that a delegated command is safe.
- The experimental MCP adapter returns bounded summaries and artifact paths by default. It should not return complete logs, full metrics rows, report bodies, PPTX contents, worker prompt/response bodies, full data files, artifact bytes, or arbitrary artifact bodies unless a future feature explicitly scopes and tests that behavior.
- Generated artifacts and logs may contain local paths, command arguments, environment details, metrics, or snippets of stdout/stderr. Review and redact artifacts before sharing them.
- The human experiment owner remains responsible for interpretation, redaction, acceptance, and final decisions.
- Lab-Sidecar should not modify, delete, move, or repair user source files as part of collection, figure rendering, report generation, or slide generation.

## Maintainer Response

Expected public-alpha response goals:

- Acknowledge valid reports as soon as practical.
- Reproduce and classify impact.
- Patch on the development branch.
- Add or update regression tests when possible.
- Document user-visible safety implications in release notes or the changelog.

## Known Public-Alpha Limits

- GitHub private vulnerability reporting should be enabled before a broader
  release announcement; until then, use a minimal public issue without exploit
  details or sensitive artifacts.
- No OS sandboxing or container isolation is provided.
- No broad security audit has been completed.
- MCP is experimental local integration, not a hardened remote service boundary, hosted service, or general multi-agent framework.
