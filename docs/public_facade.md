# Public Facade

The public facade is the stable entry point for using AI Character Framework as a library.

It is designed for application code that wants to call the framework directly without launching `main.py` or the full interactive runtime loop.

Current text chat API:

```python
from framework import create_text_chat_session

session = create_text_chat_session(
    preset="text_chat",
    character_name="default",
)

print(session.info)

response = session.ask("こんにちは。短く返して。")
print(response)
```

Current voice output boundary:

```python
from framework import VoiceOutputRequest, create_voice_output_session

voice_session = create_voice_output_session()
result = voice_session.create_output(
    VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )
)

print(result.request_state)
print(result.audio_ready)
```

## Scope

`create_text_chat_session()` is intentionally text-only.

It does not launch:

- `main.py`
- the runtime loop
- STT
- TTS
- VTube Studio / Live2D control

Use `main.py` or the preset run scripts for full runtime features such as voice input and VTS integration.

v5.0.0 adds a separate public voice output boundary through `create_voice_output_session()`. That boundary lets host apps request TTS output without importing `tts.voice_engine` or passing provider-specific secrets. It is not the full realtime voice runtime loop.

## Public API

### `create_text_chat_session()`

Creates a `TextChatSession` without starting the full runtime loop.

```python
from framework import create_text_chat_session

session = create_text_chat_session()
```

Optional preset and character arguments:

```python
session = create_text_chat_session(
    preset="text_chat",
    character_name="default",
)
```

`preset` must point to a text-only compatible preset.

As of v2.4.0, the facade also accepts direct provider/model selection:

```python
session = create_text_chat_session(
    provider="openai",
    model="gpt-4o-mini",
)
```

Arguments:

- `preset`: optional text-only preset name. When omitted, `APP_PRESET` is used if available; otherwise `text_chat` is used.
- `character_name`: optional character override. When omitted, the character configured by the selected preset is used.
- `provider`: optional direct LLM provider override. When omitted, the facade uses the default chat route with fallback.
- `model`: optional model override for the selected provider. Ignored when `provider` is omitted.

Supported public provider names include:

- `openai`
- `gemini`
- `grok`

`gemini` and `grok` are public aliases. Internally, provider definitions are still owned by `llm.factory` and `registry/llm.py`.

If `provider` is passed without `model`, the facade resolves the default model from `registry/llm.py`.


### `create_voice_output_session()`

Creates a provider-neutral `VoiceOutputSession` for app-facing TTS requests without starting the full runtime loop.

```python
from framework import VoiceOutputRequest, create_voice_output_session

session = create_voice_output_session(
    default_voice_profile_id="gentle_mina_default",
)

request = VoiceOutputRequest(
    text="今日は少し早めに休むとよさそうです。",
    voice_profile_id="gentle_mina_default",
    requested_audio_format="mp3",
    utterance_purpose="daily_advice",
    language_code="ja",
)

result = session.create_output(request)
```

Host apps should pass only framework-level voice output intent:

- `text`
- `voice_profile_id`
- `requested_audio_format`
- `utterance_purpose`
- `language_code`

FW owns and hides provider selection, provider voice IDs, API keys, model IDs, provider SDK calls, temporary audio files, and provider-specific parameters.

Without real provider configuration, `create_output()` returns a safe public result such as `request_state="unavailable"` with `audio_ready=False`. When a supported provider is configured but the real provider execution guard is closed, it returns `request_state="skipped"` with no audio handoff. These are expected mock-safe behaviors and should not be treated as accepted real TTS evidence.

For a DRC-style host app example, run:

```powershell
python examples/app_voice_output_integration.py
```

Use `--real-tts` only for an explicit configured real run. Even then, the app example does not accept provider voice IDs, API keys, model IDs, or provider-specific settings; those stay FW-side.

Before a configured real run, verify the opt-in and execution guard boundaries:

```powershell
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/smoke_voice_output_v500_release_readiness.py
```

The opt-in boundary check confirms that real TTS is explicit, provider selection is FW-owned, provider details remain hidden, and unavailable mock-safe output is not treated as real evidence. The execution guard check confirms that a configured provider still cannot import provider SDKs, call provider APIs, or write artifacts unless `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1` is set for an explicit real run. The release readiness check confirms that v5.0.0 is a mock-safe public boundary release and does not complete DRC real Web audio evidence. See `voice_output_real_tts_opt_in_checklist.md`, `voice_output_real_provider_execution_guard.md`, and `voice_output_v500_release_readiness_checklist.md` for the full checklists.

Voice output results use an app-facing artifact handoff contract:

- `audio_ready=False` means the host app must not try to play audio.
- `audio_url` is reserved for FW-hosted or FW-signed Web audio URLs.
- `audio_artifact_ref` is an opaque FW-owned artifact reference.
- generated audio should expose exactly one of `audio_url` or `audio_artifact_ref`.

The helper properties `audio_handoff_kind`, `has_audio_handoff`, and `is_generated` let app code inspect the handoff without parsing provider details. See `voice_output_artifact_result_contract.md` and run:

```powershell
python scripts/smoke_voice_output_artifact_result_contract.py
```


### `TextChatSession.info`

`TextChatSession.info` exposes stable, app-safe metadata about the created text
chat session.

```python
session = create_text_chat_session(provider="openai", model="gpt-4o-mini")

print(session.info.provider)
print(session.info.model)
print(session.info.output_language_code)
```

The info object is a `TextChatSessionInfo` instance.

Fields:

- `preset`: selected text-only preset name
- `character_name`: selected character name
- `input_language_code`: input language code
- `output_language_code`: output language code
- `llm_mode`: either `default_route` or `direct_provider`
- `provider`: resolved provider in direct provider mode, otherwise `None`
- `model`: resolved model in direct provider mode, otherwise `None`
- `route_name`: `chat` in default route mode, otherwise `None`
- `api_version`: public facade API version
- `session_type`: session type, currently `text_chat`
- `supports_streaming`: whether `ask_stream()` is part of this facade
- `supports_reset`: whether `reset()` is part of this facade
- `supports_interrupt`: whether `interrupt()` is part of this facade
- `supports_events`: whether app-facing event callbacks are part of this facade
- `supports_close`: whether `close()` is part of this facade
- `supports_voice_input`: whether voice input is part of this facade
- `supports_voice_output`: whether voice output is part of this facade
- `supports_live2d`: whether Live2D control is part of this facade

`TextChatSession.info` intentionally does not expose internal `RuntimeConfig`.

In default route mode, internal primary/fallback provider details are not exposed.
This keeps application code independent from the framework's internal routing and
fallback configuration.

In direct provider mode, `provider` and `model` expose the resolved provider/model
pair requested by application code.

### `TextChatSession.ask(text)`

Sends one text turn and returns the full assistant response as a string.

```python
response = session.ask("Hello. Please answer briefly.")
print(response)
```

### `TextChatSession.ask_stream(text)`

Sends one text turn and yields response chunks.

```python
for chunk in session.ask_stream("Hello. Please answer briefly."):
    print(chunk, end="")
```

This is a minimal streaming facade. Provider-specific emotion metadata is intentionally hidden from the public text API for now.

For an app-oriented streaming example, run:

```powershell
python examples/app_streaming_text_chat.py --provider openai --model gpt-4o-mini --message "こんにちは。1文で短く返して。"
```

The example prints chunks as they arrive and keeps the app code limited to public
`framework` imports.

### `TextChatSession.reset()`

Resets provider-owned conversation state when the underlying provider supports it.

```python
session.reset()
```

Stateless providers may treat this as a no-op.

### `TextChatSession.interrupt()`

Requests interruption of the current app-facing text session operation.

```python
accepted = session.interrupt()
```

In v4.0.0, `interrupt()` is a limited public boundary for app integration.

It allows app code to request interruption through a stable public method. Text
sessions may stop yielding future response chunks after the interrupt request is
observed.

This does not guarantee provider-level cancellation of an active LLM request,
TTS queue cancellation, or realtime voice barge-in.

`session.info.supports_interrupt` means that this stable public method is
available. It does not mean hard cancellation is supported.

### `TextChatSession.on_event(callback)`

Registers an app-facing event callback for the text session.

```python
def handle_event(event):
    print(event.type)
    print(event.data)

session.on_event(handle_event)
```

App-facing events are intended for external application code. They are separate
from internal plugin hooks and do not expose runtime, provider, STT/TTS, VTS, or
plugin manager objects.

Current text session events include:

- `response_started`
- `response_chunk`
- `response_completed`
- `reset`
- `interrupt_requested`
- `error`

### `TextChatSession.on_state_change(callback)`

Registers an app-facing state change callback for the text session.

```python
def handle_state_change(event):
    print(event.old_state)
    print(event.new_state)

session.on_state_change(handle_state_change)
```

Current text session states include:

- `idle`
- `responding`
- `interrupted`
- `error`

For a small app-facing example, run:

```powershell
python examples/app_state_events.py --provider openai --model gpt-4o-mini
```

## Public errors

The facade exposes public error classes so application code can catch framework integration errors at a clear boundary.

```python
from framework import FacadeError, create_text_chat_session

try:
    session = create_text_chat_session(provider="openai", model="gpt-4o-mini")
    print(session.ask("Hello."))
except FacadeError as e:
    print(f"Framework integration error: {e}")
```

Public info classes:

- `TextChatSessionInfo`: stable public session metadata for app integrations

Public error classes:

- `FacadeError`: base exception for public facade integration errors
- `FacadeConfigError`: raised when the selected preset or character is invalid for the text-only facade
- `FacadeProviderError`: raised when provider/model resolution or provider creation fails

### Streaming example

Use this example when you want to see the simplest app-style streaming loop:

```powershell
python examples/app_streaming_text_chat.py --provider openai --model gpt-4o-mini
```

It demonstrates this shape:

```python
from framework import FacadeError, create_text_chat_session

try:
    session = create_text_chat_session(provider="openai", model="gpt-4o-mini")
    for chunk in session.ask_stream("Hello. Please answer briefly."):
        print(chunk, end="", flush=True)
except FacadeError as e:
    print(f"Framework integration error: {e}")
```

### Reset example

Use this example when your app needs a user-facing "new conversation" or
"clear chat" action:

```powershell
python examples/app_reset_text_chat.py --provider openai --model gpt-4o-mini
```

It demonstrates this shape:

```python
from framework import FacadeError, create_text_chat_session

try:
    session = create_text_chat_session(provider="openai", model="gpt-4o-mini")
    print(session.ask("Hello. Please answer briefly."))
    session.reset()
    print(session.ask("Start a new short greeting."))
except FacadeError as e:
    print(f"Framework integration error: {e}")
```

`reset()` resets provider-owned conversation state when the underlying provider
supports it. App code should call it through the public `TextChatSession`, not
through internal provider or runtime objects.

### Session info example

Use this example when your app needs to inspect public session metadata and
capability flags:

```powershell
python examples/app_session_info.py --provider openai --model gpt-4o-mini
```

### App-facing state/events example

Use this example when your app needs to observe text session events or state
changes:

```powershell
python examples/app_state_events.py --provider openai --model gpt-4o-mini
```

### Interrupt example

Use this example when your app needs to request interruption through the public
text session boundary:

```powershell
python examples/app_interrupt_text_chat.py --provider openai --model gpt-4o-mini
```

`interrupt()` is a limited public boundary in v4.0.0. It does not guarantee
provider-level hard cancellation, TTS queue cancellation, or realtime voice
barge-in.

### Error handling example

For an app-oriented example of catching public facade errors, run:

```powershell
python examples/app_error_handling.py
```

The default mode is offline-safe. It intentionally demonstrates:

- `FacadeConfigError` for a preset that is not compatible with the text facade
- `FacadeProviderError` for an unsupported direct provider name

You can also use the same example for an optional live turn after setting API keys:

```powershell
python examples/app_error_handling.py --live --provider openai --model gpt-4o-mini
```

External apps should normally catch `FacadeError` at the framework boundary, and
may catch `FacadeConfigError` or `FacadeProviderError` when they want more
specific user-facing messages.

## Supported presets

The text facade accepts text-only presets such as:

- `text_chat`
- `bilingual_ja_en`
- other presets where voice input, voice output, VTS, and TTS are disabled

Presets such as `voice_vts` and `text_vts` are rejected by the facade because they require runtime systems outside the text-only public API.

## App integration contract

For a more explicit boundary between external application code and framework internals, see:

- `app_integration_contract.md`

The short version is:

- import from `framework`
- create sessions with `create_text_chat_session()`
- inspect public metadata through `session.info`
- send user text through `ask()` or `ask_stream()`
- reset a text conversation through `reset()`
- request interruption through `interrupt()` when supported
- observe app-facing events through `on_event()` and `on_state_change()`
- catch `FacadeError` at the app boundary
- do not depend on `RuntimeConfig` or internal runtime objects

## Minimal app integration example

Use this example when you want to see how an external application might wrap the framework API:

```powershell
python examples/minimal_app_text_chat.py
```

With provider/model override:

```powershell
python examples/minimal_app_text_chat.py --provider openai --model gpt-4o-mini --message "こんにちは。1文で短く返して。"
```

The example shows this shape:

```python
from framework import FacadeError, create_text_chat_session

class MinimalTextChatApp:
    def __init__(self):
        self._session = create_text_chat_session(provider="openai", model="gpt-4o-mini")

    @property
    def session_info(self):
        return self._session.info

    def reply(self, user_text: str) -> str:
        return self._session.ask(user_text)
```

This is intentionally different from `examples/public_text_chat.py`, which only demonstrates the smallest direct facade call.

## Import boundary

Importing `framework` should not:

- start the runtime loop
- connect to VTube Studio
- initialize STT/TTS
- create provider clients
- make network calls

Provider clients are created only when `create_text_chat_session()` is called.

## Smoke checks

Offline-safe check:

```powershell
python scripts/smoke_public_facade.py
```

Optional live LLM check using the default chat route:

```powershell
python scripts/smoke_public_facade.py --ask "こんにちは。短く返して"
```

Optional live LLM check using direct provider mode:

```powershell
python scripts/smoke_public_facade.py --provider openai --model gpt-4o-mini --ask "こんにちは。短く返して"
```

Minimal direct facade example:

```powershell
python examples/public_text_chat.py
```

Minimal app-style integration example:

```powershell
python examples/minimal_app_text_chat.py
```

Offline error handling example:

```powershell
python examples/app_error_handling.py
```

Provider-selected app-style example:

```powershell
python examples/minimal_app_text_chat.py --provider openai --model gpt-4o-mini
```

Session info example:

```powershell
python examples/app_session_info.py --provider openai --model gpt-4o-mini
```

App-facing state/events example:

```powershell
python examples/app_state_events.py --provider openai --model gpt-4o-mini
```

Interrupt boundary example:

```powershell
python examples/app_interrupt_text_chat.py --provider openai --model gpt-4o-mini
```

Voice output app integration example:

```powershell
python examples/app_voice_output_integration.py
```

Voice output real TTS opt-in boundary smoke:

```powershell
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
```

Voice output real provider execution guard smoke:

```powershell
python scripts/smoke_voice_output_real_provider_execution_guard.py
```

Host app voice output integration handoff smoke:

```powershell
python scripts/smoke_voice_output_host_app_handoff.py
```

See `host_app_voice_output_integration_handoff.md` for the general app-facing voice output handoff policy.


## Future notes

### Voice-friendly output policy

A future version may add a framework-level output policy for TTS-enabled
sessions.

The goal is to make LLM responses easier for speech synthesis to read aloud.

This should be treated as output-quality guidance, not character personality.
It should avoid unnecessary symbols, dense Markdown, tables, and excessive
abbreviations while keeping code, commands, file paths, URLs, environment
variable names, and proper nouns unchanged when necessary.

The policy should be enabled only when audio/TTS output is active.

## Public API inventory

As of v5.0.0 development, the stable public import boundary includes the v4 text APIs plus the provider-neutral voice output boundary:

```python
from framework import (
    FacadeConfigError,
    FacadeError,
    FacadeProviderError,
    TextChatSession,
    TextChatSessionInfo,
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSession,
    VoiceOutputSessionInfo,
    create_text_chat_session,
    create_voice_output_session,
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

These APIs are intended for external app integration.

The following APIs are planned or being evaluated after the current v4.0.0 text session boundary:

```python
session.close()
```

External apps should not import internal runtime modules such as `core`, provider implementations, STT/TTS clients, VTS clients, plugin manager internals, or runtime loop internals.

For voice output integrations, external apps should not import `tts.voice_engine`, should not own provider voice IDs or API keys, and should not treat local playback as Web evidence. The host app handoff policy is documented in `host_app_voice_output_integration_handoff.md`.

Importing `framework` should remain lightweight and should not load runtime, provider SDK, legacy audio playback, or VTS modules.

## v5.5.0 candidate public real-motion adapter boundary

FW-VTS-0a freezes the existing v5.2.0 root-public motion skeleton before a
future real VTube Studio adapter is implemented.

Host applications use only the Framework root:

```python
from framework import (
    MotionRequest,
    MotionResult,
    create_motion_session,
)

session = create_motion_session(adapter="mock")
result = session.apply_motion(
    MotionRequest.emotion_update("happy")
)
session.close()
```

Current v5.4.0 behavior remains unchanged:

- the mock adapter executes locally;
- real adapter support remains false;
- a closed execution guard returns typed
  `provider_execution_not_allowed`;
- an enabled VTS alias still returns typed `not_implemented`;
- normal import and mock execution do not import pyvts, open WebSockets, read
  token files, or discover private models.

External applications must not import `framework.motion`,
`framework.motion_session`, `live2d`, plugins, internal adapters, or pyvts. They
must not implement a VTS WebSocket client, read token files, or process raw VTS
requests/responses.

The proposed v5.5.0 real adapter remains default-off and unimplemented in
FW-VTS-0a. See `v550_real_motion_adapter_readiness.md`.

## v5.5.0 candidate motion adapter configuration/status

FW-VTS-0b exposes a standalone explicit-only configuration and capability
resolver from the Framework root:

```python
from framework import (
    MotionAdapterExecutionConfig,
    MotionIntent,
    get_motion_adapter_execution_capability,
    resolve_motion_adapter_execution_config,
)

config = resolve_motion_adapter_execution_config(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
    endpoint_configured=True,
    runtime_available=True,
    token_available=True,
    model_selected=True,
    configured_intents=(
        MotionIntent.EXPRESSION,
        MotionIntent.EMOTION,
    ),
)

capability = get_motion_adapter_execution_capability(config)
```

The resolver accepts boolean readiness assertions only. Host apps do not pass
endpoint values, tokens, token paths, model paths, hotkey IDs, provider clients,
WebSocket objects, or raw VTS payloads.

A `configured` capability is diagnostic configuration state, not real adapter
availability. `supports_real_adapter` remains false and public
`MotionSession` execution remains `not_implemented` until later composition and
real-transport checkpoints.

## v5.5.0 candidate internal VTube Studio transport boundary

FW-VTS-0c adds provider-specific internal transport symbols under
`framework.vtube_studio_transport`. They are intentionally not exported from
the Framework root.

Host applications and DRC must not import:

```python
from framework.vtube_studio_transport import VTubeStudioTransport
```

They continue to use root-public provider-neutral APIs. MotionSession
composition remains deferred to FW-VTS-0e, so an enabled VTS alias still
returns typed `not_implemented`.

The internal fake executes only deterministic in-memory protocol calls. It does
not connect to VTube Studio, expose hotkey names or IDs in results, or execute
real motion.

## v5.5.0 candidate guarded pyvts transport boundary

FW-VTS-0d adds `framework.vtube_studio_pyvts_transport` as an internal
provider-specific implementation of the frozen FW-VTS-0c transport Protocol.

The following remain internal and are not exported from `framework`:

```python
VTubeStudioPyvtsTransportConfig
VTubeStudioPyvtsClient
VTubeStudioPyvtsClientFactory
VTubeStudioPyvtsModuleImporter
VTubeStudioPyvtsTransport
```

Host applications and DRC must not import these symbols. MotionSession
composition remains deferred to FW-VTS-0e, so the root-public VTS alias still
returns typed `not_implemented`.

The FW-VTS-0d smoke uses only an injected fake pyvts module and fake client.
Actual pyvts import, WebSocket connection, VTube Studio authentication, and real
hotkey execution are not performed.

## v5.5.0 candidate root-public VTS MotionSession composition

FW-VTS-0e keeps the application-facing boundary provider-neutral:

```python
from framework import MotionRequest, create_motion_session
```

The new VTS arguments are keyword-only and default-off. A session enters the
real-capable composition path only when VTS-specific configuration is explicitly
supplied. The earlier call remains a compatibility boundary and still returns
typed `not_implemented`:

```python
create_motion_session(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
)
```

An explicitly composed session requires `preflight()` before `apply_motion()`.
Hotkey bindings support only the accepted hotkey-first intents:

```text
expression:<value>
emotion:<value>
gesture:<value>
stop_motion
reset_expression
```

Speaking state, idle motion, and look-at remain unsupported. Endpoint values,
authentication material, hotkey names, provider payloads, and raw exceptions are
never returned through `MotionSessionInfo`, `MotionCapability`, `MotionResult`,
or public events.

The internal composition, bridge, transport, and pyvts configuration types are
not exported from `framework`. Host applications and DRC must not import them.
Actual VTube Studio execution remains NOT_AUTHORIZED in FW-VTS-0e validation.
