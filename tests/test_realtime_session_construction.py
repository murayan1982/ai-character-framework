"""Provider-free tests for FW-RT6-4a construction/config public models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from framework.identity import SessionId
from framework.public_safety import REDACTED_VALUE
from framework.realtime import RealtimeErrorCode
from framework.realtime_session_config import (
    RealtimeSessionConfig,
    RealtimeSessionConstructionResult,
    RealtimeSessionConstructionStatus,
)


class _OpaqueStage:
    def __repr__(self) -> str:  # pragma: no cover - failure sentinel
        raise AssertionError("stage repr must not be evaluated")


class RealtimeSessionConfigTests(unittest.TestCase):
    def test_default_config_is_explicitly_mock_safe(self) -> None:
        config = RealtimeSessionConfig()

        self.assertFalse(config.real_runtime_enabled)
        self.assertIsNone(config.voice_input_stage)
        self.assertIsNone(config.text_generation_stage)
        self.assertIsNone(config.voice_output_stage)
        self.assertIsNone(config.motion_stage)

    def test_stage_bindings_are_retained_but_hidden_from_repr(self) -> None:
        stage = _OpaqueStage()
        config = RealtimeSessionConfig(
            real_runtime_enabled=True,
            text_generation_stage=stage,
        )

        self.assertIs(config.text_generation_stage, stage)
        self.assertEqual(
            repr(config),
            "RealtimeSessionConfig(real_runtime_enabled=True)",
        )

    def test_config_is_frozen_and_rejects_non_boolean_runtime_flag(self) -> None:
        config = RealtimeSessionConfig()
        with self.assertRaises(FrozenInstanceError):
            config.real_runtime_enabled = True  # type: ignore[misc]
        with self.assertRaises(TypeError):
            RealtimeSessionConfig(real_runtime_enabled=1)  # type: ignore[arg-type]


class RealtimeSessionConstructionResultTests(unittest.TestCase):
    def test_status_and_error_code_values_are_exact(self) -> None:
        self.assertEqual(
            tuple(status.value for status in RealtimeSessionConstructionStatus),
            (
                "mock_ready",
                "real_configuration_ready",
                "configuration_incomplete",
                "preflight_failed",
            ),
        )
        self.assertEqual(
            RealtimeErrorCode.CONFIGURATION_MISSING.value,
            "configuration_missing",
        )

    def test_mock_ready_result_is_immutable_and_public_safe(self) -> None:
        session_id = SessionId.new()
        result = RealtimeSessionConstructionResult(
            status="mock_ready",
            session_id=str(session_id),
            configuration_complete=True,
            runtime_executable=True,
            real_runtime_requested=False,
            real_runtime_enabled=False,
            safe_message=r"C:\private\construction.txt",
            public_metadata={
                "api_token": "private-value",
                "boundary": "realtime_session_construction",
            },
        )

        self.assertIs(result.status, RealtimeSessionConstructionStatus.MOCK_READY)
        self.assertEqual(result.session_id, session_id)
        self.assertEqual(
            result.safe_message,
            "Realtime session construction is unavailable.",
        )
        self.assertEqual(result.public_metadata["api_token"], REDACTED_VALUE)
        with self.assertRaises(TypeError):
            result.public_metadata["boundary"] = "changed"  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            result.retryable = True  # type: ignore[misc]

    def test_real_configuration_ready_may_remain_non_executable(self) -> None:
        result = RealtimeSessionConstructionResult(
            status=RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY,
            session_id=SessionId.new(),
            configuration_complete=True,
            runtime_executable=False,
            real_runtime_requested=True,
            real_runtime_enabled=False,
            safe_message="Real runtime orchestration is not available.",
        )

        self.assertFalse(result.runtime_executable)
        self.assertFalse(result.real_runtime_enabled)

    def test_configuration_incomplete_requires_canonical_missing_stage(self) -> None:
        result = RealtimeSessionConstructionResult(
            status="configuration_incomplete",
            session_id=SessionId.new(),
            configuration_complete=False,
            runtime_executable=False,
            real_runtime_requested=True,
            real_runtime_enabled=False,
            missing_stage_kinds=[" TEXT_GENERATION "],
        )

        self.assertEqual(result.missing_stage_kinds, ("text_generation",))
        with self.assertRaises(ValueError):
            RealtimeSessionConstructionResult(
                status="configuration_incomplete",
                session_id=SessionId.new(),
                configuration_complete=False,
                runtime_executable=False,
                real_runtime_requested=True,
                real_runtime_enabled=False,
            )

    def test_preflight_failed_requires_failed_stage(self) -> None:
        result = RealtimeSessionConstructionResult(
            status="preflight_failed",
            session_id=SessionId.new(),
            configuration_complete=True,
            runtime_executable=False,
            real_runtime_requested=True,
            real_runtime_enabled=False,
            failed_stage_kinds=("voice_output",),
            retryable=True,
        )

        self.assertEqual(result.failed_stage_kinds, ("voice_output",))
        self.assertTrue(result.retryable)
        with self.assertRaises(ValueError):
            RealtimeSessionConstructionResult(
                status="preflight_failed",
                session_id=SessionId.new(),
                configuration_complete=True,
                runtime_executable=False,
                real_runtime_requested=True,
                real_runtime_enabled=False,
            )

    def test_enabled_real_runtime_requires_truthful_ready_state(self) -> None:
        result = RealtimeSessionConstructionResult(
            status="real_configuration_ready",
            session_id=SessionId.new(),
            configuration_complete=True,
            runtime_executable=True,
            real_runtime_requested=True,
            real_runtime_enabled=True,
        )
        self.assertTrue(result.real_runtime_enabled)

        with self.assertRaises(ValueError):
            RealtimeSessionConstructionResult(
                status="real_configuration_ready",
                session_id=SessionId.new(),
                configuration_complete=True,
                runtime_executable=False,
                real_runtime_requested=True,
                real_runtime_enabled=True,
            )

    def test_invalid_or_duplicate_stage_kinds_are_rejected(self) -> None:
        common = dict(
            status="configuration_incomplete",
            session_id=SessionId.new(),
            configuration_complete=False,
            runtime_executable=False,
            real_runtime_requested=True,
            real_runtime_enabled=False,
        )
        with self.assertRaises(ValueError):
            RealtimeSessionConstructionResult(
                **common,
                missing_stage_kinds=("provider_specific",),
            )
        with self.assertRaises(ValueError):
            RealtimeSessionConstructionResult(
                **common,
                missing_stage_kinds=("text_generation", "text_generation"),
            )


if __name__ == "__main__":
    unittest.main()
