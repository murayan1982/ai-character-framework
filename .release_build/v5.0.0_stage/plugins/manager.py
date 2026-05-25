from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin


class PluginManager:
    """
    Minimal plugin manager.

    Responsible for:
    - registering plugins
    - running plugin lifecycle methods in a consistent order

    Event-hook dispatch is handled separately through runtime["hooks"]
    and emit(), not by this manager directly.
    """

    def __init__(self) -> None:
        self._plugins: list[BasePlugin] = []

    @property
    def plugins(self) -> list[BasePlugin]:
        return self._plugins

    def register(self, plugin: BasePlugin) -> None:
        """
        Register a plugin instance.

        Registration only stores the plugin.
        Lifecycle execution is handled separately through:
        - setup_all(runtime)
        - on_start(runtime)
        - on_stop(runtime)
        """
        if not plugin.enabled:
            return

        self._plugins.append(plugin)

    def setup_all(self, runtime: dict[str, Any]) -> None:
        """
        Run setup() for all registered plugins.
        """
        for plugin in self._plugins:
            if plugin.enabled:
                plugin.setup(runtime)

    def on_start(self, runtime: dict[str, Any]) -> None:
        """
        Run on_start() for all registered plugins.
        """
        for plugin in self._plugins:
            if plugin.enabled:
                plugin.on_start(runtime)

    def on_stop(self, runtime: dict[str, Any]) -> None:
        """
        Run on_stop() for all registered plugins.
        """
        for plugin in self._plugins:
            if plugin.enabled:
                plugin.on_stop(runtime)