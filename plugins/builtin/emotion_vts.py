from __future__ import annotations

from typing import Any

from plugins.base import BasePlugin
from core.emotion import resolve_emotion_hotkey


class EmotionVTSPlugin(BasePlugin):
    name: str = "emotion_vts"
    enabled: bool = True

    def __init__(self) -> None:
        self.runtime: dict[str, Any] | None = None

    def setup(self, runtime: dict[str, Any]) -> None:
        self.runtime = runtime
        hooks = runtime.setdefault("hooks", {})
        hooks.setdefault("on_emotion_detected", []).append(self.on_emotion_detected)

    async def on_emotion_detected(self, emotion: str) -> None:
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