"""Host-app example: public motion adapter preflight.

This example reads only public capability information.
"""

from __future__ import annotations

import framework


def main() -> None:
    events: list[str] = []

    session = framework.create_motion_session(adapter="mock")
    session.on_event(lambda event: events.append(event["type"]))

    capability = session.preflight()

    print("adapter:", capability.adapter)
    print("adapter_status:", capability.adapter_status.value)
    print("supports_expression:", capability.supports_expression)
    print("supports_speaking_state:", capability.supports_speaking_state)
    print("supports_real_adapter:", capability.supports_real_adapter)
    print("events:", ",".join(events))


if __name__ == "__main__":
    main()
