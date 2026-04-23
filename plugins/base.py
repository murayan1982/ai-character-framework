from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from typing import Any


Runtime = dict[str, Any]
HookHandler = Callable[..., Any]


class BasePlugin(ABC):
    """
    Base class for runtime plugins.

    Plugins extend the framework in two main ways:

    1. Lifecycle methods
       - setup(runtime)
       - on_start(runtime)
       - on_stop(runtime)

    2. Event hooks
       - Hooks are registered through runtime["hooks"]
       - Hook registration should happen in setup()

    Lifecycle contract:
    - setup(runtime):
        Called once after the runtime dictionary has been assembled.
        Use this to inspect runtime resources and register event hooks.
    - on_start(runtime):
        Called after plugin setup has completed and just before the
        main session loop begins.
    - on_stop(runtime):
        Called when the application/runtime is shutting down.

    Runtime contract:
    Plugins may read from the shared runtime dictionary, but should treat it
    as framework-owned state. In the current framework, plugins may expect
    these keys to exist once runtime initialization is complete:

    - "config"
    - "hooks"
    - "plugin_manager"
    - "llm"
    - "vts"
    - "stt"
    - "tts"
    - "use_stt"
    - "use_tts"
    - "log_file"

    Plugin design guidance:
    - Register hooks in setup(), not in on_start()
    - Keep plugin responsibilities small and extension-oriented
    - Prefer observing runtime events over owning core app flow
    - Avoid mutating unrelated runtime state
    - Use on_start()/on_stop() for lifecycle-side effects, not hook wiring
    """

    name: str = "base_plugin"
    enabled: bool = True

    def setup(self, runtime: Runtime) -> None:
        """
        Called once when the plugin is registered or initialized.

        This is the preferred place to:
        - inspect runtime resources
        - store references needed by the plugin
        - register event hooks through runtime["hooks"]
        """
        pass

    def on_start(self, runtime: Runtime) -> None:
        """
        Called after all plugin setup has completed and before the
        interactive session loop starts.
        """
        pass

    def on_stop(self, runtime: Runtime) -> None:
        """
        Called when the runtime is shutting down.

        Plugins can use this hook for cleanup that belongs to the plugin
        itself, as long as the plugin does not assume ownership of
        framework-managed resources.
        """
        pass

    def add_hook(
        self,
        runtime: Runtime,
        event_name: str,
        handler: HookHandler,
    ) -> None:
        """
        Register a handler to a runtime event hook list.

        This helper keeps hook registration style consistent across plugins.
        """
        hooks = runtime.setdefault("hooks", {})
        hooks.setdefault(event_name, []).append(handler)