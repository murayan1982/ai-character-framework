"""Lazy voice-input provider adapter protocol and fake adapter.

This module is provider-safe. It does not import STT provider SDKs, read API
keys, open microphones, read audio, upload audio, or execute real STT.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from .voice_input import VoiceInputRequest, VoiceInputResult
from .voice_input_audio import VoiceInputAudioSource


_SECRET_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


def _redact_mapping(values: Mapping[str, Any] | None) -> dict[str, Any]:
    if not values:
        return {}
    redacted: dict[str, Any] = {}
    for key, value in values.items():
        lowered = str(key).lower()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            redacted[str(key)] = "<redacted>"
        else:
            redacted[str(key)] = value
    return redacted


@dataclass(frozen=True)
class VoiceInputProviderAdapterInfo:
    """Provider-neutral adapter preflight result.

    `real_provider` tells host apps whether this adapter represents a real STT
    provider. The fake adapter must keep this false.
    """

    adapter_name: str
    provider: str
    available: bool
    real_provider: bool = False
    provider_execution_required: bool = False
    safe_message: str = ""
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_metadata", _redact_mapping(self.public_metadata))


@runtime_checkable
class VoiceInputProviderAdapter(Protocol):
    """Lazy provider adapter protocol for voice input.

    Implementations must remain lazy. Importing `framework` must not import
    concrete provider SDKs.
    """

    @property
    def adapter_name(self) -> str:
        ...

    def preflight(self) -> VoiceInputProviderAdapterInfo:
        ...

    def transcribe(
        self,
        *,
        audio_source: VoiceInputAudioSource,
        request: VoiceInputRequest | None = None,
    ) -> VoiceInputResult:
        ...


def _completed_result(
    *,
    text: str,
    language: str | None,
    confidence: float | None,
    duration_ms: int | None,
    public_metadata: Mapping[str, Any],
) -> VoiceInputResult:
    completed = getattr(VoiceInputResult, "completed", None)
    if callable(completed):
        attempts = (
            {
                "text": text,
                "language": language,
                "confidence": confidence,
                "duration_ms": duration_ms,
                "public_metadata": public_metadata,
            },
            {
                "text": text,
                "language": language,
                "confidence": confidence,
                "duration_ms": duration_ms,
            },
            {
                "text": text,
                "language": language,
            },
            {
                "text": text,
            },
        )
        for kwargs in attempts:
            try:
                return completed(**kwargs)
            except TypeError:
                continue
    return VoiceInputResult(text=text, language=language, confidence=confidence, duration_ms=duration_ms)


def _unavailable_result(
    *,
    safe_message: str,
    language: str | None,
    public_metadata: Mapping[str, Any],
) -> VoiceInputResult:
    unavailable = getattr(VoiceInputResult, "unavailable", None)
    if callable(unavailable):
        attempts = (
            {"safe_message": safe_message, "language": language, "public_metadata": public_metadata},
            {"safe_message": safe_message, "language": language},
            {"safe_message": safe_message},
        )
        for kwargs in attempts:
            try:
                return unavailable(**kwargs)
            except TypeError:
                continue
    try:
        return VoiceInputResult(text="", language=language, safe_message=safe_message, public_metadata=public_metadata)
    except TypeError:
        try:
            return VoiceInputResult(text="", language=language, safe_message=safe_message)
        except TypeError:
            return VoiceInputResult(text="", language=language)


@dataclass(frozen=True)
class FakeVoiceInputProviderAdapter:
    """Mock-safe fake adapter for host-app and framework contract tests."""

    transcript: str = "fake transcript"
    language: str | None = None
    confidence: float | None = 1.0
    available: bool = True
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def adapter_name(self) -> str:
        return "fake"

    def preflight(self) -> VoiceInputProviderAdapterInfo:
        return VoiceInputProviderAdapterInfo(
            adapter_name=self.adapter_name,
            provider="fake",
            available=self.available,
            real_provider=False,
            provider_execution_required=False,
            safe_message="Fake STT adapter is available for mock-safe contract tests.",
            public_metadata=self.public_metadata,
        )

    def transcribe(
        self,
        *,
        audio_source: VoiceInputAudioSource,
        request: VoiceInputRequest | None = None,
    ) -> VoiceInputResult:
        # The fake adapter intentionally does not dereference `audio_source`.
        # It only uses public metadata to shape a deterministic typed result.
        language = self.language or getattr(request, "language", None) or audio_source.language
        duration_ms = audio_source.ref.audio_format.duration_ms
        return _completed_result(
            text=self.transcript,
            language=language,
            confidence=self.confidence,
            duration_ms=duration_ms,
            public_metadata={
                "adapter": self.adapter_name,
                "source_kind": audio_source.source_kind.value,
                "audio_id": audio_source.audio_id,
                "provider_execution_executed": False,
                "audio_read": False,
                "microphone_accessed": False,
            },
        )


@dataclass(frozen=True)
class GuardedRealVoiceInputProviderAdapter:
    """Guarded real-provider adapter boundary.

    This class represents the first real-provider adapter boundary without
    executing a provider. It is intentionally guarded by explicit opt-in flags
    and credential-presence metadata.
    """

    provider: str
    allow_provider_execution: bool = False
    credentials_available: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def adapter_name(self) -> str:
        return f"guarded_{self.provider}"

    def preflight(self) -> VoiceInputProviderAdapterInfo:
        if not self.allow_provider_execution:
            return VoiceInputProviderAdapterInfo(
                adapter_name=self.adapter_name,
                provider=self.provider,
                available=False,
                real_provider=True,
                provider_execution_required=True,
                safe_message="Provider execution is not allowed. Set an explicit host-controlled opt-in before real STT.",
                public_metadata={
                    **_redact_mapping(self.public_metadata),
                    "guard": "provider_execution_not_allowed",
                    "provider_execution_executed": False,
                },
            )

        if not self.credentials_available:
            return VoiceInputProviderAdapterInfo(
                adapter_name=self.adapter_name,
                provider=self.provider,
                available=False,
                real_provider=True,
                provider_execution_required=True,
                safe_message="Provider credentials are not available to the guarded adapter.",
                public_metadata={
                    **_redact_mapping(self.public_metadata),
                    "guard": "missing_credentials",
                    "provider_execution_executed": False,
                },
            )

        return VoiceInputProviderAdapterInfo(
            adapter_name=self.adapter_name,
            provider=self.provider,
            available=False,
            real_provider=True,
            provider_execution_required=True,
            safe_message="Guard passed, but real STT execution is not implemented in this checkpoint.",
            public_metadata={
                **_redact_mapping(self.public_metadata),
                "guard": "real_stt_not_implemented",
                "provider_execution_executed": False,
            },
        )

    def transcribe(
        self,
        *,
        audio_source: VoiceInputAudioSource,
        request: VoiceInputRequest | None = None,
    ) -> VoiceInputResult:
        info = self.preflight()
        return _unavailable_result(
            safe_message=info.safe_message,
            language=getattr(request, "language", None) or audio_source.language,
            public_metadata={
                "adapter": self.adapter_name,
                "provider": self.provider,
                "real_provider": True,
                "available": info.available,
                "provider_execution_required": info.provider_execution_required,
                "provider_execution_executed": False,
                "audio_read": False,
                "microphone_accessed": False,
                **dict(info.public_metadata),
            },
        )
