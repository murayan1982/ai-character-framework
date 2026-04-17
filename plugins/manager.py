from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin


class PluginManager:
    """
    Minimal plugin manager.

    Responsible for registering plugins and calling lifecycle hooks.
    """

    def __init__(self) -> None:
        self._plugins: list[BasePlugin] = []

    @property
    def plugins(self) -> list[BasePlugin]:
        return self._plugins

    def register(self, plugin: BasePlugin, runtime: dict[str, Any] | None = None) -> None:
        """
        Register a plugin.

        If runtime is provided, plugin.setup(runtime) is called immediately.
        """
        if not plugin.enabled:
            return

        self._plugins.append(plugin)

        if runtime is not None:
            plugin.setup(runtime)

    def setup_all(self, runtime: dict[str, Any]) -> None:
        for plugin in self._plugins:
            if plugin.enabled:
                plugin.setup(runtime)

    def on_start(self, runtime: dict[str, Any]) -> None:
        for plugin in self._plugins:
            if plugin.enabled:
                plugin.on_start(runtime)

    def on_stop(self, runtime: dict[str, Any]) -> None:
        for plugin in self._plugins:
            if plugin.enabled:
                plugin.on_stop(runtime)