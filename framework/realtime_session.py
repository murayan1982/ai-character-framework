"""Public realtime session skeleton.

This module provides a mock-safe public realtime lifecycle / event boundary. It
intentionally does not execute real STT, LLM, TTS, motion, Live2D, VTube Studio,
websocket, microphone, or provider SDK code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any, Callable, Mapping

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

from .realtime_event_payloads import (
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
        self._callbacks: list[RealtimeEventCallback] = []
        self._legacy_callbacks: list[RealtimeEventCallback] = []
        self._next_event_sequence = EventSequence.first()
        self._real_runtime_enabled = bool(real_runtime_enabled)
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
                **dict(self._public_metadata),
            },
        )

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

    def on_event(self, callback: RealtimeEventCallback) -> None:
        """Register a canonical ordered realtime event callback."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callbacks.append(callback)

    def on_legacy_event(self, callback: RealtimeEventCallback) -> None:
        """Register a mapped v5 event callback for compatibility consumers."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        self._legacy_callbacks.append(callback)

    def _allocate_event_sequence(self) -> EventSequence:
        sequence = self._next_event_sequence
        self._next_event_sequence = sequence.next()
        return sequence

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
    ) -> RealtimeEvent:
        if new_phase is not _PHASE_UNCHANGED:
            self._set_phase(new_phase)
        resolved_payload = _require_runtime_event_payload(event_type, payload)
        previous_state = self._state
        self._state = new_state
        event = RealtimeEvent(
            type=event_type,
            state=new_state,
            previous_state=previous_state,
            turn_id=turn_id,
            session_id=self._session_id,
            boundary="realtime",
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata={
                "boundary": "realtime",
                **dict(public_metadata or {}),
            },
            sequence=self._allocate_event_sequence(),
            generation_id=self._generation_for_event(turn_id),
            phase=self._phase,
            payload=resolved_payload,
            timestamp=time.time(),
            monotonic_timestamp=time.monotonic(),
        )
        for callback in list(self._callbacks):
            callback(event)
        legacy_event = event.to_v5()
        if legacy_event is not None:
            for callback in list(self._legacy_callbacks):
                callback(legacy_event)
        return event

    def emit_created(self) -> RealtimeEvent:
        """Emit a public session-created event."""

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

        if self._closed:
            self._transition(
                RealtimeEventType.TURN_REJECTED,
                RealtimeState.CLOSED,
                turn_id=turn.turn_id,
                payload=LifecycleEventPayload(
                    outcome=TurnOutcome.REJECTED,
                    recovery_action=RecoveryAction.NONE,
                    reason="session_closed",
                ),
                public_error_code=RealtimeErrorCode.SESSION_CLOSED,
                safe_message="Realtime session is closed.",
            )
            return RealtimeTurnResult.closed(turn_id=turn.turn_id)

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
        self._transition(
            RealtimeEventType.TURN_COMPLETED,
            RealtimeState.COMPLETED,
            turn_id=turn.turn_id,
            payload=LifecycleEventPayload(
                outcome=TurnOutcome.COMPLETED,
                recovery_action=RecoveryAction.NONE,
                reason="mock_turn_completed",
            ),
        )

        self._active_turn_id = None
        self._active_generation_id = None
        # A completed turn returns the session to idle for the next host-app
        # interaction, without emitting another event.
        self._set_phase(RealtimePhase.IDLE)
        self._state = RealtimeState.IDLE

        return RealtimeTurnResult.completed(
            turn_id=turn.turn_id,
            input_text=turn.input_text or input_text,
            output_text="",
            public_metadata={
                "boundary": "realtime",
                "mock_runtime": True,
                **dict(public_metadata or {}),
            },
        )

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
        """Request a provider-neutral interrupt.

        Real hard cancellation is not implemented yet. This method provides a
        stable public result and emits public realtime events without touching
        provider internals.
        """

        request = request or InterruptRequest()
        if self._closed:
            result = InterruptResult.already_closed(request=request)
            self._transition(
                RealtimeEventType.INTERRUPT_UNSUPPORTED,
                RealtimeState.CLOSED,
                turn_id=request.turn_id,
                payload=InterruptEventPayload(
                    scope=request.scope,
                    outcome=result.outcome,
                    reason=request.reason.value,
                ),
                public_error_code=RealtimeErrorCode.SESSION_CLOSED,
                safe_message=result.safe_message,
                public_metadata={
                    "scope": request.scope.value,
                    "reason": request.reason.value,
                    "interrupt_outcome": result.outcome.value,
                },
            )
            return result

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
        """Request a provider-neutral output flush.

        Real queue flush / playback stop is not implemented yet. Empty mock queue
        and closed-session cases are represented as typed public results.
        """

        request = request or OutputFlushRequest()
        if self._closed:
            result = OutputFlushResult.closed(request=request)
            self._transition(
                RealtimeEventType.OUTPUT_FLUSH_UNSUPPORTED,
                RealtimeState.CLOSED,
                turn_id=request.turn_id,
                public_error_code=RealtimeErrorCode.SESSION_CLOSED,
                safe_message=result.safe_message,
                public_metadata={
                    "flush_outcome": result.outcome.value,
                    "scope": request.scope.value,
                },
            )
            return result

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
        if self._closed:
            return
        self._closed = True
        self._active_turn_id = None
        self._active_generation_id = None
        self._set_phase(None)
        self._transition(
            RealtimeEventType.SESSION_CLOSED,
            RealtimeState.CLOSED,
            payload=LifecycleEventPayload(
                outcome=TurnOutcome.CLOSED,
                recovery_action=RecoveryAction.NONE,
                reason="session_closed",
            ),
            public_metadata={"reason": "session_closed"},
        )

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
