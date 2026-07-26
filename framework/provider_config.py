"""FW-owned provider environment resolution for host-app integration.

This module is intentionally lightweight and mock-safe. It centralizes provider
credential alias handling without importing provider SDKs, creating provider
clients, validating API keys, or exposing secret values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence


ProviderConfigState = Literal[
    "configured",
    "unavailable",
    "blocked",
    "unsupported",
]


@dataclass(frozen=True, slots=True)
class ProviderEnvironmentStatus:
    """Provider-neutral public-safe status for one provider configuration area."""

    area: str
    status: ProviderConfigState
    configured: bool
    provider_selected: bool
    reason_code: str
    safe_message: str
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        """Return a secret-free provider-neutral dictionary."""

        return {
            "area": self.area,
            "status": self.status,
            "configured": self.configured,
            "provider_selected": self.provider_selected,
            "reason_code": self.reason_code,
            "safe_message": self.safe_message,
            "public_metadata": dict(self.public_metadata),
        }


@dataclass(frozen=True, slots=True)
class FrameworkProviderEnvironmentSnapshot:
    """Mock-safe snapshot of FW-owned provider environment resolution."""

    schema_version: str
    text_chat: ProviderEnvironmentStatus
    voice_output: ProviderEnvironmentStatus
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        """Return a secret-free provider-neutral dictionary."""

        return {
            "schema_version": self.schema_version,
            "text_chat": self.text_chat.to_public_dict(),
            "voice_output": self.voice_output.to_public_dict(),
            "public_metadata": dict(self.public_metadata),
        }


_TEXT_PROVIDER_ENV_ALIASES = (
    "FRAMEWORK_TEXT_PROVIDER",
    "AI_CHARACTER_TEXT_PROVIDER",
    "LLM_PROVIDER",
)

_VOICE_OUTPUT_PROVIDER_ENV_ALIASES = (
    "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
    "FRAMEWORK_TTS_PROVIDER",
)

# Provider-specific env names stay inside FW. Host apps should not bridge these
# aliases into each other. This module resolves them without mutating os.environ.
_PROVIDER_CREDENTIAL_ALIASES: dict[str, tuple[str, ...]] = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "google_generative_ai": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "xai": ("XAI_API_KEY",),
    "grok": ("XAI_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "elevenlabs": ("ELEVENLABS_API_KEY",),
}


def get_provider_environment_snapshot(
    *,
    text_provider: str | None = None,
    voice_output_provider: str | None = None,
    real_tts_enabled: bool | None = None,
) -> FrameworkProviderEnvironmentSnapshot:
    """Return FW-owned provider environment status without exposing secrets.

    The function is safe to call from host apps and smoke tests. It checks
    whether a provider appears configured from FW-owned environment conventions,
    including compatibility aliases such as GEMINI_API_KEY / GOOGLE_API_KEY.

    It never copies alias values into other environment variables.
    """

    resolved_text_provider = _first_value((text_provider,), _TEXT_PROVIDER_ENV_ALIASES)
    resolved_voice_provider = _first_value((voice_output_provider,), _VOICE_OUTPUT_PROVIDER_ENV_ALIASES)
    tts_enabled = _env_flag("FRAMEWORK_VOICE_OUTPUT_REAL_TTS") if real_tts_enabled is None else bool(real_tts_enabled)

    return FrameworkProviderEnvironmentSnapshot(
        schema_version="v5.1.provider_config",
        text_chat=_provider_status(
            area="text_chat",
            provider=resolved_text_provider,
            disabled=False,
            disabled_reason="provider_not_selected",
        ),
        voice_output=_provider_status(
            area="voice_output",
            provider=resolved_voice_provider,
            disabled=not tts_enabled,
            disabled_reason="real_tts_disabled",
        ),
        public_metadata={
            "boundary": "provider_config",
            "provider_config_owned_by_fw": "true",
            "secret_values_exposed": "false",
            "environment_mutated": "false",
        },
    )


def _provider_status(
    *,
    area: str,
    provider: str | None,
    disabled: bool,
    disabled_reason: str,
) -> ProviderEnvironmentStatus:
    if disabled:
        return ProviderEnvironmentStatus(
            area=area,
            status="unavailable",
            configured=False,
            provider_selected=bool(provider),
            reason_code=disabled_reason,
            safe_message="Provider execution is disabled for this capability.",
            public_metadata=_metadata(area=area, provider=provider, alias_registered=True, alias_matched=False),
        )

    normalized = _normalize_provider(provider)
    if not normalized:
        return ProviderEnvironmentStatus(
            area=area,
            status="unavailable",
            configured=False,
            provider_selected=False,
            reason_code="provider_not_selected",
            safe_message="No provider was selected for this capability.",
            public_metadata=_metadata(area=area, provider=None, alias_registered=False, alias_matched=False),
        )

    aliases = _PROVIDER_CREDENTIAL_ALIASES.get(normalized)
    if aliases is None:
        return ProviderEnvironmentStatus(
            area=area,
            status="unsupported",
            configured=False,
            provider_selected=True,
            reason_code="provider_alias_not_registered",
            safe_message="The selected provider does not have a registered FW environment alias rule.",
            public_metadata=_metadata(area=area, provider=normalized, alias_registered=False, alias_matched=False),
        )

    alias_matched = _any_env_value(aliases)
    if not alias_matched:
        return ProviderEnvironmentStatus(
            area=area,
            status="unavailable",
            configured=False,
            provider_selected=True,
            reason_code="credential_missing",
            safe_message="The selected provider is missing FW-owned credential configuration.",
            public_metadata=_metadata(area=area, provider=normalized, alias_registered=True, alias_matched=False),
        )

    return ProviderEnvironmentStatus(
        area=area,
        status="configured",
        configured=True,
        provider_selected=True,
        reason_code="provider_environment_configured",
        safe_message="Provider environment configuration is present according to FW-owned alias rules.",
        public_metadata=_metadata(area=area, provider=normalized, alias_registered=True, alias_matched=True),
    )


def _metadata(*, area: str, provider: str | None, alias_registered: bool, alias_matched: bool) -> dict[str, str]:
    return {
        "area": area,
        "provider_selected": str(bool(provider)).lower(),
        "provider_family": "selected" if provider else "none",
        "provider_details_exposed": "false",
        "credential_alias_registered": str(alias_registered).lower(),
        "credential_alias_matched": str(alias_matched).lower(),
        "secret_value_exposed": "false",
    }


def _normalize_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    normalized = provider.strip().lower().replace("-", "_")
    return normalized or None


def _first_value(explicit_values: Sequence[str | None], env_names: Sequence[str]) -> str | None:
    for value in explicit_values:
        if value and value.strip():
            return value.strip()
    for name in env_names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _any_env_value(names: Sequence[str]) -> bool:
    return any(bool(os.environ.get(name, "").strip()) for name in names)


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
