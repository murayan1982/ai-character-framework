# Plugin Guide

This framework supports lightweight runtime plugins for extension and customization.

Plugins are intended to be small, focused units that react to runtime lifecycle events or hook-based events.

---

## Plugin Lifecycle

Plugins follow this lifecycle:

- `setup(runtime)`
- `on_start(runtime)`
- `on_stop(runtime)`

### `setup(runtime)`

`setup()` is called after the runtime dictionary has been assembled.

Use `setup()` to:

- inspect runtime resources
- keep small references if needed
- register hook handlers

Hook registration should be done in `setup()`.

### `on_start(runtime)`

`on_start()` is called after all registered plugins have completed setup.

Use it for lightweight startup-side behavior that belongs to the plugin itself.

### `on_stop(runtime)`

`on_stop()` is called when the runtime is shutting down.

Use it for plugin-local cleanup only.

Plugins should not assume ownership of framework-managed resources.

---

## Runtime Relationship

Plugins receive the shared `runtime` dictionary.

Plugins may read from runtime, but should treat it as framework-owned shared state.

Typical runtime keys include:

- `"config"`
- `"hooks"`
- `"plugin_manager"`
- `"llm"`
- `"vts"`
- `"stt"`
- `"tts"`
- `"use_stt"`
- `"use_tts"`
- `"log_file"`

Plugins should avoid mutating unrelated runtime state.

---

## Hook / Event Model

The framework emits runtime events, and plugins can subscribe to those events through `runtime["hooks"]`.

Supported events are defined in `core/events.py`.

Current plugin-facing events are:

- `on_user_input`
- `on_llm_chunk`
- `on_llm_complete`
- `on_emotion_detected`
- `on_error`

The recommended pattern is:

1. register hook handlers in `setup()`
2. keep handlers small and focused
3. react to events instead of owning the main application flow

---

## Minimal Plugin Pattern

A minimal plugin usually looks like this:

```python
from plugins.base import BasePlugin


class MyPlugin(BasePlugin):
    name = "my_plugin"
    enabled = True

    def setup(self, runtime: dict) -> None:
        self.add_hook(runtime, "on_user_input", self.on_user_input)

    def on_user_input(self, text: str) -> None:
        print(f"[MyPlugin] received_input={text!r}")
```

This pattern is recommended because it keeps plugin wiring simple and easy to follow.

---

## Sample Plugin

A minimal sample plugin is available here:

- `plugins/samples/simple_greeting.py`

This sample demonstrates:

- inheriting from `BasePlugin`
- registering a hook in `setup()`
- reacting to a runtime event with a minimal handler

Sample plugins are provided as authoring examples.

They are not enabled by default.

---

## Builtin Plugins

Builtin plugins are part of the framework’s default plugin setup.

They are intended to serve as reference implementations as well as lightweight built-in behaviors.

Examples include:

- `ConsoleLoggerPlugin`
- `EmotionVTSPlugin`
- `ResponseLengthLoggerPlugin`

These examples show different plugin styles:

- lifecycle-focused plugin
- event bridge plugin
- minimal event logger plugin

---

## Registering a Plugin

To register a plugin, add it to the plugin manager before lifecycle execution:

```python
plugin_manager.register(MyPlugin())
plugin_manager.setup_all(runtime)
plugin_manager.on_start(runtime)
```

Registration should happen before `setup_all(runtime)`.

---

## Design Guidance

When writing plugins, prefer the following:

- keep responsibilities small
- register hooks in `setup()`
- react to events instead of controlling the main flow
- avoid broad runtime mutation
- treat builtin and sample plugins as reference patterns

For v1.8, the main goal is clarity of plugin authoring rather than large-scale plugin discovery or dependency management.
