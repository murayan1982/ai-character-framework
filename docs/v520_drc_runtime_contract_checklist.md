# v5.2.0 DRC-Driven Runtime Contract Checklist

This checklist tracks the next FW development cycle driven by DRC RT-1 needs.

## Phase 0 - Planning and inventory

- [x] Record DRC-driven priority order
- [x] Define DRC integration non-negotiables
- [ ] Inventory existing STT / voice input internals
- [ ] Inventory existing realtime / event / state internals
- [ ] Inventory existing TTS interruption / queue behavior
- [ ] Inventory existing Live2D / VTS plugin and hotkey internals
- [ ] Decide final next release version label

## Phase 1 - Public voice-input / STT session

- [ ] Design public voice-input types
- [ ] Export voice-input symbols from `framework.__all__`
- [ ] Add provider-neutral result / error contract
- [ ] Add mock-safe public session lifecycle
- [ ] Add guarded real STT execution boundary
- [ ] Add examples
- [ ] Add docs
- [ ] Add smoke tests

## Phase 2 - Unified realtime lifecycle / event contract

- [ ] Define public realtime state model
- [ ] Define public event types and payload rules
- [ ] Define turn lifecycle
- [ ] Add provider-neutral failure / interruption events
- [ ] Add app-facing callback / event stream contract
- [ ] Add docs and examples
- [ ] Add conformance smoke

## Phase 3 - Hard cancel / TTS queue / flush / barge-in

- [ ] Define public interrupt request/result
- [ ] Define TTS queue state and flush semantics
- [ ] Define barge-in policy
- [ ] Add repeated interrupt / flush / close smoke
- [ ] Document unsupported-provider behavior
- [ ] Keep provider hard-cancel claims conservative

## Phase 4 - Public motion / Live2D / VTS adapter

- [ ] Define public motion request/result
- [ ] Define public motion session lifecycle
- [ ] Add VTS unavailable / unmapped behavior
- [ ] Add secret-safe VTS token boundary
- [ ] Add docs and examples
- [ ] Add mock-safe smoke

## Phase 5 - Release readiness

- [ ] Public contract inventory updated
- [ ] Public conformance gate updated
- [ ] Package import readiness updated
- [ ] Fixed release package builder updated
- [ ] Fixed release package verification updated
- [ ] Final release tag readiness added
- [ ] Release notes added
- [ ] New FW version tagged/released

## Phase 6 - Return to DRC

- [ ] DRC consumes only new FW public APIs
- [ ] DRC RT-1 re-evaluated
- [ ] No DRC provider-internal STT/TTS/VTS workaround
- [ ] No DRC sys.path/CWD/import-cache workaround

## Commit 2 - Voice-input / STT inventory

- [x] Record public voice-input / STT boundary direction
- [x] Record candidate voice-input public symbols
- [x] Record provider-neutral result / request expectations
- [x] Record lifecycle and event requirements
- [x] Record DRC non-dependency rules for STT internals
- [ ] Add public voice-input request/result type skeleton

## Commit 3 - Public voice-input request/result types

- [x] Add `framework.voice_input`
- [x] Add `VoiceInputOutcome`
- [x] Add `VoiceInputErrorCode`
- [x] Add `VoiceInputRequest`
- [x] Add `VoiceInputResult`
- [x] Export public voice-input types from `framework`
- [x] Add provider-neutral / secret-safe public type smoke
- [ ] Add public `VoiceInputSession` skeleton
- [ ] Add `create_voice_input_session(...)`

## Commit 4 - Public voice-input session skeleton

- [x] Add `VoiceInputSessionInfo`
- [x] Add `VoiceInputSession`
- [x] Add `create_voice_input_session(...)`
- [x] Export public voice-input session symbols from `framework`
- [x] Add mock-safe `listen_result(...)`
- [x] Add `text_fallback_result(...)`
- [x] Add lifecycle: `close()`, `dispose()`, `is_closed`
- [x] Add context manager support
- [x] Add provider-neutral app-facing event callback skeleton
- [ ] Add voice-input provider config / capability preflight

## Commit 5 - Voice-input capability preflight

- [x] Add `VoiceInputProviderStatus`
- [x] Add `VoiceInputProviderConfig`
- [x] Add `VoiceInputCapabilities`
- [x] Add `resolve_voice_input_provider_config(...)`
- [x] Add `get_voice_input_capabilities(...)`
- [x] Add missing-credentials / guard-blocked / unsupported-provider preflight
- [x] Keep real STT support as not implemented rather than overclaiming readiness
- [x] Add credential-value-safe smoke
- [ ] Wire capability preflight into `VoiceInputSessionInfo` and `listen_result(...)`

## Commit 6 - Voice-input session preflight wiring

- [x] Wire `get_voice_input_capabilities(...)` into `VoiceInputSession`
- [x] Add `session.capabilities`
- [x] Add `VoiceInputSessionInfo.provider_status`
- [x] Add `VoiceInputSessionInfo.supports_real_stt`
- [x] Return missing-credentials typed result from `listen_result(...)`
- [x] Return provider-execution-guard typed result from `listen_result(...)`
- [x] Return unsupported-provider typed result from `listen_result(...)`
- [x] Preserve closed-session result precedence
- [ ] Add public voice-input host-app examples

## Commit 7 - Voice-input host-app examples

- [x] Add capability preflight example
- [x] Add public session text fallback example
- [x] Add missing-credentials example
- [x] Add example smoke
- [x] Verify examples use public `framework` imports only
- [x] Verify examples do not execute real STT
- [ ] Add public voice-input contract conformance gate

## Commit 8 - Voice-input public contract conformance gate

- [x] Add public voice-input conformance gate doc
- [x] Add public export conformance checks
- [x] Add provider-safe import conformance checks
- [x] Add `create_voice_input_session(...)` signature checks
- [x] Add request/result helper checks
- [x] Add capability preflight checks
- [x] Add session lifecycle/result/event checks
- [x] Add public-only host-app example checks
- [ ] Start unified realtime lifecycle / event contract inventory

## Commit 9 - Realtime lifecycle / event inventory

- [x] Start priority 2: unified realtime lifecycle / event contract
- [x] Record candidate public realtime symbols
- [x] Record candidate lifecycle states
- [x] Record candidate realtime event types
- [x] Record public event payload safety rules
- [x] Record public turn model direction
- [x] Record relationship to existing Text / Voice Input / Voice Output contracts
- [ ] Add public realtime lifecycle event type skeleton

## Commit 10 - Public realtime lifecycle event types

- [x] Add `framework.realtime`
- [x] Add `RealtimeState`
- [x] Add `RealtimeEventType`
- [x] Add `RealtimeErrorCode`
- [x] Add `RealtimeEvent`
- [x] Add `RealtimeTurn`
- [x] Add `RealtimeTurnResult`
- [x] Export public realtime lifecycle/event types from `framework`
- [x] Add provider-neutral / secret-safe public type smoke
- [ ] Add public `RealtimeSession` skeleton
- [ ] Add `create_realtime_session(...)`

## Commit 11 - Public realtime session skeleton

- [x] Add `RealtimeSessionInfo`
- [x] Add `RealtimeSession`
- [x] Add `create_realtime_session(...)`
- [x] Export public realtime session symbols from `framework`
- [x] Add mock-safe `run_turn(...)`
- [x] Add deterministic provider-neutral event emission
- [x] Add lifecycle: `close()`, `dispose()`, `is_closed`
- [x] Add context manager support
- [x] Add closed-session result behavior
- [ ] Add public realtime host-app examples

## Commit 12 - Realtime host-app examples

- [x] Add realtime session event-flow example
- [x] Add realtime event payload mapping example
- [x] Add realtime closed-session behavior example
- [x] Add example smoke
- [x] Verify examples use public `framework` imports only
- [x] Verify examples do not execute real STT / LLM / TTS / motion providers
- [ ] Add public realtime contract conformance gate

## Commit 13 - Realtime public contract conformance gate

- [x] Add public realtime conformance gate doc
- [x] Add public export conformance checks
- [x] Add provider-safe import conformance checks
- [x] Add `create_realtime_session(...)` signature checks
- [x] Add lifecycle/event/turn type checks
- [x] Add session lifecycle/result/event checks
- [x] Add public-only host-app example checks
- [ ] Start hard cancel / TTS queue / flush / barge-in inventory

## Commit 14 - Hard cancel / TTS queue / flush / barge-in inventory

- [x] Start priority 3: hard cancel / TTS queue / flush / barge-in
- [x] Record candidate public interruption symbols
- [x] Record candidate session methods
- [x] Record interrupt scopes and reasons
- [x] Record TTS queue / flush requirements
- [x] Record barge-in policy requirements
- [x] Record honest capability requirements
- [x] Record relationship to existing public contracts
- [ ] Add public interrupt / output control type skeleton

## Commit 15 - Public interrupt / output control types

- [x] Add `framework.output_control`
- [x] Add interrupt scope / reason / outcome enums
- [x] Add `InterruptRequest`
- [x] Add `InterruptResult`
- [x] Add `TTSQueueState`
- [x] Add output flush request/result types
- [x] Add barge-in policy / decision types
- [x] Export public interrupt/output-control types from `framework`
- [x] Add provider-neutral / secret-safe public type smoke
- [ ] Wire interrupt / output-control types into `RealtimeSession`
