"""FW-RT6-12a Control C aggregate public audio streaming gate.

The gate is offline-safe. It aggregates accepted Control A/B contracts and
tests without changing runtime, provider, application, or backpressure policy.
"""

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

EXPECTED_HEAD = "1b829c092ddb4651c3d5cdea687bbffa645ee6c5"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_public_audio_chunk_streaming_acceptance.py",
    "scripts/smoke_v600_public_audio_chunk_streaming_control_a.py",
    "scripts/smoke_v600_public_audio_chunk_streaming_control_b.py",
    "tests/test_public_audio_chunk_streaming_control_a.py",
    "tests/test_public_audio_chunk_streaming_control_b.py",
}
EXPECTED_TASKS = (
    "audio chunk typeを定義する。",
    "chunk sequenceを定義する。",
    "accepted format/max chunk/max durationをcapability化する。",
    "end-of-inputを定義する。",
    "input abortを定義する。",
    "partial transcript eventを実装する。",
    "malformed/out-of-order chunkをtyped rejectする。",
)
EXPECTED_STREAMING_EXPORTS = (
    "VOICE_INPUT_STREAMING_API_VERSION",
    "VoiceInputStreamOperationKind",
    "VoiceInputStreamRejectionCode",
    "VoiceInputStreamingCapability",
    "VoiceInputStreamConfig",
    "VoiceInputAudioChunk",
    "VoiceInputStreamEnd",
    "VoiceInputStreamAbort",
    "VoiceInputStreamOperationResult",
)
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
FORBIDDEN_RUNTIME_MODULES = {
    "openai",
    "elevenlabs",
    "pyvts",
    "pyaudio",
    "sounddevice",
    "websocket",
    "websockets",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, capture: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (result.stdout or "")
        + (result.stderr or ""),
    )
    return result.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-12a Control C surface conform")


def check_accepted_history_and_focused_gates() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-12a-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-12a-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-12a-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-12a-B-ACCEPTANCE-SYNC:END",
        "FW-RT6-12a-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-12a-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")
    for phrase in (
        "Control A implementation and acceptance: f07105742ea6068a6d1655d737c160a5f3487dd5",
        "Control B implementation and acceptance: 1b829c092ddb4651c3d5cdea687bbffa645ee6c5",
        "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted history fact missing: {phrase}")

    sources = {
        "Control A gate": PROJECT_ROOT
        / "scripts/smoke_v600_public_audio_chunk_streaming_control_a.py",
        "Control B gate": PROJECT_ROOT
        / "scripts/smoke_v600_public_audio_chunk_streaming_control_b.py",
        "Control A tests": PROJECT_ROOT
        / "tests/test_public_audio_chunk_streaming_control_a.py",
        "Control B tests": PROJECT_ROOT
        / "tests/test_public_audio_chunk_streaming_control_b.py",
    }
    _require(
        sources["Control A tests"].read_text(encoding="utf-8").count("    def test_")
        == 15,
        "Control A test count drift",
    )
    _require(
        sources["Control B tests"].read_text(encoding="utf-8").count("    def test_")
        == 21,
        "Control B test count drift",
    )
    for label, path in sources.items():
        source = path.read_text(encoding="utf-8")
        _require(
            "check_v600_public_audio_chunk_streaming_acceptance.py" in source,
            f"{label} Control C boundary sync missing",
        )

    _run(
        [
            sys.executable,
            "scripts/smoke_v600_public_audio_chunk_streaming_control_a.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "scripts/smoke_v600_public_audio_chunk_streaming_control_b.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_public_audio_chunk_streaming_control_a",
            "tests.test_public_audio_chunk_streaming_control_b",
        ],
        capture=False,
    )
    print("[OK] accepted Control A/B history and 36 focused tests conform")
    print("[OK] four gate/test files receive Control C task-boundary-only sync")


def check_namespaces_root_factory_and_import_safety() -> None:
    import framework

    streaming = importlib.import_module("framework.voice_input_streaming")
    adapter = importlib.import_module("framework.voice_input_streaming_adapter")
    _require(streaming.__all__ == EXPECTED_STREAMING_EXPORTS, "streaming exports drift")
    _require(adapter.__all__ == EXPECTED_ADAPTER_EXPORTS, "adapter exports drift")
    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_STREAMING_EXPORTS + EXPECTED_ADAPTER_EXPORTS:
        _require(name not in framework.__all__, f"explicit-only name leaked root: {name}")
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
    _require(
        not framework.VoiceInputSession().streaming_capability.audio_chunk_input_supported,
        "default VoiceInputSession support overclaim",
    )
    snapshot = framework.get_capabilities().realtime_snapshot
    _require(snapshot is not None, "realtime capability snapshot missing")
    _require(
        not snapshot.voice_input.audio_chunk_input_supported,
        "global realtime capability overclaim",
    )

    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework
import framework.voice_input_streaming as streaming
import framework.voice_input_streaming_adapter as adapter
assert len(framework.__all__) == 127
assert len(streaming.__all__) == 9
assert len(adapter.__all__) == 2
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] exact namespaces, root 127, factory, and session ownership conform")
    print("[OK] aggregate imports remain provider, network, device, and VTS safe")


def check_aggregate_runtime_truth() -> None:
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

    events = []
    legacy_events = []
    session = framework.VoiceInputSession()
    session.on_realtime_event(events.append)
    session.on_event(legacy_events.append)
    capability = session.configure_audio_streaming(
        DeterministicFakeVoiceInputStreamingAdapter(
            partial_transcripts={0: "partial"},
            final_transcript="final",
        )
    )
    _require(capability.audio_chunk_input_supported, "explicit capability missing")
    config = VoiceInputStreamConfig(
        stream_id="aggregate_stream",
        audio_format=VoiceInputAudioFormat(
            encoding=VoiceInputAudioEncoding.PCM16,
            sample_rate_hz=16_000,
            channel_count=1,
        ),
    )
    _require(session.begin_audio_stream(config), "aggregate stream begin rejected")
    malformed = session.send_audio_chunk(
        VoiceInputAudioChunk(
            "aggregate_stream",
            1,
            b"private audio",
            duration_ms=20,
        )
    )
    _require(
        malformed.rejection_code is VoiceInputStreamRejectionCode.OUT_OF_ORDER,
        "out-of-order rejection drift",
    )
    _require(malformed.retryable, "out-of-order retry truth drift")
    accepted = session.send_audio_chunk(
        VoiceInputAudioChunk(
            "aggregate_stream",
            0,
            b"private audio",
            duration_ms=20,
        )
    )
    _require(accepted.accepted, "ordered chunk rejected")
    ended = session.end_audio_input(VoiceInputStreamEnd("aggregate_stream", 1))
    _require(ended.accepted and ended.terminal, "ordered end rejected")
    _require(session.last_stream_result is not None, "final result missing")
    _require(session.last_stream_result.text == "final", "final transcript drift")
    _require(
        session.last_stream_result.outcome is VoiceInputOutcome.COMPLETED,
        "final outcome drift",
    )
    _require(
        [event.type for event in events]
        == [
            RealtimeEventType.LISTENING_STARTED,
            RealtimeEventType.TRANSCRIPT_PARTIAL,
            RealtimeEventType.TRANSCRIPT_FINAL,
        ],
        "canonical event order drift",
    )
    _require(
        len({(event.session_id, event.turn_id, event.generation_id) for event in events})
        == 1,
        "event correlation drift",
    )
    _require(not legacy_events, "stream transcript expanded legacy callback")
    _require("private audio" not in repr(events), "event exposed raw audio")

    abort_session = framework.VoiceInputSession()
    abort_events = []
    abort_session.on_realtime_event(abort_events.append)
    abort_session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
    _require(abort_session.begin_audio_stream(config), "abort stream begin rejected")
    aborted = abort_session.abort_audio_stream(VoiceInputStreamAbort("aggregate_stream"))
    _require(aborted.accepted and aborted.terminal, "cooperative abort rejected")
    _require(
        abort_session.last_stream_result.outcome is VoiceInputOutcome.INTERRUPTED,
        "abort outcome drift",
    )
    _require(
        not abort_events[-1].public_metadata["provider_hard_cancel_claimed"],
        "abort overclaimed provider cancellation",
    )
    print("[OK] ordering, typed rejection, partial/final correlation, and final result conform")
    print("[OK] cooperative abort, legacy isolation, and raw-audio safety conform")


def check_docs_tasks_and_unchanged_boundaries() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs/v600_public_audio_chunk_streaming.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "FW-RT6-12a-C-AUDIO-STREAMING-ACCEPTANCE:BEGIN",
        "FW-RT6-12a-C-AUDIO-STREAMING-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public facade marker drift: {marker}")
    section = tasklist.split(
        "## FW-RT6-12a — P1 public audio chunk streaming", 1
    )[1].split("## FW-RT6-12b", 1)[0]
    _require(section.count("- [ ]") == 0, "Control C left an aggregate task open")
    _require(section.count("- [x]") == 7, "Control C aggregate task count drift")
    for task in EXPECTED_TASKS:
        _require(section.count(task) == 1, f"task text drift: {task}")
    for phrase in (
        "7 / 7 ACCEPTED-CANDIDATE",
        "framework.voice_input_streaming",
        "framework.voice_input_streaming_adapter",
        "127 / UNCHANGED",
        "DEFERRED_TO_FW-RT6-12b",
        "final acceptance sync: NOT_AUTHORIZED",
    ):
        _require(phrase in facade + "\n" + tasklist, f"aggregate phrase missing: {phrase}")
    for accepted_document, label in (
        (app, "application contract"),
        (guide, "streaming guide"),
    ):
        _require("0 / 7 CLOSED" in accepted_document, f"historical {label} fact drift")
        _require("framework.voice_input_streaming_adapter" in accepted_document, f"{label} adapter fact drift")
    print("[OK] seven tasks are aggregate acceptance-candidates")
    print("[OK] public docs and unchanged application/streaming boundaries conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_history_and_focused_gates()
    check_namespaces_root_factory_and_import_safety()
    check_aggregate_runtime_truth()
    check_docs_tasks_and_unchanged_boundaries()
    print("v600_rt6_12a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12a_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12a_control_c_exact_surface: 7 files")
    print("v600_rt6_12a_existing_gate_test_sync: 4 files / TASK BOUNDARY ONLY")
    print("v600_rt6_12a_streaming_namespace_exports: 9 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12a_adapter_namespace_exports: 2 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12a_voice_input_session_adoption: True / EXPLICIT_ADAPTER_ONLY")
    print("v600_rt6_12a_realtime_session_adoption: False / UNCHANGED")
    print("v600_rt6_12a_backpressure_queue: False / FW-RT6-12b")
    print("v600_rt6_12a_provider_execution: False")
    print("v600_rt6_12a_network_execution: False")
    print("v600_rt6_12a_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_12a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_12b: NOT_AUTHORIZED")
    print("v600_rt6_12a_control_c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12a Control C aggregate audio streaming gate passed")


if __name__ == "__main__":
    main()
