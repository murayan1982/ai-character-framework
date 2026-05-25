# Roadmap: v4.0.0 - App Integration SDK Foundation

v4.0.0 focuses on making AI Character Framework easier and safer to use from external applications.

The main goal is to turn the current text public facade into a clearer app-facing SDK boundary without exposing internal runtime, provider, STT, TTS, or VTS implementation details.

## Positioning

v3.0.0 introduced the advanced runtime foundation:

- conversation state tracking
- runtime state events
- interruption request boundary
- TTS stop boundary
- prompt builder separation
- public text facade improvements
- plugin event documentation

v4.0.0 builds on that foundation by defining what an external app can safely import, call, observe, and rely on.

## Theme

```text
App Integration SDK Foundation
```

In practical terms:

```text
Let external apps use the framework through stable public APIs instead of internal modules.
```

## Primary goals

- Strengthen the public `framework` import boundary.
- Expand app-facing session APIs in a controlled way.
- Clarify which session actions are stable for app developers.
- Expose app-safe session metadata and state information.
- Add app-oriented examples that do not import internal modules.
- Prepare future voice/runtime integration without implementing full realtime voice barge-in yet.

## Non-goals

v4.0.0 should not try to implement everything.

Out of scope for v4.0.0:

- full concurrent voice barge-in
- always-on microphone listening while TTS is speaking
- provider-level hard cancellation of active LLM requests
- production-grade TTS queue cancellation
- full voice session facade
- GUI or mobile demo app
- character memory system
- plugin marketplace or external plugin packaging

These belong to v4.x follow-up work or v5.0.0.

## Public API direction

The existing public boundary should remain:

```python
from framework import create_text_chat_session
```

v4.0.0 should evaluate whether to keep only `create_text_chat_session()` or introduce a more general session entry point for future expansion.

Candidate future-facing shape:

```python
from framework import create_character_session

session = create_character_session(
    preset="text_chat",
    character_name="default",
)

response = session.ask("Hello.")
```

If this is too early, v4.0.0 can keep `create_text_chat_session()` as the only public constructor and prepare internal structure for a future `create_character_session()`.

## Stable app-facing actions

The app-facing session contract should clearly define actions such as:

```python
session.ask(text)
session.ask_stream(text)
session.reset()
session.interrupt()
session.close()
```

Recommended v4.0.0 scope:

- Keep `ask()` stable.
- Keep `ask_stream()` stable for text sessions.
- Keep `reset()` stable.
- Add or design `interrupt()` as an app-facing request boundary, even if v4.0.0 only supports limited behavior.
- Consider `close()` or context-manager support if lifecycle cleanup becomes necessary.

Example desired app shape:

```python
from framework import FacadeError, create_text_chat_session

try:
    session = create_text_chat_session(provider="openai", model="gpt-4o-mini")
    print(session.ask("Hello. Please answer briefly."))
    session.reset()
except FacadeError as exc:
    print(f"Framework integration error: {exc}")
```

## Session metadata direction

`session.info` should continue to expose app-safe metadata only.

Potential additions to evaluate:

- `api_version`
- `session_type`
- `supports_interrupt`
- `supports_events`
- `supports_close`
- `supports_voice_input`
- `supports_voice_output`
- `supports_live2d`

Existing fields should remain stable unless there is a strong reason to change them.

Internal objects should remain hidden:

- `RuntimeConfig`
- provider implementation classes
- runtime loop internals
- STT/TTS/VTS clients
- plugin manager internals

## State and event direction

v3.0.0 introduced runtime state and plugin state events.

v4.0.0 should decide how much of that becomes app-facing.

Possible app-facing design:

```python
session.on_state_change(callback)
session.on_event(callback)
```

Possible callback shape:

```python
def handle_state_change(event):
    print(event.old_state)
    print(event.new_state)

session.on_state_change(handle_state_change)
```

v4.0.0 does not need to expose every internal event.

Recommended first stable event set:

- state changed
- response started
- response chunk
- response completed
- error
- reset
- interrupt requested

Events should be documented as app-facing events, separate from internal plugin hooks.

## Plugin cleanup integration

Plugin/extension cleanup can be included in v4.0.0 only where it supports the app SDK boundary.

Good v4.0.0 plugin cleanup targets:

- clarify internal plugin hooks vs app-facing events
- align event naming
- document lifecycle event responsibilities
- keep sample plugins working
- avoid exposing plugin internals as the main app integration API

Not necessary for v4.0.0:

- full plugin configuration system
- third-party plugin packaging rules
- plugin marketplace-like structure
- advanced plugin dependency handling

## Documentation targets

Update or add these docs:

- `roadmap_feature_v4.0.0.md`
- `public_facade.md`
- `app_integration_contract.md`
- `plugin_events.md`
- `RELEASE_NOTES.md`

README should link app developers toward the public facade docs instead of encouraging internal imports.

## Example targets

Existing examples are already useful:

- `examples/minimal_app_text_chat.py`
- `examples/public_text_chat.py`
- `examples/app_streaming_text_chat.py`
- `examples/app_reset_text_chat.py`
- `examples/app_error_handling.py`

v4.0.0 should strengthen these and possibly add:

- `examples/app_session_info.py`
- `examples/app_state_events.py`
- `examples/app_interrupt_text_chat.py`

All app examples should import only from `framework` unless the example is explicitly marked as internal/advanced.

## Testing targets

Update or add smoke tests for:

- public import boundary
- public session metadata
- provider/model resolution
- text ask compatibility
- streaming compatibility
- reset compatibility
- interrupt API boundary if added
- event callback registration if added
- examples importability
- release package contents

Existing command set should continue to pass:

```powershell
python -m compileall -q .
python scripts/check_release_package.py
python scripts/smoke_public_facade.py
python examples/app_error_handling.py
python examples/public_text_chat.py
python examples/minimal_app_text_chat.py
```

v4.0.0 may add a dedicated smoke script such as:

```powershell
python scripts/smoke_app_sdk.py
```

## Suggested Day plan

### Day 1 - Roadmap and scope lock

- Add v4.0.0 roadmap.
- Define v4.0.0 as App Integration SDK Foundation.
- Move full realtime voice barge-in to v5.0.0.
- Mark plugin cleanup as supporting work, not the main theme.

Acceptance:

- Roadmap clearly lists goals, non-goals, and follow-up versions.

### Day 2 - Public facade inventory

- Review `framework/facade.py`.
- Review `framework/__init__.py` exports.
- Review `public_facade.md`.
- Identify public vs internal responsibilities.

Acceptance:

- Current public API is documented.
- Any accidental internal dependency is noted.

### Day 3 - App-facing session API design

- Decide whether v4.0.0 adds a new session entry point or strengthens `create_text_chat_session()` only.
- Define stable session methods.
- Define future-compatible naming for character/session APIs.

Acceptance:

- App-facing session contract is documented before implementation.

### Day 4 - State, reset, and interrupt boundary

- Decide how app code should observe state.
- Decide whether `interrupt()` is public in v4.0.0.
- Keep v4.0.0 interruption limited and clearly documented if full cancellation is not implemented.

Acceptance:

- App-facing state/reset/interrupt behavior is predictable and documented.

### Day 5 - App-facing event callbacks

- Design minimal app event callback API.
- Keep it separate from internal plugin hooks.
- Add example if implemented.

Acceptance:

- App examples can observe session events without importing `core`.

### Day 6 - Plugin/event naming cleanup

- Align plugin event names with documented responsibilities.
- Clarify plugin lifecycle vs app event lifecycle.
- Keep existing sample plugins compatible.

Acceptance:

- Plugin docs and app integration docs do not conflict.

### Day 7 - SDK examples

- Add or update app examples.
- Ensure examples only use public imports.
- Keep examples small and copyable.

Acceptance:

- A developer can understand basic app integration from examples alone.

### Day 8 - Docs and README path cleanup

- Update README app integration section.
- Update public facade and app integration contract docs.
- Add notes about what is intentionally not supported yet.

Acceptance:

- README points users to correct app-facing docs.
- Docs do not imply full voice SDK support yet.

### Day 9 - Smoke tests and release package checks

- Add or update public facade smoke tests.
- Add app SDK smoke tests if useful.
- Confirm release package includes docs/examples needed by app developers.

Acceptance:

- Compile, smoke, and release package checks pass.

### Day 10 - Final release cleanup

- Update release notes.
- Run final checks.
- Prepare v4.0.0 tag and release.

Acceptance:

- v4.0.0 can be described as a stable app integration foundation.

## Release acceptance checklist

v4.0.0 is ready when:

- Public app imports are clearly documented.
- App examples do not rely on internal modules.
- Session metadata is app-safe and stable.
- Reset behavior is stable through the public facade.
- Streaming behavior is stable through the public facade.
- Interrupt/event behavior is either implemented or explicitly documented as future work.
- README and docs agree on the framework being a developer framework, not a finished app.
- Release package checks pass.

## Follow-up versions

### v4.1.x candidates

- More app examples.
- Plugin/event cleanup follow-up.
- Better SDK documentation.
- Optional app-facing event expansion.
- Early voice-session design notes.

### v5.0.0 connection

v4.0.0 should prepare v5.0.0 by making sure future realtime voice features can be controlled through stable app-facing operations such as:

```python
session.interrupt()
session.reset()
session.on_state_change(...)
session.on_event(...)
```

v5.0.0 can then implement deeper realtime behavior behind those stable APIs.
