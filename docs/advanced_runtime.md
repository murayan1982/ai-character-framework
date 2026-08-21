# Advanced Runtime Behavior

<!-- FW-RT6-14b-ADVANCED-RUNTIME-FREEZE:BEGIN -->

This document is the frozen v6.0.0 source contract for advanced realtime behavior.
It describes the repository at implementation baseline
`7d65771784ddc5409076909f874d098758486d98`.

The source version is `6.0.0.dev0`. The v6.0.0 source candidate is documentation
frozen, but v6.0.0 has not been published. The latest published release remains
v5.5.0.

## Execution profiles

`RealtimeSession` preserves two deliberately different profiles:

| Profile | Selection | Contract |
| --- | --- | --- |
| `v5_skeleton` | Default, including omitted `real_runtime_enabled` | Provider-free compatibility behavior; existing v5 standalone runtimes remain valid. |
| `v6_unified` | Explicit `real_runtime_enabled=True` | Guarded v6 composition and preflight contract. Incomplete configuration is rejected with typed public results rather than silently falling back. |

Selecting `v6_unified` does not by itself claim that production provider
orchestration is available through `RealtimeSession.run_turn()`. Real provider
acceptance for FW-RT6-13c used the dedicated guarded operator surface; it did not
enable unified real-provider orchestration in `RealtimeSession`.

Applications should inspect the public construction result and capability snapshot
before exposing controls:

```python
from framework import RealtimeSession, RealtimeSessionConfig

session = RealtimeSession(RealtimeSessionConfig(real_runtime_enabled=True))
construction = session.construction_result
capabilities = session.capabilities()

if construction.runtime_executable and capabilities.real_runtime_enabled:
    # Continue to the application-specific preflight and execution boundary.
    pass
else:
    # Keep the UI unavailable and surface the public reason/code only.
    pass
```

Do not infer availability from the presence of credentials, provider packages, or
private configuration files.

## Identity, ordering, and terminality

Runtime-emitted canonical events carry stable session identity and a monotonic
sequence. Turn and generation identity are present where the event belongs to a
turn; session-level events can omit them. Consumers must use the applicable
identity and sequence fields instead of timing or provider callbacks to order work.

The canonical lifecycle is:

```text
session created/started
  -> turn started
  -> zero or more stage events
  -> exactly one terminal turn event
  -> optional later turns
  -> session closed
```

The public terminal outcomes are `completed`, `interrupted`, `cancelled`, `failed`,
`rejected`, and `closed`. A turn has exactly one terminal outcome. Late stage
results and late provider artifacts are rejected after terminalization and can be
reported as `realtime.stale_result.dropped` or
`realtime.audio.invalidated` without reopening the turn.

Applications must not:

- synthesize a second terminal outcome;
- treat arrival time as ordering authority;
- attach an artifact to a different session or turn;
- mutate an event envelope or capability snapshot;
- expose private provider payloads through public metadata.

## Interruption and barge-in

Interruption is cooperative unless a capability explicitly states otherwise.
`RealtimeSession.interrupt(...)` reaches active framework work, suppresses future LLM
delivery, clears pending TTS work, invalidates late audio, and completes with a
typed interrupt result.

`provider_hard_cancel_supported=False` means exactly that: the framework does not
claim that an already-sent provider request was physically cancelled. The public
contract is delivery suppression and deterministic terminalization.

The natural-turn controls introduced during FW-RT6-12 are capability-gated. Their
default posture remains disabled or unsupported. They are experimental input
controls, not a promise of concurrent microphone capture, provider cancellation,
or production barge-in UX.

## TTS work and host playback

Generation ownership and playback ownership are separate:

- the framework can cancel queued generation work, flush pending work, reject late
  artifacts, and request that the host stop playback;
- the host owns physical playback unless an explicit adapter says otherwise;
- a playback-stop request is not a playback-stop acknowledgement;
- the framework does not claim physical speaker stop from an unacknowledged
  request.

Hosts should acknowledge the matching session/turn request only after their player
has stopped or invalidated the relevant audio.

## Recovery, reset, and close

Use typed public results and recovery actions rather than parsing exception text.
The public recovery actions are `none`, `reuse_session`, `reset_turn`,
`reset_session`, `reconnect`, `close_session`, and `permanent_failure`.

Reset and close are distinct:

- turn reset clears turn-scoped state and does not reopen an already terminal turn;
- session reset follows the public lifecycle transition contract;
- close is idempotent, rejects new work, cleans pending work, and emits the session
  terminal boundary exactly once;
- stale provider callbacks after reset or close are ignored or reported through
  sanitized public events.

## Guarded real-runtime composition

`framework.guarded_real_runtime` provides the composition boundary used by the
real-runtime acceptance tooling. It validates explicit stage ownership,
configuration completeness, compatible capabilities, and cleanup behavior before
execution.

The composition boundary does not:

- read `.env` or private evidence on import;
- import provider SDKs on the provider-free path;
- own microphone capture or host playback;
- print credentials, private paths, prompts, transcripts, model identifiers,
  hotkey selectors, raw audio, provider payloads, or raw exceptions;
- turn the FW-RT6-13c operator into general `RealtimeSession` orchestration.

## Capability-first integration

Applications should build UI and control flow from `session.capabilities()`.
Important capability areas include text generation, voice input, voice output,
motion, streaming, cooperative cancellation, backpressure, accepted audio formats,
pending flush, audio invalidation, playback ownership, and host stop handshakes.

The exact field and event inventory is frozen in
[`v600_capability_event_error_reference.md`](v600_capability_event_error_reference.md).
Integration ownership and compatibility rules are in
[`app_integration_contract.md`](app_integration_contract.md), and migration steps
are in [`v600_v5_to_v6_session_migration.md`](v600_v5_to_v6_session_migration.md).

## Security and redaction

Public diagnostics are an allowlisted surface. Keep these values outside the
repository and outside public events/logs:

- API keys, tokens, and `.env` contents;
- private configuration and evidence paths;
- raw audio and provider request/response bodies;
- transcripts, LLM text, prompts, model identifiers, voice identifiers, and VTS
  hotkey selectors;
- raw provider exceptions that could contain private material.

Use stable public codes, stage names, booleans, and sanitized summaries instead.

## Non-goals and experimental scope

The v6.0.0 source freeze does not claim:

- a published v6.0.0 package or release artifact;
- default activation of real providers, network, microphone, playback, or VTS;
- provider hard-cancel guarantees;
- framework ownership of physical playback stop;
- production `RealtimeSession` unified real-provider orchestration;
- replacement or removal of v5 standalone runtimes;
- a finished consumer application;
- completion of FW-RT6-14c packaging and release work.

Natural-turn controls and guarded real-runtime/operator surfaces stay explicitly
capability-gated. Provider-specific behavior remains adapter and host policy.

## Verification

From the repository root:

```bash
python scripts/check_v600_documentation_freeze.py
python scripts/check_v600_aggregate_conformance.py --source-only
python -m unittest discover -s tests
```

The documentation checker is provider-free. It validates the exact FW-RT6-14b
surface, documentation links and freeze markers, the 127-name root-public manifest,
the FW-RT6-14a aggregate gate, and the 828-test Framework unit suite. It does not
read private configuration/evidence or execute provider, network, microphone,
playback, or VTS operations.

<!-- FW-RT6-14b-ADVANCED-RUNTIME-FREEZE:END -->
