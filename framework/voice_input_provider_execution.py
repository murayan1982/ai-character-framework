"""Explicit-only real STT provider-execution configuration and status.

This v5.4.0 candidate module is provider-safe and execution-free. It does not
inspect process environment, read credential values, import provider SDKs,
create provider clients, read audio, open microphones, or execute STT.
"""

from __future__ import annotations

from dataclasses import dataclass

from .capabilities import CapabilityStatus


_BASE_PUBLIC_METADATA = {
    "boundary": "voice_input_provider_execution",
    "configuration_source": "explicit_arguments_only",
    "credential_values_read": "false",
    "provider_sdk_imported": "false",
    "provider_client_created": "false",
    "provider_execution_executed": "false",
    "audio_read": "false",
    "microphone_accessed": "false",
}


def _normalize_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    normalized = str(provider).strip().lower()
    return normalized or None


@dataclass(frozen=True, slots=True)
class VoiceInputProviderExecutionConfig:
    """Public-safe summary of explicit real-STT execution intent.

    `credentials_available` is an availability assertion supplied by the host
    or a later credential resolver. No credential name or value is accepted.
    """

    provider: str | None = None
    allow_provider_execution: bool = False
    credentials_available: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider", _normalize_provider(self.provider))
        object.__setattr__(
            self,
            "allow_provider_execution",
            bool(self.allow_provider_execution),
        )
        object.__setattr__(
            self,
            "credentials_available",
            bool(self.credentials_available),
        )

    @property
    def provider_configured(self) -> bool:
        return self.provider is not None

    @property
    def configured(self) -> bool:
        return (
            self.allow_provider_execution
            and self.provider_configured
            and self.credentials_available
        )

    def to_public_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "allow_provider_execution": self.allow_provider_execution,
            "provider_configured": self.provider_configured,
            "credentials_available": self.credentials_available,
            "configured": self.configured,
            "credential_values_read": False,
        }


def resolve_voice_input_provider_execution_config(
    *,
    provider: str | None = None,
    allow_provider_execution: bool = False,
    credentials_available: bool = False,
) -> VoiceInputProviderExecutionConfig:
    """Resolve explicit arguments without consulting environment or secrets."""

    return VoiceInputProviderExecutionConfig(
        provider=provider,
        allow_provider_execution=allow_provider_execution,
        credentials_available=credentials_available,
    )


def get_voice_input_provider_execution_status(
    config: VoiceInputProviderExecutionConfig,
) -> CapabilityStatus:
    """Return an execution-free capability status for one explicit config."""

    if not isinstance(config, VoiceInputProviderExecutionConfig):
        raise TypeError("config must be VoiceInputProviderExecutionConfig")

    executor_available = config.provider == "openai"
    metadata = {
        **_BASE_PUBLIC_METADATA,
        "provider_configured": str(config.provider_configured).lower(),
        "credentials_available": str(config.credentials_available).lower(),
        "provider_execution_allowed": str(
            config.allow_provider_execution
        ).lower(),
        "real_stt_executor_available": str(executor_available).lower(),
        "runtime_probe_performed": "false",
    }

    if not config.allow_provider_execution:
        return CapabilityStatus(
            name="voice_input_provider_execution",
            status="blocked",
            supported=True,
            configured=False,
            available=False,
            blocked=True,
            reason_code="provider_execution_not_allowed",
            safe_message=(
                "Real STT provider execution requires explicit host-controlled "
                "opt-in."
            ),
            public_metadata=metadata,
        )

    if not config.provider_configured:
        return CapabilityStatus(
            name="voice_input_provider_execution",
            status="unavailable",
            supported=True,
            configured=False,
            available=False,
            blocked=False,
            reason_code="provider_not_configured",
            safe_message="Real STT provider is not configured.",
            public_metadata=metadata,
        )

    if not config.credentials_available:
        return CapabilityStatus(
            name="voice_input_provider_execution",
            status="unavailable",
            supported=True,
            configured=False,
            available=False,
            blocked=False,
            reason_code="credentials_unavailable",
            safe_message=(
                "Real STT provider credentials are not reported as available."
            ),
            public_metadata=metadata,
        )

    if executor_available:
        return CapabilityStatus(
            name="voice_input_provider_execution",
            status="configured",
            supported=True,
            configured=True,
            available=False,
            blocked=False,
            reason_code="real_stt_executor_available",
            safe_message=(
                "OpenAI real STT executor is implemented; this execution-free "
                "status does not probe SDK, network, or provider runtime availability."
            ),
            public_metadata=metadata,
        )

    return CapabilityStatus(
        name="voice_input_provider_execution",
        status="configured",
        supported=True,
        configured=True,
        available=False,
        blocked=False,
        reason_code="provider_execution_not_implemented",
        safe_message=(
            "Real STT provider execution is configured but is not implemented "
            "for this provider."
        ),
        public_metadata=metadata,
    )
