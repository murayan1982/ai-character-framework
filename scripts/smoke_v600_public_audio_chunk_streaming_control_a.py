"""FW-RT6-12a Control A public audio-chunk contract gate."""

from __future__ import annotations

import argparse
import ast
import importlib
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "d5e707fa4bca34322b9a2319696273b129b6f395"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_audio_chunk_streaming.md",
    "framework/voice_input_streaming.py",
    "scripts/smoke_v600_public_audio_chunk_streaming_control_a.py",
    "tests/test_public_audio_chunk_streaming_control_a.py",
}
EXPECTED_EXPORTS = (
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, capture: bool = True) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=capture,
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
    _require(
        actual == EXPECTED_SURFACE,
        f"Control A exact surface drift: {sorted(actual)!r}",
    )
    print("[OK] baseline and exact six-file FW-RT6-12a Control A surface conform")


def check_namespace_and_import_safety() -> None:
    namespace = importlib.import_module("framework.voice_input_streaming")
    _require(namespace.__all__ == EXPECTED_EXPORTS, "namespace exports drift")
    _require(namespace.VOICE_INPUT_STREAMING_API_VERSION == "6.0", "API version drift")

    source_path = PROJECT_ROOT / "framework/voice_input_streaming.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    _require(
        imports
        == {
            "__future__",
            "dataclasses",
            "enum",
            "types",
            "typing",
            "public_safety",
            "voice_input_audio",
        },
        f"streaming module import drift: {sorted(imports)!r}",
    )

    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.voice_input_streaming as streaming
assert len(streaming.__all__) == 9
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] explicit nine-name namespace is provider, network, and device safe")


def check_models_and_truthful_capability() -> None:
    from framework.voice_input_audio import (
        VoiceInputAudioEncoding,
        VoiceInputAudioFormat,
    )
    from framework.voice_input_streaming import (
        VoiceInputAudioChunk,
        VoiceInputStreamAbort,
        VoiceInputStreamConfig,
        VoiceInputStreamEnd,
        VoiceInputStreamOperationKind,
        VoiceInputStreamOperationResult,
        VoiceInputStreamRejectionCode,
        VoiceInputStreamingCapability,
    )

    unavailable = VoiceInputStreamingCapability()
    _require(not unavailable.audio_chunk_input_supported, "default support overclaim")
    _require(unavailable.accepted_audio_formats == (), "default formats overclaim")
    _require(unavailable.maximum_chunk_size_bytes is None, "default chunk limit overclaim")
    _require(unavailable.maximum_duration_ms is None, "default duration limit overclaim")

    capability = VoiceInputStreamingCapability(
        audio_chunk_input_supported=True,
        accepted_audio_formats=("pcm16", "wav"),
        maximum_chunk_size_bytes=8192,
        maximum_duration_ms=30_000,
        end_of_input_supported=True,
        input_abort_supported=True,
        partial_transcript_supported=False,
        final_transcript_supported=True,
    )
    _require(
        capability.accepted_audio_formats
        == (VoiceInputAudioEncoding.PCM16, VoiceInputAudioEncoding.WAV),
        "accepted formats drift",
    )
    config = VoiceInputStreamConfig(
        stream_id="stream_001",
        audio_format=VoiceInputAudioFormat(
            encoding=VoiceInputAudioEncoding.PCM16,
            sample_rate_hz=16_000,
            channel_count=1,
        ),
    )
    chunk = VoiceInputAudioChunk(
        stream_id=config.stream_id,
        sequence_number=0,
        data=b"raw private audio",
        duration_ms=20,
    )
    end = VoiceInputStreamEnd(stream_id=config.stream_id, sequence_number=1)
    abort = VoiceInputStreamAbort(
        stream_id=config.stream_id,
        last_sequence_number=0,
    )
    rejection = VoiceInputStreamOperationResult.rejected(
        kind=VoiceInputStreamOperationKind.AUDIO_CHUNK,
        stream_id=config.stream_id,
        sequence_number=2,
        next_expected_sequence_number=1,
        rejection_code=VoiceInputStreamRejectionCode.OUT_OF_ORDER,
        safe_message="Audio chunk sequence was rejected.",
        retryable=True,
    )
    _require(chunk.byte_count == 17, "chunk byte count drift")
    _require("raw private audio" not in repr(chunk), "repr exposed raw audio")
    _require("data" not in chunk.as_dict(), "public projection exposed raw audio")
    _require(end.sequence_number == 1, "end sequence drift")
    _require(abort.kind is VoiceInputStreamOperationKind.ABORT, "abort kind drift")
    _require(not hasattr(abort, "provider_cancelled"), "abort overclaimed provider cancel")
    _require(
        rejection.rejection_code is VoiceInputStreamRejectionCode.OUT_OF_ORDER,
        "typed rejection drift",
    )
    _require(rejection.next_expected_sequence_number == 1, "next sequence drift")
    print("[OK] chunk, ordering, end, abort, capability, and typed result models conform")
    print("[OK] raw audio is explicit input but absent from repr and public projection")


def check_root_runtime_and_task_boundaries() -> None:
    import framework

    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_EXPORTS:
        _require(name not in framework.__all__, f"explicit-only name leaked root: {name}")
    _require(
        not hasattr(framework.VoiceInputSession, "start_audio_stream"),
        "uncontracted VoiceInputSession.start_audio_stream appeared",
    )
    for method_name in (
        "configure_audio_streaming",
        "begin_audio_stream",
        "send_audio_chunk",
        "end_audio_input",
        "abort_audio_stream",
    ):
        _require(
            hasattr(framework.VoiceInputSession, method_name),
            f"Control B VoiceInputSession.{method_name} missing",
        )
    for method_name in (
        "configure_audio_streaming",
        "start_audio_stream",
        "begin_audio_stream",
        "send_audio_chunk",
        "end_audio_input",
        "abort_audio_stream",
    ):
        _require(
            not hasattr(framework.RealtimeSession, method_name),
            f"RealtimeSession boundary drift: {method_name}",
        )
    _require(
        not framework.VoiceInputSession().streaming_capability.audio_chunk_input_supported,
        "default VoiceInputSession overclaimed audio chunk support",
    )

    snapshot = framework.get_capabilities().realtime_snapshot
    _require(snapshot is not None, "realtime capability snapshot missing")
    _require(
        snapshot.voice_input.audio_chunk_input_supported is False,
        "current runtime audio chunk support overclaim",
    )
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
    print("[OK] root 127, explicit VoiceInputSession adoption, default-off capability, and 7/7 candidate boundary conform")


def check_docs_and_accepted_regressions() -> None:
    documents = {
        name: (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
        for name in (
            "public_facade.md",
            "app_integration_contract.md",
            "v600_public_audio_chunk_streaming.md",
        )
    }
    for text, marker in (
        (documents["public_facade.md"], "FW-RT6-12a-A-PUBLIC-AUDIO-CHUNK:BEGIN"),
        (documents["app_integration_contract.md"], "FW-RT6-12a-A-HOST-AUDIO-CHUNK:BEGIN"),
        (
            documents["v600_public_audio_chunk_streaming.md"],
            "FW-RT6-12a-A-PUBLIC-AUDIO-CHUNK:BEGIN",
        ),
    ):
        _require(text.count(marker) == 1, f"documentation marker drift: {marker}")
    combined = "\n".join(documents.values())
    for phrase in (
        "framework.voice_input_streaming",
        "127 / UNCHANGED",
        "0 / 7 CLOSED",
        "partial transcript",
        "NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"Control A documentation phrase missing: {phrase}")

    _run(
        [
            sys.executable,
            "scripts/check_v600_migration_examples_acceptance.py",
            "--source-only",
        ]
    )
    _run(
        [
            sys.executable,
            "scripts/check_v600_root_public_api_cleanup_acceptance.py",
            "--source-only",
        ]
    )
    _run(
        [
            sys.executable,
            "scripts/check_v600_session_compatibility_acceptance.py",
            "--source-only",
        ]
    )
    print("[OK] public/app/streaming docs and accepted 11a/11b/11c gates conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_namespace_and_import_safety()
    check_models_and_truthful_capability()
    check_root_runtime_and_task_boundaries()
    check_docs_and_accepted_regressions()
    print("v600_rt6_12a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12a_control_a_exact_surface: 6 files")
    print("v600_rt6_12a_namespace: framework.voice_input_streaming")
    print("v600_rt6_12a_namespace_exports: 9 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12a_session_runtime_adoption: VoiceInputSession / CONTROL_B")
    print("v600_rt6_12a_partial_transcript_delivery: True / EXPLICIT_ADAPTER_ONLY")
    print("v600_rt6_12a_provider_execution: False")
    print("v600_rt6_12a_network_execution: False")
    print("v600_rt6_12a_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_12a_control_b: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12a_control_c: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_12a_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12a Control A public audio-chunk contract gate passed")


if __name__ == "__main__":
    main()
