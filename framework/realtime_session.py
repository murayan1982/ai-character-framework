"""Public realtime session skeleton.

This module provides a mock-safe public realtime lifecycle / event boundary. It
intentionally does not execute real STT, LLM, TTS, motion, Live2D, VTube Studio,
websocket, microphone, or provider SDK code.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
import time
from types import MappingProxyType
from typing import Any, Callable, Iterator, Mapping

from .capabilities import _session_realtime_snapshot
from .identity import EventSequence, GenerationId, SessionId, TurnId
from .lifecycle import (
    LifecycleTransitionError,
    LifecycleTransitionErrorCode,
    RealtimePhase,
    RecoveryAction,
    TurnOutcome,
    validate_phase_transition,
)

from .output_control import (
    BargeInDecision,
    BargeInPolicy,
    BargeInPolicyMode,
    InterruptReason,
    InterruptRequest,
    InterruptResult,
    InterruptScope,
    OutputFlushRequest,
    OutputFlushResult,
    TTSQueueState,
)
from .version import REALTIME_API_VERSION

from .realtime_capabilities import RealtimeCapabilitySnapshot
from .realtime_event_hub import RealtimeEventHub
from .realtime_terminal_registry import (
    RealtimeTerminalRegistry,
    TerminalCommitDecision,
)
from .realtime_event_payloads import (
    DiagnosticEventPayload,
    InterruptEventPayload,
    LifecycleEventPayload,
    RealtimeEventPayload,
    ResponseEventPayload,
    SynthesisEventPayload,
    TranscriptEventPayload,
)
from .realtime import (
    RealtimeErrorCode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeState,
    RealtimeTurn,
    RealtimeTurnResult,
    _normalize_realtime_phase,
    _public_mapping,
    _require_runtime_event_payload,
)


RealtimeEventCallback = Callable[[RealtimeEvent], None]
_PHASE_UNCHANGED = object()


@dataclass(frozen=True)
class RealtimeSessionInfo:
    """App-safe metadata for a public realtime session."""

    api_version: str = REALTIME_API_VERSION
    session_type: str = "realtime"
    session_id: SessionId | str = field(default_factory=SessionId.new)
    state: RealtimeState | str = RealtimeState.IDLE
    supports_events: bool = True
    supports_run_turn: bool = True
    supports_voice_input: bool = True
    supports_text_chat: bool = True
    supports_voice_output: bool = True
    supports_motion: bool = False
    supports_interrupt: bool = True
    supports_output_flush: bool = True
    supports_barge_in_policy: bool = True
    supports_close: bool = True
    real_runtime_enabled: bool = False
    hard_cancel_supported: bool = False
    tts_queue_flush_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)
    phase: RealtimePhase | str | None = None

    def __post_init__(self) -> None:
        state = self.state if isinstance(self.state, RealtimeState) else RealtimeState(str(self.state))
        phase = _normalize_realtime_phase(self.phase, legacy_state=state)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


class RealtimeSession:
    """Mock-safe public realtime session skeleton.

    The session exposes unified lifecycle, events, turn results, output-control
    methods, and cleanup semantics before real runtime orchestration is
    implemented.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        public_metadata: Mapping[str, Any] | None = None,
        real_runtime_enabled: bool | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._session_id = SessionId.new()
        self._state = RealtimeState.IDLE
        self._phase: RealtimePhase | None = RealtimePhase.IDLE
        self._closed = False
        self._close_requested = False
        self._operation_lock = RLock()
        self._operation_depth = 0
        self._event_hub = RealtimeEventHub[RealtimeEvent]()
        self._terminal_registry = RealtimeTerminalRegistry[RealtimeTurnResult]()
        self._real_runtime_requested = bool(real_runtime_enabled)
        self._capability_snapshot = _session_realtime_snapshot(
            session_id=self._session_id,
            snapshot_generation=1,
            project_root=self._project_root,
            real_runtime_requested=self._real_runtime_requested,
        )
        self._real_runtime_enabled = self._capability_snapshot.real_runtime_enabled
        self._public_metadata = _public_mapping(public_metadata)
        self._barge_in_policy = BargeInPolicy.disabled()
        self._active_turn_id: TurnId | str | None = None
        self._active_generation_id: GenerationId | None = None
        self._info = RealtimeSessionInfo(
            session_id=self._session_id,
            state=self._state,
            phase=self._phase,
            real_runtime_enabled=self._real_runtime_enabled,
            public_metadata={
                "boundary": "realtime",
                "capability_snapshot_scope": self._capability_snapshot.snapshot_scope.value,
                "capability_snapshot_generation": self._capability_snapshot.snapshot_generation,
                "real_runtime_requested": self._real_runtime_requested,
                **dict(public_metadata or {}),
            },
        )

    @property
    def info(self) -> RealtimeSessionInfo:
        return RealtimeSessionInfo(
            session_id=self._session_id,
            state=self._state,
            phase=self._phase,
            real_runtime_enabled=self._real_runtime_enabled,
            public_metadata={
                "boundary": "realtime",
                "barge_in_policy": self._barge_in_policy.mode.value,
                "capability_snapshot_scope": self._capability_snapshot.snapshot_scope.value,
                "capability_snapshot_generation": self._capability_snapshot.snapshot_generation,
                "real_runtime_requested": self._real_runtime_requested,
                **dict(self._public_metadata),
            },
        )

    @property
    def capabilities(self) -> RealtimeCapabilitySnapshot:
        """Return this session's immutable truthful capability snapshot."""

        return self._capability_snapshot

    @property
    def state(self) -> RealtimeState:
        return self._state

    @property
    def phase(self) -> RealtimePhase | None:
        return self._phase

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def barge_in_policy(self) -> BargeInPolicy:
        return self._barge_in_policy

    @property
    def event_history(self) -> tuple[RealtimeEvent, ...]:
        """Return the immutable bounded canonical event-history snapshot."""

        return self._event_hub.event_history

    @property
    def event_diagnostics(self) -> Mapping[str, int]:
        """Return immutable public-safe event-hub counters."""

        diagnostics = self._event_hub.diagnostics
        return MappingProxyType(
            {
                "emitted_event_count": diagnostics.emitted_event_count,
                "callback_error_count": diagnostics.callback_error_count,
                "slow_callback_count": diagnostics.slow_callback_count,
                "history_overflow_count": diagnostics.history_overflow_count,
                "rejected_after_close_count": diagnostics.rejected_after_close_count,
                "subscriber_count": self._event_hub.subscriber_count,
                "history_limit": self._event_hub.history_limit,
            }
        )

    @property
    def terminal_results(self) -> tuple[RealtimeTurnResult, ...]:
        """Return first-terminal results in atomic commit order."""

        return tuple(
            record.result
            for record in self._terminal_registry.records
            if record.result is not None
        )

    @property
    def terminal_diagnostics(self) -> Mapping[str, int]:
        """Return immutable count-only terminal registry diagnostics."""

        diagnostics = self._terminal_registry.diagnostics
        return MappingProxyType(
            {
                "terminal_commit_count": diagnostics.terminal_commit_count,
                "duplicate_terminal_count": diagnostics.duplicate_terminal_count,
                "terminal_regression_count": diagnostics.terminal_regression_count,
                "late_non_terminal_count": diagnostics.late_non_terminal_count,
                "registry_size": diagnostics.registry_size,
            }
        )

    def _session_closed_error(self) -> LifecycleTransitionError:
        return LifecycleTransitionError(
            LifecycleTransitionErrorCode.SESSION_CLOSED,
            from_phase=self._phase,
            to_phase=None,
        )

    def _duplicate_terminal_result(
        self,
        turn_id: TurnId | str,
    ) -> RealtimeTurnResult | None:
        """Return and account for an already committed terminal result."""

        existing = self._terminal_registry.get(turn_id)
        if existing is None:
            return None
        decision = self._terminal_registry.commit(
            turn_id,
            existing.outcome,
            recovery_action=existing.recovery_action,
            reason=existing.reason,
            result=existing.result,
        )
        if decision.accepted:
            raise AssertionError("existing terminal record was recommitted")
        result = decision.record.result
        if result is None:
            raise AssertionError("session terminal record must retain its result")
        return result

    def _commit_terminal_result(
        self,
        result: RealtimeTurnResult,
        *,
        event_type: RealtimeEventType,
        new_state: RealtimeState,
        reason: str,
    ) -> RealtimeTurnResult:
        """Commit one terminal result and let only the first owner emit."""

        decision: TerminalCommitDecision[RealtimeTurnResult] = (
            self._terminal_registry.commit(
                result.turn_id,
                result.outcome,
                recovery_action=result.recovery_action,
                reason=reason,
                result=result,
            )
        )
        if decision.accepted:
            self._transition(
                event_type,
                new_state,
                turn_id=result.turn_id,
                payload=LifecycleEventPayload(
                    outcome=decision.record.outcome,
                    recovery_action=decision.record.recovery_action,
                    reason=decision.record.reason,
                ),
            )
        committed = decision.record.result
        if committed is None:
            raise AssertionError("session terminal record must retain its result")
        return committed

    @contextmanager
    def _serialized_operation(self) -> Iterator[None]:
        """Serialize one public event-producing operation and honor deferred close."""

        with self._operation_lock:
            self._operation_depth += 1
            try:
                yield
            finally:
                self._operation_depth -= 1
                if (
                    self._operation_depth == 0
                    and self._close_requested
                    and not self._closed
                ):
                    self._close_now()

    def on_event(self, callback: RealtimeEventCallback) -> str:
        """Register a canonical callback and return its opaque removal token."""

        with self._operation_lock:
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return str(self._event_hub.subscribe(callback))

    def on_legacy_event(self, callback: RealtimeEventCallback) -> str:
        """Register a mapped v5 callback and return its opaque removal token."""

        with self._operation_lock:
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return str(self._event_hub.subscribe(callback, legacy=True))

    def off_event(self, token: str) -> bool:
        """Remove a canonical or legacy callback token idempotently."""

        with self._operation_lock:
            return self._event_hub.unsubscribe(token)

    def _generation_for_event(
        self,
        turn_id: TurnId | str | None,
    ) -> GenerationId | None:
        if (
            turn_id is None
            or self._active_turn_id is None
            or self._active_generation_id is None
            or turn_id != self._active_turn_id
        ):
            return None
        return self._active_generation_id

    def _build_event_overflow(
        self,
        *,
        sequence: EventSequence,
        dropped_sequence: EventSequence | None,
        overflow_count: int,
        state: RealtimeState,
        turn_id: TurnId | str | None,
        generation_id: GenerationId | None,
        phase: RealtimePhase | None,
    ) -> RealtimeEvent:
        """Build one typed diagnostic without creating a lifecycle transition."""

        return RealtimeEvent(
            type=RealtimeEventType.EVENT_OVERFLOW,
            state=state,
            previous_state=state,
            turn_id=turn_id,
            session_id=self._session_id,
            boundary="realtime",
            safe_message="Realtime event history overflowed.",
            public_metadata={
                "boundary": "realtime",
                "history_limit": self._event_hub.history_limit,
            },
            sequence=sequence,
            generation_id=generation_id,
            phase=phase,
            payload=DiagnosticEventPayload(
                code="event_history_overflow",
                drop_reason="bounded_history_capacity",
                dropped_sequence=dropped_sequence,
                overflow_count=overflow_count,
            ),
            timestamp=time.time(),
            monotonic_timestamp=time.monotonic(),
        )

    def _set_phase(
        self,
        next_phase: RealtimePhase | str | None,
    ) -> RealtimePhase | None:
        if next_phase is None:
            self._phase = None
            return None
        resolved_next = (
            next_phase
            if isinstance(next_phase, RealtimePhase)
            else RealtimePhase(str(next_phase))
        )
        if self._closed or self._phase is None:
            raise LifecycleTransitionError(
                LifecycleTransitionErrorCode.SESSION_CLOSED,
                from_phase=self._phase,
                to_phase=resolved_next,
            )
        self._phase = validate_phase_transition(self._phase, resolved_next)
        return self._phase

    def _transition(
        self,
        event_type: RealtimeEventType,
        new_state: RealtimeState,
        *,
        turn_id: TurnId | str | None = None,
        new_phase: RealtimePhase | str | None | object = _PHASE_UNCHANGED,
        payload: RealtimeEventPayload | None = None,
        public_error_code: RealtimeErrorCode = RealtimeErrorCode.NONE,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
        _allow_closed_event: bool = False,
    ) -> RealtimeEvent:
        if self._closed and not _allow_closed_event:
            raise self._session_closed_error()
        if new_phase is not _PHASE_UNCHANGED:
            self._set_phase(new_phase)
        resolved_payload = _require_runtime_event_payload(event_type, payload)
        previous_state = self._state
        self._state = new_state
        generation_id = self._generation_for_event(turn_id)
        phase = self._phase
        metadata = {
            "boundary": "realtime",
            **dict(public_metadata or {}),
        }

        def event_factory(sequence: EventSequence) -> RealtimeEvent:
            return RealtimeEvent(
                type=event_type,
                state=new_state,
                previous_state=previous_state,
                turn_id=turn_id,
                session_id=self._session_id,
                boundary="realtime",
                public_error_code=public_error_code,
                safe_message=safe_message,
                retryable=retryable,
                public_metadata=metadata,
                sequence=sequence,
                generation_id=generation_id,
                phase=phase,
                payload=resolved_payload,
                timestamp=time.time(),
                monotonic_timestamp=time.monotonic(),
            )

        def overflow_event_factory(
            sequence: EventSequence,
            dropped_sequence: EventSequence | None,
            overflow_count: int,
        ) -> RealtimeEvent:
            return self._build_event_overflow(
                sequence=sequence,
                dropped_sequence=dropped_sequence,
                overflow_count=overflow_count,
                state=new_state,
                turn_id=turn_id,
                generation_id=generation_id,
                phase=phase,
            )

        return self._event_hub.emit(
            event_factory,
            legacy_projector=lambda emitted: emitted.to_v5(),
            overflow_event_factory=overflow_event_factory,
        )

    def emit_created(self) -> RealtimeEvent:
        """Emit a public session-created event."""

        with self._serialized_operation():
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return self._emit_created_serialized()

    def _emit_created_serialized(self) -> RealtimeEvent:
        return self._transition(
            RealtimeEventType.SESSION_STARTED,
            RealtimeState.IDLE,
            new_phase=RealtimePhase.IDLE,
            payload=LifecycleEventPayload(reason="session_started"),
            public_metadata={"reason": "session_started"},
        )

    def run_turn(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeTurnResult:
        with self._serialized_operation():
            return self._run_turn_serialized(
                turn,
                input_text=input_text,
                public_metadata=public_metadata,
            )

    def _run_turn_serialized(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeTurnResult:
        """Run a mock-safe public realtime turn.

        This skeleton intentionally does not execute real STT, LLM, TTS, or
        motion stages. It emits stable public lifecycle events and returns a
        completed provider-neutral result.
        """

        if turn is None:
            turn = RealtimeTurn(input_text=input_text, session_id=self._session_id, public_metadata=public_metadata or {})
        elif turn.session_id is None:
            turn = RealtimeTurn(
                turn_id=turn.turn_id,
                input_text=turn.input_text,
                state=turn.state,
                session_id=self._session_id,
                public_metadata=turn.public_metadata,
                phase=turn.phase,
            )

        if self._closed or self._close_requested:
            return RealtimeTurnResult.closed(turn_id=turn.turn_id)

        existing_terminal = self._duplicate_terminal_result(turn.turn_id)
        if existing_terminal is not None:
            return existing_terminal

        self._active_turn_id = turn.turn_id
        self._active_generation_id = GenerationId.new()
        transcript_text = turn.input_text or input_text
        self._transition(
            RealtimeEventType.TURN_STARTED,
            RealtimeState.LISTENING,
            turn_id=turn.turn_id,
            new_phase=RealtimePhase.LISTENING,
            payload=LifecycleEventPayload(reason="turn_admitted"),
        )
        self._transition(
            RealtimeEventType.LISTENING_STARTED,
            RealtimeState.LISTENING,
            turn_id=turn.turn_id,
            new_phase=RealtimePhase.LISTENING,
            payload=LifecycleEventPayload(reason="listening_started"),
        )
        self._transition(
            RealtimeEventType.LISTENING_COMPLETED,
            RealtimeState.TRANSCRIBING,
            turn_id=turn.turn_id,
            new_phase=RealtimePhase.TRANSCRIBING,
            payload=LifecycleEventPayload(reason="listening_completed"),
            public_metadata={"mock_stage": "voice_input"},
        )
        self._transition(
            RealtimeEventType.TRANSCRIPT_FINAL,
            RealtimeState.TRANSCRIBING,
            turn_id=turn.turn_id,
            payload=TranscriptEventPayload(
                text=transcript_text,
                is_final=True,
            ),
            public_metadata={"mock_stage": "transcript"},
        )
        self._transition(
            RealtimeEventType.RESPONSE_STARTED,
            RealtimeState.THINKING,
            turn_id=turn.turn_id,
            new_phase=RealtimePhase.THINKING,
            payload=ResponseEventPayload(text="", is_final=False),
        )
        self._transition(
            RealtimeEventType.RESPONSE_COMPLETED,
            RealtimeState.THINKING,
            turn_id=turn.turn_id,
            payload=ResponseEventPayload(text="", is_final=True),
            public_metadata={"mock_stage": "text_chat"},
        )
        self._transition(
            RealtimeEventType.SYNTHESIS_STARTED,
            RealtimeState.SPEAKING,
            turn_id=turn.turn_id,
            new_phase=RealtimePhase.SPEAKING,
            payload=SynthesisEventPayload(request_state="started"),
        )
        self._transition(
            RealtimeEventType.SYNTHESIS_COMPLETED,
            RealtimeState.COMPLETED,
            turn_id=turn.turn_id,
            payload=SynthesisEventPayload(request_state="completed"),
            public_metadata={"mock_stage": "voice_output"},
        )
        result = RealtimeTurnResult.completed(
            turn_id=turn.turn_id,
            input_text=turn.input_text or input_text,
            output_text="",
            public_metadata={
                "boundary": "realtime",
                "mock_runtime": True,
                **dict(public_metadata or {}),
            },
        )
        committed_result = self._commit_terminal_result(
            result,
            event_type=RealtimeEventType.TURN_COMPLETED,
            new_state=RealtimeState.COMPLETED,
            reason="mock_turn_completed",
        )

        self._active_turn_id = None
        self._active_generation_id = None
        # A completed turn returns the session to idle for the next host-app
        # interaction, without emitting another event.
        self._set_phase(RealtimePhase.IDLE)
        self._state = RealtimeState.IDLE

        return committed_result

    def get_tts_queue_state(self) -> TTSQueueState:
        """Return a mock-safe public TTS queue snapshot."""

        return TTSQueueState(
            queued_count=0,
            is_playing=False,
            supports_flush=False,
            supports_provider_cancel=False,
            playback_stop_required=False,
            safe_message="No public TTS queue is active in the mock realtime session.",
            public_metadata={
                "boundary": "tts_queue",
                "reason": "mock_queue_empty",
            },
        )

    def interrupt(self, request: InterruptRequest | None = None) -> InterruptResult:
        with self._serialized_operation():
            return self._interrupt_serialized(request)

    def _interrupt_serialized(
        self,
        request: InterruptRequest | None = None,
    ) -> InterruptResult:
        """Request a provider-neutral interrupt.

        Real hard cancellation is not implemented yet. This method provides a
        stable public result and emits public realtime events without touching
        provider internals.
        """

        request = request or InterruptRequest()
        if self._closed or self._close_requested:
            return InterruptResult.already_closed(request=request)

        no_active_turn = self._active_turn_id is None and request.turn_id is None
        result = (
            InterruptResult.no_active_turn(request=request)
            if no_active_turn
            else InterruptResult.not_implemented(request=request)
        )
        self._transition(
            RealtimeEventType.INTERRUPT_REQUESTED,
            self._state,
            turn_id=request.turn_id or self._active_turn_id,
            payload=InterruptEventPayload(
                scope=request.scope,
                outcome=result.outcome,
                reason=request.reason.value,
            ),
            public_metadata={
                "scope": request.scope.value,
                "reason": request.reason.value,
            },
        )

        if no_active_turn:
            self._transition(
                RealtimeEventType.INTERRUPT_UNSUPPORTED,
                self._state,
                payload=InterruptEventPayload(
                    scope=request.scope,
                    outcome=result.outcome,
                    reason=request.reason.value,
                ),
                public_error_code=RealtimeErrorCode.UNSUPPORTED,
                safe_message=result.safe_message,
                public_metadata={
                    "scope": request.scope.value,
                    "reason": request.reason.value,
                    "interrupt_outcome": result.outcome.value,
                },
            )
            return result

        next_phase = (
            RealtimePhase.RECOVERING
            if self._active_turn_id is not None
            else _PHASE_UNCHANGED
        )
        self._transition(
            RealtimeEventType.INTERRUPT_UNSUPPORTED,
            RealtimeState.INTERRUPTED,
            turn_id=request.turn_id or self._active_turn_id,
            new_phase=next_phase,
            payload=InterruptEventPayload(
                scope=request.scope,
                outcome=result.outcome,
                reason=request.reason.value,
            ),
            public_error_code=RealtimeErrorCode.UNSUPPORTED,
            safe_message=result.safe_message,
            public_metadata={
                "scope": request.scope.value,
                "reason": request.reason.value,
                "interrupt_outcome": result.outcome.value,
            },
        )
        self._set_phase(RealtimePhase.IDLE)
        self._state = RealtimeState.IDLE
        return result

    def cancel_current_turn(
        self,
        *,
        reason: InterruptReason | str = InterruptReason.HOST_APP_REQUEST,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> InterruptResult:
        """Request cancellation of the current realtime turn."""

        request = InterruptRequest(
            scope=InterruptScope.CURRENT_TURN,
            reason=reason,
            turn_id=self._active_turn_id,
            cancel_llm_stream=True,
            cancel_tts_queue=True,
            public_metadata=public_metadata or {},
        )
        return self.interrupt(request)

    def flush_output(self, request: OutputFlushRequest | None = None) -> OutputFlushResult:
        with self._serialized_operation():
            return self._flush_output_serialized(request)

    def _flush_output_serialized(
        self,
        request: OutputFlushRequest | None = None,
    ) -> OutputFlushResult:
        """Request a provider-neutral output flush.

        Real queue flush / playback stop is not implemented yet. Empty mock queue
        and closed-session cases are represented as typed public results.
        """

        request = request or OutputFlushRequest()
        if self._closed or self._close_requested:
            return OutputFlushResult.closed(request=request)

        self._transition(
            RealtimeEventType.OUTPUT_FLUSH_REQUESTED,
            self._state,
            turn_id=request.turn_id or self._active_turn_id,
            public_metadata={
                "scope": request.scope.value,
                "stop_playback": request.stop_playback,
                "clear_queued_audio": request.clear_queued_audio,
            },
        )

        queue_state = self.get_tts_queue_state()
        if queue_state.queued_count == 0 and not queue_state.is_playing:
            result = OutputFlushResult.nothing_to_flush(request=request)
            self._transition(
                RealtimeEventType.OUTPUT_FLUSH_COMPLETED,
                self._state,
                turn_id=request.turn_id or self._active_turn_id,
                safe_message=result.safe_message,
                public_metadata={
                    "flush_outcome": result.outcome.value,
                    "queued_count": queue_state.queued_count,
                },
            )
            return result

        result = OutputFlushResult.not_implemented(request=request)
        self._transition(
            RealtimeEventType.OUTPUT_FLUSH_UNSUPPORTED,
            self._state,
            turn_id=request.turn_id or self._active_turn_id,
            public_error_code=RealtimeErrorCode.UNSUPPORTED,
            safe_message=result.safe_message,
            public_metadata={
                "flush_outcome": result.outcome.value,
                "queued_count": queue_state.queued_count,
            },
        )
        return result

    def set_barge_in_policy(self, policy: BargeInPolicy) -> BargeInPolicy:
        """Set the public barge-in policy for future host-app decisions."""

        with self._serialized_operation():
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            if not isinstance(policy, BargeInPolicy):
                raise TypeError("policy must be a BargeInPolicy")
            self._barge_in_policy = policy
            return self._barge_in_policy

    def decide_barge_in(
        self,
        *,
        turn_id: TurnId | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> BargeInDecision:
        with self._serialized_operation():
            if self._closed or self._close_requested:
                return BargeInDecision.rejected(policy=self._barge_in_policy)
            return self._decide_barge_in_serialized(
                turn_id=turn_id,
                public_metadata=public_metadata,
            )

    def _decide_barge_in_serialized(
        self,
        *,
        turn_id: TurnId | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> BargeInDecision:
        """Return a provider-neutral public barge-in decision."""

        self._transition(
            RealtimeEventType.BARGE_IN_DETECTED,
            self._state,
            turn_id=turn_id or self._active_turn_id,
            payload=InterruptEventPayload(
                scope=InterruptScope.ALL,
                outcome=(
                    "unsupported"
                    if self._barge_in_policy.mode is BargeInPolicyMode.DISABLED
                    else "accepted"
                ),
                reason="barge_in_detected",
            ),
            public_metadata={
                "policy_mode": self._barge_in_policy.mode.value,
                **dict(public_metadata or {}),
            },
        )

        if self._barge_in_policy.mode is BargeInPolicyMode.DISABLED:
            decision = BargeInDecision.rejected(policy=self._barge_in_policy)
            self._transition(
                RealtimeEventType.BARGE_IN_REJECTED,
                self._state,
                turn_id=turn_id or self._active_turn_id,
                payload=InterruptEventPayload(
                    scope=InterruptScope.ALL,
                    outcome="unsupported",
                    reason="barge_in_rejected",
                ),
                safe_message=decision.safe_message,
                public_metadata={"policy_mode": self._barge_in_policy.mode.value},
            )
            return decision

        decision = BargeInDecision.accepted_for_policy(
            self._barge_in_policy,
            turn_id=turn_id or self._active_turn_id,
            public_metadata=public_metadata or {},
        )
        self._transition(
            RealtimeEventType.BARGE_IN_ACCEPTED,
            self._state,
            turn_id=turn_id or self._active_turn_id,
            payload=InterruptEventPayload(
                scope=InterruptScope.ALL,
                outcome="accepted",
                reason="barge_in_accepted",
            ),
            safe_message=decision.safe_message,
            public_metadata={
                "policy_mode": self._barge_in_policy.mode.value,
                "should_flush_queue": decision.should_flush_queue,
                "should_cancel_current_turn": decision.should_cancel_current_turn,
            },
        )
        return decision

    def close(self) -> None:
        with self._operation_lock:
            if self._closed or self._close_requested:
                return
            if self._operation_depth > 0:
                self._close_requested = True
                return
            self._close_now()

    def _close_now(self) -> None:
        if self._closed:
            return
        self._close_requested = False
        self._closed = True
        self._active_turn_id = None
        self._active_generation_id = None
        self._phase = None
        try:
            self._transition(
                RealtimeEventType.SESSION_CLOSED,
                RealtimeState.CLOSED,
                payload=LifecycleEventPayload(
                    outcome=TurnOutcome.CLOSED,
                    recovery_action=RecoveryAction.NONE,
                    reason="session_closed",
                ),
                public_metadata={"reason": "session_closed"},
                _allow_closed_event=True,
            )
        finally:
            self._event_hub.close()

    def dispose(self) -> None:
        self.close()

    def __enter__(self) -> "RealtimeSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def create_realtime_session(
    *,
    project_root: str | Path | None = None,
    public_metadata: Mapping[str, Any] | None = None,
    real_runtime_enabled: bool | None = None,
) -> RealtimeSession:
    """Create a mock-safe public realtime session.

    Real provider orchestration is not performed by this skeleton.
    """

    return RealtimeSession(
        project_root=project_root,
        public_metadata=public_metadata,
        real_runtime_enabled=real_runtime_enabled,
    )
