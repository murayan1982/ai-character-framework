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

## v5.5.0 candidate operator acceptance boundary

FW-VTS-0f1 does not add a new root-public runtime API. The operator real-motion
command is a separate CLI and imports only `MotionIntent`, `MotionOutcome`,
`MotionRequest`, and `create_motion_session` from `framework`.

Token bootstrap remains operator-only and is never called by `MotionSession`.
Private token, configuration, and evidence must use absolute paths repository
outside. The operator tools accept pyvts 0.3.3 and loopback only VTube Studio
endpoints.

The source smoke does not perform real provider execution. In FW-VTS-0f1:

```text
real VTS execution: NOT_AUTHORIZED
private token bootstrap: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Provider-specific clients, transport/configuration types, private paths, token
material, hotkey names, model identities, and raw payloads remain absent from
the public facade.

<!-- FW-VTS-0f1c-OPTIONAL-STOP-CORRECTIVE -->
## FW-VTS-0f1c optional stop_motion corrective

Baseline:

```text
1f737128554d701150427da4ce1c146759881255
```

Status:

```text
implementation: COMPLETED / AWAITING REVIEW
private token bootstrap: COMPLETED / ACCEPTED / REUSE
real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

This corrective supersedes the earlier operator-only exact-five requirement.
VTube Studio hotkey acceptance now has four required intents:

```text
expression
emotion
gesture
reset_expression
```

`stop_motion` is optional and may be configured only when the selected adapter
and model have an actually proven stop operation. A four-binding private config
is valid and must report `supports_stop_motion == false`. A five-binding private
config is valid only when its fifth binding is a real stop operation; renaming
`RemoveAllExpressions` or `TriggerAnimation` to `stop_motion` does not prove
stop support.

The operator executes and visually verifies the four required intents. It
executes and verifies `stop_motion` only when the optional binding is present.
Private evidence records:

```text
required_four_intents_verified
stop_motion_supported
stop_motion_verified
optional_stop_motion_contract
```

Accepted bootstrap evidence may remain tied to the accepted bootstrap commit
when that commit is an ancestor of the corrective acceptance commit and
`scripts/operator_v550_vtube_studio_token_bootstrap.py` is unchanged between
the two commits.

The corrective is an exact ten-file surface limited to six documentation files
and four operator/checker scripts. Framework runtime, public API, pyvts
transport, token bootstrap tooling, release files, and DRC are frozen.

<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:BEGIN -->
## FW-VTS-0f2 public real-motion acceptance sync

This block supersedes earlier pre-execution authorization status for the
FW-VTS-0f operator checkpoint. It records only public-safe facts already
accepted by the private evidence validator.

```text
checkpoint: FW-VTS-0f2
status: IMPLEMENTED / AWAITING_REVIEW
accepted framework head: b7b9639dfa1f675ba04a33cd8ce297429f98fd15
accepted bootstrap head: 1f737128554d701150427da4ce1c146759881255
pyvts version: 0.3.3
actual pyvts import: VERIFIED
actual WebSocket connection: VERIFIED
actual VTube Studio authentication: VERIFIED
model loaded: VERIFIED
hotkey inventory loaded: VERIFIED
expression: VERIFIED
emotion: VERIFIED
gesture: VERIFIED
reset_expression: VERIFIED
required four intents: VERIFIED
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: VERIFIED
real hotkey execution: VERIFIED
real motion execution: VERIFIED
operator visual confirmation: COMPLETE
session close: VERIFIED
bridge thread termination: VERIFIED
bootstrap evidence reused: VERIFIED
bootstrap operator unchanged: VERIFIED
private evidence: ACCEPTED_BY_VALIDATOR
DRC repository changed: False
private values recorded in repository: False
real VTS execution repeated by this sync: False
private evidence read by this sync: False
commit / push: NOT_AUTHORIZED
```

No token material, private path, endpoint value, hotkey identity, selector
value, model identity, provider payload, raw exception, evidence document,
or screenshot is part of this public acceptance record.
<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:BEGIN -->
## v6.0.0 development: canonical root-public API manifest

FW-RT6-0b Control A removes the duplicated release-by-release construction of
`framework.__all__`. The ordered root-public compatibility surface is now
defined once in:

```text
framework/public_api.py
```

`framework.__init__` imports the public symbols and assigns:

```python
__all__ = list(PUBLIC_API_NAMES)
```

The manifest preserves the accepted v5.5.0 root-public surface exactly. It does
not remove or rename existing text, voice-input, voice-output, realtime,
interrupt/output-control, or motion symbols.

The OpenAI voice-input compatibility names that were already root-public remain
available through lazy `framework.__getattr__` resolution. They are listed in
`PROVIDER_COMPAT_LAZY_EXPORT_MODULES`; importing `framework` alone does not
import OpenAI, ElevenLabs, VTube Studio, websocket, microphone, playback, or
legacy runtime modules.

Control A does not:

- clean up duplicate `VoiceOutputSession` method definitions;
- change any session-info API or boundary version;
- change capability truthfulness;
- implement unified realtime orchestration;
- execute a provider, network operation, microphone, playback, or VTS action.

```text
checkpoint: FW-RT6-0b Control A
status: IMPLEMENTED / AWAITING_REVIEW
canonical root-public name count: 95
v5.5 root-public compatibility preserved: True
provider compatibility exports lazy: True
next control: FW-RT6-0b Control B
next control authorized: False
```
<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:END -->

<!-- FW-RT6-0b-B-VOICE-OUTPUT-SESSION-HYGIENE:BEGIN -->
## v6.0.0 development: VoiceOutputSession lifecycle hygiene

FW-RT6-0b Control B consolidates the accumulated v5.0/v5.1
`VoiceOutputSession` compatibility overrides into one readable implementation.

The public contract remains unchanged:

```text
session.info():
method

session.is_closed:
property

session.close():
idempotent

session.dispose():
close alias

session.create_output():
v5.0-compatible method

session.speak():
v5.1-compatible wrapper
```

A closed session returns a provider-neutral non-playable result from both
`create_output()` and `speak()`:

```text
request_state: failed
public_error_code: session_closed
audio_ready: False
audio_url: None
audio_artifact_ref: None
```

Control B does not change the canonical root-public manifest, provider adapter,
real TTS execution guard, artifact handoff design, version values, or realtime
runtime behavior.

```text
checkpoint: FW-RT6-0b Control B
status: IMPLEMENTED / AWAITING_REVIEW
duplicate VoiceOutputSession methods: False
provider execution: False
network execution: False
audio playback: False
next control: FW-RT6-0b Control C
next control authorized: False
```
<!-- FW-RT6-0b-B-VOICE-OUTPUT-SESSION-HYGIENE:END -->

<!-- FW-RT6-0b-C-VERSION-METADATA:BEGIN -->
## v6.0.0 development: central version and schema metadata

FW-RT6-0b Control C defines source-development and frozen public-contract
versions in one provider-safe module:

```text
framework/version.py
```

The source version identifies the unreleased v6 development line:

```text
framework.__version__: 6.0.0.dev0
latest published release: 5.5.0
```

`framework.__version__` is metadata and is intentionally not added to
`framework.__all__`; the canonical root-public compatibility inventory remains
95 names.

Existing public session and schema values are preserved:

```text
TextChatSessionInfo.api_version: 4.0
VoiceOutputSessionInfo.boundary_version: v5.lazy_provider_adapter
VoiceInputSessionInfo.api_version: 5.2.0
RealtimeSessionInfo.api_version: 5.2.0
MotionSessionInfo.api_version: 5.5.0
FrameworkCapabilities.schema_version: v5.1.capabilities
```

This checkpoint centralizes the literals only. It does not claim that v6.0.0 is
released, correct the known capability-truthfulness gap, compose a real
realtime runtime, import a provider SDK, or execute a network, microphone,
playback, or motion operation.

```text
checkpoint: FW-RT6-0b Control C
status: IMPLEMENTED / AWAITING_REVIEW
public API values changed: False
capability truthfulness changed: False
next control: FW-RT6-0b Control D
next control authorized: False
```
<!-- FW-RT6-0b-C-VERSION-METADATA:END -->

<!-- FW-RT6-0c-B-RESOURCE-RESOLUTION:BEGIN -->
## Installable resource resolution

Public text-chat sessions resolve presets and character data independently of
the process working directory. Existing four text factory parameters remain
positional-compatible; `project_root` is an optional keyword-only compatibility
override for preset and character resources.

Resolution order is explicit `project_root`, then bundled package resources.
Invalid resource names and missing resources return path-safe public errors.
The default public voice-output artifact directory is the system temporary
area under `ai-character-framework/voice_output`, not `./temp/voice_output`.
<!-- FW-RT6-0c-B-RESOURCE-RESOLUTION:END -->

<!-- FW-RT6-1a-A-PUBLIC-IDENTITY:BEGIN -->
## v6 provider-neutral public identity primitives

FW-RT6-1a Control A adds four root-public serialization-friendly identity
types:

```text
SessionId
TurnId
GenerationId
EventSequence
```

The original 95 public names remain in the same order and the new names are
appended, producing 99 canonical root-public names. Framework identities use
kind-specific `fw_*` prefixes and never reuse provider request IDs, paths,
credentials, model IDs, or transport identifiers.

Result correlation fields are policy-locked but not yet wired in this control.
Realtime adoption is Control B, Motion adoption is Control C, and ordered event
sequence/generation fields remain FW-RT6-1c.

```text
checkpoint: FW-RT6-1a Control A
status: IMPLEMENTED / AWAITING_REVIEW
runtime behavior changed: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1a Control B
next control authorized: False
```
<!-- FW-RT6-1a-A-PUBLIC-IDENTITY:END -->

<!-- FW-RT6-1a-B-REALTIME-IDENTITY-ADOPTION:BEGIN -->
## FW-RT6-1a Control B — realtime identity adoption

Framework-generated realtime sessions and turns now use the root-public
`SessionId` and `TurnId` scalar types. Existing host applications may continue
to pass legacy non-`fw_` string identifiers; those values remain strings. A
valid serialized v6 identity is normalized to its public scalar type, while a
wrong-kind or malformed value in the reserved `fw_` namespace is rejected.

```text
checkpoint: FW-RT6-1a Control B
baseline head: 0b435e407a3fec018dce29b7446082948d1d2307
status: IMPLEMENTED / AWAITING_REVIEW
Framework-generated session identity: SessionId
Framework-generated turn identity: TurnId
legacy host session/turn strings: PRESERVED
valid serialized v6 identities: NORMALIZED
wrong-kind or malformed fw_* identity: REJECTED
root-public names: 99 / UNCHANGED
RealtimeEvent sequence/generation wiring: False
terminal behavior changed: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1a Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```

This compatibility path does not promote arbitrary provider request IDs to
Framework-owned identities. Only Framework-generated IDs use the `fw_session_`
and `fw_turn_` formats. Event sequencing, generation correlation, and terminal
model changes remain later controls.
<!-- FW-RT6-1a-B-REALTIME-IDENTITY-ADOPTION:END -->

<!-- FW-RT6-1a-C-MOTION-IDENTITY-ADOPTION:BEGIN -->
## FW-RT6-1a Control C — motion identity adoption

Framework-generated `MotionSession` instances now use the root-public
`SessionId` scalar. `MotionSessionInfo`, `MotionResult`, and callback mappings
preserve one stable session identity across mock, guarded, closed, and composed
VTube Studio paths. Callback mappings serialize the identity as a plain JSON
string.

```text
checkpoint: FW-RT6-1a Control C
baseline head: f740b374a35ed1a448beb6dc17a25427acb547fc
status: IMPLEMENTED / AWAITING_REVIEW
Framework-generated MotionSession identity: SessionId
MotionResult session_id adoption: IMPLEMENTED
legacy host session strings: PRESERVED
valid serialized SessionId: NORMALIZED
wrong-kind or malformed fw_* identity: REJECTED
callback session_id serialization: JSON STRING
MotionRequest request_id changed: False
GenerationId promoted from MotionRequest request_id: False
MotionResult turn_id/generation_id fields added: False
root-public names: 99 / UNCHANGED
VTS composition behavior changed: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1a Control D
next control authorized: False
commit / push: NOT_AUTHORIZED
```

This control does not invent turn or generation identities for standalone motion
operations. Text, voice-input, and voice-output result correlation remains
deferred, and ordered event sequencing remains FW-RT6-1c.
<!-- FW-RT6-1a-C-MOTION-IDENTITY-ADOPTION:END -->

<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:BEGIN -->
## FW-RT6-1b Control A — public lifecycle primitives

The root-public SDK now defines separate transient phase, terminal turn outcome,
recovery action, and typed transition failure models:

```text
RealtimePhase
TurnOutcome
RecoveryAction
LifecycleTransitionErrorCode
LifecycleTransitionError
```

The original 99 public names remain in the same order and these five names are
appended, producing 104 names. `RealtimeState` and current session/result runtime
behavior remain unchanged in this control. Host applications should treat the
new models as the canonical v6 vocabulary, but must not assume that the current
mock-safe `RealtimeSession` has adopted them until Controls B and C are accepted.

```text
checkpoint: FW-RT6-1b Control A
baseline head: c89ca5f0ae186564a8f7bced2ea7ce1462459172
status: IMPLEMENTED / AWAITING_REVIEW
invalid phase transition: LifecycleTransitionError
first terminal validation: ACCEPTED
terminal registry / duplicate suppression runtime: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1b Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:END -->

<!-- FW-RT6-1b-B-TURN-OUTCOME-ADOPTION:BEGIN -->
## FW-RT6-1b Control B — turn outcome and recovery adoption

`RealtimeTurnResult` now normalizes every terminal result to the root-public
`TurnOutcome` model and exposes one normalized `RecoveryAction`. Existing
terminal `RealtimeState` inputs and value comparisons remain compatible, while
transient states are rejected with `LifecycleTransitionError` code
`phase_outcome_mismatch`.

```text
checkpoint: FW-RT6-1b Control B
baseline head: 6443e524d8bc4e32eb4d7e7ecba75e26244c9f10
status: IMPLEMENTED / AWAITING_REVIEW
RealtimeTurnResult canonical outcome: TurnOutcome
RealtimeTurnResult recovery_action: RecoveryAction
completed default recovery: none
interrupted default recovery: reset_turn
cancelled default recovery: reset_turn
failed default recovery: reset_session
rejected default recovery: reuse_session
closed default recovery: none
cancelled and interrupted: DISTINCT
legacy terminal RealtimeState input/value comparison: PRESERVED
transient RealtimeState as terminal outcome: TYPED REJECTION
RealtimeSession phase adoption: DEFERRED TO CONTROL C
terminal registry: NOT IMPLEMENTED
RealtimeEvent sequence/generation/terminal fields: NOT ADDED
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1b Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```

`rejected` means that active-turn ownership was not acquired. `cancelled` means
an admitted turn ended through an explicit host/session cancellation request.
`interrupted` means an admitted turn ended through barge-in or another
asynchronous interruption. Recovery values describe the next safe action and do
not claim that reset, reconnect, close, or provider hard cancellation already
completed.
<!-- FW-RT6-1b-B-TURN-OUTCOME-ADOPTION:END -->

<!-- FW-RT6-1b-C-REALTIME-PHASE-ADOPTION:BEGIN -->
## Realtime canonical phase guidance

FW-RT6-1b Control C adds `session.phase` as the canonical transient lifecycle
surface. Host applications should inspect `RealtimePhase` for current progress
and `TurnOutcome` for terminal turn meaning.

```python
phase = session.phase
result = session.run_turn(input_text="hello")

assert result.outcome is TurnOutcome.COMPLETED
assert session.phase is RealtimePhase.IDLE
```

The legacy `session.state`, `session.info.state`, and `RealtimeEvent.state`
contracts remain available for v5 compatibility. They are not the canonical v6
terminal model. A closed session has `session.phase is None` and retains
`session.state == RealtimeState.CLOSED`.

This control does not add a canonical phase field to `RealtimeEvent`; ordered v6
event phase, sequence, generation, terminal, and typed payload work remains
FW-RT6-1c.
<!-- FW-RT6-1b-C-REALTIME-PHASE-ADOPTION:END -->

<!-- FW-RT6-1c-A-TYPED-PAYLOADS:BEGIN -->
## Typed realtime event payload foundation

FW-RT6-1c Control A adds eight root-public immutable payload dataclasses and one
public payload-kind discriminator. Host applications may construct, inspect,
and serialize these provider-neutral payloads without importing Framework
internal modules or provider SDKs.

```text
baseline head: 285e546d7065eee24d144a4fc39da82d3097bd1f
root-public prefix preserved: 104 names / SAME ORDER
canonical root-public total: 114
RealtimeEvent payload field adopted: False
RealtimeSession ordered payload emission: False
provider object or raw provider payload exposed: False
```

The payload models distinguish transcript partial/final and response
delta/completed meaning at the data-model level. Control A does not yet attach
them to `RealtimeEvent`; envelope, compatibility adapter, and ordered session
emission work remain Controls B through D.
<!-- FW-RT6-1c-A-TYPED-PAYLOADS:END -->

<!-- FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE:BEGIN -->
## FW-RT6-1c Control B — RealtimeEvent v6 envelope

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Baseline:

```text
a29b90cadcb6b7917499c30cbe753d2c72ea353b
```

`RealtimeEvent` preserves its accepted v5 constructor prefix and legacy
`as_dict()` mapping while appending an optional canonical v6 envelope. The
envelope normalizes Framework-owned sequence and generation identities, the
last observed transient phase, one typed Control A payload, terminal meaning,
and optional public timestamps.

```text
accepted root-public count: 114 / UNCHANGED
legacy RealtimeEvent field prefix: PRESERVED
legacy RealtimeEvent.as_dict keys: PRESERVED
new suffix: sequence / generation_id / phase / payload / terminal / timestamp / monotonic_timestamp
sequence continuity enforcement: False
generation lifecycle ownership: False
automatic clock reads: False
RealtimeSession canonical emission: False
v5 mapping adapter: DEFERRED / CONTROL C
terminal registry / exactly-once suppression: NOT IMPLEMENTED
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1c Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```

`EventSequence` is the authoritative ordering scalar when present. Timestamps
are optional non-negative finite public values and do not establish ordering. A
terminal flag must agree with the event type; this fixes envelope semantics but
does not suppress duplicate terminal events.
<!-- FW-RT6-1c-B-REALTIME-EVENT-ENVELOPE:END -->

<!-- FW-RT6-1c-C-V5-EVENT-ADAPTER:BEGIN -->
## Explicit v5 projection for canonical realtime events

Host applications that still consume the v5 event vocabulary may call
`event.to_v5()` or `event.as_v5_dict()`. Existing v5 events are identity
projections. Canonical v6 events use a fixed immutable mapping, and events with
no honest v5 equivalent return `None`.

```text
checkpoint: FW-RT6-1c Control C
baseline head: 532d7852bfe9370514180800a84bfc0a8e13fa9c
root-public names: 114 / UNCHANGED
legacy callback wiring: UNCHANGED
RealtimeSession ordered v6 emission: DEFERRED TO CONTROL D
partial transcript promoted to completion: False
response delta promoted to completion: False
provider/network/microphone/playback/VTS execution: False
```

The adapter preserves v6 correlation fields on the returned `RealtimeEvent`,
while `as_v5_dict()` intentionally returns only the established ten-key legacy
mapping.
<!-- FW-RT6-1c-C-V5-EVENT-ADAPTER:END -->

<!-- FW-RT6-1c-D-ORDERED-EVENT-ADOPTION:BEGIN -->
## Ordered canonical and legacy realtime callbacks

`RealtimeSession.on_event(callback)` is the canonical v6 callback path. Events
carry session-lifetime `EventSequence`, per-admitted-turn `GenerationId`, typed
payload, terminal state, and automatic public/monotonic timestamps.

`RealtimeSession.on_legacy_event(callback)` is the compatibility path. It emits
only the explicit v5 projections and preserves the correlation and ordering
fields of the canonical source event. `LISTENING_COMPLETED` is intentionally not
projected; `TRANSCRIPT_FINAL` supplies the single legacy voice-input completion.

```text
checkpoint: FW-RT6-1c Control D
baseline head: 007e1577a18c92a1dafdf9ede814b97dc2d0a05c
canonical completed-turn order: 9 events / ADOPTED
legacy completed-turn order: 8 events / ADOPTED
EventSequence starts at 1: True
EventSequence resets between turns: False
GenerationId changes per admitted turn: True
session-only generation: None
rejected-before-admission generation: None
root-public names: 114 / UNCHANGED
terminal registry / exactly-once suppression: DEFERRED
stale-result rejection / overflow queue: DEFERRED
provider/network/microphone/playback/VTS execution: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1c-D-ORDERED-EVENT-ADOPTION:END -->

<!-- FW-RT6-1d-A-DETAILED-CAPABILITY-MODELS:BEGIN -->
## Detailed realtime capability model foundation

FW-RT6-1d Control A appends seven immutable root-public models for truthful
capability reporting. `RuntimeCapabilityState` separates configured, runtime
availability, execution guard, fake runtime, real runtime, and a safe
unavailable reason. Stage-specific capability models expose text generation,
voice input, voice output, and motion details without provider objects.

`RealtimeCapabilitySnapshot` supports global and session scope, requires a
positive snapshot generation, and retains the existing v5 realtime summary
booleans as compatibility fields. Session scope requires a public `session_id`.

```text
checkpoint: FW-RT6-1d Control A
baseline head: 4709f0190f3779b83b8cb01a0cd67f6760ff8e35
root-public prefix: 114 names / SAME ORDER
canonical root-public total: 121
new detailed schema: v6.realtime_capabilities
frozen v5.1 capabilities schema changed: False
FrameworkCapabilities builder changed: False
RealtimeSession wiring changed: False
provider/network/microphone/playback/VTS execution: False
```
<!-- FW-RT6-1d-A-DETAILED-CAPABILITY-MODELS:END -->

<!-- FW-RT6-1d-B-GLOBAL-CAPABILITY-AGGREGATION:BEGIN -->
## FW-RT6-1d Control B — truthful global capability aggregation

`get_capabilities()` preserves the v5.1 `FrameworkCapabilities` return type,
keyword-only signature, five summary fields, and `v5.1.capabilities` schema. The
builder no longer reports voice input, realtime, and motion as missing public
boundaries. Their deterministic mock-safe public runtimes are reported as
available fallback capabilities, while real provider or transport success is not
claimed.

The additive `FrameworkCapabilities.realtime_snapshot` field contains one
`v6.realtime_capabilities` global snapshot built from the same authoritative
facts. It separates configured, runtime availability, guard state, fake runtime,
real runtime, and unavailable reason for every stage.

```text
checkpoint: FW-RT6-1d Control B
baseline head: a27b3e17ff7d8158859a5a624e3b03225384bfc8
Control B exact change surface: 10 files
root-public names: 121 / UNCHANGED
v5 compatibility schema: v5.1.capabilities / PRESERVED
detailed schema: v6.realtime_capabilities
voice input summary reason: mock_voice_input_available
realtime summary reason: mock_realtime_available
motion summary reason: mock_motion_available
voice output real runtime default: UNAVAILABLE
provider hard cancel supported: False
TTS pending flush supported: False
RealtimeSession snapshot adoption: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1d Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1d-B-GLOBAL-CAPABILITY-AGGREGATION:END -->

<!-- FW-RT6-1d-C-SESSION-CAPABILITY-ADOPTION:BEGIN -->
## FW-RT6-1d Control C — session-scoped capability adoption

`RealtimeSession.capabilities` now returns one immutable
`RealtimeCapabilitySnapshot` scoped to that Framework-owned session. The
snapshot uses the session's public `SessionId`, starts at generation `1`, and
remains stable for the current session lifetime because Control C adds no
capability refresh or runtime rebinding operation.

The snapshot reports the behavior of the current mock-safe `RealtimeSession`,
not merely the existence of standalone public boundaries:

```text
text generation fake runtime: available
response streaming from RealtimeSession: False
cooperative/provider hard cancel: False / False
voice input fake runtime: available
partial transcript / audio chunk input: False / False
final transcript event: True
voice output fake synthesis stage: available
streaming/cancel/pending flush/audio invalidation: False
motion wired into RealtimeSession: False
real unified runtime available: False
```

Passing `real_runtime_enabled=True` remains a host intent assertion only. The
session records `real_runtime_requested=true` in public-safe metadata but does
not claim that real unified orchestration is available or enabled.

```text
checkpoint: FW-RT6-1d Control C
baseline head: 30166d7e6fdf4291d7ecd475b988bfd1492ae7a3
Control C exact change surface: 6 files
root-public names: 121 / UNCHANGED
create_realtime_session signature changed: False
snapshot scope: session
snapshot generation: 1 / stable
snapshot session_id matches RealtimeSession: True
FrameworkCapabilities global snapshot changed: False
provider/network/microphone/playback/VTS execution: False
terminal registry / stale rejection / queue runtime: DEFERRED
next control: FW-RT6-1d Control D
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1d-C-SESSION-CAPABILITY-ADOPTION:END -->

<!-- FW-RT6-2a-A-PUBLIC-SAFETY-PRIMITIVES:BEGIN -->
## FW-RT6-2a Control A — recursive public-safety primitives

The Framework now contains one provider-neutral recursive sanitizer and safe
error-classification foundation in `framework.public_safety`.

Control A changes no existing public session/model consumer. Existing shallow
`_public_mapping` / `_redact_mapping` helpers and the TextChat raw error-event
path remain explicit follow-up work.

```text
baseline head: 463496642f87daac1d280001d0385da1277a9f42
Control A exact change surface: 5 files
root-public names: 121 / UNCHANGED
recursive mapping/list/tuple/dataclass sanitization: IMPLEMENTED
secret-like key policy centralized: IMPLEMENTED
private path redaction primitive: IMPLEMENTED
raw exception serialization by utility: False
safe error classification primitive: IMPLEMENTED
existing consumer migration: DEFERRED / Control B
TextChat raw error event correction: DEFERRED / Control C
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-2a Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2a-A-PUBLIC-SAFETY-PRIMITIVES:END -->

<!-- FW-RT6-2a-B-CORE-CONSUMER-MIGRATION:BEGIN -->
## FW-RT6-2a Control B — core public metadata consumer migration

Five established private `_public_mapping` helpers now delegate to
`framework.public_safety.public_mapping()`:

```text
framework/realtime.py
framework/voice_input.py
framework/motion.py
framework/output_control.py
framework/realtime_capabilities.py
```

The private helper names remain as compatibility wrappers. Their behavior is
upgraded from shallow redaction/copying to recursive immutable sanitization.

```text
baseline head: b351cf74a5b20e55a4aede8746841c05a58bfbb9
Control B exact change surface: 9 files
root-public names: 121 / UNCHANGED
core compatibility helpers delegated: 5
nested credential redaction: PASS
nested private path redaction: PASS
raw exception retained: False
TextChat raw error event correction: DEFERRED / Control C
all repository metadata paths claimed migrated: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-2a Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2a-B-CORE-CONSUMER-MIGRATION:END -->

<!-- FW-RT6-2a-C-TEXT-CHAT-ERROR-SAFETY:BEGIN -->
## FW-RT6-2a Control C — TextChat public error safety

`TextChatSession.ask_stream()` preserves its existing exception re-raise behavior,
but its public `error` event no longer contains a raw exception string or
exception class name.

The event now exposes only:

```text
public_error_code
safe_message
retryable
public_metadata
```

`TextChatSession.ask_result()` and the streaming error event use the same
provider-neutral classification helper. Classification is based on known
exception types and the text-chat operation context; it does not inspect
`str(error)`, `repr(error)`, provider payloads, or exception class names.

```text
baseline head: 4e1cf483f9e6568033e2b9b00e6bb7d3b0d404f9
Control C exact change surface: 5 files
root-public names: 121 / UNCHANGED
TextChatSessionEvent public type: UNCHANGED
ask_stream exception re-raise: PRESERVED
raw exception string in error event: False
exception class name in error event: False
ask_result safe classifier adoption: True
streaming event safe classifier adoption: True
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-2a Control D
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2a-C-TEXT-CHAT-ERROR-SAFETY:END -->

<!-- FW-RT6-2b-A-EVENT-HUB-PRIMITIVES:BEGIN -->
## FW-RT6-2b Control A — realtime event-hub primitives

Control A adds an internal provider-neutral event hub foundation. It does not
change `RealtimeSession`, root-public names, current callback signatures, or
runtime stage behavior.

The primitive provides:

```text
session-local EventSequence allocation
opaque callback registration token
canonical / legacy callback channels
callback exception isolation
synchronous serialized delivery
bounded event history
slow subscriber accounting
non-silent overflow factory and counters
concurrent / reentrant emission serialization
idempotent close and post-close rejection
```

The initial slow-subscriber policy is deterministic:

```text
delivery:
synchronous and serialized

automatic timeout:
False

automatic eviction:
False

exception escapes emitter:
False

slow callback:
retained and counted
```

```text
baseline head: 89c0ba7ccf150658c5bace612e68bce876db4223
Control A exact change surface: 5 files
root-public names: 121 / UNCHANGED
RealtimeSession adoption: DEFERRED / Control B
typed RealtimeEvent overflow adoption: DEFERRED / Control B
close-path integration hardening: DEFERRED / Control C
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-2b Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2b-A-EVENT-HUB-PRIMITIVES:END -->

<!-- FW-RT6-2b-B-REALTIME-SESSION-HUB-ADOPTION:BEGIN -->
## FW-RT6-2b Control B — RealtimeSession event-hub adoption

`RealtimeSession` now delegates canonical and legacy callback registration,
session-lifetime sequence allocation, callback delivery, bounded history, and
overflow accounting to the accepted Control A event hub.

The existing callback methods remain source-compatible when their return values
are ignored. They now return opaque string tokens:

```text
on_event(callback) -> str
on_legacy_event(callback) -> str
off_event(token) -> bool
```

`off_event()` removes either callback channel by token and is idempotent.

The session exposes immutable snapshots:

```text
event_history:
tuple[RealtimeEvent, ...]

event_diagnostics:
Mapping[str, int]
```

The fixed initial runtime policy is:

```text
history limit:
64 events

delivery:
synchronous / serialized

callback exception breaks turn:
False

slow callback:
retained and counted

overflow:
typed RealtimeEventType.EVENT_OVERFLOW

overflow payload:
DiagnosticEventPayload

overflow v5 projection:
None
```

The event that fills an already-full history is accepted first. Its typed
overflow diagnostic is then accepted with the next `EventSequence`. Both are
included in canonical delivery and bounded history. The overflow event does not
enter the legacy callback channel.

```text
baseline head: cee3f68ec3254a8d99a7f4c0e1f911deb1f3496f
Control B exact change surface: 5 files
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeSession factory signature changed: False
canonical completed-turn order changed: False
legacy completed-turn order changed: False
callback exception breaks turn: False
bounded event history adopted: True
typed EVENT_OVERFLOW adopted: True
post-close active-event rejection: DEFERRED / Control C
session lifecycle state lock hardening: DEFERRED / Control C
terminal registry: DEFERRED / FW-RT6-2c
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-2b Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2b-B-REALTIME-SESSION-HUB-ADOPTION:END -->

<!-- FW-RT6-2b-C-CLOSE-CONCURRENCY-HARDENING:BEGIN -->
## FW-RT6-2b Control C — close and operation-order hardening

`RealtimeSession` now owns an operation-level reentrant lock around event-producing
public operations. A concurrent operation waits for the current operation to
finish, so its lifecycle-state writes and event groups do not interleave.

A same-thread `close()` request raised from an event callback is deferred until
the outer operation finishes. The admitted operation therefore completes its
already-started event sequence before one `SESSION_CLOSED` event is emitted.

```text
serialized operations:
emit_created
run_turn
interrupt
flush_output
decide_barge_in
set_barge_in_policy
close

reentrant close during operation:
deferred

concurrent close during operation:
waits for operation boundary

SESSION_CLOSED event:
emitted once

hub seal:
immediately after SESSION_CLOSED delivery

callbacks retained after close:
False
```

After close, public methods preserve typed result behavior without emitting any
new active event:

```text
run_turn:
RealtimeTurnResult.closed / no event

interrupt:
InterruptResult.already_closed / no event

flush_output:
OutputFlushResult.closed / no event

decide_barge_in:
rejected decision / no event

emit_created:
LifecycleTransitionError(SESSION_CLOSED) / no event

set_barge_in_policy:
LifecycleTransitionError(SESSION_CLOSED) / no event

on_event / on_legacy_event:
LifecycleTransitionError(SESSION_CLOSED)
```

The bounded history and typed overflow policy from Control B are unchanged.
An overflow diagnostic accepted during the close operation is part of that
operation; after `close()` returns, no event can be accepted.

```text
baseline head: ee896aad3c9f6d38521c3da08505e77f0c60c1c0
Control C exact change surface: 7 files
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeSession factory signature changed: False
operation-level lock: RLock
reentrant close deferred: True
concurrent operation groups interleave: False
SESSION_CLOSED emitted once: True
event hub closed after close: True
close後active event: False
terminal registry: DEFERRED / FW-RT6-2c
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-2b Control D
next control authorized: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2b-C-CLOSE-CONCURRENCY-HARDENING:END -->

<!-- FW-RT6-2c-A-TERMINAL-REGISTRY-PRIMITIVES:BEGIN -->
## FW-RT6-2c Control A — terminal registry primitive foundation

Control A adds an internal provider-neutral terminal registry primitive. It is
not exported from the Framework root and is not yet adopted by
`RealtimeSession`.

```text
registry scope:
one future RealtimeSession

registry key:
TurnId or compatible legacy turn string

first terminal commit:
accepted atomically

same-outcome retry:
duplicate_terminal / suppressed

different-outcome retry:
terminal_regression / suppressed

late non-terminal admission:
rejected after terminal commit

terminal record:
immutable

terminal reason/result retention:
internal record

diagnostics:
counts only

duplicate/regression exception escapes caller:
False

multi-thread first-terminal winner:
exactly one

root-public names:
121 / unchanged
```

The first accepted record retains normalized `TurnOutcome`,
`RecoveryAction`, a reason string, and an optional typed result object. Later
attempts never replace that record.

The primitive uses the accepted `validate_terminal_transition(...)` semantics
but converts duplicate/regressive attempts into immutable suppression decisions
instead of raising through the runtime path.

```text
RealtimeSession adoption:
DEFERRED / FW-RT6-2c Control B

terminal event/result integration:
DEFERRED / FW-RT6-2c Control B

integration race and late-event hardening:
DEFERRED / FW-RT6-2c Control C

generation stale-result rejection:
DEFERRED / FW-RT6-2d

provider/network/microphone/playback/VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2c-A-TERMINAL-REGISTRY-PRIMITIVES:END -->

<!-- FW-RT6-2c-B-REALTIME-SESSION-TERMINAL-ADOPTION:BEGIN -->
## FW-RT6-2c Control B — RealtimeSession terminal-registry adoption

`RealtimeSession` now owns one internal `RealtimeTerminalRegistry` and routes its
current mock `TURN_COMPLETED` event/result path through one first-terminal
commit boundary.

```text
registry scope:
one RealtimeSession

current session-owned terminal path:
TURN_COMPLETED

terminal ownership commit:
before terminal event delivery

terminal callback observes committed result:
True

same turn_id run_turn retry:
returns first committed result

same turn_id retry emits lifecycle events:
False

same turn_id retry terminal event:
False

first terminal event count per turn:
1

first terminal result replaced:
False
```

The accepted result is stored before the terminal event is delivered. Because
callback delivery is synchronous, a `TURN_COMPLETED` callback can read
`terminal_results` and `terminal_diagnostics` and observe the committed record.

New public `RealtimeSession` read-only surfaces:

```text
terminal_results:
tuple[RealtimeTurnResult, ...]

terminal_diagnostics:
Mapping[str, int]
```

`terminal_results` contains the stored first-terminal results in commit order.
`terminal_diagnostics` contains count-only registry diagnostics:

```text
terminal_commit_count
duplicate_terminal_count
terminal_regression_count
late_non_terminal_count
registry_size
```

No internal registry class or record class is exported from the Framework root.
`RealtimeEvent`, `RealtimeTurnResult`, and the session factory signature remain
unchanged.

```text
root-public names:
121 / unchanged

RealtimeEvent public model changed:
False

RealtimeTurnResult public model changed:
False

create_realtime_session signature changed:
False

event_diagnostics keys changed:
False

terminal reason/result retained:
True

duplicate terminal event suppression:
ADOPTED FOR CURRENT SESSION TERMINAL PATH

reentrant late non-terminal rejection:
DEFERRED / FW-RT6-2c Control C

multi-thread session integration race:
DEFERRED / FW-RT6-2c Control C

generation stale-result rejection:
DEFERRED / FW-RT6-2d

provider/network/microphone/playback/VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2c-B-REALTIME-SESSION-TERMINAL-ADOPTION:END -->

<!-- FW-RT6-2c-C-REENTRANT-LATE-NON-TERMINAL:BEGIN -->
## FW-RT6-2c Control C — reentrant late non-terminal rejection

Control C applies the session terminal registry to every turn-scoped
non-terminal transition before phase, state, sequence, history, or callback
mutation.

```text
turn_id is None:
not a turn-registry admission

TURN_COMPLETED / TURN_INTERRUPTED / TURN_CANCELLED / TURN_FAILED / TURN_REJECTED:
terminal path / not a non-terminal admission

SESSION_CLOSED:
session terminal / not classified as a turn terminal

all other events with a turn_id:
RealtimeTerminalRegistry.admit_non_terminal(turn_id) required
```

A rejected late transition stops the current public operation immediately. It
emits no diagnostic event, allocates no sequence, adds no history entry, invokes
no callback, and does not change session phase, state, active generation, or the
first terminal record.

```text
late rejection diagnostics:
terminal_diagnostics["late_non_terminal_count"] only

STALE_RESULT_DROPPED:
not used / deferred to FW-RT6-2d

event_diagnostics keys:
unchanged
```

Existing typed results are reused without adding a root-public type:

```text
late interrupt / cancel_current_turn:
InterruptResult.no_active_turn

late output flush:
OutputFlushResult.nothing_to_flush

late barge-in decision:
BargeInDecision.rejected

same terminal turn run_turn retry:
first committed RealtimeTurnResult object
```

`cancel_current_turn()` now resolves the active turn while holding the accepted
session operation lock. Concurrent same-session operations remain serialized.
For concurrent `run_turn(...)` calls with one shared turn ID, exactly one full
lifecycle group executes; all other callers return the first committed result
without emitting a duplicate lifecycle group.

```text
root-public names:
121 / unchanged

RealtimeEvent public model changed:
False

RealtimeTurnResult public model changed:
False

create_realtime_session signature changed:
False

provider/network/microphone/playback/VTS execution:
False

generation stale-result rejection:
DEFERRED / FW-RT6-2d

aggregate tasklist/gap sync:
DEFERRED / FW-RT6-2c Control D

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2c-C-REENTRANT-LATE-NON-TERMINAL:END -->

<!-- FW-RT6-2d-A-GENERATION-GATE-PRIMITIVES:BEGIN -->
## FW-RT6-2d Control A — provider-neutral generation gate primitives

Control A adds an internal session-agnostic freshness primitive for future
realtime stage completions. It does not wire `RealtimeSession`, emit
`STALE_RESULT_DROPPED`, change the public event envelope, or execute a provider.

`RealtimeGenerationGate.start_generation(turn_id)` creates a fresh opaque
GenerationId for one admitted turn. Starting another generation first retires
the active generation with `GenerationAdvanceReason.NEW_TURN`.

```text
GenerationAdvanceReason:
new_turn
interrupt
cancel
reset
session_closed
turn_terminal
```

`RealtimeStageCompletionEnvelope` carries one internal stage completion:

```text
turn_id
generation_id
stage
value (internal / repr=False)
```

`RealtimeGenerationGate.admit_completion(envelope)` performs one atomic
freshness decision:

```text
current generation + matching turn:
ACCEPTED

retired generation:
STALE / retired_generation / retirement reason retained

unknown generation:
STALE / unknown_generation

current generation + different turn:
STALE / turn_mismatch
```

The generation gate does not impose single-consumer semantics. Multiple
completions from one current generation may be accepted. Terminal exactly-once
ownership remains the responsibility of the accepted terminal registry.

Read-only primitive diagnostics are immutable and count-only:

```text
generation_start_count
generation_advance_count
accepted_completion_count
stale_completion_count
active_generation_count
registry_size
```

No-active `advance(...)` is an idempotent no-op and does not change diagnostics.
The internal module is not imported or exported by `framework` root.

```text
checkpoint:
FW-RT6-2d Control A

status:
IMPLEMENTED / AWAITING_REVIEW

exact change surface:
5 files

root-public names:
121 / unchanged

RealtimeSession adoption:
DEFERRED / Control B

STALE_RESULT_DROPPED runtime emission:
DEFERRED / Control B

VTS semantic alignment:
DEFERRED / Control C

provider/network/microphone/playback/VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2d-A-GENERATION-GATE-PRIMITIVES:END -->

<!-- FW-RT6-2d-B-REALTIME-SESSION-GENERATION-ADOPTION:BEGIN -->
## FW-RT6-2d Control B — RealtimeSession generation-gate adoption

Control B adopts the accepted Control A generation gate inside
`RealtimeSession`. The gate remains internal and is imported lazily when a
session instance is created, so `import framework` preserves provider/runtime
import safety and does not eagerly load the internal gate module.

```text
exact change surface:
6 files

root-public names:
121 / unchanged

RealtimeEvent public model changed:
False

RealtimeTurnResult public model changed:
False

create_realtime_session signature changed:
False
```

The sixth file is the accepted Control A primitive smoke. Its historical
candidate-surface assertion is advanced to the Control B candidate so the
primitive regression remains executable after session adoption.

### Session ownership and correlation

Each session owns one `RealtimeGenerationGate`. A new admitted turn starts a
fresh generation through the gate. `_active_generation_id` remains the
correlation identity for the currently executing event group, while the gate is
the freshness source of truth.

```text
new turn:
fresh generation / prior active generation retired by new_turn

terminal event:
retains the turn generation

first terminal commit:
generation retired by turn_terminal before terminal callback delivery
```

### Central completion ingress

All future stage completions must pass through one internal session ingress:

```text
_apply_stage_completion(envelope, deliver=...)
```

Freshness admission and `deliver(value)` execute under the same reentrant
session operation lock.

```text
current generation + matching turn:
accepted / delivered once

retired generation:
rejected / not delivered

unknown generation:
rejected / not delivered

current generation + different turn:
rejected / not delivered
```

A stale completion never mutates session state, phase, terminal registry, or the
original stage result surface.

### Typed stale diagnostic

When the session is open, one rejected completion emits one canonical v6-only
diagnostic:

```text
type:
STALE_RESULT_DROPPED

payload:
DiagnosticEventPayload

code:
stale_stage_completion

drop_reason:
retired_generation | unknown_generation | turn_mismatch

safe_message:
Stale realtime stage completion was dropped.

legacy projection:
None
```

The event retains the rejected envelope's turn and generation IDs. For a
retired generation, `public_metadata.retired_by` contains only the stable
retirement reason. Completion values, provider objects, raw payloads, raw
exceptions, private paths, endpoints, and credentials are not copied.

After `close()` is requested, stale completion delivery remains rejected but no
new stale diagnostic event is emitted. Count-only observability remains
available through `generation_diagnostics`.

### Advance ordering

```text
normal first terminal:
turn_terminal before terminal event callbacks

interrupt of current generation:
interrupt before INTERRUPT_REQUESTED

cancel_current_turn:
cancel before INTERRUPT_REQUESTED

first close request:
session_closed before deferred-close decision

no-active interrupt:
no advance

unrelated explicit-turn interrupt:
current generation preserved

duplicate close:
no advance
```

No public reset method is added. `reset` remains a defined internal retirement
reason for a later reset boundary.

### Additive diagnostics

`RealtimeSession.generation_diagnostics` is an immutable read-only mapping with
exact keys:

```text
generation_start_count
generation_advance_count
accepted_completion_count
stale_completion_count
active_generation_count
registry_size
```

Existing `event_diagnostics` and `terminal_diagnostics` keys remain unchanged.

```text
checkpoint:
FW-RT6-2d Control B

status:
IMPLEMENTED / AWAITING_REVIEW

Control A:
ACCEPTED / REGRESSION VERIFIED

Control C race and VTS alignment:
NOT_AUTHORIZED

provider/network/microphone/playback/VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2d-B-REALTIME-SESSION-GENERATION-ADOPTION:END -->

<!-- FW-RT6-2d-C-RACE-VTS-ALIGNMENT:BEGIN -->
## FW-RT6-2d Control C — generation race and VTS alignment

Control C is docs/test-only. The accepted Control B runtime source is unchanged.
It verifies that stage-completion application and every generation-invalidating
operation are linearized by the same reentrant session operation lock.

```text
exact change surface:
6 files / docs-test-only

runtime source changed:
False

root-public names:
121 / unchanged
```

### Session race rule

The operation that first owns the session operation lock wins.

```text
completion application wins:
freshness accepted / deliver(value) completes before invalidation

generation advance wins:
completion stale / deliver(value) is never called
```

The rule is verified for interrupt, cancel, close, and new-turn replacement.
First terminal commit retires the generation by `turn_terminal` before terminal
callback delivery. A same-generation completion re-entered from the terminal
callback is stale and cannot change the retained terminal result.

Stale text-generation deltas, voice-output artifacts, and motion completions are
not copied into their original delivery surfaces. Open-session drops emit one
canonical v6-only `STALE_RESULT_DROPPED`; close-requested and post-close drops
remain count-observable without post-close event emission.

### VTube Studio alignment

The existing VTube Studio transport source is not changed. Its operation-local
`_lifecycle_generation` capture, post-await generation checks, and close-time
generation increment implement the same semantic rule:

```text
operation completion before close generation advance:
completion may be applied

close generation advance before operation completion:
late completion suppressed
```

Control C verifies source ordering and executes an injected in-memory async
client. It does not import real `pyvts`, open a network connection, read private
configuration, trigger a real hotkey, or execute real motion.

```text
checkpoint:
FW-RT6-2d Control C

status:
IMPLEMENTED / AWAITING_REVIEW

Control A:
ACCEPTED / REGRESSION VERIFIED

Control B:
ACCEPTED / REGRESSION VERIFIED

race linearization:
VERIFIED

VTS lifecycle-generation alignment:
VERIFIED / SOURCE UNCHANGED

Control D:
NOT_AUTHORIZED

provider/network/microphone/playback/VTS execution:
False

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-2d-C-RACE-VTS-ALIGNMENT:END -->


<!-- FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:BEGIN -->
## v6.0.0 provider-neutral realtime stage protocol foundation

FW-RT6-3a Control A introduces `framework.realtime_stage` as an explicitly
stable public package. It defines `RealtimeStageContext`,
`RealtimeStageResultEnvelope`, the four provider-neutral stage kinds, and the
`VoiceInputStage`, `TextGenerationStage`, `VoiceOutputStage`, and `MotionStage`
protocols.

Every stage exposes `preflight`, `capability`, `start`, `cancel`, and `close`
without provider clients, raw provider payloads, provider cancel handles, private
paths, or credentials in the public signatures. Stage results retain
session/turn/generation correlation, and result values are omitted from envelope
`repr`.

Control A preserves the canonical 121-name root surface. The stage package is
available through explicit stable public package import; `framework` root does
not import it yet. RealtimeSession injection and factory changes are deferred to
Control B and are not authorized by this checkpoint.

```text
checkpoint: FW-RT6-3a Control A
baseline head: 6fe95075e1c9ae9e62150eb9844edfe9f004a8e2
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 5 files
stable public package: framework.realtime_stage
root-public names: 121 / UNCHANGED
RealtimeSession injection: DEFERRED / Control B
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:END -->
