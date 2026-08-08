from __future__ import annotations

import json
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.motion import MotionRequest, MotionResult
from framework.vtube_studio_transport import (
    VTubeStudioTransportOperation,
    VTubeStudioTransportOutcome,
    VTubeStudioTransportResult,
)


class MotionCorrelationControlATests(unittest.TestCase):
    def _context(self) -> tuple[TurnId, GenerationId]:
        return TurnId.new(), GenerationId.new()

    def test_request_fields_are_additive_and_default_to_none(self) -> None:
        request = MotionRequest.expression_change("smile")
        self.assertEqual(
            tuple(MotionRequest.__dataclass_fields__)[:11],
            (
                "intent",
                "request_id",
                "expression",
                "emotion",
                "gesture",
                "speaking",
                "intensity",
                "duration_ms",
                "character_id",
                "model_id",
                "public_metadata",
            ),
        )
        self.assertIsNone(request.turn_id)
        self.assertIsNone(request.generation_id)
        self.assertIs(type(request.request_id), str)
        self.assertFalse(request.request_id.startswith("fw_generation_"))

    def test_result_legacy_prefix_and_defaults_remain_compatible(self) -> None:
        result = MotionResult.completed(session_id="motion-session")
        self.assertEqual(
            tuple(MotionResult.__dataclass_fields__)[:9],
            (
                "outcome",
                "state",
                "adapter_status",
                "public_error_code",
                "safe_message",
                "retryable",
                "request_id",
                "session_id",
                "public_metadata",
            ),
        )
        self.assertEqual(result.session_id, "motion-session")
        self.assertIsNone(result.turn_id)
        self.assertIsNone(result.generation_id)

    def test_all_request_factories_accept_typed_context(self) -> None:
        turn_id, generation_id = self._context()
        requests = (
            MotionRequest.expression_change(
                "smile", turn_id=turn_id, generation_id=generation_id
            ),
            MotionRequest.emotion_update(
                "happy", turn_id=turn_id, generation_id=generation_id
            ),
            MotionRequest.speaking_state(
                True, turn_id=turn_id, generation_id=generation_id
            ),
            MotionRequest.stop_motion(
                turn_id=turn_id, generation_id=generation_id
            ),
        )
        for request in requests:
            self.assertEqual(request.turn_id, turn_id)
            self.assertEqual(request.generation_id, generation_id)

    def test_serialized_context_normalizes_and_invalid_context_is_rejected(self) -> None:
        turn_id, generation_id = self._context()
        request = MotionRequest.expression_change(
            "smile",
            turn_id=str(turn_id),
            generation_id=str(generation_id),
        )
        self.assertIsInstance(request.turn_id, TurnId)
        self.assertIsInstance(request.generation_id, GenerationId)

        with self.assertRaises(ValueError):
            MotionRequest.expression_change(
                "smile", generation_id=GenerationId.new()
            )
        with self.assertRaises(ValueError):
            MotionRequest.expression_change(
                "smile", turn_id=str(SessionId.new())
            )
        with self.assertRaises(ValueError):
            MotionResult.completed(
                turn_id=turn_id, generation_id=generation_id
            )

    def test_result_factories_copy_request_context_with_session_identity(self) -> None:
        turn_id, generation_id = self._context()
        request = MotionRequest.expression_change(
            "smile", turn_id=turn_id, generation_id=generation_id
        )
        session_id = SessionId.new()
        results = (
            MotionResult.completed(request=request, session_id=session_id),
            MotionResult.unavailable(request=request, session_id=session_id),
            MotionResult.not_implemented(request=request, session_id=session_id),
            MotionResult.closed(request=request, session_id=session_id),
        )
        for result in results:
            self.assertEqual(result.request_id, request.request_id)
            self.assertEqual(result.session_id, session_id)
            self.assertEqual(result.turn_id, turn_id)
            self.assertEqual(result.generation_id, generation_id)

    def test_mock_result_and_mapping_events_preserve_request_context(self) -> None:
        turn_id, generation_id = self._context()
        request = MotionRequest.expression_change(
            "smile", turn_id=turn_id, generation_id=generation_id
        )
        events = []
        session = framework.create_motion_session()
        session.on_event(events.append)

        result = session.apply_motion(request)

        self.assertEqual(result.session_id, session.info.session_id)
        self.assertEqual(result.turn_id, turn_id)
        self.assertEqual(result.generation_id, generation_id)
        self.assertEqual(
            [event["type"] for event in events],
            ["motion.requested", "motion.started", "motion.completed"],
        )
        self.assertTrue(all(event["turn_id"] == str(turn_id) for event in events))
        self.assertTrue(
            all(event["generation_id"] == str(generation_id) for event in events)
        )
        json.dumps(
            [
                {
                    "session_id": event["session_id"],
                    "turn_id": event["turn_id"],
                    "generation_id": event["generation_id"],
                }
                for event in events
            ]
        )

    def test_guarded_and_closed_results_preserve_context_without_execution(self) -> None:
        turn_id, generation_id = self._context()
        request = MotionRequest.expression_change(
            "smile", turn_id=turn_id, generation_id=generation_id
        )
        guarded = framework.create_motion_session(
            adapter="vts",
            real_adapter_enabled=True,
            allow_provider_execution=False,
        )
        guarded_result = guarded.apply_motion(request)
        self.assertEqual(guarded_result.turn_id, turn_id)
        self.assertEqual(guarded_result.generation_id, generation_id)
        self.assertFalse(
            guarded_result.public_metadata.get("provider_call_executed", False)
        )

        session = framework.create_motion_session()
        session.close()
        closed_result = session.apply_motion(request)
        self.assertEqual(closed_result.turn_id, turn_id)
        self.assertEqual(closed_result.generation_id, generation_id)

    def test_vts_transport_projection_preserves_context_without_provider_call(self) -> None:
        turn_id, generation_id = self._context()
        request = MotionRequest.expression_change(
            "smile", turn_id=turn_id, generation_id=generation_id
        )
        session = framework.create_motion_session()
        transport_result = VTubeStudioTransportResult(
            operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
            outcome=VTubeStudioTransportOutcome.COMPLETED,
            request_id=request.request_id,
            public_metadata={
                "boundary": "test",
                "network_execution_attempted": False,
                "real_motion_executed": False,
            },
        )

        result, _ = session._vts_transport_result(
            request=request,
            transport_result=transport_result,
        )

        self.assertEqual(result.session_id, session.info.session_id)
        self.assertEqual(result.turn_id, turn_id)
        self.assertEqual(result.generation_id, generation_id)

    def test_control_a_mapping_remains_legacy_under_control_b_bridge(self) -> None:
        turn_id, generation_id = self._context()
        events = []
        realtime_events = []
        session = framework.create_motion_session()
        session.on_event(events.append)
        session.on_realtime_event(realtime_events.append)
        session.apply_motion(
            MotionRequest.expression_change(
                "smile", turn_id=turn_id, generation_id=generation_id
            )
        )
        self.assertNotIn("sequence", events[0])
        self.assertEqual(realtime_events, [])
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(session.info.api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
