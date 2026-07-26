# Roadmap: v5.1.0 - Installable SDK / Stable Host App Integration Boundary

Updated: 2026-07-26

## Theme

```text
Installable SDK / Stable Host App Integration Boundary
```

Alternative release label:

```text
App-Embeddable SDK Foundation
```

v5.1.0 focuses on reducing the integration cost found while embedding
AI-Character-Framework (FW) in Daily Rhythm Companion (DRC). This is not a
major feature-repair release. The v4 text chat public facade and v5 voice output
public boundary worked in a real app. The next step is to make those public
boundaries easier and safer for external host apps to consume.

## Background: DRC v2.0.1 / v3.0.0 feedback

DRC successfully integrated these FW public boundaries:

```text
FW v4:
- create_text_chat_session()

FW v5:
- create_voice_output_session()
- VoiceOutputRequest
- VoiceOutputResult
```

The real app path worked:

```text
DRC daily data
→ FW public text chat boundary
→ LLM answer
→ FW public voice output boundary
→ TTS generation
→ DRC-owned opaque audio URL
→ Flutter Web / PC playback
```

DRC did not need to import FW internal TTS modules or own provider-specific TTS
SDK calls for the v5 voice output path. That confirms the v4/v5 direction:
host apps should use public framework boundaries instead of internal modules.

The remaining problem is integration cost. DRC still has thick compatibility
adapters around import, CWD, public factory variants, result normalization,
provider configuration, session cleanup, and artifact handoff. Those adapters
should be pulled back into FW public SDK contracts.

## Priority model

```text
P0: External app integration foundation
P1: Realtime voice public contract
P2: Character motion public contract
```

v5.1.0 should focus primarily on P0. Realtime voice and motion work should not
start until the install/import boundary, stable signatures, typed results,
capability model, provider config ownership, lifecycle cleanup, artifact
contract, and conformance gates are stable enough to avoid adding more DRC-side
workarounds.

## Primary goals

- Make FW usable as a normal installable Python package.
- Remove the need for host apps to mutate process-global import/CWD state.
- Stabilize public factory signatures and docs/examples around those signatures.
- Provide typed results and provider-neutral public error codes.
- Add a versioned capability snapshot API for host app decision-making.
- Centralize provider configuration ownership and precedence in FW.
- Provide consistent public session lifecycle and cleanup contracts.
- Strengthen opaque voice artifact handoff semantics.
- Add a public contract conformance gate that catches docs/API mismatch before release.

## Non-goals

v5.1.0 should avoid becoming the full realtime voice release.

Out of scope unless explicitly promoted:

- real STT provider execution
- full always-on microphone barge-in
- hard cancellation for every LLM/TTS provider
- TTS playback implementation owned by FW for web apps
- VTube Studio / Live2D real adapter execution
- DRC-side Web evidence acceptance
- changing DRC to use unreleased FW main branch code

## P0 work items

### FW-F1 — Installable SDK / project-root independence

#### Problem

DRC currently needs workarounds such as:

```text
- FRAMEWORK_ROOT / FRAMEWORK_PROJECT_ROOT resolution
- sys.path mutation
- sys.modules deletion for framework.*
- import cache invalidation
- temporary CWD change to FW root
- restoration of process-global state after each call
```

These are risky in long-running host processes such as FastAPI because CWD,
`sys.path`, and `sys.modules` are process-global.

#### Goal

FW should be installable and importable as a normal Python package:

```powershell
pip install -e <FW>
```

Host app code should be able to use public imports from any CWD:

```python
from framework import create_text_chat_session

session = create_text_chat_session(
    preset="text_chat",
    character_name="default",
)
```

FW resource lookup for presets, characters, config, examples, and default
runtime resources should be anchored to package/project resources rather than
caller CWD.

#### Acceptance

```text
- public framework imports work from an arbitrary CWD
- host apps do not need sys.path mutation
- host apps do not need sys.modules deletion
- host apps do not need import cache invalidation
- host apps do not need temporary CWD changes
- FRAMEWORK_ROOT is not required for normal installed usage
- package-install smoke tests pass
- host app smoke tests pass from a temp CWD outside the FW checkout
```

### FW-F2 — Stable public factory signatures

#### Target factories

```text
- create_text_chat_session()
- create_voice_output_session()
- future create_voice_input_session()
- future create_realtime_session()
- future create_motion_session()
```

#### Goal

Factory signatures should be keyword-only, versioned, and documented. Host apps
should not need to inspect signatures and branch across names such as
`preset`, `preset_name`, `preset_id`, `character`, `character_name`, or
`character_id`.

Candidate stable forms:

```python
def create_text_chat_session(
    *,
    preset: str = "text_chat",
    character_name: str = "default",
    project_root: str | Path | None = None,
) -> TextChatSession: ...


def create_voice_output_session(
    *,
    project_root: str | Path | None = None,
    real_tts_enabled: bool | None = None,
    artifact_dir: str | Path | None = None,
) -> VoiceOutputSession: ...
```

`project_root` should be treated as an explicit override or transitional escape
hatch, not as a required host-app integration mechanism.

#### Known current mismatch to resolve

README examples should match implementation exactly. For example, if README
uses:

```python
session.speak(...)
```

but the implementation exposes:

```python
session.create_output(...)
```

then release readiness should fail until docs, examples, and implementation are
aligned.

#### Acceptance

```text
- README examples execute as written
- docs and examples use the same factory and method names as implementation
- public factory signature snapshot tests exist
- host app signature reflection is not required
- deprecated argument aliases are handled inside FW during a defined migration window
```

### FW-F3 — Typed result and provider-neutral public error contract

#### Problem

Text chat currently relies on string returns and exceptions more than voice
output does. Host apps need to normalize multiple possible response shapes and
sanitize broad exception text.

#### Goal

Introduce a typed text chat result that follows the same public-result design as
voice output.

Candidate shape:

```python
@dataclass(frozen=True)
class TextChatResult:
    outcome: Literal[
        "completed",
        "interrupted",
        "unavailable",
        "blocked",
        "skipped",
        "rejected",
        "failed",
        "expired",
        "cancelled",
    ]
    text: str | None
    public_error_code: str | None
    safe_message: str | None
    retryable: bool
```

Common provider-neutral error code candidates:

```text
configuration_missing
preset_not_found
character_not_found
provider_unavailable
authentication_required
provider_auth_failed
provider_request_failed
rate_limited
request_cancelled
timeout
unsupported_capability
empty_response
interrupted
session_closed
```

Public result/exception surfaces must not expose:

```text
- API keys
- provider raw payloads
- private file paths
- provider-specific exception messages
- provider SDK objects/classes
- provider request parameters
```

#### Acceptance

```text
- host apps do not parse exception strings for normal control flow
- retryable/non-retryable is typed
- provider-specific details do not appear in public results
- Text Chat / Voice Input / Voice Output / Realtime share an outcome vocabulary
```

### FW-F4 — Unified runtime capability snapshot

#### Goal

Add a versioned public capability snapshot that distinguishes static support,
configuration, runtime availability, and blocked/guarded states.

Candidate API:

```python
from framework import get_capabilities

capabilities = get_capabilities()
```

Candidate capability names:

```text
text_chat
streaming_text
reset
state_events
close
soft_interrupt
hard_cancel
voice_input
incremental_transcript
voice_output
tts_queue
tts_flush
barge_in
motion_events
vts_adapter
```

Each capability should expose at least:

```text
supported
configured
available
blocked
unavailable
reason_code
safe_message
```

Important rules:

```text
Guarded does not mean implemented.
Detected does not mean connected.
Configured does not mean successful.
Fallback does not mean configured-provider success.
```

#### Acceptance

```text
- host apps can decide feature availability before calling a feature
- capability schema has a version
- configured/available/successful are not conflated
- reason codes are provider-neutral
- guarded mock-safe surfaces are not reported as real provider success
```

### FW-F5 — Provider config responsibility and precedence

#### Host apps should pass

```text
- provider-neutral intent
- character ID/name
- voice profile ID
- language
- audio format
- utterance purpose
```

#### FW should own

```text
- provider selection
- provider model IDs
- API key lookup
- provider voice IDs
- provider SDK calls
- provider-specific request parameters
- retry policy
- temporary artifacts
```

Provider env var aliases such as Gemini/Google API key compatibility should be
handled by FW rather than each host app.

#### Goal

Document and test config precedence across:

```text
typed config object
factory arguments
preset/project config
environment variables
framework defaults
```

If app override is supported, it should go through typed config objects rather
than ad-hoc provider-specific kwargs in public requests.

#### Acceptance

```text
- provider secrets are never part of host app public requests
- provider-specific params do not leak into public request types
- config precedence is documented and tested
- DRC does not bridge provider env variables for FW compatibility
```

### FW-F6 — Public session lifecycle / close / dispose

#### Goal

All public sessions should have consistent cleanup semantics.

Required surface:

```text
close()
dispose() or alias policy
context manager support
idempotent cleanup
session_closed outcome/error after close
```

Candidate usage:

```python
with create_text_chat_session(...) as session:
    result = session.ask("...")
```

Cleanup responsibilities may include:

```text
- callback removal
- background task shutdown
- provider client closing
- microphone/STT resource release
- TTS queue disposal
- temporary artifact cleanup
- motion/VTS connection close
```

#### Acceptance

```text
- close() is idempotent
- operations after close return/raise session_closed through public contract
- context manager cleanup works
- mock-safe leak tests exist
- Text / Voice Input / Voice Output / Realtime / Motion sessions share lifecycle semantics
```

### FW-F7 — Opaque voice artifact contract hardening

FW v5 voice output artifact handoff worked in DRC and should be preserved. v5.1.0
should make the contract stricter.

#### Required semantics

```text
- artifact IDs are opaque
- raw local paths are not public results
- generated audio exposes exactly one playable/public handoff
- audio_url and audio_artifact_ref are mutually exclusive
- artifact expiry is typed
- artifact missing is typed
- cleanup ownership is explicit
- content type and audio format are explicit
- provider/private path cannot be inferred from the ref
```

Candidate public type:

```python
@dataclass(frozen=True)
class VoiceArtifactRef:
    artifact_id: str
    expires_at: datetime | None
    content_type: str | None
    audio_format: str | None
```

Host apps can then copy/resolve the opaque artifact into their own delivery
surface without depending on FW internal file paths.

#### Acceptance

```text
- raw local paths never appear in public VoiceOutputResult
- expired/missing artifacts are typed outcomes
- cleanup owner is documented
- generated results have exactly one handoff: audio_url OR opaque artifact ref
```

### FW-F8 — Public contract conformance gate

#### Goal

Add a release gate that automatically catches divergence between public docs,
examples, public exports, signatures, and result models.

Minimum checks:

```text
- README public methods exist on real objects
- README examples execute or are snippet-checked
- public examples import and run mock-safe
- framework.__all__ matches documented public API list
- public factory signature snapshots are stable
- provider internal modules are not imported by public import
- public package works from arbitrary CWD
- public results contain no private/provider-specific details
- release artifact contents pass the same conformance checks
```

#### Acceptance

```text
- docs/API mismatch fails release readiness
- package-install public smoke passes
- public surface snapshot is checked on release artifact contents
```

## P1 deferred roadmap: Realtime voice public contract

v5.1.0 should document P1 requirements but does not need to implement them unless
promoted.

### FW-F9 — Public voice input / STT session

Candidate APIs:

```python
voice_input = create_voice_input_session(...)
result = voice_input.transcribe(audio_request)
```

and later incremental input:

```python
voice_input.start()
voice_input.push_audio(chunk)
voice_input.finish_input()
```

Public request/result/event contracts should be provider-neutral and mock-safe.
Real provider execution must be explicit opt-in.

### FW-F10 — Unified realtime session / lifecycle / streaming

Required state/event concepts:

```text
idle
listening
transcribing
thinking
responding
speaking
interrupting
interrupted
reconnecting
error
closed
```

Events should carry:

```text
session_id
turn_id
event_id or sequence
timestamp
event_type
public payload
```

Turn IDs or generation IDs are required so host apps can ignore stale delayed
events.

### FW-F11 — Hard cancellation / TTS queue / flush / barge-in

Public operations should distinguish:

```text
soft_interrupt
hard_cancel_llm
cancel_current_tts
flush_tts_queue
stop_playback
cancel_turn
close_session
```

Barge-in should coordinate LLM response cancellation, pending chunk discard,
current TTS cancellation, queued speech flush, playback-stop event emission, and
return to listening state.

## P2 deferred roadmap: Character motion public contract

### FW-F12 — Public motion event / Live2D / VTube Studio adapter

DRC should not directly own VTube Studio WebSocket, authentication tokens, hotkey
IDs, reconnect logic, or provider-specific payloads.

Candidate public surface:

```python
motion_session.emit(
    MotionEvent(
        type="expression",
        value="happy",
        turn_id="...",
    )
)
```

Result states should include:

```text
accepted
sent
acknowledged
skipped
unsupported
unavailable
failed
```

Real adapter execution should be explicit opt-in.

## Recommended small-commit plan

### Commit 1 — Roadmap and DRC feedback lock

```text
docs: add v5.1.0 host app integration roadmap
```

Acceptance:

```text
- v5.1.0 theme is documented as Installable SDK / Stable Host App Integration Boundary
- DRC v2.0.1/v3.0.0 feedback is summarized
- P0/P1/P2 priority model is documented
- P0 items FW-F1 through FW-F8 have goals and acceptance criteria
- P1/P2 items are recorded as deferred contracts, not immediate implementation scope
```

### Commit 2 — Public contract inventory

```text
docs/test: add public contract inventory for v5.1.0
```

Acceptance:

```text
- existing public exports are enumerated
- documented examples are checked against real objects where practical
- mismatches such as speak/create_output are recorded
- v5.1.0 implementation order is confirmed before code changes
```

### Commit 3 — Installable package smoke

```text
test: add installable SDK smoke for arbitrary CWD imports
```

Acceptance:

```text
- package can be installed editable in an isolated temp environment
- public imports work outside repo root
- smoke proves no sys.path/CWD workaround is needed by host apps
- provider SDKs/internal runtime modules remain lazy
```

### Commit 4 — Package/resource root resolver

```text
feat: add package resource root resolver for public SDK usage
```

Acceptance:

```text
- preset/character/config lookup does not depend on caller CWD
- project_root override remains available but not required
- legacy local checkout behavior remains compatible during migration
```

### Commit 5 — Stable public factory signatures

```text
feat: stabilize public factory signatures for host apps
```

Acceptance:

```text
- text and voice output factories use documented keyword-only signatures
- aliases are handled inside FW with deprecation policy
- signature snapshot test passes
```

### Commit 6 — Typed text chat result / public errors

```text
feat: add typed text chat result and provider-neutral public errors
```

Acceptance:

```text
- host apps can use typed outcomes for text chat
- provider-neutral error codes are documented
- private/provider data is sanitized from public results
```

### Commit 7 — Capability snapshot API

```text
feat: add public runtime capability snapshot
```

Acceptance:

```text
- get_capabilities() returns a versioned snapshot
- supported/configured/available/blocked/unavailable are separated
- guarded/mock-safe states do not masquerade as real provider success
```

### Commit 8 — Provider config ownership

```text
docs/test: centralize provider config ownership and precedence
```

Acceptance:

```text
- FW owns provider env alias handling
- config precedence is documented and covered by smoke tests
- host app requests remain provider-neutral
```

### Commit 9 — Public session lifecycle

```text
feat: add consistent public session close contract
```

Acceptance:

```text
- close() is idempotent across public sessions
- context manager support is documented/tested
- closed-session operations return public session_closed outcomes/errors
```

### Commit 10 — Voice artifact hardening

```text
feat/test: harden opaque voice artifact contract
```

Acceptance:

```text
- raw local paths are not public handoffs
- audio_url and audio_artifact_ref are mutually exclusive
- VoiceArtifactRef or equivalent opaque public type is documented/tested
```

### Commit 11 — Public contract conformance gate

```text
test: add public contract conformance release gate
```

Acceptance:

```text
- README/docs/examples/__all__/signatures/result models are cross-checked
- docs/API mismatch fails release readiness
- conformance checks run against release artifact contents
```

### Commit 12 — v5.1.0 readiness checklist

```text
docs/test: add v5.1.0 host app SDK readiness checklist
```

Acceptance:

```text
- release readiness separates SDK integration readiness from realtime/motion readiness
- DRC v3.0.0 restart prerequisites are documented
- standard verification command set is fixed
```

## DRC v3.0.0 restart rule

DRC v3.0.0 realtime work should not start merely because code exists on FW main.
It should start only after required FW public contracts are:

```text
- implemented
- mock-safe tested
- importable from a public package/release artifact
- free of project-root/CWD workarounds for normal use
- documented as stable public API
- covered by release readiness checks
- tagged/released with a fixed artifact
```

Until then, DRC should not add new workarounds such as FW internal imports,
provider-specific STT/TTS/LLM code, direct VTS WebSocket ownership, new sys.path
mutation, new sys.modules deletion, new import cache invalidation, new temporary
CWD changes, or new dependencies on FW checkout structure.

## Release acceptance checklist

v5.1.0 is ready when:

```text
- FW is installable and importable from arbitrary CWD
- host apps do not need sys.path/CWD/sys.modules workarounds
- public factory signatures are stable and documented
- docs/examples match implementation
- TextChatResult or equivalent typed text result exists
- provider-neutral public error codes exist
- get_capabilities() or equivalent versioned snapshot exists
- provider config ownership and precedence are documented/tested
- public sessions have idempotent close/context manager behavior
- opaque voice artifact contract forbids raw local paths
- public contract conformance gate passes
- release artifact contents pass the same checks
- DRC can remove or greatly shrink its FW compatibility adapters
```

## Follow-up versions

### v5.2.x candidates

```text
- public voice input / STT session
- mock-safe incremental transcript contract
- explicit real STT provider guard
```

### v6.0.0 candidate

```text
Realtime Voice Interaction Runtime
```

Potential scope:

```text
- unified realtime lifecycle
- streaming events
- provider-level hard cancellation where supported
- TTS queue / flush / barge-in
- motion events / VTS adapter foundation
```
