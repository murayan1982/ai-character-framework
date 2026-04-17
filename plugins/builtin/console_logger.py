from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin


class ConsoleLoggerPlugin(BasePlugin):
    """
    Built-in plugin that logs runtime lifecycle events to the console.
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