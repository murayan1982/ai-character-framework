"""Provider-neutral public execution model for v6 realtime orchestration.

This module contains only public-safe execution classifications. It must not
import provider SDKs, network transports, microphone/audio runtime code, VTS,
or application-specific modules.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class RealtimeExecutionErrorCode(str, Enum):
    """Stable public classification for realtime execution-boundary failures."""

    BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP = "blocking_call_in_active_event_loop"
    BLOCKING_CALL_FROM_RUNTIME_THREAD = "blocking_call_from_runtime_thread"


_SAFE_MESSAGES = MappingProxyType(
    {
        RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP: (
            "A blocking realtime turn call cannot run on an active event-loop thread."
        ),
        RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD: (
            "A blocking realtime turn call cannot run from the realtime runtime thread."
        ),
    }
)


class RealtimeExecutionError(RuntimeError):
    """Public-safe typed realtime execution-boundary failure."""

    def __init__(self, code: RealtimeExecutionErrorCode | str) -> None:
        resolved_code = (
            code
            if isinstance(code, RealtimeExecutionErrorCode)
            else RealtimeExecutionErrorCode(str(code))
        )
        safe_message = _SAFE_MESSAGES[resolved_code]
        self.code = resolved_code
        self.safe_message = safe_message
        super().__init__(safe_message)
