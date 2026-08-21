# v5 standalone sessions to the v6 realtime session

This guide records the public, provider-neutral migration boundary for
FW-RT6-11c. It does not enable provider execution or claim that the current
source can run production unified orchestration.

> Current freeze note: the FW-RT6-11c sections below are retained historical
> implementation evidence. The FW-RT6-14b migration freeze at the end of this
> document is the current v6.0.0 source-candidate migration contract.

## Choose the target deliberately

The v5 standalone sessions remain supported throughout v6:

| Existing public owner | Compatibility mode | v6 composition destination |
| --- | --- | --- |
| `TextChatSession` | `v5_standalone` | text-generation stage |
| `VoiceInputSession` | `v5_standalone` | voice-input stage |
| `VoiceOutputSession` | `v5_standalone` | voice-output stage |
| `MotionSession` | `v5_standalone` | motion stage |
| default `RealtimeSession` | `v5_skeleton` | provider-free compatibility path |
| explicit unified request | `v6_unified` | injected provider-neutral stages |

Existing applications do not have to migrate all stages at once. Keep a v5
standalone session when its independent lifecycle is still required. Move to
`RealtimeSession` when one session must own shared session, turn, generation,
event, interrupt, stale-result, terminal, diagnostics, and close semantics.

## Text-only first

The provider-free text-only example uses the public `RealtimeSession` API and
the deterministic compatibility runtime:

```python
import framework

with framework.create_realtime_session() as session:
    result = session.run_turn(input_text="今日は少し眠いです。")
    print(session.compatibility_profile.mode.value)  # v5_skeleton
    print(result.outcome.value)                      # completed
```

This is a source-safe learning and integration path. Its result contains
`public_metadata["mock_runtime"] == True`; it is not evidence of provider,
network, microphone, synthesis, playback, or real motion execution.

See `examples/app_v600_realtime_text_only.py`.

## Requesting unified mode

Unified mode is requested explicitly. Supplying an injected stage without an
explicit request does not select it.

```python
import framework

session = framework.create_realtime_session(real_runtime_enabled=True)
print(session.compatibility_profile.mode.value)  # v6_unified
print(session.construction_result.status.value)  # configuration_incomplete
```

The current source truthfully reports that production unified orchestration is
not available. A missing or preflight-failed composition returns a typed
construction result. Calling `run_turn(...)` returns a typed rejected result;
it never silently executes the deterministic mock path as real unified work.

Applications may then make an explicit product decision:

- keep the rejected unified result and ask the operator to configure stages;
- continue using an existing v5 standalone session; or
- explicitly create the provider-free compatibility session for a demo,
  test, or offline experience.

See `examples/app_v600_realtime_unavailable_fallback.py`. The fallback in
that example is host-selected and remains visibly marked as mock runtime.

## Ownership changes

| Concern | v5 standalone flow | v6 realtime flow |
| --- | --- | --- |
| session lifecycle | one owner per standalone session | one `RealtimeSession` owner |
| turn/generation identity | optional standalone correlation | Framework-owned shared identity |
| event order | session-specific callbacks | canonical realtime event sequence |
| stale completion | session-specific behavior | shared generation gate |
| terminal outcome | standalone result | exactly one realtime turn terminal |
| interrupt/flush | separate public boundaries | coordinated typed result |
| playback | host-owned | still host-owned |
| motion mapping | app/plugin-owned | still app/plugin-owned through the hook |
| close/dispose | standalone close | one aggregate close result |

The migration does not move provider credentials, SDK clients, raw payloads,
private paths, microphone ownership, playback handles, or character-specific
motion mapping into host-facing Framework metadata.

## Follow-up examples

Control A establishes this guide, text-only entry point, explicit unavailable
handling, and credential-free import gate. The following executable examples
remain FW-RT6-11c Control B work:

- host-captured audio;
- interrupt and partial completion;
- local host-playback coordination;
- motion lifecycle extension hooks.

Those examples must preserve the accepted boundaries: audio capture and
playback stay host-owned, partial transcript/audio streaming is not invented,
Framework cancellation does not imply provider hard cancel, and motion mapping
stays application/plugin-owned.

## Import and credential safety

Both Control A example modules:

- import only the public `framework` root;
- perform no work at import time;
- require no provider credential;
- load no optional provider SDK when imported;
- perform no provider, network, microphone, audio, playback, or VTube Studio
  operation during the acceptance gate.

Run the Control A gate from the repository root:

```powershell
python scripts\smoke_v600_migration_examples_control_a.py
python -m unittest tests.test_migration_examples_control_a
```

<!-- FW-RT6-11c-A-MIGRATION-GUIDE:END -->


<!-- FW-RT6-11c-B-MIGRATION-EXAMPLES:BEGIN -->
## Control B executable boundary examples

Control B adds four provider-free examples without changing Framework runtime
source or claiming production unified orchestration:

```text
exact Control B implementation surface: 9 files
```

- `examples/app_v600_host_captured_audio.py`
- `examples/app_v600_interrupt_partial_completion.py`
- `examples/app_v600_local_playback_boundary.py`
- `examples/app_v600_motion_extension_hook.py`

### Host-captured audio remains a host handoff

The host-audio example intentionally uses the retained public
`VoiceInputSession` boundary. The host supplies an opaque capture identifier to
`VoiceInputAudioSource`; the Framework example does not open a microphone,
read audio bytes, resolve a private path, or upload audio. A deterministic
`FakeVoiceInputProviderAdapter` proves the public handoff without provider or
network execution.

This does not claim that the current `RealtimeSession` accepts streaming audio
chunks. Audio chunk input and partial transcript streaming remain P1 work.

### Interrupt partial completion is subsystem aggregation

The interrupt example starts one provider-free realtime turn and submits an
`InterruptRequest.user_barge_in(...)`. Its additive
`coordination_result` is terminal and may report `partial` because the targeted
subsystems have different terminal observations such as `unsupported` and
`not_active`.

The outer compatibility result remains `not_implemented` when no subsystem
reports an effective cancellation. `partial` does not mean partial transcript,
partial audio, provider hard cancellation, or successful interruption.

### Local playback remains host-owned

The playback example uses a provider-free demo session snapshot to exercise the
already accepted host coordination events. `flush_output(...)` can request a
host stop, and `acknowledge_host_playback_stop(...)` can record host receipt.
Neither the request nor the acknowledgement confirms physical media-engine or
speaker stop. The example performs no playback.

### Motion mapping remains a host/plugin extension

The motion example registers `set_motion_lifecycle_hook(...)` and maps selected
lifecycle notifications to provider-neutral `MotionRequest` values. It
configures no motion stage, so mapped requests produce typed `not_configured`
motion outcomes. The conversation still completes exactly once, and no VTube
Studio, WebSocket, network, or provider operation occurs.

### Shared example safety

All six FW-RT6-11c Control A+B examples:

- use the public `framework` root as their only Framework import;
- perform no work during module import;
- preserve required Windows/Python system environment in credential-free
  subprocess verification while removing credential-bearing variables;
- require no optional provider SDK or credential;
- execute no network, audio read, microphone, physical playback, provider, or
  real VTube Studio operation in acceptance verification.

Control B changes no root-public name, factory signature, runtime source, API
or schema version. All eight FW-RT6-11c aggregate tasks remain open until the
separately reviewed aggregate acceptance control.
<!-- FW-RT6-11c-B-MIGRATION-EXAMPLES:END -->


<!-- FW-RT6-14b-MIGRATION-FREEZE:BEGIN -->
## v6.0.0 migration freeze

This section freezes the migration contract at baseline
`7d65771784ddc5409076909f874d098758486d98`. The source version is
`6.0.0.dev0`; v6.0.0 is not yet a published release, and the latest published
release remains v5.5.0.

### Decision path

1. Keep the existing v5 standalone session if it already owns the required
   text, voice-input, voice-output, or motion lifecycle.
2. Adopt default `RealtimeSession` first when the application needs shared
   identity, ordering, terminality, interruption, stale rejection, or aggregate
   close semantics without real providers.
3. Inspect `construction_result` and `capabilities()` before exposing any v6
   control.
4. Request `real_runtime_enabled=True` only when the host has an explicit
   guarded stage composition and preflight policy.
5. Treat `configuration_incomplete` and `preflight_failed` as typed
   unavailability. Never reinterpret them as permission to execute the mock path
   under a real-runtime label.

### Minimal compatibility migration

Before:

```python
from framework import create_text_chat_session

with create_text_chat_session() as session:
    result = session.ask("hello")
```

Provider-free v6 lifecycle adoption:

```python
import framework

with framework.create_realtime_session() as session:
    capability_snapshot = session.capabilities()
    result = session.run_turn(input_text="hello")

    assert session.compatibility_profile.mode.value == "v5_skeleton"
    assert result.outcome.value == "completed"
    assert result.public_metadata["mock_runtime"] is True
```

This is a compatibility and integration path, not real-provider evidence.

### Explicit unified request

```python
import framework

session = framework.create_realtime_session(real_runtime_enabled=True)
construction = session.construction_result

if not construction.runtime_executable:
    # Display only the public status, safe message, and retryability.
    # Keep provider configuration and exceptions private.
    unavailable_status = construction.status.value
else:
    capability_snapshot = session.capabilities()
    # Continue through the host's separately reviewed execution boundary.
```

An executable construction result proves that the selected composition passed
the public construction contract. It does not transfer microphone, physical
playback, credential, private evidence, or provider-client ownership to the
Framework.

### Capability-first UI migration

Replace version tests and provider-name tests with capability tests:

| UI decision | Public source of truth |
| --- | --- |
| Enable text streaming | `text_generation.streaming_supported` |
| Enable audio chunk submission | `voice_input.audio_chunk_input_supported` plus accepted formats and limits |
| Show partial transcript | `voice_input.partial_transcript_supported` |
| Offer interrupt | cooperative-cancel and stage-specific capability fields |
| Offer output flush | `voice_output.pending_flush_supported` |
| Stop a host player | playback ownership plus stop-request/ack capabilities |
| Offer motion | `motion.provider_neutral_intent_supported` and configured runtime state |

Capability snapshots are immutable observations. A false or unsupported value
must disable the feature or route to a typed fallback; it must not be replaced by
provider knowledge hidden in the app.

### Event adapter migration

Legacy callbacks may be adapted to the canonical event stream, but the canonical
event envelope owns session ID, turn ID, sequence, and public timestamp/order
semantics. During migration:

- process each sequence once;
- correlate work by session and turn identity;
- accept exactly one terminal event per turn;
- drop artifacts after terminalization or generation invalidation;
- keep all event metadata public-safe and recursively allowlisted;
- do not treat `realtime.playback_stop.requested_to_host` as proof of physical
  stop; wait for the matching host acknowledgement.

The frozen event inventory is in
[`v600_capability_event_error_reference.md`](v600_capability_event_error_reference.md).

### Error and recovery migration

Do not parse exception strings. Branch on public enums and typed results:

- construction status for composition availability;
- `RealtimeErrorCode` for public operation failure class;
- `RealtimeExecutionErrorCode` for invalid blocking execution context;
- `LifecycleTransitionErrorCode` for lifecycle violations;
- `TurnOutcome`, `InterruptOutcome`, and `OutputFlushOutcome` for terminal results;
- `RecoveryAction` for the next safe host action.

Log stable codes, stage kinds, booleans, and counts only. Provider exceptions,
payloads, prompts, transcripts, credentials, private paths, model/voice identifiers,
audio, VTS hotkeys, and selectors remain outside public events and repository
evidence.

### Phased adoption checklist

- [ ] Record current v5 owners and close behavior.
- [ ] Add provider-free `RealtimeSession` lifecycle tests.
- [ ] Gate every control from `capabilities()`.
- [ ] Correlate events by session/turn/sequence.
- [ ] Enforce exactly-once terminal handling and stale rejection.
- [ ] Keep microphone capture and physical playback host-owned.
- [ ] Add stop-request acknowledgement only after the host stops or invalidates
      matching audio.
- [ ] Add explicit real-runtime request, private configuration, and preflight only
      after provider-free behavior is accepted.
- [ ] Retain a visible v5 or mock fallback; never disguise it as real execution.
- [ ] Run the documentation and aggregate gates before release preparation.

### Non-goals

Migration does not remove v5 standalone APIs, enable providers by default, promise
provider hard cancel, make the Framework own physical playback stop, or claim that
the accepted FW-RT6-13c operator is unified production `RealtimeSession`
orchestration. Natural-turn controls remain experimental and capability-gated.
FW-RT6-14c package, tag, and publication work is outside this freeze.

<!-- FW-RT6-14b-MIGRATION-FREEZE:END -->
