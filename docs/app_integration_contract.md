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
