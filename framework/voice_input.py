"""Public voice-input / STT request and result contracts.

This module intentionally contains provider-neutral public data types only.
It must not import microphone, STT provider, audio runtime, or provider SDK
modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


_SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


def _public_mapping(values: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a shallow immutable public-safe metadata mapping."""

    if not values:
        return MappingProxyType({})

    safe: dict[str, Any] = {}
    for key, value in values.items():
        text_key = str(key)
        lower_key = text_key.lower()
        if any(fragment in lower_key for fragment in _SECRET_KEY_FRAGMENTS):
            safe[text_key] = "<redacted>"
        else:
            safe[text_key] = value
    return MappingProxyType(safe)


class VoiceInputOutcome(str, Enum):
    """Provider-neutral voice-input outcome."""

    COMPLETED = "completed"
    NO_INPUT = "no_input"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    CLOSED = "closed"


class VoiceInputErrorCode(str, Enum):
    """Provider-neutral public voice-input error code."""

    NONE = "none"
    NO_INPUT = "no_input"
    INTERRUPTED = "interrupted"
    UNAVAILABLE = "unavailable"
    MISSING_CREDENTIALS = "missing_credentials"
    PROVIDER_ERROR = "provider_error"
    SESSION_CLOSED = "session_closed"
    INVALID_REQUEST = "invalid_request"


@dataclass(frozen=True)
class VoiceInputRequest:
    """Provider-neutral request for public voice-input / STT sessions."""

    language: str | None = None
    timeout_ms: int | None = None
    max_duration_ms: int | None = None
    vad_enabled: bool = True
    input_device_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive when provided")
        if self.max_duration_ms is not None and self.max_duration_ms <= 0:
            raise ValueError("max_duration_ms must be positive when provided")
        object.__setattr__(self, "metadata", _public_mapping(self.metadata))

    @classmethod
    def from_text_fallback(
        cls,
        *,
        language: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputRequest":
        """Create a request marker for text-fallback STT-like flows."""

        merged = dict(metadata or {})
        merged.setdefault("input_mode", "text_fallback")
        return cls(language=language, metadata=merged)


@dataclass(frozen=True)
class VoiceInputResult:
    """Provider-neutral public result for voice-input / STT sessions."""

    outcome: VoiceInputOutcome | str
    text: str = ""
    language: str | None = None
    confidence: float | None = None
    duration_ms: int | None = None
    public_error_code: VoiceInputErrorCode | str = VoiceInputErrorCode.NONE
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = self.outcome if isinstance(self.outcome, VoiceInputOutcome) else VoiceInputOutcome(str(self.outcome))
        error_code = (
            self.public_error_code
            if isinstance(self.public_error_code, VoiceInputErrorCode)
            else VoiceInputErrorCode(str(self.public_error_code))
        )

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0 when provided")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative when provided")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @property
    def is_completed(self) -> bool:
        return self.outcome is VoiceInputOutcome.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return self.outcome in {
            VoiceInputOutcome.COMPLETED,
            VoiceInputOutcome.NO_INPUT,
            VoiceInputOutcome.INTERRUPTED,
            VoiceInputOutcome.FAILED,
            VoiceInputOutcome.UNAVAILABLE,
            VoiceInputOutcome.CLOSED,
        }

    @classmethod
    def completed(
        cls,
        text: str,
        *,
        language: str | None = None,
        confidence: float | None = None,
        duration_ms: int | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.COMPLETED,
            text=text,
            language=language,
            confidence=confidence,
            duration_ms=duration_ms,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def no_input(cls, *, safe_message: str = "No voice input was detected.") -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.NO_INPUT,
            public_error_code=VoiceInputErrorCode.NO_INPUT,
            safe_message=safe_message,
            retryable=True,
        )

    @classmethod
    def interrupted(cls, *, safe_message: str = "Voice input was interrupted.") -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.INTERRUPTED,
            public_error_code=VoiceInputErrorCode.INTERRUPTED,
            safe_message=safe_message,
            retryable=True,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        safe_message: str = "Voice input is unavailable.",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.UNAVAILABLE,
            public_error_code=VoiceInputErrorCode.UNAVAILABLE,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def failed(
        cls,
        *,
        public_error_code: VoiceInputErrorCode | str = VoiceInputErrorCode.PROVIDER_ERROR,
        safe_message: str = "Voice input failed.",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.FAILED,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def closed(cls, *, safe_message: str = "Voice input session is closed.") -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.CLOSED,
            public_error_code=VoiceInputErrorCode.SESSION_CLOSED,
            safe_message=safe_message,
            retryable=False,
        )
