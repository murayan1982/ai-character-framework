# v5.1.0 Public Contract Inventory

Updated: 2026-07-26

## Purpose

This inventory freezes the current public surface before v5.1.0 starts changing
host-app integration behavior.

v5.0.0 proved that the public Text Chat and Voice Output boundaries can work in
a real app. Daily Rhythm Companion (DRC) was able to route daily data through FW
Text Chat, generate a response, send that response through the FW Voice Output
boundary, create TTS audio, publish an opaque DRC-owned audio URL, and play it in
Flutter Web / PC without importing FW internal TTS modules or provider SDKs.

v5.1.0 should now reduce the cost of embedding FW from host apps. The first step
is to record the current public API, known mismatches, and release-gate gaps
before changing implementation.

## Inventory scope

This inventory covers the public contract surfaces that DRC currently depends on
or needs for v3.0.0 planning:

```text
- framework.__all__ public exports
- create_text_chat_session() factory presence and signature
- create_voice_output_session() factory presence and signature
- public Voice Output request/result/session info types
- Voice Output session callable methods
- mock-safe Voice Output result shape
- public examples that should remain runnable without provider credentials
- import safety for provider/internal modules
- README/docs/API alignment risks
```

This inventory intentionally does **not** execute real provider calls and does
not mark DRC real evidence as accepted.

## Current public exports to preserve

The v5.1.0 baseline should preserve at least these public exports:

```text
create_text_chat_session
TextChatSessionInfo
create_voice_output_session
VoiceOutputSession
VoiceOutputSessionInfo
VoiceOutputRequest
VoiceOutputResult
```

Additional existing public symbols may remain, but v5.1.0 should avoid changing
or removing these without an explicit deprecation/migration note.

## Current known risks

### 1. Checkout-oriented import integration

DRC still carries compatibility code around FW checkout discovery, `sys.path`,
`sys.modules`, import cache invalidation, and temporary CWD changes.

v5.1.0 should move FW toward a normal installable SDK that can be imported from
arbitrary host-app CWDs.

### 2. Factory and method name drift

Host apps should not need to inspect signatures or probe multiple public method
names.

Known area to resolve under FW-F2:

```text
README / docs examples may describe session.speak(...)
current implementation may expose session.create_output(...)
```

The inventory smoke records this mismatch if present. It does not fail yet,
because Commit 2 is an inventory checkpoint. Later conformance gates should make
this kind of mismatch fail release readiness.

### 3. Text Chat result normalization

Text Chat should move toward a typed public result, similar to the Voice Output
result contract, so host apps do not parse strings or broad exception text for
normal control flow.

### 4. Capability discovery

Session info currently exposes some static support flags. DRC needs a runtime
snapshot that separates `supported`, `configured`, `available`, `blocked`, and
`unavailable` with provider-neutral reason codes.

### 5. Lifecycle and artifact contracts

Public sessions should expose consistent close/dispose/context-manager behavior.
Voice artifacts should remain opaque, never expose raw local paths, and guarantee
that generated audio has exactly one public handoff: URL or artifact reference.

## Commit 2 acceptance

```text
- current public exports are enumerated in docs
- a mock-safe inventory smoke imports framework and records public signatures
- Voice Output public request/result shape is checked without provider execution
- known docs/API mismatch around speak/create_output is recorded without failing
- provider/internal modules remain lazy during public import
- this commit does not change runtime behavior, DRC code, providers, or release artifacts
```

## Next implementation order

After this inventory, v5.1.0 should proceed in this order:

```text
FW-1  Installable SDK / project-root independence
FW-2  Stable factory signatures and docs/API conformance
FW-3  Typed result / provider-neutral error
FW-4  Capability snapshot
FW-5  Provider config ownership
FW-6  Session lifecycle and close/dispose
FW-7  Opaque voice artifact hardening
FW-8  Public contract conformance gate
```

Realtime voice input, realtime lifecycle, hard cancellation, TTS queue/flush, and
motion/VTS public adapters should wait until the P0 host-app integration contract
is stable.
