"""Provider-free tests for FW-RT6-8b Control B runtime adoption."""

from __future__ import annotations

import inspect
import unittest

import framework
from framework import RealtimeEventType, RealtimeState, TurnOutcome
from framework.motion import (
    MotionAdapterStatus,
    MotionErrorCode,
    MotionOutcome,
    MotionRequest,
    MotionResult,
    MotionState,
)
from framework.motion_lifecycle import MotionLifecycleSignal
from framework.realtime_capabilities import (
    RealtimeMotionCapability,
    RuntimeCapabilityState,
)
from framework.realtime_session import RealtimeSession
from framework.realtime_stage import (
    RealtimeStageContext,
    RealtimeStageKind,
    RealtimeStageResultEnvelope,
)


def _ready_motion_capability() -> RealtimeMotionCapability:
    return RealtimeMotionCapability(
        runtime=RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            guarded=False,
            fake_runtime=False,
            real_runtime=True,
            unavailable_reason=None,
            public_metadata={"provider_execution_performed": False},
        ),
        request_cancel_supported=True,
        completion_event_supported=True,
        provider_neutral_intent_supported=True,
    )


class _MotionStage:
    stage_kind = RealtimeStageKind.MOTION

    def __init__(
        self,
        *,
        mode: str = "completed",
        preflight_error: Exception | None = None,
    ) -> None:
        self.mode = mode
        self.preflight_error = preflight_error
        self.preflight_count = 0
        self.start_calls: list[tuple[RealtimeStageContext, MotionRequest]] = []
        self.cancel_count = 0
        self.close_count = 0
        self.on_start = None

    def preflight(self) -> RealtimeMotionCapability:
        self.preflight_count += 1
        if self.preflight_error is not None:
            raise self.preflight_error
        return _ready_motion_capability()

    def capability(self) -> RealtimeMotionCapability:
        raise AssertionError("Control B must use the construction preflight snapshot")

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: MotionRequest,
    ) -> RealtimeStageResultEnvelope[MotionResult]:
        self.start_calls.append((context, request))
        if self.on_start is not None:
            self.on_start()
        if self.mode == "exception":
            raise RuntimeError("private provider failure")

        result = MotionResult.completed(
            request=request,
            session_id=context.session_id,
        )
        envelope_context = context
        if self.mode == "unsupported":
            result = MotionResult(
                outcome=MotionOutcome.UNSUPPORTED,
                state=MotionState.UNAVAILABLE,
                adapter_status=MotionAdapterStatus.UNSUPPORTED_ADAPTER,
                public_error_code=MotionErrorCode.UNSUPPORTED,
                safe_message="Motion intent is unsupported.",
                request_id=request.request_id,
                session_id=context.session_id,
                turn_id=request.turn_id,
                generation_id=request.generation_id,
            )
        elif self.mode == "result_mismatch":
            result = MotionResult.completed(
                request=MotionRequest.speaking_state(
                    True,
                    turn_id=request.turn_id,
                    generation_id=request.generation_id,
                ),
                session_id=context.session_id,
            )
        elif self.mode == "context_mismatch":
            envelope_context = RealtimeStageContext(
                session_id=context.session_id,
                turn_id=context.turn_id,
                generation_id=framework.GenerationId.new(),
            )

        return RealtimeStageResultEnvelope(
            stage_kind=self.stage_kind,
            context=envelope_context,
            result=result,
        )

    def cancel(self, *, context: RealtimeStageContext) -> bool:
        self.cancel_count += 1
        return False

    def close(self) -> None:
        self.close_count += 1


def _listening_only_hook(notifications: list[object]):
    def hook(notification):
        notifications.append(notification)
        if notification.signal is not MotionLifecycleSignal.LISTENING:
            return None
        return MotionRequest.speaking_state(True)

    return hook


class MotionLifecycleControlBTests(unittest.TestCase):
    def test_registration_is_explicit_and_preserves_factory_config_surface(self) -> None:
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
        self.assertEqual(
            tuple(inspect.signature(framework.create_realtime_session).parameters),
            expected,
        )
        self.assertNotIn("motion_lifecycle_hook", expected)
        self.assertTrue(hasattr(RealtimeSession, "set_motion_lifecycle_hook"))

        session = framework.create_realtime_session()
        with self.assertRaises(TypeError):
            session.set_motion_lifecycle_hook(object())  # type: ignore[arg-type]
        session.set_motion_lifecycle_hook(lambda notification: None)
        session.set_motion_lifecycle_hook(None)
        session.close()
        with self.assertRaises(framework.LifecycleTransitionError):
            session.set_motion_lifecycle_hook(None)

    def test_hook_cannot_change_while_turn_is_active(self) -> None:
        session = framework.create_realtime_session()
        start = session.start_turn(input_text="active")
        self.assertTrue(start.accepted)
        with self.assertRaises(RuntimeError):
            session.set_motion_lifecycle_hook(lambda notification: None)
        session.close()

    def test_no_hook_preserves_mock_runtime_and_never_starts_motion_stage(self) -> None:
        stage = _MotionStage()
        session = framework.create_realtime_session(motion_stage=stage)

        result = session.run_turn(input_text="no hook")

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(stage.start_calls, [])
        self.assertFalse(
            any(event.boundary == "motion" for event in session.event_history)
        )

    def test_mapped_signals_execute_after_source_with_shared_sequence(self) -> None:
        stage = _MotionStage()
        notifications: list[object] = []
        session = framework.create_realtime_session(motion_stage=stage)

        def hook(notification):
            notifications.append(notification)
            return MotionRequest.speaking_state(
                notification.signal is MotionLifecycleSignal.SPEAKING
            )

        session.set_motion_lifecycle_hook(hook)
        result = session.run_turn(input_text="mapped")

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(
            [notification.signal for notification in notifications],
            [
                MotionLifecycleSignal.LISTENING,
                MotionLifecycleSignal.THINKING,
                MotionLifecycleSignal.SPEAKING,
                MotionLifecycleSignal.COMPLETED,
            ],
        )
        self.assertEqual(len(stage.start_calls), 4)
        events = session.event_history
        for notification in notifications:
            source_index = next(
                index
                for index, event in enumerate(events)
                if event.sequence == notification.source_sequence
            )
            motion_triplet = events[source_index + 1 : source_index + 4]
            self.assertEqual(
                [event.type for event in motion_triplet],
                [
                    RealtimeEventType.MOTION_REQUESTED,
                    RealtimeEventType.MOTION_STARTED,
                    RealtimeEventType.MOTION_COMPLETED,
                ],
            )
            self.assertTrue(all(event.boundary == "motion" for event in motion_triplet))
            self.assertTrue(
                all(event.turn_id == notification.turn_id for event in motion_triplet)
            )
            self.assertTrue(
                all(
                    event.generation_id == notification.generation_id
                    for event in motion_triplet
                )
            )
        self.assertEqual(
            [int(event.sequence) for event in events],
            list(range(1, len(events) + 1)),
        )

    def test_hook_skip_failure_and_invalid_return_are_isolated(self) -> None:
        hooks = (
            lambda notification: None,
            lambda notification: (_ for _ in ()).throw(RuntimeError("private")),
            lambda notification: object(),
        )
        for hook in hooks:
            with self.subTest(hook=hook):
                stage = _MotionStage()
                session = framework.create_realtime_session(motion_stage=stage)
                session.set_motion_lifecycle_hook(hook)

                result = session.run_turn(input_text="isolated")

                self.assertIs(result.outcome, TurnOutcome.COMPLETED)
                self.assertEqual(stage.start_calls, [])
                self.assertFalse(
                    any(event.boundary == "motion" for event in session.event_history)
                )

    def test_missing_stage_is_typed_not_configured_without_started_event(self) -> None:
        notifications: list[object] = []
        session = framework.create_realtime_session()
        session.set_motion_lifecycle_hook(_listening_only_hook(notifications))

        result = session.run_turn(input_text="missing stage")
        motion_events = tuple(
            event for event in session.event_history if event.boundary == "motion"
        )

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(
            [event.type for event in motion_events],
            [RealtimeEventType.MOTION_REQUESTED, RealtimeEventType.MOTION_FAILED],
        )
        self.assertIs(motion_events[-1].payload.outcome, MotionOutcome.NOT_CONFIGURED)
        self.assertIs(
            motion_events[-1].public_error_code,
            framework.RealtimeErrorCode.CONFIGURATION_MISSING,
        )

    def test_preflight_failure_is_unavailable_and_stage_never_starts(self) -> None:
        stage = _MotionStage(preflight_error=RuntimeError("private preflight"))
        notifications: list[object] = []
        session = framework.create_realtime_session(motion_stage=stage)
        session.set_motion_lifecycle_hook(_listening_only_hook(notifications))

        result = session.run_turn(input_text="preflight")
        motion_events = tuple(
            event for event in session.event_history if event.boundary == "motion"
        )

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(stage.preflight_count, 1)
        self.assertEqual(stage.start_calls, [])
        self.assertEqual(
            [event.type for event in motion_events],
            [RealtimeEventType.MOTION_REQUESTED, RealtimeEventType.MOTION_FAILED],
        )
        self.assertIs(motion_events[-1].payload.outcome, MotionOutcome.UNAVAILABLE)

    def test_stage_exception_and_correlation_mismatch_fail_safely(self) -> None:
        for mode in ("exception", "result_mismatch", "context_mismatch"):
            with self.subTest(mode=mode):
                stage = _MotionStage(mode=mode)
                notifications: list[object] = []
                session = framework.create_realtime_session(motion_stage=stage)
                session.set_motion_lifecycle_hook(_listening_only_hook(notifications))

                result = session.run_turn(input_text=mode)
                motion_events = tuple(
                    event
                    for event in session.event_history
                    if event.boundary == "motion"
                )

                self.assertIs(result.outcome, TurnOutcome.COMPLETED)
                self.assertEqual(len(stage.start_calls), 1)
                self.assertEqual(
                    [event.type for event in motion_events],
                    [
                        RealtimeEventType.MOTION_REQUESTED,
                        RealtimeEventType.MOTION_STARTED,
                        RealtimeEventType.MOTION_FAILED,
                    ],
                )
                self.assertIs(motion_events[-1].payload.outcome, MotionOutcome.FAILED)
                self.assertNotIn("private", motion_events[-1].safe_message)

    def test_unsupported_adapter_outcome_is_preserved(self) -> None:
        stage = _MotionStage(mode="unsupported")
        notifications: list[object] = []
        session = framework.create_realtime_session(motion_stage=stage)
        session.set_motion_lifecycle_hook(_listening_only_hook(notifications))

        result = session.run_turn(input_text="unsupported")
        motion_result = next(
            event
            for event in session.event_history
            if event.type is RealtimeEventType.MOTION_FAILED
        )

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertIs(motion_result.payload.outcome, MotionOutcome.UNSUPPORTED)
        self.assertIs(
            motion_result.public_error_code,
            framework.RealtimeErrorCode.UNSUPPORTED,
        )

    def test_transient_stage_completion_uses_common_stale_generation_gate(self) -> None:
        stage = _MotionStage()
        notifications: list[object] = []
        session = framework.create_realtime_session(motion_stage=stage)
        stage.on_start = lambda: session._advance_generation("interrupt")
        session.set_motion_lifecycle_hook(_listening_only_hook(notifications))

        result = session.run_turn(input_text="stale")
        types = [event.type for event in session.event_history]
        motion_failure = next(
            event
            for event in session.event_history
            if event.type is RealtimeEventType.MOTION_FAILED
        )

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertIn(RealtimeEventType.STALE_RESULT_DROPPED, types)
        self.assertIs(motion_failure.payload.outcome, MotionOutcome.INTERRUPTED)
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)

    def test_terminal_motion_is_post_terminal_and_does_not_reopen_generation(self) -> None:
        stage = _MotionStage()
        notifications: list[object] = []
        session = framework.create_realtime_session(motion_stage=stage)
        session.set_motion_lifecycle_hook(
            lambda notification: (
                notifications.append(notification)
                or (
                    MotionRequest.stop_motion()
                    if notification.signal is MotionLifecycleSignal.COMPLETED
                    else None
                )
            )
        )

        result = session.run_turn(input_text="terminal")
        events = session.event_history
        terminal_index = next(
            index
            for index, event in enumerate(events)
            if event.type is RealtimeEventType.TURN_COMPLETED
        )

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(
            [event.type for event in events[terminal_index + 1 :]],
            [
                RealtimeEventType.MOTION_REQUESTED,
                RealtimeEventType.MOTION_STARTED,
                RealtimeEventType.MOTION_COMPLETED,
            ],
        )
        self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)
        self.assertEqual(session.generation_diagnostics["generation_advance_count"], 1)
        self.assertIsNone(session._generation_gate.current_generation_id)

    def test_terminal_signal_mapping_covers_interrupt_cancel_and_failure(self) -> None:
        cases = (
            (
                RealtimeEventType.TURN_INTERRUPTED,
                TurnOutcome.INTERRUPTED,
                RealtimeState.INTERRUPTED,
                MotionLifecycleSignal.INTERRUPTED,
            ),
            (
                RealtimeEventType.TURN_CANCELLED,
                TurnOutcome.CANCELLED,
                RealtimeState.INTERRUPTED,
                MotionLifecycleSignal.INTERRUPTED,
            ),
            (
                RealtimeEventType.TURN_FAILED,
                TurnOutcome.FAILED,
                RealtimeState.FAILED,
                MotionLifecycleSignal.FAILED,
            ),
        )
        for event_type, outcome, state, signal in cases:
            with self.subTest(event_type=event_type):
                stage = _MotionStage()
                notifications: list[object] = []
                session = framework.create_realtime_session(motion_stage=stage)
                session.set_motion_lifecycle_hook(
                    lambda notification: (
                        notifications.append(notification)
                        or MotionRequest.stop_motion()
                    )
                )
                start = session.start_turn(input_text=event_type.value)
                terminal = framework.RealtimeTurnResult(
                    turn_id=start.turn_id,
                    outcome=outcome,
                    session_id=start.session_id,
                    generation_id=start.generation_id,
                )

                with session._serialized_operation():
                    session._commit_terminal_result(
                        terminal,
                        event_type=event_type,
                        new_state=state,
                        reason=event_type.value,
                    )

                self.assertEqual([item.signal for item in notifications], [signal])
                self.assertIs(notifications[0].outcome, outcome)
                self.assertEqual(len(stage.start_calls), 1)
                self.assertEqual(session.terminal_diagnostics["terminal_commit_count"], 1)

    def test_turn_rejected_and_session_closed_are_not_hook_sources(self) -> None:
        notifications: list[object] = []
        session = framework.create_realtime_session(real_runtime_enabled=True)
        session.set_motion_lifecycle_hook(
            lambda notification: notifications.append(notification) or None
        )

        rejected = session.run_turn(input_text="rejected")
        session.close()

        self.assertIs(rejected.outcome, TurnOutcome.REJECTED)
        self.assertEqual(notifications, [])

    def test_callback_or_hook_close_prevents_stage_start(self) -> None:
        for owner in ("callback", "hook"):
            with self.subTest(owner=owner):
                stage = _MotionStage()
                session = framework.create_realtime_session(motion_stage=stage)
                if owner == "callback":
                    session.on_event(
                        lambda event: (
                            session.close()
                            if event.type is RealtimeEventType.LISTENING_STARTED
                            else None
                        )
                    )
                    session.set_motion_lifecycle_hook(
                        lambda notification: MotionRequest.speaking_state(True)
                    )
                else:
                    session.set_motion_lifecycle_hook(
                        lambda notification: (
                            session.close() or MotionRequest.speaking_state(True)
                        )
                    )

                result = session.run_turn(input_text=owner)

                self.assertIs(result.outcome, TurnOutcome.COMPLETED)
                self.assertEqual(stage.start_calls, [])
                self.assertTrue(session._closed)

    def test_stage_close_ownership_remains_session_owned_and_idempotent(self) -> None:
        stage = _MotionStage()
        session = framework.create_realtime_session(motion_stage=stage)
        session.set_motion_lifecycle_hook(None)

        session.close()
        session.close()

        self.assertEqual(stage.close_count, 1)
        self.assertEqual(stage.cancel_count, 0)


if __name__ == "__main__":
    unittest.main()
