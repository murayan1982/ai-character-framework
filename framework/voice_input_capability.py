"""Public voice-input / STT capability and provider preflight contracts.

This module is intentionally provider-neutral and mock-safe. It checks only
public configuration intent and credential presence without importing STT
provider SDKs or executing real provider calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping
import os

from .voice_input import _public_mapping


_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_SUPPORTED_PROVIDERS = {"mock", "google", "openai", "whisper"}


class VoiceInputProviderStatus(str, Enum):
    """Provider-neutral voice-input provider preflight status."""

    DISABLED = "disabled"
    MISSING_CREDENTIALS = "missing_credentials"
    PROVIDER_EXECUTION_NOT_ALLOWED = "provider_execution_not_allowed"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    REAL_STT_NOT_IMPLEMENTED = "real_stt_not_implemented"
    REAL_STT_EXECUTOR_AVAILABLE = "real_stt_executor_available"


@dataclass(frozen=True)
class VoiceInputProviderConfig:
    """Public-safe voice-input provider configuration summary."""

    provider: str | None = None
    real_stt_enabled: bool = False
    provider_execution_allowed: bool = False
    credentials_available: bool = False
    credential_source: str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


@dataclass(frozen=True)
class VoiceInputCapabilities:
    """Public-safe voice-input capability snapshot."""

    supports_voice_input_session: bool = True
    supports_text_fallback: bool = True
    supports_real_stt: bool = False
    real_executor_available: bool = False
    runtime_probe_performed: bool = False
    provider_status: VoiceInputProviderStatus = VoiceInputProviderStatus.DISABLED
    provider: str | None = None
    safe_message: str = "Real voice input is disabled."
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.provider_status
            if isinstance(self.provider_status, VoiceInputProviderStatus)
            else VoiceInputProviderStatus(str(self.provider_status))
        )
        object.__setattr__(self, "provider_status", status)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE_VALUES


def _normalized_provider(provider: str | None, env: Mapping[str, str]) -> str | None:
    raw = provider or env.get("FRAMEWORK_VOICE_INPUT_PROVIDER") or env.get("FRAMEWORK_STT_PROVIDER")
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    return normalized or None


def _credential_keys(provider: str | None) -> tuple[str, ...]:
    if provider == "google":
        return ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_API_KEY")
    if provider == "openai":
        return ("OPENAI_API_KEY",)
    if provider == "whisper":
        return ()
    if provider == "mock":
        return ()
    return ()


def _credential_source(provider: str | None, env: Mapping[str, str]) -> tuple[bool, str | None]:
    keys = _credential_keys(provider)
    if not keys:
        return True, None
    for key in keys:
        if env.get(key):
            return True, key
    return False, None


def resolve_voice_input_provider_config(
    *,
    provider: str | None = None,
    real_stt_enabled: bool | None = None,
    allow_provider_execution: bool | None = None,
    credential_env: Mapping[str, str] | None = None,
    public_metadata: Mapping[str, Any] | None = None,
) -> VoiceInputProviderConfig:
    """Resolve public-safe voice-input provider configuration.

    `credential_env` exists for tests and host-app preflight. Passing it avoids
    mutating process environment and keeps this function mock-safe.
    """

    env = credential_env if credential_env is not None else os.environ
    resolved_provider = _normalized_provider(provider, env)

    resolved_real_stt_enabled = (
        _truthy(real_stt_enabled)
        if real_stt_enabled is not None
        else _truthy(env.get("FRAMEWORK_VOICE_INPUT_REAL_STT") or env.get("FRAMEWORK_STT_REAL_STT"))
    )
    resolved_provider_execution_allowed = (
        _truthy(allow_provider_execution)
        if allow_provider_execution is not None
        else _truthy(env.get("FRAMEWORK_VOICE_INPUT_ALLOW_PROVIDER_EXECUTION"))
    )

    credentials_available, credential_source = _credential_source(resolved_provider, env)

    return VoiceInputProviderConfig(
        provider=resolved_provider,
        real_stt_enabled=resolved_real_stt_enabled,
        provider_execution_allowed=resolved_provider_execution_allowed,
        credentials_available=credentials_available,
        credential_source=credential_source,
        public_metadata={
            "boundary": "voice_input",
            **dict(public_metadata or {}),
        },
    )


def get_voice_input_capabilities(
    *,
    provider: str | None = None,
    real_stt_enabled: bool | None = None,
    allow_provider_execution: bool | None = None,
    credential_env: Mapping[str, str] | None = None,
    public_metadata: Mapping[str, Any] | None = None,
) -> VoiceInputCapabilities:
    """Return a provider-neutral voice-input capability preflight snapshot."""

    config = resolve_voice_input_provider_config(
        provider=provider,
        real_stt_enabled=real_stt_enabled,
        allow_provider_execution=allow_provider_execution,
        credential_env=credential_env,
        public_metadata=public_metadata,
    )

    if not config.real_stt_enabled:
        return VoiceInputCapabilities(
            provider_status=VoiceInputProviderStatus.DISABLED,
            provider=config.provider,
            safe_message="Real voice input is disabled.",
            retryable=False,
            public_metadata={
                "boundary": "voice_input",
                "reason": "real_stt_disabled",
            },
        )

    if not config.provider:
        return VoiceInputCapabilities(
            provider_status=VoiceInputProviderStatus.DISABLED,
            provider=None,
            safe_message="Real voice input provider is not configured.",
            retryable=False,
            public_metadata={
                "boundary": "voice_input",
                "reason": "provider_not_configured",
            },
        )

    if config.provider not in _SUPPORTED_PROVIDERS:
        return VoiceInputCapabilities(
            provider_status=VoiceInputProviderStatus.UNSUPPORTED_PROVIDER,
            provider=config.provider,
            safe_message="Configured voice input provider is not supported by the public preflight contract.",
            retryable=False,
            public_metadata={
                "boundary": "voice_input",
                "reason": "unsupported_provider",
            },
        )

    if not config.credentials_available:
        return VoiceInputCapabilities(
            provider_status=VoiceInputProviderStatus.MISSING_CREDENTIALS,
            provider=config.provider,
            safe_message="Voice input provider credentials are missing.",
            retryable=True,
            public_metadata={
                "boundary": "voice_input",
                "reason": "missing_credentials",
            },
        )

    if not config.provider_execution_allowed:
        return VoiceInputCapabilities(
            provider_status=VoiceInputProviderStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
            provider=config.provider,
            safe_message="Voice input provider execution is not allowed by public guard.",
            retryable=False,
            public_metadata={
                "boundary": "voice_input",
                "reason": "provider_execution_not_allowed",
            },
        )

    if config.provider == "openai":
        return VoiceInputCapabilities(
            supports_real_stt=True,
            real_executor_available=True,
            runtime_probe_performed=False,
            provider_status=VoiceInputProviderStatus.REAL_STT_EXECUTOR_AVAILABLE,
            provider=config.provider,
            safe_message=(
                "OpenAI real STT executor is implemented; capability inspection "
                "does not probe SDK, network, or provider runtime availability."
            ),
            retryable=False,
            public_metadata={
                "boundary": "voice_input",
                "reason": "real_stt_executor_available",
                "real_stt_executor_available": True,
                "runtime_probe_performed": False,
                "provider_execution_executed": False,
            },
        )

    return VoiceInputCapabilities(
        provider_status=VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED,
        provider=config.provider,
        safe_message="Real voice input provider execution is not implemented for this provider.",
        retryable=False,
        public_metadata={
            "boundary": "voice_input",
            "reason": "real_stt_not_implemented",
            "real_stt_executor_available": False,
            "runtime_probe_performed": False,
            "provider_execution_executed": False,
        },
    )
