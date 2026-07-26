"""Host-app example: public motion expression and speaking-state flow.

This example is mock-safe. It does not connect to a real character runtime or
load private model resources.
"""

from __future__ import annotations

import framework


def main() -> None:
    events: list[str] = []

    session = framework.create_motion_session(adapter="mock")
    session.on_event(lambda event: events.append(event["type"]))

    session.emit_created()

    expression_result = session.apply_motion(
        framework.MotionRequest.expression_change(
            "smile",
            intensity=0.7,
            character_id="cheerful_sora",
        )
    )

    speaking_result = session.apply_motion(
        framework.MotionRequest.speaking_state(
            True,
            character_id="cheerful_sora",
        )
    )

    print("adapter_status:", session.info.adapter_status.value)
    print("expression_outcome:", expression_result.outcome.value)
    print("expression_mock_motion:", expression_result.public_metadata["mock_motion"])
    print("speaking_outcome:", speaking_result.outcome.value)
    print("state_after:", session.state.value)
    print("events:", ",".join(events))


if __name__ == "__main__":
    main()
