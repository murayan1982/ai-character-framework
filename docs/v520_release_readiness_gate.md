# v5.2.0 Release Readiness Gate

This checkpoint adds a source-tree release readiness gate for FW v5.2.0.

It verifies that the DRC-driven public runtime contracts are mock-safe,
provider-neutral, and app-facing before fixed release packaging begins.

## Covered priorities

The gate covers the four v5.2.0 priorities:

1. Public voice-input / STT session
2. Unified realtime lifecycle / event contract
3. Hard cancel / TTS queue / flush / barge-in
4. Public motion / Live2D / VTS adapter

## Required conformance gates

The release readiness gate requires these mock-safe conformance gates to pass:

- `scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- `scripts/smoke_v520_realtime_public_contract_conformance_gate.py`
- `scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py`
- `scripts/smoke_v520_motion_public_contract_conformance_gate.py`

It also requires the baseline release package check:

- `scripts/check_release_package.py`

## Public contract readiness

The release readiness gate verifies that the framework root exposes the public
symbols DRC needs for RT-1 style integration:

- voice input / STT symbols
- realtime session and lifecycle event symbols
- interrupt / output-control symbols
- motion session and adapter symbols

Host apps must be able to use `import framework` without eager provider runtime
imports.

## Honest runtime status

This gate does not claim real runtime implementation.

v5.2.0 public contracts remain honest about what is implemented:

- real STT is not implemented;
- real realtime orchestration is not implemented;
- real hard cancel is not implemented;
- real TTS queue flush / playback stop is not implemented;
- real barge-in audio detection is not implemented;
- real Live2D / VTS adapter runtime is not implemented.

The release readiness gate accepts mock-safe, provider-neutral public contracts
with typed unavailable / not-implemented / closed-session behavior.

## Provider safety

The gate must not execute or import provider/runtime modules such as:

- Whisper / speech-recognition / microphone libraries
- LLM provider SDKs
- TTS provider SDKs
- audio playback internals
- websocket / VTS / Live2D runtime modules

Private token values, raw audio paths, private model paths, provider payloads,
and operator evidence must not be required.

## Next checkpoint

After this source-tree release readiness gate passes, the next checkpoint should
add the fixed v5.2.0 release package builder.

Suggested next commit:

```text
docs/test: add fixed release package builder for v5.2.0
```
