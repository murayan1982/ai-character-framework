"""Internal persistent asyncio bridge for v6 realtime orchestration.

The bridge owns one lazy worker thread and one persistent asyncio event loop.
It is intentionally not exported from the framework root. RealtimeSession
adoption and public blocking/async execution guards are owned by later
FW-RT6-4c controls.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar


_T = TypeVar("_T")


class _RealtimeExecutionBridge:
    """Lifecycle-owned worker thread and persistent asyncio event loop."""

    def __init__(
        self,
        *,
        thread_name: str = "framework-realtime-runtime",
        start_timeout_seconds: float = 2.0,
    ) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False
        self._thread_name = str(thread_name)
        self._start_timeout_seconds = float(start_timeout_seconds)

    @property
    def started(self) -> bool:
        with self._lock:
            return self._thread is not None

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def thread_alive(self) -> bool:
        with self._lock:
            thread = self._thread
        return bool(thread is not None and thread.is_alive())

    @property
    def stopped(self) -> bool:
        return self._stopped.is_set()

    @property
    def loop_identity(self) -> int | None:
        with self._lock:
            loop = self._loop
        return id(loop) if loop is not None else None

    @property
    def thread_identity(self) -> int | None:
        with self._lock:
            thread = self._thread
        return thread.ident if thread is not None else None

    def is_runtime_thread(self) -> bool:
        runtime_thread_id = self.thread_identity
        return (
            runtime_thread_id is not None
            and runtime_thread_id == threading.get_ident()
        )

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
            closed_before_start = self._closed
        self._ready.set()

        try:
            if not closed_before_start:
                loop.run_forever()
        finally:
            pending = tuple(
                task
                for task in asyncio.all_tasks(loop)
                if not task.done()
            )
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            asyncio.set_event_loop(None)
            loop.close()
            with self._lock:
                self._loop = None
            self._stopped.set()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Realtime execution bridge is closed")
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._thread_main,
                    name=self._thread_name,
                    daemon=True,
                )
                self._thread.start()

        if not self._ready.wait(timeout=self._start_timeout_seconds):
            raise RuntimeError("Realtime execution bridge did not start")

        with self._lock:
            if self._closed or self._loop is None:
                raise RuntimeError("Realtime execution bridge is closed")

    def submit(
        self,
        coroutine: Coroutine[Any, Any, _T],
    ) -> concurrent.futures.Future[_T]:
        self.start()
        with self._lock:
            if self._closed or self._loop is None:
                coroutine.close()
                raise RuntimeError("Realtime execution bridge is closed")
            loop = self._loop

        try:
            return asyncio.run_coroutine_threadsafe(coroutine, loop)
        except BaseException:
            coroutine.close()
            raise

    def run(
        self,
        coroutine: Coroutine[Any, Any, _T],
        *,
        timeout_seconds: float | None = None,
    ) -> _T:
        future = self.submit(coroutine)
        return future.result(timeout=timeout_seconds)

    def wait_stopped(self, *, timeout_seconds: float = 2.0) -> bool:
        """Wait for a started runtime thread to terminate without creating one."""

        with self._lock:
            thread = self._thread
        if thread is None:
            return True
        if thread.ident == threading.get_ident():
            return not thread.is_alive()
        return self._stopped.wait(timeout=timeout_seconds)

    def shutdown(self, *, timeout_seconds: float = 2.0) -> bool:
        """Request shutdown and truthfully report whether the worker stopped."""

        with self._lock:
            already_closed = self._closed
            self._closed = True
            thread = self._thread
            loop = self._loop

        if thread is None:
            self._stopped.set()
            return True

        if not already_closed and loop is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass

        if thread.ident == threading.get_ident():
            return not thread.is_alive()

        thread.join(timeout=timeout_seconds)
        return not thread.is_alive()
