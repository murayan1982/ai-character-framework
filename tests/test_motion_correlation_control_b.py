from __future__ import annotations

import inspect
import threading
from types import SimpleNamespace
import unittest

import framework
from framework.identity import EventSequence, TurnId
from framework.lifecycle import RealtimePhase
from framework.motion import MotionEventType, MotionOutcome, MotionRequest
from framework.realtime import RealtimeEvent, RealtimeEventType, RealtimeState
from framework.realtime_event_hub import RealtimeEventHub
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeGenerationGate,
)
from framework.vtube_studio_transport import (
    VTubeStudioTransportOperation,
    VTubeStudioTransportOutcome,
    VTubeStudioTransportResult,
)


class _BlockingVtsComposition:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.closed = False

    def resolve_request(self, request: MotionRequest) -> SimpleNamespace:
        return SimpleNamespace(resolved=True, request=request, reason="resolved")

    def trigger(self, request: MotionRequest) -> VTubeStudioTransportResult:
        self.entered.set()
        if not self.release.wait(timeout=2.0):
            raise AssertionError("test did not release the synthetic VTS completion")
        return VTubeStudioTransportResult(
            operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
            outcome=VTubeStudioTransportOutcome.COMPLETED,
            request_id=request.request_id,
            public_metadata={
                "boundary": "synthetic_vts",
                "network_execution_attempted": False,
                "late_completion_suppressed": False,
                "real_motion_executed": False,
            },
        )

    def close(self) -> None:
        self.closed = True
        self.release.set()


def _vts_session() -> framework.MotionSession:
    session = framework.create_motion_session(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
        runtime_available=True,
        model_selected=True,
        vts_endpoint_host="synthetic.invalid",
        vts_endpoint_port=8001,
        vts_authentication_token="synthetic-test-token",
        vts_hotkey_bindings={"expression:smile": "SyntheticSmile"},
    )
    session._vts_preflight_ready = True
    return session


class MotionCorrelationControlBTests(unittest.TestCase):
    def _bound_session(self):
        hub = RealtimeEventHub[RealtimeEvent]()
        gate = RealtimeGenerationGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        session = framework.create_motion_session()
        session._bind_realtime_coordination(
            event_hub=hub,
            generation_gate=gate,
        )
        return session, hub, gate, turn_id, generation_id

    def test_shared_hub_owns_motion_sequence_and_typed_payload(self) -> None:
        session, hub, gate, turn_id, generation_id = self._bound_session()
        scoped_events = []
        session.on_realtime_event(scoped_events.append)

        other_session_id = framework.SessionId.new()
        hub.emit(
            lambda sequence: RealtimeEvent(
                type=RealtimeEventType.SESSION_CREATED,
                state=RealtimeState.IDLE,
                session_id=other_session_id,
                sequence=sequence,
                phase=RealtimePhase.IDLE,
            )
        )
        result = session.apply_motion(
            MotionRequest.expression_change(
                "smile",
                turn_id=turn_id,
                generation_id=generation_id,
            )
        )

        self.assertEqual(result.outcome, MotionOutcome.COMPLETED)
        self.assertEqual(
            [event.type for event in scoped_events],
            [
                RealtimeEventType.MOTION_REQUESTED,
                RealtimeEventType.MOTION_STARTED,
                RealtimeEventType.MOTION_COMPLETED,
            ],
        )
        self.assertEqual([int(event.sequence) for event in scoped_events], [2, 3, 4])
        self.assertEqual(
            [int(event.sequence) for event in hub.event_history],
            [1, 2, 3, 4],
        )
        self.assertTrue(
            all(event.payload.request_id == result.request_id for event in scoped_events)
        )
        self.assertEqual(gate.diagnostics["accepted_completion_count"], 1)

    def test_legacy_mapping_stays_unsequenced_and_correlated(self) -> None:
        session, _hub, _gate, turn_id, generation_id = self._bound_session()
        events = []
        session.on_event(events.append)
        result = session.apply_motion(
            MotionRequest.expression_change(
                "smile",
                turn_id=turn_id,
                generation_id=generation_id,
            )
        )

        self.assertEqual(
            [event["type"] for event in events],
            ["motion.requested", "motion.started", "motion.completed"],
        )
        self.assertTrue(all("sequence" not in event for event in events))
        self.assertTrue(all(event["turn_id"] == str(turn_id) for event in events))
        self.assertTrue(
            all(event["generation_id"] == str(generation_id) for event in events)
        )
        self.assertEqual(result.session_id, session.info.session_id)

    def test_unbound_standalone_does_not_allocate_competing_sequence(self) -> None:
        session = framework.create_motion_session()
        legacy_events = []
        canonical_events = []
        session.on_event(legacy_events.append)
        session.on_realtime_event(canonical_events.append)

        result = session.apply_motion(MotionRequest.expression_change("smile"))

        self.assertEqual(result.outcome, MotionOutcome.COMPLETED)
        self.assertIsNone(result.turn_id)
        self.assertIsNone(result.generation_id)
        self.assertEqual(canonical_events, [])
        self.assertEqual(len(legacy_events), 3)
        self.assertTrue(all("sequence" not in event for event in legacy_events))

    def test_started_callback_can_retire_generation_before_mock_completion(self) -> None:
        session, _hub, gate, turn_id, generation_id = self._bound_session()
        canonical_events = []
        legacy_events = []

        def retire_on_started(event: RealtimeEvent) -> None:
            canonical_events.append(event)
            if event.type is RealtimeEventType.MOTION_STARTED:
                gate.advance(GenerationAdvanceReason.INTERRUPT)

        session.on_realtime_event(retire_on_started)
        session.on_event(legacy_events.append)
        result = session.apply_motion(
            MotionRequest.expression_change(
                "smile",
                turn_id=turn_id,
                generation_id=generation_id,
            )
        )

        self.assertEqual(result.outcome, MotionOutcome.INTERRUPTED)
        self.assertEqual(result.public_metadata["late_motion_completion_delivered"], False)
        self.assertEqual(
            [event.type for event in canonical_events],
            [
                RealtimeEventType.MOTION_REQUESTED,
                RealtimeEventType.MOTION_STARTED,
                RealtimeEventType.STALE_RESULT_DROPPED,
            ],
        )
        self.assertNotIn(RealtimeEventType.MOTION_COMPLETED, [e.type for e in canonical_events])
        self.assertEqual(legacy_events[-1]["type"], MotionEventType.INTERRUPTED.value)
        self.assertNotIn("motion.completed", [event["type"] for event in legacy_events])
        self.assertEqual(gate.diagnostics["stale_completion_count"], 1)

    def test_late_vts_completion_is_dropped_by_common_gate(self) -> None:
        hub = RealtimeEventHub[RealtimeEvent]()
        gate = RealtimeGenerationGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        session = _vts_session()
        composition = _BlockingVtsComposition()
        session._vts_composition = composition
        session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)
        canonical_events = []
        legacy_events = []
        session.on_realtime_event(canonical_events.append)
        session.on_event(legacy_events.append)
        request = MotionRequest.expression_change(
            "smile",
            turn_id=turn_id,
            generation_id=generation_id,
        )
        result_box = []

        worker = threading.Thread(
            target=lambda: result_box.append(session.apply_motion(request)),
            daemon=True,
        )
        worker.start()
        self.assertTrue(composition.entered.wait(timeout=1.0))
        gate.advance(GenerationAdvanceReason.INTERRUPT)
        composition.release.set()
        worker.join(timeout=2.0)

        self.assertFalse(worker.is_alive())
        self.assertEqual(len(result_box), 1)
        self.assertEqual(result_box[0].outcome, MotionOutcome.INTERRUPTED)
        self.assertEqual(
            result_box[0].public_metadata["vts_lifecycle_generation_guard_preserved"],
            True,
        )
        self.assertNotIn(
            RealtimeEventType.MOTION_COMPLETED,
            [event.type for event in canonical_events],
        )
        self.assertNotIn("motion.completed", [event["type"] for event in legacy_events])
        self.assertEqual(canonical_events[-1].type, RealtimeEventType.STALE_RESULT_DROPPED)

    def test_unknown_correlated_generation_is_rejected_without_owner_replacement(self) -> None:
        hub = RealtimeEventHub[RealtimeEvent]()
        gate = RealtimeGenerationGate()
        active_turn = TurnId.new()
        active_generation = gate.start_generation(active_turn)
        session = framework.create_motion_session()
        session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)
        request_turn = TurnId.new()
        request_generation = framework.GenerationId.new()

        result = session.apply_motion(
            MotionRequest.expression_change(
                "smile",
                turn_id=request_turn,
                generation_id=request_generation,
            )
        )

        self.assertEqual(result.outcome, MotionOutcome.INTERRUPTED)
        self.assertEqual(gate.current_turn_id, active_turn)
        self.assertEqual(gate.current_generation_id, active_generation)
        self.assertEqual(gate.diagnostics["generation_start_count"], 1)

    def test_binding_is_single_owner_and_close_releases_scoped_subscriber(self) -> None:
        session, hub, gate, _turn_id, _generation_id = self._bound_session()
        session.on_realtime_event(lambda _event: None)
        self.assertEqual(hub.subscriber_count, 1)
        session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)
        self.assertEqual(hub.subscriber_count, 1)
        with self.assertRaises(RuntimeError):
            session._bind_realtime_coordination(
                event_hub=RealtimeEventHub[RealtimeEvent](),
                generation_gate=gate,
            )
        session.close()
        self.assertEqual(hub.subscriber_count, 0)
        session.on_realtime_event(lambda _event: None)
        self.assertEqual(hub.subscriber_count, 0)

    def test_public_surface_and_v55_factory_signature_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        self.assertEqual(
            set(inspect.signature(framework.create_motion_session).parameters),
            {
                "project_root",
                "adapter",
                "real_adapter_enabled",
                "allow_provider_execution",
                "runtime_available",
                "model_selected",
                "vts_endpoint_host",
                "vts_endpoint_port",
                "vts_authentication_token",
                "vts_hotkey_bindings",
                "vts_connect_timeout_seconds",
                "vts_authenticate_timeout_seconds",
                "vts_request_timeout_seconds",
                "vts_close_timeout_seconds",
                "public_metadata",
            },
        )


if __name__ == "__main__":
    unittest.main()
