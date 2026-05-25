from __future__ import annotations

from plugins.base import BasePlugin


class ResponseLengthLoggerPlugin(BasePlugin):
    """
    Built-in reference plugin that logs the final response length.

    This plugin is intentionally simple:
    - it registers one hook in setup()
    - it reacts to one runtime event
    - it uses no external services

    Use this as a minimal example when authoring new plugins.
    """

    name: str = "response_length_logger"
    enabled: bool = True

    def setup(self, runtime: dict) -> None:
        self.add_hook(runtime, "on_llm_complete", self.on_llm_complete)

    async def on_llm_complete(self, text: str) -> None:
        print(f"[Plugin:{self.name}] response_length={len(text)}")