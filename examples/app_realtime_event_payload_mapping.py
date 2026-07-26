"""Host-app example: public realtime event payload mapping.

This example shows how a host app can convert `RealtimeEvent` objects into
public-safe dictionaries for UI state updates or logs.
"""

from __future__ import annotations

import framework


def main() -> None:
    event = framework.RealtimeEvent(
        type=framework.RealtimeEventType.TURN_STARTED,
        state=framework.RealtimeState.LISTENING,
        previous_state=framework.RealtimeState.IDLE,
        turn_id="example-turn",
        session_id="example-session",
        public_metadata={"screen": "daily_check", "api_key": "should-not-leak"},
    )

    payload = event.as_dict()

    print("event_type:", payload["type"])
    print("state:", payload["state"])
    print("previous_state:", payload["previous_state"])
    print("turn_id:", payload["turn_id"])
    print("metadata_api_key:", payload["public_metadata"]["api_key"])


if __name__ == "__main__":
    main()
