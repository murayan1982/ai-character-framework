"""Provider-free tests for FW-RT6-10b Control A close planning."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import math
import sys
import unittest

import framework
from framework.session_close import (
    SessionCleanupOutcome,
    SessionCleanupResult,
    SessionCleanupTarget,
    SessionCloseOutcome,
    SessionClosePlan,
    SessionCloseResult,
    build_session_close_plan,
)


def _results_for_plan(
    plan: SessionClosePlan,
    *,
    override: dict[SessionCleanupTarget, SessionCleanupResult] | None = None,
) -> tuple[SessionCleanupResult, ...]:
    overrides = override or {}
    required = set(plan.required_targets)
    return tuple(
        overrides.get(
            target,
            (
                SessionCleanupResult.completed(target)
                if target in required
                else SessionCleanupResult.not_required(target)
            ),
        )
        for target in SessionCleanupTarget
    )


class SessionCloseControlATests(unittest.TestCase):
    def test_explicit_package_exports_are_exact_and_root_surface_is_unchanged(self) -> None:
        import framework.session_close as session_close

        self.assertEqual(
            tuple(session_close.__all__),
            (
                "SessionCleanupTarget",
                "SessionCleanupOutcome",
                "SessionCloseOutcome",
                "SessionClosePlan",
                "SessionCleanupResult",
                "SessionCloseResult",
                "build_session_close_plan",
            ),
        )
        self.assertNotIn("SessionClosePlan", framework.__all__)
        self.assertFalse(hasattr(framework, "SessionClosePlan"))
        self.assertEqual(len(framework.__all__), 127)

    def test_plan_records_exact_required_targets_in_close_order(self) -> None:
        plan = build_session_close_plan(
            active_turn_terminal_required=True,
            stage_cleanup_required=True,
            provider_client_cleanup_required=True,
            callback_hub_close_required=True,
            execution_bridge_shutdown_required=True,
        )

        self.assertEqual(
            plan.required_targets,
            (
                SessionCleanupTarget.ACTIVE_TURN,
                SessionCleanupTarget.STAGE,
                SessionCleanupTarget.PROVIDER_CLIENT,
                SessionCleanupTarget.CALLBACK_HUB,
                SessionCleanupTarget.EXECUTION_BRIDGE,
            ),
        )
        self.assertFalse(plan.decision_is_execution)
        self.assertTrue(plan.side_effect_free)

    def test_plan_timeouts_are_finite_positive_and_boolean_fields_are_exact(self) -> None:
        plan = build_session_close_plan(
            stage_cleanup_timeout_seconds=0.5,
            provider_cleanup_timeout_seconds=1,
            bridge_shutdown_timeout_seconds=3.5,
        )
        self.assertEqual(plan.stage_cleanup_timeout_seconds, 0.5)
        self.assertEqual(plan.provider_cleanup_timeout_seconds, 1.0)
        self.assertEqual(plan.bridge_shutdown_timeout_seconds, 3.5)

        for bad in (0, -1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                build_session_close_plan(stage_cleanup_timeout_seconds=bad)
        with self.assertRaises(TypeError):
            build_session_close_plan(stage_cleanup_timeout_seconds=True)
        with self.assertRaises(TypeError):
            build_session_close_plan(stage_cleanup_required=1)  # type: ignore[arg-type]

    def test_plan_is_immutable_and_public_metadata_is_redacted(self) -> None:
        plan = build_session_close_plan(
            callback_hub_close_required=True,
            public_metadata={
                "boundary": "session_close",
                "secret": "must-not-leak",
                "private_path": "C:/private/file",
            },
        )

        self.assertEqual(plan.public_metadata["secret"], "<redacted>")
        self.assertEqual(plan.public_metadata["private_path"], "<redacted:path>")
        self.assertNotIn("must-not-leak", repr(plan))
        self.assertNotIn("C:/private/file", repr(plan))
        with self.assertRaises(FrozenInstanceError):
            plan.callback_hub_close_required = False  # type: ignore[misc]

    def test_cleanup_result_is_typed_and_failure_needs_safe_message(self) -> None:
        complete = SessionCleanupResult.completed(SessionCleanupTarget.STAGE)
        already = SessionCleanupResult.already_closed(
            SessionCleanupTarget.PROVIDER_CLIENT
        )
        timeout = SessionCleanupResult.timed_out_result(
            SessionCleanupTarget.EXECUTION_BRIDGE
        )
        failed = SessionCleanupResult.failed_result(
            SessionCleanupTarget.CALLBACK_HUB
        )

        self.assertTrue(complete.successful)
        self.assertTrue(already.successful)
        self.assertTrue(timeout.timed_out)
        self.assertTrue(failed.failed)
        with self.assertRaisesRegex(ValueError, "safe message"):
            SessionCleanupResult(
                target=SessionCleanupTarget.STAGE,
                outcome=SessionCleanupOutcome.TIMED_OUT,
            )

    def test_successful_first_close_terminalizes_active_turn_and_records_all_targets(self) -> None:
        plan = build_session_close_plan(
            active_turn_terminal_required=True,
            stage_cleanup_required=True,
            callback_hub_close_required=True,
            execution_bridge_shutdown_required=True,
        )
        result = SessionCloseResult.from_cleanup(
            plan,
            cleanup_results=_results_for_plan(plan),
            active_turn_terminalized=True,
        )

        self.assertIs(result.outcome, SessionCloseOutcome.CLOSED)
        self.assertTrue(result.session_closed)
        self.assertTrue(result.active_turn_terminalized)
        self.assertEqual(result.diagnostics["cleanup_required_count"], 4)
        self.assertEqual(result.diagnostics["cleanup_completed_count"], 4)
        self.assertEqual(result.diagnostics["cleanup_timeout_count"], 0)
        self.assertEqual(result.diagnostics["cleanup_failure_count"], 0)

    def test_cleanup_timeout_is_truthful_and_does_not_reopen_session(self) -> None:
        plan = build_session_close_plan(
            stage_cleanup_required=True,
            execution_bridge_shutdown_required=True,
        )
        results = _results_for_plan(
            plan,
            override={
                SessionCleanupTarget.STAGE:
                    SessionCleanupResult.timed_out_result(
                        SessionCleanupTarget.STAGE,
                        safe_message="Realtime stage cleanup timed out.",
                    ),
            },
        )
        result = SessionCloseResult.from_cleanup(
            plan,
            cleanup_results=results,
            active_turn_terminalized=False,
        )

        self.assertIs(
            result.outcome,
            SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES,
        )
        self.assertTrue(result.session_closed)
        self.assertEqual(result.diagnostics["cleanup_timeout_count"], 1)
        self.assertEqual(result.diagnostics["cleanup_failure_count"], 0)

    def test_active_turn_terminal_fact_cannot_be_claimed_or_omitted(self) -> None:
        active_plan = build_session_close_plan(
            active_turn_terminal_required=True,
        )
        with self.assertRaisesRegex(ValueError, "active-turn terminal fact"):
            SessionCloseResult.from_cleanup(
                active_plan,
                cleanup_results=_results_for_plan(active_plan),
                active_turn_terminalized=False,
            )

        idle_plan = build_session_close_plan()
        with self.assertRaisesRegex(ValueError, "active-turn terminal fact"):
            SessionCloseResult.from_cleanup(
                idle_plan,
                cleanup_results=_results_for_plan(idle_plan),
                active_turn_terminalized=True,
            )

        failed_active = _results_for_plan(
            active_plan,
            override={
                SessionCleanupTarget.ACTIVE_TURN:
                    SessionCleanupResult.failed_result(
                        SessionCleanupTarget.ACTIVE_TURN,
                        safe_message="Active turn could not be terminalized.",
                    ),
            },
        )
        with self.assertRaisesRegex(ValueError, "must reach its closed terminal"):
            SessionCloseResult.from_cleanup(
                active_plan,
                cleanup_results=failed_active,
                active_turn_terminalized=False,
            )

    def test_required_and_nonrequired_targets_cannot_misreport_execution(self) -> None:
        required = build_session_close_plan(stage_cleanup_required=True)
        missing = _results_for_plan(
            required,
            override={
                SessionCleanupTarget.STAGE:
                    SessionCleanupResult.not_required(SessionCleanupTarget.STAGE),
            },
        )
        with self.assertRaisesRegex(ValueError, "required cleanup target"):
            SessionCloseResult.from_cleanup(
                required,
                cleanup_results=missing,
                active_turn_terminalized=False,
            )

        idle = build_session_close_plan()
        false_claim = _results_for_plan(
            idle,
            override={
                SessionCleanupTarget.PROVIDER_CLIENT:
                    SessionCleanupResult.completed(
                        SessionCleanupTarget.PROVIDER_CLIENT
                    ),
            },
        )
        with self.assertRaisesRegex(ValueError, "non-required cleanup target"):
            SessionCloseResult.from_cleanup(
                idle,
                cleanup_results=false_claim,
                active_turn_terminalized=False,
            )

    def test_cleanup_results_require_each_target_exactly_once(self) -> None:
        plan = build_session_close_plan()
        incomplete = (
            SessionCleanupResult.not_required(SessionCleanupTarget.ACTIVE_TURN),
        )
        with self.assertRaisesRegex(ValueError, "every canonical target"):
            SessionCloseResult.from_cleanup(
                plan,
                cleanup_results=incomplete,
                active_turn_terminalized=False,
            )

        duplicated = tuple(_results_for_plan(plan)) + (
            SessionCleanupResult.not_required(SessionCleanupTarget.ACTIVE_TURN),
        )
        with self.assertRaisesRegex(ValueError, "at most once"):
            SessionCloseResult.from_cleanup(
                plan,
                cleanup_results=duplicated,
                active_turn_terminalized=False,
            )

    def test_repeated_close_is_side_effect_free_and_attempts_no_cleanup(self) -> None:
        result = SessionCloseResult.already_closed(
            public_metadata={"boundary": "session_close"}
        )

        self.assertIs(result.outcome, SessionCloseOutcome.ALREADY_CLOSED)
        self.assertTrue(result.session_closed)
        self.assertFalse(result.active_turn_terminalized)
        self.assertEqual(result.plan.required_targets, ())
        self.assertEqual(result.diagnostics["cleanup_attempted_count"], 0)
        self.assertEqual(result.diagnostics["cleanup_completed_count"], 0)

    def test_control_a_is_provider_free_and_runtime_adoption_remains_deferred(self) -> None:
        self.assertFalse(hasattr(framework.RealtimeSession, "close_result"))
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
            self.assertNotIn(module_name, sys.modules)


if __name__ == "__main__":
    unittest.main()
