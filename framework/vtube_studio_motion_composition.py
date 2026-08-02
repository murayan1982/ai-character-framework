"""Internal root-public MotionSession to VTube Studio composition.

FW-VTS-0e owns the synchronous/public to asynchronous/internal boundary for the
VTube Studio motion adapter.  The module is imported lazily by MotionSession
only after explicit configuration guards pass.  It does not read environment
variables or files, bootstrap tokens, retry, reconnect, or import the actual
``pyvts`` package during normal module import.

These symbols are internal and are intentionally not exported from the
``framework`` root.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine, Mapping
from dataclasses import dataclass, field
from typing import Any

from .motion import MotionIntent, MotionRequest
from .motion_adapter_execution import MotionAdapterExecutionConfig
from .vtube_studio_pyvts_transport import (
    VTubeStudioPyvtsTransport,
    VTubeStudioPyvtsTransportConfig,
)
from .vtube_studio_transport import (
    VTubeStudioHotkeyRequest,
    VTubeStudioTransport,
    VTubeStudioTransportOperation,
    VTubeStudioTransportOutcome,
    VTubeStudioTransportResult,
)


_BRIDGE_TIMEOUT_MARGIN_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class VTubeStudioMotionResolution:
    """Internal request-to-hotkey resolution without public hotkey exposure."""

    request: VTubeStudioHotkeyRequest | None = field(
        default=None,
        repr=False,
    )
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.request is not None


class _PersistentAsyncBridge:
    """One lifecycle-owned worker thread and persistent asyncio event loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False

    @property
    def started(self) -> bool:
        with self._lock:
            return self._thread is not None

    @property
    def thread_alive(self) -> bool:
        with self._lock:
            thread = self._thread
        return bool(thread is not None and thread.is_alive())

    @property
    def loop_identity(self) -> int | None:
        with self._lock:
            loop = self._loop
        return id(loop) if loop is not None else None

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
            asyncio.set_event_loop(None)
            loop.close()
            with self._lock:
                self._loop = None

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("VTube Studio async bridge is closed")
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._thread_main,
                    name="framework-vts-motion-bridge",
                    daemon=True,
                )
                self._thread.start()
        if not self._ready.wait(timeout=2.0):
            raise RuntimeError("VTube Studio async bridge did not start")
        with self._lock:
            if self._closed or self._loop is None:
                raise RuntimeError("VTube Studio async bridge is closed")

    def submit(
        self,
        coroutine: Coroutine[Any, Any, VTubeStudioTransportResult],
        *,
        timeout_seconds: float,
    ) -> VTubeStudioTransportResult:
        self.start()
        with self._lock:
            if self._closed or self._loop is None:
                coroutine.close()
                raise RuntimeError("VTube Studio async bridge is closed")
            loop = self._loop

        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise

    async def _cancel_pending(self) -> None:
        current = asyncio.current_task()
        pending = tuple(
            task
            for task in asyncio.all_tasks()
            if task is not current and not task.done()
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    def shutdown(self, *, timeout_seconds: float) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            thread = self._thread

        if thread is None:
            return

        self._ready.wait(timeout=timeout_seconds)
        with self._lock:
            loop = self._loop

        if loop is not None and loop.is_running():
            cleanup = asyncio.run_coroutine_threadsafe(
                self._cancel_pending(),
                loop,
            )
            try:
                cleanup.result(timeout=timeout_seconds)
            except (
                concurrent.futures.TimeoutError,
                concurrent.futures.CancelledError,
                RuntimeError,
            ):
                cleanup.cancel()
            finally:
                try:
                    loop.call_soon_threadsafe(loop.stop)
                except RuntimeError:
                    pass
        thread.join(timeout=timeout_seconds)


class VTubeStudioMotionComposition:
    """Internal VTube Studio session composition and lifecycle owner."""

    def __init__(
        self,
        *,
        execution_config: MotionAdapterExecutionConfig,
        endpoint_host: str,
        endpoint_port: int,
        authentication_token: str,
        hotkey_bindings: Mapping[str, str],
        connect_timeout_seconds: float,
        authenticate_timeout_seconds: float,
        request_timeout_seconds: float,
        close_timeout_seconds: float,
    ) -> None:
        self._hotkey_bindings = dict(hotkey_bindings)
        self._request_timeout_seconds = float(request_timeout_seconds)
        self._close_timeout_seconds = float(close_timeout_seconds)
        self._preflight_timeout_seconds = (
            float(connect_timeout_seconds)
            + float(authenticate_timeout_seconds)
            + float(request_timeout_seconds)
            + _BRIDGE_TIMEOUT_MARGIN_SECONDS
        )
        self._bridge = _PersistentAsyncBridge()
        self._transport: VTubeStudioTransport = VTubeStudioPyvtsTransport(
            config=VTubeStudioPyvtsTransportConfig(
                execution_config=execution_config,
                endpoint_host=endpoint_host,
                endpoint_port=endpoint_port,
                authentication_token=authentication_token,
                connect_timeout_seconds=connect_timeout_seconds,
                authenticate_timeout_seconds=authenticate_timeout_seconds,
                request_timeout_seconds=request_timeout_seconds,
                close_timeout_seconds=close_timeout_seconds,
            )
        )
        self._closed = False

    @property
    def bridge_started(self) -> bool:
        return self._bridge.started

    @property
    def bridge_thread_alive(self) -> bool:
        return self._bridge.thread_alive

    @property
    def bridge_loop_identity(self) -> int | None:
        return self._bridge.loop_identity

    @property
    def transport(self) -> VTubeStudioTransport:
        """Internal test/readiness access; never exported from framework root."""

        return self._transport

    def _bridge_timeout_result(
        self,
        *,
        operation: VTubeStudioTransportOperation,
        request_id: str | None = None,
    ) -> VTubeStudioTransportResult:
        return VTubeStudioTransportResult(
            operation=operation,
            outcome=VTubeStudioTransportOutcome.TIMED_OUT,
            request_id=request_id,
            safe_message="The VTube Studio session bridge timed out.",
            retryable=True,
            public_metadata={
                "boundary": "vts_motion_composition",
                "reason": "session_bridge_timed_out",
                "timeout_stage": "session_bridge",
                "worker_thread_started": self._bridge.started,
                "persistent_event_loop": True,
                "raw_payload_exposed": False,
                "raw_exception_exposed": False,
                "endpoint_exposed": False,
                "authentication_material_exposed": False,
                "model_identity_exposed": False,
                "hotkey_name_exposed": False,
                "hotkey_identifier_exposed": False,
                "real_hotkey_triggered": False,
                "real_motion_executed": False,
            },
        )

    def preflight(self) -> VTubeStudioTransportResult:
        try:
            return self._bridge.submit(
                self._transport.preflight(),
                timeout_seconds=self._preflight_timeout_seconds,
            )
        except concurrent.futures.TimeoutError:
            return self._bridge_timeout_result(
                operation=VTubeStudioTransportOperation.PREFLIGHT,
            )
        except (concurrent.futures.CancelledError, RuntimeError):
            outcome = (
                VTubeStudioTransportOutcome.CLOSED
                if self._closed
                else VTubeStudioTransportOutcome.FAILED
            )
            return VTubeStudioTransportResult(
                operation=VTubeStudioTransportOperation.PREFLIGHT,
                outcome=outcome,
                safe_message=(
                    "The VTube Studio motion composition is closed."
                    if self._closed
                    else "The VTube Studio session bridge failed."
                ),
                public_metadata={
                    "boundary": "vts_motion_composition",
                    "reason": (
                        "composition_closed"
                        if self._closed
                        else "session_bridge_failed"
                    ),
                    "raw_exception_exposed": False,
                    "real_motion_executed": False,
                },
            )

    def resolve_request(
        self,
        request: MotionRequest,
    ) -> VTubeStudioMotionResolution:
        intent = request.intent
        selector: str | None = None

        if intent is MotionIntent.EXPRESSION:
            value = str(request.expression or "").strip().casefold()
            selector = f"expression:{value}" if value else None
        elif intent is MotionIntent.EMOTION:
            value = str(request.emotion or "").strip().casefold()
            selector = f"emotion:{value}" if value else None
        elif intent is MotionIntent.GESTURE:
            value = str(request.gesture or "").strip().casefold()
            selector = f"gesture:{value}" if value else None
        elif intent is MotionIntent.STOP_MOTION:
            selector = "stop_motion"
        elif intent is MotionIntent.RESET_EXPRESSION:
            selector = "reset_expression"
        else:
            return VTubeStudioMotionResolution(reason="unsupported_intent")

        if selector is None:
            return VTubeStudioMotionResolution(reason="intent_value_missing")

        hotkey_name = self._hotkey_bindings.get(selector)
        if hotkey_name is None:
            return VTubeStudioMotionResolution(reason="hotkey_binding_missing")

        return VTubeStudioMotionResolution(
            request=VTubeStudioHotkeyRequest(
                intent=intent,
                hotkey_name=hotkey_name,
                request_id=request.request_id,
                public_metadata={
                    "boundary": "vts_motion_composition",
                    "intent": intent.value,
                },
            ),
            reason="hotkey_binding_resolved",
        )

    def trigger(
        self,
        resolved_request: VTubeStudioHotkeyRequest,
    ) -> VTubeStudioTransportResult:
        try:
            return self._bridge.submit(
                self._transport.trigger_hotkey(resolved_request),
                timeout_seconds=(
                    self._request_timeout_seconds
                    + _BRIDGE_TIMEOUT_MARGIN_SECONDS
                ),
            )
        except concurrent.futures.TimeoutError:
            return self._bridge_timeout_result(
                operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
                request_id=resolved_request.request_id,
            )
        except (concurrent.futures.CancelledError, RuntimeError):
            outcome = (
                VTubeStudioTransportOutcome.CLOSED
                if self._closed
                else VTubeStudioTransportOutcome.FAILED
            )
            return VTubeStudioTransportResult(
                operation=VTubeStudioTransportOperation.TRIGGER_HOTKEY,
                outcome=outcome,
                request_id=resolved_request.request_id,
                safe_message=(
                    "The VTube Studio motion composition is closed."
                    if self._closed
                    else "The VTube Studio session bridge failed."
                ),
                retryable=not self._closed,
                public_metadata={
                    "boundary": "vts_motion_composition",
                    "reason": (
                        "composition_closed"
                        if self._closed
                        else "session_bridge_failed"
                    ),
                    "late_completion_suppressed": self._closed,
                    "raw_exception_exposed": False,
                    "real_motion_executed": False,
                },
            )

    def close(self) -> VTubeStudioTransportResult:
        if self._closed:
            return VTubeStudioTransportResult(
                operation=VTubeStudioTransportOperation.CLOSE,
                outcome=VTubeStudioTransportOutcome.COMPLETED,
                safe_message="The VTube Studio motion composition is closed.",
                public_metadata={
                    "boundary": "vts_motion_composition",
                    "reason": "already_closed",
                    "already_closed": True,
                    "worker_thread_terminated": (
                        not self._bridge.thread_alive
                    ),
                    "real_motion_executed": False,
                },
            )

        self._closed = True
        if not self._bridge.started:
            result = VTubeStudioTransportResult(
                operation=VTubeStudioTransportOperation.CLOSE,
                outcome=VTubeStudioTransportOutcome.COMPLETED,
                safe_message="The VTube Studio motion composition is closed.",
                public_metadata={
                    "boundary": "vts_motion_composition",
                    "reason": "closed_before_bridge_start",
                    "worker_thread_started": False,
                    "real_motion_executed": False,
                },
            )
        else:
            try:
                result = self._bridge.submit(
                    self._transport.close(),
                    timeout_seconds=(
                        self._close_timeout_seconds
                        + _BRIDGE_TIMEOUT_MARGIN_SECONDS
                    ),
                )
            except concurrent.futures.TimeoutError:
                result = self._bridge_timeout_result(
                    operation=VTubeStudioTransportOperation.CLOSE,
                )
            except (concurrent.futures.CancelledError, RuntimeError):
                result = VTubeStudioTransportResult(
                    operation=VTubeStudioTransportOperation.CLOSE,
                    outcome=VTubeStudioTransportOutcome.CLOSED,
                    safe_message=(
                        "The VTube Studio motion composition is closed."
                    ),
                    public_metadata={
                        "boundary": "vts_motion_composition",
                        "reason": "composition_closed",
                        "raw_exception_exposed": False,
                        "real_motion_executed": False,
                    },
                )

        self._bridge.shutdown(
            timeout_seconds=(
                self._close_timeout_seconds
                + _BRIDGE_TIMEOUT_MARGIN_SECONDS
            )
        )
        return result


def create_vtube_studio_motion_composition(
    *,
    execution_config: MotionAdapterExecutionConfig,
    endpoint_host: str,
    endpoint_port: int,
    authentication_token: str,
    hotkey_bindings: Mapping[str, str],
    connect_timeout_seconds: float,
    authenticate_timeout_seconds: float,
    request_timeout_seconds: float,
    close_timeout_seconds: float,
) -> VTubeStudioMotionComposition:
    """Create the internal composition without exporting it publicly."""

    return VTubeStudioMotionComposition(
        execution_config=execution_config,
        endpoint_host=endpoint_host,
        endpoint_port=endpoint_port,
        authentication_token=authentication_token,
        hotkey_bindings=hotkey_bindings,
        connect_timeout_seconds=connect_timeout_seconds,
        authenticate_timeout_seconds=authenticate_timeout_seconds,
        request_timeout_seconds=request_timeout_seconds,
        close_timeout_seconds=close_timeout_seconds,
    )
