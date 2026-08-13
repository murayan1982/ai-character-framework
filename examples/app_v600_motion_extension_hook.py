"""Provider-free host/plugin motion lifecycle mapping through the public root.

The mapping selects provider-neutral requests.  No motion stage is configured,
so mapped work fails truthfully as ``not_configured`` and no VTube Studio or
network operation occurs.  Motion failure does not replace the conversation
terminal result.
"""

from __future__ import annotations

import framework


def run_motion_extension_hook() -> tuple[
    str,
    tuple[str, ...],
    tuple[str, ...],
    int,
    bool,
]:
    """Map speaking/terminal signals and return public-safe observations."""

    signals: list[str] = []

    def character_motion(notification: object) -> framework.MotionRequest | None:
        signal = notification.signal.value
        signals.append(signal)
        if signal == "speaking":
            return framework.MotionRequest.speaking_state(True)
        if signal in {"completed", "interrupted", "failed"}:
            return framework.MotionRequest.stop_motion()
        return None

    with framework.create_realtime_session() as session:
        session.set_motion_lifecycle_hook(character_motion)
        result = session.run_turn(input_text="motion extension demo")
        motion_outcomes = tuple(
            event.payload.outcome.value
            for event in session.event_history
            if event.boundary == "motion" and event.payload.outcome is not None
        )
        terminal_count = sum(
            item.turn_id == result.turn_id for item in session.terminal_results
        )
        return (
            result.outcome.value,
            tuple(signals),
            motion_outcomes,
            terminal_count,
            False,
        )


def main() -> None:
    outcome, signals, motion_outcomes, terminal_count, real_vts = (
        run_motion_extension_hook()
    )
    print("conversation_outcome:", outcome)
    print("lifecycle_signals:", ",".join(signals))
    print("motion_outcomes:", ",".join(motion_outcomes))
    print("conversation_terminal_count:", terminal_count)
    print("real_vts_execution_performed:", real_vts)
    print("provider_execution_performed:", False)


if __name__ == "__main__":
    main()
