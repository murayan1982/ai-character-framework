# v5.1.0 Host App SDK Readiness Notes

## Readiness definition

v5.1.0 is not primarily a new provider/runtime release. It is ready when an
external host app can use FW public text chat and voice output boundaries without
process-global import/CWD workarounds and without provider-specific knowledge.

## Expected verification command shape

The exact script names should be finalized during implementation, but v5.1.0
should have a command set similar to:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_installable_sdk_import_boundary.py
python scripts/smoke_public_factory_signatures.py
python scripts/smoke_public_result_error_contract.py
python scripts/smoke_runtime_capabilities.py
python scripts/smoke_provider_config_ownership.py
python scripts/smoke_public_session_lifecycle.py
python scripts/smoke_voice_artifact_opaque_contract.py
python scripts/smoke_public_contract_conformance.py
python scripts/smoke_v510_host_app_sdk_readiness.py
python scripts/check_release_package.py
```

Release verification should run on both the committed working tree and the fixed
release artifact contents.

## Mock-safe first

All readiness checks should pass without:

```text
- provider API keys
- real LLM/TTS/STT provider calls
- VTube Studio connection
- microphone access
- private audio files
- DRC app checkout
```

Real-provider execution can have separate opt-in checks, but those are not the
basis for public SDK boundary readiness.

## Session lifecycle / close contract checkpoint

Public text chat and voice output sessions now expose idempotent `close()`,
`dispose()`, context manager support, and `is_closed`. Host applications can
call these boundaries during session eviction without inspecting FW internals.

## Public contract conformance gate

v5.1.0 includes a mock-safe conformance gate:

```powershell
python scripts/smoke_v510_public_contract_conformance_gate.py
```

The gate checks the public SDK surface across docs, examples, `framework.__all__`,
factory signatures, typed text result behavior, voice output method naming,
capability snapshot behavior, session lifecycle, and opaque voice artifact refs.
It must not import provider SDKs, call providers, require credentials, or create
real audio artifacts.

## Commit 13 - Package import readiness

Added `docs/v510_package_import_readiness.md` and
`scripts/smoke_v510_package_import_readiness.py` as a mock-safe pre-release gate.
The smoke verifies that `framework` can be copied into a package-like directory
and imported from outside the repository root without provider SDK eager imports,
provider execution, checkout-layout assumptions, CWD mutation, or real audio
artifact creation.

## Commit 14 - release readiness gate

v5.1.0 adds a release-readiness gate that runs the current mock-safe public
contract, provider-config, lifecycle, opaque artifact, conformance, package
import readiness, and release package static checks from one command.

This does not create release artifacts, tags, or downstream DRC validation. It is
a pre-release decision gate for the source tree.

## v5.1.0 Fixed Release Package Builder

A fixed package builder is available at
`scripts/build_v510_fixed_release_package.py`. It creates
`release/ai-character-framework_v5.1.0.zip`, writes a local manifest, verifies
the archive layout, extracts the archive, and runs the v5.1.0 release readiness
gate inside the extracted tree. The builder is mock-safe and does not create a
git tag.

## Commit 16 - fixed release package verification

Added `docs/v510_fixed_release_package_verification.md` and
`scripts/smoke_v510_fixed_release_package_verification.py`.

This gate builds the local v5.1.0 fixed release package, validates the manifest,
checks release zip hygiene, extracts the package outside the repository root, and
runs a mock-safe public API exercise from a host-app-like CWD. Generated release
artifacts remain local evidence unless intentionally tracked.

## Commit 17 - final release tag readiness

Added a final v5.1.0 pre-tag readiness checkpoint:
`scripts/smoke_v510_final_release_tag_readiness.py`.

This checkpoint runs the existing release readiness gate, fixed release
package verification, and release package check; verifies the generated
fixed release ZIP and manifest; checks local-secret hygiene; and optionally
enforces a clean Git working tree before creating the `v5.1.0` tag.

## Post-release note cleanup

Added `docs/release_notes_v5.1.0.md` as the post-release note for the tagged
v5.1.0 release.

The note records the public host-app integration surface, validation evidence,
known transition baseline, non-goals, and local release artifact policy without
moving or rewriting the already-pushed `v5.1.0` tag.

## v5.2.0 planning start - DRC-driven runtime contracts

After the v5.1.0 release, the next framework cycle starts from DRC RT-1 needs.

Priority order:

1. Public voice-input / STT session
2. Unified realtime lifecycle / event contract
3. Hard cancel / TTS queue / flush / barge-in
4. Public motion / Live2D / VTS adapter
5. Release a new FW version
6. Return to DRC and re-evaluate RT-1

This is documented in `docs/roadmap_feature_v5.2.0.md` and tracked by
`docs/v520_drc_runtime_contract_checklist.md`.

## v5.2.0 voice-input inventory checkpoint

Added `docs/v520_voice_input_stt_inventory.md` and
`scripts/smoke_v520_voice_input_inventory.py`.

This checkpoint records the public voice-input / STT session direction before
implementation, including candidate public symbols, provider-neutral result
shape, guarded real execution, lifecycle expectations, event expectations, and
DRC non-dependency rules.

## v5.2.0 public voice-input type checkpoint

Added the first public voice-input / STT contract types:

- `VoiceInputOutcome`
- `VoiceInputErrorCode`
- `VoiceInputRequest`
- `VoiceInputResult`

This checkpoint is provider-neutral and mock-safe. It does not add real STT
execution yet.

## v5.2.0 public voice-input session skeleton checkpoint

Added the first public voice-input session boundary:

- `create_voice_input_session(...)`
- `VoiceInputSession`
- `VoiceInputSessionInfo`

The skeleton is mock-safe, provider-neutral, lifecycle-aware, event-capable, and
does not execute real STT providers yet.

## v5.2.0 voice-input capability preflight checkpoint

Added public voice-input / STT capability preflight symbols:

- `VoiceInputProviderStatus`
- `VoiceInputProviderConfig`
- `VoiceInputCapabilities`
- `resolve_voice_input_provider_config(...)`
- `get_voice_input_capabilities(...)`

The preflight is mock-safe, credential-value-safe, and does not execute real STT.

## v5.2.0 voice-input session preflight wiring checkpoint

Wired public voice-input capability preflight into `VoiceInputSession`.

`listen_result(...)` now returns status-specific provider-neutral unavailable
results for disabled, missing-credentials, provider-execution-guarded,
unsupported-provider, and real-STT-not-implemented states.

## v5.2.0 voice-input host-app examples checkpoint

Added mock-safe public voice-input examples for host apps:

- capability preflight
- session text fallback
- missing-credentials handling

The examples use only public `framework` imports and do not execute real STT.

## v5.2.0 voice-input conformance gate checkpoint

Added `scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`.

The gate verifies the public voice-input / STT contract so far: exports,
provider-safe import, factory signature, request/result helpers, capability
preflight, session lifecycle/events, and public-only host-app examples.

## v5.2.0 realtime lifecycle / event inventory checkpoint

Started priority 2 of the DRC-driven v5.2.0 work: unified realtime lifecycle /
event contract.

Added `docs/v520_realtime_lifecycle_event_inventory.md` and
`scripts/smoke_v520_realtime_lifecycle_event_inventory.py`.

This checkpoint records candidate public realtime symbols, lifecycle states,
event types, event payload safety rules, turn model direction, and relationship
to existing public Text Chat / Voice Input / Voice Output contracts.

## v5.2.0 public realtime lifecycle event type checkpoint

Added the first public realtime lifecycle / event contract types:

- `RealtimeState`
- `RealtimeEventType`
- `RealtimeErrorCode`
- `RealtimeEvent`
- `RealtimeTurn`
- `RealtimeTurnResult`

This checkpoint is provider-neutral and mock-safe. It does not add realtime
session orchestration yet.

## v5.2.0 public realtime session skeleton checkpoint

Added the first public realtime session boundary:

- `create_realtime_session(...)`
- `RealtimeSession`
- `RealtimeSessionInfo`

The skeleton is mock-safe, provider-neutral, lifecycle-aware, event-capable, and
does not execute real STT / LLM / TTS / motion providers yet.

## v5.2.0 realtime host-app examples checkpoint

Added mock-safe public realtime examples for host apps:

- session event flow
- event payload mapping
- closed-session behavior

The examples use only public `framework` imports and do not execute real
STT / LLM / TTS / motion providers.

## v5.2.0 realtime conformance gate checkpoint

Added `scripts/smoke_v520_realtime_public_contract_conformance_gate.py`.

The gate verifies the public realtime lifecycle / event contract so far:
exports, provider-safe import, factory signature, lifecycle/event/turn types,
session lifecycle/events, and public-only host-app examples.

## v5.2.0 hard cancel / TTS queue / flush / barge-in inventory checkpoint

Started priority 3 of the DRC-driven v5.2.0 work: public interruption and output
control.

Added `docs/v520_cancel_tts_queue_barge_in_inventory.md` and
`scripts/smoke_v520_cancel_tts_queue_barge_in_inventory.py`.

This checkpoint records candidate public symbols, session methods, interrupt
scopes, TTS queue / flush behavior, barge-in policy behavior, honest capability
requirements, and relationship to existing public runtime contracts.

## v5.2.0 public interrupt / output control type checkpoint

Added the first public hard-cancel / TTS queue / flush / barge-in contract
types:

- `InterruptScope`
- `InterruptReason`
- `InterruptOutcome`
- `InterruptRequest`
- `InterruptResult`
- `TTSQueueState`
- `OutputFlushOutcome`
- `OutputFlushRequest`
- `OutputFlushResult`
- `BargeInPolicyMode`
- `BargeInPolicy`
- `BargeInDecision`

This checkpoint is provider-neutral and mock-safe. It does not add real
cancellation, queue flush, playback stop, or barge-in detection yet.

## v5.2.0 realtime interrupt / output-control wiring checkpoint

Wired public interrupt / output-control types into `RealtimeSession`.

The public session now exposes mock-safe interrupt, cancel-current-turn,
output-flush, queue-state, and barge-in policy/decision methods. These return
typed provider-neutral results and do not execute real hard cancel, TTS queue
flush, playback stop, provider cancel, or barge-in detection.
