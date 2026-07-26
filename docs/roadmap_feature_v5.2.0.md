# AI-Character-Framework v5.2.0 Roadmap

Working title: **Public Voice Input / Realtime Runtime Boundary Foundation**

This roadmap starts the next FW development cycle after the v5.1.0 release.

The driver is the DRC-side RT-1 requirement: DRC should not implement or depend
on FW internal STT, realtime lifecycle, cancellation, TTS queue, barge-in, or
Live2D / VTube Studio adapter internals.

Before DRC RT-1 is re-evaluated, FW should provide a new released public
runtime contract that DRC can consume through stable public APIs.

## Priority order from DRC

1. Public voice-input / STT session
2. Unified realtime lifecycle / event contract
3. Hard cancel / TTS queue / flush / barge-in
4. Public motion / Live2D / VTS adapter
5. Release a new FW version
6. Return to DRC and re-evaluate RT-1

## Non-negotiable integration rules

DRC must not:

- import FW internals;
- construct provider-specific STT / LLM / TTS clients directly;
- depend on FW checkout layout, temporary CWD changes, or sys.path hacks;
- own VTube Studio WebSocket implementation directly for FW-controlled motion;
- depend on raw local audio paths, provider payloads, or token files;
- implement hard cancel / TTS queue / flush / barge-in semantics outside the FW
  public boundary.

FW should expose provider-neutral, mock-safe contracts for these surfaces before
DRC proceeds with RT-1.

## Scope 1 - Public voice-input / STT session

Goal: allow host apps to capture or submit voice input through a public FW
session without importing STT internals.

Candidate public concepts:

- `create_voice_input_session(...)`
- `VoiceInputSession`
- `VoiceInputSessionInfo`
- `VoiceInputRequest`
- `VoiceInputResult`
- `VoiceInputEvent`
- `VoiceInputErrorCode`

Required behavior:

- mock-safe session creation path;
- provider-neutral unavailable / missing credentials result;
- optional real STT execution behind explicit guards;
- lifecycle methods: `close()`, `dispose()`, `is_closed`;
- context manager support;
- public event callbacks or event stream hook;
- no eager provider SDK import on `import framework`;
- no private token, local path, raw provider payload, or audio buffer exposure in
  public results.

## Scope 2 - Unified realtime lifecycle / event contract

Goal: define a public lifecycle and event model that can connect Text Chat,
Voice Input, Voice Output, and future motion output.

Candidate public concepts:

- `RealtimeSession`
- `RealtimeSessionInfo`
- `RealtimeEvent`
- `RealtimeEventType`
- `RealtimeState`
- `RealtimeTurn`
- `RealtimeResult`

Candidate state model:

- `idle`
- `listening`
- `transcribing`
- `thinking`
- `speaking`
- `motion`
- `interrupted`
- `failed`
- `closed`

Required behavior:

- app-facing event contract;
- provider-neutral event payloads;
- stable event names;
- lifecycle transition checks;
- cleanup / shutdown path;
- mock-safe conformance smoke;
- no provider-specific payload leakage.

## Scope 3 - Hard cancel / TTS queue / flush / barge-in

Goal: define the public cancellation and interruption boundary for realtime
interaction.

Candidate public concepts:

- `InterruptRequest`
- `InterruptResult`
- `CancelScope`
- `TTSQueueState`
- `BargeInPolicy`
- `session.interrupt(...)`
- `session.flush_output(...)`
- `session.cancel_current_turn(...)`

Required behavior:

- LLM streaming cancel boundary;
- TTS queue cancel boundary;
- queued audio flush boundary;
- current-turn interruption result;
- idempotent interruption behavior;
- provider-neutral unsupported / unavailable result;
- no fake promise of provider-level hard cancellation when a provider does not
  support it;
- smoke tests for repeated interrupt / flush / close ordering.

## Scope 4 - Public motion / Live2D / VTS adapter

Goal: allow host apps to request character motion/expression through public FW
contracts without owning VTS internals.

Candidate public concepts:

- `create_motion_session(...)`
- `MotionSession`
- `MotionSessionInfo`
- `MotionRequest`
- `MotionResult`
- `MotionArtifactRef`
- `MotionCapability`
- `MotionEvent`

Required behavior:

- provider-neutral expression / motion request model;
- Live2D / VTube Studio adapter boundary;
- VTS unavailable behavior that does not fail conversation flow;
- hotkey mapping stays FW-owned or config-owned, not DRC-owned internals;
- public errors for unavailable, unmapped, connection_failed, and closed session;
- mock-safe smoke with no real VTS connection required;
- no VTS token exposure.

## Release target

The next FW release should happen only after the public contracts above are
documented, exported, smoke-tested, package-import-ready, and verified in a
fixed release package.

Working target:

```text
v5.2.0
```

The version may be adjusted later if the implementation becomes a breaking
runtime release. Until then, `v5.2.0` is the planning label.

## DRC RT-1 re-evaluation gate

DRC can re-evaluate RT-1 only after the new FW release provides:

- package-importable public voice-input boundary;
- unified realtime lifecycle / event contract;
- public interruption / output flush semantics;
- public motion / VTS adapter boundary;
- typed provider-neutral results and errors;
- session cleanup path for all relevant runtime sessions;
- mock-safe release package verification;
- no need for DRC-side sys.path, CWD, provider-client, STT/TTS, or VTS-internal
  workarounds.
