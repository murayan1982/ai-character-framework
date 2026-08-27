# v6 Capability, Event, and Error Reference

<!-- FW-RT6-14c-DETERMINISTIC-RELEASE:BEGIN -->
## Current release metadata note

Source metadata and the latest published release are both `6.0.0`. FW-RT6-14c
changed no capability, event, result, error, API/schema version, or root-public
export. The separately authorized tag, asset, redownload, and clean-tree
verification completed without changing this reference vocabulary.
<!-- FW-RT6-14c-DETERMINISTIC-RELEASE:END -->

<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-14c reference publication acceptance

```text
latest published release: 6.0.0
release commit: 61e15f62d1ecc5faee016abae82200f8de56c5dd
release tag: v6.0.0 / PUSHED / VERIFIED
GitHub Release: PUBLIC / VERIFIED
FW-RT6-14c canonical tasks: 14 / 14 ACCEPTED
capability/event/error changes from publication: 0
root-public names: 127 / UNCHANGED
final acceptance sync: AWAITING_SYNC_COMMIT_PUSH
```
<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-14b-CAPABILITY-EVENT-ERROR-REFERENCE:BEGIN -->

This provider-neutral reference freezes the public v6.0.0 source-candidate
vocabulary at baseline `7d65771784ddc5409076909f874d098758486d98`.
The source version is `6.0.0.dev0`; v6.0.0 is not published, and v5.5.0 remains
the latest published release.

Python enums and dataclasses exported through `framework` are the executable
source of truth. This reference is an integration index, not a replacement for
type checking. The root-public manifest contains exactly 127 names.

## Capability snapshot

`RealtimeCapabilitySnapshot.as_dict()` exposes these top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Capability-schema identifier. Do not infer package version from it. |
| `snapshot_scope` | Global or session observation scope. |
| `snapshot_generation` | Positive generation of the immutable snapshot. |
| `session_id` | Session identity for session-scoped snapshots. |
| `text_generation` | Detailed text-generation capability. |
| `voice_input` | Detailed voice-input capability. |
| `voice_output` | Detailed voice-output capability. |
| `motion` | Detailed motion capability. |
| `supports_text_chat` | Compatibility summary boolean. |
| `supports_voice_input` | Compatibility summary boolean. |
| `supports_voice_output` | Compatibility summary boolean. |
| `supports_motion` | Compatibility summary boolean. |
| `real_runtime_enabled` | Whether the selected snapshot truthfully represents enabled real runtime. |
| `hard_cancel_supported` | Aggregate hard-cancel claim; false does not forbid cooperative cancellation. |
| `tts_queue_flush_supported` | Aggregate TTS queue-flush claim. |
| `public_metadata` | Recursively sanitized, immutable public metadata. |

Detailed capability fields are frozen as follows:

| Area | Fields |
| --- | --- |
| Text generation | `runtime`, `streaming_supported`, `cooperative_cancel_supported`, `provider_hard_cancel_supported`, `public_metadata` |
| Voice input | `runtime`, `audio_chunk_input_supported`, `partial_transcript_supported`, `final_transcript_supported`, `input_abort_supported`, `backpressure_supported`, `accepted_audio_formats`, `maximum_chunk_size`, `maximum_duration`, `public_metadata` |
| Voice output | `runtime`, `streaming_audio_supported`, `generation_cancel_supported`, `provider_hard_cancel_supported`, `pending_flush_supported`, `active_audio_invalidation_supported`, `playback_ownership`, `host_playback_stop_request_supported`, `host_playback_stop_ack_supported`, `audio_formats`, `maximum_text_size`, `public_metadata` |
| Motion | `runtime`, `request_cancel_supported`, `completion_event_supported`, `provider_neutral_intent_supported`, `public_metadata`, `stop_motion_supported` |

Capability fields are independent. For example, cooperative cancellation must not
be reported as provider hard cancellation, and a host stop-request capability must
not be reported as physical playback-stop ownership.

## Construction status

`RealtimeSessionConstructionStatus` values:

| Value | Meaning |
| --- | --- |
| `mock_ready` | Provider-free compatibility runtime is available. |
| `real_configuration_ready` | Explicit real composition passed public construction checks. |
| `configuration_incomplete` | Required stage configuration is missing. |
| `preflight_failed` | Configured stage preflight did not pass. |

`RealtimeSessionConstructionResult` contains `status`, `session_id`,
`configuration_complete`, `runtime_executable`, `real_runtime_requested`,
`real_runtime_enabled`, `missing_stage_kinds`, `failed_stage_kinds`,
`safe_message`, `retryable`, and `public_metadata`. It intentionally has no
provider objects, credential values, private paths, payloads, or raw exceptions.

## Event envelope

`RealtimeEvent` contains:

| Field | Contract |
| --- | --- |
| `type` | One `RealtimeEventType`. |
| `state`, `previous_state`, `phase` | Provider-neutral lifecycle observation. |
| `session_id`, `turn_id`, `generation_id` | Correlation identities; never substitute provider IDs. |
| `sequence` | Monotonic event order within the owning stream. |
| `boundary` | Public boundary name. |
| `public_error_code` | One `RealtimeErrorCode`. |
| `safe_message`, `retryable` | Sanitized operator/app guidance. |
| `public_metadata` | Recursively sanitized public mapping. |
| `payload` | Typed public event payload when required. |
| `terminal` | Derived terminal flag that must match the event type. |
| `timestamp`, `monotonic_timestamp` | Optional non-negative public timing observations. |

Consumers order by identity and `sequence`, not timestamp or callback arrival.
They accept exactly one terminal event for a turn and reject late artifacts.

## Event types

The 48 public `RealtimeEventType` values are:

### Session and turn

- `realtime.session.created`
- `realtime.session.started`
- `realtime.session.closed`
- `realtime.turn.started`
- `realtime.turn.completed`
- `realtime.turn.interrupted`
- `realtime.turn.cancelled`
- `realtime.turn.failed`
- `realtime.turn.rejected`

### Listening, voice input, and transcript

- `realtime.listening.started`
- `realtime.listening.completed`
- `realtime.voice_input.started`
- `realtime.voice_input.preflight`
- `realtime.voice_input.completed`
- `realtime.voice_input.failed`
- `realtime.speech.started`
- `realtime.speech.ended`
- `realtime.transcript.partial`
- `realtime.transcript.final`

### Text response

- `realtime.text_chat.started`
- `realtime.text_chat.completed`
- `realtime.response.started`
- `realtime.response.delta`
- `realtime.response.completed`

### Synthesis, audio, and playback ownership

- `realtime.voice_output.started`
- `realtime.voice_output.completed`
- `realtime.synthesis.started`
- `realtime.synthesis.completed`
- `realtime.audio.available`
- `realtime.audio.invalidated`
- `realtime.playback_stop.requested_to_host`
- `realtime.playback_stop.acknowledged_by_host`

### Motion

- `realtime.motion.requested`
- `realtime.motion.started`
- `realtime.motion.completed`
- `realtime.motion.failed`

### Interrupt, output flush, and barge-in

- `realtime.interrupt.requested`
- `realtime.interrupt.accepted`
- `realtime.interrupt.completed`
- `realtime.interrupt.unsupported`
- `realtime.output.flush.requested`
- `realtime.output.flush.completed`
- `realtime.output.flush.unsupported`
- `realtime.barge_in.detected`
- `realtime.barge_in.accepted`
- `realtime.barge_in.rejected`

### Diagnostics

- `realtime.stale_result.dropped`
- `realtime.event.overflow`

The terminal turn event types are completed, interrupted, cancelled, failed, and
rejected. `realtime.session.closed` is the session terminal boundary. Compatibility
projection can map selected canonical v6 events to retained v5 event names; hosts
must not count a projection and its canonical source as two terminal outcomes.

## Public error codes

`RealtimeErrorCode` values:

| Value | Typical public meaning |
| --- | --- |
| `none` | No public failure. |
| `unavailable` | Requested public capability is unavailable. |
| `unsupported` | Boundary exists but the operation is unsupported. |
| `interrupted` | Work ended through interruption. |
| `session_closed` | Session no longer accepts work. |
| `invalid_request` | Public request failed validation. |
| `configuration_missing` | Required public configuration is absent. |
| `stage_failed` | A configured stage failed safely. |
| `provider_error` | Provider failure was mapped to a sanitized public class. |
| `cancelled` | Work was cancelled. |
| `rejected` | Work was not admitted. |

`RealtimeExecutionErrorCode` values:

- `blocking_call_in_active_event_loop`
- `blocking_call_from_runtime_thread`

`LifecycleTransitionErrorCode` values:

- `invalid_phase_transition`
- `phase_outcome_mismatch`
- `duplicate_terminal`
- `terminal_regression`
- `session_closed`

Applications branch on the enum/code and show `safe_message` where appropriate.
They must not parse or expose raw exception text.

## Outcomes and recovery

| Enum | Values |
| --- | --- |
| `TurnOutcome` | `completed`, `interrupted`, `cancelled`, `failed`, `rejected`, `closed` |
| `InterruptOutcome` | `accepted`, `unsupported`, `no_active_turn`, `already_closed`, `not_implemented`, `failed` |
| `OutputFlushOutcome` | `flushed`, `nothing_to_flush`, `unsupported`, `not_implemented`, `failed`, `closed` |
| `RecoveryAction` | `none`, `reuse_session`, `reset_turn`, `reset_session`, `reconnect`, `close_session`, `permanent_failure` |

An `accepted` interrupt is cooperative unless hard cancellation is independently
advertised. `flushed` describes Framework-owned pending work; it does not by itself
prove that a host player or speaker stopped.

## Compatibility and ownership

- v5 standalone sessions remain public and supported.
- Default `RealtimeSession` remains `v5_skeleton` and provider-free.
- `v6_unified` is explicit-only and rejects incomplete/failed composition.
- Microphone capture and physical playback remain host-owned.
- Credentials, provider clients, VTS mapping, and private evidence remain outside
  public metadata.
- The FW-RT6-13c operator acceptance did not enable production unified
  real-provider orchestration in `RealtimeSession`.

## Non-goals and experimental scope

This reference does not announce a published v6.0.0 release, enable providers or
devices, guarantee provider hard cancel, claim Framework-owned physical playback
stop, remove v5 APIs, or authorize FW-RT6-14c packaging and publication. Natural-
turn controls remain capability-gated experimental behavior. Only an executable
snapshot from the active session is authoritative for an application's UI.

## Related contracts

- [`advanced_runtime.md`](advanced_runtime.md)
- [`app_integration_contract.md`](app_integration_contract.md)
- [`public_facade.md`](public_facade.md)
- [`v600_v5_to_v6_session_migration.md`](v600_v5_to_v6_session_migration.md)
- [`v600_aggregate_conformance.md`](v600_aggregate_conformance.md)

<!-- FW-RT6-14b-CAPABILITY-EVENT-ERROR-REFERENCE:END -->


<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-14b integrated-reference acceptance

The capability, construction, event-envelope, exact 48-event, public-error,
outcome, recovery, compatibility, ownership, non-goal, and experimental-scope
inventory is accepted at implementation commit
`72cfa09f6551e1fc3d042777733627c900237cdc`.

```text
final acceptance-sync exact surface: 8 files
capability/event/error reference: 48 EVENTS / ACCEPTED
root-public names: 127 / UNCHANGED
production Framework source changes: 0 files
test source changes: 0 files
FW-RT6-14b tasks: 8 / 8 ACCEPTED
FW-RT6-14b final acceptance sync: PASS
FW-RT6-14c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
FW-RT6-14c implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

The acceptance record changes no API/schema version and adds no event, result,
error code, capability field, provider namespace, or execution claim.
<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->
