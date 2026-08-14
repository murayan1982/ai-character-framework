"""Public voice-input / STT session boundary.

The default path remains mock-safe. FW-RT6-7a Control A corrects real-STT
capability/correlation foundations and Control B adds provider-neutral default
fake/real composition. FW-RT6-7c keeps result and mapping-callback compatibility
while adopting Framework-owned v6 correlation.
"""

from __future__ import annotations

from . import voice_input_composition as _voice_input_composition
from .backpressure import (
    BackpressureAdmissionResult,
    BackpressureCapability,
    BackpressureControlResult,
    BackpressureSnapshot,
)
from .voice_input_audio import VoiceInputAudioSource
from .voice_input_provider_adapter import FakeVoiceInputProviderAdapter, VoiceInputProviderAdapter
from .voice_input_stream_runtime import VoiceInputStreamRuntime
from .voice_input_streaming import (
    VoiceInputAudioChunk,
    VoiceInputStreamAbort,
    VoiceInputStreamConfig,
    VoiceInputStreamEnd,
    VoiceInputStreamOperationResult,
    VoiceInputStreamingCapability,
)
from .voice_input_streaming_adapter import VoiceInputStreamingAdapter

from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Callable, Mapping

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

if TYPE_CHECKING:
    from .session_close import SessionCloseResult
    from .session_compatibility import SessionCompatibilityProfile

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
        self._retired_realtime_event_callbacks: tuple[
            VoiceInputRealtimeCallback, ...
        ] = ()
        self._realtime_event_lock = RLock()
        self._input_operation_lock = RLock()
        self._generation_gate = RealtimeGenerationGate()
        self._active_input_context: _VoiceInputTurnContext | None = None
        self._stream_input_context: _VoiceInputTurnContext | None = None
        self._last_stream_result: VoiceInputResult | None = None
        self._streaming_runtime = VoiceInputStreamRuntime(
            on_partial=self._emit_stream_partial_transcript
        )
        self._provider = provider
        self._language = language
        self._allow_provider_execution = allow_provider_execution
        self._credential_env = credential_env
        self._closed = False
        self._callbacks: list[VoiceInputCallback] = []
        self._last_close_result: SessionCloseResult | None = None
        self._callback_failure_count = 0

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

    @property
    def last_close_result(self) -> SessionCloseResult | None:
        """Return the latest immutable close observation."""

        return self._last_close_result

    @property
    def streaming_capability(self) -> VoiceInputStreamingCapability:
        """Return the explicitly configured audio-chunk streaming capability."""

        return self._streaming_runtime.capability

    @property
    def audio_input_backpressure_capability(self) -> BackpressureCapability:
        """Return truthful limits for the session-owned audio-input boundary."""

        return self._streaming_runtime.backpressure_capability

    @property
    def audio_input_backpressure_snapshot(self) -> BackpressureSnapshot:
        """Return count-only audio admission state without raw audio."""

        return self._streaming_runtime.backpressure_snapshot

    @property
    def last_audio_input_backpressure_result(
        self,
    ) -> BackpressureAdmissionResult | None:
        """Return the most recent typed audio-input admission rejection."""

        return self._streaming_runtime.last_backpressure_result

    def pause_audio_input(self) -> BackpressureControlResult:
        """Pause new audio chunks without cancelling an accepted chunk."""

        with self._input_operation_lock:
            if self._closed:
                raise RuntimeError("Voice input session is closed.")
            return self._streaming_runtime.pause_backpressure()

    def resume_audio_input(self) -> BackpressureControlResult:
        """Resume new audio chunks without changing accepted work."""

        with self._input_operation_lock:
            if self._closed:
                raise RuntimeError("Voice input session is closed.")
            return self._streaming_runtime.resume_backpressure()

    @property
    def last_stream_result(self) -> VoiceInputResult | None:
        """Return the latest final or interrupted streaming transcript result."""

        return self._last_stream_result

    @property
    def compatibility_profile(self) -> SessionCompatibilityProfile:
        """Return the immutable warning-free v5 standalone profile."""

        from .session_compatibility import (
            StandaloneSessionKind,
            build_session_compatibility_profile,
        )

        return build_session_compatibility_profile(
            StandaloneSessionKind.VOICE_INPUT
        )

    def on_realtime_event(
        self,
        callback: VoiceInputRealtimeCallback,
    ) -> VoiceInputRealtimeCallback:
        """Register an additive canonical v6 event callback and return it."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._realtime_event_lock:
            if self._closed:
                raise RuntimeError("Voice input session is closed.")
            self._realtime_event_callbacks.append(callback)
        return callback

    def _dispatch_public_callbacks(
        self,
        callbacks: tuple[Callable[[object], None], ...],
        event: object,
    ) -> int:
        """Invoke callbacks with the input-operation lock fully released."""

        from .callback_isolation import (
            CallbackBoundary,
            dispatch_isolated_callbacks,
        )

        lock = self._input_operation_lock
        is_owned = getattr(lock, "_is_owned", None)
        release_save = getattr(lock, "_release_save", None)
        acquire_restore = getattr(lock, "_acquire_restore", None)
        restore_state: object | None = None
        if callable(is_owned) and is_owned():
            if not callable(release_save) or not callable(acquire_restore):
                raise RuntimeError("input callback lock release is unavailable")
            restore_state = release_save()
        try:
            result = dispatch_isolated_callbacks(
                callbacks,
                event,
                boundary=CallbackBoundary.PUBLIC_CALLBACK,
            )
        finally:
            if restore_state is not None:
                acquire_restore(restore_state)

        if result.failed_count:
            with self._realtime_event_lock:
                self._callback_failure_count += result.failed_count
        return result.failed_count

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

    def _apply_input_completion(
        self,
        *,
        context: _VoiceInputTurnContext,
        value: object,
        deliver: Callable[[object], None],
    ) -> GenerationAdmissionDecision[object]:
        return self._generation_gate.apply_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=context.turn_id,
                generation_id=context.generation_id,
                stage="voice_input_transcript",
                value=value,
            ),
            deliver=deliver,
        )

    def _emit_stale_input_completion(
        self,
        *,
        context: _VoiceInputTurnContext,
        decision: GenerationAdmissionDecision[object],
    ) -> RealtimeEvent | None:
        if decision.accepted or decision.stale_reason is None:
            raise ValueError("stale voice-input diagnostic requires a rejected completion")
        metadata: dict[str, object] = {
            "stale_reason": decision.stale_reason.value,
            "late_transcript_delivered": False,
            "provider_hard_cancel_claimed": False,
        }
        if decision.retired_by is not None:
            metadata["retired_by"] = decision.retired_by.value
        event = self._emit_realtime_event(
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
        if self._closed:
            with self._realtime_event_lock:
                self._retired_realtime_event_callbacks = ()
        return event

    def _finish_input_context(self, context: _VoiceInputTurnContext) -> None:
        if not self._input_context_is_current(context):
            return
        self._generation_gate.advance(GenerationAdvanceReason.TURN_TERMINAL)
        self._active_input_context = None

    def configure_audio_streaming(
        self,
        adapter: VoiceInputStreamingAdapter,
    ) -> VoiceInputStreamingCapability:
        """Install an explicit provider-neutral streaming adapter.

        The factory signature remains unchanged.  Configuration is rejected
        after close or while any voice-input operation owns the generation.
        """

        with self._input_operation_lock:
            if self._closed:
                raise RuntimeError("Voice input session is closed.")
            if self._active_input_context is not None:
                raise RuntimeError("Voice input operation is already active.")
            return self._streaming_runtime.configure(adapter)

    def begin_audio_stream(self, config: VoiceInputStreamConfig) -> bool:
        """Admit one host-owned stream; return false when unavailable or busy."""

        with self._input_operation_lock:
            if self._closed or self._active_input_context is not None:
                return False
            if not self._streaming_runtime.begin(config):
                return False
            context = self._new_realtime_turn_context()
            self._stream_input_context = context
            self._last_stream_result = None
            self._emit_realtime_event(
                RealtimeEventType.LISTENING_STARTED,
                state=RealtimeState.LISTENING,
                context=context,
                payload=LifecycleEventPayload(reason="audio_stream_started"),
                public_metadata={
                    "input_mode": "audio_stream",
                    "stream_id": config.stream_id,
                    "audio_encoding": config.audio_format.encoding.value,
                    "host_audio_capture_owned": True,
                },
            )
            return True

    def _emit_stream_partial_transcript(
        self,
        stream_id: str,
        chunk_sequence_number: int,
        text: str,
        confidence: float | None,
    ) -> None:
        with self._input_operation_lock:
            context = self._stream_input_context
            if (
                context is None
                or not self._input_context_is_current(context)
                or self._streaming_runtime.active_stream_id != stream_id
            ):
                return
            self._emit_realtime_event(
                RealtimeEventType.TRANSCRIPT_PARTIAL,
                state=RealtimeState.TRANSCRIBING,
                previous_state=RealtimeState.LISTENING,
                context=context,
                payload=TranscriptEventPayload(
                    text=text,
                    is_final=False,
                    confidence=confidence,
                ),
                public_metadata={
                    "input_mode": "audio_stream",
                    "stream_id": stream_id,
                    "chunk_sequence_number": chunk_sequence_number,
                    "provider_hard_cancel_claimed": False,
                },
            )

    def _terminate_stream_failure(
        self,
        *,
        stream_id: str,
        safe_message: str,
    ) -> None:
        context = self._stream_input_context
        if context is None or not self._input_context_is_current(context):
            return
        self._last_stream_result = VoiceInputResult.failed(
            public_error_code=VoiceInputErrorCode.PROVIDER_ERROR,
            safe_message=safe_message,
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation_id=context.generation_id,
        )
        self._emit_realtime_event(
            RealtimeEventType.VOICE_INPUT_FAILED,
            state=RealtimeState.FAILED,
            previous_state=RealtimeState.LISTENING,
            context=context,
            payload=LifecycleEventPayload(reason="audio_stream_failed"),
            public_error_code=RealtimeErrorCode.PROVIDER_ERROR,
            safe_message=safe_message,
            public_metadata={
                "input_mode": "audio_stream",
                "stream_id": stream_id,
                "raw_exception_exposed": False,
            },
        )
        self._finish_input_context(context)
        self._stream_input_context = None

    def send_audio_chunk(
        self,
        chunk: VoiceInputAudioChunk,
    ) -> VoiceInputStreamOperationResult:
        """Validate and deliver exactly the next chunk to the configured adapter."""

        # Admission occurs before the operation lock so a concurrent caller gets
        # an immediate typed capacity rejection instead of waiting unboundedly.
        result = self._streaming_runtime.send(chunk)
        with self._input_operation_lock:
            if not result.accepted and result.terminal:
                context = self._stream_input_context
                if context is not None and self._input_context_is_current(context):
                    self._terminate_stream_failure(
                        stream_id=chunk.stream_id,
                        safe_message=result.safe_message,
                    )
            return result

    def end_audio_input(
        self,
        marker: VoiceInputStreamEnd,
    ) -> VoiceInputStreamOperationResult:
        """Accept the ordered end marker and emit one correlated final transcript."""

        with self._input_operation_lock:
            operation, final_result = self._streaming_runtime.end(marker)
            context = self._stream_input_context
            if not operation.accepted:
                if operation.terminal and context is not None:
                    self._terminate_stream_failure(
                        stream_id=marker.stream_id,
                        safe_message=operation.safe_message,
                    )
                return operation
            if context is None or final_result is None:
                raise AssertionError("accepted stream end requires a final result")
            correlated = self._correlate_input_result(final_result, context)
            applied: list[object] = []
            decision = self._apply_input_completion(
                context=context,
                value=correlated,
                deliver=applied.append,
            )
            if not decision.accepted:
                self._emit_stale_input_completion(context=context, decision=decision)
                self._last_stream_result = self._stale_input_result(context)
                self._stream_input_context = None
                return operation
            delivered = applied[0]
            if not isinstance(delivered, VoiceInputResult):
                raise AssertionError("stream final delivery must retain VoiceInputResult")
            self._last_stream_result = delivered
            self._emit_realtime_event(
                RealtimeEventType.TRANSCRIPT_FINAL,
                state=RealtimeState.TRANSCRIBING,
                context=context,
                payload=TranscriptEventPayload(
                    text=delivered.text,
                    is_final=True,
                    confidence=delivered.confidence,
                ),
                public_metadata={
                    "input_mode": "audio_stream",
                    "stream_id": marker.stream_id,
                    "end_sequence_number": marker.sequence_number,
                },
            )
            self._finish_input_context(context)
            self._stream_input_context = None
            return operation

    def abort_audio_stream(
        self,
        request: VoiceInputStreamAbort,
    ) -> VoiceInputStreamOperationResult:
        """Cooperatively abort an active stream without hard-cancel overclaim."""

        with self._input_operation_lock:
            operation = self._streaming_runtime.abort(request)
            if not operation.accepted:
                return operation
            context = self._stream_input_context
            if context is not None and self._input_context_is_current(context):
                self._generation_gate.advance(GenerationAdvanceReason.CANCEL)
                self._last_stream_result = VoiceInputResult.interrupted(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    generation_id=context.generation_id,
                )
                self._active_input_context = None
                self._emit_realtime_event(
                    RealtimeEventType.VOICE_INPUT_FAILED,
                    state=RealtimeState.INTERRUPTED,
                    previous_state=RealtimeState.LISTENING,
                    context=context,
                    payload=LifecycleEventPayload(reason="audio_stream_aborted"),
                    public_error_code=RealtimeErrorCode.INTERRUPTED,
                    safe_message="Audio input stream was interrupted.",
                    retryable=True,
                    public_metadata={
                        "input_mode": "audio_stream",
                        "stream_id": request.stream_id,
                        "provider_hard_cancel_claimed": False,
                        "host_audio_capture_stopped_claimed": False,
                    },
                )
            self._stream_input_context = None
            return operation

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

    def _closed_input_result(self) -> VoiceInputResult:
        """Return the unified post-close rejection without admitting a turn."""

        return VoiceInputResult.closed(session_id=self._session_id)

    @staticmethod
    def _legacy_mapping_from_realtime_event(
        event: RealtimeEvent,
    ) -> Mapping[str, Any] | None:
        """Project selected canonical events to the existing voice-input mapping."""

        input_mode = event.public_metadata.get("input_mode")
        event_type: str | None = None
        payload: Mapping[str, Any] | None = None

        if (
            event.type is RealtimeEventType.VOICE_INPUT_PREFLIGHT
            and input_mode == "listen"
        ):
            event_type = "voice_input.started"
            payload = {"language": event.public_metadata.get("language")}
        elif (
            event.type is RealtimeEventType.VOICE_INPUT_FAILED
            and input_mode == "listen"
        ):
            event_type = "voice_input.unavailable"
            payload = {
                "provider_status": event.public_metadata.get("provider_status"),
                "reason": event.public_metadata.get("reason"),
                "provider": event.public_metadata.get("provider"),
            }
        elif (
            event.type is RealtimeEventType.TRANSCRIPT_FINAL
            and input_mode == "text_fallback"
        ):
            event_type = "voice_input.text_fallback"
            payload = {"language": event.public_metadata.get("language")}
        elif event.type is RealtimeEventType.SESSION_CLOSED:
            event_type = "voice_input.closed"
            payload = {}

        if event_type is None or payload is None:
            return None
        return MappingProxyType(
            {
                "type": event_type,
                "session_type": "voice_input",
                "payload": _public_mapping(payload),
            }
        )

    def abort_input(self) -> bool:
        """Cooperatively invalidate the active input generation once.

        A true result means only that Framework generation invalidation was
        accepted. It does not claim provider hard cancellation or physical
        termination of host audio capture.
        """

        with self._input_operation_lock:
            stream_id = self._streaming_runtime.active_stream_id
            if stream_id is not None:
                return self.abort_audio_stream(
                    VoiceInputStreamAbort(
                        stream_id=stream_id,
                        reason="host_requested",
                    )
                ).accepted
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
        """Emit one canonical event and its explicit legacy mapping projection."""

        if not isinstance(event_type, RealtimeEventType):
            raise TypeError("event_type must be a RealtimeEventType")
        if not isinstance(state, RealtimeState):
            raise TypeError("state must be a RealtimeState")

        with self._realtime_event_lock:
            sequence = self._next_realtime_event_sequence
            self._next_realtime_event_sequence = sequence.next()
            callbacks = (
                self._retired_realtime_event_callbacks
                if self._closed
                and event_type is RealtimeEventType.STALE_RESULT_DROPPED
                else tuple(self._realtime_event_callbacks)
            )

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
        legacy_event = self._legacy_mapping_from_realtime_event(event)
        with self._realtime_event_lock:
            legacy_callbacks = (
                tuple(self._callbacks)
                if legacy_event is not None
                else ()
            )
        self._dispatch_public_callbacks(callbacks, event)
        if legacy_event is not None:
            self._dispatch_public_callbacks(legacy_callbacks, legacy_event)
        return event

    def on_event(self, callback: VoiceInputCallback) -> None:
        """Register an app-facing provider-neutral event callback."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._realtime_event_lock:
            if self._closed:
                raise RuntimeError("Voice input session is closed.")
            self._callbacks.append(callback)

    def _unavailable_from_capability(
        self,
        context: _VoiceInputTurnContext,
    ) -> VoiceInputResult:
        status = self._capabilities.provider_status
        reason = self._capabilities.public_metadata.get("reason", status.value)

        error_code = VoiceInputErrorCode.UNAVAILABLE
        if status is VoiceInputProviderStatus.MISSING_CREDENTIALS:
            error_code = VoiceInputErrorCode.MISSING_CREDENTIALS
        elif status is VoiceInputProviderStatus.UNSUPPORTED_PROVIDER:
            error_code = VoiceInputErrorCode.INVALID_REQUEST

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
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation_id=context.generation_id,
        )

    def listen_result(self, request: VoiceInputRequest | None = None) -> VoiceInputResult:
        """Return a provider-neutral voice-input result.

        Real STT is intentionally not executed in this skeleton. The session
        now uses voice-input capability preflight to return status-specific
        public results.
        """

        if self._closed:
            return self._closed_input_result()

        if request is None:
            request = VoiceInputRequest(language=self._language)

        context = self._new_realtime_turn_context()
        status = self._capabilities.provider_status
        reason = self._capabilities.public_metadata.get("reason", status.value)
        event_metadata = {
            "input_mode": "listen",
            "language": request.language or self._language,
            "provider_status": status.value,
            "reason": reason,
            "provider": self._capabilities.provider,
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

            result = self._unavailable_from_capability(context)
            error_code = RealtimeErrorCode.UNAVAILABLE
            if result.public_error_code is VoiceInputErrorCode.INVALID_REQUEST:
                error_code = RealtimeErrorCode.INVALID_REQUEST
            elif result.public_error_code is VoiceInputErrorCode.MISSING_CREDENTIALS:
                error_code = RealtimeErrorCode.CONFIGURATION_MISSING
            self._emit_realtime_event(
                RealtimeEventType.VOICE_INPUT_FAILED,
                state=RealtimeState.FAILED,
                previous_state=RealtimeState.IDLE,
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

    def text_fallback_result(
        self,
        text: str,
        *,
        language: str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> VoiceInputResult:
        """Return a completed result for app-provided text fallback input."""

        if self._closed:
            return self._closed_input_result()

        context = self._new_realtime_turn_context()
        effective_language = language or self._language
        event_metadata = {
            "input_mode": "text_fallback",
            "language": effective_language,
            "raw_audio_retained": False,
            "audio_path_exposed": False,
        }
        result = VoiceInputResult.completed(
            text,
            language=effective_language,
            public_metadata={
                "boundary": "voice_input",
                "input_mode": "text_fallback",
                **dict(public_metadata or {}),
            },
            session_id=context.session_id,
            turn_id=context.turn_id,
            generation_id=context.generation_id,
        )
        with self._input_operation_lock:
            self._emit_realtime_event(
                RealtimeEventType.VOICE_INPUT_PREFLIGHT,
                state=RealtimeState.IDLE,
                context=context,
                payload=LifecycleEventPayload(reason="text_fallback_preflight"),
                public_metadata=event_metadata,
            )
            if not self._input_context_is_current(context):
                return VoiceInputResult.interrupted(
                    session_id=context.session_id,
                    turn_id=context.turn_id,
                    generation_id=context.generation_id,
                )
            applied_results: list[object] = []
            decision = self._apply_input_completion(
                context=context,
                value=result,
                deliver=applied_results.append,
            )
            if not decision.accepted:
                self._emit_stale_input_completion(
                    context=context,
                    decision=decision,
                )
                return self._stale_input_result(context)
            result = applied_results[0]
            if not isinstance(result, VoiceInputResult):
                raise AssertionError("voice input delivery must retain its result")
            self._emit_realtime_event(
                RealtimeEventType.TRANSCRIPT_FINAL,
                state=RealtimeState.TRANSCRIBING,
                previous_state=RealtimeState.IDLE,
                context=context,
                payload=TranscriptEventPayload(text=result.text, is_final=True),
                public_metadata=event_metadata,
            )
            self._finish_input_context(context)
            return result

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
            return self._closed_input_result()

        if not isinstance(audio_source, VoiceInputAudioSource):
            raise TypeError("audio_source must be a VoiceInputAudioSource")

        effective_request = request or VoiceInputRequest(
            language=audio_source.language,
            max_duration_ms=audio_source.max_duration_ms,
        )
        context = self._new_realtime_turn_context()
        event_metadata = {
            "input_mode": "host_audio",
            "language": effective_request.language or audio_source.language or self._language,
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
            from .callback_isolation import criticality_for_stage, stage_failure_policy

            failure_policy = stage_failure_policy(
                criticality_for_stage("voice_input")
            )
            with self._input_operation_lock:
                decision = self._apply_input_completion(
                    context=context,
                    value=None,
                    deliver=lambda _value: None,
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
                    public_metadata={
                        **event_metadata,
                        "stage_criticality": failure_policy.criticality.value,
                        "failure_action": failure_policy.failure_action.value,
                    },
                )
                self._finish_input_context(context)
            raise

        with self._input_operation_lock:
            if result.is_completed:
                if not self._closed:
                    self._emit_realtime_event(
                        RealtimeEventType.LISTENING_COMPLETED,
                        state=RealtimeState.TRANSCRIBING,
                        previous_state=RealtimeState.LISTENING,
                        context=context,
                        payload=LifecycleEventPayload(reason="voice_input_completed"),
                        public_metadata=event_metadata,
                    )
                applied_results: list[object] = []
                decision = self._apply_input_completion(
                    context=context,
                    value=result,
                    deliver=applied_results.append,
                )
                if not decision.accepted:
                    self._emit_stale_input_completion(
                        context=context,
                        decision=decision,
                    )
                    return self._stale_input_result(context)
                applied_result = applied_results[0]
                if not isinstance(applied_result, VoiceInputResult):
                    raise AssertionError("voice input delivery must retain its result")
                self._emit_realtime_event(
                    RealtimeEventType.TRANSCRIPT_FINAL,
                    state=RealtimeState.TRANSCRIBING,
                    context=context,
                    payload=TranscriptEventPayload(
                        text=applied_result.text,
                        is_final=True,
                        confidence=applied_result.confidence,
                    ),
                    public_metadata=event_metadata,
                )
                self._finish_input_context(context)
                return applied_result

            applied_results = []
            decision = self._apply_input_completion(
                context=context,
                value=result,
                deliver=applied_results.append,
            )
            if not decision.accepted:
                self._emit_stale_input_completion(
                    context=context,
                    decision=decision,
                )
                return self._stale_input_result(context)
            applied_result = applied_results[0]
            if not isinstance(applied_result, VoiceInputResult):
                raise AssertionError("voice input delivery must retain its result")
            result = applied_result

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
        from .session_close import (
            SessionCleanupResult,
            SessionCleanupTarget,
            SessionCloseResult,
            _runtime_close_result,
            build_session_close_plan,
        )

        with self._input_operation_lock:
            if self._closed:
                self._last_close_result = SessionCloseResult.already_closed(
                    public_metadata={"boundary": "voice_input"}
                )
                return
            context = self._active_input_context
            plan = build_session_close_plan(
                active_turn_terminal_required=context is not None,
                callback_hub_close_required=True,
                public_metadata={"boundary": "voice_input"},
            )
            self._closed = True
            self._streaming_runtime.close()
            if self._stream_input_context is not None:
                self._last_stream_result = VoiceInputResult.closed(
                    session_id=self._stream_input_context.session_id,
                    turn_id=self._stream_input_context.turn_id,
                    generation_id=self._stream_input_context.generation_id,
                )
            self._stream_input_context = None
            self._generation_gate.advance(GenerationAdvanceReason.SESSION_CLOSED)
            self._active_input_context = None
            callback_result = SessionCleanupResult.completed(
                SessionCleanupTarget.CALLBACK_HUB
            )
            callback_failures_before = self._callback_failure_count
            try:
                self._emit_realtime_event(
                    RealtimeEventType.SESSION_CLOSED,
                    state=RealtimeState.CLOSED,
                    previous_state=(
                        RealtimeState.LISTENING
                        if context is not None
                        else RealtimeState.IDLE
                    ),
                    context=context,
                    payload=LifecycleEventPayload(reason="session_closed"),
                    public_error_code=RealtimeErrorCode.SESSION_CLOSED,
                    safe_message="Voice input session is closed.",
                    public_metadata={"input_mode": "session"},
                )
            except Exception:
                callback_result = SessionCleanupResult.failed_result(
                    SessionCleanupTarget.CALLBACK_HUB,
                    safe_message="Voice input callback cleanup failed.",
                )
            finally:
                with self._realtime_event_lock:
                    callback_failed = (
                        self._callback_failure_count > callback_failures_before
                    )
                    self._retired_realtime_event_callbacks = tuple(
                        self._realtime_event_callbacks
                    )
                    self._realtime_event_callbacks.clear()
                    self._callbacks.clear()
                if callback_failed:
                    callback_result = SessionCleanupResult.failed_result(
                        SessionCleanupTarget.CALLBACK_HUB,
                        safe_message="Voice input callback cleanup failed.",
                    )
            first_result = _runtime_close_result(
                plan,
                observed={
                    SessionCleanupTarget.ACTIVE_TURN: (
                        SessionCleanupResult.completed(
                            SessionCleanupTarget.ACTIVE_TURN
                        )
                        if context is not None
                        else SessionCleanupResult.not_required(
                            SessionCleanupTarget.ACTIVE_TURN
                        )
                    ),
                    SessionCleanupTarget.CALLBACK_HUB: callback_result,
                },
                active_turn_terminalized=context is not None,
                public_metadata={"boundary": "voice_input"},
            )
            if self._last_close_result is None:
                self._last_close_result = first_result

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
