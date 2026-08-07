"""Provider-free tests for FW-RT6-4a Control B session construction adoption."""

from __future__ import annotations

import inspect
import unittest

import framework
from framework.identity import SessionId
from framework.realtime_capabilities import (
    RealtimeMotionCapability,
    RealtimeVoiceInputCapability,
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from framework.realtime_session import RealtimeSession
from framework.realtime_session_config import (
    RealtimeSessionConfig,
    RealtimeSessionConstructionStatus,
)
from framework.realtime_stage import RealtimeStageKind


def _real_runtime_state() -> RuntimeCapabilityState:
    return RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=False,
        real_runtime=True,
        unavailable_reason=None,
        public_metadata={"provider_execution_performed": False},
    )


def _capability_for(stage_kind: RealtimeStageKind) -> object:
    runtime = _real_runtime_state()
    if stage_kind is RealtimeStageKind.VOICE_INPUT:
        return RealtimeVoiceInputCapability(
            runtime=runtime,
            audio_chunk_input_supported=True,
            partial_transcript_supported=True,
            final_transcript_supported=True,
            input_abort_supported=True,
            backpressure_supported=True,
            accepted_audio_formats=("pcm16",),
            maximum_chunk_size=4096,
            maximum_duration=30,
        )
    if stage_kind is RealtimeStageKind.TEXT_GENERATION:
        return TextGenerationCapability(
            runtime=runtime,
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=True,
        )
    if stage_kind is RealtimeStageKind.VOICE_OUTPUT:
        return RealtimeVoiceOutputCapability(
            runtime=runtime,
            streaming_audio_supported=True,
            generation_cancel_supported=True,
            provider_hard_cancel_supported=True,
            pending_flush_supported=True,
            active_audio_invalidation_supported=True,
            audio_formats=("wav",),
            maximum_text_size=4000,
        )
    if stage_kind is RealtimeStageKind.MOTION:
        return RealtimeMotionCapability(
            runtime=runtime,
            request_cancel_supported=True,
            completion_event_supported=True,
            provider_neutral_intent_supported=True,
        )
    raise AssertionError("unknown test stage kind")


class _FakeStage:
    def __init__(
        self,
        stage_kind: RealtimeStageKind,
        *,
        capability: object | None = None,
        preflight_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.stage_kind = stage_kind
        self.preflight_result = (
            capability if capability is not None else _capability_for(stage_kind)
        )
        self.preflight_error = preflight_error
        self.close_error = close_error
        self.calls: list[str] = []

    def preflight(self) -> object:
        self.calls.append("preflight")
        if self.preflight_error is not None:
            raise self.preflight_error
        return self.preflight_result

    def capability(self) -> object:
        self.calls.append("capability")
        raise AssertionError("capability refresh must not run during construction")

    def start(self, *, context: object, request: object) -> object:
        self.calls.append("start")
        raise AssertionError("stage execution must not run during construction")

    def cancel(self, *, context: object) -> bool:
        self.calls.append("cancel")
        raise AssertionError("stage cancellation must not run during construction")

    def close(self) -> None:
        self.calls.append("close")
        if self.close_error is not None:
            raise self.close_error


def _all_stages() -> dict[str, _FakeStage]:
    return {
        "voice_input": _FakeStage(RealtimeStageKind.VOICE_INPUT),
        "text_generation": _FakeStage(RealtimeStageKind.TEXT_GENERATION),
        "voice_output": _FakeStage(RealtimeStageKind.VOICE_OUTPUT),
        "motion": _FakeStage(RealtimeStageKind.MOTION),
    }


class RealtimeSessionConstructionAdoptionTests(unittest.TestCase):
    def test_factory_and_constructor_append_keyword_only_config(self) -> None:
        expected = (
            "project_root",
            "public_metadata",
            "real_runtime_enabled",
            "voice_input_stage",
            "text_generation_stage",
            "voice_output_stage",
            "motion_stage",
            "config",
        )
        for callable_object in (framework.create_realtime_session, RealtimeSession):
            signature = inspect.signature(callable_object)
            self.assertEqual(tuple(signature.parameters), expected)
            self.assertTrue(
                all(
                    parameter.kind is inspect.Parameter.KEYWORD_ONLY
                    for parameter in signature.parameters.values()
                )
            )
            self.assertIsNone(signature.parameters["config"].default)

    def test_config_cannot_mix_with_legacy_runtime_or_stage_inputs(self) -> None:
        config = RealtimeSessionConfig()
        with self.assertRaises(TypeError):
            framework.create_realtime_session(config=object())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            framework.create_realtime_session(
                config=config,
                real_runtime_enabled=False,
            )
        with self.assertRaises(TypeError):
            framework.create_realtime_session(
                config=config,
                motion_stage=_FakeStage(RealtimeStageKind.MOTION),
            )

    def test_default_session_preserves_mock_snapshot_and_internal_result(self) -> None:
        session = framework.create_realtime_session()
        snapshot = session.capabilities

        self.assertEqual(snapshot.session_id, session.info.session_id)
        self.assertTrue(snapshot.supports_text_chat)
        self.assertTrue(snapshot.supports_voice_input)
        self.assertTrue(snapshot.supports_voice_output)
        self.assertFalse(snapshot.supports_motion)
        self.assertFalse(snapshot.real_runtime_enabled)
        self.assertIs(snapshot, session.capabilities)
        self.assertIs(
            session._construction_result.status,
            RealtimeSessionConstructionStatus.MOCK_READY,
        )
        self.assertTrue(session._construction_result.runtime_executable)
        self.assertEqual(session._construction_result.session_id, session.info.session_id)

    def test_mock_config_preflights_injected_stages_but_keeps_mock_snapshot(self) -> None:
        stages = _all_stages()
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                voice_input_stage=stages["voice_input"],
                text_generation_stage=stages["text_generation"],
                voice_output_stage=stages["voice_output"],
                motion_stage=stages["motion"],
            )
        )

        self.assertTrue(all(stage.calls == ["preflight"] for stage in stages.values()))
        self.assertFalse(session.info.supports_motion)
        self.assertFalse(session.capabilities.supports_motion)
        self.assertTrue(session.capabilities.text_generation.runtime.fake_runtime)
        self.assertEqual(session.injected_stage_kinds, tuple(stages))

        result = session.run_turn(input_text="mock-path-remains-deterministic")
        self.assertEqual(result.outcome.value, "completed")
        self.assertTrue(all(stage.calls == ["preflight"] for stage in stages.values()))

    def test_real_text_configuration_projects_preflight_capability(self) -> None:
        text_stage = _FakeStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                text_generation_stage=text_stage,
            )
        )
        snapshot = session.capabilities

        self.assertEqual(text_stage.calls, ["preflight"])
        self.assertIs(snapshot.text_generation, text_stage.preflight_result)
        self.assertTrue(snapshot.supports_text_chat)
        self.assertFalse(snapshot.supports_voice_input)
        self.assertFalse(snapshot.supports_voice_output)
        self.assertFalse(snapshot.supports_motion)
        self.assertFalse(snapshot.real_runtime_enabled)
        self.assertIs(
            session._construction_result.status,
            RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY,
        )
        self.assertFalse(session._construction_result.runtime_executable)

    def test_real_all_stage_snapshot_and_info_are_consistent(self) -> None:
        stages = _all_stages()
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                voice_input_stage=stages["voice_input"],
                text_generation_stage=stages["text_generation"],
                voice_output_stage=stages["voice_output"],
                motion_stage=stages["motion"],
            )
        )
        snapshot = session.capabilities
        info = session.info

        self.assertTrue(snapshot.supports_text_chat)
        self.assertTrue(snapshot.supports_voice_input)
        self.assertTrue(snapshot.supports_voice_output)
        self.assertTrue(snapshot.supports_motion)
        self.assertTrue(snapshot.hard_cancel_supported)
        self.assertTrue(snapshot.tts_queue_flush_supported)
        self.assertEqual(info.supports_text_chat, snapshot.supports_text_chat)
        self.assertEqual(info.supports_voice_input, snapshot.supports_voice_input)
        self.assertEqual(info.supports_voice_output, snapshot.supports_voice_output)
        self.assertEqual(info.supports_motion, snapshot.supports_motion)
        self.assertEqual(info.hard_cancel_supported, snapshot.hard_cancel_supported)
        self.assertEqual(
            info.tts_queue_flush_supported,
            snapshot.tts_queue_flush_supported,
        )
        self.assertTrue(all(stage.calls == ["preflight"] for stage in stages.values()))

    def test_real_request_without_text_stage_is_typed_incomplete_internally(self) -> None:
        motion_stage = _FakeStage(RealtimeStageKind.MOTION)
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                motion_stage=motion_stage,
            )
        )
        result = session._construction_result

        self.assertIs(
            result.status,
            RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE,
        )
        self.assertEqual(result.missing_stage_kinds, ("text_generation",))
        self.assertFalse(result.configuration_complete)
        self.assertEqual(motion_stage.calls, ["preflight"])
        self.assertEqual(
            session.capabilities.text_generation.runtime.unavailable_reason,
            "stage_not_configured",
        )

    def test_preflight_exception_is_typed_and_raw_detail_is_not_exposed(self) -> None:
        text_stage = _FakeStage(
            RealtimeStageKind.TEXT_GENERATION,
            preflight_error=RuntimeError(r"credential=C:\private\provider-token"),
        )
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                text_generation_stage=text_stage,
            )
        )
        result = session._construction_result

        self.assertIs(
            result.status,
            RealtimeSessionConstructionStatus.PREFLIGHT_FAILED,
        )
        self.assertEqual(result.failed_stage_kinds, ("text_generation",))
        self.assertNotIn("credential", repr(result).lower())
        self.assertNotIn("private", repr(result).lower())
        self.assertEqual(
            session.capabilities.text_generation.runtime.unavailable_reason,
            "stage_preflight_failed",
        )

    def test_wrong_preflight_result_type_is_safe_failure(self) -> None:
        text_stage = _FakeStage(
            RealtimeStageKind.TEXT_GENERATION,
            capability=RealtimeMotionCapability(),
        )
        session = framework.create_realtime_session(
            config=RealtimeSessionConfig(
                real_runtime_enabled=True,
                text_generation_stage=text_stage,
            )
        )

        self.assertEqual(
            session._construction_result.failed_stage_kinds,
            ("text_generation",),
        )
        self.assertEqual(text_stage.calls, ["preflight"])

    def test_fake_or_unusable_capability_is_not_real_configuration_ready(self) -> None:
        fake_runtime = RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            guarded=False,
            fake_runtime=True,
            real_runtime=False,
            unavailable_reason=None,
        )
        for capability in (
            TextGenerationCapability(),
            TextGenerationCapability(runtime=fake_runtime),
        ):
            with self.subTest(capability=capability):
                text_stage = _FakeStage(
                    RealtimeStageKind.TEXT_GENERATION,
                    capability=capability,
                )
                session = framework.create_realtime_session(
                    config=RealtimeSessionConfig(
                        real_runtime_enabled=True,
                        text_generation_stage=text_stage,
                    )
                )
                self.assertIs(
                    session._construction_result.status,
                    RealtimeSessionConstructionStatus.PREFLIGHT_FAILED,
                )
                self.assertEqual(
                    session.capabilities.text_generation.runtime.unavailable_reason,
                    "stage_preflight_failed",
                )

    def test_snapshot_is_stable_after_turn_and_close(self) -> None:
        session = framework.create_realtime_session()
        snapshot = session.capabilities
        session.run_turn(input_text="stable-snapshot")
        self.assertIs(session.capabilities, snapshot)
        session.close()
        self.assertIs(session.capabilities, snapshot)
        self.assertEqual(snapshot.snapshot_generation, 1)

    def test_session_owns_unique_identity_hub_registry_and_gate(self) -> None:
        first = framework.create_realtime_session()
        second = framework.create_realtime_session()

        self.assertIsInstance(first.info.session_id, SessionId)
        self.assertNotEqual(first.info.session_id, second.info.session_id)
        self.assertIsNot(first._event_hub, second._event_hub)
        self.assertIsNot(first._terminal_registry, second._terminal_registry)
        self.assertIsNot(first._generation_gate, second._generation_gate)

    def test_stage_close_remains_once_only_after_preflight(self) -> None:
        text_stage = _FakeStage(RealtimeStageKind.TEXT_GENERATION)
        session = framework.create_realtime_session(
            text_generation_stage=text_stage,
        )
        session.close()
        session.close()

        self.assertEqual(text_stage.calls, ["preflight", "close"])
        self.assertEqual(session.stage_diagnostics["stage_close_count"], 1)

    def test_invalid_stage_protocol_and_kind_reject_safely(self) -> None:
        class _MissingClose:
            stage_kind = "voice_input"

            def preflight(self) -> object:
                return RealtimeVoiceInputCapability()

            def capability(self) -> object:
                return RealtimeVoiceInputCapability()

            def start(self, *, context: object, request: object) -> object:
                return None

            def cancel(self, *, context: object) -> bool:
                return False

        with self.assertRaises(TypeError) as missing_close:
            framework.create_realtime_session(voice_input_stage=_MissingClose())
        self.assertNotIn("private", str(missing_close.exception).lower())

        with self.assertRaises(ValueError) as wrong_kind:
            framework.create_realtime_session(
                voice_input_stage=_FakeStage(RealtimeStageKind.MOTION)
            )
        self.assertNotIn("private", str(wrong_kind.exception).lower())

    def test_close_failure_remains_count_only_and_public_safe(self) -> None:
        stage = _FakeStage(
            RealtimeStageKind.TEXT_GENERATION,
            close_error=RuntimeError(r"credential=C:\private\operator-token"),
        )
        session = framework.create_realtime_session(text_generation_stage=stage)
        session.close()
        session.close()

        self.assertTrue(session.is_closed)
        self.assertEqual(stage.calls, ["preflight", "close"])
        self.assertEqual(session.stage_diagnostics["stage_close_count"], 0)
        self.assertEqual(session.stage_diagnostics["stage_close_error_count"], 1)
        self.assertNotIn("credential", repr(session.info).lower())
        self.assertNotIn("private", repr(session.info).lower())


if __name__ == "__main__":
    unittest.main()
