from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.events import create_hook_registry
from core.state import (
    ConversationState,
    RuntimeState,
    clear_interruption,
    is_interruption_requested,
    request_interruption,
    set_runtime_state,
)


async def main() -> None:
    events: list[tuple[str, str]] = []

    def on_state_change(
        old_state: ConversationState,
        new_state: ConversationState,
    ) -> None:
        events.append((old_state.value, new_state.value))

    runtime = {
        "state": RuntimeState(),
        "hooks": create_hook_registry(),
    }
    runtime["hooks"]["on_state_change"].append(on_state_change)

    assert runtime["state"].current == ConversationState.IDLE
    assert is_interruption_requested(runtime) is False

    await request_interruption(runtime)

    assert runtime["state"].current == ConversationState.INTERRUPTED
    assert is_interruption_requested(runtime) is True
    assert events == [("idle", "interrupted")]

    clear_interruption(runtime)

    assert runtime["state"].current == ConversationState.INTERRUPTED
    assert is_interruption_requested(runtime) is False
    assert events == [("idle", "interrupted")]

    await set_runtime_state(runtime, ConversationState.IDLE)

    assert runtime["state"].current == ConversationState.IDLE
    assert is_interruption_requested(runtime) is False
    assert events == [("idle", "interrupted"), ("interrupted", "idle")]

    print("[OK] interruption state helpers preserve expected ownership boundaries")


if __name__ == "__main__":
    asyncio.run(main())