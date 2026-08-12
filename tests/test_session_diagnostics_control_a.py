"""Provider-free tests for FW-RT6-10c Control A diagnostics models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import json
import sys
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.lifecycle import RealtimePhase, RecoveryAction, TurnOutcome
from framework.realtime import RealtimeErrorCode, RealtimeState, RealtimeTurnResult
from framework.session_diagnostics import (
    SessionDiagnosticsSnapshot,
    SessionTerminalSnapshot,
    build_session_diagnostics_snapshot,
    build_session_terminal_snapshot,
)


class SessionDiagnosticsControlATests(unittest.TestCase):
    def setUp(self) -> None:
        self.session_id = SessionId.new()
        self.turn_id = TurnId.new()
        self.generation_id = GenerationId.new()

    def _failed_result(self) -> RealtimeTurnResult:
        return RealtimeTurnResult.failed(
            session_id=self.session_id,
            turn_id=self.turn_id,
            generation_id=self.generation_id,
            public_error_code=RealtimeErrorCode.PROVIDER_ERROR,
            safe_message="private-safe-message-sentinel",
            retryable=True,
            recovery_action=RecoveryAction.RECONNECT,
            public_metadata={
                "provider_payload": "private-payload-sentinel",
                "private_path": "C:/private/diagnostics.txt",
            },
        )

    def test_explicit_exports_are_exact_and_root_surface_is_unchanged(self) -> None:
        import framework.session_diagnostics as diagnostics

        self.assertEqual(
            tuple(diagnostics.__all__),
            (
                "SessionTerminalSnapshot",
                "SessionDiagnosticsSnapshot",
                "build_session_terminal_snapshot",
                "build_session_diagnostics_snapshot",
            ),
        )
        self.assertNotIn("SessionDiagnosticsSnapshot", framework.__all__)
        self.assertFalse(hasattr(framework, "SessionDiagnosticsSnapshot"))
        self.assertEqual(len(framework.__all__), 127)

    def test_terminal_projection_has_exact_public_safe_fields(self) -> None:
        terminal = build_session_terminal_snapshot(self._failed_result())
        self.assertIsNotNone(terminal)
        assert terminal is not None
        self.assertEqual(
            tuple(field.name for field in fields(terminal)),
            (
                "session_id",
                "turn_id",
                "generation_id",
                "outcome",
                "public_error_code",
                "retryable",
                "recovery_action",
            ),
        )
        self.assertIs(terminal.outcome, TurnOutcome.FAILED)
        self.assertIs(terminal.public_error_code, RealtimeErrorCode.PROVIDER_ERROR)
        self.assertIs(terminal.recovery_action, RecoveryAction.RECONNECT)

    def test_terminal_projection_discards_private_rich_result_values(self) -> None:
        terminal = build_session_terminal_snapshot(self._failed_result())
        serialized = json.dumps(terminal.as_dict(), sort_keys=True)  # type: ignore[union-attr]
        rendered = repr(terminal)
        for secret in (
            "private-safe-message-sentinel",
            "private-payload-sentinel",
            "C:/private/diagnostics.txt",
            "provider_payload",
            "public_metadata",
            "input_text",
            "output_text",
            "audio",
        ):
            self.assertNotIn(secret, serialized)
            self.assertNotIn(secret, rendered)

    def test_terminal_projection_normalizes_all_public_ids(self) -> None:
        result = RealtimeTurnResult.failed(
            session_id=str(self.session_id),
            turn_id=str(self.turn_id),
            generation_id=str(self.generation_id),
        )
        terminal = build_session_terminal_snapshot(result)
        assert terminal is not None
        self.assertIsInstance(terminal.session_id, SessionId)
        self.assertIsInstance(terminal.turn_id, TurnId)
        self.assertIsInstance(terminal.generation_id, GenerationId)

    def test_terminal_projection_none_and_missing_session_are_explicit(self) -> None:
        self.assertIsNone(build_session_terminal_snapshot(None))
        with self.assertRaisesRegex(ValueError, "session_id"):
            build_session_terminal_snapshot(
                RealtimeTurnResult.completed(turn_id=self.turn_id)
            )
        with self.assertRaises(TypeError):
            build_session_terminal_snapshot(object())  # type: ignore[arg-type]

    def test_idle_snapshot_is_exact_and_derives_no_error(self) -> None:
        snapshot = build_session_diagnostics_snapshot(
            session_id=str(self.session_id),
            state="idle",
            phase="idle",
            is_closed=False,
        )
        self.assertIsInstance(snapshot.session_id, SessionId)
        self.assertIs(snapshot.state, RealtimeState.IDLE)
        self.assertIs(snapshot.phase, RealtimePhase.IDLE)
        self.assertIs(snapshot.last_safe_error_code, RealtimeErrorCode.NONE)
        self.assertEqual(snapshot.queue_depth, 0)
        self.assertEqual(snapshot.active_generation_count, 0)
        self.assertIsNone(snapshot.last_terminal_result)

    def test_active_snapshot_requires_one_paired_context(self) -> None:
        snapshot = build_session_diagnostics_snapshot(
            session_id=self.session_id,
            state=RealtimeState.THINKING,
            phase=RealtimePhase.THINKING,
            is_closed=False,
            active_turn_id=self.turn_id,
            active_generation_id=self.generation_id,
            active_generation_count=1,
            queue_depth=2,
        )
        self.assertEqual(snapshot.active_turn_id, self.turn_id)
        self.assertEqual(snapshot.active_generation_id, self.generation_id)
        with self.assertRaisesRegex(ValueError, "both be present"):
            build_session_diagnostics_snapshot(
                session_id=self.session_id,
                state=RealtimeState.THINKING,
                phase=RealtimePhase.THINKING,
                is_closed=False,
                active_turn_id=self.turn_id,
            )
        with self.assertRaisesRegex(ValueError, "must match"):
            build_session_diagnostics_snapshot(
                session_id=self.session_id,
                state=RealtimeState.IDLE,
                phase=RealtimePhase.IDLE,
                is_closed=False,
                active_generation_count=1,
            )

    def test_closed_snapshot_rejects_active_context_and_state_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "closed diagnostics"):
            build_session_diagnostics_snapshot(
                session_id=self.session_id,
                state=RealtimeState.CLOSED,
                phase=None,
                is_closed=True,
                active_turn_id=self.turn_id,
                active_generation_id=self.generation_id,
                active_generation_count=1,
            )
        with self.assertRaisesRegex(ValueError, "must match RealtimeState.CLOSED"):
            build_session_diagnostics_snapshot(
                session_id=self.session_id,
                state=RealtimeState.CLOSED,
                phase=None,
                is_closed=False,
            )

    def test_counts_reject_boolean_negative_and_active_count_above_one(self) -> None:
        for field_name in (
            "queue_depth",
            "active_generation_count",
            "stale_completion_count",
            "duplicate_terminal_count",
            "overflow_count",
        ):
            with self.subTest(field_name=field_name, value=True):
                with self.assertRaises(TypeError):
                    build_session_diagnostics_snapshot(
                        session_id=self.session_id,
                        state=RealtimeState.IDLE,
                        phase=RealtimePhase.IDLE,
                        is_closed=False,
                        **{field_name: True},  # type: ignore[arg-type]
                    )
            with self.subTest(field_name=field_name, value=-1):
                with self.assertRaises(ValueError):
                    build_session_diagnostics_snapshot(
                        session_id=self.session_id,
                        state=RealtimeState.IDLE,
                        phase=RealtimePhase.IDLE,
                        is_closed=False,
                        **{field_name: -1},
                    )
        with self.assertRaisesRegex(ValueError, "0 or 1"):
            build_session_diagnostics_snapshot(
                session_id=self.session_id,
                state=RealtimeState.IDLE,
                phase=RealtimePhase.IDLE,
                is_closed=False,
                active_generation_count=2,
            )

    def test_last_terminal_and_safe_error_are_projected_and_consistent(self) -> None:
        snapshot = build_session_diagnostics_snapshot(
            session_id=self.session_id,
            state=RealtimeState.FAILED,
            phase=None,
            is_closed=False,
            last_terminal_result=self._failed_result(),
            stale_completion_count=3,
            duplicate_terminal_count=4,
            overflow_count=5,
        )
        self.assertIsInstance(snapshot.last_terminal_result, SessionTerminalSnapshot)
        self.assertIs(
            snapshot.last_safe_error_code,
            RealtimeErrorCode.PROVIDER_ERROR,
        )
        with self.assertRaisesRegex(ValueError, "must be derived"):
            SessionDiagnosticsSnapshot(
                session_id=self.session_id,
                state=RealtimeState.IDLE,
                phase=RealtimePhase.IDLE,
                is_closed=False,
                active_turn_id=None,
                active_generation_id=None,
                queue_depth=0,
                active_generation_count=0,
                last_terminal_result=None,
                last_safe_error_code=RealtimeErrorCode.PROVIDER_ERROR,
                stale_completion_count=0,
                duplicate_terminal_count=0,
                overflow_count=0,
            )

    def test_snapshot_is_frozen_slotted_and_as_dict_is_primitive_only(self) -> None:
        snapshot = build_session_diagnostics_snapshot(
            session_id=self.session_id,
            state=RealtimeState.FAILED,
            phase=None,
            is_closed=False,
            last_terminal_result=self._failed_result(),
        )
        with self.assertRaises(FrozenInstanceError):
            snapshot.queue_depth = 9  # type: ignore[misc]
        self.assertFalse(hasattr(snapshot, "__dict__"))
        encoded = json.dumps(snapshot.as_dict(), sort_keys=True)
        self.assertIn('"last_safe_error_code": "provider_error"', encoded)
        self.assertNotIn("private-safe-message-sentinel", encoded)

    def test_control_a_remains_provider_free_after_runtime_adoption(self) -> None:
        self.assertNotIn("SessionDiagnosticsSnapshot", framework.__all__)
        for module_name in (
            "pyvts",
            "websockets",
            "pyaudio",
            "sounddevice",
            "openai",
        ):
            self.assertNotIn(module_name, sys.modules)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
