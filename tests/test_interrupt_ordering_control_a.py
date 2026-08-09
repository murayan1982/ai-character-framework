"""Provider-free tests for FW-RT6-9b Control A interrupt ordering."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import unittest

import framework
from framework.identity import SessionId, TurnId
from framework.interrupt_ordering import (
    DEFAULT_INTERRUPT_ORDERING_POLICY,
    InterruptAdmissionOutcome,
    InterruptOrderingDecision,
    InterruptOrderingKey,
    InterruptOrderingPolicy,
    InterruptOrderingRule,
)
from framework.output_control import InterruptRequest, InterruptResult


def _key() -> InterruptOrderingKey:
    return InterruptOrderingKey(
        session_id=SessionId.new(),
        resolved_turn_id=TurnId.new(),
    )


class InterruptOrderingControlATests(unittest.TestCase):
    def test_explicit_package_exports_and_vocabularies_are_exact(self) -> None:
        import framework.interrupt_ordering as ordering

        self.assertEqual(
            tuple(ordering.__all__),
            (
                "DEFAULT_INTERRUPT_ORDERING_POLICY",
                "InterruptAdmissionOutcome",
                "InterruptOrderingDecision",
                "InterruptOrderingKey",
                "InterruptOrderingPolicy",
                "InterruptOrderingRule",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in InterruptOrderingRule),
            (
                "RESOLVED_TURN_IDENTITY",
                "REPLAY_OWNER_TERMINAL_RESULT",
                "FIRST_TERMINAL_RESERVATION_WINS",
                "FIRST_ADMISSION_WINS",
                "OWNER_FLUSH_BEFORE_TERMINAL",
                "TYPED_REJECT_NEW_TURN",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in InterruptAdmissionOutcome),
            (
                "OWNER",
                "DUPLICATE_REPLAY",
                "EXISTING_TERMINAL",
                "ALREADY_CLOSED",
                "NEW_TURN_REJECTED",
            ),
        )

    def test_policy_deliberately_reuses_turn_identity(self) -> None:
        policy = DEFAULT_INTERRUPT_ORDERING_POLICY
        self.assertFalse(policy.request_id_required)
        self.assertEqual(
            policy.idempotency_key_fields,
            ("session_id", "resolved_turn_id"),
        )
        self.assertIs(
            policy.request_identity,
            InterruptOrderingRule.RESOLVED_TURN_IDENTITY,
        )
        self.assertNotIn("request_id", tuple(item.name for item in fields(InterruptRequest)))

    def test_policy_fixes_all_five_race_and_duplicate_rules(self) -> None:
        policy = InterruptOrderingPolicy()
        self.assertIs(
            policy.duplicate_interrupt,
            InterruptOrderingRule.REPLAY_OWNER_TERMINAL_RESULT,
        )
        self.assertIs(
            policy.normal_completion_race,
            InterruptOrderingRule.FIRST_TERMINAL_RESERVATION_WINS,
        )
        self.assertIs(policy.close_race, InterruptOrderingRule.FIRST_ADMISSION_WINS)
        self.assertIs(
            policy.flush_race,
            InterruptOrderingRule.OWNER_FLUSH_BEFORE_TERMINAL,
        )
        self.assertIs(
            policy.new_turn_during_interrupt,
            InterruptOrderingRule.TYPED_REJECT_NEW_TURN,
        )

    def test_policy_rejects_reinterpretation(self) -> None:
        with self.assertRaisesRegex(ValueError, "close_race must use"):
            InterruptOrderingPolicy(close_race="first_terminal_reservation_wins")
        with self.assertRaises(ValueError):
            InterruptOrderingPolicy(flush_race="host_decides")
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_INTERRUPT_ORDERING_POLICY.close_race = (  # type: ignore[misc]
                InterruptOrderingRule.FIRST_ADMISSION_WINS
            )

    def test_key_requires_session_and_resolved_turn(self) -> None:
        key = _key()
        self.assertIsInstance(key.session_id, SessionId)
        self.assertIsInstance(key.resolved_turn_id, TurnId)
        with self.assertRaisesRegex(ValueError, "session_id"):
            InterruptOrderingKey(  # type: ignore[arg-type]
                session_id=None,
                resolved_turn_id=TurnId.new(),
            )
        with self.assertRaisesRegex(ValueError, "resolved_turn_id"):
            InterruptOrderingKey(  # type: ignore[arg-type]
                session_id=SessionId.new(),
                resolved_turn_id=None,
            )

    def test_key_preserves_legacy_host_identifiers(self) -> None:
        key = InterruptOrderingKey(
            session_id="legacy-session",
            resolved_turn_id="legacy-turn",
        )
        self.assertEqual(key.session_id, "legacy-session")
        self.assertEqual(key.resolved_turn_id, "legacy-turn")
        with self.assertRaisesRegex(ValueError, "invalid Framework identity"):
            InterruptOrderingKey(
                session_id="fw_turn_" + "0" * 32,
                resolved_turn_id="legacy-turn",
            )

    def test_owner_is_only_decision_that_executes_and_reserves(self) -> None:
        decision = InterruptOrderingDecision.owner(_key())
        self.assertIs(decision.outcome, InterruptAdmissionOutcome.OWNER)
        self.assertTrue(decision.execute_interrupt)
        self.assertTrue(decision.terminal_reserved)
        self.assertFalse(decision.reuse_owner_terminal_result)
        self.assertFalse(decision.side_effect_free)

    def test_duplicate_replays_without_repeat_side_effects(self) -> None:
        decision = InterruptOrderingDecision.duplicate_replay(_key())
        self.assertIs(
            decision.outcome,
            InterruptAdmissionOutcome.DUPLICATE_REPLAY,
        )
        self.assertTrue(decision.reuse_owner_terminal_result)
        self.assertFalse(decision.execute_interrupt)
        self.assertFalse(decision.terminal_reserved)
        self.assertTrue(decision.side_effect_free)

    def test_existing_terminal_and_closed_decisions_claim_no_effect(self) -> None:
        terminal = InterruptOrderingDecision.existing_terminal(_key())
        closed = InterruptOrderingDecision.already_closed()
        self.assertIs(terminal.outcome, InterruptAdmissionOutcome.EXISTING_TERMINAL)
        self.assertIs(closed.outcome, InterruptAdmissionOutcome.ALREADY_CLOSED)
        self.assertIsNone(closed.key)
        self.assertTrue(terminal.side_effect_free)
        self.assertTrue(closed.side_effect_free)

    def test_new_turn_during_interrupt_is_typed_reject(self) -> None:
        decision = InterruptOrderingDecision.new_turn_rejected(_key())
        self.assertIs(
            decision.outcome,
            InterruptAdmissionOutcome.NEW_TURN_REJECTED,
        )
        self.assertTrue(decision.typed_reject)
        self.assertFalse(decision.execute_interrupt)
        self.assertTrue(decision.side_effect_free)

    def test_decision_rejects_inconsistent_flags_and_keys(self) -> None:
        key = _key()
        with self.assertRaisesRegex(ValueError, "exact ordering decision flags"):
            InterruptOrderingDecision(
                outcome=InterruptAdmissionOutcome.DUPLICATE_REPLAY,
                key=key,
                execute_interrupt=True,
            )
        with self.assertRaisesRegex(ValueError, "requires one resolved turn key"):
            InterruptOrderingDecision(
                outcome=InterruptAdmissionOutcome.EXISTING_TERMINAL,
            )
        with self.assertRaisesRegex(ValueError, "must not invent a turn key"):
            InterruptOrderingDecision(
                outcome=InterruptAdmissionOutcome.ALREADY_CLOSED,
                key=key,
            )
        with self.assertRaisesRegex(TypeError, "must be a boolean"):
            InterruptOrderingDecision(  # type: ignore[arg-type]
                outcome=InterruptAdmissionOutcome.OWNER,
                key=key,
                execute_interrupt=1,
                terminal_reserved=True,
            )

    def test_root_public_request_result_and_versions_remain_unchanged(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("InterruptOrderingPolicy", framework.__all__)
        self.assertEqual(
            tuple(item.name for item in fields(InterruptRequest)),
            (
                "scope",
                "reason",
                "turn_id",
                "flush_output",
                "cancel_tts_queue",
                "cancel_llm_stream",
                "stop_motion",
                "public_metadata",
                "timeout_seconds",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in fields(InterruptResult)),
            (
                "outcome",
                "scope",
                "reason",
                "turn_id",
                "safe_message",
                "retryable",
                "provider_cancel_supported",
                "queue_flush_supported",
                "public_metadata",
                "motion_result",
            ),
        )
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
