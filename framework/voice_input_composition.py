"""Internal provider-neutral voice-input default composition for FW-RT6-7a.

This module is intentionally not root-public. Importing it does not import an
STT provider SDK or provider-specific Framework adapter/runtime module. The
provider-specific OpenAI chain is imported only after all explicit real-runtime
gates pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .voice_input import VoiceInputRequest, VoiceInputResult
from .voice_input_audio import VoiceInputAudioSource
from .voice_input_provider_adapter import FakeVoiceInputProviderAdapter

_DEFAULT_OPENAI_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
_DEFAULT_MAX_AUDIO_BYTES = 25 * 1024 * 1024
_DEFAULT_PROVIDER_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class VoiceInputCompositionConfig:
    """Internal provider-neutral composition inputs owned by VoiceInputSession."""

    provider: str | None
    real_stt_requested: bool
    allow_provider_execution: bool
    private_credential: str | None = field(repr=False, compare=False)
    allow_provider_sdk_import: bool = False
    allow_provider_client_creation: bool = False
    allow_real_provider_execution: bool = False
    max_audio_bytes: int = _DEFAULT_MAX_AUDIO_BYTES
    provider_timeout_seconds: float = _DEFAULT_PROVIDER_TIMEOUT_SECONDS
    provider_max_retries: int = 0

    def __post_init__(self) -> None:
        provider = (
            str(self.provider).strip().lower()
            if self.provider is not None
            else None
        )
        object.__setattr__(self, "provider", provider or None)

        if self.private_credential is not None:
            if not isinstance(self.private_credential, str):
                raise TypeError("private_credential must be a string or None")
            credential = self.private_credential.strip()
            if not credential:
                raise ValueError("private_credential must be non-empty when provided")
            object.__setattr__(self, "private_credential", credential)

        if self.max_audio_bytes <= 0:
            raise ValueError("max_audio_bytes must be positive")
        if self.provider_timeout_seconds <= 0:
            raise ValueError("provider_timeout_seconds must be positive")
        if self.provider_max_retries < 0:
            raise ValueError("provider_max_retries must be non-negative")


def credential_presence_env(
    *,
    provider: str | None,
    credential_env: Mapping[str, str] | None,
    private_credential: str | None,
) -> Mapping[str, str] | None:
    """Add presence-only OpenAI credential evidence without exposing its value.

    If no private credential is explicitly supplied, the original mapping (or
    None) is returned unchanged so accepted v5 capability-resolution behavior is
    preserved.
    """

    if private_credential is None:
        return credential_env

    normalized_provider = (
        str(provider).strip().lower()
        if provider is not None
        else None
    )
    if normalized_provider != "openai":
        return credential_env

    values = dict(credential_env or {})
    values["OPENAI_API_KEY"] = "<present>"
    return values


def _unavailable(
    *,
    reason: str,
    safe_message: str,
    provider: str | None,
) -> VoiceInputResult:
    return VoiceInputResult.unavailable(
        safe_message=safe_message,
        retryable=False,
        public_metadata={
            "boundary": "voice_input",
            "provider": provider,
            "reason": reason,
            "provider_execution_executed": False,
            "provider_sdk_imported": False,
            "provider_client_created": False,
            "audio_read": False,
            "microphone_accessed": False,
            "private_auth_value_exposed": False,
            "audio_path_exposed": False,
            "provider_payload_exposed": False,
        },
    )


def transcribe_default(
    *,
    config: VoiceInputCompositionConfig,
    audio_source: VoiceInputAudioSource,
    request: VoiceInputRequest,
    capability_supports_real_stt: bool,
    capability_reason: str,
    capability_safe_message: str,
) -> VoiceInputResult:
    """Select the mock-safe default or guarded real composition path."""

    if not config.real_stt_requested:
        return FakeVoiceInputProviderAdapter().transcribe(
            audio_source=audio_source,
            request=request,
        )

    if not capability_supports_real_stt:
        return _unavailable(
            reason=capability_reason,
            safe_message=capability_safe_message,
            provider=config.provider,
        )

    if config.provider != "openai":
        return _unavailable(
            reason="provider_execution_not_implemented",
            safe_message="Real STT default composition is not implemented for this provider.",
            provider=config.provider,
        )

    if not config.allow_provider_execution:
        return _unavailable(
            reason="provider_execution_not_allowed",
            safe_message="Real STT provider execution requires explicit host-controlled opt-in.",
            provider=config.provider,
        )

    if config.private_credential is None:
        return _unavailable(
            reason="private_credential_required",
            safe_message=(
                "Real OpenAI STT requires an explicitly supplied private credential; "
                "credential_env values are never consumed by runtime composition."
            ),
            provider=config.provider,
        )

    if not config.allow_provider_sdk_import:
        return _unavailable(
            reason="provider_sdk_import_not_allowed",
            safe_message="OpenAI SDK import requires explicit host-controlled opt-in.",
            provider=config.provider,
        )

    if not config.allow_provider_client_creation:
        return _unavailable(
            reason="provider_client_creation_not_allowed",
            safe_message="OpenAI client creation requires explicit host-controlled opt-in.",
            provider=config.provider,
        )

    if not config.allow_real_provider_execution:
        return _unavailable(
            reason="real_provider_execution_not_allowed",
            safe_message="Real OpenAI STT execution requires explicit host-controlled opt-in.",
            provider=config.provider,
        )

    return _execute_openai_real(
        config=config,
        audio_source=audio_source,
        request=request,
    )


def _execute_openai_real(
    *,
    config: VoiceInputCompositionConfig,
    audio_source: VoiceInputAudioSource,
    request: VoiceInputRequest,
) -> VoiceInputResult:
    """Lazy-build the already accepted v5.4 OpenAI real-provider chain."""

    # Provider-specific Framework modules remain lazy until every explicit gate
    # above has passed. These modules themselves do not import the OpenAI SDK;
    # the accepted client factory imports it only when invoked by the executor.
    from .openai_voice_input_provider_adapter import (
        OpenAIVoiceInputProviderAdapter,
    )
    from .openai_voice_input_real_provider import (
        OpenAIVoiceInputPrivateCredential,
        OpenAIVoiceInputRealClientFactory,
        OpenAIVoiceInputRealProviderExecutor,
        OpenAIVoiceInputRealProviderPolicy,
    )
    from .voice_input_provider_execution import (
        resolve_voice_input_provider_execution_config,
    )

    credential = OpenAIVoiceInputPrivateCredential(config.private_credential)
    policy = OpenAIVoiceInputRealProviderPolicy(
        max_audio_bytes=config.max_audio_bytes,
        timeout_seconds=config.provider_timeout_seconds,
        max_retries=config.provider_max_retries,
        allow_provider_sdk_import=config.allow_provider_sdk_import,
        allow_provider_client_creation=config.allow_provider_client_creation,
        allow_real_provider_execution=config.allow_real_provider_execution,
    )
    factory = OpenAIVoiceInputRealClientFactory(
        credential=credential,
        policy=policy,
    )
    adapter = OpenAIVoiceInputProviderAdapter(
        execution_config=resolve_voice_input_provider_execution_config(
            provider="openai",
            allow_provider_execution=config.allow_provider_execution,
            credentials_available=True,
        ),
        model=_DEFAULT_OPENAI_TRANSCRIPTION_MODEL,
        client_factory=factory,
    )
    return OpenAIVoiceInputRealProviderExecutor(adapter=adapter).execute(
        audio_source=audio_source,
        request=request,
    )
