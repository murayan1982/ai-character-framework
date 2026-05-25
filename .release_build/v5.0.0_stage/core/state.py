from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.events import emit


class ConversationState(str, Enum):
    """Known high-level states for one conversation runtime session."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    RESPONDING = "responding"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    EXITING = "exiting"
    ERROR = "error"


@dataclass
class RuntimeState:
    """Mutable conversation state for one active runtime session."""

    current: ConversationState = ConversationState.IDLE
    interruption_requested: bool = False

    def set(self, state: ConversationState) -> ConversationState:
        self.current = state
        return self.current


async def set_runtime_state(
    runtime: dict[str, Any],
    new_state: ConversationState,
) -> None:
    """Update runtime state and emit on_state_change when it changes."""
    state = runtime.get("state")
    if state is None:
        return

    old_state = state.current
    if old_state == new_state:
        return

    state.set(new_state)
    await emit(runtime, "on_state_change", old_state, new_state)


async def request_interruption(runtime: dict[str, Any]) -> None:
    """Request interruption for the active runtime response."""
    state = runtime.get("state")
    if state is None:
        return

    state.interruption_requested = True
    await set_runtime_state(runtime, ConversationState.INTERRUPTED)


def clear_interruption(runtime: dict[str, Any]) -> None:
    """Clear any pending interruption request."""
    state = runtime.get("state")
    if state is None:
        return

    state.interruption_requested = False


def is_interruption_requested(runtime: dict[str, Any]) -> bool:
    """Return whether interruption has been requested."""
    state = runtime.get("state")
    if state is None:
        return False

    return bool(state.interruption_requested)
