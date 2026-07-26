"""Host-app example: public realtime interrupt handling.

This example is mock-safe. It does not execute real LLM streaming cancellation,
real TTS queue cancellation, playback stop, provider cancellation, or barge-in
audio detection.
"""

from __future__ import annotations

import framework


def main() -> None:
    event_types: list[str] = []

    session = framework.create_realtime_session()
    session.on_event(lambda event: event_types.append(event.type.value))

    request = framework.InterruptRequest.user_barge_in(turn_id="example-turn")
    result = session.interrupt(request)

    print("interrupt_outcome:", result.outcome.value)
    print("interrupt_scope:", result.scope.value)
    print("interrupt_reason:", result.reason.value)
    print("provider_cancel_supported:", result.provider_cancel_supported)
    print("queue_flush_supported:", result.queue_flush_supported)
    print("events:", ",".join(event_types))


if __name__ == "__main__":
    main()
