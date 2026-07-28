"""OpenAI voice-input adapter/config/client-injection contract.

REQ-2 is provider-safe and execution-free. This module does not import the
OpenAI SDK, inspect environment variables, read credential values, create or
resolve clients, read audio, open microphones, or execute transcription.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from .voice_input import VoiceInputRequest, VoiceInputResult
from .voice_input_audio import (
    VoiceInputAudioEncoding,
    VoiceInputAudioSource,
    VoiceInputAudioSourceKind,
)
from .voice_input_provider_adapter import VoiceInputProviderAdapterInfo
from .voice_input_provider_execution import VoiceInputProviderExecutionConfig


_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


def _public_mapping(values: Mapping[str, Any] | None) -> dict[str, Any]:
    if not values:
        return {}
    public: dict[str, Any] = {}
    for key, value in values.items():
        text_key = str(key)
        lowered = text_key.lower()
        public[text_key] = (
            "<redacted>"
            if any(marker in lowered for marker in _SECRET_MARKERS)
            else value
        )
    return public


@runtime_checkable
class OpenAIVoiceInputTranscriptionsResource(Protocol):
    """Structural contract for `client.audio.transcriptions`."""

    def create(self, **kwargs: Any) -> Any:
        ...


@runtime_checkable
class OpenAIVoiceInputAudioResource(Protocol):
    """Structural contract for `client.audio`."""

    transcriptions: OpenAIVoiceInputTranscriptionsResource


@runtime_checkable
class OpenAIVoiceInputClient(Protocol):
    """Minimum injected client shape reserved for a later execution checkpoint."""

    audio: OpenAIVoiceInputAudioResource


OpenAIVoiceInputClientFactory = Callable[[], OpenAIVoiceInputClient]


class OpenAIVoiceInputPreflightStatus(str, Enum):
    """Typed REQ-2 configuration/source preflight states."""

    PROVIDER_EXECUTION_NOT_ALLOWED = "provider_execution_not_allowed"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    CREDENTIALS_UNAVAILABLE = "credentials_unavailable"
    MODEL_NOT_CONFIGURED = "model_not_configured"
    CLIENT_CONFIGURATION_CONFLICT = "client_configuration_conflict"
    CLIENT_NOT_CONFIGURED = "client_not_configured"
    SOURCE_REQUIRED = "source_required"
    UNSUPPORTED_SOURCE = "unsupported_source"
    UNSUPPORTED_AUDIO_FORMAT = "unsupported_audio_format"
    SOURCE_NOT_BOUNDED = "source_not_bounded"
    SOURCE_DURATION_EXCEEDS_BOUND = "source_duration_exceeds_bound"
    READY_NOT_EXECUTED = "ready_not_executed"


@dataclass(frozen=True, slots=True)
class OpenAIVoiceInputPreflight:
    """Public-safe typed snapshot for the OpenAI adapter contract."""

    status: OpenAIVoiceInputPreflightStatus | str
    configured: bool
    source_supported: bool
    safe_message: str
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.status
            if isinstance(self.status, OpenAIVoiceInputPreflightStatus)
            else OpenAIVoiceInputPreflightStatus(str(self.status))
        )
        object.__setattr__(self, "status", status)
        object.__setattr__(
            self,
            "public_metadata",
            _public_mapping(self.public_metadata),
        )

    @property
    def is_ready(self) -> bool:
        return self.status is OpenAIVoiceInputPreflightStatus.READY_NOT_EXECUTED


@dataclass(frozen=True)
class OpenAIVoiceInputProviderAdapter:
    """Execution-free OpenAI adapter contract for later real STT work.

    A direct client or client factory may be injected, but REQ-2 never resolves
    the factory and never calls the client.
    """

    execution_config: VoiceInputProviderExecutionConfig
    model: str
    client: OpenAIVoiceInputClient | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    client_factory: OpenAIVoiceInputClientFactory | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model", str(self.model).strip())
        object.__setattr__(
            self,
            "public_metadata",
            _public_mapping(self.public_metadata),
        )

    @property
    def adapter_name(self) -> str:
        return "openai"

    def _metadata(
        self,
        *,
        audio_source: VoiceInputAudioSource | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            **dict(self.public_metadata),
            "provider": "openai",
            "configured_provider": self.execution_config.provider or "",
            "model_configured": bool(self.model),
            "client_injected": self.client is not None,
            "client_factory_injected": self.client_factory is not None,
            "client_factory_invoked": False,
            "provider_sdk_imported": False,
            "provider_client_created": False,
            "provider_execution_executed": False,
            "credential_values_read": False,
            "audio_read": False,
            "microphone_accessed": False,
            "source_path_exposed": False,
        }
        if audio_source is not None:
            metadata.update(
                {
                    "source_kind": audio_source.source_kind.value,
                    "audio_encoding": audio_source.ref.audio_format.encoding.value,
                    "max_duration_ms_present": audio_source.max_duration_ms is not None,
                    "declared_duration_ms": audio_source.ref.audio_format.duration_ms,
                }
            )
        return metadata

    def preflight_contract(
        self,
        *,
        audio_source: VoiceInputAudioSource | None = None,
    ) -> OpenAIVoiceInputPreflight:
        """Validate declarations and public source metadata without side effects."""

        metadata = self._metadata(audio_source=audio_source)

        if not self.execution_config.allow_provider_execution:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
                configured=False,
                source_supported=False,
                safe_message=(
                    "OpenAI STT execution requires explicit host-controlled opt-in."
                ),
                public_metadata=metadata,
            )

        if self.execution_config.provider is None:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.PROVIDER_NOT_CONFIGURED,
                configured=False,
                source_supported=False,
                safe_message="OpenAI STT provider is not configured.",
                public_metadata=metadata,
            )

        if self.execution_config.provider != "openai":
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.UNSUPPORTED_PROVIDER,
                configured=False,
                source_supported=False,
                safe_message="The REQ-2 adapter contract supports only provider=openai.",
                public_metadata=metadata,
            )

        if not self.execution_config.credentials_available:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.CREDENTIALS_UNAVAILABLE,
                configured=False,
                source_supported=False,
                safe_message=(
                    "OpenAI credential availability was not asserted by the host."
                ),
                public_metadata=metadata,
            )

        if not self.model:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.MODEL_NOT_CONFIGURED,
                configured=False,
                source_supported=False,
                safe_message="OpenAI transcription model is not configured.",
                public_metadata=metadata,
            )

        if self.client is not None and self.client_factory is not None:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.CLIENT_CONFIGURATION_CONFLICT,
                configured=False,
                source_supported=False,
                safe_message=(
                    "Configure either an injected OpenAI client or client factory, "
                    "not both."
                ),
                public_metadata=metadata,
            )

        if self.client is None and self.client_factory is None:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.CLIENT_NOT_CONFIGURED,
                configured=False,
                source_supported=False,
                safe_message=(
                    "An OpenAI client or client factory must be injected explicitly."
                ),
                public_metadata=metadata,
            )

        if audio_source is None:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.SOURCE_REQUIRED,
                configured=True,
                source_supported=False,
                safe_message=(
                    "A host-owned FILE_PATH WAV source is required for source "
                    "preflight."
                ),
                public_metadata=metadata,
            )

        if audio_source.source_kind is not VoiceInputAudioSourceKind.FILE_PATH:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.UNSUPPORTED_SOURCE,
                configured=True,
                source_supported=False,
                safe_message=(
                    "REQ-2 accepts FILE_PATH source metadata only; opaque IDs and "
                    "URLs remain unsupported."
                ),
                public_metadata=metadata,
            )

        if (
            audio_source.ref.audio_format.encoding
            is not VoiceInputAudioEncoding.WAV
        ):
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.UNSUPPORTED_AUDIO_FORMAT,
                configured=True,
                source_supported=False,
                safe_message="REQ-2 accepts declared WAV source metadata only.",
                public_metadata=metadata,
            )

        if audio_source.max_duration_ms is None:
            return OpenAIVoiceInputPreflight(
                status=OpenAIVoiceInputPreflightStatus.SOURCE_NOT_BOUNDED,
                configured=True,
                source_supported=False,
                safe_message=(
                    "REQ-2 requires an explicit max_duration_ms source bound."
                ),
                public_metadata=metadata,
            )

        declared_duration_ms = audio_source.ref.audio_format.duration_ms
        if (
            declared_duration_ms is not None
            and declared_duration_ms > audio_source.max_duration_ms
        ):
            return OpenAIVoiceInputPreflight(
                status=(
                    OpenAIVoiceInputPreflightStatus
                    .SOURCE_DURATION_EXCEEDS_BOUND
                ),
                configured=True,
                source_supported=False,
                safe_message=(
                    "Declared audio duration exceeds the host-provided bound."
                ),
                public_metadata=metadata,
            )

        return OpenAIVoiceInputPreflight(
            status=OpenAIVoiceInputPreflightStatus.READY_NOT_EXECUTED,
            configured=True,
            source_supported=True,
            safe_message=(
                "OpenAI adapter contract is ready, but provider execution and "
                "audio resolution are deferred to a later checkpoint."
            ),
            public_metadata=metadata,
        )

    def preflight(self) -> VoiceInputProviderAdapterInfo:
        """Return the existing provider-adapter protocol preflight shape."""

        contract = self.preflight_contract()
        return VoiceInputProviderAdapterInfo(
            adapter_name=self.adapter_name,
            provider="openai",
            available=False,
            real_provider=True,
            provider_execution_required=True,
            safe_message=contract.safe_message,
            public_metadata={
                **dict(contract.public_metadata),
                "guard": contract.status.value,
                "contract_configured": contract.configured,
                "source_supported": contract.source_supported,
            },
        )

    def transcribe(
        self,
        *,
        audio_source: VoiceInputAudioSource,
        request: VoiceInputRequest | None = None,
    ) -> VoiceInputResult:
        """Return a typed unavailable result without resolving audio or clients."""

        contract = self.preflight_contract(audio_source=audio_source)
        return VoiceInputResult.unavailable(
            safe_message=contract.safe_message,
            retryable=False,
            public_metadata={
                **dict(contract.public_metadata),
                "adapter": self.adapter_name,
                "guard": contract.status.value,
                "contract_ready": contract.is_ready,
                "request_language_present": bool(
                    getattr(request, "language", None)
                ),
            },
        )
