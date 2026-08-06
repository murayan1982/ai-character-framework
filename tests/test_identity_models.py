"""Fast provider-free tests for identity and immutable public models."""

from __future__ import annotations

import unittest

from framework.identity import (
    EventSequence,
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)
from framework.lifecycle import RecoveryAction, TurnOutcome
from framework.realtime_event_payloads import (
    AudioEventPayload,
    DiagnosticEventPayload,
    LifecycleEventPayload,
    ResponseEventPayload,
    TranscriptEventPayload,
)


_HEX = "0123456789abcdef0123456789abcdef"


class IdentityTests(unittest.TestCase):
    def test_framework_ids_round_trip(self) -> None:
        values = (
            SessionId(f"fw_session_{_HEX}"),
            TurnId(f"fw_turn_{_HEX}"),
            GenerationId(f"fw_generation_{_HEX}"),
        )

        for value in values:
            parsed = type(value).parse(str(value))
            self.assertEqual(parsed, value)
            self.assertIsInstance(parsed, type(value))
            self.assertEqual(parsed.to_json_value(), str(value))

    def test_new_ids_have_provider_neutral_prefixes(self) -> None:
        created = (SessionId.new(), TurnId.new(), GenerationId.new())

        self.assertTrue(str(created[0]).startswith("fw_session_"))
        self.assertTrue(str(created[1]).startswith("fw_turn_"))
        self.assertTrue(str(created[2]).startswith("fw_generation_"))
        self.assertTrue(
            all(len(str(value).rsplit("_", 1)[-1]) == 32 for value in created)
        )

    def test_invalid_framework_namespace_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_session_id(f"fw_turn_{_HEX}")
        with self.assertRaises(ValueError):
            normalize_turn_id(f" fw_turn_{_HEX}")

    def test_legacy_host_ids_remain_compatible(self) -> None:
        self.assertEqual(normalize_session_id("host-session"), "host-session")
        self.assertEqual(normalize_turn_id("host-turn"), "host-turn")
        self.assertIsNone(normalize_session_id(None))
        self.assertIsNone(normalize_turn_id(None))

    def test_event_sequence_is_positive_and_monotonic(self) -> None:
        first = EventSequence.first()
        second = first.next()

        self.assertEqual(first, 1)
        self.assertEqual(second, 2)
        self.assertIsInstance(second, EventSequence)
        self.assertEqual(EventSequence.parse(3).to_json_value(), 3)

    def test_event_sequence_rejects_bool_and_zero(self) -> None:
        with self.assertRaises(TypeError):
            EventSequence(True)
        with self.assertRaises(ValueError):
            EventSequence(0)


class PayloadModelTests(unittest.TestCase):
    def test_transcript_payload_normalizes_and_serializes(self) -> None:
        payload = TranscriptEventPayload(
            text="hello",
            is_final=True,
            confidence=1,
        )

        self.assertEqual(payload.confidence, 1.0)
        self.assertEqual(
            dict(payload.as_dict()),
            {
                "kind": "transcript",
                "text": "hello",
                "is_final": True,
                "confidence": 1.0,
            },
        )
        with self.assertRaises(TypeError):
            payload.as_dict()["text"] = "changed"

    def test_response_payload_rejects_negative_delta(self) -> None:
        with self.assertRaises(ValueError):
            ResponseEventPayload(text="delta", delta_index=-1)

    def test_audio_payload_requires_opaque_reference(self) -> None:
        with self.assertRaises(ValueError):
            AudioEventPayload(available=True)

        payload = AudioEventPayload(
            artifact_ref="audio-artifact-001",
            available=True,
        )
        self.assertTrue(payload.available)
        self.assertEqual(payload.artifact_ref, "audio-artifact-001")

    def test_audio_payload_rejects_private_path_and_secret(self) -> None:
        with self.assertRaises(ValueError):
            AudioEventPayload(artifact_ref=r"C:\private\voice.mp3")
        with self.assertRaises(ValueError):
            AudioEventPayload(artifact_ref="api_token_value")

    def test_diagnostic_payload_normalizes_sequence(self) -> None:
        payload = DiagnosticEventPayload(
            code="history_overflow",
            dropped_sequence=3,
            overflow_count=2,
        )

        self.assertEqual(payload.dropped_sequence, EventSequence(3))
        self.assertEqual(dict(payload.as_dict())["dropped_sequence"], 3)

    def test_lifecycle_payload_normalizes_enums(self) -> None:
        payload = LifecycleEventPayload(
            outcome="completed",
            recovery_action="reuse_session",
            reason="done",
        )

        self.assertIs(payload.outcome, TurnOutcome.COMPLETED)
        self.assertIs(payload.recovery_action, RecoveryAction.REUSE_SESSION)
        self.assertEqual(dict(payload.as_dict())["reason"], "done")


if __name__ == "__main__":
    unittest.main()
