"""Provider-free FW-RT6-10d Control B runtime-adoption regressions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import unittest

import framework
from core.events import EVENT_USER_INPUT, emit
from framework.facade import TextChatSession, TextChatSessionInfo
from framework.motion import MotionIntent, MotionRequest
from framework.motion_session import MotionSession
from framework.realtime import RealtimeEventType
from framework.realtime_session import RealtimeSession
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind
from framework.session_close import SessionCloseOutcome
from llm.base import BaseLLM


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _ChunkLLM(BaseLLM):
    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def ask_stream(self, text: str):
        del text
        yield "safe", []


class _RaisingStage:
    def __init__(self, stage_kind: RealtimeStageKind) -> None:
        self.stage_kind = stage_kind

    def start(self, *, context: object, request: object) -> object:
        del context, request
        raise RuntimeError("private-stage-exception-sentinel")

    def cancel(self, context: object) -> bool:
        del context
        return True


def _text_info() -> TextChatSessionInfo:
    return TextChatSessionInfo(
        preset="text_chat",
        character_name="test",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="fake",
        provider="fake",
        model="fake-model",
        route_name=None,
    )


def _raising(_: object) -> None:
    raise RuntimeError("private-callback-exception-sentinel")


class CallbackIsolationControlBTests(unittest.TestCase):
    def test_root_versions_factories_and_explicit_policy_surface_stay_stable(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertFalse(hasattr(framework, "CallbackIsolationPolicy"))
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")
        self.assertTrue(callable(framework.create_realtime_session))
        self.assertTrue(callable(framework.create_voice_input_session))

    def test_text_callbacks_are_isolated_and_do_not_corrupt_success(self) -> None:
        session = TextChatSession(_ChunkLLM(), _text_info())
        observed: list[str] = []

        session.on_realtime_event(_raising)
        session.on_realtime_event(lambda event: observed.append(event.type.value))
        session.on_event(_raising)
        session.on_event(lambda event: observed.append(event.type))
        session.on_state_change(_raising)
        session.on_state_change(
            lambda event: observed.append(f"state:{event.new_state}")
        )

        result = session.ask_result("hello")

        self.assertTrue(result.is_completed)
        self.assertEqual(result.text, "safe")
        self.assertEqual(session._state, "idle")
        self.assertIn("realtime.turn.completed", observed)
        self.assertIn("response_completed", observed)
        self.assertIn("state:idle", observed)

    def test_text_callback_snapshot_is_stable_and_reentrant(self) -> None:
        session = TextChatSession(_ChunkLLM(), _text_info())
        observed: list[str] = []

        def late(_: object) -> None:
            observed.append("late")

        def first(_: object) -> None:
            observed.append("first")
            if late not in session._event_callbacks:
                session.on_event(late)

        session.on_event(first)
        session.on_event(lambda _: observed.append("last"))
        session._emit_event("one")
        self.assertEqual(observed, ["first", "last"])
        session._emit_event("two")
        self.assertEqual(observed, ["first", "last", "first", "last", "late"])

    def test_voice_callbacks_continue_and_run_without_input_operation_lock(self) -> None:
        session = framework.create_voice_input_session(language="ja-JP")
        canonical: list[str] = []
        legacy: list[str] = []
        lock_observations: list[bool] = []

        def canonical_failure(_: object) -> None:
            lock_observations.append(session._input_operation_lock._is_owned())
            raise RuntimeError("private-canonical-sentinel")

        def legacy_failure(_: object) -> None:
            lock_observations.append(session._input_operation_lock._is_owned())
            raise RuntimeError("private-legacy-sentinel")

        session.on_realtime_event(canonical_failure)
        session.on_realtime_event(lambda event: canonical.append(event.type.value))
        session.on_event(legacy_failure)
        session.on_event(lambda event: legacy.append(event["type"]))

        result = session.listen_result()

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.UNAVAILABLE)
        self.assertEqual(
            canonical,
            ["realtime.voice_input.preflight", "realtime.voice_input.failed"],
        )
        self.assertEqual(legacy, ["voice_input.started", "voice_input.unavailable"])
        self.assertTrue(lock_observations)
        self.assertFalse(any(lock_observations))

    def test_voice_callback_can_reenter_abort_without_deadlock(self) -> None:
        session = framework.create_voice_input_session()
        lock_observations: list[bool] = []

        def abort_on_start(event: object) -> None:
            if event["type"] == "voice_input.started":  # type: ignore[index]
                lock_observations.append(
                    session._input_operation_lock._is_owned()
                )
                self.assertTrue(session.abort_input())

        session.on_event(abort_on_start)
        result = session.listen_result()

        self.assertEqual(result.outcome, framework.VoiceInputOutcome.INTERRUPTED)
        self.assertEqual(lock_observations, [False])

    def test_motion_callbacks_are_isolated_snapshot_and_lock_free(self) -> None:
        session = MotionSession()
        observed: list[str] = []
        lock_observations: list[bool] = []

        def failure(_: object) -> None:
            lock_observations.append(
                session._realtime_coordination_lock._is_owned()
            )
            raise RuntimeError("private-motion-callback-sentinel")

        session.on_event(failure)
        session.on_event(lambda event: observed.append(event["type"]))
        payload = session.emit_created()

        self.assertEqual(payload["type"], "motion.session.created")
        self.assertEqual(observed, ["motion.session.created"])
        self.assertEqual(lock_observations, [False])

    def test_sync_and_async_plugin_hooks_are_isolated_in_order(self) -> None:
        observed: list[str] = []
        runtime: dict[str, object] = {"hooks": {EVENT_USER_INPUT: []}}
        handlers = runtime["hooks"][EVENT_USER_INPUT]  # type: ignore[index]

        async def async_failure(value: str) -> None:
            observed.append(f"async-failed:{value}")
            await asyncio.sleep(0)
            raise RuntimeError("private-async-plugin-sentinel")

        def first(value: str) -> None:
            observed.append(f"first:{value}")
            if len(handlers) == 4:
                handlers.append(lambda item: observed.append(f"late:{item}"))

        def sync_failure(value: str) -> None:
            observed.append(f"sync-failed:{value}")
            raise RuntimeError("private-sync-plugin-sentinel")

        handlers.extend((first, sync_failure, async_failure, lambda value: observed.append(f"last:{value}")))
        self.assertIsNone(asyncio.run(emit(runtime, EVENT_USER_INPUT, "one")))
        self.assertEqual(
            observed,
            ["first:one", "sync-failed:one", "async-failed:one", "last:one"],
        )
        self.assertIsNone(asyncio.run(emit(runtime, EVENT_USER_INPUT, "two")))
        self.assertEqual(observed[-5:], [
            "first:two",
            "sync-failed:two",
            "async-failed:two",
            "last:two",
            "late:two",
        ])

    def test_realtime_callbacks_are_isolated_lock_free_and_snapshot_safe(self) -> None:
        session = RealtimeSession()
        observed: list[str] = []
        lock_observations: list[bool] = []
        first_token: dict[str, str] = {}

        def first(event: object) -> None:
            observed.append("first")
            lock_observations.append(session._operation_lock._is_owned())
            self.assertTrue(session.off_event(first_token["value"]))

        first_token["value"] = session.on_event(first)
        session.on_event(_raising)
        session.on_event(lambda event: observed.append(event.type.value))

        started = session.start_turn(input_text="hello")

        self.assertTrue(started.accepted)
        self.assertEqual(observed, ["first", "realtime.turn.started"])
        self.assertEqual(lock_observations, [False])
        self.assertEqual(session.event_diagnostics["callback_error_count"], 1)

    def test_stage_exceptions_become_typed_critical_and_noncritical_results(self) -> None:
        for stage_kind, criticality, action in (
            (RealtimeStageKind.TEXT_GENERATION, "critical", "fail_current_operation"),
            (RealtimeStageKind.VOICE_OUTPUT, "non_critical", "continue_degraded"),
        ):
            with self.subTest(stage_kind=stage_kind.value):
                session = RealtimeSession()
                started = session.start_turn(input_text="hello")
                context = RealtimeStageContext(
                    session_id=session._session_id,
                    turn_id=started.turn_id,
                    generation_id=started.generation_id,
                )
                session._injected_stages = {
                    stage_kind.value: _RaisingStage(stage_kind)
                }
                session._stage_capabilities = {stage_kind.value: object()}

                envelope = session._execute_interruptible_stage(
                    stage_kind=stage_kind.value,
                    context=context,
                    request=object(),
                )

                self.assertIsNotNone(envelope)
                self.assertEqual(envelope.stage_kind, stage_kind)
                self.assertEqual(envelope.public_metadata["stage_criticality"], criticality)
                self.assertEqual(envelope.public_metadata["failure_action"], action)
                self.assertTrue(envelope.public_metadata["session_remains_open"])
                self.assertTrue(envelope.public_metadata["runtime_remains_available"])
                self.assertFalse(envelope.public_metadata["raw_exception_retained"])
                self.assertNotIn("private-stage", repr(envelope))
                self.assertNotIn("private-stage", json.dumps(dict(envelope.public_metadata)))

    def test_motion_stage_failure_is_noncritical_and_does_not_replace_terminal(self) -> None:
        session = RealtimeSession()
        started = session.start_turn(input_text="hello")
        request = MotionRequest(
            intent=MotionIntent.EXPRESSION,
            expression="smile",
            turn_id=started.turn_id,
            generation_id=started.generation_id,
        )
        terminals_before = session.terminal_results

        result = session._motion_lifecycle_failure_result(
            request=request,
            reason="stage_exception",
        )

        self.assertEqual(result.public_metadata["stage_criticality"], "non_critical")
        self.assertEqual(result.public_metadata["failure_action"], "continue_degraded")
        self.assertFalse(result.public_metadata["conversation_terminal_changed"])
        self.assertEqual(session.terminal_results, terminals_before)
        self.assertFalse(session.is_closed)

    def test_callback_failure_during_close_is_typed_and_sessions_stay_closed(self) -> None:
        text = TextChatSession(_ChunkLLM(), _text_info())
        stream = text.ask_stream("hello")
        self.assertEqual(next(stream), "safe")
        text.on_event(_raising)

        voice = framework.create_voice_input_session()
        voice.on_event(_raising)

        motion = MotionSession()
        motion.on_event(_raising)

        realtime = RealtimeSession()
        realtime.start_turn(input_text="hello")
        realtime.on_event(_raising)

        for session in (text, voice, motion, realtime):
            with self.subTest(session=type(session).__name__):
                session.close()
                self.assertTrue(session.is_closed)
                self.assertIs(
                    session.last_close_result.outcome,
                    SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES,
                )
                self.assertNotIn("private-callback", repr(session.last_close_result))

    def test_control_b_surface_keeps_aggregate_tasks_open_and_control_c_out(self) -> None:
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split(
            "## FW-RT6-10d — Callback and plugin isolation",
            1,
        )[1].split("## FW-RT6-11a", 1)[0]
        self.assertEqual(section.count("- [ ]"), 6)
        self.assertEqual(section.count("- [x]"), 0)
        self.assertNotIn("check_v600_callback_isolation_acceptance", "\n".join(
            str(path.relative_to(PROJECT_ROOT))
            for path in PROJECT_ROOT.glob("scripts/*callback_isolation*")
        ))


if __name__ == "__main__":
    unittest.main()
