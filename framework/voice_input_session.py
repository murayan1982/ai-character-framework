"""Public voice-input / STT session skeleton.

This module provides the first mock-safe public voice-input session boundary.
It intentionally does not execute real STT providers yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .voice_input import VoiceInputRequest, VoiceInputResult, _public_mapping


VoiceInputCallback = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class VoiceInputSessionInfo:
    """App-safe metadata for a public voice-input session."""

    api_version: str = "5.2.0"
    session_type: str = "voice_input"
    provider: str | None = None
    language: str | None = None
    real_stt_enabled: bool = False
    supports_listen_result: bool = True
    supports_text_fallback: bool = True
    supports_events: bool = True
    supports_close: bool = True
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


class VoiceInputSession:
    """Mock-safe public voice-input session skeleton.

    The session exposes the host-app lifecycle and typed-result boundary before
    real STT provider execution is implemented.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        provider: str | None = None,
        language: str | None = None,
        real_stt_enabled: bool | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._provider = provider
        self._language = language
        self._real_stt_enabled = bool(real_stt_enabled)
        self._closed = False
        self._callbacks: list[VoiceInputCallback] = []
        self._info = VoiceInputSessionInfo(
            provider=provider,
            language=language,
            real_stt_enabled=self._real_stt_enabled,
            public_metadata=public_metadata or {},
        )

    @property
    def info(self) -> VoiceInputSessionInfo:
        return self._info

    @property
    def is_closed(self) -> bool:
        return self._closed

    def on_event(self, callback: VoiceInputCallback) -> None:
        """Register an app-facing provider-neutral event callback."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callbacks.append(callback)

    def _emit(self, event_type: str, **payload: Any) -> None:
        event = MappingProxyType(
            {
                "type": event_type,
                "session_type": "voice_input",
                "payload": _public_mapping(payload),
            }
        )
        for callback in list(self._callbacks):
            callback(event)

    def listen_result(self, request: VoiceInputRequest | None = None) -> VoiceInputResult:
        """Return a provider-neutral voice-input result.

        Real STT is intentionally not executed in this skeleton. Until a real
        guarded provider boundary is implemented, an open session reports
        `unavailable` safely.
        """

        if self._closed:
            self._emit("voice_input.closed")
            return VoiceInputResult.closed()

        if request is None:
            request = VoiceInputRequest(language=self._language)

        self._emit("voice_input.started", language=request.language or self._language)

        if self._real_stt_enabled:
            self._emit("voice_input.unavailable", reason="real_stt_not_implemented")
            return VoiceInputResult.unavailable(
                safe_message="Real voice input is not implemented in this public skeleton.",
                retryable=False,
                public_metadata={
                    "boundary": "voice_input",
                    "real_stt_enabled": True,
                    "reason": "real_stt_not_implemented",
                },
            )

        self._emit("voice_input.unavailable", reason="real_stt_disabled")
        return VoiceInputResult.unavailable(
            safe_message="Voice input is unavailable because real STT execution is disabled.",
            retryable=False,
            public_metadata={
                "boundary": "voice_input",
                "real_stt_enabled": False,
                "reason": "real_stt_disabled",
            },
        )

    def text_fallback_result(
        self,
        text: str,
        *,
        language: str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> VoiceInputResult:
        """Return a completed result for app-provided text fallback input."""

        if self._closed:
            self._emit("voice_input.closed")
            return VoiceInputResult.closed()

        self._emit("voice_input.text_fallback", language=language or self._language)
        return VoiceInputResult.completed(
            text,
            language=language or self._language,
            public_metadata={
                "boundary": "voice_input",
                "input_mode": "text_fallback",
                **dict(public_metadata or {}),
            },
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._emit("voice_input.closed")

    def dispose(self) -> None:
        self.close()

    def __enter__(self) -> "VoiceInputSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def create_voice_input_session(
    *,
    project_root: str | Path | None = None,
    provider: str | None = None,
    language: str | None = None,
    real_stt_enabled: bool | None = None,
    public_metadata: Mapping[str, Any] | None = None,
) -> VoiceInputSession:
    """Create a mock-safe public voice-input session.

    This factory is provider-neutral by default. Real STT execution is not
    performed by this skeleton.
    """

    return VoiceInputSession(
        project_root=project_root,
        provider=provider,
        language=language,
        real_stt_enabled=real_stt_enabled,
        public_metadata=public_metadata,
    )
