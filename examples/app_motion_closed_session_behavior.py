"""Host-app example: public motion closed-session behavior."""

from __future__ import annotations

import framework


def main() -> None:
    events: list[str] = []

    session = framework.create_motion_session(adapter="mock")
    session.on_event(lambda event: events.append(event["type"]))

    session.close()
    session.dispose()

    result = session.apply_motion(framework.MotionRequest.expression_change("smile"))

    print("is_closed:", session.is_closed)
    print("state:", session.state.value)
    print("closed_outcome:", result.outcome.value)
    print("closed_error:", result.public_error_code.value)
    print("events:", ",".join(events))


if __name__ == "__main__":
    main()
