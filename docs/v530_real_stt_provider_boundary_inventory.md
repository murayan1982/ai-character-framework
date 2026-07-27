# v5.3.0 Real STT Provider Boundary Inventory

Status:

```text
STT-1a: ACCEPTED
STT-1b: READY pending next small commit
```

## Reason

DRC RT-2 has completed microphone permission, capture lifecycle, private
temporary artifact handling, opaque capture ID handling, and cleanup.

DRC RT-3 remains blocked because the framework does not yet expose a public real
STT provider execution boundary for host-captured audio.

## Current v5.2.0 framework state

The v5.2.0 public voice-input contract exists:

- public `VoiceInputRequest`
- public `VoiceInputResult`
- public `VoiceInputSession`
- public `VoiceInputSessionInfo`
- public voice-input capability preflight
- mock-safe provider-neutral session behavior

## Global capability inventory note

The v5.2.0 baseline already exposes voice-input status through the global
capability surface. STT-1a records that as existing behavior and does not change
runtime capability code.

The missing pieces for real STT handoff are:

- provider-neutral host-audio source contract
- lazy provider adapter protocol
- fake provider adapter for contract tests
- guarded real provider adapter
- public session wiring that accepts host-captured audio

## Design decision

The first real STT path should not make the framework open the device microphone.

The DRC path should be:

```text
host app capture -> opaque/private audio source -> FW public voice-input API -> guarded STT provider adapter -> typed VoiceInputResult
```

This keeps responsibility clear: host app owns permission prompts, OS recording,
capture limits, and local cleanup; FW owns provider-neutral STT behavior; DRC
does not import FW internals or provider-specific code.

## STT-1b target

STT-1b should add a provider-neutral host-audio source contract.

Candidate public shape:

```text
VoiceInputAudioSource
VoiceInputAudioFormat
VoiceInputAudioRef
```

The contract should support opaque host-captured audio handoff without requiring
the framework to open the microphone.

## STT-1a does not do

- runtime code change
- provider dependency addition
- provider client creation
- API key read
- real STT provider call
- audio file read
- raw audio processing
- microphone access
- DRC code change
- public API change
- release package creation
- tag creation

## STT-1a acceptance evidence

Local verification accepted STT-1a with these facts:

```text
v530_real_stt_provider_boundary_inventory_status: accepted
v530_source_commit: c2e247064987c94bf735a359700f0462439b8286
v530_public_voice_input_contract_present: True
v530_public_real_stt_execution_present: False
v530_legacy_microphone_stt_present: True
v530_host_audio_source_contract_present: False
v530_lazy_provider_adapter_present: False
v530_global_capability_voice_input_synced: True
v530_framework_import_provider_safe: True
v530_default_provider_execution_allowed: False
v530_runtime_code_changed: False
v530_provider_execution_executed: False
v530_microphone_accessed: False
v530_audio_handled: False
v530_drc_rt3_status: blocked-pending-framework-real-stt
v530_stt1b_authorization: ready-for-stt1b
```

The v5.2.0 compatibility gates also passed:

- `smoke_v520_voice_input_inventory.py`
- `smoke_v520_voice_input_public_contract_conformance_gate.py`
- `smoke_v520_release_readiness_gate.py`

No provider execution, microphone access, raw audio handling, DRC change, release
package, tag creation, or runtime code change was performed.

## STT-1b implementation inventory note

After STT-1b implementation, the provider-neutral host-audio source contract is
present and exported from the public framework root.

The inventory now expects:

```text
v530_host_audio_source_contract_present: True
```

The contract remains data-only. It does not read audio, access microphones, call
providers, read API keys, or execute real STT.

## STT-1b data-only runtime allowlist note

The inventory smoke allows the STT-1b public data-only host-audio contract files
while continuing to reject unapproved provider/audio runtime changes.

Allowed STT-1b implementation files:

```text
framework/__init__.py
framework/voice_input_audio.py
docs/v530_host_audio_source_contract.md
scripts/smoke_v530_host_audio_source_contract.py
```

This does not mean provider execution, microphone access, audio file reads, raw
audio handling, or real STT execution occurred.

## STT-1b acceptance sync note

STT-1b is accepted.

The public host-audio source contract is now present as a data-only framework
boundary, while lazy provider adapter execution remains absent:

```text
v530_host_audio_source_contract_present: True
v530_lazy_provider_adapter_present: False
v530_provider_execution_executed: False
v530_microphone_accessed: False
v530_audio_handled: False
```

STT-1c is now ready to start in the next small commit.

## STT-1c lazy provider adapter inventory note

After STT-1c implementation, the lazy provider adapter protocol and fake adapter
are present.

The inventory now expects:

```text
v530_lazy_provider_adapter_present: True
```

This does not mean real provider execution occurred. The fake adapter remains
mock-safe and does not read audio, access microphones, call providers, or read
API keys.

## STT-1c acceptance sync note

STT-1c is accepted.

The lazy provider adapter protocol and fake adapter are now present:

```text
v530_lazy_provider_adapter_present: True
v530_provider_execution_executed: False
v530_microphone_accessed: False
v530_audio_handled: False
v530_stt1c_status: accepted
v530_stt1d_authorization: ready-for-stt1d
```

The fake adapter is mock-safe and returns typed `VoiceInputResult` without
reading audio or executing a real provider.

STT-1d is now ready to start in the next small commit.
