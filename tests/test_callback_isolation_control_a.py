"""Provider-free tests for FW-RT6-10d Control A isolation contracts."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, fields
import json
from pathlib import Path
import sys
import unittest

import framework
from framework.callback_isolation import (
    CallbackBoundary,
    CallbackDispatchResult,
    CallbackFailureAction,
    CallbackIsolationPolicy,
    StageCriticality,
    StageFailureAction,
    StageFailurePolicy,
    callback_isolation_policy,
    criticality_for_stage,
    dispatch_isolated_callbacks,
    dispatch_isolated_callbacks_async,
    stage_failure_policy,
)
from framework.realtime_stage import RealtimeStageKind


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CallbackIsolationControlATests(unittest.TestCase):
    def test_explicit_exports_are_exact_and_root_surface_is_unchanged(self) -> None:
        import framework.callback_isolation as isolation

        self.assertEqual(
            tuple(isolation.__all__),
            (
                "CallbackBoundary",
                "CallbackFailureAction",
                "CallbackIsolationPolicy",
                "CallbackDispatchResult",
                "StageCriticality",
                "StageFailureAction",
                "StageFailurePolicy",
                "callback_isolation_policy",
                "criticality_for_stage",
                "stage_failure_policy",
                "dispatch_isolated_callbacks",
                "dispatch_isolated_callbacks_async",
            ),
        )
        self.assertNotIn("CallbackIsolationPolicy", framework.__all__)
        self.assertFalse(hasattr(framework, "CallbackIsolationPolicy"))
        self.assertEqual(len(framework.__all__), 127)

    def test_callback_and_failure_action_vocabularies_are_exact(self) -> None:
        self.assertEqual(
            tuple(value.value for value in CallbackBoundary),
            ("public_callback", "plugin_hook", "motion_hook"),
        )
        self.assertEqual(
            tuple(value.value for value in CallbackFailureAction),
            ("continue_dispatch", "skip_motion"),
        )

    def test_public_and_plugin_policies_continue_without_runtime_failure(self) -> None:
        for boundary in (
            CallbackBoundary.PUBLIC_CALLBACK,
            CallbackBoundary.PLUGIN_HOOK,
        ):
            with self.subTest(boundary=boundary):
                policy = callback_isolation_policy(boundary)
                self.assertIs(
                    policy.failure_action,
                    CallbackFailureAction.CONTINUE_DISPATCH,
                )
                self.assertTrue(policy.continue_remaining_handlers)
                self.assertFalse(policy.runtime_failure_on_exception)
                self.assertTrue(policy.invoke_without_session_lock)
                self.assertTrue(policy.reentrant_safe)

    def test_motion_hook_policy_skips_motion_and_preserves_runtime(self) -> None:
        policy = callback_isolation_policy(CallbackBoundary.MOTION_HOOK)

        self.assertIs(policy.failure_action, CallbackFailureAction.SKIP_MOTION)
        self.assertFalse(policy.continue_remaining_handlers)
        self.assertFalse(policy.runtime_failure_on_exception)
        self.assertTrue(policy.invoke_without_session_lock)
        self.assertTrue(policy.reentrant_safe)

    def test_policy_models_reject_contradictory_or_mutable_state(self) -> None:
        policy = callback_isolation_policy(CallbackBoundary.PUBLIC_CALLBACK)
        with self.assertRaises(FrozenInstanceError):
            policy.reentrant_safe = False  # type: ignore[misc]
        with self.assertRaisesRegex(ValueError, "cannot fail the runtime"):
            CallbackIsolationPolicy(
                boundary=CallbackBoundary.PUBLIC_CALLBACK,
                failure_action=CallbackFailureAction.CONTINUE_DISPATCH,
                continue_remaining_handlers=True,
                runtime_failure_on_exception=True,
                invoke_without_session_lock=True,
                reentrant_safe=True,
            )

    def test_sync_dispatch_isolates_failure_and_continues_in_order(self) -> None:
        observed: list[str] = []

        def failing(value: str) -> None:
            observed.append(f"failed:{value}")
            raise RuntimeError("private-callback-exception-sentinel")

        result = dispatch_isolated_callbacks(
            (
                lambda value: observed.append(f"first:{value}"),
                failing,
                lambda value: observed.append(f"last:{value}"),
            ),
            "payload",
        )

        self.assertEqual(
            observed,
            ["first:payload", "failed:payload", "last:payload"],
        )
        self.assertEqual(
            (result.attempted_count, result.completed_count, result.failed_count),
            (3, 2, 1),
        )
        self.assertFalse(result.runtime_failed)
        self.assertNotIn("private-callback", repr(result))
        self.assertNotIn("private-callback", json.dumps(result.as_dict()))

    def test_sync_dispatch_snapshots_registry_and_is_reentrant(self) -> None:
        callbacks: list[object] = []
        observed: list[str] = []

        def second(label: str) -> None:
            observed.append(f"second:{label}")

        def first(label: str) -> None:
            observed.append(f"first:{label}")
            if label == "outer":
                callbacks.remove(second)
                nested = dispatch_isolated_callbacks(callbacks, "inner")
                self.assertTrue(nested.all_completed)

        callbacks.extend((first, second))
        result = dispatch_isolated_callbacks(callbacks, "outer")

        self.assertEqual(
            observed,
            ["first:outer", "first:inner", "second:outer"],
        )
        self.assertEqual(result.completed_count, 2)
        self.assertEqual(result.failed_count, 0)

    def test_async_plugin_dispatch_awaits_and_isolates_each_handler(self) -> None:
        observed: list[str] = []

        async def failing(value: str) -> None:
            observed.append(f"async-failed:{value}")
            await asyncio.sleep(0)
            raise RuntimeError("private-plugin-exception-sentinel")

        async def scenario() -> CallbackDispatchResult:
            return await dispatch_isolated_callbacks_async(
                (
                    lambda value: observed.append(f"sync:{value}"),
                    failing,
                    lambda value: observed.append(f"last:{value}"),
                ),
                "hook",
            )

        result = asyncio.run(scenario())
        self.assertEqual(
            observed,
            ["sync:hook", "async-failed:hook", "last:hook"],
        )
        self.assertIs(result.boundary, CallbackBoundary.PLUGIN_HOOK)
        self.assertEqual(result.as_dict()["failed_count"], 1)
        self.assertFalse(result.runtime_failed)
        self.assertNotIn("private-plugin", repr(result))

    def test_non_callable_and_wrong_dispatch_mode_fail_safely(self) -> None:
        async def callback() -> None:
            return None

        result = dispatch_isolated_callbacks((None, callback))  # type: ignore[arg-type]
        self.assertEqual(
            (result.attempted_count, result.completed_count, result.failed_count),
            (2, 0, 2),
        )
        with self.assertRaisesRegex(ValueError, "motion hooks"):
            dispatch_isolated_callbacks(
                (),
                boundary=CallbackBoundary.MOTION_HOOK,
            )

    def test_stage_criticality_and_failure_actions_are_exact(self) -> None:
        self.assertEqual(
            tuple(value.value for value in StageCriticality),
            ("critical", "non_critical"),
        )
        self.assertEqual(
            tuple(value.value for value in StageFailureAction),
            ("fail_current_operation", "continue_degraded"),
        )
        self.assertIs(
            criticality_for_stage(RealtimeStageKind.VOICE_INPUT),
            StageCriticality.CRITICAL,
        )
        self.assertIs(
            criticality_for_stage("text_generation"),
            StageCriticality.CRITICAL,
        )
        self.assertIs(
            criticality_for_stage(RealtimeStageKind.VOICE_OUTPUT),
            StageCriticality.NON_CRITICAL,
        )
        self.assertIs(
            criticality_for_stage("motion"),
            StageCriticality.NON_CRITICAL,
        )

    def test_stage_failure_policies_keep_session_runtime_and_terminal_truth(self) -> None:
        critical = stage_failure_policy(StageCriticality.CRITICAL)
        non_critical = stage_failure_policy(StageCriticality.NON_CRITICAL)

        self.assertIs(
            critical.failure_action,
            StageFailureAction.FAIL_CURRENT_OPERATION,
        )
        self.assertTrue(critical.current_operation_fails)
        self.assertIs(
            non_critical.failure_action,
            StageFailureAction.CONTINUE_DEGRADED,
        )
        self.assertFalse(non_critical.current_operation_fails)
        for policy in (critical, non_critical):
            self.assertTrue(policy.session_remains_open)
            self.assertTrue(policy.runtime_remains_available)
            self.assertFalse(policy.existing_terminal_replacement_allowed)
        with self.assertRaisesRegex(ValueError, "cannot kill"):
            StageFailurePolicy(
                criticality=StageCriticality.CRITICAL,
                failure_action=StageFailureAction.FAIL_CURRENT_OPERATION,
                current_operation_fails=True,
                session_remains_open=False,
                runtime_remains_available=True,
                existing_terminal_replacement_allowed=False,
            )

    def test_models_have_only_public_safe_fields(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(CallbackDispatchResult)),
            (
                "boundary",
                "attempted_count",
                "completed_count",
                "failed_count",
            ),
        )
        result = CallbackDispatchResult(
            boundary="public_callback",
            attempted_count=2,
            completed_count=1,
            failed_count=1,
        )
        rendered = json.dumps(result.as_dict(), sort_keys=True)
        for forbidden in (
            "exception",
            "callback_identity",
            "provider_payload",
            "transcript",
            "audio",
            "private_path",
            "thread",
            "client",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_control_a_remains_explicit_provider_free_and_task_open(self) -> None:
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split(
            "## FW-RT6-10d — Callback and plugin isolation",
            1,
        )[1].split("## FW-RT6-11a", 1)[0]
        self.assertEqual(section.count("- [ ]"), 6)
        self.assertEqual(section.count("- [x]"), 0)
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
