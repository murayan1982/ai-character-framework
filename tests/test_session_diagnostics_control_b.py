"""Provider-free runtime tests for FW-RT6-10c Control B diagnostics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
from threading import Event, RLock, Thread
import time
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.lifecycle import RealtimePhase, TurnOutcome
from framework.output_control import TTSQueueState
from framework.realtime import (
    RealtimeErrorCode,
    RealtimeEventType,
    RealtimeState,
    RealtimeTurn,
)
from framework.realtime_generation_gate import RealtimeStageCompletionEnvelope
from framework.session_diagnostics import SessionDiagnosticsSnapshot


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _ObservedRLock:
    """Minimal RLock wrapper used to observe lock-order progress in one test."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.acquired = Event()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        result = self._lock.acquire(blocking, timeout)
        if result:
            self.acquired.set()
        return result

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> "_ObservedRLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.release()


class SessionDiagnosticsControlBTests(unittest.TestCase):
    def test_property_is_read_only_and_root_import_remains_lazy(self) -> None:
        session = framework.create_realtime_session()
        snapshot = session.diagnostics_snapshot

        self.assertIsInstance(snapshot, SessionDiagnosticsSnapshot)
        with self.assertRaises(AttributeError):
            session.diagnostics_snapshot = snapshot  # type: ignore[misc]
        self.assertNotIn("SessionDiagnosticsSnapshot", framework.__all__)
        self.assertFalse(hasattr(framework, "SessionDiagnosticsSnapshot"))
        self.assertEqual(len(framework.__all__), 127)

    def test_idle_snapshot_has_exact_zero_state(self) -> None:
        session = framework.create_realtime_session()
        snapshot = session.diagnostics_snapshot

        self.assertIs(snapshot.state, RealtimeState.IDLE)
        self.assertIs(snapshot.phase, RealtimePhase.IDLE)
        self.assertFalse(snapshot.is_closed)
        self.assertIsNone(snapshot.active_turn_id)
        self.assertIsNone(snapshot.active_generation_id)
        self.assertEqual(snapshot.queue_depth, 0)
        self.assertEqual(snapshot.active_generation_count, 0)
        self.assertIsNone(snapshot.last_terminal_result)
        self.assertIs(snapshot.last_safe_error_code, RealtimeErrorCode.NONE)
        self.assertEqual(snapshot.stale_completion_count, 0)
        self.assertEqual(snapshot.duplicate_terminal_count, 0)
        self.assertEqual(snapshot.overflow_count, 0)

    def test_active_snapshot_uses_generation_gate_identity(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="private-active-input")
        snapshot = session.diagnostics_snapshot

        self.assertTrue(started.accepted)
        self.assertEqual(snapshot.active_turn_id, started.turn_id)
        self.assertEqual(snapshot.active_generation_id, started.generation_id)
        self.assertEqual(snapshot.active_generation_count, 1)
        self.assertIs(snapshot.state, RealtimeState.LISTENING)
        self.assertIs(snapshot.phase, RealtimePhase.LISTENING)
        self.assertNotIn("private-active-input", repr(snapshot))

    def test_legacy_host_turn_id_is_preserved_for_active_and_terminal_views(self) -> None:
        session = framework.create_realtime_session()
        legacy_turn_id = "legacy-host-turn"
        turn = RealtimeTurn(
            session_id=session.info.session_id,
            turn_id=legacy_turn_id,
            input_text="private-legacy-input",
        )
        started = session.start_turn(turn)

        self.assertTrue(started.accepted)
        self.assertEqual(session.diagnostics_snapshot.active_turn_id, legacy_turn_id)
        session.close()
        terminal = session.diagnostics_snapshot.last_terminal_result
        self.assertIsNotNone(terminal)
        assert terminal is not None
        self.assertEqual(terminal.turn_id, legacy_turn_id)
        self.assertNotIn("private-legacy-input", repr(terminal))

    def test_terminal_event_callback_observes_no_retired_active_generation(self) -> None:
        session = framework.create_realtime_session()
        observed: list[SessionDiagnosticsSnapshot] = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.SESSION_CLOSED:
                observed.append(session.diagnostics_snapshot)

        session.on_event(callback)
        session.start_turn(input_text="private-callback-input")
        session.close()

        self.assertEqual(len(observed), 1)
        snapshot = observed[0]
        self.assertIsNone(snapshot.active_turn_id)
        self.assertIsNone(snapshot.active_generation_id)
        self.assertEqual(snapshot.active_generation_count, 0)
        self.assertIsNotNone(snapshot.last_terminal_result)
        self.assertNotIn("private-callback-input", repr(snapshot))

    def test_close_snapshot_is_terminal_closed_and_has_no_active_context(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="private-close-input")
        session.close()
        snapshot = session.diagnostics_snapshot

        self.assertIs(snapshot.state, RealtimeState.CLOSED)
        self.assertIsNone(snapshot.phase)
        self.assertTrue(snapshot.is_closed)
        self.assertIsNone(snapshot.active_turn_id)
        self.assertIsNone(snapshot.active_generation_id)
        self.assertEqual(snapshot.active_generation_count, 0)
        terminal = snapshot.last_terminal_result
        self.assertIsNotNone(terminal)
        assert terminal is not None
        self.assertEqual(terminal.turn_id, started.turn_id)
        self.assertIs(terminal.outcome, TurnOutcome.CLOSED)
        self.assertIs(
            snapshot.last_safe_error_code,
            RealtimeErrorCode.SESSION_CLOSED,
        )

    def test_queue_projection_keeps_only_queued_count(self) -> None:
        session = framework.create_realtime_session()
        session.get_tts_queue_state = lambda: TTSQueueState(  # type: ignore[method-assign]
            queued_count=7,
            current_item_id="private-item-identity",
            is_playing=True,
            safe_message="private-queue-message",
            public_metadata={"provider_payload": "private-queue-payload"},
        )
        snapshot = session.diagnostics_snapshot
        rendered = json.dumps(snapshot.as_dict(), sort_keys=True)

        self.assertEqual(snapshot.queue_depth, 7)
        self.assertNotIn("private-item-identity", rendered)
        self.assertNotIn("private-queue-message", rendered)
        self.assertNotIn("private-queue-payload", rendered)

    def test_stale_count_reuses_generation_gate_diagnostics(self) -> None:
        session = framework.create_realtime_session()
        started = session.start_turn(input_text="private-stale-input")
        assert started.generation_id is not None
        session.cancel_current_turn()
        delivered: list[str] = []
        decision = session._apply_stage_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=started.turn_id,
                generation_id=started.generation_id,
                stage="text_generation",
                value="private-stale-value",
            ),
            deliver=delivered.append,
        )
        snapshot = session.diagnostics_snapshot

        self.assertFalse(decision.accepted)
        self.assertEqual(delivered, [])
        self.assertEqual(snapshot.stale_completion_count, 1)
        self.assertEqual(
            snapshot.stale_completion_count,
            session.generation_diagnostics["stale_completion_count"],
        )
        self.assertNotIn("private-stale-value", repr(snapshot))

    def test_duplicate_count_reuses_terminal_registry_diagnostics(self) -> None:
        session = framework.create_realtime_session()
        session.start_turn(input_text="private-duplicate-input")
        session.close()
        record = session._terminal_registry.records[-1]
        decision = session._terminal_registry.commit(
            record.turn_id,
            record.outcome,
            recovery_action=record.recovery_action,
            reason=record.reason,
            result=record.result,
        )
        snapshot = session.diagnostics_snapshot

        self.assertFalse(decision.accepted)
        self.assertEqual(snapshot.duplicate_terminal_count, 1)
        self.assertEqual(
            snapshot.duplicate_terminal_count,
            session.terminal_diagnostics["duplicate_terminal_count"],
        )

    def test_overflow_count_reuses_event_hub_diagnostics(self) -> None:
        session = framework.create_realtime_session()
        for _ in range(70):
            session.emit_created()
        snapshot = session.diagnostics_snapshot

        self.assertGreater(snapshot.overflow_count, 0)
        self.assertEqual(
            snapshot.overflow_count,
            session.event_diagnostics["history_overflow_count"],
        )

    def test_each_read_is_a_new_frozen_value(self) -> None:
        session = framework.create_realtime_session()
        first = session.diagnostics_snapshot
        second = session.diagnostics_snapshot

        self.assertIsNot(first, second)
        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            first.queue_depth = 1  # type: ignore[misc]

    def test_inverted_existing_lock_contention_does_not_deadlock(self) -> None:
        session = framework.create_realtime_session()
        observed_lock = _ObservedRLock()
        session._operation_lock = observed_lock  # type: ignore[assignment]
        snapshot_box: list[SessionDiagnosticsSnapshot] = []

        session._turn_admission_lock.acquire()
        worker = Thread(
            target=lambda: snapshot_box.append(session.diagnostics_snapshot),
            daemon=True,
        )
        worker.start()
        self.assertTrue(observed_lock.acquired.wait(0.5))
        time.sleep(0.01)
        operation_available = observed_lock.acquire(timeout=0.5)
        if operation_available:
            observed_lock.release()
        session._turn_admission_lock.release()
        worker.join(1.0)

        self.assertTrue(operation_available)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(snapshot_box), 1)

    def test_versions_and_provider_isolation_remain_after_aggregate_acceptance(self) -> None:
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split("## FW-RT6-10c — Public diagnostics", 1)[1].split(
            "## FW-RT6-10d", 1
        )[0]

        self.assertEqual(section.count("- [ ]"), 0)
        self.assertEqual(section.count("- [x]"), 9)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        for module_name in (
            "pyvts",
            "websockets",
            "pyaudio",
            "sounddevice",
            "openai",
        ):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
