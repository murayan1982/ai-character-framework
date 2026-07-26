"""Host-app example: public motion real-adapter guard behavior.

The real adapter path is intentionally guarded and does not execute provider
runtime code in this example.
"""

from __future__ import annotations

import framework


def main() -> None:
    events: list[str] = []

    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=False,
    )
    session.on_event(lambda event: events.append(event["type"]))

    result = session.apply_motion(framework.MotionRequest.expression_change("smile"))

    print("adapter:", session.info.adapter)
    print("real_adapter_enabled:", session.info.real_adapter_enabled)
    print("real_adapter_supported:", session.info.real_adapter_supported)
    print("guard_outcome:", result.outcome.value)
    print("guard_status:", result.adapter_status.value)
    print("guard_error:", result.public_error_code.value)
    print("events:", ",".join(events))


if __name__ == "__main__":
    main()
