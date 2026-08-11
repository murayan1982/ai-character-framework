"""Provider-free runtime adoption tests for FW-RT6-10b Control B."""

from __future__ import annotations

import asyncio
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import framework
from framework.audio.voice_output import VoiceOutputSession
from framework.facade import TextChatSession, TextChatSessionInfo
from framework.lifecycle import TurnOutcome
from framework.motion_session import MotionSession
from framework.realtime import RealtimeEventType
from framework.realtime_execution_bridge import _RealtimeExecutionBridge
from framework.realtime_session import RealtimeSession
from framework.session_close import (
    SessionCleanupOutcome,
    SessionCleanupTarget,
    SessionCloseOutcome,
    SessionCloseResult,
)
from framework.voice_input_session import VoiceInputSession
from llm.base import BaseLLM


class _ChunkLLM(BaseLLM):
    @property
    def provider_name(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return "fake-model"

    def ask_stream(self, text: str):
        del text
        yield "first", []
        yield "late", []


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


class _CloseStage:
    def __init__(self, *, delay: float = 0.0, error: Exception | None = None) -> None:
        self.delay = delay
        self.error = error
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error


class _MotionComposition:
    def __init__(self, *, delay: float = 0.0, outcome: str = "completed") -> None:
        self.delay = delay
        self.outcome = outcome
        self.close_count = 0
        self.bridge_thread_alive = False

    def close(self) -> SimpleNamespace:
        self.close_count += 1
        if self.delay:
            time.sleep(self.delay)
        return SimpleNamespace(outcome=SimpleNamespace(value=self.outcome))


def _cleanup_outcome(
    result: SessionCloseResult,
    target: SessionCleanupTarget,
) -> SessionCleanupOutcome:
    return next(
        item.outcome for item in result.cleanup_results if item.target is target
    )


class SessionCloseControlBTests(unittest.TestCase):
    def test_all_five_public_sessions_publish_first_and_duplicate_results(self) -> None:
        sessions = (
            RealtimeSession(),
            TextChatSession(_ChunkLLM(), _text_info()),
            VoiceInputSession(),
            VoiceOutputSession(),
            MotionSession(),
        )
        for session in sessions:
            with self.subTest(session=type(session).__name__):
                self.assertIsNone(session.last_close_result)
                self.assertIsNone(session.close())
                self.assertIs(session.last_close_result.outcome, SessionCloseOutcome.CLOSED)
                self.assertTrue(session.is_closed)
                first = session.last_close_result
                self.assertIsNone(session.dispose())
                self.assertIs(
                    session.last_close_result.outcome,
                    SessionCloseOutcome.ALREADY_CLOSED,
                )
                self.assertEqual(
                    session.last_close_result.diagnostics["cleanup_attempted_count"],
                    0,
                )
                self.assertIsNot(first, session.last_close_result)

    def test_realtime_close_commits_active_turn_and_one_correlated_final_event(self) -> None:
        session = RealtimeSession()
        events = []
        session.on_event(events.append)
        started = session.start_turn(input_text="hello")
        self.assertTrue(started.accepted)

        session.close()

        terminal = session.terminal_results[-1]
        self.assertIs(terminal.outcome, TurnOutcome.CLOSED)
        self.assertEqual(terminal.turn_id, started.turn_id)
        self.assertEqual(terminal.generation_id, started.generation_id)
        closed = [event for event in events if event.type is RealtimeEventType.SESSION_CLOSED]
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].turn_id, started.turn_id)
        self.assertEqual(closed[0].generation_id, started.generation_id)
        self.assertTrue(session.last_close_result.active_turn_terminalized)
        self.assertEqual(session.event_diagnostics["subscriber_count"], 0)

    def test_realtime_stage_closes_run_in_parallel_under_one_deadline(self) -> None:
        session = RealtimeSession()
        fast = _CloseStage()
        slow = _CloseStage(delay=0.20)
        session._injected_stages = {"fast": fast, "slow": slow}
        started = time.monotonic()
        with patch("framework.realtime_session._SESSION_CLOSE_TIMEOUT_SECONDS", 0.03):
            session.close()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.15)
        self.assertTrue(session.is_closed)
        self.assertIs(
            _cleanup_outcome(session.last_close_result, SessionCleanupTarget.STAGE),
            SessionCleanupOutcome.TIMED_OUT,
        )
        self.assertEqual(session.stage_diagnostics["stage_close_count"], 1)
        self.assertEqual(session.stage_diagnostics["stage_close_error_count"], 1)

    def test_realtime_stage_failure_is_typed_and_does_not_reopen(self) -> None:
        session = RealtimeSession()
        failing = _CloseStage(error=RuntimeError("private provider failure"))
        session._injected_stages = {"failing": failing}
        session.close()
        self.assertTrue(session.is_closed)
        self.assertIs(
            session.last_close_result.outcome,
            SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES,
        )
        self.assertIs(
            _cleanup_outcome(session.last_close_result, SessionCleanupTarget.STAGE),
            SessionCleanupOutcome.FAILED,
        )
        self.assertNotIn("private provider failure", repr(session.last_close_result))

    def test_realtime_bridge_reports_confirmed_shutdown(self) -> None:
        bridge = _RealtimeExecutionBridge(thread_name="control-b-test-bridge")
        self.assertEqual(bridge.run(asyncio.sleep(0, result=7)), 7)
        self.assertTrue(bridge.shutdown(timeout_seconds=1.0))
        self.assertFalse(bridge.thread_alive)
        self.assertTrue(bridge.shutdown(timeout_seconds=0.01))

    def test_realtime_concurrent_duplicate_does_not_repeat_cleanup_or_event(self) -> None:
        session = RealtimeSession()
        stage = _CloseStage(delay=0.05)
        session._injected_stages = {"stage": stage}
        events = []
        session.on_event(events.append)
        first = threading.Thread(target=session.close)
        first.start()
        time.sleep(0.01)
        session.close()
        first.join(timeout=1.0)

        self.assertFalse(first.is_alive())
        self.assertEqual(stage.close_count, 1)
        self.assertEqual(
            sum(event.type is RealtimeEventType.SESSION_CLOSED for event in events),
            1,
        )
        self.assertIs(
            session.last_close_result.outcome,
            SessionCloseOutcome.ALREADY_CLOSED,
        )

    def test_text_close_terminalizes_active_context_and_suppresses_late_chunks(self) -> None:
        session = TextChatSession(_ChunkLLM(), _text_info())
        events = []
        session.on_realtime_event(events.append)
        stream = session.ask_stream("hello")
        self.assertEqual(next(stream), "first")
        session.close()
        self.assertEqual(list(stream), [])

        self.assertEqual(events[-1].type, RealtimeEventType.SESSION_CLOSED)
        self.assertEqual(events[-1].turn_id, events[0].turn_id)
        self.assertTrue(session.last_close_result.active_turn_terminalized)
        self.assertEqual(session._realtime_event_callbacks, [])
        self.assertEqual(session._event_callbacks, [])
        self.assertEqual(session._state_change_callbacks, [])

    def test_text_callback_failure_is_typed_while_session_stays_closed(self) -> None:
        session = TextChatSession(_ChunkLLM(), _text_info())
        stream = session.ask_stream("hello")
        self.assertEqual(next(stream), "first")
        session.on_event(lambda _event: (_ for _ in ()).throw(RuntimeError("secret")))
        session.close()
        self.assertTrue(session.is_closed)
        self.assertIs(
            _cleanup_outcome(
                session.last_close_result,
                SessionCleanupTarget.CALLBACK_HUB,
            ),
            SessionCleanupOutcome.FAILED,
        )
        self.assertNotIn("secret", repr(session.last_close_result))

    def test_voice_input_close_uses_active_context_and_clears_callbacks(self) -> None:
        session = VoiceInputSession()
        canonical = []
        legacy = []
        session.on_realtime_event(canonical.append)
        session.on_event(legacy.append)
        context = session._new_realtime_turn_context()
        session.close()

        self.assertEqual(canonical[-1].type, RealtimeEventType.SESSION_CLOSED)
        self.assertEqual(canonical[-1].turn_id, context.turn_id)
        self.assertEqual(canonical[-1].generation_id, context.generation_id)
        self.assertEqual(legacy[-1]["type"], "voice_input.closed")
        self.assertTrue(session.last_close_result.active_turn_terminalized)
        self.assertEqual(session._realtime_event_callbacks, [])
        self.assertEqual(session._callbacks, [])

    def test_voice_output_has_no_persistent_provider_cleanup_target(self) -> None:
        session = VoiceOutputSession()
        session.close()
        self.assertIs(
            _cleanup_outcome(
                session.last_close_result,
                SessionCleanupTarget.PROVIDER_CLIENT,
            ),
            SessionCleanupOutcome.NOT_REQUIRED,
        )

    def test_motion_maps_composition_and_bridge_cleanup_and_clears_callbacks(self) -> None:
        session = MotionSession()
        composition = _MotionComposition()
        session._vts_composition = composition
        events = []
        session.on_event(events.append)
        session.close()

        self.assertEqual(composition.close_count, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(session._callbacks, [])
        self.assertEqual(session._realtime_event_callbacks, [])
        self.assertIs(
            _cleanup_outcome(
                session.last_close_result,
                SessionCleanupTarget.PROVIDER_CLIENT,
            ),
            SessionCleanupOutcome.COMPLETED,
        )
        self.assertIs(
            _cleanup_outcome(
                session.last_close_result,
                SessionCleanupTarget.EXECUTION_BRIDGE,
            ),
            SessionCleanupOutcome.COMPLETED,
        )

    def test_motion_composition_timeout_is_bounded_and_typed(self) -> None:
        session = MotionSession(vts_close_timeout_seconds=0.02)
        session._vts_composition = _MotionComposition(delay=0.20)
        started = time.monotonic()
        session.close()
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.15)
        self.assertTrue(session.is_closed)
        self.assertIs(
            _cleanup_outcome(
                session.last_close_result,
                SessionCleanupTarget.PROVIDER_CLIENT,
            ),
            SessionCleanupOutcome.TIMED_OUT,
        )

    def test_close_result_name_is_explicit_and_control_a_surface_stays_exact(self) -> None:
        self.assertTrue(hasattr(framework.RealtimeSession, "last_close_result"))
        self.assertFalse(hasattr(framework.RealtimeSession, "close_result"))
        self.assertNotIn("SessionCloseResult", framework.__all__)
        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(framework.RealtimeSessionInfo().api_version, "5.2.0")
        self.assertEqual(framework.MotionSessionInfo().api_version, "5.5.0")


if __name__ == "__main__":
    unittest.main()
