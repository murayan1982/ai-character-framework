"""Provider-neutral public result type for text chat sessions.

This module is intentionally lightweight. Importing it must not import provider
SDKs, runtime audio modules, or application-specific configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping


TextChatOutcome = Literal[
    "completed",
    "interrupted",
    "unavailable",
    "blocked",
    "skipped",
    "rejected",
    "failed",
    "expired",
    "cancelled",
]

TextChatPublicErrorCode = Literal[
    "configuration_missing",
    "provider_unavailable",
    "authentication_required",
    "rate_limited",
    "request_cancelled",
    "timeout",
    "unsupported_capability",
    "session_closed",
    "invalid_request",
    "provider_request_failed",
    "empty_response",
    "unknown_error",
]


@dataclass(frozen=True, slots=True)
class TextChatResult:
    """Provider-neutral public result for text chat operations.

    `TextChatResult` is the typed result shape that host applications can rely
    on without parsing raw exception strings or provider-specific payloads.

    v5.1.0 first makes the type public. Runtime methods that return this type
    can be added as a non-breaking follow-up while preserving existing text
    return behavior during migration.
    """

    outcome: TextChatOutcome
    text: str | None = None
    public_error_code: TextChatPublicErrorCode | None = None
    safe_message: str | None = None
    retryable: bool = False
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Whether the operation completed successfully."""

        return self.outcome == "completed"

    @property
    def is_interrupted(self) -> bool:
        """Whether the operation was interrupted or cancelled."""

        return self.outcome in {"interrupted", "cancelled"}

    @property
    def is_failed(self) -> bool:
        """Whether the operation ended in a non-success state."""

        return not self.is_completed

    @property
    def has_text(self) -> bool:
        """Whether the result includes usable response text."""

        return bool(self.text)

    @classmethod
    def completed(
        cls,
        text: str,
        *,
        safe_message: str | None = None,
        public_metadata: Mapping[str, str] | None = None,
    ) -> "TextChatResult":
        """Build a completed text chat result."""

        return cls(
            outcome="completed",
            text=text,
            safe_message=safe_message,
            retryable=False,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def failed(
        cls,
        *,
        public_error_code: TextChatPublicErrorCode = "unknown_error",
        safe_message: str | None = None,
        retryable: bool = False,
        public_metadata: Mapping[str, str] | None = None,
    ) -> "TextChatResult":
        """Build a failed text chat result with a provider-neutral error code."""

        return cls(
            outcome="failed",
            text=None,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
        )

    @classmethod
    def interrupted(
        cls,
        *,
        safe_message: str | None = None,
        public_metadata: Mapping[str, str] | None = None,
    ) -> "TextChatResult":
        """Build an interrupted text chat result."""

        return cls(
            outcome="interrupted",
            text=None,
            public_error_code="request_cancelled",
            safe_message=safe_message,
            retryable=True,
            public_metadata=public_metadata or {},
        )
