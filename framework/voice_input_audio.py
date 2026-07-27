"""Provider-neutral host-captured audio source contract for voice input.

This module defines public data-only contracts. It does not read audio, open
microphones, import provider SDKs, or execute STT providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


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


class VoiceInputAudioSourceKind(str, Enum):
    """Where the host-captured audio can be resolved by the host app."""

    OPAQUE_ID = "opaque_id"
    FILE_PATH = "file_path"
    URL = "url"


class VoiceInputAudioEncoding(str, Enum):
    """Provider-neutral audio encoding hint."""

    WAV = "wav"
    M4A = "m4a"
    MP3 = "mp3"
    WEBM = "webm"
    OGG = "ogg"
    FLAC = "flac"
    PCM16 = "pcm16"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VoiceInputAudioFormat:
    """Provider-neutral audio format metadata."""

    encoding: VoiceInputAudioEncoding = VoiceInputAudioEncoding.UNKNOWN
    sample_rate_hz: int | None = None
    channel_count: int | None = None
    duration_ms: int | None = None
    mime_type: str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sample_rate_hz is not None and self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive when provided")
        if self.channel_count is not None and self.channel_count <= 0:
            raise ValueError("channel_count must be positive when provided")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative when provided")
        object.__setattr__(self, "public_metadata", _redact_mapping(self.public_metadata))

    @classmethod
    def unknown(cls, **metadata: Any) -> "VoiceInputAudioFormat":
        return cls(public_metadata=metadata)

    @classmethod
    def wav(
        cls,
        *,
        sample_rate_hz: int | None = None,
        channel_count: int | None = None,
        duration_ms: int | None = None,
        **metadata: Any,
    ) -> "VoiceInputAudioFormat":
        return cls(
            encoding=VoiceInputAudioEncoding.WAV,
            sample_rate_hz=sample_rate_hz,
            channel_count=channel_count,
            duration_ms=duration_ms,
            mime_type="audio/wav",
            public_metadata=metadata,
        )


@dataclass(frozen=True)
class VoiceInputAudioRef:
    """Opaque reference to host-captured audio."""

    source_kind: VoiceInputAudioSourceKind
    value: str
    audio_format: VoiceInputAudioFormat = field(default_factory=VoiceInputAudioFormat)
    audio_id: str = field(default_factory=lambda: f"audio_{uuid4().hex}")
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("value must be non-empty")
        object.__setattr__(self, "public_metadata", _redact_mapping(self.public_metadata))

    @classmethod
    def opaque_id(
        cls,
        audio_id: str,
        *,
        audio_format: VoiceInputAudioFormat | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputAudioRef":
        return cls(
            source_kind=VoiceInputAudioSourceKind.OPAQUE_ID,
            value=audio_id,
            audio_id=audio_id,
            audio_format=audio_format or VoiceInputAudioFormat(),
            public_metadata=public_metadata or {},
        )

    @classmethod
    def file_path(
        cls,
        path: str,
        *,
        audio_format: VoiceInputAudioFormat | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputAudioRef":
        return cls(
            source_kind=VoiceInputAudioSourceKind.FILE_PATH,
            value=path,
            audio_format=audio_format or VoiceInputAudioFormat(),
            public_metadata=public_metadata or {},
        )

    @classmethod
    def url(
        cls,
        url: str,
        *,
        audio_format: VoiceInputAudioFormat | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputAudioRef":
        return cls(
            source_kind=VoiceInputAudioSourceKind.URL,
            value=url,
            audio_format=audio_format or VoiceInputAudioFormat(),
            public_metadata=public_metadata or {},
        )

    def with_public_metadata(self, **metadata: Any) -> "VoiceInputAudioRef":
        merged = dict(self.public_metadata)
        merged.update(metadata)
        return replace(self, public_metadata=_redact_mapping(merged))


@dataclass(frozen=True)
class VoiceInputAudioSource:
    """Provider-neutral host-audio handoff source.

    This class describes host-captured audio for public STT requests. It does not
    read referenced audio, validate paths, upload data, access microphones, or
    call providers.
    """

    ref: VoiceInputAudioRef
    language: str | None = None
    max_duration_ms: int | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.max_duration_ms is not None and self.max_duration_ms <= 0:
            raise ValueError("max_duration_ms must be positive when provided")
        object.__setattr__(self, "public_metadata", _redact_mapping(self.public_metadata))

    @classmethod
    def from_opaque_id(
        cls,
        audio_id: str,
        *,
        audio_format: VoiceInputAudioFormat | None = None,
        language: str | None = None,
        max_duration_ms: int | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputAudioSource":
        return cls(
            ref=VoiceInputAudioRef.opaque_id(audio_id, audio_format=audio_format, public_metadata=public_metadata),
            language=language,
            max_duration_ms=max_duration_ms,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def from_file_path(
        cls,
        path: str,
        *,
        audio_format: VoiceInputAudioFormat | None = None,
        language: str | None = None,
        max_duration_ms: int | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputAudioSource":
        return cls(
            ref=VoiceInputAudioRef.file_path(path, audio_format=audio_format, public_metadata=public_metadata),
            language=language,
            max_duration_ms=max_duration_ms,
            public_metadata=public_metadata or {},
        )

    @property
    def source_kind(self) -> VoiceInputAudioSourceKind:
        return self.ref.source_kind

    @property
    def audio_id(self) -> str:
        return self.ref.audio_id
