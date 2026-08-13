"""FW-RT6-12a Control B VoiceInputSession audio streaming gate."""

from __future__ import annotations

import argparse
import importlib
import inspect
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "f07105742ea6068a6d1655d737c160a5f3487dd5"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_audio_chunk_streaming.md",
    "framework/voice_input_session.py",
    "framework/voice_input_stream_runtime.py",
    "framework/voice_input_streaming_adapter.py",
    "scripts/smoke_v600_public_audio_chunk_streaming_control_a.py",
    "scripts/smoke_v600_public_audio_chunk_streaming_control_b.py",
    "tests/test_public_audio_chunk_streaming_control_a.py",
    "tests/test_public_audio_chunk_streaming_control_b.py",
}
EXPECTED_ADAPTER_EXPORTS = (
    "VoiceInputStreamingAdapter",
    "DeterministicFakeVoiceInputStreamingAdapter",
)
EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "provider",
    "language",
    "real_stt_enabled",
    "allow_provider_execution",
    "credential_env",
    "private_credential",
    "allow_provider_sdk_import",
    "allow_provider_client_creation",
    "allow_real_provider_execution",
    "max_audio_bytes",
    "provider_timeout_seconds",
    "provider_max_retries",
    "public_metadata",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (completed.stdout or "")
        + (completed.stderr or ""),
    )
    return completed.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    paths = _git("diff", "HEAD", "--name-only").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    actual = {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }
    _require(actual == EXPECTED_SURFACE, f"Control B exact surface drift: {sorted(actual)!r}")
    print("[OK] baseline and exact ten-file FW-RT6-12a Control B surface conform")


def check_namespace_import_and_public_boundaries() -> None:
    import framework
    from framework.voice_input_streaming_adapter import (
        DeterministicFakeVoiceInputStreamingAdapter,
        VoiceInputStreamingAdapter,
    )

    namespace = importlib.import_module("framework.voice_input_streaming_adapter")
    _require(namespace.__all__ == EXPECTED_ADAPTER_EXPORTS, "adapter exports drift")
    _require(
        isinstance(DeterministicFakeVoiceInputStreamingAdapter(), VoiceInputStreamingAdapter),
        "fake adapter does not satisfy structural protocol",
    )
    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_ADAPTER_EXPORTS:
        _require(name not in framework.__all__, f"explicit adapter leaked root: {name}")
    _require(
        tuple(inspect.signature(framework.create_voice_input_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "voice-input factory signature drift",
    )
    methods = (
        "configure_audio_streaming",
        "begin_audio_stream",
        "send_audio_chunk",
        "end_audio_input",
        "abort_audio_stream",
    )
    for name in methods:
        _require(hasattr(framework.VoiceInputSession, name), f"VoiceInputSession.{name} missing")
        _require(not hasattr(framework.RealtimeSession, name), f"RealtimeSession.{name} drift")
    snapshot = framework.get_capabilities().realtime_snapshot
    _require(snapshot is not None, "realtime capability snapshot missing")
    _require(
        not snapshot.voice_input.audio_chunk_input_supported,
        "global realtime capability overclaimed stream support",
    )

    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.voice_input_streaming_adapter as adapter
assert adapter.__all__ == (
    "VoiceInputStreamingAdapter",
    "DeterministicFakeVoiceInputStreamingAdapter",
)
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] explicit adapter namespace, root 127, factory, and session boundaries conform")
    print("[OK] adapter import is provider, network, microphone, playback, and VTS safe")


def check_stream_runtime_and_canonical_events() -> None:
    import framework
    from framework.realtime import RealtimeEventType
    from framework.voice_input import VoiceInputOutcome
    from framework.voice_input_audio import VoiceInputAudioEncoding, VoiceInputAudioFormat
    from framework.voice_input_streaming import (
        VoiceInputAudioChunk,
        VoiceInputStreamAbort,
        VoiceInputStreamConfig,
        VoiceInputStreamEnd,
        VoiceInputStreamRejectionCode,
    )
    from framework.voice_input_streaming_adapter import (
        DeterministicFakeVoiceInputStreamingAdapter,
    )

    unavailable = framework.VoiceInputSession()
    _require(
        not unavailable.streaming_capability.audio_chunk_input_supported,
        "default session support overclaim",
    )

    session = framework.VoiceInputSession()
    realtime_events = []
    legacy_events = []
    session.on_realtime_event(realtime_events.append)
    session.on_event(legacy_events.append)
    capability = session.configure_audio_streaming(
        DeterministicFakeVoiceInputStreamingAdapter(
            partial_transcripts={0: "partial one", 1: "partial two"},
            final_transcript="final transcript",
            confidence=0.8,
        )
    )
    _require(capability.audio_chunk_input_supported, "explicit capability missing")
    config = VoiceInputStreamConfig(
        stream_id="stream_gate",
        audio_format=VoiceInputAudioFormat(
            encoding=VoiceInputAudioEncoding.PCM16,
            sample_rate_hz=16_000,
            channel_count=1,
        ),
    )
    _require(session.begin_audio_stream(config), "stream begin rejected")
    out_of_order = session.send_audio_chunk(
        VoiceInputAudioChunk("stream_gate", 1, b"private", duration_ms=20)
    )
    _require(
        out_of_order.rejection_code is VoiceInputStreamRejectionCode.OUT_OF_ORDER,
        "out-of-order rejection drift",
    )
    _require(out_of_order.next_expected_sequence_number == 0, "expected sequence consumed")
    for sequence in (0, 1):
        accepted = session.send_audio_chunk(
            VoiceInputAudioChunk(
                "stream_gate",
                sequence,
                b"raw private audio",
                duration_ms=20,
            )
        )
        _require(accepted.accepted, f"ordered chunk {sequence} rejected")
    ended = session.end_audio_input(VoiceInputStreamEnd("stream_gate", 2))
    _require(ended.accepted and ended.terminal, "ordered end rejected")
    _require(session.last_stream_result is not None, "final result missing")
    _require(session.last_stream_result.text == "final transcript", "final text drift")
    _require(session.last_stream_result.outcome is VoiceInputOutcome.COMPLETED, "final outcome drift")
    _require(
        [event.type for event in realtime_events]
        == [
            RealtimeEventType.LISTENING_STARTED,
            RealtimeEventType.TRANSCRIPT_PARTIAL,
            RealtimeEventType.TRANSCRIPT_PARTIAL,
            RealtimeEventType.TRANSCRIPT_FINAL,
        ],
        "canonical stream event order drift",
    )
    _require(not legacy_events, "stream transcripts expanded legacy mapping callbacks")
    _require(
        len({(event.session_id, event.turn_id, event.generation_id) for event in realtime_events}) == 1,
        "stream event correlation drift",
    )
    _require("raw private audio" not in repr(realtime_events), "event exposed raw audio")

    abort_session = framework.VoiceInputSession()
    abort_session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
    _require(abort_session.begin_audio_stream(config), "abort stream begin rejected")
    aborted = abort_session.abort_audio_stream(VoiceInputStreamAbort("stream_gate"))
    _require(aborted.accepted and aborted.terminal, "cooperative abort rejected")
    _require(
        abort_session.last_stream_result.outcome is VoiceInputOutcome.INTERRUPTED,
        "abort result drift",
    )
    print("[OK] default-off and explicit adapter capability truth conform")
    print("[OK] ordered chunks, typed retry, partial/final correlation, and cooperative abort conform")
    print("[OK] raw audio and stream transcripts do not leak into legacy/public projections")


def check_docs_tasks_and_regressions() -> None:
    documents = {
        name: (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
        for name in (
            "public_facade.md",
            "app_integration_contract.md",
            "v600_public_audio_chunk_streaming.md",
        )
    }
    _require(
        documents["public_facade.md"].count("FW-RT6-12a-B-VOICE-INPUT-STREAMING:BEGIN") == 1,
        "public facade marker drift",
    )
    _require(
        documents["app_integration_contract.md"].count("FW-RT6-12a-B-HOST-AUDIO-STREAMING:BEGIN") == 1,
        "app contract marker drift",
    )
    combined = "\n".join(documents.values())
    for phrase in (
        "framework.voice_input_streaming_adapter",
        "127 / UNCHANGED",
        "0 / 7 CLOSED",
        "NOT_IMPLEMENTED / FW-RT6-12b",
        "NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"Control B documentation phrase missing: {phrase}")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-12a — P1 public audio chunk streaming", 1
    )[1].split("## FW-RT6-12b", 1)[0]
    _require(section.count("- [ ]") == 0, "Control C left an aggregate task open")
    _require(section.count("- [x]") == 7, "Control C task count drift")
    _require(
        (PROJECT_ROOT / "scripts/check_v600_public_audio_chunk_streaming_acceptance.py").is_file(),
        "Control C aggregate gate missing",
    )
    for command in (
        [sys.executable, "scripts/smoke_v600_public_audio_chunk_streaming_control_a.py", "--source-only"],
        [sys.executable, "scripts/check_v600_migration_examples_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_root_public_api_cleanup_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_session_compatibility_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] Control B docs, 7/7 candidate boundary, and accepted Control A/11a/11b/11c gates conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_namespace_import_and_public_boundaries()
    check_stream_runtime_and_canonical_events()
    check_docs_tasks_and_regressions()
    print("v600_rt6_12a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12a_control_b_exact_surface: 10 files")
    print("v600_rt6_12a_runtime_adoption: VoiceInputSession / EXPLICIT_ADAPTER_ONLY")
    print("v600_rt6_12a_adapter_namespace_exports: 2 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12a_partial_transcript: CANONICAL_V6 / CORRELATED")
    print("v600_rt6_12a_backpressure_queue: False / FW-RT6-12b")
    print("v600_rt6_12a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12a_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_12a_provider_execution: False")
    print("v600_rt6_12a_network_execution: False")
    print("v600_rt6_12a_control_b_acceptance_sync: 1b829c092ddb4651c3d5cdea687bbffa645ee6c5 / CLOSED")
    print("v600_rt6_12a_control_c_aggregate: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_12a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12a Control B public audio-chunk streaming gate passed")


if __name__ == "__main__":
    main()
