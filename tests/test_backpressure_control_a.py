"""Provider-free FW-RT6-12b Control A contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib
from pathlib import Path
import subprocess
import sys
import unittest

import framework


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "framework.backpressure"
EXPECTED_EXPORTS = (
    "BACKPRESSURE_API_VERSION",
    "BackpressureBoundary",
    "BackpressureState",
    "BackpressureOverflowPolicy",
    "BackpressureOperationKind",
    "BackpressureRejectionCode",
    "BackpressureCapability",
    "BackpressureSnapshot",
    "BackpressureAdmission",
    "BackpressureAdmissionResult",
    "BackpressureOverflowEvent",
    "BackpressureControlResult",
)


class BackpressureControlATests(unittest.TestCase):
    @staticmethod
    def _snapshot(
        *,
        boundary: str = "audio_input",
        state: str = "accepting",
        pending: int = 0,
        in_flight: int = 0,
        maximum_pending: int = 2,
        maximum_in_flight: int = 1,
        overflow: int = 0,
    ):
        from framework.backpressure import BackpressureSnapshot

        return BackpressureSnapshot(
            boundary=boundary,
            state=state,
            pending_count=pending,
            in_flight_count=in_flight,
            maximum_pending_count=maximum_pending,
            maximum_in_flight_count=maximum_in_flight,
            overflow_count=overflow,
        )

    def test_namespace_has_exact_explicit_exports(self) -> None:
        namespace = importlib.import_module(NAMESPACE)

        self.assertEqual(namespace.__all__, EXPECTED_EXPORTS)
        self.assertEqual(namespace.BACKPRESSURE_API_VERSION, "6.0")
        self.assertEqual(len(namespace.__all__), len(set(namespace.__all__)))

    def test_namespace_import_is_provider_network_and_device_safe(self) -> None:
        code = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.backpressure as backpressure
assert len(backpressure.__all__) == 12
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

    def test_framework_root_remains_frozen_and_explicit_only(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        for name in EXPECTED_EXPORTS:
            self.assertNotIn(name, framework.__all__)

    def test_boundary_and_policy_vocabularies_are_exact(self) -> None:
        from framework.backpressure import (
            BackpressureBoundary,
            BackpressureOperationKind,
            BackpressureOverflowPolicy,
            BackpressureRejectionCode,
            BackpressureState,
        )

        self.assertEqual(
            tuple(item.value for item in BackpressureBoundary),
            ("audio_input", "response_delta", "voice_output", "event_subscriber"),
        )
        self.assertEqual(
            tuple(item.value for item in BackpressureState),
            ("accepting", "paused", "closed"),
        )
        self.assertEqual(
            tuple(item.value for item in BackpressureOverflowPolicy),
            ("reject_newest",),
        )
        self.assertEqual(
            tuple(item.value for item in BackpressureOperationKind),
            ("admit", "pause", "resume"),
        )
        self.assertEqual(
            tuple(item.value for item in BackpressureRejectionCode),
            (
                "none",
                "capacity_reached",
                "paused",
                "closed",
                "already_paused",
                "already_accepting",
            ),
        )

    def test_default_capability_is_truthfully_unsupported(self) -> None:
        from framework.backpressure import BackpressureCapability

        capability = BackpressureCapability(boundary="audio_input")
        self.assertFalse(capability.supported)
        self.assertIsNone(capability.maximum_pending_count)
        self.assertIsNone(capability.maximum_in_flight_count)
        self.assertFalse(capability.pause_resume_supported)
        self.assertFalse(capability.retryable_rejection_supported)
        self.assertFalse(capability.overflow_event_supported)
        self.assertFalse(capability.silent_drop)
        self.assertEqual(capability.overflow_policy.value, "reject_newest")

    def test_supported_capability_requires_limits_rejection_and_event(self) -> None:
        from framework.backpressure import BackpressureBoundary, BackpressureCapability

        for boundary in BackpressureBoundary:
            capability = BackpressureCapability(
                boundary=boundary,
                supported=True,
                maximum_pending_count=3,
                maximum_in_flight_count=2,
                pause_resume_supported=True,
                retryable_rejection_supported=True,
                overflow_event_supported=True,
                public_metadata={"source": "fake"},
            )
            self.assertEqual(capability.boundary, boundary)
            self.assertEqual(capability.maximum_pending_count, 3)
            self.assertEqual(capability.maximum_in_flight_count, 2)
            self.assertFalse(capability.as_dict()["silent_drop"])

    def test_capability_rejects_overclaim_and_silent_drop(self) -> None:
        from framework.backpressure import BackpressureCapability

        invalid = (
            {"supported": True},
            {
                "supported": True,
                "maximum_pending_count": 1,
                "maximum_in_flight_count": 1,
            },
            {"maximum_pending_count": 1},
            {"silent_drop": True},
            {"maximum_pending_count": 0},
            {"maximum_in_flight_count": True},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                BackpressureCapability(boundary="audio_input", **kwargs)

    def test_snapshot_reports_pending_in_flight_and_capacity(self) -> None:
        snapshot = self._snapshot(pending=2, in_flight=0, overflow=3)
        self.assertTrue(snapshot.at_capacity)
        self.assertEqual(snapshot.as_dict()["maximum_in_flight_count"], 1)
        self.assertEqual(snapshot.as_dict()["overflow_count"], 3)

        in_flight_full = self._snapshot(pending=0, in_flight=1)
        self.assertTrue(in_flight_full.at_capacity)
        self.assertFalse(self._snapshot().at_capacity)

    def test_snapshot_rejects_counts_outside_fixed_limits(self) -> None:
        for kwargs in (
            {"pending": 3},
            {"in_flight": 2},
            {"pending": -1},
            {"maximum_pending": 0},
            {"overflow": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                self._snapshot(**kwargs)

    def test_admission_is_opaque_public_safe_and_payload_free(self) -> None:
        from framework.backpressure import BackpressureAdmission
        from framework.public_safety import REDACTED_BINARY, REDACTED_VALUE

        admission = BackpressureAdmission(
            boundary="response_delta",
            item_id="delta_0001",
            public_metadata={"payload": b"private", "api_key": "private"},
        )
        projection = admission.as_dict()
        self.assertEqual(projection["item_id"], "delta_0001")
        self.assertEqual(projection["public_metadata"]["payload"], REDACTED_BINARY)
        self.assertEqual(projection["public_metadata"]["api_key"], REDACTED_VALUE)
        self.assertNotIn("private", repr(admission))
        self.assertFalse(hasattr(admission, "payload"))

        for invalid in ("", "C:\\private\\audio.raw", "https://private.invalid"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                BackpressureAdmission(boundary="audio_input", item_id=invalid)

    def test_accepted_admission_is_typed_and_never_dropped(self) -> None:
        from framework.backpressure import (
            BackpressureAdmission,
            BackpressureAdmissionResult,
        )

        result = BackpressureAdmissionResult(
            accepted=True,
            admission=BackpressureAdmission("voice_output", "voice_1"),
            snapshot=self._snapshot(boundary="voice_output", pending=1),
            safe_message="Accepted.",
        )
        self.assertTrue(result.accepted)
        self.assertFalse(result.retryable)
        self.assertFalse(result.dropped)
        self.assertEqual(result.as_dict()["rejection_code"], "none")

    def test_capacity_rejection_is_retryable_non_silent_and_non_consuming(self) -> None:
        from framework.backpressure import (
            BackpressureAdmission,
            BackpressureAdmissionResult,
            BackpressureRejectionCode,
        )

        admission = BackpressureAdmission("audio_input", "chunk_8")
        snapshot = self._snapshot(pending=2, overflow=1)
        result = BackpressureAdmissionResult(
            accepted=False,
            admission=admission,
            snapshot=snapshot,
            rejection_code=BackpressureRejectionCode.CAPACITY_REACHED,
            safe_message="Capacity reached.",
            retryable=True,
        )
        self.assertFalse(result.accepted)
        self.assertTrue(result.retryable)
        self.assertFalse(result.dropped)
        self.assertEqual(result.admission.item_id, "chunk_8")

    def test_paused_and_closed_rejections_have_truthful_retry_semantics(self) -> None:
        from framework.backpressure import (
            BackpressureAdmission,
            BackpressureAdmissionResult,
            BackpressureRejectionCode,
        )

        admission = BackpressureAdmission("event_subscriber", "event_4")
        paused = BackpressureAdmissionResult(
            accepted=False,
            admission=admission,
            snapshot=self._snapshot(boundary="event_subscriber", state="paused"),
            rejection_code=BackpressureRejectionCode.PAUSED,
            retryable=True,
        )
        closed = BackpressureAdmissionResult(
            accepted=False,
            admission=admission,
            snapshot=self._snapshot(boundary="event_subscriber", state="closed"),
            rejection_code=BackpressureRejectionCode.CLOSED,
            retryable=False,
        )
        self.assertTrue(paused.retryable)
        self.assertFalse(closed.retryable)

    def test_admission_result_rejects_false_retry_or_drop_claims(self) -> None:
        from framework.backpressure import (
            BackpressureAdmission,
            BackpressureAdmissionResult,
            BackpressureRejectionCode,
        )

        admission = BackpressureAdmission("audio_input", "chunk_9")
        full = self._snapshot(pending=2)
        invalid = (
            {"accepted": True, "rejection_code": "capacity_reached"},
            {"accepted": True, "retryable": True},
            {
                "accepted": False,
                "rejection_code": BackpressureRejectionCode.CAPACITY_REACHED,
                "retryable": False,
            },
            {
                "accepted": False,
                "rejection_code": BackpressureRejectionCode.CAPACITY_REACHED,
                "retryable": True,
                "dropped": True,
            },
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BackpressureAdmissionResult(
                    admission=admission,
                    snapshot=full,
                    **kwargs,
                )

    def test_overflow_event_is_required_to_be_full_retryable_and_non_dropping(self) -> None:
        from framework.backpressure import (
            BackpressureAdmission,
            BackpressureOverflowEvent,
        )

        admission = BackpressureAdmission("response_delta", "delta_5")
        event = BackpressureOverflowEvent(
            admission=admission,
            snapshot=self._snapshot(boundary="response_delta", in_flight=1, overflow=1),
        )
        self.assertEqual(event.boundary.value, "response_delta")
        self.assertEqual(event.as_dict()["rejection_code"], "capacity_reached")
        self.assertTrue(event.retryable)
        self.assertFalse(event.dropped)

        for kwargs in (
            {"snapshot": self._snapshot(boundary="response_delta")},
            {
                "snapshot": self._snapshot(
                    boundary="response_delta", in_flight=1, overflow=1
                ),
                "retryable": False,
            },
            {
                "snapshot": self._snapshot(
                    boundary="response_delta", in_flight=1, overflow=1
                ),
                "dropped": True,
            },
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BackpressureOverflowEvent(admission=admission, **kwargs)

    def test_pause_and_resume_are_typed_and_do_not_cancel_or_drop(self) -> None:
        from framework.backpressure import BackpressureControlResult

        paused = BackpressureControlResult(
            kind="pause",
            boundary="voice_output",
            accepted=True,
            previous_state="accepting",
            current_state="paused",
            snapshot=self._snapshot(boundary="voice_output", state="paused", pending=1),
        )
        resumed = BackpressureControlResult(
            kind="resume",
            boundary="voice_output",
            accepted=True,
            previous_state="paused",
            current_state="accepting",
            snapshot=self._snapshot(boundary="voice_output", state="accepting", pending=1),
        )
        self.assertEqual(paused.cancelled_count, 0)
        self.assertFalse(paused.dropped)
        self.assertEqual(resumed.current_state.value, "accepting")

    def test_duplicate_pause_resume_and_closed_control_are_typed(self) -> None:
        from framework.backpressure import BackpressureControlResult

        cases = (
            ("pause", "paused", "already_paused"),
            ("resume", "accepting", "already_accepting"),
            ("pause", "closed", "closed"),
            ("resume", "closed", "closed"),
        )
        for kind, state, code in cases:
            result = BackpressureControlResult(
                kind=kind,
                boundary="audio_input",
                accepted=False,
                previous_state=state,
                current_state=state,
                snapshot=self._snapshot(state=state),
                rejection_code=code,
            )
            self.assertFalse(result.accepted)
            self.assertEqual(result.rejection_code.value, code)

    def test_models_are_immutable_and_safe_messages_reject_paths(self) -> None:
        from framework.backpressure import (
            BackpressureAdmission,
            BackpressureAdmissionResult,
        )

        admission = BackpressureAdmission("audio_input", "chunk_10")
        with self.assertRaises(FrozenInstanceError):
            admission.item_id = "changed"  # type: ignore[misc]
        with self.assertRaises(ValueError):
            BackpressureAdmissionResult(
                accepted=True,
                admission=admission,
                snapshot=self._snapshot(),
                safe_message="C:\\private\\payload.raw",
            )

    def test_control_a_leaves_runtime_and_task_closure_for_control_b(self) -> None:
        from framework.backpressure import BackpressureCapability
        from framework.voice_input_streaming import VoiceInputStreamingCapability

        self.assertFalse(
            VoiceInputStreamingCapability().audio_chunk_input_supported
        )
        self.assertFalse(
            framework.get_capabilities()
            .realtime_snapshot.voice_input.backpressure_supported
        )
        self.assertFalse(BackpressureCapability(boundary="audio_input").supported)

        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
        section = tasklist.split("## FW-RT6-12b — P1 backpressure", 1)[1].split(
            "## FW-RT6-12c", 1
        )[0]
        self.assertEqual(section.count("- [ ]"), 6)
        self.assertEqual(section.count("- [x]"), 0)
        self.assertIn("FW-RT6-12a-FINAL-ACCEPTANCE-SYNC:BEGIN", tasklist)
        acceptance_marker_count = tasklist.count(
            "FW-RT6-12b-A-ACCEPTANCE-SYNC:BEGIN"
        )
        self.assertLessEqual(acceptance_marker_count, 1)
        if acceptance_marker_count:
            self.assertEqual(
                tasklist.count("FW-RT6-12b-A-ACCEPTANCE-SYNC:END"),
                1,
            )
            self.assertIn(
                "Control A: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
                tasklist,
            )


if __name__ == "__main__":
    unittest.main()
