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
