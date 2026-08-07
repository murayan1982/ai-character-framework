from __future__ import annotations

import unittest

import framework
from framework import RealtimeExecutionError, RealtimeExecutionErrorCode


class RealtimeExecutionModelTests(unittest.TestCase):
    def test_error_codes_are_exact_and_provider_neutral(self) -> None:
        self.assertEqual(
            tuple(code.value for code in RealtimeExecutionErrorCode),
            (
                "blocking_call_in_active_event_loop",
                "blocking_call_from_runtime_thread",
            ),
        )

    def test_error_normalizes_string_code(self) -> None:
        error = RealtimeExecutionError("blocking_call_in_active_event_loop")
        self.assertIs(
            error.code,
            RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP,
        )

    def test_error_message_is_stable_public_safe_text(self) -> None:
        error = RealtimeExecutionError(
            RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD
        )
        self.assertEqual(str(error), error.safe_message)
        self.assertIn("realtime runtime thread", error.safe_message)
        self.assertNotIn("provider", error.safe_message.lower())

    def test_invalid_error_code_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RealtimeExecutionError("not-a-public-code")

    def test_execution_error_is_runtime_error(self) -> None:
        error = RealtimeExecutionError(
            RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP
        )
        self.assertIsInstance(error, RuntimeError)

    def test_root_public_surface_appends_exact_two_execution_names(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(framework.__all__[124], "RealtimeTurnStartResult")
        self.assertEqual(
            tuple(framework.__all__[125:]),
            ("RealtimeExecutionErrorCode", "RealtimeExecutionError"),
        )
        self.assertIs(framework.RealtimeExecutionError, RealtimeExecutionError)
        self.assertIs(
            framework.RealtimeExecutionErrorCode,
            RealtimeExecutionErrorCode,
        )


if __name__ == "__main__":
    unittest.main()
