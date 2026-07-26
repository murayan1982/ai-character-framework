"""Public realtime session skeleton.

This module provides a mock-safe public realtime lifecycle / event boundary. It
intentionally does not execute real STT, LLM, TTS, motion, Live2D, VTube Studio,
websocket, microphone, or provider SDK code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from .realtime import (
    RealtimeErrorCode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeState,
    RealtimeTurn,
    RealtimeTurnResult,
    _public_mapping,
)


RealtimeEventCallback = Callable[[RealtimeEvent], None]


@dataclass(frozen=True)
class RealtimeSessionInfo:
    """App-safe metadata for a public realtime session."""

    api_version: str = "5.2.0"
    session_type: str = "realtime"
    session_id: str = field(default_factory=lambda: uuid4().hex)
    state: RealtimeState | str = RealtimeState.IDLE
    supports_events: bool = True
    supports_run_turn: bool = True
    supports_voice_input: bool = True
    supports_text_chat: bool = True
    supports_voice_output: bool = True
    supports_motion: bool = False
    supports_interrupt: bool = False
    supports_close: bool = True
    real_runtime_enabled: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        state = self.state if isinstance(self.state, RealtimeState) else RealtimeState(str(self.state))
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


class RealtimeSession:
    """Mock-safe public realtime session skeleton.

    The session exposes unified lifecycle, events, turn results, and cleanup
    semantics before real runtime orchestration is implemented.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        public_metadata: Mapping[str, Any] | None = None,
        real_runtime_enabled: bool | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._session_id = uuid4().hex
        self._state = RealtimeState.IDLE
        self._closed = False
        self._callbacks: list[RealtimeEventCallback] = []
        self._real_runtime_enabled = bool(real_runtime_enabled)
        self._public_metadata = _public_mapping(public_metadata)
        self._info = RealtimeSessionInfo(
            session_id=self._session_id,
            state=self._state,
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
            real_runtime_enabled=self._real_runtime_enabled,
            public_metadata={
                "boundary": "realtime",
                **dict(self._public_metadata),
            },
        )

    @property
    def state(self) -> RealtimeState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._closed

    def on_event(self, callback: RealtimeEventCallback) -> None:
        """Register a provider-neutral realtime event callback."""

        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callbacks.append(callback)

    def _transition(
        self,
        event_type: RealtimeEventType,
        new_state: RealtimeState,
        *,
        turn_id: str | None = None,
        public_error_code: RealtimeErrorCode = RealtimeErrorCode.NONE,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeEvent:
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
        )
        for callback in list(self._callbacks):
            callback(event)
        return event

    def emit_created(self) -> RealtimeEvent:
        """Emit a public session-created event."""

        return self._transition(
            RealtimeEventType.SESSION_CREATED,
            RealtimeState.IDLE,
            public_metadata={"reason": "session_created"},
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
            )

        if self._closed:
            self._transition(
                RealtimeEventType.SESSION_CLOSED,
                RealtimeState.CLOSED,
                turn_id=turn.turn_id,
                public_error_code=RealtimeErrorCode.SESSION_CLOSED,
                safe_message="Realtime session is closed.",
            )
            return RealtimeTurnResult.closed(turn_id=turn.turn_id)

        self._transition(RealtimeEventType.TURN_STARTED, RealtimeState.LISTENING, turn_id=turn.turn_id)
        self._transition(RealtimeEventType.VOICE_INPUT_STARTED, RealtimeState.LISTENING, turn_id=turn.turn_id)
        self._transition(
            RealtimeEventType.VOICE_INPUT_COMPLETED,
            RealtimeState.TRANSCRIBING,
            turn_id=turn.turn_id,
            public_metadata={"mock_stage": "voice_input"},
        )
        self._transition(RealtimeEventType.TEXT_CHAT_STARTED, RealtimeState.THINKING, turn_id=turn.turn_id)
        self._transition(
            RealtimeEventType.TEXT_CHAT_COMPLETED,
            RealtimeState.SPEAKING,
            turn_id=turn.turn_id,
            public_metadata={"mock_stage": "text_chat"},
        )
        self._transition(RealtimeEventType.VOICE_OUTPUT_STARTED, RealtimeState.SPEAKING, turn_id=turn.turn_id)
        self._transition(
            RealtimeEventType.VOICE_OUTPUT_COMPLETED,
            RealtimeState.COMPLETED,
            turn_id=turn.turn_id,
            public_metadata={"mock_stage": "voice_output"},
        )
        self._transition(RealtimeEventType.TURN_COMPLETED, RealtimeState.COMPLETED, turn_id=turn.turn_id)

        # A completed turn returns the session to idle for the next host-app
        # interaction, without emitting another event.
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

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._transition(
            RealtimeEventType.SESSION_CLOSED,
            RealtimeState.CLOSED,
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
