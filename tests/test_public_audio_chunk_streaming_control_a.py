"""Provider-free FW-RT6-12a Control A public contract tests."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys
import unittest

import framework


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "framework.voice_input_streaming"
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


class PublicAudioChunkStreamingControlATests(unittest.TestCase):
    def test_namespace_has_exact_explicit_exports(self) -> None:
        namespace = importlib.import_module(NAMESPACE)

        self.assertEqual(namespace.__all__, EXPECTED_EXPORTS)
        self.assertEqual(namespace.VOICE_INPUT_STREAMING_API_VERSION, "6.0")
        self.assertEqual(len(namespace.__all__), len(set(namespace.__all__)))

    def test_namespace_import_is_provider_and_device_safe(self) -> None:
        code = r'''
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
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_root_inventory_remains_frozen_and_does_not_reexport_namespace(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        for name in EXPECTED_EXPORTS:
            self.assertNotIn(name, framework.__all__)

    def test_default_capability_is_truthfully_unsupported(self) -> None:
        from framework.voice_input_streaming import VoiceInputStreamingCapability

        capability = VoiceInputStreamingCapability()
        self.assertFalse(capability.audio_chunk_input_supported)
        self.assertEqual(capability.accepted_audio_formats, ())
        self.assertIsNone(capability.maximum_chunk_size_bytes)
        self.assertIsNone(capability.maximum_duration_ms)
        self.assertFalse(capability.end_of_input_supported)
        self.assertFalse(capability.input_abort_supported)
        self.assertFalse(capability.partial_transcript_supported)
        self.assertFalse(capability.final_transcript_supported)

    def test_supported_capability_requires_formats_limits_end_and_final(self) -> None:
        from framework.voice_input_audio import VoiceInputAudioEncoding
        from framework.voice_input_streaming import VoiceInputStreamingCapability

        capability = VoiceInputStreamingCapability(
            audio_chunk_input_supported=True,
            accepted_audio_formats=(VoiceInputAudioEncoding.PCM16, "wav", "pcm16"),
            maximum_chunk_size_bytes=8192,
            maximum_duration_ms=30_000,
            end_of_input_supported=True,
            input_abort_supported=True,
            partial_transcript_supported=False,
            final_transcript_supported=True,
        )
        self.assertEqual(
            capability.accepted_audio_formats,
            (VoiceInputAudioEncoding.PCM16, VoiceInputAudioEncoding.WAV),
        )
        self.assertEqual(
            capability.as_dict()["accepted_audio_formats"],
            ("pcm16", "wav"),
        )

        invalid_kwargs = (
            {},
            {"accepted_audio_formats": ("pcm16",)},
            {
                "accepted_audio_formats": ("pcm16",),
                "maximum_chunk_size_bytes": 1,
            },
            {
                "accepted_audio_formats": ("pcm16",),
                "maximum_chunk_size_bytes": 1,
                "maximum_duration_ms": 1,
            },
        )
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                VoiceInputStreamingCapability(
                    audio_chunk_input_supported=True,
                    final_transcript_supported=True,
                    **kwargs,
                )

    def test_unsupported_capability_cannot_overclaim_features(self) -> None:
        from framework.voice_input_streaming import VoiceInputStreamingCapability

        for kwargs in (
            {"accepted_audio_formats": ("pcm16",)},
            {"maximum_chunk_size_bytes": 1},
            {"maximum_duration_ms": 1},
            {"end_of_input_supported": True},
            {"input_abort_supported": True},
            {"partial_transcript_supported": True},
            {"final_transcript_supported": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                VoiceInputStreamingCapability(**kwargs)

    def test_stream_config_requires_opaque_id_and_explicit_format(self) -> None:
        from framework.voice_input_audio import (
            VoiceInputAudioEncoding,
            VoiceInputAudioFormat,
        )
        from framework.voice_input_streaming import VoiceInputStreamConfig

        config = VoiceInputStreamConfig(
            stream_id="stream_001",
            audio_format=VoiceInputAudioFormat(
                encoding=VoiceInputAudioEncoding.PCM16,
                sample_rate_hz=16_000,
                channel_count=1,
            ),
            language=" ja-JP ",
        )
        self.assertEqual(config.stream_id, "stream_001")
        self.assertEqual(config.language, "ja-JP")
        with self.assertRaises(ValueError):
            VoiceInputStreamConfig(
                stream_id="stream_002",
                audio_format=VoiceInputAudioFormat(),
            )
        with self.assertRaises(ValueError):
            VoiceInputStreamConfig(
                stream_id=r"C:\private\audio.raw",
                audio_format=config.audio_format,
            )

    def test_chunk_is_non_empty_zero_based_and_raw_bytes_are_not_projected(self) -> None:
        from framework.voice_input_streaming import VoiceInputAudioChunk

        chunk = VoiceInputAudioChunk(
            stream_id="stream_001",
            sequence_number=0,
            data=b"private raw audio",
            duration_ms=20,
            public_metadata={"api_key": "secret", "source": "host"},
        )
        self.assertEqual(chunk.byte_count, 17)
        self.assertEqual(chunk.data, b"private raw audio")
        self.assertNotIn("private raw audio", repr(chunk))
        projection = dict(chunk.as_dict())
        self.assertNotIn("data", projection)
        self.assertEqual(projection["byte_count"], 17)
        self.assertEqual(projection["public_metadata"]["api_key"], "<redacted>")

    def test_chunk_rejects_empty_or_structurally_invalid_values(self) -> None:
        from framework.voice_input_streaming import VoiceInputAudioChunk

        with self.assertRaises(ValueError):
            VoiceInputAudioChunk(stream_id="stream", sequence_number=0, data=b"")
        with self.assertRaises(ValueError):
            VoiceInputAudioChunk(stream_id="stream", sequence_number=-1, data=b"x")
        with self.assertRaises(TypeError):
            VoiceInputAudioChunk(stream_id="stream", sequence_number=True, data=b"x")
        with self.assertRaises(TypeError):
            VoiceInputAudioChunk(stream_id="stream", sequence_number=0, data="x")

    def test_end_of_input_uses_an_explicit_next_sequence_number(self) -> None:
        from framework.voice_input_streaming import (
            VoiceInputStreamEnd,
            VoiceInputStreamOperationKind,
        )

        end = VoiceInputStreamEnd(stream_id="stream", sequence_number=3)
        self.assertEqual(end.kind, VoiceInputStreamOperationKind.END_OF_INPUT)
        self.assertEqual(end.sequence_number, 3)
        with self.assertRaises(ValueError):
            VoiceInputStreamEnd(stream_id="stream", sequence_number=-1)

    def test_abort_is_out_of_band_correlation_not_provider_cancel_proof(self) -> None:
        from framework.voice_input_streaming import (
            VoiceInputStreamAbort,
            VoiceInputStreamOperationKind,
        )

        abort = VoiceInputStreamAbort(
            stream_id="stream",
            reason="host_requested",
            last_sequence_number=2,
        )
        self.assertEqual(abort.kind, VoiceInputStreamOperationKind.ABORT)
        self.assertEqual(abort.last_sequence_number, 2)
        self.assertFalse(hasattr(abort, "provider_cancelled"))

    def test_operation_results_enforce_accepted_rejected_consistency(self) -> None:
        from framework.voice_input_streaming import (
            VoiceInputStreamOperationKind,
            VoiceInputStreamOperationResult,
            VoiceInputStreamRejectionCode,
        )

        accepted = VoiceInputStreamOperationResult.accepted_operation(
            kind=VoiceInputStreamOperationKind.AUDIO_CHUNK,
            stream_id="stream",
            sequence_number=0,
            next_expected_sequence_number=1,
        )
        rejected = VoiceInputStreamOperationResult.rejected(
            kind=VoiceInputStreamOperationKind.AUDIO_CHUNK,
            stream_id="stream",
            sequence_number=2,
            next_expected_sequence_number=1,
            rejection_code=VoiceInputStreamRejectionCode.OUT_OF_ORDER,
            safe_message="Audio chunk sequence was rejected.",
            retryable=True,
        )
        self.assertTrue(accepted.accepted)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.OUT_OF_ORDER)
        self.assertTrue(rejected.retryable)
        self.assertEqual(rejected.as_dict()["next_expected_sequence_number"], 1)

        with self.assertRaises(ValueError):
            VoiceInputStreamOperationResult(
                kind="audio_chunk",
                accepted=False,
                stream_id="stream",
            )
        with self.assertRaises(ValueError):
            VoiceInputStreamOperationResult(
                kind="audio_chunk",
                accepted=True,
                stream_id="stream",
                rejection_code="out_of_order",
            )

    def test_rejection_codes_cover_required_future_runtime_failures(self) -> None:
        from framework.voice_input_streaming import VoiceInputStreamRejectionCode

        self.assertEqual(
            {value.value for value in VoiceInputStreamRejectionCode},
            {
                "none",
                "not_supported",
                "invalid_stream_id",
                "invalid_format",
                "empty_chunk",
                "chunk_too_large",
                "duration_exceeded",
                "out_of_order",
                "already_ended",
                "already_aborted",
                "session_closed",
            },
        )

    def test_control_a_adds_no_session_streaming_methods(self) -> None:
        for session_type in (framework.VoiceInputSession, framework.RealtimeSession):
            for name in (
                "start_audio_stream",
                "send_audio_chunk",
                "end_audio_input",
                "abort_audio_stream",
            ):
                self.assertFalse(hasattr(session_type, name), f"{session_type.__name__}.{name}")

    def test_docs_and_task_boundary_record_control_a_truth(self) -> None:
        docs = {
            name: (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
            for name in (
                "public_facade.md",
                "app_integration_contract.md",
                "v600_public_audio_chunk_streaming.md",
            )
        }
        for text in docs.values():
            self.assertIn("framework.voice_input_streaming", text)
            self.assertIn("127 / UNCHANGED", text)
            self.assertIn("0 / 7 CLOSED", text)
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
        section = tasklist.split(
            "## FW-RT6-12a — P1 public audio chunk streaming", 1
        )[1].split("## FW-RT6-12b", 1)[0]
        self.assertEqual(section.count("- [ ]"), 7)
        self.assertEqual(section.count("- [x]"), 0)


if __name__ == "__main__":
    unittest.main()
