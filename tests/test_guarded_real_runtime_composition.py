"""Provider-free contract tests for FW-RT6-13b guarded composition."""

from __future__ import annotations

import subprocess
import sys
import unittest

from framework.guarded_real_runtime import (
    GuardedRealRuntimeCompositionConfig,
    GuardedRealRuntimeCompositionStatus,
    GuardedRealRuntimeStageStatus,
    compose_guarded_real_runtime,
)
from framework.realtime_capabilities import (
    RealtimeMotionCapability,
    RealtimeVoiceInputCapability,
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from framework.realtime_session_config import RealtimeSessionConfig
from framework.realtime_stage import RealtimeStageKind


PRIVATE_MARKER = "PRIVATE_STAGE_CONFIG_MUST_NOT_LEAK"


def _real_runtime() -> RuntimeCapabilityState:
    return RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=False,
        real_runtime=True,
        unavailable_reason=None,
        public_metadata={"private_model": PRIVATE_MARKER},
    )


def _capability(
    stage_kind: RealtimeStageKind,
    *,
    ready: bool = True,
):
    runtime = _real_runtime()
    if stage_kind is RealtimeStageKind.VOICE_INPUT:
        return RealtimeVoiceInputCapability(
            runtime=runtime,
            final_transcript_supported=ready,
            accepted_audio_formats=("wav",),
        )
    if stage_kind is RealtimeStageKind.TEXT_GENERATION:
        return TextGenerationCapability(
            runtime=runtime,
            streaming_supported=ready,
            cooperative_cancel_supported=True,
        )
    if stage_kind is RealtimeStageKind.VOICE_OUTPUT:
        if not ready:
            return RealtimeVoiceOutputCapability(
                runtime=RuntimeCapabilityState(
                    configured=True,
                    runtime_available=True,
                    guarded=True,
                    real_runtime=True,
                    unavailable_reason="operator_guarded",
                ),
                audio_formats=("wav",),
            )
        return RealtimeVoiceOutputCapability(
            runtime=runtime,
            streaming_audio_supported=True,
            generation_cancel_supported=True,
            playback_ownership="host",
            audio_formats=("wav",),
        )
    return RealtimeMotionCapability(
        runtime=runtime,
        request_cancel_supported=True,
        completion_event_supported=True,
        provider_neutral_intent_supported=ready,
        stop_motion_supported=True,
    )


class _Stage:
    def __init__(
        self,
        stage_kind: RealtimeStageKind,
        *,
        capability=None,
        preflight_error: BaseException | None = None,
        close_error: BaseException | None = None,
    ) -> None:
        self.stage_kind = stage_kind
        self._capability = capability or _capability(stage_kind)
        self._preflight_error = preflight_error
        self._close_error = close_error
        self.preflight_count = 0
        self.close_count = 0

    def preflight(self):
        self.preflight_count += 1
        if self._preflight_error is not None:
            raise self._preflight_error
        return self._capability

    def capability(self):
        return self._capability

    def start(self, *, context, request):
        del context, request
        return object()

    def cancel(self, *, context):
        del context
        return True

    def close(self) -> None:
        self.close_count += 1
        if self._close_error is not None:
            raise self._close_error


def _factory_config(
    *,
    real_runtime_enabled: bool = True,
    allow_provider_execution: bool = True,
    stages: dict[RealtimeStageKind, object] | None = None,
    factories: dict[RealtimeStageKind, object] | None = None,
) -> GuardedRealRuntimeCompositionConfig:
    resolved_stages = stages or {
        stage_kind: _Stage(stage_kind)
        for stage_kind in RealtimeStageKind
    }
    resolved_factories = factories or {
        stage_kind: (lambda stage=stage: stage)
        for stage_kind, stage in resolved_stages.items()
    }
    return GuardedRealRuntimeCompositionConfig(
        real_runtime_enabled=real_runtime_enabled,
        allow_provider_execution=allow_provider_execution,
        voice_input_factory=resolved_factories.get(RealtimeStageKind.VOICE_INPUT),
        text_generation_factory=resolved_factories.get(
            RealtimeStageKind.TEXT_GENERATION
        ),
        voice_output_factory=resolved_factories.get(RealtimeStageKind.VOICE_OUTPUT),
        motion_factory=resolved_factories.get(RealtimeStageKind.MOTION),
    )


def _close_ready_result(result) -> None:
    config = result.session_config
    if config is None:
        return
    for stage in (
        config.motion_stage,
        config.voice_output_stage,
        config.text_generation_stage,
        config.voice_input_stage,
    ):
        if stage is not None:
            stage.close()


class GuardedRealRuntimeCompositionTests(unittest.TestCase):
    def test_explicit_module_import_is_provider_sdk_lazy_and_root_unchanged(self) -> None:
        source = """
import sys
import framework
before = set(sys.modules)
root_before = tuple(framework.__all__)
import framework.guarded_real_runtime
loaded = set(sys.modules) - before
for name in ('openai', 'pyvts', 'requests', 'sounddevice'):
    if name in loaded:
        raise AssertionError(name)
if tuple(framework.__all__) != root_before:
    raise AssertionError('root drift')
if 'compose_guarded_real_runtime' in framework.__all__:
    raise AssertionError('unexpected root export')
"""
        completed = subprocess.run(
            [sys.executable, "-c", source],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_first_opt_in_disabled_blocks_every_factory(self) -> None:
        calls: list[str] = []

        def forbidden_factory():
            calls.append("called")
            raise AssertionError("factory must stay lazy")

        factories = {kind: forbidden_factory for kind in RealtimeStageKind}
        result = compose_guarded_real_runtime(
            _factory_config(
                real_runtime_enabled=False,
                allow_provider_execution=True,
                factories=factories,
            )
        )

        self.assertIs(result.status, GuardedRealRuntimeCompositionStatus.DISABLED)
        self.assertEqual(calls, [])
        self.assertTrue(
            all(
                item.status is GuardedRealRuntimeStageStatus.BLOCKED
                and not item.factory_reached
                for item in result.stage_results
            )
        )

    def test_second_opt_in_missing_blocks_every_factory(self) -> None:
        calls: list[str] = []

        def forbidden_factory():
            calls.append("called")
            raise AssertionError("factory must stay lazy")

        factories = {kind: forbidden_factory for kind in RealtimeStageKind}
        result = compose_guarded_real_runtime(
            _factory_config(
                real_runtime_enabled=True,
                allow_provider_execution=False,
                factories=factories,
            )
        )

        self.assertIs(
            result.status,
            GuardedRealRuntimeCompositionStatus.PROVIDER_EXECUTION_BLOCKED,
        )
        self.assertEqual(calls, [])
        self.assertFalse(result.runtime_ready)

    def test_incomplete_configuration_is_fail_closed_before_factory_reach(self) -> None:
        calls: list[str] = []
        stages = {kind: _Stage(kind) for kind in RealtimeStageKind}

        def reached_factory():
            calls.append("called")
            return stages[RealtimeStageKind.VOICE_INPUT]

        config = GuardedRealRuntimeCompositionConfig(
            real_runtime_enabled=True,
            allow_provider_execution=True,
            voice_input_factory=reached_factory,
        )
        result = compose_guarded_real_runtime(config)

        self.assertIs(
            result.status,
            GuardedRealRuntimeCompositionStatus.CONFIGURATION_INCOMPLETE,
        )
        self.assertEqual(calls, [])
        self.assertEqual(
            tuple(item.status for item in result.stage_results),
            (
                GuardedRealRuntimeStageStatus.NOT_REACHED,
                GuardedRealRuntimeStageStatus.CONFIGURATION_MISSING,
                GuardedRealRuntimeStageStatus.CONFIGURATION_MISSING,
                GuardedRealRuntimeStageStatus.CONFIGURATION_MISSING,
            ),
        )

    def test_four_real_stages_preflight_once_and_return_session_handoff(self) -> None:
        stages = {kind: _Stage(kind) for kind in RealtimeStageKind}
        factory_calls: list[str] = []
        factories = {
            kind: (
                lambda stage=stage, kind=kind: (
                    factory_calls.append(kind.value),
                    stage,
                )[1]
            )
            for kind, stage in stages.items()
        }
        result = compose_guarded_real_runtime(
            _factory_config(stages=stages, factories=factories)
        )
        try:
            self.assertIs(result.status, GuardedRealRuntimeCompositionStatus.READY)
            self.assertTrue(result.runtime_ready)
            self.assertIsInstance(result.session_config, RealtimeSessionConfig)
            self.assertTrue(result.session_config.real_runtime_enabled)
            self.assertEqual(
                factory_calls,
                [kind.value for kind in RealtimeStageKind],
            )
            self.assertEqual(
                result.ready_stage_kinds,
                tuple(kind.value for kind in RealtimeStageKind),
            )
            self.assertEqual(result.failed_stage_kinds, ())
            self.assertTrue(
                all(
                    item.status is GuardedRealRuntimeStageStatus.READY
                    and item.factory_reached
                    and item.preflight_reached
                    and item.capability_reached
                    and item.ready
                    for item in result.stage_results
                )
            )
            self.assertTrue(all(stage.preflight_count == 1 for stage in stages.values()))
        finally:
            _close_ready_result(result)

    def test_stage_specific_capability_requirements_fail_safely(self) -> None:
        for failed_kind in RealtimeStageKind:
            with self.subTest(stage=failed_kind.value):
                stages = {
                    kind: _Stage(
                        kind,
                        capability=_capability(
                            kind,
                            ready=kind is not failed_kind,
                        ),
                    )
                    for kind in RealtimeStageKind
                }
                result = compose_guarded_real_runtime(
                    _factory_config(stages=stages)
                )

                self.assertIs(
                    result.status,
                    GuardedRealRuntimeCompositionStatus.PREFLIGHT_FAILED,
                )
                failed = next(
                    item
                    for item in result.stage_results
                    if item.stage_kind is failed_kind
                )
                self.assertIs(
                    failed.status,
                    GuardedRealRuntimeStageStatus.CAPABILITY_UNAVAILABLE,
                )
                self.assertTrue(all(stage.close_count == 1 for stage in stages.values()))

    def test_factory_failure_normalizes_raw_exception_and_continues_reach(self) -> None:
        stages = {kind: _Stage(kind) for kind in RealtimeStageKind}

        def failing_factory():
            raise RuntimeError(PRIVATE_MARKER)

        factories = {
            kind: (lambda stage=stage: stage)
            for kind, stage in stages.items()
        }
        factories[RealtimeStageKind.TEXT_GENERATION] = failing_factory
        result = compose_guarded_real_runtime(
            _factory_config(stages=stages, factories=factories)
        )

        self.assertIs(
            result.status,
            GuardedRealRuntimeCompositionStatus.PREFLIGHT_FAILED,
        )
        failed = result.stage_results[1]
        self.assertIs(failed.status, GuardedRealRuntimeStageStatus.FACTORY_FAILED)
        self.assertTrue(failed.factory_reached)
        self.assertFalse(failed.preflight_reached)
        self.assertNotIn(PRIVATE_MARKER, repr(result))
        self.assertNotIn("RuntimeError", repr(result))
        self.assertTrue(stages[RealtimeStageKind.MOTION].preflight_count == 1)

    def test_preflight_failure_and_cleanup_failure_are_count_only(self) -> None:
        stages = {kind: _Stage(kind) for kind in RealtimeStageKind}
        stages[RealtimeStageKind.VOICE_OUTPUT] = _Stage(
            RealtimeStageKind.VOICE_OUTPUT,
            preflight_error=ValueError(PRIVATE_MARKER),
            close_error=RuntimeError(PRIVATE_MARKER),
        )
        result = compose_guarded_real_runtime(_factory_config(stages=stages))

        self.assertIs(result.stage_results[2].status, GuardedRealRuntimeStageStatus.PREFLIGHT_FAILED)
        self.assertEqual(result.public_metadata["cleanup_failure_count"], 1)
        self.assertNotIn(PRIVATE_MARKER, repr(result))
        self.assertNotIn("ValueError", repr(result))
        self.assertTrue(all(stage.close_count == 1 for stage in stages.values()))

    def test_invalid_protocol_or_stage_kind_is_rejected_and_closed(self) -> None:
        class InvalidStage:
            def __init__(self) -> None:
                self.close_count = 0

            def close(self) -> None:
                self.close_count += 1

        invalid = InvalidStage()
        stages = {kind: _Stage(kind) for kind in RealtimeStageKind}
        factories = {
            kind: (lambda stage=stage: stage)
            for kind, stage in stages.items()
        }
        factories[RealtimeStageKind.MOTION] = lambda: invalid
        result = compose_guarded_real_runtime(
            _factory_config(stages=stages, factories=factories)
        )

        self.assertIs(
            result.stage_results[3].status,
            GuardedRealRuntimeStageStatus.PROTOCOL_REJECTED,
        )
        self.assertEqual(invalid.close_count, 1)
        self.assertFalse(result.runtime_ready)

    def test_private_factory_state_and_capabilities_never_enter_public_result(self) -> None:
        stages = {kind: _Stage(kind) for kind in RealtimeStageKind}

        def private_factory(stage):
            private_configuration = PRIVATE_MARKER
            return lambda: (private_configuration and stage)

        factories = {
            kind: private_factory(stage)
            for kind, stage in stages.items()
        }
        config = _factory_config(stages=stages, factories=factories)
        result = compose_guarded_real_runtime(config)
        try:
            self.assertTrue(result.runtime_ready)
            self.assertNotIn(PRIVATE_MARKER, repr(config))
            self.assertNotIn(PRIVATE_MARKER, repr(result))
            self.assertNotIn(PRIVATE_MARKER, str(result.public_metadata))
            self.assertFalse(result.public_metadata["raw_exception_exposed"])
            self.assertFalse(result.public_metadata["private_configuration_exposed"])
        finally:
            _close_ready_result(result)


if __name__ == "__main__":
    unittest.main()
