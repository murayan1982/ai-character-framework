"""Public voice-input / STT session boundary.

The default path remains mock-safe. FW-RT6-7a Control A corrects real-STT
capability/correlation foundations and Control B adds provider-neutral default
fake/real composition without changing v5 result/callback compatibility.
"""

from __future__ import annotations

from . import voice_input_composition as _voice_input_composition
from .voice_input_audio import VoiceInputAudioSource
from .voice_input_provider_adapter import FakeVoiceInputProviderAdapter, VoiceInputProviderAdapter

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .voice_input import (
    VoiceInputErrorCode,
    VoiceInputOutcome,
    VoiceInputRequest,
    VoiceInputResult,
    _public_mapping,
)
from .identity import (
    EventSequence,
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
)
from .realtime import (
    RealtimeErrorCode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeState,
)
from .realtime_event_payloads import RealtimeEventPayload
from .version import VOICE_INPUT_API_VERSION

from .voice_input_capability import (
    VoiceInputCapabilities,
    VoiceInputProviderStatus,
    get_voice_input_capabilities,
    resolve_voice_input_provider_config,
)


VoiceInputCallback = Callable[[Mapping[str, Any]], None]
VoiceInputRealtimeCallback = Callable[[RealtimeEvent], None]


@dataclass(frozen=True, slots=True)
class _VoiceInputTurnContext:
    """Internal Framework-owned correlation context for one voice-input operation."""

    session_id: SessionId
    turn_id: TurnId
    generation_id: GenerationId


@dataclass(frozen=True)
class VoiceInputSessionInfo:
    """App-safe metadata for a public voice-input session."""

    api_version: str = VOICE_INPUT_API_VERSION
    session_type: str = "voice_input"
    session_id: SessionId | str = field(default_factory=SessionId.new)
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
        object.__setattr__(self, "session_id", normalize_session_id(self.session_id))
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
        private_credential: str | None = None,
        allow_provider_sdk_import: bool = False,
        allow_provider_client_creation: bool = False,
        allow_real_provider_execution: bool = False,
        max_audio_bytes: int = 25 * 1024 * 1024,
        provider_timeout_seconds: float = 30.0,
        provider_max_retries: int = 0,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._session_id = SessionId.new()
        self._next_realtime_event_sequence = EventSequence.first()
        self._realtime_event_callbacks: list[VoiceInputRealtimeCallback] = []
        self._realtime_event_lock = RLock()
        self._provider = provider
        self._language = language
        self._allow_provider_execution = allow_provider_execution
        self._credential_env = credential_env
        self._closed = False
        self._callbacks: list[VoiceInputCallback] = []

        capability_credential_env = _voice_input_composition.credential_presence_env(
            provider=provider,
            credential_env=credential_env,
            private_credential=private_credential,
        )
        resolved_provider_config = resolve_voice_input_provider_config(
            provider=provider,
            real_stt_enabled=real_stt_enabled,
            allow_provider_execution=allow_provider_execution,
            credential_env=capability_credential_env,
            public_metadata=public_metadata,
        )
        self._real_stt_enabled = resolved_provider_config.real_stt_enabled
        self._capabilities = get_voice_input_capabilities(
            provider=provider,
            real_stt_enabled=real_stt_enabled,
            allow_provider_execution=allow_provider_execution,
            credential_env=capability_credential_env,
            public_metadata=public_metadata,
        )
        self._composition_config = _voice_input_composition.VoiceInputCompositionConfig(
            provider=self._capabilities.provider or resolved_provider_config.provider,
            real_stt_requested=resolved_provider_config.real_stt_enabled,
            allow_provider_execution=resolved_provider_config.provider_execution_allowed,
            private_credential=private_credential,
            allow_provider_sdk_import=allow_provider_sdk_import,
            allow_provider_client_creation=allow_provider_client_creation,
            allow_real_provider_execution=allow_real_provider_execution,
            max_audio_bytes=max_audio_bytes,
            provider_timeout_seconds=provider_timeout_seconds,
            provider_max_retries=provider_max_retries,
        )
        self._info = VoiceInputSessionInfo(
            session_id=self._session_id,
            provider=self._capabilities.provider or provider,
            language=language,
            real_stt_enabled=resolved_provider_config.real_stt_enabled,
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
    def session_id(self) -> SessionId:
        """Return the stable Framework correlation identity for this session."""

        return self._session_id

    @property
    def is_closed(self) -> bool:
        return self._closed

    def on_realtime_event(
        self,
        callback: VoiceInputRealtimeCallback,
    ) -> VoiceInputRealtimeCallback:
        """Register an additive canonical v6 event callback and return it."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._realtime_event_lock:
            self._realtime_event_callbacks.append(callback)
        return callback

    def _new_realtime_turn_context(self) -> _VoiceInputTurnContext:
        """Allocate one Framework-owned turn/generation correlation context."""

        return _VoiceInputTurnContext(
            session_id=self._session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )

    def _emit_realtime_event(
        self,
        event_type: RealtimeEventType,
        *,
        state: RealtimeState,
        context: _VoiceInputTurnContext | None = None,
        previous_state: RealtimeState | None = None,
        payload: RealtimeEventPayload | None = None,
        public_error_code: RealtimeErrorCode = RealtimeErrorCode.NONE,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeEvent:
        """Emit one sequenced canonical event without changing legacy callbacks."""

        if not isinstance(event_type, RealtimeEventType):
            raise TypeError("event_type must be a RealtimeEventType")
        if not isinstance(state, RealtimeState):
            raise TypeError("state must be a RealtimeState")

        with self._realtime_event_lock:
            sequence = self._next_realtime_event_sequence
            self._next_realtime_event_sequence = sequence.next()
            callbacks = tuple(self._realtime_event_callbacks)

        event = RealtimeEvent(
            type=event_type,
            state=state,
            previous_state=previous_state,
            session_id=self._session_id,
            turn_id=context.turn_id if context is not None else None,
            generation_id=(
                context.generation_id if context is not None else None
            ),
            sequence=sequence,
            payload=payload,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata={
                "boundary": "voice_input",
                **dict(public_metadata or {}),
            },
            boundary="voice_input",
        )
        for callback in callbacks:
            callback(event)
        return event

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

    def transcribe_audio_result(
        self,
        audio_source: VoiceInputAudioSource,
        *,
        request: VoiceInputRequest | None = None,
        adapter: VoiceInputProviderAdapter | None = None,
    ) -> VoiceInputResult:
        """Transcribe host-captured audio through provider-neutral selection.

        An explicit adapter retains precedence. Without one, the normal default
        remains mock-safe fake transcription unless real STT was explicitly
        requested. A real request never silently falls back to fake; it is either
        rejected truthfully by a closed guard or lazily composed through the
        accepted real-provider runtime.
        """

        if self.is_closed:
            try:
                return self.listen_result(request=request)
            except TypeError:
                return self.listen_result()

        if not isinstance(audio_source, VoiceInputAudioSource):
            raise TypeError("audio_source must be a VoiceInputAudioSource")

        effective_request = request or VoiceInputRequest(
            language=audio_source.language,
            max_duration_ms=audio_source.max_duration_ms,
        )
        if adapter is not None:
            return adapter.transcribe(
                audio_source=audio_source,
                request=effective_request,
            )

        reason = self._capabilities.public_metadata.get(
            "reason",
            self._capabilities.provider_status.value,
        )
        return _voice_input_composition.transcribe_default(
            config=self._composition_config,
            audio_source=audio_source,
            request=effective_request,
            capability_supports_real_stt=self._capabilities.supports_real_stt,
            capability_reason=str(reason),
            capability_safe_message=self._capabilities.safe_message,
        )

    def listen_audio_result(
        self,
        audio_source: VoiceInputAudioSource,
        *,
        request: VoiceInputRequest | None = None,
        adapter: VoiceInputProviderAdapter | None = None,
    ) -> VoiceInputResult:
        """Alias for host-captured audio transcription through a lazy adapter."""

        return self.transcribe_audio_result(audio_source, request=request, adapter=adapter)

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
    private_credential: str | None = None,
    allow_provider_sdk_import: bool = False,
    allow_provider_client_creation: bool = False,
    allow_real_provider_execution: bool = False,
    max_audio_bytes: int = 25 * 1024 * 1024,
    provider_timeout_seconds: float = 30.0,
    provider_max_retries: int = 0,
    public_metadata: Mapping[str, Any] | None = None,
) -> VoiceInputSession:
    """Create a provider-neutral public voice-input session.

    The default remains mock-safe. Real provider composition requires explicit
    real-STT intent, all runtime gates, and an explicit private credential.
    """

    return VoiceInputSession(
        project_root=project_root,
        provider=provider,
        language=language,
        real_stt_enabled=real_stt_enabled,
        allow_provider_execution=allow_provider_execution,
        credential_env=credential_env,
        private_credential=private_credential,
        allow_provider_sdk_import=allow_provider_sdk_import,
        allow_provider_client_creation=allow_provider_client_creation,
        allow_real_provider_execution=allow_real_provider_execution,
        max_audio_bytes=max_audio_bytes,
        provider_timeout_seconds=provider_timeout_seconds,
        provider_max_retries=provider_max_retries,
        public_metadata=public_metadata,
    )
