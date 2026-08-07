from __future__ import annotations

import asyncio
import threading
import unittest

from framework.realtime_execution_bridge import _RealtimeExecutionBridge


async def _runtime_identity() -> tuple[int, int]:
    return id(asyncio.get_running_loop()), threading.get_ident()


async def _value(value: str) -> str:
    await asyncio.sleep(0)
    return value


class RealtimeExecutionBridgeTests(unittest.TestCase):
    def test_bridge_is_lazy_before_first_execution(self) -> None:
        bridge = _RealtimeExecutionBridge()
        self.assertFalse(bridge.started)
        self.assertFalse(bridge.thread_alive)
        self.assertIsNone(bridge.loop_identity)
        bridge.shutdown()

    def test_first_run_starts_one_runtime_thread_and_loop(self) -> None:
        bridge = _RealtimeExecutionBridge()
        try:
            loop_id, thread_id = bridge.run(_runtime_identity())
            self.assertTrue(bridge.started)
            self.assertTrue(bridge.thread_alive)
            self.assertEqual(bridge.loop_identity, loop_id)
            self.assertEqual(bridge.thread_identity, thread_id)
        finally:
            bridge.shutdown()

    def test_subsequent_runs_reuse_same_loop_and_thread(self) -> None:
        bridge = _RealtimeExecutionBridge()
        try:
            first = bridge.run(_runtime_identity())
            second = bridge.run(_runtime_identity())
            self.assertEqual(first, second)
            self.assertEqual(bridge.loop_identity, first[0])
            self.assertEqual(bridge.thread_identity, first[1])
        finally:
            bridge.shutdown()

    def test_submit_returns_future_without_new_loop_per_call(self) -> None:
        bridge = _RealtimeExecutionBridge()
        try:
            first = bridge.submit(_runtime_identity()).result(timeout=2.0)
            second = bridge.submit(_runtime_identity()).result(timeout=2.0)
            self.assertEqual(first, second)
        finally:
            bridge.shutdown()

    def test_coroutine_executes_on_runtime_thread_not_caller(self) -> None:
        bridge = _RealtimeExecutionBridge()
        caller_thread = threading.get_ident()
        try:
            _, runtime_thread = bridge.run(_runtime_identity())
            self.assertNotEqual(runtime_thread, caller_thread)
            self.assertEqual(runtime_thread, bridge.thread_identity)
        finally:
            bridge.shutdown()

    def test_shutdown_is_idempotent_and_stops_runtime(self) -> None:
        bridge = _RealtimeExecutionBridge()
        bridge.run(_value("ok"))
        bridge.shutdown()
        bridge.shutdown()
        self.assertTrue(bridge.closed)
        self.assertFalse(bridge.thread_alive)

    def test_shutdown_before_start_does_not_create_runtime(self) -> None:
        bridge = _RealtimeExecutionBridge()
        bridge.shutdown()
        self.assertTrue(bridge.closed)
        self.assertFalse(bridge.started)
        self.assertFalse(bridge.thread_alive)

    def test_execution_after_shutdown_is_rejected(self) -> None:
        bridge = _RealtimeExecutionBridge()
        bridge.shutdown()
        coroutine = _value("blocked")
        try:
            with self.assertRaisesRegex(RuntimeError, "bridge is closed"):
                bridge.run(coroutine)
        finally:
            coroutine.close()


if __name__ == "__main__":
    unittest.main()
