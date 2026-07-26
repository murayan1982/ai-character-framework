"""Public voice-input / STT session skeleton.

This module provides the first mock-safe public voice-input session boundary.
It intentionally does not execute real STT providers yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .voice_input import (
    VoiceInputErrorCode,
    VoiceInputOutcome,
    VoiceInputRequest,
    VoiceInputResult,
    _public_mapping,
)
from .voice_input_capability import (
    VoiceInputCapabilities,
    VoiceInputProviderStatus,
    get_voice_input_capabilities,
)


VoiceInputCallback = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class VoiceInputSessionInfo:
    """App-safe metadata for a public voice-input session."""

    api_version: str = "5.2.0"
    session_type: str = "voice_input"
    provider: str | None = None
    language: str | None = None
    real_stt_enabled: bool = False
    provider_status: VoiceInputProviderStatus | str = VoiceInputProviderStatus.DISABLED
    supports_listen_result: bool = True
    supports_text_fallback: bool = True
    supports_events: bool = True
    supports_close: bool = True
    supports_real_stt: bool = False
    safe_message: str = "Real voice input is disabled."
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.provider_status
            if isinstance(self.provider_status, VoiceInputProviderStatus)
            else VoiceInputProviderStatus(str(self.provider_status))
        )
        object.__setattr__(self, "provider_status", status)
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
        allow_provider_execution: bool | None = None,
        credential_env: Mapping[str, str] | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._provider = provider
        self._language = language
        self._real_stt_enabled = bool(real_stt_enabled)
        self._allow_provider_execution = allow_provider_execution
        self._credential_env = credential_env
        self._closed = False
        self._callbacks: list[VoiceInputCallback] = []
        self._capabilities = get_voice_input_capabilities(
            provider=provider,
            real_stt_enabled=real_stt_enabled,
            allow_provider_execution=allow_provider_execution,
            credential_env=credential_env,
            public_metadata=public_metadata,
        )
        self._info = VoiceInputSessionInfo(
            provider=self._capabilities.provider or provider,
            language=language,
            real_stt_enabled=bool(real_stt_enabled),
            provider_status=self._capabilities.provider_status,
            supports_real_stt=self._capabilities.supports_real_stt,
            safe_message=self._capabilities.safe_message,
            public_metadata={
                "boundary": "voice_input",
                "provider_status": self._capabilities.provider_status.value,
                **dict(public_metadata or {}),
            },
        )

    @property
    def info(self) -> VoiceInputSessionInfo:
        return self._info

    @property
    def capabilities(self) -> VoiceInputCapabilities:
        return self._capabilities

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

    def _unavailable_from_capability(self) -> VoiceInputResult:
        status = self._capabilities.provider_status
        reason = self._capabilities.public_metadata.get("reason", status.value)

        error_code = VoiceInputErrorCode.UNAVAILABLE
        if status is VoiceInputProviderStatus.MISSING_CREDENTIALS:
            error_code = VoiceInputErrorCode.MISSING_CREDENTIALS
        elif status is VoiceInputProviderStatus.UNSUPPORTED_PROVIDER:
            error_code = VoiceInputErrorCode.INVALID_REQUEST

        self._emit(
            "voice_input.unavailable",
            provider_status=status.value,
            reason=reason,
            provider=self._capabilities.provider,
        )

        return VoiceInputResult(
            outcome=VoiceInputOutcome.UNAVAILABLE,
            public_error_code=error_code,
            safe_message=self._capabilities.safe_message,
            retryable=self._capabilities.retryable,
            public_metadata={
                "boundary": "voice_input",
                "provider_status": status.value,
                "reason": reason,
                "supports_real_stt": self._capabilities.supports_real_stt,
            },
        )

    def listen_result(self, request: VoiceInputRequest | None = None) -> VoiceInputResult:
        """Return a provider-neutral voice-input result.

        Real STT is intentionally not executed in this skeleton. The session
        now uses voice-input capability preflight to return status-specific
        public results.
        """

        if self._closed:
            self._emit("voice_input.closed")
            return VoiceInputResult.closed()

        if request is None:
            request = VoiceInputRequest(language=self._language)

        self._emit("voice_input.started", language=request.language or self._language)
        return self._unavailable_from_capability()

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
    allow_provider_execution: bool | None = None,
    credential_env: Mapping[str, str] | None = None,
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
        allow_provider_execution=allow_provider_execution,
        credential_env=credential_env,
        public_metadata=public_metadata,
    )
