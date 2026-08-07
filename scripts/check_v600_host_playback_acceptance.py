"""FW-RT6-6e Control C aggregate host-playback acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "eefa693ff3453e43d4341270bf92d780f370a477"
EXPECTED_SURFACE = {
    "docs/v600_realtime_voice_output_contract.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_host_playback_acceptance.py",
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


def _load_script(module_name: str, relative_path: str):
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control C exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] exact three-file FW-RT6-6e Control C aggregate surface conforms")


def check_accepted_control_a_b_runtime() -> None:
    control_b = _load_script(
        "_fw_rt6_6e_control_b_accepted",
        "scripts/smoke_v600_host_playback_control_b.py",
    )

    # Reuse accepted model/runtime checks directly. Do not call historical
    # docs/tasklist checks because Control C intentionally changes 0/6 to 6/6.
    control_b.check_control_a_foundation()
    control_b.check_capability_adoption()
    control_b.check_flush_request_and_ack()
    control_b.check_empty_mock_preserved()
    control_b.check_artifact_invalidation_event()
    control_b.check_legacy_deprecation_boundary()

    print("[OK] accepted Control A+B host-playback model/runtime checks conform")


def check_aggregate_truthfulness() -> None:
    import framework
    from framework.capabilities import get_capabilities
    from framework.realtime import RealtimeEventType
    from framework.realtime_session import RealtimeSession

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert("VoiceEngine" not in framework.__all__, "legacy VoiceEngine leaked root-public")

    snapshot = get_capabilities(real_tts_enabled=False).realtime_snapshot
    _assert(snapshot is not None, "global realtime snapshot missing")
    voice = snapshot.voice_output
    _assert(voice.playback_ownership == "host", "public playback ownership drift")
    _assert(voice.host_playback_stop_request_supported is True, "host request support missing")
    _assert(voice.host_playback_stop_ack_supported is True, "optional host ack support missing")

    _assert(
        RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST.value
        == "realtime.playback_stop.requested_to_host",
        "host stop request event drift",
    )
    _assert(
        RealtimeEventType.PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST.value
        == "realtime.playback_stop.acknowledged_by_host",
        "host stop acknowledgement event drift",
    )
    _assert(
        RealtimeEventType.AUDIO_INVALIDATED.value == "realtime.audio.invalidated",
        "artifact invalidation event drift",
    )

    session = RealtimeSession()
    try:
        _assert(
            session.capabilities.voice_output.playback_ownership == "host",
            "session playback ownership drift",
        )
    finally:
        session.close()

    legacy_source = (PROJECT_ROOT / "tts/voice_engine.py").read_text(encoding="utf-8")
    for marker in (
        'LEGACY_LOCAL_PLAYER_STATUS = "deprecated_internal_compatibility"',
        'LEGACY_LOCAL_PLAYER_REMOVAL_POLICY = "future_major_only_with_migration_notice"',
        '"ffplay"',
    ):
        _assert(marker in legacy_source, f"legacy boundary marker missing: {marker}")

    print("[OK] aggregate ownership/event/deprecation truthfulness conforms")


def check_tasklist_and_docs() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md"
    ).read_text(encoding="utf-8")

    start = tasklist.index("## FW-RT6-6e — Host playback boundary")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [x]") == 6, "FW-RT6-6e must be 6 / 6 accepted-candidate")
    _assert(section.count("- [ ]") == 0, "FW-RT6-6e open task remains")

    next_start = tasklist.index("## FW-RT6-7a — VoiceInputSession capability correction")
    next_end = tasklist.index("\n---\n", next_start)
    next_section = tasklist[next_start:next_end]
    _assert(next_section.count("- [ ]") == 6, "FW-RT6-7a must remain 0 / 6 CLOSED")
    _assert(next_section.count("- [x]") == 0, "FW-RT6-7a was opened by Control C")

    for text in (tasklist, contract):
        _assert(
            "FW-RT6-6e-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )

    required = (
        "FW-RT6-6e tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "host playback physical stop claimed: False",
        "artifact invalidation emitted: AUDIO_INVALIDATED",
        "legacy VoiceEngine / ffplay root-public: False",
        "runtime source changed: False",
        "FW-RT6-7a tasks: 0 / 6 CLOSED",
        "next checkpoint: FW-RT6-7a / NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    )
    for marker in required:
        _assert(
            marker in tasklist or marker in contract,
            f"aggregate acceptance marker missing: {marker}",
        )

    print("[OK] all six FW-RT6-6e tasks are accepted-candidates; FW-RT6-7a remains closed")


def check_runtime_sources_unchanged() -> None:
    actual = _changed_paths()
    runtime_changed = {
        path
        for path in actual
        if path.startswith("framework/")
        or path.startswith("tts/")
        or path.startswith("core/")
    }
    _assert(not runtime_changed, f"Control C changed runtime sources: {sorted(runtime_changed)!r}")
    print("[OK] Control C introduces no runtime source change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_accepted_control_a_b_runtime()
    check_aggregate_truthfulness()
    check_tasklist_and_docs()
    check_runtime_sources_unchanged()

    print("v600_rt6_6e_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6e_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6e_control_c_status: implemented-awaiting-review")
    print("v600_rt6_6e_control_c_exact_surface: 3 files")
    print("v600_rt6_6e_playback_ownership: host / PASS")
    print("v600_rt6_6e_host_stop_request_event_runtime: True / PASS")
    print("v600_rt6_6e_host_stop_ack_optional: True / PASS")
    print("v600_rt6_6e_host_playback_physical_stop_claimed: False / PASS")
    print("v600_rt6_6e_artifact_invalidation_emitted: True / PASS")
    print("v600_rt6_6e_artifact_invalidation_implies_physical_stop: False / PASS")
    print("v600_rt6_6e_legacy_ffplay_root_public: False / PASS")
    print("v600_rt6_6e_legacy_local_player_status: deprecated_internal_compatibility")
    print("v600_rt6_6e_runtime_changed: False")
    print("v600_rt6_6e_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6e_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_7a_task_count: 0 / 6 CLOSED")
    print("v600_rt6_6e_provider_execution: False")
    print("v600_rt6_6e_network_execution: False")
    print("v600_rt6_6e_microphone_access: False")
    print("v600_rt6_6e_playback_execution: False")
    print("v600_rt6_6e_real_vts_execution: False")
    print("v600_rt6_6e_next_checkpoint: FW-RT6-7a / NOT_AUTHORIZED")
    print("v600_rt6_6e_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
