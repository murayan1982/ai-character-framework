# App Integration Contract

This document describes the intended boundary between external application code and AI Character Framework.

The goal is to let apps use the framework as a library without depending on internal runtime details.

## Recommended import boundary

Application code should import from `framework`:

```python
from framework import FacadeError, create_text_chat_session
```

For voice output integrations, application code should also import only the public FW boundary:

```python
from framework import VoiceOutputRequest, create_voice_output_session
```

Avoid importing directly from internal packages such as `core`, `runtime`, `llm`, `tts`, `stt`, or `live2d` for app-facing integrations.

## Session creation

v4.0.0 keeps `create_text_chat_session()` as the stable public constructor for external app integration.

```python
session = create_text_chat_session()
```

For direct provider mode:

```python
session = create_text_chat_session(
    provider="openai",
    model="gpt-4o-mini",
)
```

If `provider` is omitted, the facade uses the default chat route with fallback.
If `provider` is provided, the facade uses direct provider mode.

A broader constructor such as `create_character_session()` is intentionally not introduced in v4.0.0.

Reason:

- v4.0.0 focuses on the text app integration SDK boundary.
- Voice, Live2D, realtime interruption, and always-on microphone behavior are not part of the v4.0.0 public session contract.
- A generic character session constructor could imply broader runtime support than this version guarantees.
- Future versions can add a broader constructor after the text session contract is stable.

## Public session metadata

Use `session.info` to inspect app-safe metadata:

```python
info = session.info

print(info.api_version)
print(info.session_type)
print(info.preset)
print(info.character_name)
print(info.llm_mode)
print(info.provider)
print(info.model)
print(info.output_language_code)
```

`session.info` is a `TextChatSessionInfo` instance.
It intentionally does not expose `RuntimeConfig`.

Apps may rely on these fields as the public text facade metadata contract:

- `preset`
- `character_name`
- `input_language_code`
- `output_language_code`
- `llm_mode`
- `provider`
- `model`
- `route_name`
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

In default route mode:

```python
info.llm_mode == "default_route"
info.provider is None
info.model is None
info.route_name == "chat"
```

In direct provider mode:

```python
info.llm_mode == "direct_provider"
info.provider == "openai"
info.model == "gpt-4o-mini"
info.route_name is None
```

## Stable text session contract

External apps may rely on the following text session operations:

```python
session.ask(text)
session.ask_stream(text)
session.reset()
session.interrupt()
session.on_event(callback)
session.on_state_change(callback)
```

These methods are part of the stable app-facing contract for text sessions.

### `ask(text)`

Sends one user message and returns one complete assistant response.

Expected app-facing behavior:

- accepts a non-empty text string
- returns a response string
- preserves conversation state within the session
- raises a `FacadeError` subclass for framework-level integration errors

### `ask_stream(text)`

Sends one user message and yields response chunks.

Expected app-facing behavior:

- accepts a non-empty text string
- yields text chunks
- preserves conversation state within the session
- may stop yielding future chunks after `interrupt()` is requested
- raises a `FacadeError` subclass for framework-level integration errors

### `reset()`

Clears the app-facing conversation state for the current session.

Expected app-facing behavior:

- keeps the session object usable
- clears previous conversation history/state where supported by the provider
- does not require the app to recreate the session
- does not expose internal runtime objects

Stateless providers may treat reset as a no-op.

### `interrupt()`

Requests interruption of the current app-facing text session operation.

In v4.0.0, this is a limited public boundary for app integration.

Text sessions can stop yielding future response chunks after an interrupt request is observed, but this does not guarantee provider-level cancellation of an already-running LLM request.

Expected app-facing behavior:

- keeps the session object usable
- returns whether the interrupt request was accepted
- may stop streaming output at a chunk boundary
- does not guarantee hard cancellation of active provider requests
- does not imply TTS queue cancellation
- does not imply realtime voice barge-in support

`session.info.supports_interrupt` means that this stable public method is available. It does not mean hard cancellation is supported.

## App-facing event callbacks

v4.0.0 exposes minimal app-facing callbacks on text sessions:

```python
session.on_event(callback)
session.on_state_change(callback)
```

These callbacks are intended for external application code.

They are separate from internal plugin hooks and should not require apps to import `core`, `plugins`, runtime objects, provider implementations, STT/TTS, or VTS modules.

### `on_event(callback)`

Registers a callback for app-facing session events.

```python
def handle_event(event):
    print(event.type)
    print(event.data)

session.on_event(handle_event)
```

Current text session event types:

- `response_started`
- `response_chunk`
- `response_completed`
- `reset`
- `interrupt_requested`
- `error`

### `on_state_change(callback)`

Registers a callback for app-facing session state changes.

```python
def handle_state_change(event):
    print(event.old_state)
    print(event.new_state)

session.on_state_change(handle_state_change)
```

Current text session states:

- `idle`
- `responding`
- `interrupted`
- `error`

### Boundary notes

App-facing events are best-effort notifications for external apps.

They do not expose internal runtime state, plugin hooks, provider objects, STT/TTS clients, VTS clients, or the plugin manager.

In v4.0.0, these callbacks apply to the text facade only.

## Error boundary

Catch public facade errors at the app boundary:

```python
try:
    session = create_text_chat_session(provider="openai", model="gpt-4o-mini")
    response = session.ask("Hello.")
except FacadeError as exc:
    print(f"Framework integration error: {exc}")
```

Public facade errors are:

- `FacadeError`
- `FacadeConfigError`
- `FacadeProviderError`

## What apps should not depend on

External apps should not depend on:

- `RuntimeConfig` shape
- internal route/fallback provider details
- provider implementation classes
- runtime session loop internals
- STT/TTS/VTS internals through app-facing facades
- provider voice IDs, API keys, model IDs, or provider-specific TTS parameters
- internal plugin hooks as the main app integration API

Those details may change across framework versions.

## Public voice output boundary

v5.0.0 adds a separate provider-neutral voice output boundary for host apps such as Daily Rhythm Companion. Apps request voice output through FW public types and do not own provider-specific implementation details.

```python
from framework import VoiceOutputRequest, create_voice_output_session

session = create_voice_output_session(
    default_voice_profile_id="gentle_mina_default",
)

result = session.create_output(
    VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )
)
```

The app-facing request should contain only FW-level voice output intent:

- `text`
- `voice_profile_id`
- `requested_audio_format`
- `utterance_purpose`
- `language_code`

FW owns and hides:

- provider selection
- provider voice IDs
- API keys
- model IDs
- provider-specific request parameters
- provider SDK calls
- local playback and temporary audio implementation details

Without explicit real TTS configuration, the public result is expected to be safe unavailable:

```python
result.request_state == "unavailable"
result.audio_ready is False
```

When a supported provider is configured but the FW execution guard is closed, the public result is expected to be safe skipped:

```python
result.request_state == "skipped"
result.audio_ready is False
```

These unavailable/skipped states are useful for app integration and smoke tests, but they are not real TTS evidence. Real DRC Web evidence still requires Web UI playback confirmation, screenshot/private evidence handling, marker-only evidence JSON, and acceptance validator success.

Run the DRC-style app example with no provider credentials:

```powershell
python examples/app_voice_output_integration.py
```

The example demonstrates that the app passes `VoiceOutputRequest` and keeps provider voice IDs, API keys, model IDs, and provider-specific options FW-side.

Before any configured real TTS run, use the FW opt-in and execution guard checks:

```powershell
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
```

See `voice_output_real_tts_opt_in_checklist.md` for the real TTS opt-in layers and evidence rules. See `voice_output_real_provider_execution_guard.md` for the final `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1` guard. Passing these FW checks means the boundary is ready for a deliberate configured real run; it does not mark DRC `real_tts_web_audio_output` as accepted.

## Text facade scope

`create_text_chat_session()` remains text-only. Voice output is available through the separate `create_voice_output_session()` boundary, not through the text chat session.

Supported:

- text input
- text output
- optional direct provider/model selection
- public session metadata
- public facade error classes
- streaming through `ask_stream()`
- reset through `reset()`
- limited interrupt boundary through `interrupt()`
- app-facing callbacks through `on_event()` and `on_state_change()`

Not supported through this facade yet:

- voice input
- Live2D / VTube Studio control
- full interactive runtime loop
- provider-level hard cancellation of active LLM requests
- TTS queue cancellation or realtime voice barge-in
- full voice session facade

Use `main.py` or the preset run scripts for full runtime behavior beyond the public text and voice-output boundaries.

## Planned or evaluated session operations

The following operation is planned or being evaluated after the current v4.0.0 text session boundary:

```python
session.close()
```

This operation should not imply full realtime voice behavior in v4.0.0.

## Public constructor policy

The public constructor for v4.0.0 is:

```python
create_text_chat_session(...)
```

The following constructor is a future candidate, not a v4.0.0 public API:

```python
create_character_session(...)
```

External apps should not depend on `create_character_session()` until it is explicitly documented as stable.

## Future note - Voice-friendly output policy

A future version may add a framework-level output policy for TTS-enabled sessions.

The goal would be to make LLM responses easier for speech synthesis to read aloud.
This should be treated as output-quality guidance, not character personality.

The policy should avoid unnecessary symbols, dense Markdown, tables, and excessive abbreviations while preserving code, commands, file paths, URLs, environment variable names, and proper nouns when necessary.

This should be enabled only when audio/TTS output is active.

## Voice output artifact result contract

Apps should treat `VoiceOutputResult` as the only public handoff shape for app-facing TTS.

Important fields:

- `request_state`: public lifecycle state such as `unavailable`, `skipped`, `rejected`, `generated`, or `failed`
- `audio_ready`: whether app playback may proceed
- `audio_format`: normalized format such as `mp3`
- `audio_url`: FW-provided Web audio URL when available
- `audio_artifact_ref`: opaque FW-owned artifact reference when URL hosting is not available
- `public_metadata`: app-safe metadata only

Apps must not infer provider identity from artifact paths or metadata. They should branch like this:

```python
if not result.audio_ready:
    show_unavailable(result.message)
elif result.audio_url:
    play_url(result.audio_url)
elif result.audio_artifact_ref:
    request_fw_artifact_playback(result.audio_artifact_ref)
else:
    report_contract_error()
```

The v5.0.0 result contract is documented in `voice_output_artifact_result_contract.md` and checked by:

```powershell
python scripts/smoke_voice_output_artifact_result_contract.py
```

The configured-provider execution guard is documented in `voice_output_real_provider_execution_guard.md` and checked by:

```powershell
python scripts/smoke_voice_output_real_provider_execution_guard.py
```

This still does not complete DRC real TTS evidence. DRC must keep `real_tts_web_audio_output` as `NOT_ACCEPTED` until its Web UI playback evidence workflow validates.

## Host app voice output integration handoff

General host apps should use the same v5.0.0 handoff policy as the DRC reference integration target. The policy is documented in `host_app_voice_output_integration_handoff.md` and checked by:

```powershell
python scripts/smoke_voice_output_host_app_handoff.py
```

The handoff keeps app code provider-neutral:

- import voice output only from `framework`
- pass only `VoiceOutputRequest` app intent fields
- treat `voice_profile_id` as a FW-level profile, not a provider voice ID
- branch on `VoiceOutputResult.audio_ready`, `audio_url`, and `audio_artifact_ref` only
- treat `unavailable`, `skipped`, `rejected`, and `failed` as non-playable states
- count only a generated result with exactly one handoff as app-playable output

This is a host app integration contract, not DRC evidence acceptance. DRC still needs its separate Web UI playback evidence workflow after integrating through the FW public boundary.

## v5.0.0 voice output release readiness

v5.0.0 release readiness is defined as a mock-safe public voice output boundary release. The release can be ready while real provider execution and DRC Web audio evidence remain separate follow-up workflows.

Application integrations should keep the following boundary in place:

- app code imports from `framework` only
- app code passes provider-neutral `VoiceOutputRequest` fields only
- FW owns provider selection, API keys, provider voice IDs, model IDs, provider SDK calls, and artifact handling
- `unavailable` and `skipped` results are readiness states, not playable audio evidence
- DRC `real_tts_web_audio_output` remains `NOT_ACCEPTED` until DRC validates Web UI playback evidence through the FW public boundary

Run the release readiness smoke before cutting v5.0.0:

```powershell
python scripts/smoke_voice_output_host_app_handoff.py
python scripts/smoke_voice_output_v500_release_readiness.py
```

See `voice_output_v500_release_readiness_checklist.md` for the full release readiness checklist.

## v5.5.0 candidate host-app motion contract

The host-app motion boundary is Framework-root-only:

```python
from framework import (
    MotionRequest,
    MotionResult,
    create_motion_session,
)
```

FW owns adapter configuration, provider dependency loading, connection and
authentication state, token handling, model readiness, request serialization,
timeouts, cleanup, exception normalization, and public-safe event/result
mapping.

Host apps, including DRC, must not:

- import `framework.motion` or `framework.motion_session` directly;
- import `live2d`, plugins, internal adapters, or pyvts;
- implement a VTube Studio WebSocket client;
- generate, read, update, or delete VTS token files;
- process raw VTS request/response payloads;
- receive pyvts/WebSocket objects, internal hotkey IDs, private endpoints, raw
  exceptions, credentials, or private model paths.

The current v5.4.0 MotionSession is mock-safe and real-adapter
`not_implemented`. FW-VTS-0a reserves a v5.5.0 candidate line but does not
authorize real provider execution.

DRC RT-7 stop rule:

```text
Do not begin DRC real-motion integration until FW-VTS-0f is accepted,
a Framework real-motion adapter is released, and the root-public contract is
fixed.
```

<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:BEGIN -->
## Canonical public import inventory

Host applications continue to import supported SDK contracts from `framework`.
The exact ordered root-public inventory is maintained by
`framework.public_api.PUBLIC_API_NAMES` and exposed by `framework.__all__`.

This change is an SDK hygiene checkpoint, not a host migration. Existing
imports remain valid, including the frozen provider-specific OpenAI voice-input
compatibility exports. Those compatibility exports stay lazy and do not cause
provider SDK import or provider execution during ordinary application startup.

Host applications should continue to prefer provider-neutral contracts such as:

```python
from framework import (
    create_text_chat_session,
    create_voice_input_session,
    create_voice_output_session,
    create_realtime_session,
    create_motion_session,
)
```

New provider-specific names must not be added to the root-public API without a
separate exact contract review. Future provider integrations should use
provider-neutral factories and capability/result contracts.

```text
checkpoint: FW-RT6-0b Control A
runtime behavior changed: False
provider execution: False
network execution: False
DRC or other host repository changes required: False
```
<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:END -->

<!-- FW-RT6-0b-B-VOICE-OUTPUT-SESSION-HYGIENE:BEGIN -->
## Voice-output lifecycle compatibility

Host applications keep the existing method-based voice-output contract:

```python
session = create_voice_output_session()
info = session.info()
result = session.speak(request)
session.close()
```

`info` remains a method. `close()` and `dispose()` are idempotent, and context
manager exit closes the session. Calls to `create_output()` or `speak()` after
close return the same safe `session_closed` result and never expose playable
audio.

This cleanup removes duplicate internal method definitions only. Host code does
not need to change, and no provider, network, microphone, audio playback, VTS,
or host-application repository operation is performed by the checkpoint.
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
## Resource-root integration contract

Host applications do not need to change CWD or prepend the checkout to
`sys.path` for preset and character resource lookup. A host-owned resource tree
may be selected explicitly with keyword-only `project_root`; provider secrets
and provider configuration are not read from that argument.

Voice-output artifact precedence remains explicit `artifact_dir`, environment
override, explicit project root, then a framework-owned system temporary root.
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
## Realtime phase and terminal outcome separation

For v6 realtime integration, applications should use `RealtimePhase` to observe
transient session progress and `TurnOutcome` to interpret a terminal turn result.

```text
session.phase:
RealtimePhase | None

result.outcome:
TurnOutcome

closed session phase:
None
```

The accepted v5 `RealtimeState` properties and event values remain compatible,
but applications should not use terminal `RealtimeState` values as the canonical
v6 phase model. Invalid internal phase regressions produce the public-safe
`LifecycleTransitionError`; provider exceptions and payloads are not required at
the host boundary.

`RealtimeEvent` still uses the legacy state mapping in this control. Event phase,
sequence, generation, terminal flag, and typed payload integration remain
FW-RT6-1c.
<!-- FW-RT6-1b-C-REALTIME-PHASE-ADOPTION:END -->

<!-- FW-RT6-1c-A-TYPED-PAYLOADS:BEGIN -->
## Host-app typed realtime payload guidance

Applications may import the v6 payload models from `framework` and branch on
`RealtimeEventPayloadKind` instead of parsing provider-specific dictionaries.

```python
from framework import TranscriptEventPayload

payload = TranscriptEventPayload(
    text="hello",
    is_final=True,
    confidence=0.9,
)
public_value = payload.as_dict()
```

```text
baseline head: 285e546d7065eee24d144a4fc39da82d3097bd1f
public payload mapping: immutable / JSON-safe
provider SDK object required: False
provider payload parsing required: False
local artifact path accepted: False
RealtimeEvent integration: DEFERRED TO CONTROL B
RealtimeSession emission integration: DEFERRED TO CONTROL D
```

Applications must not treat `AudioEventPayload.artifact_ref` as a filesystem
path. Runtime callbacks continue to use the existing `RealtimeEvent` contract
until later FW-RT6-1c controls adopt the v6 envelope.
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
## Host-app v5 event compatibility adapter

Applications may explicitly project a canonical event before invoking legacy
handlers:

```python
legacy_event = event.to_v5()
if legacy_event is not None:
    legacy_handler(legacy_event.as_dict())
```

```text
checkpoint: FW-RT6-1c Control C
baseline head: 532d7852bfe9370514180800a84bfc0a8e13fa9c
identity v5 event returns same object: True
unmapped event returns None: True
legacy dictionary keys: 10 / SAME ORDER
canonical on_event wiring: DEFERRED TO CONTROL D
on_legacy_event wiring: DEFERRED TO CONTROL D
provider payload parsing required: False
```

`TURN_CANCELLED` and `TURN_REJECTED` remain distinct canonical v6 meanings.
Their v5 projections use the available interrupted and failed event categories,
while preserving the typed lifecycle payload and public error code.
<!-- FW-RT6-1c-C-V5-EVENT-ADAPTER:END -->

<!-- FW-RT6-1c-D-ORDERED-EVENT-ADOPTION:BEGIN -->
## Host-app ordered realtime event integration

New host applications register `on_event` and consume the canonical ordered
stream. Applications that still require the v5 vocabulary register
`on_legacy_event`; the Framework performs the explicit lossy projection and does
not promote partial or unmapped events into legacy completion categories.

Host applications must use `EventSequence` as the authoritative ordering value.
Timestamps are diagnostic public values and do not replace sequence ordering. A
completed admitted turn uses one stable `GenerationId`; the next admitted turn
uses a different value. Session-only and rejected-before-admission events have no
generation.

```text
canonical completed turn:
TURN_STARTED -> LISTENING_STARTED -> LISTENING_COMPLETED -> TRANSCRIPT_FINAL
-> RESPONSE_STARTED -> RESPONSE_COMPLETED -> SYNTHESIS_STARTED
-> SYNTHESIS_COMPLETED -> TURN_COMPLETED

legacy projection:
TURN_STARTED -> VOICE_INPUT_STARTED -> VOICE_INPUT_COMPLETED
-> TEXT_CHAT_STARTED -> TEXT_CHAT_COMPLETED -> VOICE_OUTPUT_STARTED
-> VOICE_OUTPUT_COMPLETED -> TURN_COMPLETED
```

```text
checkpoint: FW-RT6-1c Control D
baseline head: 007e1577a18c92a1dafdf9ede814b97dc2d0a05c
on_event canonical events: True
on_legacy_event mapped v5 events only: True
sequence session lifetime: True
sequence reset between turns: False
generation stable within admitted turn: True
generation absent before admission: True
typed payload by canonical runtime category: True
automatic timestamp and monotonic_timestamp: True
terminal registry / duplicate suppression: DEFERRED
automatic stale-result rejection: DEFERRED
bounded event queue / overflow runtime: DEFERRED
provider partial transcript / response delta callbacks: DEFERRED
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
## v6.0.0 stable realtime stage protocol package

Host integration code may use the explicitly stable public package
`framework.realtime_stage` for protocol typing and fake composition boundaries.
The package provides provider-neutral stage context/result envelopes plus four
stage protocols with one common lifecycle vocabulary:

```text
preflight
capability
start
cancel
close
```

The stage context carries `session_id`, `turn_id`, and `generation_id`. Requests,
results, and capability snapshots are existing Framework public models; provider
clients, raw payloads, provider-specific cancellation handles, credentials, and
private paths are not public protocol inputs or outputs.

Control A does not change `create_realtime_session`, does not inject or execute a
stage, and does not add the stage names to the 121-name root-public surface.
RealtimeSession injection remains deferred to Control B.

```text
checkpoint: FW-RT6-3a Control A
status: IMPLEMENTED / AWAITING_REVIEW
stable public package: framework.realtime_stage
root-public names: 121 / UNCHANGED
RealtimeSession injection: DEFERRED / Control B
real provider execution: False
network / microphone / playback / real VTS execution: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:END -->


<!-- FW-RT6-3a-B-STAGE-INJECTION:BEGIN -->
## v6.0.0 app-facing realtime stage injection boundary

Applications may pass provider-neutral stage implementations through the four
new keyword-only `create_realtime_session(...)` slots defined by FW-RT6-3a
Control B. The implementations must satisfy the corresponding stable protocol
from `framework.realtime_stage`; provider clients, provider-specific cancellation
handles, raw payloads, credentials, and private paths are not factory arguments.

Construction validates protocol shape and stage identity only. It does not call
`preflight()`, `capability()`, `start()`, or `cancel()`. The current mock
`run_turn()` path also does not execute injected stages. Session close owns one
best-effort `close()` attempt per injected stage and records failures only in
count-only diagnostics.

```text
checkpoint: FW-RT6-3a Control B
baseline head: af474e2ceec9988bec1b7e7fadfe2d4037774597
status: IMPLEMENTED / AWAITING_REVIEW
stage injection: PROVIDER-NEUTRAL
fake stage injection: PASS
factory signature change: ADDITIVE / KEYWORD-ONLY
raw injected implementation exposure: False
stage lifecycle execution during construction: False
stage execution during current run_turn: False / DEFERRED
root-public names: 121 / UNCHANGED
provider SDK root import: False
real provider execution: False
real orchestration: False
network / microphone / playback / real VTS execution: False
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3a-B-STAGE-INJECTION:END -->

<!-- FW-RT6-3b-A-DETERMINISTIC-FAKE-RUNTIME:BEGIN -->
## v6.0.0 deterministic fake realtime controller

Test and validation code may explicitly import
`framework.realtime_fake_runtime` to reproduce provider-free ordering and fault
scenarios. The package provides an integer-tick fake clock/scheduler, stage
pause/resume, artificial delay, late-completion injection, duplicate-terminal
injection, cancellation-timeout injection, queue-overflow injection, and an
exact deterministic trace assertion helper.

The package is not imported by `framework` root and does not change the
121-name root-public surface. It does not use wall-clock sleep, background
threads, network access, provider SDKs, microphone input, playback, or real
VTube Studio. Control A does not connect the controller to
`RealtimeSession`, the generation gate, or the terminal registry; that adoption
and aggregate acceptance remain deferred to separately authorized work.

```text
checkpoint: FW-RT6-3b Control A
baseline head: dc02a13b98cb6fd7a8ff300366dac77b9b6f5873
status: IMPLEMENTED / AWAITING_REVIEW
explicit package: framework.realtime_fake_runtime
fake clock / scheduler: True
stage pause / resume: True
artificial delay: True
late completion injection: True
duplicate terminal injection: True
cancellation timeout injection: True
queue overflow injection: True
deterministic event trace assertion helper: True
race reproducible: True
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
provider SDK / network / microphone / playback / real VTS execution: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3b-A-DETERMINISTIC-FAKE-RUNTIME:END -->

<!-- FW-RT6-3b-B-GATE-TERMINAL-ADOPTION:BEGIN -->
## v6.0.0 deterministic fake-runtime gate/terminal adoption

Validation code may explicitly use
`framework.realtime_fake_runtime.DeterministicRealtimeRaceHarness` to drive the
accepted `RealtimeGenerationGate` and `RealtimeTerminalRegistry` with the
deterministic fake controller. Late completion injection is classified by the
actual generation gate, and duplicate terminal injection is classified by the
actual terminal registry.

This is provider-free test-support adoption. It does not execute injected
`RealtimeSession` stages, replace the mock `run_turn()` path, emit fake trace
records through the realtime event hub, or claim production orchestration.

```text
checkpoint: FW-RT6-3b Control B
baseline head: c3999bd16b2d6104fc90d6282da9a60c84068875
status: IMPLEMENTED / AWAITING_REVIEW
explicit package: framework.realtime_fake_runtime
deterministic race harness: DeterministicRealtimeRaceHarness
RealtimeGenerationGate adoption: True
RealtimeTerminalRegistry adoption: True
late completion classified by actual gate: True
duplicate terminal classified by actual registry: True
race reproducible: True
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
event-hub trace projection: DEFERRED
provider SDK / network / microphone / playback / real VTS execution: False
tasklist checkboxes changed: False
aggregate FW-RT6-3b acceptance: DEFERRED
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3b-B-GATE-TERMINAL-ADOPTION:END -->

<!-- FW-RT6-6a-A-VOICE-SYNTHESIS-PROTOCOL:BEGIN -->
## v6.0.0 voice-synthesis generation typing boundary

Host applications continue to use the existing root voice-output session API.
Framework composition/test code that needs generation-level typing may
explicitly import `framework.realtime_voice_output`.

The additive protocol keeps provider details outside application-visible
correlation:

```text
Framework correlation:
session_id / turn_id / generation_id / SynthesisWorkId

provider adapter input:
VoiceOutputRequest only

provider receives Framework correlation IDs:
False

active generation exposes request text/provider/artifact:
False
```

`RealtimeVoiceOutputCapability.generation_cancel_supported` and
`provider_hard_cancel_supported` remain the canonical capability facts.
Cooperative cancel acceptance never implies provider hard-cancel completion.
Control A does not wire a provider adapter, execute TTS, create a queue, perform
playback, or change the existing root-public voice-output API.

```text
checkpoint: FW-RT6-6a Control A
status: IMPLEMENTED / AWAITING_REVIEW
root-public names: 127 / UNCHANGED
Control B provider/stage adoption: DEFERRED / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6a-A-VOICE-SYNTHESIS-PROTOCOL:END -->

<!-- FW-RT6-6a-B-PROVIDER-ACTIVE-ADOPTION:BEGIN -->
## v6.0.0 voice-synthesis provider adoption and active work observability

FW-RT6-6a Control B keeps host applications on the existing root voice-output
session API. Framework composition may use the accepted
`framework.realtime_voice_output` protocols while the existing internal
voice-output adapters now supply provider-neutral `RealtimeVoiceOutputCapability`
facts.

The reference synthesis stage owns an opaque `SynthesisWorkId` and a thread-safe
`active_generation` snapshot containing only correlation context plus that work
ID. Request text, provider details, artifact data, and provider handles remain
private.

Control B does not claim cancellation that does not exist in the current
provider boundary:

```text
generation_cancel_supported = False
provider_hard_cancel_supported = False
active matching cancel -> UNSUPPORTED
provider/network/microphone/playback/real VTS execution: False
root-public names: 127 / UNCHANGED
```

Pending queue control, active cancellation execution, artifact invalidation, and
host playback stop remain FW-RT6-6c/6d/6e responsibilities.

```text
checkpoint: FW-RT6-6a Control B
baseline head: 5a509c9ddc18cd55dc84b264193bab973c176ee6
status: IMPLEMENTED / AWAITING_REVIEW
stable exports changed: False
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6a-B-PROVIDER-ACTIVE-ADOPTION:END -->

<!-- FW-RT6-6b-A-OPAQUE-ARTIFACT-STORE:BEGIN -->
## FW-RT6-6b Control A — opaque voice artifact store foundation

Voice output artifact storage now has an explicitly stable provider-neutral
package:

```text
framework.voice_artifacts
```

Control A does not re-export the package from the `framework` root.

```text
root-public names: 127 / UNCHANGED
```

The stable package defines `VoiceArtifactId`, `VoiceArtifactState`,
`VoiceArtifactRecord`, and `VoiceArtifactStore`. Framework-owned artifact IDs use
only this opaque format:

```text
fw_voice_artifact_<32 lowercase hex>
```

Host applications must treat `VoiceArtifactRef.artifact_id` as an opaque value.
It is not a local path, `file://` URL, provider object, provider identifier, or
storage implementation key that callers may parse.

`VoiceArtifactStore` separates internal storage from the public reference and
fixes provider-neutral `store`, `resolve`, `open`, `delete`, `expire`, and
`bind_generation` operations. `open()` is valid only while the artifact record is
`valid`; expired and deleted artifacts are not playable through the store.

Provider adapters still receive only `VoiceOutputRequest`. They do not receive
session, turn, generation, or synthesis-work identities. Generation association
is a Framework orchestration operation through `bind_generation()` and does not
change the accepted FW-RT6-6a provider-adapter protocol.

Control A does not yet replace the current real-provider local-path handoff.
Provider adoption and `str(artifact_path)` removal remain FW-RT6-6b Control B.
Pending queue behavior, active generation cancellation/invalidation, and host
playback remain FW-RT6-6c/6d/6e.
<!-- FW-RT6-6b-A-OPAQUE-ARTIFACT-STORE:END -->

<!-- FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:BEGIN -->
## FW-RT6-6c Control A — bounded pending voice-output queue foundation

FW-RT6-6c Control A adds the explicitly stable provider-neutral package
`framework.realtime_voice_output_queue`. It is not re-exported from the
`framework` root, so the root-public surface remains 127 names.

The queue owns pending synthesis work only. Each accepted item has Framework
session / turn / generation context plus an opaque `SynthesisWorkId`; request
text remains private to the concrete queue entry and is absent from public
pending snapshots.

`max_pending_depth` is fixed per queue instance. Admission returns a typed
`VoiceSynthesisEnqueueResult`. A full queue returns `REJECTED_FULL`, leaves all
already pending work unchanged, and emits one typed `VoiceSynthesisQueueEvent`
overflow diagnostic to the configured component callback. The caller therefore
receives a typed rejection even if the diagnostic callback itself fails.

`clear_pending()` clears pending items only and always reports
`active_generation_cancelled=False`. It does not cancel active synthesis, apply
provider hard cancel, invalidate completed artifacts, suppress future delivery,
or stop host playback.

Control A does not execute a synthesis stage or provider. Queue-to-stage work-ID
handoff and explicit active/pending composition remain Control B work.

```text
checkpoint: FW-RT6-6c Control A
baseline head: 3bdd196c34d2ffd3eaa2dfc30cc39cf22aa34409
FW-RT6-6c exact contract review: COMPLETED
status: IMPLEMENTED / AWAITING_REVIEW
stable package: framework.realtime_voice_output_queue
root-public names: 127 / UNCHANGED
active generation cancellation: False / DEFERRED FW-RT6-6d
provider/network/microphone/playback/real VTS execution: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:END -->

<!-- FW-RT6-6c-B-PENDING-ACTIVE-HANDOFF:BEGIN -->
## FW-RT6-6c Control B — pending-to-active voice synthesis handoff

The accepted bounded pending queue now composes with the accepted concrete
provider-neutral synthesis stage without expanding either stable protocol.
`BoundedVoiceSynthesisPendingQueue.handoff_next()` is a reference-only helper on
the non-stable concrete queue implementation.

The oldest pending entry leaves the queue only after the concrete stage claims
its exact enqueue-time `SynthesisWorkId`. During provider execution the item is
therefore active/stage-owned and is no longer pending/queue-owned. The result
envelope preserves the same context and work identity.

A closed or already-active stage rejects the claim before the FIFO is mutated.
Pending clear remains queue-only and cannot cancel or alter active synthesis.
Generation cancellation, artifact invalidation, future-delivery suppression,
and host playback remain later boundaries.

```text
checkpoint: FW-RT6-6c Control B
baseline head: 820056ff897e7bfdcfa20c3f7d4b14df0633c3b1
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
status: IMPLEMENTED / AWAITING_REVIEW
root-public names: 127 / UNCHANGED
queue stable exports: 8 / UNCHANGED
voice synthesis stable exports: 7 / UNCHANGED
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6c-B-PENDING-ACTIVE-HANDOFF:END -->

<!-- FW-RT6-6d-A-TYPED-CANCEL-RESULT:BEGIN -->
## FW-RT6-6d Control A — app integration cancellation-result typing

Host applications continue to use the existing root voice-output APIs. Advanced
Framework integration code may explicitly inspect
`framework.realtime_voice_output.VoiceSynthesisCancelResult` when composing the
v6 realtime voice-output control boundary.

The typed result now distinguishes cooperative request/completion, timeout,
provider hard-cancel applied versus unsupported, artifact invalidation, and
future-delivery suppression. These fields are truthful result vocabulary only in
Control A; the current concrete stage still returns `UNSUPPORTED` for a matching
active synthesis cancel.

```text
checkpoint: FW-RT6-6d Control A
baseline head: 3613056b798bd0a46ecee87a252ed5f36156a67d
root-public names: 127 / UNCHANGED
VoiceSynthesisStage signature changed: False
provider adapter signature changed: False
active cancel execution: False
provider hard cancel capability changed: False
artifact invalidation execution: False
future delivery suppression execution: False
host playback changed: False
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6d-A-TYPED-CANCEL-RESULT:END -->

<!-- FW-RT6-6d-B-CANCEL-INVALIDATION-ADOPTION:BEGIN -->
## FW-RT6-6d Control B — cooperative voice-output cancellation adoption

FW-RT6-6d Control B adopts the accepted typed cancellation vocabulary in one
Framework-owned reference control boundary. Host applications remain on the
existing root APIs; the new cancelable reference stage and output controller are
internal implementation helpers and are not added to the 127-name root surface.

The reference boundary keeps provider cancellation truth separate from
Framework-cooperative suppression:

```text
active cooperative cancel: IMPLEMENTED
bounded completion wait: IMPLEMENTED
provider hard cancel applied: False
provider hard cancel unsupported: True
completed FW artifact invalidation: IMPLEMENTED
late/future audio handoff after cancel: SUPPRESSED
late completion freshness: existing RealtimeGenerationGate
pending clear vs active cancel: DISTINCT
host playback stop: NOT_IMPLEMENTED / FW-RT6-6e
```

The provider adapter protocol remains correlation-free and unchanged. Current
provider capabilities continue to report provider hard cancel as unsupported.
`RealtimeSession` real-runtime orchestration remains unchanged; guarded real TTS
composition is still later roadmap work.

```text
checkpoint: FW-RT6-6d Control B
baseline head: 5e26f29847a357225a29c724c6014aa15ff1c83d
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 6 files
root-public names: 127 / UNCHANGED
stable voice exports: 7 / UNCHANGED
stable artifact exports: 4 / UNCHANGED
stable queue exports: 8 / UNCHANGED
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6d tasks: 0 / 7 CLOSED
Control C: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-6d-B-CANCEL-INVALIDATION-ADOPTION:END -->

<!-- FW-RT6-6e-A-HOST-PLAYBACK-FOUNDATION:BEGIN -->
## FW-RT6-6e Control A — playback ownership / host-stop coordination contract

Host applications that consume a voice-output artifact own playback when
`RealtimeVoiceOutputCapability.playback_ownership == "host"`.

The Framework may represent a request for the host to stop that playback through
the canonical v6 `PLAYBACK_STOP_REQUESTED_TO_HOST` event. A host may optionally
acknowledge receipt through `PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST`.

Neither event is proof that speakers, browser audio, platform media playback, or
another host-owned playback engine has physically stopped.

```text
host stop request received:
physical stop success = NOT IMPLIED

host acknowledgement received:
physical stop success = NOT IMPLIED

FW artifact invalidated:
physical stop success = NOT IMPLIED
```

Applications must therefore treat artifact invalidation and playback stopping as
separate facts. Control A defines the typed contract only; runtime coordination
is deferred to FW-RT6-6e Control B.
<!-- FW-RT6-6e-A-HOST-PLAYBACK-FOUNDATION:END -->

<!-- FW-RT6-6e-B-HOST-PLAYBACK-ADOPTION:BEGIN -->
## FW-RT6-6e Control B — app host playback coordination

When the detailed voice-output capability reports:

```text
playback_ownership = host
host_playback_stop_request_supported = True
```

an app should treat `PLAYBACK_STOP_REQUESTED_TO_HOST` as a request to its own
playback layer. The app may optionally report receipt through
`RealtimeSession.acknowledge_host_playback_stop()`.

Acknowledgement is not a speaker/media-engine stop confirmation. Apps that need a
separate physical-stop result must keep that result in their own host playback
layer until a later explicit Framework contract defines otherwise.

The Framework may emit `AUDIO_INVALIDATED` after its accepted artifact lifecycle
control invalidates a Framework-owned artifact. Apps must still separately stop
already-buffered or already-downloaded host playback.
<!-- FW-RT6-6e-B-HOST-PLAYBACK-ADOPTION:END -->

<!-- FW-RT6-7a-A-VOICE-INPUT-CORRECTION:BEGIN -->
## FW-RT6-7a Control A — voice-input host integration correction

Host applications may treat the OpenAI real-STT executor as an implemented
Framework capability when the explicit public configuration guards pass. This
does not mean the Framework has probed the optional SDK, network, credentials,
or provider service during capability inspection.

```text
executor implementation available:
True for OpenAI

runtime probe performed:
False

provider execution performed:
False
```

The public `VoiceInputSession` now exposes stable session identity and an
additive canonical realtime-event callback scaffold. Turn/generation correlation
is Framework-owned. Existing mapping callbacks remain compatible.

Control A does not yet make the session choose a real provider automatically.
The default host-audio path remains fake/mock-safe unless an adapter is supplied.
Provider-neutral default fake/real composition is FW-RT6-7a Control B work.

Applications must not construct provider-native clients or infer real runtime
availability from executor implementation availability.
<!-- FW-RT6-7a-A-VOICE-INPUT-CORRECTION:END -->

<!-- FW-RT6-7a-B-PROVIDER-NEUTRAL-COMPOSITION:BEGIN -->
## FW-RT6-7a Control B — host default fake/real selection

Hosts may use `create_voice_input_session()` plus
`transcribe_audio_result()` without constructing provider-specific Framework
adapter/factory/executor objects.

The provider-neutral selection contract is:

```text
default/no real STT intent:
fake path

explicit adapter:
host-provided adapter wins

real STT intent with incomplete guards:
typed unavailable / no silent fake fallback

real OpenAI STT with all explicit guards:
Framework-owned lazy composition
```

The following gates remain separate:

```text
real_stt_enabled
allow_provider_execution
allow_provider_sdk_import
allow_provider_client_creation
allow_real_provider_execution
```

`private_credential` is an explicit secret-bearing argument and is never copied
to session info, public metadata, events, safe messages, or results.
`credential_env` remains preflight/capability input only; runtime composition
does not consume its credential value.

Host-owned FILE_PATH audio is still opened only by the accepted real executor
after all real-runtime guards pass. Framework microphone capture is not added.

FW-RT6-7b owns typed voice-input stage lifecycle/transcript events and stale
generation handling. FW-RT6-7c owns additive `VoiceInputResult` correlation and
the final v5 result/callback compatibility bridge.
<!-- FW-RT6-7a-B-PROVIDER-NEUTRAL-COMPOSITION:END -->

<!-- FW-RT6-7b-A-LIFECYCLE-PRIVACY:BEGIN -->
## FW-RT6-7b Control A — host-audio lifecycle integration

Hosts continue to own audio capture and hand one `VoiceInputAudioSource` to
`transcribe_audio_result()`. The Framework assigns one turn/generation context
for that operation and emits canonical preflight, listening start, listening
completion and final-transcript events. Non-completed results and adapter
exceptions emit a typed, safe `VOICE_INPUT_FAILED` event without changing the
existing result or exception behavior.

For a `FILE_PATH` source, the path remains an execution-private value. Public
events expose only:

```text
audio_id: opaque
source_kind: file_path
raw_audio_retained: False
audio_path_exposed: False
```

The Framework does not retain raw audio or the host audio source in session
state. Control A performs no microphone, provider, network or audio execution
during acceptance verification.

Input abort and late-transcript rejection remain Control B work. Result-level
session/turn/generation correlation remains FW-RT6-7c.
<!-- FW-RT6-7b-A-LIFECYCLE-PRIVACY:END -->

<!-- FW-RT6-7b-B-ABORT-STALE-GATE:BEGIN -->
## FW-RT6-7b Control B — host input abort and late completion handling

An app may call `VoiceInputSession.abort_input()` while
`transcribe_audio_result()` is in progress. The first call that invalidates the
active Framework generation returns `True`; a call with no active input, or a
duplicate call for the same operation, returns `False`.

The return value is a Framework admission fact only:

```text
active generation invalidated:
True

provider request hard-cancelled:
NOT IMPLIED

host microphone/capture stopped:
NOT IMPLIED
```

The host remains responsible for stopping its own capture mechanism. A provider
adapter may still finish after the abort. The session rejects that late
completion at its generation gate, returns the existing interrupted
`VoiceInputResult` to the waiting caller, emits one typed
`STALE_RESULT_DROPPED` diagnostic, and does not emit `TRANSCRIPT_FINAL` for the
retired generation.

Starting a newer voice-input operation likewise retires the earlier generation.
Only the current operation may publish its final transcript. Stale diagnostic
metadata contains safe retirement facts and never the raw audio source or a
host `FILE_PATH` value.

Apps must not interpret this control as provider hard cancellation, result-level
correlation, or unified close rejection. Additive `VoiceInputResult`
correlation and close compatibility remain FW-RT6-7c; partial streaming remains
P1 scope.
<!-- FW-RT6-7b-B-ABORT-STALE-GATE:END -->

<!-- FW-RT6-7c-A-RESULT-CORRELATION:BEGIN -->
## FW-RT6-7c Control A — host use of correlated voice-input results

Hosts may read `session_id`, `turn_id`, and `generation_id` directly from a
`VoiceInputResult` returned by `transcribe_audio_result()`. These identities
match the canonical events for that operation, including an interrupted result
whose provider completion arrived after abort or after a newer input started.

```text
result/session event correlation:
same Framework-owned IDs

adapter-supplied correlation:
replaced by session-owned IDs

legacy factory call without IDs:
preserved; correlation fields are None
```

The new fields are appended to the existing result shape. Existing factory
names, positional result fields, outcomes, error codes, safe messages and
metadata behavior remain compatible. Serialized Framework IDs are validated;
non-Framework legacy session/turn strings remain accepted for direct host
construction.

This control does not yet attach correlation to `listen_result()` or text
fallback, adapt legacy mapping callbacks from canonical v6 events, or unify
closed-session result rejection. Those remain FW-RT6-7c Control B.
<!-- FW-RT6-7c-A-RESULT-CORRELATION:END -->

<!-- FW-RT6-7c-B-COMPATIBILITY-BRIDGE:BEGIN -->
## FW-RT6-7c Control B — app result/callback compatibility bridge

Apps may correlate every open-session result-returning voice-input operation
without constructing identities. `listen_result()` and
`text_fallback_result()` now receive the same session-owned turn/generation
context already used by `transcribe_audio_result()`.

```text
open operation result:
session_id + turn_id + generation_id

post-close rejection:
session_id only; no turn or generation admitted
```

The canonical `on_realtime_event()` callback remains the v6 authority. For apps
that still use `on_event()`, the session explicitly projects the accepted legacy
mapping events from canonical preflight/failure/final/close events. Mapping
objects keep their existing `type`, `session_type`, and `payload` keys.

`listen_result()` continues to report the provider-neutral unavailable outcome
when live capture is not implemented. Text fallback continues to return a
completed result. Host-audio `transcribe_audio_result()` continues to emit no
legacy mapping callbacks, so this bridge does not invent a previously absent
host-audio callback flow.

Calling `close()` is idempotent. The first close emits exactly one canonical
`SESSION_CLOSED` and one mapped `voice_input.closed` event. All later result
operations return the same safe session-only closed rejection without emitting
another close event.

This contract does not imply provider hard cancellation, provider/network/audio
execution, Framework microphone ownership, or partial streaming. It adds no
root-public name and does not change `VOICE_INPUT_API_VERSION`. FW-RT6-7c
aggregate checkbox closure remains Control C.
<!-- FW-RT6-7c-B-COMPATIBILITY-BRIDGE:END -->

<!-- FW-RT6-8a-A-MOTION-CORRELATION:BEGIN -->
## FW-RT6-8a Control A — motion request/result correlation

An app or Framework orchestrator may attach an existing unified-turn context to
the public `MotionRequest` through two additive optional fields:

```text
turn_id: TurnId | legacy string | None
generation_id: GenerationId | serialized GenerationId | None
```

The same two fields are appended to `MotionResult`. `MotionSession` preserves
them through mock success, guarded/unavailable, preflight failure, unsupported,
closed, and VTube Studio transport-result projection paths. Existing mapping
callbacks add JSON-safe `turn_id` and `generation_id` values and keep the
existing `session_id` and `request_id` values unchanged.

When a request has no correlation context, the new request/result/event values
remain `None`. A standalone motion session does not allocate a turn or
generation. A generation requires a turn; a correlated result additionally
requires its existing session identity.

```text
MotionRequest request_id changed: False
GenerationId promoted from request_id: False
MotionResult session_id compatibility: PRESERVED
legacy MotionRequest/MotionResult positional prefix: PRESERVED
standalone correlation identity invented: False
root-public names: 127 / UNCHANGED
MotionSessionInfo.api_version: 5.5.0 / UNCHANGED
```

Control A does not add `on_realtime_event()`, allocate `EventSequence`, replace
the existing mapping callback, or change VTube Studio lifecycle-generation
suppression. Those adoption steps require one shared ordering/freshness owner
and remain Control B work.

```text
unified EventSequence bridge: DEFERRED TO CONTROL B
common stale guard / VTS suppression adoption: DEFERRED TO CONTROL B
VTS lifecycle-generation source changed: False
provider/network/audio/microphone/real VTS execution: False
FW-RT6-8a aggregate tasks: 0 / 5 CLOSED
Control B: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-8a-A-MOTION-CORRELATION:END -->

<!-- FW-RT6-8a-B-MOTION-COORDINATION:BEGIN -->
## FW-RT6-8a Control B — unified motion ordering and freshness

`MotionSession` now has an additive `on_realtime_event(callback)` registration
point for canonical motion events. The Framework binds the session internally to
the same provider-neutral `RealtimeEventHub` and `RealtimeGenerationGate` that
own the unified turn. The host does not construct, import, or pass either
internal owner, and the existing `create_motion_session(...)` signature remains
unchanged.

The binding is single-owner and does not create a second sequence or freshness
domain. A callback may be registered before binding; canonical delivery begins
only after the Framework owner is bound. An unbound standalone `MotionSession`
keeps the v5.5 mapping callback behavior and allocates no `EventSequence`.

For a bound session, selected existing mapping events have these canonical
counterparts on the shared sequencer:

| Motion mapping event | Canonical event |
|---|---|
| `motion.requested` | `realtime.motion.requested` |
| `motion.started` | `realtime.motion.started` |
| `motion.completed` | `realtime.motion.completed` |
| `motion.failed`, `motion.unsupported`, `motion.interrupted` | `realtime.motion.failed` |

Canonical motion events carry `MotionEventPayload`, the existing motion-session
identity, the request's optional turn/generation correlation, and the sequence
allocated by the shared hub. The v5.5 mapping callback remains sequence-free and
keeps its existing JSON-safe `session_id`, `request_id`, `turn_id`, and
`generation_id` representation.

When both request correlation IDs are present, the bound common generation gate
must admit the terminal result before it is published. `MotionSession` neither
starts nor advances the unified generation and cannot replace an unknown or
retired generation. A rejected completion becomes a correlated
`MotionOutcome.INTERRUPTED` result, emits one canonical
`realtime.stale_result.dropped` diagnostic and one legacy
`motion.interrupted` projection, and emits no completed event.

The VTube Studio transport's existing lifecycle-generation check remains the
lower-level close/late-task defense. Its result is additionally subject to the
same common gate at the motion-session boundary. Consequently a VTS completion
that arrives after unified generation retirement cannot be delivered as motion
success even when the lower transport itself was not closed. This is completion
suppression, not provider hard cancellation or a new cancel/clear API; those
capabilities remain FW-RT6-8c scope.

```text
exact Control B surface: 7 files
unified EventSequence owner: shared RealtimeEventHub / PASS
separate local motion sequencer: False / PASS
common freshness owner: shared RealtimeGenerationGate / PASS
MotionSession starts or advances unified generation: False / PASS
late motion completion delivered: False / PASS
VTS lifecycle-generation guard replaced: False / PASS
legacy mapping callback sequence field added: False / PASS
create_motion_session signature changed: False / PASS
root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-8a aggregate tasks: 0 / 5 CLOSED
Control B status: IMPLEMENTED / AWAITING_REVIEW
Control C aggregate review: DEFERRED
FW-RT6-8b / FW-RT6-8c: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-8a-B-MOTION-COORDINATION:END -->

<!-- FW-RT6-8b-A-MOTION-LIFECYCLE-HOOK:BEGIN -->
## FW-RT6-8b Control A — provider-neutral motion lifecycle hook

Control A adds the stable explicit package `framework.motion_lifecycle`. It
defines a host/plugin extension contract and an isolated invocation boundary;
it does not adopt the hook in `RealtimeSession` or execute a motion stage.

```python
from framework import MotionRequest
from framework.motion_lifecycle import (
    MotionLifecycleNotification,
    MotionLifecycleSignal,
)


def character_motion(notification: MotionLifecycleNotification):
    if notification.signal is MotionLifecycleSignal.SPEAKING:
        return MotionRequest.speaking_state(True)
    return None
```

The six signals intentionally combine three transient notifications with three
terminal notifications without changing the accepted lifecycle model:

| Hook signal | Canonical source selected for Control B |
|---|---|
| `listening` | `LISTENING_STARTED` |
| `thinking` | `RESPONSE_STARTED` |
| `speaking` | `SYNTHESIS_STARTED` |
| `interrupted` | `TURN_INTERRUPTED` or `TURN_CANCELLED` |
| `completed` | `TURN_COMPLETED` |
| `failed` | `TURN_FAILED` |

Transient notifications have no terminal outcome. Terminal notifications must
match the accepted `TurnOutcome`; cancellation remains distinct in the
notification even though it selects the `interrupted` motion signal.
`TURN_REJECTED` and `SESSION_CLOSED` are not Control A hook signals.

The notification carries the existing session, turn, generation, and source
event sequence. A hook may return one provider-neutral `MotionRequest` or
`None`. An uncorrelated request inherits the notification's turn/generation.
Matching correlation is preserved; partial or mismatched correlation becomes a
public-safe failed hook result and is not executed.

```text
product-specific mapping in Framework core: False
provider-neutral hook return: MotionRequest | None
None result: SKIPPED / not unsupported / not failure
hook exception escapes Framework boundary: False
raw hook exception public: False
conversation terminal changed by hook failure: False
unsupported motion intent channel: MotionOutcome.UNSUPPORTED
```

Unsupported adapter execution remains an existing typed motion outcome. It is
not conflated with a hook skip or hook-resolution failure. The Control B
coordinator must preserve an already committed conversation terminal before it
invokes a terminal hook, and motion/hook failure must not commit or replace a
conversation terminal.

Control A changes no existing runtime source, root-public manifest, public
factory signature, or motion API version. It imports no provider SDK and
performs no provider, network, audio, microphone, or real VTS operation.

```text
exact Control A surface: 5 files
stable explicit package: framework.motion_lifecycle
root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
runtime hook adoption: DEFERRED TO CONTROL B
MotionStage execution: DEFERRED TO CONTROL B
canonical hook/motion event integration: DEFERRED TO CONTROL B
FW-RT6-8b aggregate tasks: 0 / 6 CLOSED
Control B: NOT_AUTHORIZED
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-8b-A-MOTION-LIFECYCLE-HOOK:END -->

<!-- FW-RT6-8b-B-MOTION-LIFECYCLE-ADOPTION:BEGIN -->
## FW-RT6-8b Control B — RealtimeSession motion lifecycle adoption

`RealtimeSession.set_motion_lifecycle_hook(hook)` explicitly installs the one
host/plugin-owned mapping hook for a session. Passing `None` disables it. The
hook is not a factory or `RealtimeSessionConfig` parameter and cannot be
replaced while a turn is active. Product-specific expression, emotion, gesture,
character, model, hotkey, or provider selection remains outside Framework core.

After the canonical source event has been sequenced and delivered, the session
builds one correlated `MotionLifecycleNotification`. The adopted mapping is:

| Canonical source | Hook signal / outcome |
|---|---|
| `LISTENING_STARTED` | `listening` / no outcome |
| `RESPONSE_STARTED` | `thinking` / no outcome |
| `SYNTHESIS_STARTED` | `speaking` / no outcome |
| `TURN_INTERRUPTED` | `interrupted` / `INTERRUPTED` |
| `TURN_CANCELLED` | `interrupted` / `CANCELLED` |
| `TURN_COMPLETED` | `completed` / `COMPLETED` |
| `TURN_FAILED` | `failed` / `FAILED` |

`TURN_REJECTED` and `SESSION_CLOSED` do not invoke the hook. A skipped or failed
hook emits no motion events and starts no stage. Only a mapped
`MotionRequest` enters the existing injected `MotionStage` boundary.

Mapped execution uses the session's existing `RealtimeEventHub`. A usable stage
emits `MOTION_REQUESTED`, `MOTION_STARTED`, then `MOTION_COMPLETED` or
`MOTION_FAILED`. A missing or failed-preflight stage emits requested then one
typed failure without a started event. Stage exceptions, malformed envelopes,
and request/result/context correlation mismatch normalize to a public-safe
failed result; raw error details do not escape. An adapter's existing
`MotionOutcome.UNSUPPORTED` remains unsupported and is not reclassified as hook
skip/failure.

Transient completion admission uses the existing shared
`RealtimeGenerationGate`. A completion retired by interrupt, cancellation,
replacement, or close is dropped with `STALE_RESULT_DROPPED` and a correlated
motion interrupted failure. The motion sidecar never starts or advances a turn
generation.

Terminal motion starts only after the terminal registry commit and canonical
terminal publication. It is a post-terminal side effect validated against that
committed terminal source, not a late pre-terminal completion. It does not
reopen a retired generation, change the conversation state, replace the
conversation outcome, or create a second conversation terminal.

```text
exact Control B surface: 5 files
public registration: RealtimeSession.set_motion_lifecycle_hook / PASS
factory/config hook parameter added: False / PASS
source event published before hook: True / PASS
shared EventSequence owner: RealtimeEventHub / PASS
transient completion freshness owner: RealtimeGenerationGate / PASS
terminal motion reopens generation: False / PASS
conversation terminal changed by hook/stage failure: False / PASS
missing MotionStage: MotionOutcome.NOT_CONFIGURED / PASS
unsupported adapter outcome preserved: MotionOutcome.UNSUPPORTED / PASS
root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
FW-RT6-8b aggregate tasks: 0 / 6 CLOSED
Control B status: IMPLEMENTED / AWAITING_REVIEW
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
provider/network/audio/microphone/real VTS execution: False / PASS
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-8b-B-MOTION-LIFECYCLE-ADOPTION:END -->
