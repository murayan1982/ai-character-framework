"""Provider-free interrupt aggregation and partial-completion truthfulness.

``partial`` here describes heterogeneous terminal subsystem observations.  It
does not claim partial transcript or audio streaming, effective cancellation,
or provider hard-cancel completion.
"""

from __future__ import annotations

import framework


def run_interrupt_partial_completion() -> tuple[
    bool,
    str,
    str,
    bool,
    bool,
    int,
    int,
    bool,
    bool,
]:
    """Return public interrupt facts for one provider-free admitted turn."""

    with framework.create_realtime_session() as session:
        start = session.start_turn(input_text="interrupt aggregation demo")
        result = session.interrupt(
            framework.InterruptRequest.user_barge_in(turn_id=start.turn_id)
        )
        aggregate = result.coordination_result
        if aggregate is None:
            raise AssertionError("interrupt coordination result is unavailable")
        return (
            start.accepted,
            result.outcome.value,
            aggregate.outcome.value,
            aggregate.partial,
            aggregate.is_terminal,
            aggregate.completed_count,
            aggregate.timed_out_count,
            result.provider_cancel_supported,
            session.capabilities.voice_input.partial_transcript_supported,
        )


def main() -> None:
    (
        admitted,
        outer_outcome,
        aggregate_outcome,
        partial,
        aggregate_terminal,
        completed_count,
        timed_out_count,
        provider_hard_cancel,
        partial_transcript,
    ) = run_interrupt_partial_completion()
    print("turn_admitted:", admitted)
    print("interrupt_outcome:", outer_outcome)
    print("coordination_outcome:", aggregate_outcome)
    print("coordination_partial:", partial)
    print("coordination_terminal:", aggregate_terminal)
    print("completed_subsystem_count:", completed_count)
    print("timed_out_subsystem_count:", timed_out_count)
    print("provider_hard_cancel_supported:", provider_hard_cancel)
    print("partial_transcript_supported:", partial_transcript)
    print("provider_execution_performed:", False)


if __name__ == "__main__":
    main()
