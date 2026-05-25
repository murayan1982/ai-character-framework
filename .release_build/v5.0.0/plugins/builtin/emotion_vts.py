from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin
from core.emotion import resolve_emotion_hotkey


class EmotionVTSPlugin(BasePlugin):
    """
    Built-in plugin that bridges detected emotion events to VTS hotkey actions.

    This plugin does not generate emotion labels itself.
    It listens to the runtime emotion event, resolves the configured
    character-level hotkey mapping, and triggers VTS if available.
    """

    name: str = "emotion_vts"
    enabled: bool = True

    def __init__(self) -> None:
        self.runtime: dict[str, Any] | None = None

    def setup(self, runtime: dict[str, Any]) -> None:
        """
        Register the plugin hook during setup().

        Hook registration belongs in setup() so the plugin is fully wired
        before the runtime session starts.
        """
        self.runtime = runtime
        self.add_hook(runtime, "on_emotion_detected", self.on_emotion_detected)

    async def on_emotion_detected(self, emotion: str) -> None:
        """
        Resolve a detected emotion into a character-specific VTS hotkey
        and trigger it when the runtime is configured to do so.
        """
        if self.runtime is None:
            return

        config = self.runtime.get("config")
        vts = self.runtime.get("vts")

        if config is None:
            return
        if not getattr(config, "emotion_enabled", False):
            return
        if not getattr(config, "vts_emotion_enabled", False):
            return
        if vts is None:
            return

        hotkey_name = resolve_emotion_hotkey(
            emotion,
            getattr(config, "vts_hotkeys", None),
        )
        if not hotkey_name:
            return

        await vts.trigger_hotkey(hotkey_name)