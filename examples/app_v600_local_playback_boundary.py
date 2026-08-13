"""Provider-free demonstration of the host-owned local playback boundary.

The demo session reports that a host player may still be active so the public
coordination events can be exercised.  It performs no media playback.  A host
acknowledgement records receipt only and never confirms physical stop success.
"""

from __future__ import annotations

import framework


class _HostPlaybackDemoSession(framework.RealtimeSession):
    """Public-session demo double with a host-owned active playback snapshot."""

    def get_tts_queue_state(self) -> framework.TTSQueueState:
        return framework.TTSQueueState(
            queued_count=0,
            is_playing=True,
            supports_flush=False,
            supports_provider_cancel=False,
            playback_stop_required=True,
            safe_message="Host playback demo only.",
            public_metadata={"boundary": "host_playback_example"},
        )


def run_local_playback_boundary() -> tuple[str, bool, bool, bool, bool]:
    """Request and acknowledge host stop without claiming physical success."""

    with _HostPlaybackDemoSession() as session:
        start = session.start_turn(input_text="local playback boundary demo")
        flush = session.flush_output(
            framework.OutputFlushRequest(
                turn_id=start.turn_id,
                stop_playback=True,
                clear_queued_audio=True,
            )
        )
        requested = any(
            event.type.value == "realtime.playback_stop.requested_to_host"
            for event in session.event_history
        )
        acknowledgement = session.acknowledge_host_playback_stop(
            turn_id=start.turn_id,
            acknowledged=True,
        )
        return (
            flush.outcome.value,
            requested,
            acknowledgement is not None,
            bool(
                acknowledgement
                and acknowledgement.public_metadata.get(
                    "physical_playback_stop_confirmed"
                )
            ),
            False,
        )


def main() -> None:
    outcome, requested, acknowledged, physical_stop, playback_executed = (
        run_local_playback_boundary()
    )
    print("flush_outcome:", outcome)
    print("host_stop_requested:", requested)
    print("host_stop_acknowledged:", acknowledged)
    print("physical_playback_stop_confirmed:", physical_stop)
    print("playback_execution_performed:", playback_executed)
    print("provider_execution_performed:", False)


if __name__ == "__main__":
    main()
