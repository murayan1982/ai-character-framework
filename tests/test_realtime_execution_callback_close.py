from __future__ import annotations

import asyncio
import threading
import unittest

import framework
from framework import (
    RealtimeEventType,
    RealtimeExecutionError,
    RealtimeExecutionErrorCode,
    RealtimeState,
    TurnOutcome,
)
from framework.realtime_execution_bridge import _RealtimeExecutionBridge


class RealtimeExecutionCallbackCloseTests(unittest.TestCase):
    def test_async_turn_callbacks_execute_on_runtime_thread(self) -> None:
        session = framework.create_realtime_session()
        caller_thread = threading.get_ident()
        callback_threads: list[int] = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                callback_threads.append(threading.get_ident())

        session.on_event(callback)

        async def scenario():
            return await session.run_turn_async(input_text="async callback context")

        try:
            result = asyncio.run(scenario())
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(callback_threads, [session._execution_bridge.thread_identity])
            self.assertNotEqual(callback_threads[0], caller_thread)
        finally:
            session.close()

    def test_blocking_turn_callbacks_execute_on_runtime_thread(self) -> None:
        session = framework.create_realtime_session()
        caller_thread = threading.get_ident()
        callback_threads: list[int] = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                callback_threads.append(threading.get_ident())

        session.on_event(callback)
        try:
            result = session.run_turn_blocking(input_text="blocking callback context")
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(callback_threads, [session._execution_bridge.thread_identity])
            self.assertNotEqual(callback_threads[0], caller_thread)
        finally:
            session.close()

    def test_direct_interrupt_callbacks_execute_on_caller_thread(self) -> None:
        session = framework.create_realtime_session()
        caller_thread = threading.get_ident()
        callback_threads: list[int] = []

        def callback(event) -> None:
            if event.type in {
                RealtimeEventType.INTERRUPT_REQUESTED,
                RealtimeEventType.INTERRUPT_UNSUPPORTED,
            }:
                callback_threads.append(threading.get_ident())

        session.on_event(callback)
        try:
            session.interrupt()
            self.assertTrue(callback_threads)
            self.assertEqual(set(callback_threads), {caller_thread})
            self.assertFalse(session._execution_bridge.started)
        finally:
            session.close()

    def test_runtime_callback_blocking_reentrancy_is_typed_rejection(self) -> None:
        session = framework.create_realtime_session()
        rejection_codes: list[RealtimeExecutionErrorCode] = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                try:
                    session.run_turn_blocking(input_text="reentrant blocking")
                except RealtimeExecutionError as error:
                    rejection_codes.append(error.code)

        session.on_event(callback)
        try:
            result = session.run_turn_blocking(input_text="outer blocking")
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(
                rejection_codes,
                [RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD],
            )
        finally:
            session.close()

    def test_runtime_callback_legacy_reentrancy_is_typed_rejection(self) -> None:
        session = framework.create_realtime_session()
        rejection_codes: list[RealtimeExecutionErrorCode] = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                try:
                    session.run_turn(input_text="reentrant legacy")
                except RealtimeExecutionError as error:
                    rejection_codes.append(error.code)

        session.on_event(callback)
        try:
            result = session.run_turn_blocking(input_text="outer legacy guard")
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(
                rejection_codes,
                [RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD],
            )
        finally:
            session.close()

    def test_runtime_callback_cancel_is_reentrant_and_deadlock_free(self) -> None:
        session = framework.create_realtime_session()
        callback_threads: list[int] = []
        outcomes: list[str] = []

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                callback_threads.append(threading.get_ident())
                outcomes.append(session.cancel_current_turn().outcome.value)

        session.on_event(callback)
        try:
            result = session.run_turn_blocking(input_text="cancel callback")
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(callback_threads, [session._execution_bridge.thread_identity])
            self.assertEqual(outcomes, ["not_implemented"])
            self.assertIsNone(session._active_turn_context)
        finally:
            session.close()

    def test_runtime_callback_close_is_deferred_and_stops_bridge(self) -> None:
        session = framework.create_realtime_session()
        callback_observations: list[tuple[bool, bool, bool]] = []
        shutdown_operation_depths: list[int] = []
        original_shutdown = session._execution_bridge.shutdown

        def checked_shutdown(*, timeout_seconds: float = 2.0) -> None:
            shutdown_operation_depths.append(session._operation_depth)
            original_shutdown(timeout_seconds=timeout_seconds)

        session._execution_bridge.shutdown = checked_shutdown  # type: ignore[method-assign]

        def callback(event) -> None:
            if event.type is RealtimeEventType.LISTENING_STARTED:
                session.close()
                callback_observations.append(
                    (
                        session._closed,
                        session._close_requested,
                        session._execution_bridge.closed,
                    )
                )

        session.on_event(callback)
        result = session.run_turn_blocking(input_text="close callback")
        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertEqual(callback_observations, [(False, True, False)])
        self.assertTrue(session._closed)
        self.assertIs(session.state, RealtimeState.CLOSED)
        self.assertTrue(session._execution_bridge.closed)
        self.assertEqual(shutdown_operation_depths, [0])
        self.assertTrue(session._execution_bridge.wait_stopped(timeout_seconds=2.0))
        self.assertFalse(session._execution_bridge.thread_alive)
        self.assertIsNone(session._execution_bridge.loop_identity)

    def test_close_after_completed_turn_stops_started_bridge(self) -> None:
        session = framework.create_realtime_session()
        result = session.run_turn_blocking(input_text="close after turn")
        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertTrue(session._execution_bridge.thread_alive)

        session.close()

        self.assertTrue(session._closed)
        self.assertTrue(session._execution_bridge.closed)
        self.assertFalse(session._execution_bridge.thread_alive)
        self.assertTrue(session._execution_bridge.stopped)

    def test_close_before_execution_is_idempotent_and_does_not_start_bridge(self) -> None:
        session = framework.create_realtime_session()
        self.assertFalse(session._execution_bridge.started)

        session.close()
        session.close()

        self.assertTrue(session._closed)
        self.assertTrue(session._execution_bridge.closed)
        self.assertFalse(session._execution_bridge.started)
        self.assertFalse(session._execution_bridge.thread_alive)
        self.assertTrue(session._execution_bridge.stopped)

    def test_bridge_shutdown_from_runtime_thread_never_self_joins(self) -> None:
        bridge = _RealtimeExecutionBridge()

        async def shutdown_from_runtime() -> tuple[int, bool]:
            runtime_thread = threading.get_ident()
            bridge.shutdown()
            return runtime_thread, bridge.closed

        runtime_thread, closed = bridge.run(shutdown_from_runtime())
        self.assertTrue(closed)
        self.assertEqual(runtime_thread, bridge.thread_identity)
        self.assertTrue(bridge.wait_stopped(timeout_seconds=2.0))
        self.assertFalse(bridge.thread_alive)
        self.assertIsNone(bridge.loop_identity)


if __name__ == "__main__":
    unittest.main()
