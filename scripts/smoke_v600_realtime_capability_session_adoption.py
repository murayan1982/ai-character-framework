"""FW-RT6-1d Control C session capability adoption smoke.

Mock-safe: no provider, network, microphone, playback, VTube Studio, private
configuration, or application repository operation is performed.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "30166d7e6fdf4291d7ecd475b988bfd1492ae7a3"
EXPECTED_BASELINE_SUBJECT = "refactor/test: aggregate truthful global capabilities"
EXPECTED_BASELINE_PARENT = "a27b3e17ff7d8158859a5a624e3b03225384bfc8"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_capability_contract.md",
    "framework/capabilities.py",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_capability_session_adoption.py",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
)
DOC_MARKER = "FW-RT6-1d-C-SESSION-CAPABILITY-ADOPTION:BEGIN"


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _assert_history_and_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline HEAD")
    _require(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "unexpected Control B subject",
    )
    _require(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "unexpected Control B parent",
    )
    _require(_changed_paths() == EXPECTED_SURFACE, "Control C surface is not exact")
    _ok("accepted Control B history and exact six-file Control C surface conform")


def _assert_public_contract() -> None:
    import framework

    _require(len(framework.__all__) == 121, "root-public name count drifted")
    signature = inspect.signature(framework.create_realtime_session)
    _require(
        tuple(signature.parameters) == (
            "project_root",
            "public_metadata",
            "real_runtime_enabled",
        ),
        "create_realtime_session parameter names changed",
    )
    _require(
        all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in signature.parameters.values()
        ),
        "create_realtime_session must remain keyword-only",
    )
    _require(
        hasattr(framework.RealtimeSession, "capabilities"),
        "RealtimeSession.capabilities is missing",
    )
    _ok("root-public surface and realtime factory compatibility are preserved")


def _assert_global_snapshot_unchanged() -> None:
    import framework

    global_snapshot = framework.get_capabilities(
        real_tts_enabled=False
    ).realtime_snapshot
    _require(global_snapshot is not None, "global detailed snapshot is missing")
    _require(global_snapshot.snapshot_scope.value == "global", "global scope changed")
    _require(global_snapshot.session_id is None, "global snapshot gained a session ID")
    _require(global_snapshot.snapshot_generation == 1, "global generation changed")
    _require(global_snapshot.supports_motion is True, "global motion summary changed")
    _require(
        global_snapshot.public_metadata.get("session_wiring_adopted") is False,
        "Control B global metadata changed",
    )
    _ok("Control B global detailed snapshot remains unchanged")


def _assert_session_snapshot() -> None:
    import framework

    session = framework.create_realtime_session()
    snapshot = session.capabilities

    _require(
        isinstance(snapshot, framework.RealtimeCapabilitySnapshot),
        "session capabilities type is incorrect",
    )
    _require(snapshot.snapshot_scope.value == "session", "snapshot is not session-scoped")
    _require(snapshot.snapshot_generation == 1, "session generation must start at 1")
    _require(snapshot.session_id == session.info.session_id, "session IDs do not match")
    _require(snapshot is session.capabilities, "snapshot object must be stable")

    _require(snapshot.supports_text_chat is True, "text summary must be true")
    _require(snapshot.supports_voice_input is True, "voice input summary must be true")
    _require(snapshot.supports_voice_output is True, "voice output summary must be true")
    _require(snapshot.supports_motion is False, "motion must not be claimed as wired")
    _require(snapshot.real_runtime_enabled is False, "real runtime must remain false")
    _require(snapshot.hard_cancel_supported is False, "hard cancel overclaim")
    _require(snapshot.tts_queue_flush_supported is False, "queue flush overclaim")

    _require(snapshot.text_generation.runtime.fake_runtime is True, "text fake runtime missing")
    _require(snapshot.text_generation.streaming_supported is False, "session streaming overclaim")
    _require(
        snapshot.text_generation.cooperative_cancel_supported is False,
        "cooperative cancel overclaim",
    )
    _require(
        snapshot.text_generation.provider_hard_cancel_supported is False,
        "provider hard cancel overclaim",
    )

    _require(snapshot.voice_input.runtime.fake_runtime is True, "voice input fake runtime missing")
    _require(snapshot.voice_input.audio_chunk_input_supported is False, "audio chunk overclaim")
    _require(snapshot.voice_input.partial_transcript_supported is False, "partial overclaim")
    _require(snapshot.voice_input.final_transcript_supported is True, "final transcript missing")
    _require(snapshot.voice_input.accepted_audio_formats == (), "audio formats overclaim")

    _require(snapshot.voice_output.runtime.fake_runtime is True, "voice output fake runtime missing")
    _require(snapshot.voice_output.streaming_audio_supported is False, "streaming audio overclaim")
    _require(snapshot.voice_output.generation_cancel_supported is False, "generation cancel overclaim")
    _require(snapshot.voice_output.pending_flush_supported is False, "pending flush overclaim")
    _require(
        snapshot.voice_output.active_audio_invalidation_supported is False,
        "audio invalidation overclaim",
    )

    _require(snapshot.motion.runtime.runtime_available is False, "motion runtime overclaim")
    _require(
        snapshot.motion.runtime.unavailable_reason == "not_wired_to_realtime_session",
        "motion unavailable reason mismatch",
    )
    _require(snapshot.motion.completion_event_supported is False, "motion event overclaim")

    before = session.capabilities
    result = session.run_turn(input_text="capability contract")
    _require(result.is_terminal is True, "mock turn did not complete")
    _require(session.capabilities is before, "snapshot changed after a turn")
    _require(session.capabilities.snapshot_generation == 1, "generation changed after turn")
    session.close()
    _require(session.capabilities is before, "snapshot changed after close")
    _ok("session-scoped identity, stage facts, and lifetime stability conform")


def _assert_real_runtime_request_is_truthful() -> None:
    import framework

    session = framework.create_realtime_session(real_runtime_enabled=True)
    snapshot = session.capabilities
    _require(session.info.real_runtime_enabled is False, "info overclaims real runtime")
    _require(snapshot.real_runtime_enabled is False, "snapshot overclaims real runtime")
    _require(
        snapshot.public_metadata.get("real_runtime_requested") is True,
        "real runtime request intent was not recorded",
    )
    _require(
        snapshot.public_metadata.get("real_runtime_available") is False,
        "real runtime availability overclaim",
    )
    _require(
        session.info.public_metadata.get("real_runtime_requested") is True,
        "session info request intent missing",
    )
    session.close()
    _ok("real runtime request intent is separated from actual availability")


def _assert_docs() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_capability_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(DOC_MARKER in text, f"{relative} missing Control C marker")
        for phrase in (
            "snapshot generation: 1 / stable",
            "real unified runtime available: False",
            "RealtimeSession.capabilities",
        ):
            _require(phrase in text, f"{relative} missing phrase: {phrase}")
    _ok("capability and host-app docs record truthful session adoption")


def _assert_import_safety() -> None:
    loaded = tuple(sys.modules)
    forbidden = sorted(
        name
        for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _require(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    _ok("session capability adoption stayed provider/runtime execution safe")


def main() -> None:
    _assert_history_and_surface()
    _assert_public_contract()
    _assert_global_snapshot_unchanged()
    _assert_session_snapshot()
    _assert_real_runtime_request_is_truthful()
    _assert_docs()
    _assert_import_safety()

    print("v600_rt6_1d_control_c_status: implemented-awaiting-review")
    print("v600_rt6_1d_control_c_exact_change_surface: True")
    print("v600_rt6_1d_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_1d_control_c_session_snapshot: True")
    print("v600_rt6_1d_control_c_snapshot_scope: session")
    print("v600_rt6_1d_control_c_snapshot_generation: 1 / stable")
    print("v600_rt6_1d_control_c_real_runtime_request_separated: True")
    print("v600_rt6_1d_control_c_motion_session_wiring: False")
    print("v600_rt6_1d_control_c_global_snapshot_changed: False")
    print("v600_rt6_1d_control_c_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_1d_control_c_session_adoption: OK")


if __name__ == "__main__":
    main()
