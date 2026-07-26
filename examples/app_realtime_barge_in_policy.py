"""Host-app example: public realtime barge-in policy and decision.

This example shows policy-level decisions only. It does not perform real audio
barge-in detection or real provider cancellation.
"""

from __future__ import annotations

import framework


def main() -> None:
    event_types: list[str] = []

    session = framework.create_realtime_session()
    session.on_event(lambda event: event_types.append(event.type.value))

    rejected = session.decide_barge_in(turn_id="turn-disabled")

    session.set_barge_in_policy(framework.BargeInPolicy.hard_cancel())
    accepted = session.decide_barge_in(turn_id="turn-hard-cancel")

    print("rejected_accepted:", rejected.accepted)
    print("policy_mode:", session.barge_in_policy.mode.value)
    print("accepted_accepted:", accepted.accepted)
    print("should_stop_output:", accepted.should_stop_output)
    print("should_flush_queue:", accepted.should_flush_queue)
    print("should_cancel_current_turn:", accepted.should_cancel_current_turn)
    print("events:", ",".join(event_types))


if __name__ == "__main__":
    main()
