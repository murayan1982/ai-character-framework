from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.events import create_hook_registry
from core.pipeline import process_ai_response
from core.state import ConversationState, RuntimeState


class FakeLLM:
    def ask_stream(self, user_input: str):
        yield "こんにちは。", []


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

    result = await process_ai_response(
        runtime=runtime,
        llm=FakeLLM(),
        user_input="test",
        vts=None,
        tts=None,
        use_tts=False,
    )

    assert result == "こんにちは。"
    assert events == [
        ("idle", "thinking"),
        ("thinking", "responding"),
    ]

    print("[OK] runtime pipeline state flow reaches thinking then responding")


if __name__ == "__main__":
    asyncio.run(main())