"""Provider-free unit tests for atomic first-terminal ownership."""

from __future__ import annotations

import unittest

from framework.lifecycle import (
    LifecycleTransitionErrorCode,
    RecoveryAction,
    TurnOutcome,
)
from framework.realtime_terminal_registry import (
    RealtimeTerminalRegistry,
    TerminalCommitStatus,
)


class RealtimeTerminalRegistryTests(unittest.TestCase):
    def test_first_terminal_retains_record_and_diagnostics(self) -> None:
        registry: RealtimeTerminalRegistry[dict[str, str]] = (
            RealtimeTerminalRegistry()
        )

        decision = registry.commit(
            "turn-a",
            "completed",
            recovery_action="reuse_session",
            reason="done",
            result={"text": "ok"},
        )

        self.assertTrue(decision.accepted)
        self.assertIs(
            decision.status,
            TerminalCommitStatus.FIRST_TERMINAL,
        )
        self.assertIs(decision.record.outcome, TurnOutcome.COMPLETED)
        self.assertIs(
            decision.record.recovery_action,
            RecoveryAction.REUSE_SESSION,
        )
        self.assertEqual(decision.record.reason, "done")
        self.assertEqual(decision.record.result, {"text": "ok"})
        self.assertIs(registry.get("turn-a"), decision.record)
        self.assertEqual(registry.records, (decision.record,))
        self.assertEqual(len(registry), 1)

        diagnostics = registry.diagnostics
        self.assertEqual(diagnostics.terminal_commit_count, 1)
        self.assertEqual(diagnostics.registry_size, 1)
        self.assertEqual(diagnostics.duplicate_terminal_count, 0)
        self.assertEqual(diagnostics.terminal_regression_count, 0)

    def test_duplicate_terminal_is_suppressed_and_original_retained(self) -> None:
        registry: RealtimeTerminalRegistry[int] = RealtimeTerminalRegistry()
        first = registry.commit(
            "turn-a",
            TurnOutcome.CANCELLED,
            reason="first",
            result=1,
        )

        duplicate = registry.commit(
            "turn-a",
            TurnOutcome.CANCELLED,
            reason="second",
            result=2,
        )

        self.assertFalse(duplicate.accepted)
        self.assertIs(
            duplicate.status,
            TerminalCommitStatus.DUPLICATE_TERMINAL,
        )
        self.assertIs(
            duplicate.error_code,
            LifecycleTransitionErrorCode.DUPLICATE_TERMINAL,
        )
        self.assertIs(duplicate.record, first.record)
        self.assertEqual(duplicate.record.reason, "first")
        self.assertEqual(duplicate.record.result, 1)
        self.assertEqual(registry.diagnostics.duplicate_terminal_count, 1)

    def test_terminal_regression_is_suppressed(self) -> None:
        registry: RealtimeTerminalRegistry[str] = RealtimeTerminalRegistry()
        first = registry.commit("turn-a", "completed", result="complete")

        regression = registry.commit(
            "turn-a",
            "failed",
            result="replacement",
        )

        self.assertFalse(regression.accepted)
        self.assertIs(
            regression.status,
            TerminalCommitStatus.TERMINAL_REGRESSION,
        )
        self.assertIs(
            regression.error_code,
            LifecycleTransitionErrorCode.TERMINAL_REGRESSION,
        )
        self.assertIs(regression.record, first.record)
        self.assertEqual(regression.record.result, "complete")
        self.assertEqual(
            registry.diagnostics.terminal_regression_count,
            1,
        )

    def test_late_non_terminal_attempts_are_rejected_and_counted(self) -> None:
        registry: RealtimeTerminalRegistry[None] = RealtimeTerminalRegistry()

        self.assertTrue(registry.admit_non_terminal("turn-a"))
        registry.commit("turn-a", "interrupted")
        self.assertFalse(registry.admit_non_terminal("turn-a"))
        self.assertFalse(registry.admit_non_terminal("turn-a"))

        diagnostics = registry.diagnostics
        self.assertEqual(diagnostics.late_non_terminal_count, 2)
        self.assertTrue(registry.is_terminal("turn-a"))

    def test_records_preserve_commit_order_across_turns(self) -> None:
        registry: RealtimeTerminalRegistry[None] = RealtimeTerminalRegistry()

        registry.commit("turn-b", "rejected")
        registry.commit("turn-a", "closed")

        self.assertEqual(
            tuple(record.turn_id for record in registry.records),
            ("turn-b", "turn-a"),
        )
        self.assertEqual(
            tuple(record.outcome for record in registry.records),
            (TurnOutcome.REJECTED, TurnOutcome.CLOSED),
        )
        self.assertEqual(registry.diagnostics.registry_size, 2)


if __name__ == "__main__":
    unittest.main()
