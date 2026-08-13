# v5 standalone sessions to the v6 realtime session

This guide records the public, provider-neutral migration boundary for
FW-RT6-11c. It does not enable provider execution or claim that the current
source can run production unified orchestration.

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
