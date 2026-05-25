from __future__ import annotations

import inspect
from typing import Any, Callable

EventHandler = Callable[..., Any]

EVENT_USER_INPUT = "on_user_input"
EVENT_LLM_CHUNK = "on_llm_chunk"
EVENT_LLM_COMPLETE = "on_llm_complete"
EVENT_EMOTION_DETECTED = "on_emotion_detected"
EVENT_STATE_CHANGE = "on_state_change"
EVENT_ERROR = "on_error"

SUPPORTED_EVENTS = (
    EVENT_USER_INPUT,
    EVENT_LLM_CHUNK,
    EVENT_LLM_COMPLETE,
    EVENT_EMOTION_DETECTED,
    EVENT_STATE_CHANGE,
    EVENT_ERROR,
)


def create_hook_registry() -> dict[str, list[EventHandler]]:
    """
    Create the default runtime hook registry.

    This defines the supported plugin-facing runtime events.
    """
    return {event_name: [] for event_name in SUPPORTED_EVENTS}


async def emit(runtime: dict[str, Any], event_name: str, *args, **kwargs) -> None:
    """
    Emit a runtime event to all registered handlers.

    Event dispatch is best-effort:
    - Unknown or unregistered events are ignored
    - Handlers are called in registration order
    - Async handlers are awaited
    - Sync handlers are called directly
    """
    hooks = runtime.get("hooks", {})
    handlers = hooks.get(event_name, [])

    for handler in handlers:
        result = handler(*args, **kwargs)
        if inspect.isawaitable(result):
            await result