"""Public voice-input / STT session boundary.

The default path remains mock-safe. FW-RT6-7a Control A corrects real-STT
capability/correlation foundations and Control B adds provider-neutral default
fake/real composition without changing v5 result/callback compatibility.
"""

from __future__ import annotations

from . import voice_input_composition as _voice_input_composition
from .voice_input_audio import VoiceInputAudioSource
from .voice_input_provider_adapter import FakeVoiceInputProviderAdapter, VoiceInputProviderAdapter

from dataclasses import dataclass, field, replace
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
from .realtime_event_payloads import (
    DiagnosticEventPayload,
    LifecycleEventPayload,
    RealtimeEventPayload,
    TranscriptEventPayload,
)
from .realtime_generation_gate import (
    GenerationAdmissionDecision,
    GenerationAdvanceReason,
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
)
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
        self._input_operation_lock = RLock()
        self._generation_gate = RealtimeGenerationGate()
        self._active_input_context: _VoiceInputTurnContext | None = None
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

        with self._input_operation_lock:
            turn_id = TurnId.new()
            context = _VoiceInputTurnContext(
                session_id=self._session_id,
                turn_id=turn_id,
                generation_id=self._generation_gate.start_generation(turn_id),
            )
            self._active_input_context = context
            return context

    def _input_context_is_current(self, context: _VoiceInputTurnContext) -> bool:
        return (
            self._active_input_context == context
            and self._generation_gate.current_turn_id == context.turn_id
            and self._generation_gate.current_generation_id == context.generation_id
        )

    def _admit_input_completion(
        self,
        *,
        context: _VoiceInputTurnContext,
        value: object,
    ) -> GenerationAdmissionDecision[object]:
        return self._generation_gate.admit_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=context.turn_id,
                generation_id=context.generation_id,
                stage="voice_input",
                value=value,
            )
        )

    def _emit_stale_input_completion(
        self,
        *,
        context: _VoiceInputTurnContext,
        decision: GenerationAdmissionDecision[object],
    ) -> RealtimeEvent:
        if decision.accepted or decision.stale_reason is None:
            raise ValueError("stale voice-input diagnostic requires a rejected completion")
        metadata: dict[str, object] = {
            "stale_reason": decision.stale_reason.value,
            "late_transcript_delivered": False,
            "provider_hard_cancel_claimed": False,
        }
        if decision.retired_by is not None:
            metadata["retired_by"] = decision.retired_by.value
        return self._emit_realtime_event(
            RealtimeEventType.STALE_RESULT_DROPPED,
            state=RealtimeState.INTERRUPTED,
            previous_state=RealtimeState.LISTENING,
            context=context,
            payload=DiagnosticEventPayload(
                code="stale_voice_input_completion",
                drop_reason=decision.stale_reason.value,
            ),
            safe_message="Stale voice input completion was dropped.",
            public_metadata=metadata,
        )

    def _finish_input_context(self, context: _VoiceInputTurnContext) -> None:
        if not self._input_context_is_current(context):
            return
        self._generation_gate.advance(GenerationAdvanceReason.TURN_TERMINAL)
        self._active_input_context = None

    @staticmethod
    def _correlate_input_result(
        result: VoiceInputResult,
        context: _VoiceInputTurnContext,
    ) -> VoiceInputResult:
        if not isinstance(result, VoiceInputResult):
            raise TypeError("voice-input adapter must return a VoiceInputResult")
        return replace(
            result,
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation_id=context.generation_id,
        )

    @staticmethod
    def _stale_input_result(
        context: _VoiceInputTurnContext,
    ) -> VoiceInputResult:
        return VoiceInputResult.interrupted(
            safe_message="Stale voice input completion was dropped.",
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation_id=context.generation_id,
        )

    def abort_input(self) -> bool:
        """Cooperatively invalidate the active input generation once.

        A true result means only that Framework generation invalidation was
        accepted. It does not claim provider hard cancellation or physical
        termination of host audio capture.
        """

        with self._input_operation_lock:
            context = self._active_input_context
            if context is None or not self._input_context_is_current(context):
                return False
            retired = self._generation_gate.advance(GenerationAdvanceReason.CANCEL)
            if retired is None:
                return False
            self._active_input_context = None
            self._emit_realtime_event(
                RealtimeEventType.VOICE_INPUT_FAILED,
                state=RealtimeState.INTERRUPTED,
                previous_state=RealtimeState.LISTENING,
                context=context,
                payload=LifecycleEventPayload(reason="input_aborted"),
                public_error_code=RealtimeErrorCode.INTERRUPTED,
                safe_message="Voice input was interrupted.",
                retryable=True,
                public_metadata={
                    "generation_invalidated": True,
                    "provider_hard_cancel_claimed": False,
                    "host_audio_capture_stopped_claimed": False,
                },
            )
            return True

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

        context = self._new_realtime_turn_context()
        event_metadata = {
            "audio_id": audio_source.audio_id,
            "source_kind": audio_source.source_kind.value,
            "raw_audio_retained": False,
            "audio_path_exposed": False,
        }
        with self._input_operation_lock:
            self._emit_realtime_event(
                RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                state=RealtimeState.IDLE,
                context=context,
                payload=LifecycleEventPayload(reason="voice_input_preflight"),
                public_metadata=event_metadata,
            )
            if not self._input_context_is_current(context):
                return VoiceInputResult.interrupted(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    generation_id=context.generation_id,
                )
            self._emit_realtime_event(
                RealtimeEventType.LISTENING_STARTED,
                state=RealtimeState.LISTENING,
                previous_state=RealtimeState.IDLE,
                context=context,
                payload=LifecycleEventPayload(reason="voice_input_started"),
                public_metadata=event_metadata,
            )
            if not self._input_context_is_current(context):
                return VoiceInputResult.interrupted(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    generation_id=context.generation_id,
                )

        effective_request = request or VoiceInputRequest(
            language=audio_source.language,
            max_duration_ms=audio_source.max_duration_ms,
        )
        try:
            if adapter is not None:
                result = adapter.transcribe(
                    audio_source=audio_source,
                    request=effective_request,
                )
            else:
                reason = self._capabilities.public_metadata.get(
                    "reason",
                    self._capabilities.provider_status.value,
                )
                result = _voice_input_composition.transcribe_default(
                    config=self._composition_config,
                    audio_source=audio_source,
                    request=effective_request,
                    capability_supports_real_stt=self._capabilities.supports_real_stt,
                    capability_reason=str(reason),
                    capability_safe_message=self._capabilities.safe_message,
                )
            result = self._correlate_input_result(result, context)
        except Exception:
            with self._input_operation_lock:
                decision = self._admit_input_completion(
                    context=context,
                    value=None,
                )
                if not decision.accepted:
                    self._emit_stale_input_completion(
                        context=context,
                        decision=decision,
                    )
                    return self._stale_input_result(context)
                self._emit_realtime_event(
                    RealtimeEventType.VOICE_INPUT_FAILED,
                    state=RealtimeState.FAILED,
                    previous_state=RealtimeState.LISTENING,
                    context=context,
                    payload=LifecycleEventPayload(reason="voice_input_stage_exception"),
                    public_error_code=RealtimeErrorCode.STAGE_FAILED,
                    safe_message="Voice input failed.",
                    public_metadata=event_metadata,
                )
                self._finish_input_context(context)
            raise

        with self._input_operation_lock:
            decision = self._admit_input_completion(
                context=context,
                value=result,
            )
            if not decision.accepted:
                self._emit_stale_input_completion(
                    context=context,
                    decision=decision,
                )
                return self._stale_input_result(context)

            if result.is_completed:
                self._emit_realtime_event(
                    RealtimeEventType.LISTENING_COMPLETED,
                    state=RealtimeState.TRANSCRIBING,
                    previous_state=RealtimeState.LISTENING,
                    context=context,
                    payload=LifecycleEventPayload(reason="voice_input_completed"),
                    public_metadata=event_metadata,
                )
                if not self._input_context_is_current(context):
                    stale = self._admit_input_completion(
                        context=context,
                        value=result,
                    )
                    self._emit_stale_input_completion(
                        context=context,
                        decision=stale,
                    )
                    return self._stale_input_result(context)
                self._emit_realtime_event(
                    RealtimeEventType.TRANSCRIPT_FINAL,
                    state=RealtimeState.TRANSCRIBING,
                    context=context,
                    payload=TranscriptEventPayload(
                        text=result.text,
                        is_final=True,
                        confidence=result.confidence,
                    ),
                    public_metadata=event_metadata,
                )
                self._finish_input_context(context)
                return result

            error_code = RealtimeErrorCode.STAGE_FAILED
            if result.public_error_code is VoiceInputErrorCode.UNAVAILABLE:
                error_code = RealtimeErrorCode.UNAVAILABLE
            elif result.public_error_code is VoiceInputErrorCode.INVALID_REQUEST:
                error_code = RealtimeErrorCode.INVALID_REQUEST
            elif result.public_error_code is VoiceInputErrorCode.INTERRUPTED:
                error_code = RealtimeErrorCode.INTERRUPTED
            elif result.public_error_code is VoiceInputErrorCode.PROVIDER_ERROR:
                error_code = RealtimeErrorCode.PROVIDER_ERROR

            self._emit_realtime_event(
                RealtimeEventType.VOICE_INPUT_FAILED,
                state=RealtimeState.FAILED,
                previous_state=RealtimeState.LISTENING,
                context=context,
                payload=LifecycleEventPayload(reason=result.outcome.value),
                public_error_code=error_code,
                safe_message=result.safe_message,
                retryable=result.retryable,
                public_metadata={
                    **event_metadata,
                    "outcome": result.outcome.value,
                },
            )
            self._finish_input_context(context)
            return result

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
