from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab_sidecar.core.paths import state_dir


SENSITIVE_PATH_ARG_RE = re.compile(
    r"(?:--(?:output|out|path|dir|cwd|workdir|log|save|dest|destination)\s+|[<>]\s*)"
    r"(?P<quote>[\"']?)"
    r"(?P<path>(?:[A-Za-z]:[\\/][^\s\"']+|\\\\[^\s\"']+|/(?![\\/])[^\s\"']+))"
    r"(?P=quote)",
    re.IGNORECASE,
)
CONFIRMATION_PATTERNS = [
    "&&",
    "||",
    ";",
    "|",
    ">",
    "<",
    " pip install ",
    " uv pip ",
    " conda install ",
    " git commit",
    " git push",
    " git checkout",
    " git switch",
]
BLOCKED_PATTERNS = [
    r"\brm\s+-rf\b",
    r"\bremove-item\b",
    r"\brmdir\b",
    r"\brd\s+/",
    r"\bdel\s+",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
    r"\bdiskpart\b",
    r"\bformat\b",
    r"\breg\s+delete\b",
    r"\bset-executionpolicy\b",
    r"\b-encodedcommand\b",
    r"\bcurl\b.*\bsh\b",
    r"\biwr\b.*\biex\b",
]


@dataclass
class SafetyDecision:
    allowed: bool
    requires_confirmation: bool
    level: str
    reasons: list[str] = field(default_factory=list)
    command_hash: str | None = None
    confirmation_token: str | None = None
    cwd: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_confirmation": self.requires_confirmation,
            "level": self.level,
            "reasons": self.reasons,
            "command_hash": self.command_hash,
            "confirmation_token": self.confirmation_token,
            "cwd": str(self.cwd) if self.cwd else None,
        }


def assess_run_command(
    root: Path,
    command: str,
    cwd: Path | None = None,
    risk_acceptance: str | dict[str, Any] | None = None,
) -> SafetyDecision:
    root = root.resolve()
    resolved_cwd = _resolve_cwd(root, cwd)
    reasons: list[str] = []

    if not _is_within(resolved_cwd, root):
        return SafetyDecision(
            allowed=False,
            requires_confirmation=False,
            level="blocked",
            reasons=["cwd is outside the configured workspace"],
            cwd=resolved_cwd,
        )

    if _is_within(resolved_cwd, state_dir(root).resolve()):
        return SafetyDecision(
            allowed=False,
            requires_confirmation=False,
            level="blocked",
            reasons=["cwd is inside .lab-sidecar"],
            cwd=resolved_cwd,
        )

    external_paths = _workspace_external_paths(root, command)
    if external_paths:
        return SafetyDecision(
            allowed=False,
            requires_confirmation=False,
            level="blocked",
            reasons=[
                "command references path outside the configured workspace: "
                + ", ".join(str(path) for path in external_paths[:3])
            ],
            cwd=resolved_cwd,
        )

    lowered = f" {command.lower()} "
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, lowered):
            reasons.append(f"blocked pattern: {pattern}")
    if reasons:
        return SafetyDecision(
            allowed=False,
            requires_confirmation=False,
            level="blocked",
            reasons=reasons,
            cwd=resolved_cwd,
        )

    for pattern in CONFIRMATION_PATTERNS:
        if pattern in lowered:
            reasons.append(f"requires confirmation: {pattern.strip()}")

    command_hash = _command_hash(command, resolved_cwd)
    token = _confirmation_token(command_hash)
    if reasons and _provided_token(risk_acceptance) != token:
        return SafetyDecision(
            allowed=False,
            requires_confirmation=True,
            level="confirm",
            reasons=reasons,
            command_hash=command_hash,
            confirmation_token=token,
            cwd=resolved_cwd,
        )

    return SafetyDecision(
        allowed=True,
        requires_confirmation=False,
        level="confirmed" if reasons else "low",
        reasons=reasons,
        command_hash=command_hash,
        cwd=resolved_cwd,
    )


def _resolve_cwd(root: Path, cwd: Path | None) -> Path:
    if cwd is None:
        return root
    path = Path(cwd)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _workspace_external_paths(root: Path, command: str) -> list[Path]:
    paths: list[Path] = []
    for match in SENSITIVE_PATH_ARG_RE.finditer(command):
        paths.append(Path(match.group("path")).resolve())

    unique: list[Path] = []
    for path in paths:
        if not _is_within(path, root) and path not in unique:
            unique.append(path)
    return unique


def _command_hash(command: str, cwd: Path) -> str:
    payload = f"{cwd}\n{command}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()[:24]


def _confirmation_token(command_hash: str) -> str:
    return hashlib.sha256(f"lab-sidecar-mcp-v1:{command_hash}".encode("utf-8")).hexdigest()[:16]


def _provided_token(value: str | dict[str, Any] | None) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        token = value.get("token")
        return token if isinstance(token, str) else None
    return None
