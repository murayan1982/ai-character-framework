from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    """
    Base class for all plugins.

    Plugins can hook into runtime lifecycle events.
    """

    name: str = "base_plugin"
    enabled: bool = True

    def setup(self, runtime: dict[str, Any]) -> None:
        """
        Called once when the plugin is registered or initialized.

        Override this method if the plugin needs access to runtime resources.
        """
        pass

    def on_start(self, runtime: dict[str, Any]) -> None:
        """
        Called when the application/runtime starts.
        """
        pass

    def on_stop(self, runtime: dict[str, Any]) -> None:
        """
        Called when the application/runtime stops.
        """
        pass