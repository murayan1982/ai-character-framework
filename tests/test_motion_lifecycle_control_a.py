from __future__ import annotations

import unittest

import framework
from framework.identity import EventSequence, GenerationId, SessionId, TurnId
from framework.lifecycle import TurnOutcome
from framework.motion import (
    MotionAdapterStatus,
    MotionErrorCode,
    MotionIntent,
    MotionOutcome,
    MotionRequest,
    MotionResult,
    MotionState,
)
from framework.motion_lifecycle import (
    MotionLifecycleHook,
    MotionLifecycleHookOutcome,
    MotionLifecycleHookResult,
    MotionLifecycleNotification,
    MotionLifecycleSignal,
    invoke_motion_lifecycle_hook,
)


class MotionLifecycleControlATests(unittest.TestCase):
    def _notification(
        self,
        signal: MotionLifecycleSignal = MotionLifecycleSignal.THINKING,
        *,
        outcome: TurnOutcome | None = None,
    ) -> MotionLifecycleNotification:
        return MotionLifecycleNotification(
            signal=signal,
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
            source_sequence=EventSequence.first(),
            outcome=outcome,
        )

    def test_signal_contract_contains_exact_six_values(self) -> None:
        self.assertEqual(
            tuple(signal.value for signal in MotionLifecycleSignal),
            (
                "listening",
                "thinking",
                "speaking",
                "interrupted",
                "completed",
                "failed",
            ),
        )

    def test_notification_normalizes_identity_sequence_and_metadata(self) -> None:
        session_id = SessionId.new()
        turn_id = TurnId.new()
        generation_id = GenerationId.new()
        notification = MotionLifecycleNotification(
            signal="listening",
            session_id=str(session_id),
            turn_id=str(turn_id),
            generation_id=str(generation_id),
            source_sequence=1,
            public_metadata={
                "token": "private-value",
                "path": r"C:\private\motion.json",
            },
        )

        self.assertIsInstance(notification.session_id, SessionId)
        self.assertIsInstance(notification.turn_id, TurnId)
        self.assertIsInstance(notification.generation_id, GenerationId)
        self.assertIsInstance(notification.source_sequence, EventSequence)
        self.assertEqual(notification.public_metadata["token"], "<redacted>")
        self.assertEqual(notification.public_metadata["path"], "<redacted:path>")

    def test_transient_and_terminal_outcome_rules_are_distinct(self) -> None:
        for signal in (
            MotionLifecycleSignal.LISTENING,
            MotionLifecycleSignal.THINKING,
            MotionLifecycleSignal.SPEAKING,
        ):
            self.assertIsNone(self._notification(signal).outcome)

        accepted = (
            (MotionLifecycleSignal.INTERRUPTED, TurnOutcome.INTERRUPTED),
            (MotionLifecycleSignal.INTERRUPTED, TurnOutcome.CANCELLED),
            (MotionLifecycleSignal.COMPLETED, TurnOutcome.COMPLETED),
            (MotionLifecycleSignal.FAILED, TurnOutcome.FAILED),
        )
        for signal, outcome in accepted:
            self.assertIs(self._notification(signal, outcome=outcome).outcome, outcome)

        with self.assertRaises(ValueError):
            self._notification(
                MotionLifecycleSignal.THINKING,
                outcome=TurnOutcome.COMPLETED,
            )
        with self.assertRaises(ValueError):
            self._notification(MotionLifecycleSignal.COMPLETED)
        with self.assertRaises(ValueError):
            self._notification(
                MotionLifecycleSignal.FAILED,
                outcome=TurnOutcome.REJECTED,
            )

    def test_uncorrelated_request_inherits_notification_context(self) -> None:
        notification = self._notification()
        original = MotionRequest.expression_change("smile")

        result = invoke_motion_lifecycle_hook(
            lambda _notification: original,
            notification,
        )

        self.assertIs(result.outcome, MotionLifecycleHookOutcome.MAPPED)
        self.assertTrue(result.is_mapped)
        self.assertIsNotNone(result.request)
        self.assertEqual(result.request.request_id, original.request_id)
        self.assertEqual(result.request.turn_id, notification.turn_id)
        self.assertEqual(result.request.generation_id, notification.generation_id)
        self.assertIsNone(original.turn_id)
        self.assertIsNone(original.generation_id)

    def test_matching_correlation_is_preserved(self) -> None:
        notification = self._notification()
        request = MotionRequest.emotion_update(
            "happy",
            turn_id=notification.turn_id,
            generation_id=notification.generation_id,
        )

        result = invoke_motion_lifecycle_hook(lambda _notification: request, notification)

        self.assertIs(result.request, request)

    def test_mapped_result_model_rejects_uncorrelated_request(self) -> None:
        with self.assertRaises(ValueError):
            MotionLifecycleHookResult(
                outcome=MotionLifecycleHookOutcome.MAPPED,
                notification=self._notification(),
                request=MotionRequest.expression_change("smile"),
            )

    def test_partial_or_mismatched_correlation_is_isolated(self) -> None:
        notification = self._notification()
        requests = (
            MotionRequest.expression_change(
                "smile",
                turn_id=notification.turn_id,
            ),
            MotionRequest.expression_change(
                "smile",
                turn_id=TurnId.new(),
                generation_id=GenerationId.new(),
            ),
        )

        for request in requests:
            result = invoke_motion_lifecycle_hook(
                lambda _notification, value=request: value,
                notification,
            )
            self.assertIs(result.outcome, MotionLifecycleHookOutcome.FAILED)
            self.assertIsNone(result.request)
            self.assertEqual(
                result.public_metadata["reason"],
                "correlation_mismatch",
            )
            self.assertFalse(result.public_metadata["conversation_terminal_changed"])

    def test_none_is_typed_skip_not_unsupported_or_failure(self) -> None:
        result = invoke_motion_lifecycle_hook(
            lambda _notification: None,
            self._notification(),
        )

        self.assertIs(result.outcome, MotionLifecycleHookOutcome.SKIPPED)
        self.assertIsNone(result.request)
        self.assertEqual(result.public_metadata["reason"], "no_motion_request")

    def test_invalid_return_is_public_safe_failure(self) -> None:
        result = invoke_motion_lifecycle_hook(
            lambda _notification: "provider-specific-hotkey",  # type: ignore[return-value]
            self._notification(),
        )

        self.assertIs(result.outcome, MotionLifecycleHookOutcome.FAILED)
        self.assertEqual(result.public_metadata["reason"], "invalid_hook_result")
        self.assertNotIn("hotkey", repr(result).lower())

    def test_hook_exception_does_not_escape_or_expose_raw_detail(self) -> None:
        notification = self._notification(
            MotionLifecycleSignal.COMPLETED,
            outcome=TurnOutcome.COMPLETED,
        )

        def failing_hook(_notification: MotionLifecycleNotification) -> MotionRequest:
            raise RuntimeError(r"token=private C:\private\motion.json")

        result = invoke_motion_lifecycle_hook(failing_hook, notification)

        self.assertIs(result.outcome, MotionLifecycleHookOutcome.FAILED)
        self.assertIs(result.notification.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(result.public_metadata["reason"], "hook_exception")
        self.assertFalse(result.public_metadata["conversation_terminal_changed"])
        self.assertNotIn("token", repr(result).lower())
        self.assertNotIn("motion.json", repr(result).lower())

    def test_host_plugin_owns_character_specific_mapping(self) -> None:
        notification = self._notification(MotionLifecycleSignal.SPEAKING)
        expression = invoke_motion_lifecycle_hook(
            lambda _notification: MotionRequest.expression_change("smile"),
            notification,
        )
        gesture = invoke_motion_lifecycle_hook(
            lambda _notification: MotionRequest(
                intent=MotionIntent.GESTURE,
                gesture="wave",
            ),
            notification,
        )

        self.assertIs(expression.request.intent, MotionIntent.EXPRESSION)
        self.assertIs(gesture.request.intent, MotionIntent.GESTURE)

    def test_adapter_unsupported_remains_existing_typed_motion_outcome(self) -> None:
        request = MotionRequest(
            intent=MotionIntent.LOOK_AT,
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
        result = MotionResult(
            outcome=MotionOutcome.UNSUPPORTED,
            state=MotionState.UNAVAILABLE,
            adapter_status=MotionAdapterStatus.CONFIGURED,
            public_error_code=MotionErrorCode.UNSUPPORTED,
            request_id=request.request_id,
            session_id=SessionId.new(),
            turn_id=request.turn_id,
            generation_id=request.generation_id,
        )

        self.assertIs(result.outcome, MotionOutcome.UNSUPPORTED)
        self.assertIs(result.public_error_code, MotionErrorCode.UNSUPPORTED)

    def test_explicit_package_does_not_expand_root_public_surface(self) -> None:
        import framework.motion_lifecycle as module

        expected = (
            "MotionLifecycleSignal",
            "MotionLifecycleNotification",
            "MotionLifecycleHookOutcome",
            "MotionLifecycleHookResult",
            "MotionLifecycleHook",
            "invoke_motion_lifecycle_hook",
        )
        self.assertEqual(tuple(module.__all__), expected)
        self.assertEqual(len(framework.__all__), 127)
        self.assertTrue(all(name not in framework.__all__ for name in expected))
        self.assertTrue(isinstance(lambda _notification: None, MotionLifecycleHook))
        self.assertTrue(issubclass(MotionLifecycleHookResult, object))


if __name__ == "__main__":
    unittest.main()
