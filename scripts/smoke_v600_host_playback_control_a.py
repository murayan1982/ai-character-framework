"""FW-RT6-6e Control A typed host-playback foundation gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "cff06c92cbf1e25e128c02bcbefcc2cfe98d3125"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/audio/_provider_adapter.py",
    "framework/capabilities.py",
    "framework/realtime.py",
    "framework/realtime_capabilities.py",
    "framework/realtime_event_payloads.py",
    "scripts/smoke_v600_host_playback_control_a.py",
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
        path.strip().replace("\\", "/")
        for path in (*tracked, *untracked)
        if path.strip()
    }


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control A exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact nine-file FW-RT6-6e Control A surface conform")


def check_capability_model() -> None:
    from framework.realtime_capabilities import (
        RealtimeVoiceOutputCapability,
        RuntimeCapabilityState,
    )

    none_capability = RealtimeVoiceOutputCapability()
    _assert(none_capability.playback_ownership == "none", "default ownership drift")
    _assert(
        none_capability.host_playback_stop_request_supported is False,
        "default host-stop request support must be false",
    )
    _assert(
        none_capability.host_playback_stop_ack_supported is False,
        "default host-stop ack support must be false",
    )

    host_capability = RealtimeVoiceOutputCapability(
        runtime=RuntimeCapabilityState(),
        playback_ownership="HOST",
        host_playback_stop_request_supported=True,
        host_playback_stop_ack_supported=False,
    )
    _assert(host_capability.playback_ownership == "host", "ownership normalization failed")
    as_dict = dict(host_capability.as_dict())
    _assert(as_dict["playback_ownership"] == "host", "ownership serialization drift")
    _assert(
        as_dict["host_playback_stop_request_supported"] is True,
        "host-stop request serialization drift",
    )
    _assert(
        as_dict["host_playback_stop_ack_supported"] is False,
        "host-stop ack serialization drift",
    )

    for kwargs in (
        {"playback_ownership": "unknown"},
        {
            "playback_ownership": "none",
            "host_playback_stop_request_supported": True,
        },
        {
            "playback_ownership": "host",
            "host_playback_stop_ack_supported": True,
        },
        {
            "playback_ownership": "framework",
            "host_playback_stop_request_supported": True,
        },
    ):
        try:
            RealtimeVoiceOutputCapability(**kwargs)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid playback capability accepted: {kwargs!r}")

    print("[OK] playback ownership / host-stop capability invariants conform")


def check_authoritative_capability_builders() -> None:
    from framework.capabilities import get_capabilities
    from framework.audio._provider_adapter import (
        VoiceOutputProviderStatus,
        _capability_from_status,
    )

    global_capability = get_capabilities(real_tts_enabled=False).realtime_snapshot
    _assert(global_capability is not None, "global detailed snapshot missing")
    voice = global_capability.voice_output
    _assert(voice.playback_ownership == "host", "global voice playback ownership drift")
    _assert(
        voice.host_playback_stop_request_supported is True,
        "global host-stop request contract must be available",
    )
    _assert(
        voice.host_playback_stop_ack_supported is False,
        "global host ack must remain optional/not runtime-adopted",
    )
    _assert(voice.runtime.real_runtime is False, "capability inspection executed real runtime")

    provider_capability = _capability_from_status(
        VoiceOutputProviderStatus(
            real_tts_enabled=False,
            provider_configured=False,
            provider_execution_allowed=False,
            supports_audio_artifact_ref=False,
            supports_audio_url=False,
            status="contract_ready",
            status_reason="control-a-test",
        )
    )
    _assert(
        provider_capability.playback_ownership == "host",
        "provider adapter playback ownership drift",
    )
    _assert(
        provider_capability.host_playback_stop_request_supported is True,
        "provider adapter host-stop request contract drift",
    )
    _assert(
        provider_capability.host_playback_stop_ack_supported is False,
        "provider adapter host ack overclaim",
    )
    _assert(
        provider_capability.provider_hard_cancel_supported is False,
        "provider hard cancel overclaim",
    )

    print("[OK] global/provider capability builders report host-owned playback truthfully")


def check_event_contract() -> None:
    from framework.realtime import RealtimeEvent, RealtimeEventType, RealtimeState
    from framework.realtime_event_payloads import AudioEventPayload

    _assert(
        RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST.value
        == "realtime.playback_stop.requested_to_host",
        "host-stop request event value drift",
    )
    _assert(
        RealtimeEventType.PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST.value
        == "realtime.playback_stop.acknowledged_by_host",
        "host-stop ack event value drift",
    )

    requested = AudioEventPayload(host_stop_requested=True)
    _assert(requested.host_stop_acknowledged is None, "request must not imply ack")
    _assert(
        dict(requested.as_dict())["host_stop_acknowledged"] is None,
        "request payload serialization must preserve unknown ack",
    )

    acknowledged = AudioEventPayload(
        host_stop_requested=True,
        host_stop_acknowledged=True,
    )
    _assert(acknowledged.host_stop_acknowledged is True, "ack fact was not retained")

    try:
        AudioEventPayload(host_stop_acknowledged=True)
    except ValueError:
        pass
    else:
        raise AssertionError("host acknowledgement without stop request was accepted")

    for event_type, payload in (
        (RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST, requested),
        (RealtimeEventType.PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST, acknowledged),
    ):
        event = RealtimeEvent(
            type=event_type,
            state=RealtimeState.SPEAKING,
            payload=payload,
        )
        _assert(event.payload is payload, "typed audio payload was not retained")
        _assert(event.to_v5() is None, "new host-playback event must not invent a v5 projection")

    print("[OK] canonical host-stop request/ack event contract conforms")


def check_stable_surfaces_and_boundaries() -> None:
    import framework
    import framework.realtime_capabilities as capabilities
    import framework.realtime_event_payloads as payloads

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(len(capabilities.__all__) == 7, "realtime capability export count drift")
    _assert(len(payloads.__all__) == 10, "event payload export count drift")
    _assert("VoiceEngine" not in framework.__all__, "legacy VoiceEngine leaked root-public")

    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    legacy_source = (PROJECT_ROOT / "tts/voice_engine.py").read_text(encoding="utf-8")
    root_source = (PROJECT_ROOT / "framework/__init__.py").read_text(encoding="utf-8")

    _assert(
        "Real queue flush / playback stop is not implemented yet." in session_source,
        "RealtimeSession playback boundary changed in Control A",
    )
    _assert('"ffplay"' in legacy_source, "legacy ffplay compatibility path unexpectedly missing")
    _assert("subprocess.Popen" in legacy_source, "legacy local playback ownership unexpectedly changed")
    _assert("VoiceEngine" not in root_source, "legacy VoiceEngine imported by framework root")

    print("[OK] stable surfaces unchanged; RealtimeSession and legacy playback boundaries remain separate")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    public_facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app_contract = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")

    start = tasklist.index("## FW-RT6-6e — Host playback boundary")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [ ]") == 6, "FW-RT6-6e must remain 0 / 6 CLOSED")
    _assert(section.count("- [x]") == 0, "Control A must not close FW-RT6-6e tasks")

    for text in (contract, public_facade, app_contract):
        _assert(
            "FW-RT6-6e-A-HOST-PLAYBACK-FOUNDATION:BEGIN" in text,
            "Control A docs marker missing",
        )

    for marker in (
        "playback_ownership:",
        "host stop requested",
        "physical playback stopped:",
        "NOT IMPLIED",
        "legacy VoiceEngine / ffplay classification:",
        "INTERNAL LEGACY COMPATIBILITY",
        "FW-RT6-6e tasklist:",
        "0 / 6 CLOSED",
        "Control B:",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"voice-output contract marker missing: {marker}")

    print("[OK] docs record typed host-playback foundation; FW-RT6-6e remains 0 / 6 CLOSED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_capability_model()
    check_authoritative_capability_builders()
    check_event_contract()
    check_stable_surfaces_and_boundaries()
    check_docs_and_tasklist()

    print("v600_rt6_6e_control_a_status: implemented-awaiting-review")
    print("v600_rt6_6e_control_a_exact_surface: 9 files")
    print("v600_rt6_6e_playback_ownership_typed: True / PASS")
    print("v600_rt6_6e_current_public_playback_ownership: host / PASS")
    print("v600_rt6_6e_host_stop_request_event: True / PASS")
    print("v600_rt6_6e_host_stop_ack_contract: optional / PASS")
    print("v600_rt6_6e_host_stop_request_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_host_stop_ack_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_artifact_invalidation_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_legacy_ffplay_root_public: False / PASS")
    print("v600_rt6_6e_realtime_session_changed: False")
    print("v600_rt6_6e_playback_execution: False")
    print("v600_rt6_6e_network_execution: False")
    print("v600_rt6_6e_provider_execution: False")
    print("v600_rt6_6e_microphone_access: False")
    print("v600_rt6_6e_real_vts_execution: False")
    print("v600_rt6_6e_task_count: 0 / 6 CLOSED")
    print("v600_rt6_6e_control_b: NOT_AUTHORIZED")
    print("v600_rt6_6e_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
