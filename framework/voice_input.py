"""Public voice-input / STT request and result contracts.

This module intentionally contains provider-neutral public data types only.
It must not import microphone, STT provider, audio runtime, or provider SDK
modules.
"""

from __future__ import annotations
from .public_safety import public_mapping as _recursive_public_mapping

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .identity import (
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)


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
    """Delegate to the common recursive public-safety utility."""
    return _recursive_public_mapping(values)


def _normalize_generation_id(
    value: GenerationId | str | None,
) -> GenerationId | None:
    if value is None:
        return None
    if isinstance(value, GenerationId):
        return value
    if not isinstance(value, str):
        raise TypeError("generation_id must be a GenerationId, string, or None")
    return GenerationId.parse(value)


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
    session_id: SessionId | str | None = None
    turn_id: TurnId | str | None = None
    generation_id: GenerationId | str | None = None

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

        session_id = normalize_session_id(self.session_id)
        turn_id = normalize_turn_id(self.turn_id)
        generation_id = _normalize_generation_id(self.generation_id)
        if turn_id is not None and session_id is None:
            raise ValueError("turn_id requires session_id")
        if generation_id is not None and turn_id is None:
            raise ValueError("generation_id requires turn_id")

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "public_error_code", error_code)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "turn_id", turn_id)
        object.__setattr__(self, "generation_id", generation_id)

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
        session_id: SessionId | str | None = None,
        turn_id: TurnId | str | None = None,
        generation_id: GenerationId | str | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.COMPLETED,
            text=text,
            language=language,
            confidence=confidence,
            duration_ms=duration_ms,
            public_metadata=public_metadata or {},
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
        )

    @classmethod
    def no_input(
        cls,
        *,
        safe_message: str = "No voice input was detected.",
        session_id: SessionId | str | None = None,
        turn_id: TurnId | str | None = None,
        generation_id: GenerationId | str | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.NO_INPUT,
            public_error_code=VoiceInputErrorCode.NO_INPUT,
            safe_message=safe_message,
            retryable=True,
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
        )

    @classmethod
    def interrupted(
        cls,
        *,
        safe_message: str = "Voice input was interrupted.",
        session_id: SessionId | str | None = None,
        turn_id: TurnId | str | None = None,
        generation_id: GenerationId | str | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.INTERRUPTED,
            public_error_code=VoiceInputErrorCode.INTERRUPTED,
            safe_message=safe_message,
            retryable=True,
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        safe_message: str = "Voice input is unavailable.",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
        session_id: SessionId | str | None = None,
        turn_id: TurnId | str | None = None,
        generation_id: GenerationId | str | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.UNAVAILABLE,
            public_error_code=VoiceInputErrorCode.UNAVAILABLE,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
        )

    @classmethod
    def failed(
        cls,
        *,
        public_error_code: VoiceInputErrorCode | str = VoiceInputErrorCode.PROVIDER_ERROR,
        safe_message: str = "Voice input failed.",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
        session_id: SessionId | str | None = None,
        turn_id: TurnId | str | None = None,
        generation_id: GenerationId | str | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.FAILED,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
        )

    @classmethod
    def closed(
        cls,
        *,
        safe_message: str = "Voice input session is closed.",
        session_id: SessionId | str | None = None,
        turn_id: TurnId | str | None = None,
        generation_id: GenerationId | str | None = None,
    ) -> "VoiceInputResult":
        return cls(
            outcome=VoiceInputOutcome.CLOSED,
            public_error_code=VoiceInputErrorCode.SESSION_CLOSED,
            safe_message=safe_message,
            retryable=False,
            session_id=session_id,
            turn_id=turn_id,
            generation_id=generation_id,
        )
