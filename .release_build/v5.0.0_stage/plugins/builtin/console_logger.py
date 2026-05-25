from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin
from core.events import EVENT_STATE_CHANGE

"""
Built-in reference plugin for lifecycle and console logging.

This plugin demonstrates:
- lifecycle usage (setup / on_start / on_stop)
- light runtime inspection
- simple runtime event hook logging
"""
class ConsoleLoggerPlugin(BasePlugin):
    """
    Minimal built-in lifecycle plugin.

    This plugin is intentionally simple and acts as a small example of
    setup/on_start/on_stop behavior with a small state-change event hook.
    """

    name: str = "console_logger"
    enabled: bool = True

    def setup(self, runtime: dict[str, Any]) -> None:
        config = runtime.get("config")
        preset = getattr(config, "app_preset", "unknown") if config else "unknown"
        self.add_hook(runtime, EVENT_STATE_CHANGE, self.on_state_change)

        print(f"[Plugin:{self.name}] setup complete")
        print(f"[Plugin:{self.name}] preset={preset}")

    def on_start(self, runtime: dict[str, Any]) -> None:
        print(f"[Plugin:{self.name}] runtime started")

    def on_stop(self, runtime: dict[str, Any]) -> None:
        print(f"[Plugin:{self.name}] runtime stopped")

    def on_state_change(self, old_state: Any, new_state: Any) -> None:
        """Log state transitions without mutating runtime state."""
        old_value = getattr(old_state, "value", str(old_state))
        new_value = getattr(new_state, "value", str(new_state))
        print(f"[Plugin:{self.name}] state={old_value} -> {new_value}")