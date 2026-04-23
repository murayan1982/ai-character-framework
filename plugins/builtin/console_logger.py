from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin

"""
Built-in reference plugin for lifecycle and console logging.

This plugin demonstrates:
- lifecycle usage (setup / on_start / on_stop)
- light runtime inspection
- simple non-hook plugin behavior
"""
class ConsoleLoggerPlugin(BasePlugin):
    """
    Minimal built-in lifecycle plugin.

    This plugin is intentionally simple and acts as a small example of
    setup/on_start/on_stop behavior without event-hook registration.
    """

    name: str = "console_logger"
    enabled: bool = True

    def setup(self, runtime: dict[str, Any]) -> None:
        config = runtime.get("config")
        preset = getattr(config, "app_preset", "unknown") if config else "unknown"

        print(f"[Plugin:{self.name}] setup complete")
        print(f"[Plugin:{self.name}] preset={preset}")

    def on_start(self, runtime: dict[str, Any]) -> None:
        print(f"[Plugin:{self.name}] runtime started")

    def on_stop(self, runtime: dict[str, Any]) -> None:
        print(f"[Plugin:{self.name}] runtime stopped")