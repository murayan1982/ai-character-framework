# v5.0.0 - Public Voice Output / TTS Boundary Foundation

## Development notes

This version adds a public, provider-neutral voice output boundary for app integrations while keeping provider-specific TTS details inside FW.

Current v5 additions include:

- `create_voice_output_session()`
- `VoiceOutputSession` / `VoiceOutputSessionInfo`
- `VoiceOutputRequest` / `VoiceOutputResult`
- lazy internal provider adapter behavior
- DRC-style app voice output integration example:
  - `examples/app_voice_output_integration.py`
- real TTS opt-in boundary checklist and mock-safe smoke check:
  - `voice_output_real_tts_opt_in_checklist.md`
  - `scripts/smoke_voice_output_real_tts_opt_in_boundary.py`
- voice output artifact result contract and mock-safe smoke check:
  - `voice_output_artifact_result_contract.md`
  - `scripts/smoke_voice_output_artifact_result_contract.py`
- real provider execution guard and mock-safe smoke check:
  - `voice_output_real_provider_execution_guard.md`
  - `scripts/smoke_voice_output_real_provider_execution_guard.py`
- v5.0.0 voice output release readiness checklist and mock-safe smoke check:
  - `voice_output_v500_release_readiness_checklist.md`
  - `scripts/smoke_voice_output_v500_release_readiness.py`

Host apps should pass `text`, `voice_profile_id`, `requested_audio_format`, `utterance_purpose`, and `language_code` only. Voice output results use the public `audio_ready`, `audio_format`, `audio_url`, and `audio_artifact_ref` handoff contract. Provider selection, provider voice IDs, API keys, model IDs, provider-specific parameters, SDK calls, and audio artifact handling remain FW responsibilities.

Mock-safe public checks should pass without provider credentials. Unavailable or execution-guarded skipped provider status must not be counted as real TTS evidence. A configured provider cannot import provider SDKs, call provider APIs, or write audio artifacts unless `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1` is set for an explicit real run. v5.0.0 release readiness is documented as a mock-safe public boundary release, while real provider runs and DRC Web evidence remain separate follow-up workflows.

---

# v4.0.0 - App Integration SDK Foundation

## Summary

v4.0.0 strengthens AI Character Framework as an app-facing SDK foundation.

This release focuses on making the framework safer and easier to use from
external applications through stable public APIs, app-safe session metadata,
limited interruption boundaries, app-facing event callbacks, SDK examples, and
release-package smoke checks.

The public facade remains intentionally text-only. Realtime voice runtime
features, provider-level hard cancellation, TTS queue cancellation, and
always-on microphone barge-in are reserved for future runtime work.

## Theme

```text
App Integration SDK Foundation
```

In practical terms:

```text
Let external apps use the framework through stable public APIs instead of internal modules.
```

## Added

- Added app-safe SDK metadata to `TextChatSessionInfo`:
  - `api_version`
  - `session_type`
  - `supports_streaming`
  - `supports_reset`
  - `supports_interrupt`
  - `supports_events`
  - `supports_close`
  - `supports_voice_input`
  - `supports_voice_output`
  - `supports_live2d`
- Added public text session interruption boundary:
  - `session.interrupt()`
- Added app-facing event callback APIs:
  - `session.on_event(callback)`
  - `session.on_state_change(callback)`
- Added public app-facing event models:
  - `TextChatSessionEvent`
  - `TextChatStateChange`
- Added SDK-oriented examples:
  - `examples/app_session_info.py`
  - `examples/app_state_events.py`
  - `examples/app_interrupt_text_chat.py`
- Added app SDK smoke check:
  - `scripts/smoke_app_sdk.py`
- Added v4.0.0 and v5.0.0 roadmap docs:
  - `roadmap_feature_v4.0.0.md`
  - `roadmap_feature_v5.0.0.md`

## Changed

- Kept `create_text_chat_session()` as the stable public constructor for v4.0.0.
- Clarified that `create_character_session()` is a future candidate, not a v4.0.0 public API.
- Strengthened the public `framework` import boundary.
- Clarified that external apps should import from `framework` instead of internal modules.
- Clarified app-facing session operations:
  - `session.ask(text)`
  - `session.ask_stream(text)`
  - `session.reset()`
  - `session.interrupt()`
  - `session.on_event(callback)`
  - `session.on_state_change(callback)`
- Clarified the difference between app-facing events and internal plugin hooks.
- Updated README app integration guidance for the v4.0.0 SDK boundary.
- Updated public facade docs to include:
  - app-safe capability metadata
  - limited interrupt boundary
  - app-facing event callbacks
  - new SDK examples
- Updated app integration contract docs to match the current public APIs.
- Updated release package policy and checks to include the app SDK smoke path.

## Public API

The stable public import boundary now includes:

```python
from framework import (
    FacadeConfigError,
    FacadeError,
    FacadeProviderError,
    TextChatSession,
    TextChatSessionEvent,
    TextChatSessionInfo,
    TextChatStateChange,
    create_text_chat_session,
)
```

The current app-facing text session supports:

```python
session.ask(text)
session.ask_stream(text)
session.reset()
session.interrupt()
session.on_event(callback)
session.on_state_change(callback)
```

## Interruption Boundary

`session.interrupt()` is now available as a public app-facing boundary.

In v4.0.0, this is intentionally limited:

- It lets app code request interruption through a stable public method.
- Text sessions may stop yielding future chunks after the request is observed.
- It does not guarantee provider-level hard cancellation of active LLM requests.
- It does not imply TTS queue cancellation.
- It does not imply realtime voice barge-in.

Full realtime voice interruption behavior belongs to future runtime work.

## App-facing Events

Text sessions can now expose app-facing callbacks:

```python
def handle_event(event):
    print(event.type)
    print(event.data)

def handle_state_change(event):
    print(event.old_state)
    print(event.new_state)

session.on_event(handle_event)
session.on_state_change(handle_state_change)
```

Current app-facing event types include:

- `response_started`
- `response_chunk`
- `response_completed`
- `reset`
- `interrupt_requested`
- `error`

Current app-facing states include:

- `idle`
- `responding`
- `interrupted`
- `error`

These callbacks are separate from internal plugin hooks.

## Examples

New app-oriented examples:

```powershell
python examples/app_session_info.py --provider openai --model gpt-4o-mini
python examples/app_state_events.py --provider openai --model gpt-4o-mini
python examples/app_interrupt_text_chat.py --provider openai --model gpt-4o-mini
```

Existing app integration examples remain available:

```powershell
python examples/public_text_chat.py
python examples/minimal_app_text_chat.py
python examples/app_error_handling.py
python examples/app_streaming_text_chat.py
python examples/app_reset_text_chat.py
```

## Documentation

Updated or added:

- `../README.md`
- `public_facade.md`
- `app_integration_contract.md`
- `plugin_events.md`
- `release_package_policy.md`
- `roadmap_feature_v4.0.0.md`
- `roadmap_feature_v5.0.0.md`

The docs now distinguish:

- public app-facing SDK APIs
- internal runtime/plugin hooks
- limited text-session interrupt behavior
- future realtime voice runtime scope

## Verification

Run the standard checks before tagging the release:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/check_release_package.py
```

Optional live LLM check:

```powershell
python scripts/smoke_public_facade.py --provider openai --model gpt-4o-mini --ask "こんにちは。短く返して"
```

Optional app examples:

```powershell
python examples/app_error_handling.py
python examples/public_text_chat.py
python examples/minimal_app_text_chat.py
python examples/app_streaming_text_chat.py --provider openai --model gpt-4o-mini
python examples/app_reset_text_chat.py --provider openai --model gpt-4o-mini
python examples/app_session_info.py --provider openai --model gpt-4o-mini
python examples/app_state_events.py --provider openai --model gpt-4o-mini
python examples/app_interrupt_text_chat.py --provider openai --model gpt-4o-mini
```

## Notes

v4.0.0 is an SDK boundary release, not a realtime voice runtime release.

The following remain future work:

- full concurrent voice barge-in
- always-on microphone listening while TTS is speaking
- provider-level hard cancellation of active LLM requests
- production-grade TTS queue cancellation
- full public voice session facade
- GUI or mobile demo app

These are tracked as future v4.x or v5.0.0 work.

## Notes for GitHub Release

When publishing the release, copy the relevant contents of this file into the
GitHub Release page.

After the next version starts, this file may be updated for the next current
release.

Past release details are preserved by the corresponding Git tag and GitHub
Release.
