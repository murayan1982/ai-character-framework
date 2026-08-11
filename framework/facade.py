from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Callable, Generator, Mapping

from llm.base import BaseLLM
from config.prompt_builder import build_final_system_instruction

if TYPE_CHECKING:
    from config.loader import RuntimeConfig
    from framework.session_close import SessionCloseResult

from framework.version import TEXT_CHAT_API_VERSION
from framework.identity import EventSequence, GenerationId, SessionId, TurnId
from framework.lifecycle import RealtimePhase, TurnOutcome
from framework.realtime import (
    RealtimeErrorCode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeState,
)
from framework.realtime_event_payloads import (
    InterruptEventPayload,
    LifecycleEventPayload,
    RealtimeEventPayload,
    ResponseEventPayload,
)
from framework.output_control import InterruptOutcome, InterruptRequest, InterruptResult
from framework.public_safety import (
    PublicErrorClassification,
    classify_public_exception,
    public_mapping,
)

from framework.audio import (
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSession,
    VoiceOutputSessionInfo,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
    create_voice_output_session,
)

DEFAULT_TEXT_CHAT_PRESET = "text_chat"

# Public-facing aliases for app developers. Internal provider identifiers remain
# owned by llm.factory / registry.llm.
PROVIDER_ALIASES = {
    "gemini": "google",
    "grok": "xai",
}


class FacadeError(Exception):
    """Base exception for public facade integration errors."""


class FacadeConfigError(FacadeError):
    """Raised when facade preset or text-only configuration is invalid."""


class FacadeProviderError(FacadeError):
    """Raised when facade provider/model resolution or creation fails."""


@dataclass(frozen=True)
class TextChatSessionInfo:
    """Public, stable session information for app integrations.

    This model intentionally exposes only integration-safe metadata. Internal
    RuntimeConfig details remain private so the runtime can evolve without
    breaking application code that depends on the public facade.
    """

    preset: str
    character_name: str
    input_language_code: str
    output_language_code: str
    llm_mode: str
    provider: str | None
    model: str | None
    route_name: str | None
    api_version: str = TEXT_CHAT_API_VERSION
    session_type: str = "text_chat"
    supports_streaming: bool = True
    supports_reset: bool = True
    supports_interrupt: bool = True
    supports_events: bool = True
    supports_close: bool = True
    supports_voice_input: bool = False
    supports_voice_output: bool = False
    supports_live2d: bool = False


@dataclass(frozen=True)
class TextChatSessionEvent:
    """Public app-facing event emitted by a text chat session.

    Events are intentionally small and app-safe. They do not expose provider,
    runtime, plugin, STT/TTS, or VTS implementation objects.
    """

    type: str
    data: dict[str, object]


@dataclass(frozen=True)
class TextChatStateChange:
    """Public app-facing state transition emitted by a text chat session."""

    old_state: str
    new_state: str


@dataclass(frozen=True, slots=True)
class _TextChatRealtimeTurnContext:
    """Internal v6 correlation context for one legacy text-chat turn."""

    session_id: SessionId
    turn_id: TurnId
    generation_id: GenerationId
    input_text: str = field(repr=False)


class TextChatSession:
    """Public text-chat session facade.

    This class is the small public entry point for developers who want to use
    the framework as a library instead of launching the interactive main loop.
    It owns one LLM instance and exposes simple text-only turn methods.
    """

    def __init__(self, llm: BaseLLM, info: TextChatSessionInfo):
        self._llm = llm
        self.info = info
        self._interrupt_requested = False
        self._state = "idle"
        self._event_callbacks: list[Callable[[TextChatSessionEvent], None]] = []
        self._state_change_callbacks: list[Callable[[TextChatStateChange], None]] = []
        self._session_id = SessionId.new()
        self._next_realtime_event_sequence = EventSequence.first()
        self._realtime_event_callbacks: list[Callable[[RealtimeEvent], None]] = []
        self._realtime_event_lock = RLock()
        self._active_realtime_turn_context: _TextChatRealtimeTurnContext | None = None
        self._fw_public_closed = False
        self._last_close_result: SessionCloseResult | None = None

    @property
    def session_id(self) -> SessionId:
        """Return the stable v6 correlation identity for this text session."""

        return self._session_id

    def on_realtime_event(
        self,
        callback: Callable[[RealtimeEvent], None],
    ) -> Callable[[RealtimeEvent], None]:
        """Register a canonical v6 realtime-event callback and return it.

        FW-RT6-5c Control A adds the callback boundary and identity scaffold only.
        Existing ``ask()`` / ``ask_stream()`` event behavior is adopted in a later
        control so legacy app-facing events remain unchanged in this checkpoint.
        """

        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._realtime_event_lock:
            if self.is_closed:
                raise RuntimeError("Text chat session is closed.")
            self._realtime_event_callbacks.append(callback)
        return callback

    def _new_realtime_turn_context(
        self,
        input_text: str,
    ) -> _TextChatRealtimeTurnContext:
        """Create one Framework-owned turn/generation correlation context."""

        return _TextChatRealtimeTurnContext(
            session_id=self._session_id,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
            input_text=input_text,
        )

    def _emit_realtime_event(
        self,
        event_type: RealtimeEventType,
        *,
        state: RealtimeState,
        context: _TextChatRealtimeTurnContext | None = None,
        previous_state: RealtimeState | None = None,
        phase: RealtimePhase | None = None,
        payload: RealtimeEventPayload | None = None,
        terminal: bool | None = None,
        public_error_code: RealtimeErrorCode = RealtimeErrorCode.NONE,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, object] | None = None,
    ) -> RealtimeEvent:
        """Emit one sequenced canonical v6 event to compatibility callbacks."""

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
            phase=phase,
            payload=payload,
            terminal=terminal,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=public_metadata or {},
            boundary="text_chat",
        )
        for callback in callbacks:
            callback(event)
        return event

    def on_event(
        self,
        callback: Callable[[TextChatSessionEvent], None],
    ) -> Callable[[TextChatSessionEvent], None]:
        """Register an app-facing event callback and return it.

        This callback API is separate from internal plugin hooks. It is intended
        for external apps that want to observe text session events without
        importing runtime or plugin internals.
        """
        if self.is_closed:
            raise RuntimeError("Text chat session is closed.")
        self._event_callbacks.append(callback)
        return callback

    def on_state_change(
        self,
        callback: Callable[[TextChatStateChange], None],
    ) -> Callable[[TextChatStateChange], None]:
        """Register an app-facing state change callback and return it."""
        if self.is_closed:
            raise RuntimeError("Text chat session is closed.")
        self._state_change_callbacks.append(callback)
        return callback

    def _emit_event(
        self,
        event_type: str,
        data: dict[str, object] | None = None,
    ) -> None:
        """Emit one app-facing event to registered callbacks."""
        event = TextChatSessionEvent(type=event_type, data=data or {})
        for callback in list(self._event_callbacks):
            callback(event)

    def _set_state(self, new_state: str) -> None:
        """Update the app-facing session state and notify callbacks."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        event = TextChatStateChange(old_state=old_state, new_state=new_state)
        for callback in list(self._state_change_callbacks):
            callback(event)

    def _emit_legacy_event_from_realtime_event(
        self,
        event: RealtimeEvent,
        *,
        context: _TextChatRealtimeTurnContext | None = None,
        classification: PublicErrorClassification | None = None,
    ) -> None:
        """Project selected canonical events onto the stable v4/v5 facade event shape."""

        if event.type is RealtimeEventType.RESPONSE_STARTED:
            if context is None:
                raise RuntimeError("Text chat compatibility context is required.")
            self._emit_event("response_started", {"text": context.input_text})
            return

        if event.type is RealtimeEventType.RESPONSE_DELTA:
            payload = event.payload
            if not isinstance(payload, ResponseEventPayload):
                raise RuntimeError("Text chat response delta payload is invalid.")
            self._emit_event("response_chunk", {"chunk": payload.text})
            return

        if event.type is RealtimeEventType.RESPONSE_COMPLETED:
            self._emit_event("response_completed")
            return

        if event.type is RealtimeEventType.INTERRUPT_REQUESTED:
            self._emit_event("interrupt_requested")
            return

        if event.type is RealtimeEventType.TURN_FAILED:
            if classification is None:
                raise RuntimeError("Text chat failure classification is required.")
            self._emit_event("error", _text_chat_error_event_data(classification))

    def ask(self, text: str) -> str:
        """Send one text turn and return the full assistant response."""
        return "".join(self.ask_stream(text))



    @property
    def is_closed(self) -> bool:
        """Whether this public text chat session has been closed."""

        return self._fw_public_closed

    @property
    def last_close_result(self) -> SessionCloseResult | None:
        """Return the latest immutable close observation."""

        return self._last_close_result

    def close(self) -> None:
        """Close the public text chat session.

        The public close boundary is intentionally idempotent. It marks the
        session as closed without exposing provider clients or private runtime
        resources to host applications. Provider-specific cleanup hooks can be
        wired behind this method in later checkpoints.
        """

        from framework.session_close import (
            SessionCleanupResult,
            SessionCleanupTarget,
            SessionCloseResult,
            _runtime_close_result,
            build_session_close_plan,
        )

        with self._realtime_event_lock:
            if self._fw_public_closed:
                self._last_close_result = SessionCloseResult.already_closed(
                    public_metadata={"boundary": "text_chat"}
                )
                return
            context = self._active_realtime_turn_context
            plan = build_session_close_plan(
                active_turn_terminal_required=context is not None,
                callback_hub_close_required=context is not None,
                public_metadata={"boundary": "text_chat"},
            )
            self._fw_public_closed = True
            self._interrupt_requested = True

        callback_result = SessionCleanupResult.not_required(
            SessionCleanupTarget.CALLBACK_HUB
        )
        if context is not None:
            callback_result = SessionCleanupResult.completed(
                SessionCleanupTarget.CALLBACK_HUB
            )
            try:
                if self._state != "closed":
                    self._set_state("closed")
                self._emit_event("closed")
                self._emit_realtime_event(
                    RealtimeEventType.SESSION_CLOSED,
                    state=RealtimeState.CLOSED,
                    previous_state=RealtimeState.THINKING,
                    context=context,
                    payload=LifecycleEventPayload(
                        outcome=TurnOutcome.CLOSED,
                        reason="session_closed",
                    ),
                    public_error_code=RealtimeErrorCode.SESSION_CLOSED,
                    safe_message="Text chat session is closed.",
                    public_metadata={"boundary": "text_chat"},
                )
            except Exception:
                callback_result = SessionCleanupResult.failed_result(
                    SessionCleanupTarget.CALLBACK_HUB,
                    safe_message="Text chat callback cleanup failed.",
                )
            finally:
                with self._realtime_event_lock:
                    self._active_realtime_turn_context = None
                    self._realtime_event_callbacks.clear()
                self._event_callbacks.clear()
                self._state_change_callbacks.clear()
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
            public_metadata={"boundary": "text_chat"},
        )
        if self._last_close_result is None:
            self._last_close_result = first_result

    def dispose(self) -> None:
        """Compatibility alias for ``close()``."""

        self.close()

    def __enter__(self) -> "TextChatSession":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False
    def ask_result(self, message: str) -> "TextChatResult":
        """Return a provider-neutral typed result for a text chat request.

        This method is the non-breaking typed-result companion to ``ask()``.
        Existing ``ask()`` behavior is preserved for v4/v5 compatibility, while
        host apps can use ``ask_result()`` to avoid parsing raw exception strings
        or ad-hoc response shapes.
        """

        from .text_chat_result import TextChatResult

        if getattr(self, "_fw_public_closed", False):
            return TextChatResult.failed(
                public_error_code="session_closed",
                safe_message="Text chat session is closed.",
                retryable=False,
                public_metadata={"boundary": "text_chat"},
            )

        try:
            response = self.ask(message)
        except Exception as exc:  # noqa: BLE001 - public boundary converts to safe result
            classification = _classify_text_chat_exception(exc)
            return TextChatResult.failed(
                public_error_code=classification.public_error_code,
                safe_message=classification.safe_message,
                retryable=classification.retryable,
                public_metadata=dict(classification.public_metadata),
            )

        text = _text_chat_response_to_text(response)
        if text is None:
            return TextChatResult.failed(
                public_error_code="empty_response",
                safe_message="Text chat returned no response text.",
                retryable=True,
                public_metadata={"boundary": "text_chat"},
            )

        return TextChatResult.completed(
            text,
            public_metadata={"boundary": "text_chat"},
        )
    def ask_stream(self, text: str) -> Generator[str, None, None]:
        """Send one text turn and yield assistant response chunks."""
        if self.is_closed:
            return
        context = self._new_realtime_turn_context(text)
        self._active_realtime_turn_context = context
        self._interrupt_requested = False
        self._set_state("responding")

        self._emit_realtime_event(
            RealtimeEventType.TURN_STARTED,
            state=RealtimeState.THINKING,
            previous_state=RealtimeState.IDLE,
            phase=RealtimePhase.THINKING,
            context=context,
            payload=LifecycleEventPayload(reason="text_chat_started"),
        )
        response_started = self._emit_realtime_event(
            RealtimeEventType.RESPONSE_STARTED,
            state=RealtimeState.THINKING,
            phase=RealtimePhase.THINKING,
            context=context,
            payload=ResponseEventPayload(text="", is_final=False),
        )
        self._emit_legacy_event_from_realtime_event(
            response_started,
            context=context,
        )

        completed = False
        response_parts: list[str] = []
        delta_index = 0
        try:
            for chunk, _emotions in self._llm.ask_stream(text):
                if self.is_closed:
                    break
                if self._interrupt_requested:
                    self._set_state("interrupted")
                    self._emit_realtime_event(
                        RealtimeEventType.TURN_INTERRUPTED,
                        state=RealtimeState.INTERRUPTED,
                        previous_state=RealtimeState.THINKING,
                        context=context,
                        payload=LifecycleEventPayload(
                            outcome=TurnOutcome.INTERRUPTED,
                            reason="interrupt_requested",
                        ),
                        public_error_code=RealtimeErrorCode.INTERRUPTED,
                        safe_message=_TEXT_CHAT_SAFE_MESSAGES["request_cancelled"],
                        retryable=False,
                        public_metadata={"boundary": "text_chat"},
                    )
                    break
                if chunk:
                    response_parts.append(chunk)
                    response_delta = self._emit_realtime_event(
                        RealtimeEventType.RESPONSE_DELTA,
                        state=RealtimeState.THINKING,
                        phase=RealtimePhase.THINKING,
                        context=context,
                        payload=ResponseEventPayload(
                            text=chunk,
                            delta_index=delta_index,
                            is_final=False,
                        ),
                    )
                    delta_index += 1
                    self._emit_legacy_event_from_realtime_event(response_delta)
                    yield chunk
            else:
                if self.is_closed:
                    return
                completed = True
                response_completed = self._emit_realtime_event(
                    RealtimeEventType.RESPONSE_COMPLETED,
                    state=RealtimeState.THINKING,
                    phase=RealtimePhase.THINKING,
                    context=context,
                    payload=ResponseEventPayload(
                        text="".join(response_parts),
                        is_final=True,
                    ),
                )
                self._emit_legacy_event_from_realtime_event(response_completed)
                self._emit_realtime_event(
                    RealtimeEventType.TURN_COMPLETED,
                    state=RealtimeState.COMPLETED,
                    previous_state=RealtimeState.THINKING,
                    context=context,
                    payload=LifecycleEventPayload(
                        outcome=TurnOutcome.COMPLETED,
                        reason="text_chat_completed",
                    ),
                )
        except Exception as exc:
            if self.is_closed:
                raise
            self._set_state("error")
            classification = _classify_text_chat_exception(exc)
            failed = self._emit_realtime_event(
                RealtimeEventType.TURN_FAILED,
                state=RealtimeState.FAILED,
                previous_state=RealtimeState.THINKING,
                context=context,
                payload=LifecycleEventPayload(
                    outcome=TurnOutcome.FAILED,
                    reason="text_chat_failed",
                ),
                public_error_code=_text_chat_realtime_error_code(classification),
                safe_message=classification.safe_message,
                retryable=classification.retryable,
                public_metadata={
                    **dict(classification.public_metadata),
                    "text_chat_public_error_code": classification.public_error_code,
                },
            )
            self._emit_legacy_event_from_realtime_event(
                failed,
                classification=classification,
            )
            raise
        finally:
            if self._active_realtime_turn_context is context:
                self._active_realtime_turn_context = None
            if (
                not self.is_closed
                and (completed or self._state in {"responding", "interrupted", "error"})
            ):
                self._set_state("idle")

    def reset(self) -> None:
        """Reset provider-owned conversation state when supported."""
        self._llm.reset_session()
        self._emit_event("reset")
        self._set_state("idle")

    def interrupt_result(
        self,
        request: InterruptRequest | None = None,
    ) -> InterruptResult:
        """Return the typed v6 outcome for one text-chat interrupt request.

        This compatibility boundary only accepts cooperative suppression of future
        delivered text chunks. It does not claim provider transport hard-cancel or
        output-queue flush support. The stable legacy ``interrupt()`` method keeps
        its historical boolean request-received contract separately.
        """

        if request is not None and not isinstance(request, InterruptRequest):
            raise TypeError("request must be an InterruptRequest or None")

        context = self._active_realtime_turn_context
        request = request or InterruptRequest(
            turn_id=context.turn_id if context is not None else None,
        )

        if self.is_closed:
            result = InterruptResult(
                outcome=InterruptOutcome.ALREADY_CLOSED,
                scope=request.scope,
                reason=request.reason,
                turn_id=(
                    context.turn_id
                    if context is not None
                    else request.turn_id
                ),
                safe_message="Text chat session is already closed.",
                retryable=False,
                provider_cancel_supported=False,
                queue_flush_supported=False,
                public_metadata={
                    "boundary": "text_chat",
                    "reason": "session_closed",
                },
            )
            state = RealtimeState.CLOSED
            phase = None
        elif context is None:
            result = InterruptResult(
                outcome=InterruptOutcome.NO_ACTIVE_TURN,
                scope=request.scope,
                reason=request.reason,
                turn_id=request.turn_id,
                safe_message="There is no active text chat turn to interrupt.",
                retryable=False,
                provider_cancel_supported=False,
                queue_flush_supported=False,
                public_metadata={
                    "boundary": "text_chat",
                    "reason": "no_active_turn",
                },
            )
            state = RealtimeState.IDLE
            phase = RealtimePhase.IDLE
        else:
            self._interrupt_requested = True
            result = InterruptResult(
                outcome=InterruptOutcome.ACCEPTED,
                scope=request.scope,
                reason=request.reason,
                turn_id=context.turn_id,
                safe_message="Text chat interrupt request was accepted.",
                retryable=False,
                provider_cancel_supported=False,
                queue_flush_supported=False,
                public_metadata={
                    "boundary": "text_chat",
                    "cooperative_delivery_interrupt": True,
                },
            )
            state = RealtimeState.THINKING
            phase = RealtimePhase.THINKING

        requested = self._emit_realtime_event(
            RealtimeEventType.INTERRUPT_REQUESTED,
            state=state,
            context=context,
            phase=phase,
            payload=InterruptEventPayload(
                scope=result.scope,
                outcome=result.outcome,
                reason=result.reason.value,
            ),
            safe_message=result.safe_message,
            retryable=result.retryable,
            public_metadata=result.public_metadata,
        )
        self._emit_legacy_event_from_realtime_event(requested)
        return result

    def interrupt(self) -> bool:
        """Preserve the legacy v4/v5 boolean interrupt request contract.

        The typed runtime outcome is available through ``interrupt_result()``.
        Historically this method returned ``True`` when the host request was
        received, even if there was no active turn, so that observable behavior
        remains unchanged.
        """

        self.interrupt_result()
        return True


def _resolve_preset_name(preset: str | None) -> str:
    """Resolve facade preset priority: explicit argument -> .env -> default."""
    if preset:
        return preset

    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()

    return os.getenv("APP_PRESET", DEFAULT_TEXT_CHAT_PRESET)


def _is_text_only_config(config: "RuntimeConfig") -> bool:
    """Return whether a RuntimeConfig is compatible with the text facade."""
    return (
        not config.input_voice_enabled
        and not config.output_voice_enabled
        and not config.vts_enabled
        and config.tts_provider == "none"
    )


def _validate_text_only_config(config: "RuntimeConfig") -> None:
    """Reject presets that would require runtime systems outside the facade."""
    if _is_text_only_config(config):
        return

    raise FacadeConfigError(
        "create_text_chat_session() currently supports text-only presets only. "
        f"Preset '{config.app_preset}' enables one or more unsupported runtime features: "
        f"input_voice_enabled={config.input_voice_enabled}, "
        f"output_voice_enabled={config.output_voice_enabled}, "
        f"vts_enabled={config.vts_enabled}, "
        f"tts_provider={config.tts_provider!r}. "
        "Use a text-only preset such as 'text_chat', or launch main.py for full runtime features."
    )


def _load_facade_config(
    preset: str | None,
    character_name: str | None,
    *,
    project_root: str | Path | None = None,
) -> "RuntimeConfig":
    """Build RuntimeConfig for the public facade without starting the runtime loop.

    Boundary rules:
    - explicit function arguments override preset / environment defaults
    - APP_PRESET is used only when preset is not passed
    - character_name overrides the character selected by the preset
    - only text-only presets are accepted by the public text-chat facade
    """
    from config.loader import (
        RuntimeConfig,
        load_character_data,
        load_preset_file,
        normalize_language_code,
    )

    preset_name = _resolve_preset_name(preset)

    try:
        preset_data = load_preset_file(
            preset_name,
            project_root=project_root,
        )
    except (FileNotFoundError, ValueError) as e:
        raise FacadeConfigError(
            f"Facade preset not found: {preset_name!r}. "
            "Pass an existing text-only preset name, such as 'text_chat'."
        ) from e

    resolved_character_name = character_name or preset_data.get(
        "character_name",
        preset_data.get("character", "default"),
    )

    try:
        character_data = load_character_data(
            resolved_character_name,
            project_root=project_root,
        )
    except (FileNotFoundError, ValueError) as e:
        raise FacadeConfigError(
            f"Facade character not found: {resolved_character_name!r}. "
            "Pass an existing character name or update the selected preset."
        ) from e

    config = RuntimeConfig(
        app_preset=preset_name,
        input_language_code=normalize_language_code(
            preset_data.get("input_language_code", "ja"),
            default="ja",
        ),
        output_language_code=normalize_language_code(
            preset_data.get("output_language_code", "ja"),
            default="en",
        ),
        input_voice_enabled=bool(preset_data.get("input_voice_enabled", False)),
        output_voice_enabled=bool(preset_data.get("output_voice_enabled", False)),
        vts_enabled=bool(preset_data.get("vts_enabled", False)),
        tts_provider=preset_data.get("tts_provider", "none"),
        allow_text_fallback_during_stt=bool(
            preset_data.get("allow_text_fallback_during_stt", False)
        ),
        emotion_enabled=bool(preset_data.get("emotion_enabled", False)),
        vts_emotion_enabled=bool(preset_data.get("vts_emotion_enabled", False)),
        character_name=resolved_character_name,
        character_profile=character_data.profile,
        system_prompt=character_data.system_prompt,
        vts_hotkeys=character_data.vts_hotkeys,
    )

    _validate_text_only_config(config)
    return config


def _build_system_instruction(config: "RuntimeConfig") -> str:
    """Build the same final system instruction used by the runtime layer."""
    return build_final_system_instruction(config)


def _build_catalog_llm(llm_name: str, system_instruction: str) -> BaseLLM:
    """Build one catalog LLM without importing the full runtime builder."""
    from llm.factory import create_llm
    from registry.llm import LLM_CATALOG

    if llm_name not in LLM_CATALOG:
        raise FacadeProviderError(f"Unknown LLM catalog entry: {llm_name}")

    llm_config = LLM_CATALOG[llm_name]

    try:
        return create_llm(
            provider=llm_config["provider"],
            model=llm_config["model"],
            system_instruction=system_instruction,
        )
    except ValueError as e:
        raise FacadeProviderError(str(e)) from e


def _normalize_provider(provider: str) -> str:
    """Normalize public provider aliases to internal provider identifiers."""
    normalized = provider.strip().lower()
    return PROVIDER_ALIASES.get(normalized, normalized)


def _resolve_default_model_for_provider(provider: str) -> str:
    """Resolve the first registry model matching a provider.

    The registry remains the owner of default provider/model pairs. The facade
    only selects an existing catalog model when an app passes provider without a
    model override.
    """
    from registry.llm import LLM_CATALOG

    for llm_config in LLM_CATALOG.values():
        if llm_config.get("provider") == provider:
            return llm_config["model"]

    raise FacadeProviderError(
        f"No default model is registered for provider {provider!r}. "
        "Pass both provider and model, or add the provider to registry.llm.LLM_CATALOG."
    )


def _resolve_provider_model(
    provider: str,
    model: str | None,
) -> tuple[str, str]:
    """Validate facade provider/model arguments and resolve model defaults."""
    from llm.factory import get_supported_llm_providers

    resolved_provider = _normalize_provider(provider)
    supported_providers = get_supported_llm_providers()

    if resolved_provider not in supported_providers:
        public_aliases = sorted(PROVIDER_ALIASES.keys())
        raise FacadeProviderError(
            f"Unsupported facade provider: {provider!r}. "
            f"Supported providers: {sorted(supported_providers)}. "
            f"Aliases: {public_aliases}."
        )

    resolved_model = model or _resolve_default_model_for_provider(resolved_provider)
    return resolved_provider, resolved_model


def _build_direct_provider_llm(
    provider: str,
    model: str,
    system_instruction: str,
) -> BaseLLM:
    """Build one explicitly selected provider/model for facade integration use."""
    from llm.factory import create_llm

    try:
        return create_llm(
            provider=provider,
            model=model,
            system_instruction=system_instruction,
        )
    except ValueError as e:
        raise FacadeProviderError(str(e)) from e


def _build_text_chat_info(
    config: "RuntimeConfig",
    provider: str | None,
    model: str | None,
) -> TextChatSessionInfo:
    """Build the public session info model without exposing RuntimeConfig."""
    if provider:
        resolved_provider, resolved_model = _resolve_provider_model(
            provider=provider,
            model=model,
        )
        return TextChatSessionInfo(
            preset=config.app_preset,
            character_name=config.character_name,
            input_language_code=config.input_language_code,
            output_language_code=config.output_language_code,
            llm_mode="direct_provider",
            provider=resolved_provider,
            model=resolved_model,
            route_name=None,
        )

    return TextChatSessionInfo(
        preset=config.app_preset,
        character_name=config.character_name,
        input_language_code=config.input_language_code,
        output_language_code=config.output_language_code,
        llm_mode="default_route",
        provider=None,
        model=None,
        route_name="chat",
    )


def _build_text_chat_llm(
    system_instruction: str,
    info: TextChatSessionInfo,
) -> BaseLLM:
    """Build the public facade's text-chat LLM path.

    In direct provider mode, the facade builds exactly one provider/model pair.
    In default route mode, it keeps the chat route with fallback while hiding
    internal route members from the public info model.
    """
    if info.provider and info.model:
        return _build_direct_provider_llm(
            provider=info.provider,
            model=info.model,
            system_instruction=system_instruction,
        )

    from llm.fallback_llm import FallbackLLM
    from registry.llm import LLM_ROUTES

    route_config = LLM_ROUTES["chat"]
    primary = _build_catalog_llm(route_config["primary"], system_instruction)
    fallback = _build_catalog_llm(route_config["fallback"], system_instruction)

    return FallbackLLM(primary, fallback)


def create_text_chat_session(
    preset: str | None = None,
    character_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    *,
    project_root: str | Path | None = None,
) -> TextChatSession:
    """Create a text-only chat session without starting the app runtime loop.

    Args:
        preset: Optional text-only preset name. When omitted, APP_PRESET is used
            if available, otherwise 'text_chat' is used.
        character_name: Optional character override. When omitted, the character
            configured by the selected preset is used.
        provider: Optional direct LLM provider override. When omitted, the
            facade uses the default chat route with fallback.
        model: Optional model override for the selected provider. Ignored when
            provider is omitted.
        project_root: Optional compatibility root for preset and character
            resources. Provider configuration is not resolved from this path.
    """
    config = _load_facade_config(
        preset=preset,
        character_name=character_name,
        project_root=project_root,
    )
    system_instruction = _build_system_instruction(config)
    info = _build_text_chat_info(
        config=config,
        provider=provider,
        model=model,
    )
    llm = _build_text_chat_llm(
        system_instruction=system_instruction,
        info=info,
    )
    return TextChatSession(llm, info)

def _text_chat_response_to_text(response: object) -> str | None:
    """Convert known public-ish text response shapes into plain text."""

    if response is None:
        return None
    if isinstance(response, str):
        text = response.strip()
        return text or None

    for attr_name in ("text", "message", "content"):
        value = getattr(response, attr_name, None)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text

    text = str(response).strip()
    if not text or text == "None":
        return None
    return text

_TEXT_CHAT_SAFE_MESSAGES = {
    "configuration_missing": "Text chat configuration is missing or invalid.",
    "authentication_required": "Text chat provider authentication is required.",
    "rate_limited": "Text chat provider rate limit was reached.",
    "request_cancelled": "Text chat request was cancelled or interrupted.",
    "timeout": "Text chat request timed out.",
    "unsupported_capability": "Text chat capability is not supported by this session.",
    "session_closed": "Text chat session is closed.",
    "invalid_request": "Text chat request is invalid.",
    "provider_request_failed": "Text chat provider request failed.",
    "provider_unavailable": "Text chat provider is unavailable.",
    "unknown_error": "Text chat request failed.",
}


def _classify_text_chat_exception(exc: Exception) -> PublicErrorClassification:
    """Classify one text-chat exception without exposing raw exception material."""

    if isinstance(exc, FacadeConfigError):
        return PublicErrorClassification(
            public_error_code="configuration_missing",
            safe_message=_TEXT_CHAT_SAFE_MESSAGES["configuration_missing"],
            retryable=False,
            public_metadata={
                "boundary": "text_chat",
                "error_category": "configuration",
            },
        )

    if isinstance(exc, FacadeProviderError):
        return PublicErrorClassification(
            public_error_code="provider_request_failed",
            safe_message=_TEXT_CHAT_SAFE_MESSAGES["provider_request_failed"],
            retryable=True,
            public_metadata={
                "boundary": "text_chat",
                "error_category": "provider_request",
            },
        )

    base = classify_public_exception(
        exc,
        fallback_error_code="provider_request_failed",
        fallback_safe_message=_TEXT_CHAT_SAFE_MESSAGES["provider_request_failed"],
        fallback_retryable=True,
    )
    code = base.public_error_code
    return PublicErrorClassification(
        public_error_code=code,
        safe_message=_TEXT_CHAT_SAFE_MESSAGES.get(
            code,
            _TEXT_CHAT_SAFE_MESSAGES["unknown_error"],
        ),
        retryable=base.retryable,
        public_metadata={
            "boundary": "text_chat",
            **dict(base.public_metadata),
        },
    )


def _text_chat_realtime_error_code(
    classification: PublicErrorClassification,
) -> RealtimeErrorCode:
    """Map the stable text-chat classifier onto the existing v6 error vocabulary."""

    return {
        "configuration_missing": RealtimeErrorCode.CONFIGURATION_MISSING,
        "session_closed": RealtimeErrorCode.SESSION_CLOSED,
        "invalid_request": RealtimeErrorCode.INVALID_REQUEST,
        "unsupported_capability": RealtimeErrorCode.UNSUPPORTED,
        "provider_unavailable": RealtimeErrorCode.UNAVAILABLE,
        "request_cancelled": RealtimeErrorCode.CANCELLED,
    }.get(classification.public_error_code, RealtimeErrorCode.PROVIDER_ERROR)


def _text_chat_error_event_data(
    classification: PublicErrorClassification,
) -> dict[str, object]:
    """Return the stable public TextChat error-event payload."""

    metadata = public_mapping(classification.public_metadata)
    return {
        "public_error_code": classification.public_error_code,
        "safe_message": classification.safe_message,
        "retryable": classification.retryable,
        "public_metadata": dict(metadata),
    }


def _text_chat_exception_to_public_error_code(exc: Exception) -> str:
    """Compatibility helper backed by the common safe classifier."""

    return _classify_text_chat_exception(exc).public_error_code


def _text_chat_exception_is_retryable(exc: Exception) -> bool:
    """Compatibility helper backed by the common safe classifier."""

    return _classify_text_chat_exception(exc).retryable


def _text_chat_exception_to_safe_message(exc: Exception) -> str:
    """Compatibility helper backed by the common safe classifier."""

    return _classify_text_chat_exception(exc).safe_message
