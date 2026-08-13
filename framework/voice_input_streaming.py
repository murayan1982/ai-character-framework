"""Provider-neutral public audio-chunk streaming contract models.

FW-RT6-12a Control A defines immutable, data-only vocabulary. Importing this
module does not open a microphone, read audio, import provider SDKs, create a
runtime, perform network work, or attach these contracts to a session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .public_safety import looks_like_private_path, public_mapping
from .voice_input_audio import VoiceInputAudioEncoding, VoiceInputAudioFormat


VOICE_INPUT_STREAMING_API_VERSION = "6.0"


class VoiceInputStreamOperationKind(str, Enum):
    """Kind of one host-to-Framework streaming input operation."""

    AUDIO_CHUNK = "audio_chunk"
    END_OF_INPUT = "end_of_input"
    ABORT = "abort"


class VoiceInputStreamRejectionCode(str, Enum):
    """Provider-neutral reason that a streaming operation was rejected."""

    NONE = "none"
    NOT_SUPPORTED = "not_supported"
    INVALID_STREAM_ID = "invalid_stream_id"
    INVALID_FORMAT = "invalid_format"
    EMPTY_CHUNK = "empty_chunk"
    CHUNK_TOO_LARGE = "chunk_too_large"
    DURATION_EXCEEDED = "duration_exceeded"
    OUT_OF_ORDER = "out_of_order"
    ALREADY_ENDED = "already_ended"
    ALREADY_ABORTED = "already_aborted"
    SESSION_CLOSED = "session_closed"


def _normalize_stream_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("stream_id must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("stream_id must be non-empty")
    if len(normalized) > 128:
        raise ValueError("stream_id must be at most 128 characters")
    if looks_like_private_path(normalized) or any(
        marker in normalized for marker in ("/", "\\", "://")
    ):
        raise ValueError("stream_id must be an opaque identifier, not a path or URL")
    return normalized


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _positive_optional_int(value: object, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer or None")
    if value < 1:
        raise ValueError(f"{field_name} must be at least 1")
    return value


def _normalize_formats(
    values: tuple[VoiceInputAudioEncoding | str, ...]
    | list[VoiceInputAudioEncoding | str],
) -> tuple[VoiceInputAudioEncoding, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError("accepted_audio_formats must be a tuple or list")
    normalized: list[VoiceInputAudioEncoding] = []
    for value in values:
        encoding = (
            value
            if isinstance(value, VoiceInputAudioEncoding)
            else VoiceInputAudioEncoding(str(value).strip().lower())
        )
        if encoding is VoiceInputAudioEncoding.UNKNOWN:
            raise ValueError("accepted_audio_formats must not contain unknown")
        if encoding not in normalized:
            normalized.append(encoding)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class VoiceInputStreamingCapability:
    """Truthful limits for one public audio-chunk streaming boundary."""

    audio_chunk_input_supported: bool = False
    accepted_audio_formats: tuple[VoiceInputAudioEncoding | str, ...] = ()
    maximum_chunk_size_bytes: int | None = None
    maximum_duration_ms: int | None = None
    end_of_input_supported: bool = False
    input_abort_supported: bool = False
    partial_transcript_supported: bool = False
    final_transcript_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "audio_chunk_input_supported",
            "end_of_input_supported",
            "input_abort_supported",
            "partial_transcript_supported",
            "final_transcript_supported",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a boolean")
        formats = _normalize_formats(self.accepted_audio_formats)
        maximum_chunk_size_bytes = _positive_optional_int(
            self.maximum_chunk_size_bytes,
            field_name="maximum_chunk_size_bytes",
        )
        maximum_duration_ms = _positive_optional_int(
            self.maximum_duration_ms,
            field_name="maximum_duration_ms",
        )
        if self.audio_chunk_input_supported:
            if not formats:
                raise ValueError("supported chunk input requires accepted_audio_formats")
            if maximum_chunk_size_bytes is None:
                raise ValueError("supported chunk input requires maximum_chunk_size_bytes")
            if maximum_duration_ms is None:
                raise ValueError("supported chunk input requires maximum_duration_ms")
            if not self.end_of_input_supported:
                raise ValueError("supported chunk input requires end_of_input_supported")
            if not self.final_transcript_supported:
                raise ValueError("supported chunk input requires final_transcript_supported")
        elif any(
            (
                formats,
                maximum_chunk_size_bytes is not None,
                maximum_duration_ms is not None,
                self.end_of_input_supported,
                self.input_abort_supported,
                self.partial_transcript_supported,
                self.final_transcript_supported,
            )
        ):
            raise ValueError("unsupported chunk input must not advertise streaming features")
        object.__setattr__(self, "accepted_audio_formats", formats)
        object.__setattr__(self, "maximum_chunk_size_bytes", maximum_chunk_size_bytes)
        object.__setattr__(self, "maximum_duration_ms", maximum_duration_ms)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "audio_chunk_input_supported": self.audio_chunk_input_supported,
                "accepted_audio_formats": tuple(
                    value.value for value in self.accepted_audio_formats
                ),
                "maximum_chunk_size_bytes": self.maximum_chunk_size_bytes,
                "maximum_duration_ms": self.maximum_duration_ms,
                "end_of_input_supported": self.end_of_input_supported,
                "input_abort_supported": self.input_abort_supported,
                "partial_transcript_supported": self.partial_transcript_supported,
                "final_transcript_supported": self.final_transcript_supported,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class VoiceInputStreamConfig:
    """Immutable format and language selection for one host-owned stream."""

    stream_id: str
    audio_format: VoiceInputAudioFormat
    language: str | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.audio_format, VoiceInputAudioFormat):
            raise TypeError("audio_format must be VoiceInputAudioFormat")
        if self.audio_format.encoding is VoiceInputAudioEncoding.UNKNOWN:
            raise ValueError("stream audio_format encoding must be explicit")
        language = self.language
        if language is not None:
            if not isinstance(language, str):
                raise TypeError("language must be a string or None")
            language = language.strip() or None
        object.__setattr__(self, "stream_id", _normalize_stream_id(self.stream_id))
        object.__setattr__(self, "language", language)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))


@dataclass(frozen=True, slots=True)
class VoiceInputAudioChunk:
    """One ordered, non-empty audio payload supplied by the host application."""

    stream_id: str
    sequence_number: int
    data: bytes = field(repr=False)
    duration_ms: int | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)
    kind: VoiceInputStreamOperationKind = field(
        init=False,
        default=VoiceInputStreamOperationKind.AUDIO_CHUNK,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        data = bytes(self.data)
        if not data:
            raise ValueError("data must be non-empty")
        object.__setattr__(self, "stream_id", _normalize_stream_id(self.stream_id))
        object.__setattr__(
            self,
            "sequence_number",
            _non_negative_int(self.sequence_number, field_name="sequence_number"),
        )
        object.__setattr__(self, "data", data)
        object.__setattr__(
            self,
            "duration_ms",
            _positive_optional_int(self.duration_ms, field_name="duration_ms"),
        )
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    @property
    def byte_count(self) -> int:
        return len(self.data)

    def as_dict(self) -> Mapping[str, object]:
        """Return a safe projection that deliberately excludes raw audio bytes."""

        return MappingProxyType(
            {
                "kind": self.kind.value,
                "stream_id": self.stream_id,
                "sequence_number": self.sequence_number,
                "byte_count": self.byte_count,
                "duration_ms": self.duration_ms,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class VoiceInputStreamEnd:
    """In-order end marker whose sequence is the next expected sequence."""

    stream_id: str
    sequence_number: int
    kind: VoiceInputStreamOperationKind = field(
        init=False,
        default=VoiceInputStreamOperationKind.END_OF_INPUT,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "stream_id", _normalize_stream_id(self.stream_id))
        object.__setattr__(
            self,
            "sequence_number",
            _non_negative_int(self.sequence_number, field_name="sequence_number"),
        )


@dataclass(frozen=True, slots=True)
class VoiceInputStreamAbort:
    """Out-of-band host abort request that does not consume a sequence number."""

    stream_id: str
    reason: str = "host_requested"
    last_sequence_number: int | None = None
    kind: VoiceInputStreamOperationKind = field(
        init=False,
        default=VoiceInputStreamOperationKind.ABORT,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")
        reason = self.reason.strip()
        if not reason:
            raise ValueError("reason must be non-empty")
        if looks_like_private_path(reason):
            raise ValueError("reason must not contain a private path")
        last_sequence_number = self.last_sequence_number
        if last_sequence_number is not None:
            last_sequence_number = _non_negative_int(
                last_sequence_number,
                field_name="last_sequence_number",
            )
        object.__setattr__(self, "stream_id", _normalize_stream_id(self.stream_id))
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "last_sequence_number", last_sequence_number)


@dataclass(frozen=True, slots=True)
class VoiceInputStreamOperationResult:
    """Typed acknowledgement or rejection for a streaming operation."""

    kind: VoiceInputStreamOperationKind | str
    accepted: bool
    stream_id: str
    sequence_number: int | None = None
    next_expected_sequence_number: int | None = None
    rejection_code: VoiceInputStreamRejectionCode | str = (
        VoiceInputStreamRejectionCode.NONE
    )
    safe_message: str = ""
    retryable: bool = False
    terminal: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind = (
            self.kind
            if isinstance(self.kind, VoiceInputStreamOperationKind)
            else VoiceInputStreamOperationKind(str(self.kind))
        )
        rejection_code = (
            self.rejection_code
            if isinstance(self.rejection_code, VoiceInputStreamRejectionCode)
            else VoiceInputStreamRejectionCode(str(self.rejection_code))
        )
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a boolean")
        if type(self.retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        if type(self.terminal) is not bool:
            raise TypeError("terminal must be a boolean")
        if self.accepted and rejection_code is not VoiceInputStreamRejectionCode.NONE:
            raise ValueError("accepted result must use rejection_code=none")
        if not self.accepted and rejection_code is VoiceInputStreamRejectionCode.NONE:
            raise ValueError("rejected result requires a rejection code")
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")
        if looks_like_private_path(self.safe_message):
            raise ValueError("safe_message must not contain a private path")
        sequence_number = self.sequence_number
        if sequence_number is not None:
            sequence_number = _non_negative_int(
                sequence_number,
                field_name="sequence_number",
            )
        next_expected = self.next_expected_sequence_number
        if next_expected is not None:
            next_expected = _non_negative_int(
                next_expected,
                field_name="next_expected_sequence_number",
            )
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "stream_id", _normalize_stream_id(self.stream_id))
        object.__setattr__(self, "sequence_number", sequence_number)
        object.__setattr__(self, "next_expected_sequence_number", next_expected)
        object.__setattr__(self, "rejection_code", rejection_code)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, object]:
        return MappingProxyType(
            {
                "kind": self.kind.value,
                "accepted": self.accepted,
                "stream_id": self.stream_id,
                "sequence_number": self.sequence_number,
                "next_expected_sequence_number": (
                    self.next_expected_sequence_number
                ),
                "rejection_code": self.rejection_code.value,
                "safe_message": self.safe_message,
                "retryable": self.retryable,
                "terminal": self.terminal,
                "public_metadata": dict(self.public_metadata),
            }
        )

    @classmethod
    def accepted_operation(
        cls,
        *,
        kind: VoiceInputStreamOperationKind,
        stream_id: str,
        sequence_number: int | None,
        next_expected_sequence_number: int | None,
        terminal: bool = False,
    ) -> "VoiceInputStreamOperationResult":
        return cls(
            kind=kind,
            accepted=True,
            stream_id=stream_id,
            sequence_number=sequence_number,
            next_expected_sequence_number=next_expected_sequence_number,
            terminal=terminal,
        )

    @classmethod
    def rejected(
        cls,
        *,
        kind: VoiceInputStreamOperationKind,
        stream_id: str,
        rejection_code: VoiceInputStreamRejectionCode,
        safe_message: str,
        sequence_number: int | None = None,
        next_expected_sequence_number: int | None = None,
        retryable: bool = False,
        terminal: bool = False,
    ) -> "VoiceInputStreamOperationResult":
        return cls(
            kind=kind,
            accepted=False,
            stream_id=stream_id,
            sequence_number=sequence_number,
            next_expected_sequence_number=next_expected_sequence_number,
            rejection_code=rejection_code,
            safe_message=safe_message,
            retryable=retryable,
            terminal=terminal,
        )


__all__ = (
    "VOICE_INPUT_STREAMING_API_VERSION",
    "VoiceInputStreamOperationKind",
    "VoiceInputStreamRejectionCode",
    "VoiceInputStreamingCapability",
    "VoiceInputStreamConfig",
    "VoiceInputAudioChunk",
    "VoiceInputStreamEnd",
    "VoiceInputStreamAbort",
    "VoiceInputStreamOperationResult",
)
