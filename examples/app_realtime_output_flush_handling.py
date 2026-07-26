"""Host-app example: public realtime output flush handling.

This example shows typed empty-queue behavior. It does not stop real playback or
flush a real TTS queue.
"""

from __future__ import annotations

import framework


def main() -> None:
    event_types: list[str] = []

    session = framework.create_realtime_session()
    session.on_event(lambda event: event_types.append(event.type.value))

    queue = session.get_tts_queue_state()
    result = session.flush_output(framework.OutputFlushRequest())

    print("queued_count:", queue.queued_count)
    print("queue_supports_flush:", queue.supports_flush)
    print("queue_supports_provider_cancel:", queue.supports_provider_cancel)
    print("flush_outcome:", result.outcome.value)
    print("flush_flushed:", result.flushed)
    print("events:", ",".join(event_types))


if __name__ == "__main__":
    main()
