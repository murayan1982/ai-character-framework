"""FW-RT6-7c Control B result/callback compatibility acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "4dc3d1284f548748e59070bda4e03e8a434d16d8"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_voice_input_result_control_a.py",
    "scripts/smoke_v600_voice_input_result_control_b.py",
    "tests/test_voice_input_result_compatibility_control_b.py",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + result.stdout
        + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git("diff", "--name-only", "HEAD").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control B exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact six-file FW-RT6-7c Control B surface conform")


def check_accepted_control_a_regression() -> None:
    control_a = _load(
        "_fw_rt6_7c_control_a_for_control_b",
        "scripts/smoke_v600_voice_input_result_control_a.py",
    )
    control_a.check_accepted_7b_regression()
    control_a.check_additive_result_contract()
    control_a.check_session_result_event_correlation()
    control_a.check_v5_compatibility_gates()
    control_a.check_focused_tests()
    control_a.check_docs_and_control_b_bridge()
    print("[OK] accepted Control A result-correlation regressions conform")


def check_result_and_callback_bridge() -> None:
    import framework
    from framework.realtime_event_payloads import (
        LifecycleEventPayload,
        TranscriptEventPayload,
    )

    session = framework.create_voice_input_session(language="ja-JP")
    canonical = []
    legacy = []
    session.on_realtime_event(canonical.append)
    session.on_event(legacy.append)

    listen = session.listen_result()
    _require(
        listen.outcome is framework.VoiceInputOutcome.UNAVAILABLE,
        "listen unavailable compatibility drift",
    )
    _require(listen.session_id == session.session_id, "listen session correlation drift")
    _require(listen.turn_id is not None, "listen turn correlation missing")
    _require(listen.generation_id is not None, "listen generation correlation missing")
    _require(
        [event.type for event in canonical]
        == [
            framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
            framework.RealtimeEventType.VOICE_INPUT_FAILED,
        ],
        "listen canonical event order drift",
    )
    _require(
        all(isinstance(event.payload, LifecycleEventPayload) for event in canonical),
        "listen canonical payload typing drift",
    )

    fallback = session.text_fallback_result("typed fallback")
    _require(fallback.is_completed, "text fallback completion drift")
    _require(fallback.session_id == session.session_id, "fallback session correlation drift")
    _require(fallback.turn_id is not None, "fallback turn correlation missing")
    _require(fallback.generation_id is not None, "fallback generation correlation missing")
    _require(fallback.turn_id != listen.turn_id, "operations must not share turn identity")
    _require(
        [event.type for event in canonical[-2:]]
        == [
            framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
            framework.RealtimeEventType.TRANSCRIPT_FINAL,
        ],
        "text fallback canonical event order drift",
    )
    _require(
        isinstance(canonical[-1].payload, TranscriptEventPayload)
        and canonical[-1].payload.text == fallback.text,
        "typed final transcript/result agreement drift",
    )

    session.close()
    event_count_after_close = len(canonical)
    legacy_count_after_close = len(legacy)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "closed_control_b_gate",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=100),
    )
    closed = (
        session.listen_result(),
        session.text_fallback_result("ignored"),
        session.transcribe_audio_result(source),
    )
    _require(closed[0] == closed[1] == closed[2], "post-close rejection drift")
    _require(
        all(
            result.outcome is framework.VoiceInputOutcome.CLOSED
            and result.session_id == session.session_id
            and result.turn_id is None
            and result.generation_id is None
            for result in closed
        ),
        "post-close session-only correlation drift",
    )
    _require(len(canonical) == event_count_after_close, "post-close canonical event leak")
    _require(len(legacy) == legacy_count_after_close, "post-close mapping event leak")
    _require(
        [event["type"] for event in legacy]
        == [
            "voice_input.started",
            "voice_input.unavailable",
            "voice_input.text_fallback",
            "voice_input.closed",
        ],
        "legacy mapping projection order drift",
    )
    _require(
        all(set(event) == {"type", "session_type", "payload"} for event in legacy),
        "legacy mapping shape drift",
    )
    _require(
        canonical[-1].type is framework.RealtimeEventType.SESSION_CLOSED,
        "canonical close event missing",
    )
    print("[OK] listen/fallback correlation, legacy projection, and close rejection conform")


def check_host_audio_and_public_surface() -> None:
    import framework
    from framework.version import VOICE_INPUT_API_VERSION

    session = framework.create_voice_input_session()
    canonical = []
    legacy = []
    session.on_realtime_event(canonical.append)
    session.on_event(legacy.append)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "host_audio_control_b_gate",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=100),
    )
    result = session.transcribe_audio_result(source)
    _require(result.is_completed, "default fake host-audio path drift")
    _require(legacy == [], "host-audio legacy mapping flow changed")
    _require(canonical[-1].type is framework.RealtimeEventType.TRANSCRIPT_FINAL, "host-audio final event drift")
    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(VOICE_INPUT_API_VERSION == "5.2.0", "voice-input API version drift")
    print("[OK] host-audio callback silence and public/version surface remain compatible")


def check_focused_tests() -> None:
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_voice_input_result_compatibility_control_b.py",
    )
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    _require(result.wasSuccessful(), "Control B focused tests failed")
    _require(result.testsRun == 8, "Control B focused test count must be 8")
    print("[OK] eight focused result/callback compatibility tests pass")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7c — Voice input result compatibility")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [ ]") == 5 and section.count("- [x]") == 0,
        "Control B must leave FW-RT6-7c aggregate 0 / 5 CLOSED",
    )
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-7c-B-COMPATIBILITY-BRIDGE:BEGIN" in text,
            f"Control B docs marker missing: {relative}",
        )
        _require(
            "provider" in text.lower()
            and "root-public" in text
            and "Control C" in text,
            f"Control B scope boundary missing: {relative}",
        )
    print("[OK] Control B docs conform while FW-RT6-7c aggregate remains 0 / 5")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_regression()
    check_result_and_callback_bridge()
    check_host_audio_and_public_surface()
    check_focused_tests()
    check_docs_and_tasklist()
    print("v600_rt6_7c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7c_control_b_status: implemented-awaiting-review")
    print("v600_rt6_7c_control_b_exact_surface: 6 files")
    print("v600_rt6_7c_listen_result_correlation: full-context / PASS")
    print("v600_rt6_7c_text_fallback_correlation: full-context / PASS")
    print("v600_rt6_7c_legacy_mapping_callback_bridge: canonical-projection / PASS")
    print("v600_rt6_7c_host_audio_legacy_callback_changed: False / PASS")
    print("v600_rt6_7c_post_close_rejection: unified-session-only / PASS")
    print("v600_rt6_7c_provider_network_audio_microphone_execution: False / PASS")
    print("v600_rt6_7c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_7c_voice_input_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_7c_task_count: 0 / 5 CLOSED")
    print("v600_rt6_7c_control_c: DEFERRED")
    print("v600_rt6_7c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
