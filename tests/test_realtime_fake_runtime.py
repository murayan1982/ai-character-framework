"""Provider-free unit tests for deterministic fake runtime race controls."""

from __future__ import annotations

import unittest

from framework.lifecycle import TurnOutcome
from framework.realtime_fake_runtime import (
    DeterministicFakeClock,
    DeterministicFakeRuntimeController,
    DeterministicRealtimeRaceHarness,
    FakeRuntimeClosedError,
    FakeRuntimeQueueOverflow,
    FakeRuntimeTraceKind,
    assert_deterministic_trace,
)
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    StaleCompletionReason,
)
from framework.realtime_stage import RealtimeStageKind
from framework.realtime_terminal_registry import TerminalCommitStatus


class DeterministicFakeRuntimeTests(unittest.TestCase):
    def test_integer_clock_never_moves_backwards(self) -> None:
        clock = DeterministicFakeClock(initial_tick=5)

        self.assertEqual(clock.advance_by(2), 7)
        self.assertEqual(clock.advance_to(10), 10)
        with self.assertRaises(ValueError):
            clock.advance_to(9)

    def test_same_tick_actions_run_in_insertion_order(self) -> None:
        controller = DeterministicFakeRuntimeController()
        seen: list[tuple[str, int]] = []

        first = controller.schedule_stage_action(
            RealtimeStageKind.VOICE_INPUT,
            lambda action: seen.append(
                (action.action_id, controller.clock.now_tick)
            ),
            delay_ticks=3,
            correlation_key="first",
        )
        second = controller.schedule_stage_action(
            RealtimeStageKind.VOICE_INPUT,
            lambda action: seen.append(
                (action.action_id, controller.clock.now_tick)
            ),
            delay_ticks=3,
            correlation_key="second",
        )

        executed = controller.run_until_idle()

        self.assertEqual(executed, (first, second))
        self.assertEqual(
            seen,
            [(first.action_id, 3), (second.action_id, 3)],
        )
        self.assertEqual(controller.pending_count, 0)

    def test_paused_stage_waits_while_other_stage_runs(self) -> None:
        controller = DeterministicFakeRuntimeController()
        seen: list[str] = []
        controller.pause_stage(RealtimeStageKind.VOICE_INPUT)
        controller.schedule_stage_action(
            RealtimeStageKind.VOICE_INPUT,
            lambda action: seen.append("voice"),
            correlation_key="voice",
        )
        controller.schedule_stage_action(
            RealtimeStageKind.TEXT_GENERATION,
            lambda action: seen.append("text"),
            correlation_key="text",
        )

        first_batch = controller.run_due()

        self.assertEqual(len(first_batch), 1)
        self.assertEqual(seen, ["text"])
        self.assertEqual(controller.pending_count, 1)
        self.assertTrue(
            controller.resume_stage(RealtimeStageKind.VOICE_INPUT)
        )

        second_batch = controller.run_due()
        self.assertEqual(len(second_batch), 1)
        self.assertEqual(seen, ["text", "voice"])

    def test_cancellation_timeout_runs_at_exact_fake_tick(self) -> None:
        controller = DeterministicFakeRuntimeController(initial_tick=2)
        observed: list[int] = []
        controller.inject_cancellation_timeout(
            RealtimeStageKind.VOICE_OUTPUT,
            lambda action: observed.append(controller.clock.now_tick),
            timeout_ticks=4,
            correlation_key="cancel",
        )

        self.assertEqual(controller.advance_by(3), ())
        executed = controller.advance_by(1)

        self.assertEqual(len(executed), 1)
        self.assertEqual(observed, [6])
        self.assertIn(
            FakeRuntimeTraceKind.CANCELLATION_TIMEOUT_INJECTED,
            tuple(event.kind for event in controller.trace),
        )

    def test_queue_overflow_and_close_are_explicit(self) -> None:
        controller = DeterministicFakeRuntimeController(max_queue_size=1)
        controller.schedule_stage_action(
            RealtimeStageKind.MOTION,
            lambda action: None,
            correlation_key="first",
        )

        with self.assertRaises(FakeRuntimeQueueOverflow):
            controller.schedule_stage_action(
                RealtimeStageKind.MOTION,
                lambda action: None,
                correlation_key="overflow",
            )

        self.assertIs(
            controller.trace[-1].kind,
            FakeRuntimeTraceKind.QUEUE_OVERFLOW_INJECTED,
        )
        controller.close()
        self.assertTrue(controller.closed)
        self.assertEqual(controller.pending_count, 0)

        with self.assertRaises(FakeRuntimeClosedError):
            controller.schedule_stage_action(
                RealtimeStageKind.MOTION,
                lambda action: None,
                correlation_key="closed",
            )

    def test_trace_signature_is_exact_and_metadata_free(self) -> None:
        controller = DeterministicFakeRuntimeController()
        controller.schedule_stage_action(
            RealtimeStageKind.VOICE_INPUT,
            lambda action: None,
            delay_ticks=2,
            correlation_key="trace",
            public_metadata={"private_like": "not-in-signature"},
        )
        controller.run_next()

        expected = (
            "0|0|action_scheduled|fake-action-000000|stage_action|voice_input|trace",
            "1|2|clock_advanced|-|-|-|-",
            "2|2|action_executed|fake-action-000000|stage_action|voice_input|trace",
        )
        controller.assert_trace(expected)
        self.assertEqual(controller.trace_signature(), expected)
        with self.assertRaises(AssertionError):
            assert_deterministic_trace(controller.trace, expected[:-1])

    def test_race_harness_classifies_retired_completion(self) -> None:
        harness: DeterministicRealtimeRaceHarness[str, None] = (
            DeterministicRealtimeRaceHarness()
        )
        generation_id = harness.start_generation("turn-a")
        harness.inject_late_generation_completion(
            RealtimeStageKind.TEXT_GENERATION,
            turn_id="turn-a",
            generation_id=generation_id,
            value="late",
            correlation_key="late",
            delay_ticks=2,
        )
        harness.advance_generation(GenerationAdvanceReason.INTERRUPT)

        harness.run_until_idle()

        self.assertEqual(len(harness.generation_admissions), 1)
        admission = harness.generation_admissions[0]
        self.assertFalse(admission.accepted)
        self.assertIs(
            admission.stale_reason,
            StaleCompletionReason.RETIRED_GENERATION,
        )
        self.assertIs(
            admission.retired_by,
            GenerationAdvanceReason.INTERRUPT,
        )
        self.assertEqual(
            harness.generation_diagnostics["stale_completion_count"],
            1,
        )

    def test_race_harness_classifies_duplicate_terminal(self) -> None:
        harness: DeterministicRealtimeRaceHarness[None, str] = (
            DeterministicRealtimeRaceHarness()
        )
        harness.inject_duplicate_terminal(
            RealtimeStageKind.VOICE_OUTPUT,
            turn_id="turn-a",
            outcome=TurnOutcome.COMPLETED,
            correlation_key="terminal",
            result="first-result",
            copies=3,
            interval_ticks=1,
        )

        harness.run_until_idle()

        self.assertEqual(
            tuple(record.status for record in harness.terminal_commits),
            (
                TerminalCommitStatus.FIRST_TERMINAL,
                TerminalCommitStatus.DUPLICATE_TERMINAL,
                TerminalCommitStatus.DUPLICATE_TERMINAL,
            ),
        )
        self.assertEqual(len(harness.terminal_records), 1)
        self.assertEqual(
            harness.terminal_records[0].result,
            "first-result",
        )
        diagnostics = harness.terminal_diagnostics
        self.assertEqual(diagnostics.terminal_commit_count, 1)
        self.assertEqual(diagnostics.duplicate_terminal_count, 2)


if __name__ == "__main__":
    unittest.main()
