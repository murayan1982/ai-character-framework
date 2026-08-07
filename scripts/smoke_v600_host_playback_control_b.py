"""FW-RT6-6e Control B host-playback runtime coordination gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "6c1d920fb8c15d3f66eed58a8a35c506224dc66e"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/audio/_provider_adapter.py",
    "framework/capabilities.py",
    "framework/realtime_session.py",
    "tts/voice_engine.py",
    "scripts/smoke_v600_host_playback_control_b.py",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _assert(
        result.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        p.strip().replace("\\", "/")
        for p in (*tracked, *untracked)
        if p.strip()
    }


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control B exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact eight-file FW-RT6-6e Control B surface conform")


def check_control_a_foundation() -> None:
    import importlib.util

    path = PROJECT_ROOT / "scripts/smoke_v600_host_playback_control_a.py"
    spec = importlib.util.spec_from_file_location("_fw_rt6_6e_control_a", path)
    _assert(spec is not None and spec.loader is not None, "cannot load Control A gate")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Reuse model/event/stable-boundary checks. The historical authoritative
    # builder check encoded pre-Control-B ack adoption and is intentionally not
    # called here.
    module.check_capability_model()
    module.check_event_contract()
    module.check_stable_surfaces_and_boundaries()
    print("[OK] accepted Control A model/event/stable-boundary checks conform")


def check_capability_adoption() -> None:
    from framework.capabilities import get_capabilities
    from framework.audio._provider_adapter import (
        VoiceOutputProviderStatus,
        _capability_from_status,
    )
    from framework.realtime_session import RealtimeSession

    global_voice = get_capabilities(real_tts_enabled=False).realtime_snapshot.voice_output
    _assert(global_voice.playback_ownership == "host", "global ownership drift")
    _assert(global_voice.host_playback_stop_request_supported is True, "global request support drift")
    _assert(global_voice.host_playback_stop_ack_supported is True, "global ack adoption missing")

    provider_voice = _capability_from_status(
        VoiceOutputProviderStatus(
            real_tts_enabled=False,
            provider_configured=False,
            provider_execution_allowed=False,
            supports_audio_artifact_ref=False,
            supports_audio_url=False,
            status="contract_ready",
            status_reason="control-b-test",
        )
    )
    _assert(provider_voice.playback_ownership == "host", "provider ownership drift")
    _assert(provider_voice.host_playback_stop_request_supported is True, "provider request support drift")
    _assert(provider_voice.host_playback_stop_ack_supported is True, "provider ack adoption missing")

    session = RealtimeSession()
    try:
        voice = session.capabilities.voice_output
        _assert(voice.playback_ownership == "host", "session ownership drift")
        _assert(voice.host_playback_stop_request_supported is True, "session request support missing")
        _assert(voice.host_playback_stop_ack_supported is True, "session ack support missing")
    finally:
        session.close()

    print("[OK] global/provider/session capabilities agree on host-owned coordination")


def check_flush_request_and_ack() -> None:
    from framework.output_control import (
        OutputFlushOutcome,
        OutputFlushRequest,
        TTSQueueState,
    )
    from framework.realtime import RealtimeEventType, RealtimeTurn
    from framework.realtime_event_payloads import AudioEventPayload
    from framework.realtime_session import RealtimeSession

    class _PlaybackRequiredSession(RealtimeSession):
        def get_tts_queue_state(self) -> TTSQueueState:
            return TTSQueueState(
                queued_count=0,
                is_playing=True,
                supports_flush=False,
                supports_provider_cancel=False,
                playback_stop_required=True,
                safe_message="host playback may still be active",
                public_metadata={"boundary": "test_host_playback"},
            )

    session = _PlaybackRequiredSession()
    try:
        turn = RealtimeTurn(input_text="host playback control")
        start = session.start_turn(turn)
        _assert(start.accepted, "test turn was not admitted")
        generation_id = start.generation_id
        _assert(generation_id is not None, "accepted turn missing generation")

        before = len(session.event_history)
        result = session.flush_output(
            OutputFlushRequest(
                turn_id=turn.turn_id,
                stop_playback=True,
                clear_queued_audio=True,
            )
        )
        _assert(
            result.outcome is OutputFlushOutcome.NOT_IMPLEMENTED,
            "host stop request must not turn unsupported FW queue flush into FLUSHED",
        )

        new_events = session.event_history[before:]
        event_types = tuple(event.type for event in new_events)
        _assert(
            event_types == (
                RealtimeEventType.OUTPUT_FLUSH_REQUESTED,
                RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST,
                RealtimeEventType.OUTPUT_FLUSH_UNSUPPORTED,
            ),
            f"unexpected host-stop flush event order: {event_types!r}",
        )
        requested = new_events[1]
        _assert(isinstance(requested.payload, AudioEventPayload), "request payload is not audio")
        _assert(requested.payload.host_stop_requested is True, "host stop request fact missing")
        _assert(requested.payload.host_stop_acknowledged is None, "request incorrectly implies ack")
        _assert(requested.generation_id == generation_id, "request generation correlation drift")
        _assert(
            requested.public_metadata.get("physical_playback_stop_confirmed") is False,
            "host stop request overclaimed physical stop",
        )

        # Complete the turn, then acknowledge after terminal to prove host-owned
        # playback coordination may outlive turn terminal.
        completed = session.run_turn(turn)
        _assert(completed.generation_id == generation_id, "terminal generation drift")

        count_before_ack = len(session.event_history)
        ack = session.acknowledge_host_playback_stop(
            turn_id=turn.turn_id,
            acknowledged=True,
        )
        _assert(ack is not None, "host acknowledgement was not accepted")
        _assert(ack.type is RealtimeEventType.PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST, "ack event type drift")
        _assert(ack.generation_id == generation_id, "post-terminal ack lost generation")
        _assert(isinstance(ack.payload, AudioEventPayload), "ack payload is not audio")
        _assert(ack.payload.host_stop_requested is True, "ack lost request fact")
        _assert(ack.payload.host_stop_acknowledged is True, "ack fact missing")
        _assert(
            ack.public_metadata.get("physical_playback_stop_confirmed") is False,
            "host acknowledgement overclaimed physical stop",
        )

        duplicate = session.acknowledge_host_playback_stop(
            turn_id=turn.turn_id,
            acknowledged=True,
        )
        _assert(duplicate is ack, "duplicate ack did not converge to first event")
        _assert(
            len(session.event_history) == count_before_ack + 1,
            "duplicate ack emitted a second canonical event",
        )
    finally:
        session.close()

    print("[OK] flush requests host stop truthfully and optional post-terminal ack is idempotent")


def check_empty_mock_preserved() -> None:
    from framework.output_control import OutputFlushOutcome
    from framework.realtime import RealtimeEventType
    from framework.realtime_session import RealtimeSession

    session = RealtimeSession()
    try:
        before = len(session.event_history)
        result = session.flush_output()
        _assert(result.outcome is OutputFlushOutcome.NOTHING_TO_FLUSH, "empty mock flush behavior changed")
        new_types = tuple(event.type for event in session.event_history[before:])
        _assert(
            RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST not in new_types,
            "empty mock queue emitted unnecessary host-stop request",
        )
    finally:
        session.close()

    print("[OK] empty mock queue preserves existing NOTHING_TO_FLUSH behavior")


def check_artifact_invalidation_event() -> None:
    from framework.realtime import RealtimeEventType, RealtimeTurn
    from framework.realtime_event_payloads import AudioEventPayload
    from framework.realtime_session import RealtimeSession

    session = RealtimeSession()
    try:
        turn = RealtimeTurn(input_text="artifact invalidation")
        result = session.run_turn(turn)
        event = session._record_voice_artifact_invalidation(
            turn_id=result.turn_id,
            generation_id=result.generation_id,
            invalidated_artifact_count=1,
        )
        _assert(event.type is RealtimeEventType.AUDIO_INVALIDATED, "invalidation event type drift")
        _assert(isinstance(event.payload, AudioEventPayload), "invalidation payload type drift")
        _assert(event.payload.invalidated is True, "invalidation fact missing")
        _assert(event.generation_id == result.generation_id, "invalidation generation correlation drift")
        _assert(
            event.public_metadata.get("physical_playback_stop_confirmed") is False,
            "artifact invalidation overclaimed physical stop",
        )
    finally:
        session.close()

    print("[OK] accepted artifact invalidation fact emits AUDIO_INVALIDATED without physical-stop claim")


def check_legacy_deprecation_boundary() -> None:
    import framework

    source = (PROJECT_ROOT / "tts/voice_engine.py").read_text(encoding="utf-8")
    root = (PROJECT_ROOT / "framework/__init__.py").read_text(encoding="utf-8")

    for marker in (
        'LEGACY_LOCAL_PLAYER_STATUS = "deprecated_internal_compatibility"',
        'LEGACY_LOCAL_PLAYER_REMOVAL_POLICY = "future_major_only_with_migration_notice"',
        "Legacy runtime compatibility boundary",
        "ffplay",
        "subprocess.Popen",
    ):
        _assert(marker in source, f"legacy deprecation marker missing: {marker}")

    _assert("VoiceEngine" not in framework.__all__, "VoiceEngine leaked root-public")
    _assert("from tts.voice_engine" not in root, "framework root imports legacy player")
    print("[OK] legacy VoiceEngine/ffplay is explicit deprecated internal compatibility")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    public = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")

    start = tasklist.index("## FW-RT6-6e — Host playback boundary")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [ ]") == 6 and section.count("- [x]") == 0, "Control B changed aggregate task state")
    _assert("FW-RT6-6e-A-ACCEPTANCE-SYNC:BEGIN" in tasklist, "Control A acceptance sync missing")

    for text in (contract, public, app):
        _assert("FW-RT6-6e-B-HOST-PLAYBACK-ADOPTION:BEGIN" in text, "Control B docs marker missing")

    for marker in (
        "host stop request => physical stop:",
        "False",
        "host acknowledgement => physical stop:",
        "artifact invalidation => physical stop:",
        "deprecated_internal_compatibility",
        "future major only with migration notice",
        "FW-RT6-6e tasklist:",
        "0 / 6 CLOSED",
        "Control C:",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"Control B contract marker missing: {marker}")

    print("[OK] docs record runtime adoption while FW-RT6-6e aggregate remains open")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_control_a_foundation()
    check_capability_adoption()
    check_flush_request_and_ack()
    check_empty_mock_preserved()
    check_artifact_invalidation_event()
    check_legacy_deprecation_boundary()
    check_docs_and_tasklist()

    print("v600_rt6_6e_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6e_control_b_status: implemented-awaiting-review")
    print("v600_rt6_6e_control_b_exact_surface: 8 files")
    print("v600_rt6_6e_playback_ownership_session_adopted: True / PASS")
    print("v600_rt6_6e_host_stop_request_runtime: True / PASS")
    print("v600_rt6_6e_host_stop_ack_runtime: optional / PASS")
    print("v600_rt6_6e_post_terminal_host_ack: True / PASS")
    print("v600_rt6_6e_duplicate_host_ack_idempotent: True / PASS")
    print("v600_rt6_6e_empty_mock_flush_preserved: True / PASS")
    print("v600_rt6_6e_artifact_invalidation_event: True / PASS")
    print("v600_rt6_6e_host_stop_request_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_host_stop_ack_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_artifact_invalidation_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_legacy_ffplay_root_public: False / PASS")
    print("v600_rt6_6e_legacy_local_player_status: deprecated_internal_compatibility")
    print("v600_rt6_6e_physical_playback_execution: False")
    print("v600_rt6_6e_provider_execution: False")
    print("v600_rt6_6e_network_execution: False")
    print("v600_rt6_6e_microphone_access: False")
    print("v600_rt6_6e_real_vts_execution: False")
    print("v600_rt6_6e_task_count: 0 / 6 CLOSED")
    print("v600_rt6_6e_control_c: NOT_AUTHORIZED")
    print("v600_rt6_6e_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
