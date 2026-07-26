"""Host-app example: public realtime session event flow.

This example is mock-safe. It does not execute real STT, LLM, TTS, motion,
Live2D, VTube Studio, websocket, microphone, or provider SDK code.
"""

from __future__ import annotations

import framework


def main() -> None:
    event_types: list[str] = []

    with framework.create_realtime_session() as session:
        session.on_event(lambda event: event_types.append(event.type.value))

        result = session.run_turn(input_text="今日は少し眠いです。")

        print("result_outcome:", result.outcome.value)
        print("result_input_text:", result.input_text)
        print("result_mock_runtime:", result.public_metadata.get("mock_runtime"))
        print("session_closed_inside:", session.is_closed)

    print("session_closed_after:", session.is_closed)
    print("events:", ",".join(event_types))


if __name__ == "__main__":
    main()
