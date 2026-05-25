from __future__ import annotations

from plugins.base import BasePlugin


class SimpleGreetingPlugin(BasePlugin):
    """
    Minimal sample plugin for plugin authors.

    This sample demonstrates:
    - subclassing BasePlugin
    - registering a hook in setup()
    - reacting to a runtime event with a small handler

    It is intentionally simple so new plugin authors can copy it
    as a starting point.
    """

    name: str = "simple_greeting"
    enabled: bool = True

    def setup(self, runtime: dict) -> None:
        """
        Register plugin hooks during setup().
        """
        self.add_hook(runtime, "on_user_input", self.on_user_input)

    def on_user_input(self, text: str) -> None:
        """
        Handle the user input event.

        This sample only prints a lightweight message so authors can
        see when the hook fires.
        """
        print(f"[SamplePlugin:{self.name}] received_input={text!r}")