from __future__ import annotations

import asyncio
import threading
import unittest

import framework
from framework import (
    RealtimeEventType,
    RealtimeExecutionError,
    RealtimeExecutionErrorCode,
    RealtimeTurn,
    TurnOutcome,
)


class RealtimeExecutionSessionAdoptionTests(unittest.TestCase):
    def test_session_owns_lazy_bridge_at_construction_and_start_turn(self) -> None:
        session = framework.create_realtime_session()
        self.assertFalse(session._execution_bridge.started)
        start = session.start_turn(input_text="reserved")
        self.assertTrue(start.accepted)
        self.assertFalse(session._execution_bridge.started)
        session._execution_bridge.shutdown()

    def test_run_turn_async_is_safe_on_host_event_loop(self) -> None:
        session = framework.create_realtime_session()

        async def scenario():
            result = await session.run_turn_async(input_text="async")
            return result

        try:
            result = asyncio.run(scenario())
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(result.session_id, session.info.session_id)
            self.assertTrue(session._execution_bridge.started)
            self.assertTrue(session._execution_bridge.thread_alive)
        finally:
            session._execution_bridge.shutdown()

    def test_run_turn_async_reuses_same_runtime_loop_for_later_turn(self) -> None:
        session = framework.create_realtime_session()

        async def scenario():
            first = await session.run_turn_async(input_text="first")
            first_loop = session._execution_bridge.loop_identity
            first_thread = session._execution_bridge.thread_identity
            second = await session.run_turn_async(input_text="second")
            return first, second, first_loop, first_thread

        try:
            first, second, first_loop, first_thread = asyncio.run(scenario())
            self.assertIs(first.outcome, TurnOutcome.COMPLETED)
            self.assertIs(second.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(session._execution_bridge.loop_identity, first_loop)
            self.assertEqual(session._execution_bridge.thread_identity, first_thread)
        finally:
            session._execution_bridge.shutdown()

    def test_run_turn_blocking_uses_persistent_bridge(self) -> None:
        session = framework.create_realtime_session()
        try:
            result = session.run_turn_blocking(input_text="blocking")
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertTrue(session._execution_bridge.started)
            self.assertTrue(session._execution_bridge.thread_alive)
        finally:
            session._execution_bridge.shutdown()

    def test_legacy_run_turn_delegates_to_blocking_compatibility(self) -> None:
        session = framework.create_realtime_session()
        calls = []
        original = session.run_turn_blocking

        def wrapped(*args, **kwargs):
            calls.append((args, kwargs))
            return original(*args, **kwargs)

        session.run_turn_blocking = wrapped  # type: ignore[method-assign]
        try:
            result = session.run_turn(input_text="legacy")
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(len(calls), 1)
        finally:
            session._execution_bridge.shutdown()

    def test_blocking_wrapper_is_typed_rejection_on_active_host_loop(self) -> None:
        session = framework.create_realtime_session()

        async def scenario():
            with self.assertRaises(RealtimeExecutionError) as captured:
                session.run_turn_blocking(input_text="invalid")
            return captured.exception

        error = asyncio.run(scenario())
        self.assertIs(
            error.code,
            RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP,
        )
        self.assertFalse(session._execution_bridge.started)
        self.assertIsNone(session._active_turn_context)
        session._execution_bridge.shutdown()

    def test_legacy_run_turn_is_typed_rejection_on_active_host_loop(self) -> None:
        session = framework.create_realtime_session()

        async def scenario():
            with self.assertRaises(RealtimeExecutionError) as captured:
                session.run_turn(input_text="invalid legacy")
            return captured.exception

        error = asyncio.run(scenario())
        self.assertIs(
            error.code,
            RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP,
        )
        self.assertFalse(session._execution_bridge.started)
        session._execution_bridge.shutdown()

    def test_blocking_wrapper_is_typed_rejection_on_runtime_thread(self) -> None:
        session = framework.create_realtime_session()

        async def runtime_attempt():
            try:
                session.run_turn_blocking(input_text="runtime callback")
            except RealtimeExecutionError as error:
                return error.code
            raise AssertionError("runtime-thread blocking execution was not rejected")

        try:
            code = session._execution_bridge.run(runtime_attempt())
            self.assertIs(
                code,
                RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD,
            )
        finally:
            session._execution_bridge.shutdown()

    def test_concurrent_async_turn_requests_preserve_single_active_admission(self) -> None:
        session = framework.create_realtime_session()
        entered = threading.Event()
        release = threading.Event()

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                entered.set()
                release.wait(timeout=2.0)

        session.on_event(callback)

        async def scenario():
            first_task = asyncio.create_task(
                session.run_turn_async(input_text="first async")
            )
            await asyncio.to_thread(entered.wait, 2.0)
            second = await session.run_turn_async(input_text="second async")
            release.set()
            first = await first_task
            return first, second

        try:
            first, second = asyncio.run(scenario())
            self.assertIs(first.outcome, TurnOutcome.COMPLETED)
            self.assertIs(second.outcome, TurnOutcome.REJECTED)
            self.assertIsNone(second.generation_id)
            self.assertEqual(
                second.public_metadata.get("reason"),
                "active_turn_exists",
            )
            self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        finally:
            release.set()
            session._execution_bridge.shutdown()

    def test_concurrent_blocking_turn_requests_preserve_single_active_admission(self) -> None:
        session = framework.create_realtime_session()
        entered = threading.Event()
        release = threading.Event()
        first_result = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                entered.set()
                release.wait(timeout=2.0)

        session.on_event(callback)

        def run_first() -> None:
            first_result.append(session.run_turn_blocking(input_text="first blocking"))

        worker = threading.Thread(target=run_first)
        worker.start()
        self.assertTrue(entered.wait(timeout=2.0))
        try:
            second = session.run_turn_blocking(input_text="second blocking")
            self.assertIs(second.outcome, TurnOutcome.REJECTED)
            self.assertIsNone(second.generation_id)
            self.assertEqual(second.public_metadata.get("reason"), "active_turn_exists")
            self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        finally:
            release.set()
            worker.join(timeout=2.0)
            session._execution_bridge.shutdown()
        self.assertEqual(len(first_result), 1)
        self.assertIs(first_result[0].outcome, TurnOutcome.COMPLETED)

    def test_explicit_start_then_async_execution_reuses_generation(self) -> None:
        session = framework.create_realtime_session()
        turn = RealtimeTurn(input_text="explicit then async")
        start = session.start_turn(turn)
        self.assertTrue(start.accepted)
        self.assertIsNotNone(start.generation_id)

        async def scenario():
            return await session.run_turn_async(turn)

        try:
            result = asyncio.run(scenario())
            self.assertEqual(result.generation_id, start.generation_id)
            self.assertEqual(session.generation_diagnostics["generation_start_count"], 1)
        finally:
            session._execution_bridge.shutdown()

    def test_real_runtime_rejection_does_not_start_bridge_or_fallback_to_mock(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)

        async def scenario():
            return await session.run_turn_async(input_text="no fallback")

        result = asyncio.run(scenario())
        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertFalse(session._execution_bridge.started)
        self.assertNotEqual(result.public_metadata.get("mock_runtime"), True)
        session._execution_bridge.shutdown()


if __name__ == "__main__":
    unittest.main()
