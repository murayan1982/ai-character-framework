"""Provider-free FW-RT6-12a Control B session streaming tests."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
import subprocess
import sys
import unittest

import framework
from framework.realtime import RealtimeEventType
from framework.voice_input import VoiceInputOutcome, VoiceInputResult
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
    VoiceInputStreamingAdapter,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER_EXPORTS = (
    "VoiceInputStreamingAdapter",
    "DeterministicFakeVoiceInputStreamingAdapter",
)
STREAMING_METHODS = (
    "configure_audio_streaming",
    "begin_audio_stream",
    "send_audio_chunk",
    "end_audio_input",
    "abort_audio_stream",
)
FACTORY_PARAMETERS = (
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


def _config(
    stream_id: str = "stream_001",
    *,
    encoding: VoiceInputAudioEncoding = VoiceInputAudioEncoding.PCM16,
) -> VoiceInputStreamConfig:
    return VoiceInputStreamConfig(
        stream_id=stream_id,
        audio_format=VoiceInputAudioFormat(
            encoding=encoding,
            sample_rate_hz=16_000,
            channel_count=1,
        ),
        language="ja-JP",
    )


def _chunk(
    sequence_number: int,
    *,
    stream_id: str = "stream_001",
    data: bytes = b"private audio",
    duration_ms: int | None = 20,
) -> VoiceInputAudioChunk:
    return VoiceInputAudioChunk(
        stream_id=stream_id,
        sequence_number=sequence_number,
        data=data,
        duration_ms=duration_ms,
    )


class _ExplodingAdapter(DeterministicFakeVoiceInputStreamingAdapter):
    def accept_chunk(self, chunk, *, emit_partial):  # type: ignore[no-untyped-def]
        raise RuntimeError(r"C:\private\api_key=secret raw private audio")


class PublicAudioChunkStreamingControlBTests(unittest.TestCase):
    def test_adapter_namespace_is_exact_explicit_and_structural(self) -> None:
        namespace = importlib.import_module("framework.voice_input_streaming_adapter")
        self.assertEqual(namespace.__all__, ADAPTER_EXPORTS)
        adapter = DeterministicFakeVoiceInputStreamingAdapter()
        self.assertIsInstance(adapter, VoiceInputStreamingAdapter)
        self.assertNotIn("VoiceInputStreamingAdapter", framework.__all__)
        self.assertNotIn("DeterministicFakeVoiceInputStreamingAdapter", framework.__all__)

    def test_adapter_namespace_import_is_provider_network_and_device_safe(self) -> None:
        code = r'''
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
        completed = subprocess.run(
            [sys.executable, "-I", "-c", code],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_root_factory_and_realtime_session_boundaries_remain_frozen(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(
            tuple(inspect.signature(framework.create_voice_input_session).parameters),
            FACTORY_PARAMETERS,
        )
        for name in STREAMING_METHODS:
            self.assertTrue(hasattr(framework.VoiceInputSession, name), name)
            self.assertFalse(hasattr(framework.RealtimeSession, name), name)

    def test_default_session_is_truthfully_unsupported(self) -> None:
        session = framework.create_voice_input_session()
        self.assertFalse(session.streaming_capability.audio_chunk_input_supported)
        self.assertFalse(session.begin_audio_stream(_config()))
        self.assertIsNone(session.last_stream_result)

    def test_explicit_fake_adapter_enables_truthful_capability(self) -> None:
        session = framework.create_voice_input_session()
        capability = session.configure_audio_streaming(
            DeterministicFakeVoiceInputStreamingAdapter()
        )
        self.assertTrue(capability.audio_chunk_input_supported)
        self.assertEqual(capability.accepted_audio_formats, (VoiceInputAudioEncoding.PCM16,))
        self.assertEqual(capability.maximum_chunk_size_bytes, 8192)
        self.assertEqual(capability.maximum_duration_ms, 30_000)
        self.assertTrue(capability.partial_transcript_supported)
        self.assertFalse(capability.public_metadata["provider_execution"])

    def test_wrong_format_and_busy_second_begin_are_rejected(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        self.assertFalse(session.begin_audio_stream(_config(encoding=VoiceInputAudioEncoding.WAV)))
        self.assertTrue(session.begin_audio_stream(_config()))
        self.assertFalse(session.begin_audio_stream(_config("stream_002")))
        with self.assertRaises(RuntimeError):
            session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())

    def test_ordered_chunks_emit_correlated_partial_then_final_events(self) -> None:
        session = framework.VoiceInputSession()
        events = []
        session.on_realtime_event(events.append)
        session.configure_audio_streaming(
            DeterministicFakeVoiceInputStreamingAdapter(
                partial_transcripts={0: "hel", 1: "hello"},
                final_transcript="hello world",
                confidence=0.75,
            )
        )
        self.assertTrue(session.begin_audio_stream(_config()))
        first = session.send_audio_chunk(_chunk(0))
        second = session.send_audio_chunk(_chunk(1))
        ended = session.end_audio_input(VoiceInputStreamEnd("stream_001", 2))
        self.assertTrue(first.accepted)
        self.assertEqual(first.next_expected_sequence_number, 1)
        self.assertTrue(second.accepted)
        self.assertEqual(second.next_expected_sequence_number, 2)
        self.assertTrue(ended.accepted)
        self.assertTrue(ended.terminal)
        self.assertEqual(
            [event.type for event in events],
            [
                RealtimeEventType.LISTENING_STARTED,
                RealtimeEventType.TRANSCRIPT_PARTIAL,
                RealtimeEventType.TRANSCRIPT_PARTIAL,
                RealtimeEventType.TRANSCRIPT_FINAL,
            ],
        )
        self.assertEqual([event.payload.text for event in events[1:]], ["hel", "hello", "hello world"])
        self.assertEqual([event.payload.is_final for event in events[1:]], [False, False, True])
        self.assertEqual(len({event.session_id for event in events}), 1)
        self.assertEqual(len({event.turn_id for event in events}), 1)
        self.assertEqual(len({event.generation_id for event in events}), 1)
        self.assertEqual([int(event.sequence) for event in events], [1, 2, 3, 4])
        self.assertEqual(session.last_stream_result.text, "hello world")
        self.assertEqual(session.last_stream_result.outcome, VoiceInputOutcome.COMPLETED)

    def test_stream_partial_and_final_do_not_expand_legacy_mapping_callbacks(self) -> None:
        session = framework.VoiceInputSession()
        legacy_events = []
        session.on_event(legacy_events.append)
        session.configure_audio_streaming(
            DeterministicFakeVoiceInputStreamingAdapter(partial_transcripts={0: "partial"})
        )
        self.assertTrue(session.begin_audio_stream(_config()))
        session.send_audio_chunk(_chunk(0))
        session.end_audio_input(VoiceInputStreamEnd("stream_001", 1))
        self.assertEqual(legacy_events, [])

    def test_raw_audio_is_absent_from_results_events_and_representations(self) -> None:
        session = framework.VoiceInputSession()
        events = []
        session.on_realtime_event(events.append)
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        operation = session.send_audio_chunk(
            _chunk(0, data=b"raw-private-audio-token", duration_ms=20)
        )
        session.end_audio_input(VoiceInputStreamEnd("stream_001", 1))
        combined = repr(operation) + repr(events) + repr(session.last_stream_result)
        self.assertNotIn("raw-private-audio-token", combined)

    def test_out_of_order_rejection_preserves_next_expected_sequence(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        rejected = session.send_audio_chunk(_chunk(1))
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.OUT_OF_ORDER)
        self.assertEqual(rejected.next_expected_sequence_number, 0)
        self.assertTrue(rejected.retryable)
        accepted = session.send_audio_chunk(_chunk(0))
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.next_expected_sequence_number, 1)

    def test_oversized_chunk_is_retryable_without_consuming_sequence(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        rejected = session.send_audio_chunk(_chunk(0, data=b"x" * 8193))
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.CHUNK_TOO_LARGE)
        self.assertEqual(rejected.next_expected_sequence_number, 0)
        self.assertTrue(session.send_audio_chunk(_chunk(0)).accepted)

    def test_missing_or_excessive_duration_is_typed_and_retryable(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        for duration in (None, 30_001):
            rejected = session.send_audio_chunk(_chunk(0, duration_ms=duration))
            self.assertEqual(
                rejected.rejection_code,
                VoiceInputStreamRejectionCode.DURATION_EXCEEDED,
            )
            self.assertTrue(rejected.retryable)
            self.assertEqual(rejected.next_expected_sequence_number, 0)

    def test_wrong_stream_id_and_out_of_order_end_are_typed(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        wrong = session.send_audio_chunk(_chunk(0, stream_id="stream_other"))
        self.assertEqual(wrong.rejection_code, VoiceInputStreamRejectionCode.INVALID_STREAM_ID)
        out_of_order = session.end_audio_input(VoiceInputStreamEnd("stream_001", 1))
        self.assertEqual(out_of_order.rejection_code, VoiceInputStreamRejectionCode.OUT_OF_ORDER)
        self.assertEqual(out_of_order.next_expected_sequence_number, 0)
        self.assertTrue(out_of_order.retryable)

    def test_duplicate_end_is_terminal_and_preserves_final_result(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        final = session.end_audio_input(VoiceInputStreamEnd("stream_001", 0))
        original = session.last_stream_result
        duplicate = session.end_audio_input(VoiceInputStreamEnd("stream_001", 0))
        self.assertTrue(final.accepted)
        self.assertEqual(duplicate.rejection_code, VoiceInputStreamRejectionCode.ALREADY_ENDED)
        self.assertTrue(duplicate.terminal)
        self.assertIs(session.last_stream_result, original)

    def test_abort_is_cooperative_correlated_and_idempotently_terminal(self) -> None:
        session = framework.VoiceInputSession()
        events = []
        session.on_realtime_event(events.append)
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        session.send_audio_chunk(_chunk(0))
        request = VoiceInputStreamAbort(
            "stream_001", reason="host_requested", last_sequence_number=0
        )
        accepted = session.abort_audio_stream(request)
        duplicate = session.abort_audio_stream(request)
        self.assertTrue(accepted.accepted)
        self.assertTrue(accepted.terminal)
        self.assertEqual(duplicate.rejection_code, VoiceInputStreamRejectionCode.ALREADY_ABORTED)
        self.assertEqual(session.last_stream_result.outcome, VoiceInputOutcome.INTERRUPTED)
        self.assertEqual(events[-1].type, RealtimeEventType.VOICE_INPUT_FAILED)
        self.assertFalse(events[-1].public_metadata["provider_hard_cancel_claimed"])
        self.assertFalse(events[-1].public_metadata["host_audio_capture_stopped_claimed"])

    def test_abort_input_bridges_to_the_active_audio_stream(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        self.assertTrue(session.abort_input())
        self.assertFalse(session.abort_input())
        self.assertEqual(session.last_stream_result.outcome, VoiceInputOutcome.INTERRUPTED)

    def test_close_terminalizes_active_stream_and_post_close_operations(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())
        session.begin_audio_stream(_config())
        session.close()
        self.assertEqual(session.last_stream_result.outcome, VoiceInputOutcome.CLOSED)
        rejected = session.send_audio_chunk(_chunk(0))
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.SESSION_CLOSED)
        self.assertTrue(rejected.terminal)
        with self.assertRaises(RuntimeError):
            session.configure_audio_streaming(DeterministicFakeVoiceInputStreamingAdapter())

    def test_adapter_exception_is_safely_terminalized_without_private_data(self) -> None:
        session = framework.VoiceInputSession()
        events = []
        session.on_realtime_event(events.append)
        session.configure_audio_streaming(_ExplodingAdapter())
        session.begin_audio_stream(_config())
        rejected = session.send_audio_chunk(_chunk(0))
        self.assertFalse(rejected.accepted)
        self.assertTrue(rejected.terminal)
        self.assertEqual(rejected.rejection_code, VoiceInputStreamRejectionCode.NOT_SUPPORTED)
        combined = repr(rejected) + repr(events) + repr(session.last_stream_result)
        self.assertNotIn("api_key", combined)
        self.assertNotIn("raw private audio", combined)
        self.assertEqual(session.last_stream_result.outcome, VoiceInputOutcome.FAILED)
        self.assertTrue(session.begin_audio_stream(_config("stream_002")))
        self.assertTrue(
            session.end_audio_input(VoiceInputStreamEnd("stream_002", 0)).accepted
        )

    def test_partial_callback_can_reentrantly_abort_without_late_acceptance(self) -> None:
        session = framework.VoiceInputSession()
        abort_results = []

        def on_event(event) -> None:  # type: ignore[no-untyped-def]
            if event.type is RealtimeEventType.TRANSCRIPT_PARTIAL:
                abort_results.append(
                    session.abort_audio_stream(
                        VoiceInputStreamAbort("stream_001", last_sequence_number=0)
                    )
                )

        session.on_realtime_event(on_event)
        session.configure_audio_streaming(
            DeterministicFakeVoiceInputStreamingAdapter(partial_transcripts={0: "partial"})
        )
        session.begin_audio_stream(_config())
        result = session.send_audio_chunk(_chunk(0))
        self.assertTrue(abort_results[0].accepted)
        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_code, VoiceInputStreamRejectionCode.ALREADY_ABORTED)
        self.assertEqual(session.last_stream_result.outcome, VoiceInputOutcome.INTERRUPTED)

    def test_sequential_streams_reuse_one_explicit_adapter_safely(self) -> None:
        session = framework.VoiceInputSession()
        session.configure_audio_streaming(
            DeterministicFakeVoiceInputStreamingAdapter(final_transcript="done")
        )
        for stream_id in ("stream_001", "stream_002"):
            self.assertTrue(session.begin_audio_stream(_config(stream_id)))
            self.assertTrue(
                session.end_audio_input(VoiceInputStreamEnd(stream_id, 0)).accepted
            )
            self.assertEqual(session.last_stream_result.text, "done")

    def test_docs_and_tasklist_record_control_b_without_closing_tasks(self) -> None:
        docs = {
            name: (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
            for name in (
                "public_facade.md",
                "app_integration_contract.md",
                "v600_public_audio_chunk_streaming.md",
            )
        }
        self.assertIn("FW-RT6-12a-B-VOICE-INPUT-STREAMING:BEGIN", docs["public_facade.md"])
        self.assertIn("FW-RT6-12a-B-HOST-AUDIO-STREAMING:BEGIN", docs["app_integration_contract.md"])
        for text in docs.values():
            self.assertIn("framework.voice_input_streaming_adapter", text)
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
