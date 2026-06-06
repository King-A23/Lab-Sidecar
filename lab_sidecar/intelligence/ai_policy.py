from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lab_sidecar.core.paths import config_path


DEFAULT_MAX_INPUT_CHARS = 6000
MIN_MAX_INPUT_CHARS = 1000
MAX_MAX_INPUT_CHARS = 20000


@dataclass(frozen=True)
class AIProviderPolicy:
    provider_name: str | None = None
    model_name: str | None = None
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    redact_secrets: bool = True
    cloud_upload_allowed: bool = False
    audit_prompt_response: bool = False
    fake_provider_enabled: bool = False
    fake_provider_unavailable: bool = False
    real_provider_enabled: bool = False
    api_key_env: str = "LAB_SIDECAR_AI_API_KEY"
    enabled: bool = False
    redact: bool | None = None
    audit_retention: bool | None = None

    def __post_init__(self) -> None:
        if self.redact is not None:
            object.__setattr__(self, "redact_secrets", self.redact)
        if self.audit_retention is not None:
            object.__setattr__(self, "audit_prompt_response", self.audit_retention)
        if self.enabled and self.provider_name == "fake":
            object.__setattr__(self, "fake_provider_enabled", True)
        if self.enabled and self.provider_name not in {None, "fake"}:
            object.__setattr__(self, "real_provider_enabled", True)

    @property
    def audit_enabled(self) -> bool:
        return self.audit_prompt_response


@dataclass(frozen=True)
class ProviderAvailability:
    available: bool
    reason: str
    smoke_skip_reason: str | None = None


def load_ai_provider_policy(root: Path) -> AIProviderPolicy:
    data = _load_workspace_config(root)
    raw = data.get("ai_provider") or data.get("intelligence", {}).get("ai_provider") or {}
    if not isinstance(raw, dict):
        raw = {}

    provider_name = _optional_str(raw.get("provider") or raw.get("provider_name"))
    model_name = _optional_str(raw.get("model") or raw.get("model_name"))
    max_input_chars = _bounded_int(
        raw.get("max_input_chars") or raw.get("max_input_budget"),
        DEFAULT_MAX_INPUT_CHARS,
        MIN_MAX_INPUT_CHARS,
        MAX_MAX_INPUT_CHARS,
    )
    audit = raw.get("audit") if isinstance(raw.get("audit"), dict) else {}
    redaction = raw.get("redaction") if isinstance(raw.get("redaction"), dict) else {}

    return AIProviderPolicy(
        provider_name=provider_name,
        model_name=model_name,
        max_input_chars=max_input_chars,
        redact_secrets=_bool_value(redaction.get("enabled", raw.get("redact_secrets")), True),
        cloud_upload_allowed=_bool_value(raw.get("cloud_upload_allowed"), False),
        audit_prompt_response=_bool_value(
            audit.get("prompt_response", raw.get("audit_prompt_response", raw.get("audit_retention"))),
            False,
        ),
        fake_provider_enabled=provider_name == "fake" and _bool_value(raw.get("enabled"), False),
        fake_provider_unavailable=_bool_value(raw.get("fake_unavailable"), False),
        real_provider_enabled=provider_name not in {None, "fake"} and _bool_value(raw.get("enabled"), False),
        api_key_env=_optional_str(raw.get("api_key_env") or raw.get("key_env")) or _default_key_env(provider_name),
    )


def provider_availability(policy: AIProviderPolicy) -> ProviderAvailability:
    if policy.fake_provider_enabled:
        if policy.fake_provider_unavailable:
            return ProviderAvailability(False, "fake provider configured unavailable")
        return ProviderAvailability(True, "fake provider enabled")

    if not policy.real_provider_enabled:
        return ProviderAvailability(
            False,
            "no explicit workspace AI provider configuration",
            "skipped: workspace config does not explicitly enable a real provider",
        )
    if not policy.cloud_upload_allowed:
        return ProviderAvailability(
            False,
            "cloud upload disabled by workspace policy",
            "skipped: workspace config does not allow cloud upload",
        )
    if not policy.provider_name:
        return ProviderAvailability(False, "provider name missing", "skipped: provider name missing")
    if not policy.model_name:
        return ProviderAvailability(False, "model name missing", "skipped: model name missing")
    if not os.environ.get(policy.api_key_env):
        return ProviderAvailability(
            False,
            f"missing provider key in {policy.api_key_env}",
            f"skipped: {policy.api_key_env} is not set",
        )
    return ProviderAvailability(True, "real provider explicitly enabled")


def real_provider_smoke_skip_reason(root: Path) -> str | None:
    policy = load_ai_provider_policy(root)
    availability = provider_availability(policy)
    if policy.real_provider_enabled and availability.available:
        return None
    return availability.smoke_skip_reason or availability.reason


def _load_workspace_config(root: Path) -> dict[str, Any]:
    path = config_path(root)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _default_key_env(provider_name: str | None) -> str:
    if provider_name == "openai":
        return "OPENAI_API_KEY"
    if provider_name:
        return f"{provider_name.upper()}_API_KEY"
    return "LAB_SIDECAR_AI_API_KEY"
