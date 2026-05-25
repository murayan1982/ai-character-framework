# Roadmap: v5.0.0 - Public Voice Output / TTS Boundary Foundation

v5.0.0 focuses on making AI-Character-Framework safe to use as an embedded conversation and voice-output engine from external applications.

The immediate driver is feedback from Daily Rhythm Companion (DRC): DRC v2.0.0 real TTS Web audio evidence should not call FW internal `tts.voice_engine` directly, should not own provider-specific TTS implementation, and should not depend on ElevenLabs, local `ffplay`, or temporary audio playback internals.

v4.0.0 remains frozen as the TextChat public facade release. v5.0.0 adds a public voice output / TTS boundary before deeper realtime interruption work.

## Theme

```text
Public Voice Output / TTS Boundary Foundation
```

Alternative release label:

```text
App-Safe Voice Output Runtime
```

In practical terms:

```text
Let host apps request voice output through a provider-neutral FW public API while FW owns provider selection, secrets, voice IDs, model IDs, and audio generation details.
```

## Background: DRC feedback

During DRC v2.0.0 real TTS Web audio evidence work, the lack of a public voice output boundary became a blocker.

Confirmed v4.0.0 status:

- `framework.__all__` exposes TextChat public facade APIs only.
- `create_text_chat_session()` is public.
- `TextChatSessionInfo.supports_voice_output` is `False`.
- `import framework` intentionally does not import `tts.voice_engine`.
- Existing public facade smoke checks treat `tts.voice_engine` as a forbidden import.
- FW has internal TTS code in `tts/voice_engine.py` and `registry/tts.py`, but it is runtime/internal oriented.

Current internal TTS characteristics:

- ElevenLabs-oriented implementation.
- Depends on `ELEVENLABS_API_KEY`, `VOICE_ID`, and `TTS_MODEL_ID`.
- Uses local `ffplay` playback.
- Creates temporary MP3 files and removes them after playback.
- Does not expose a public Web-app-friendly result such as `audio_url`, audio bytes, or an artifact reference.

Therefore, DRC must not call `tts.voice_engine.py` directly. Doing so would couple DRC to FW internals, ElevenLabs-specific settings, and local playback behavior.

## v4.0.0 handling

v4.0.0 remains complete and frozen as the TextChat public facade release.

```text
v4.0.0: maintain as TextChat public facade release
v4.0.0: bugfix only
voice output / TTS public boundary: v5.0.0 scope
```

Do not force TTS public APIs into v4.0.0. Do not break TextChat facade import safety or responsibility separation.

## Primary goals

- Add a public voice output session boundary that external apps can use safely.
- Keep host apps provider-neutral.
- Hide provider names, provider voice IDs, API keys, model IDs, provider-specific parameters, SDK calls, and temporary file management behind FW.
- Preserve lightweight `import framework` behavior.
- Ensure API keys and provider SDKs are required only during explicit real TTS execution.
- Return Web-app-friendly voice output results where practical.
- Prepare the boundary for future OpenAI TTS or other provider adapters.
- Keep DRC real TTS evidence blocked until the public boundary exists and is used.

## Non-goals

v5.0.0 should avoid becoming too broad.

Out of scope unless explicitly promoted:

- full always-on microphone barge-in
- wake word detection
- VAD tuning
- mobile app integration
- GUI overlay
- advanced memory system
- SSML editor
- pronunciation dictionary UI
- requiring provider-level hard cancellation for every TTS provider
- exposing ElevenLabs/OpenAI-specific configuration to host apps as the public contract

## Public API direction

Candidate public API:

```python
create_voice_output_session(...)
VoiceOutputSession
VoiceOutputSessionInfo
VoiceOutputRequest
VoiceOutputResult
```

Expected host-app request shape:

```python
VoiceOutputRequest(
    text="今日は少し早めに休むとよさそうです。",
    voice_profile_id="gentle_mina_default",
    requested_audio_format="mp3",
    utterance_purpose="daily_advice",
    language_code="ja",
)
```

Host apps, including DRC, should provide only framework-level voice output intent:

- `text`
- `voice_profile_id`
- `requested_audio_format`
- `utterance_purpose`
- `language_code`

FW should own and hide:

- provider selection
- provider voice ID
- API key lookup
- model ID
- provider-specific request parameters
- ElevenLabs/OpenAI/etc. SDK calls
- temporary audio file management
- local playback implementation details

Possible result shape:

```python
VoiceOutputResult(
    request_state="unavailable | skipped | generated | failed",
    audio_ready=False,
    audio_format=None,
    audio_url=None,
    audio_artifact_id=None,
    public_message="Voice output provider is not configured.",
)
```

The exact result fields may change during implementation, but the public result must remain provider-safe.

## Import boundary requirements

`import framework` must stay lightweight.

Required behavior:

- `import framework` must not import ElevenLabs SDKs.
- `import framework` must not import `tts.voice_engine`.
- `import framework` must not run TTS provider API key validation.
- Public facade smoke tests must pass without TTS API keys.
- Real provider implementation must be lazy-imported only during explicit voice output execution.
- Provider misconfiguration should produce safe unavailable / failed results, not import-time crashes.

Existing import-safety behavior from `smoke_public_facade.py` should be preserved and extended for the voice output boundary.

## Mock-safe behavior

Without any real provider credentials:

- public voice output API can be imported
- `create_voice_output_session()` can return a session object
- `VoiceOutputSessionInfo` can be inspected
- voice output can report `unavailable` or `skipped` safely
- no provider SDK is imported
- no API key validation runs at import time
- smoke tests can verify the public API and lazy boundary

## Real-run behavior

When explicitly enabled and configured:

- real TTS generation can run through the FW boundary
- provider API keys are read from FW configuration/environment
- host apps do not know provider voice IDs or provider-specific parameters
- output can be returned in a Web-app-friendly form where practical
- local playback remains an internal/manual runtime option, not the only public result path

## DRC completion dependency

DRC v2.0.0 real TTS Web audio evidence remains blocked until FW v5.0.0 provides a public voice output boundary.

Current DRC status remains:

```text
real_tts_web_audio_output: NOT_ACCEPTED
DRC v2.0.0: NOT_RELEASED
DRC-side change target: none until FW public boundary exists
```

DRC must not:

- import `tts.voice_engine` directly
- own ElevenLabs/OpenAI provider code
- own provider voice IDs
- treat local `ffplay` playback as Web evidence
- mark real TTS evidence as accepted before public boundary validation

After FW v5 boundary is available, DRC can resume and target status such as:

```text
engine: framework
adapter_mode: framework
real_tts_enabled: true
framework_root: pass
framework_voice_output_boundary: pass
framework_voice_output_public_boundary: pass
capability.status: available
```

DRC evidence completion still requires Web UI execution, actual playback confirmation, screenshot/private evidence handling, marker-only evidence JSON, and acceptance validator success.

## TTS provider boundary direction

The current TTS implementation is ElevenLabs-oriented. v5.0.0 should avoid hardening ElevenLabs assumptions into public app-facing contracts.

Recommended internal direction:

- define provider-neutral voice output request/result types
- map `voice_profile_id` to provider-specific settings inside FW
- keep provider adapters lazy and internal
- start with the existing ElevenLabs implementation behind an adapter
- allow future OpenAI TTS or other adapters without changing DRC integration
- keep `stop`, `flush`, and `is_speaking` behavior behind runtime/provider boundaries

Possible future internal shapes:

```python
class TTSProvider:
    def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
        ...

class VoiceOutputSession:
    def speak(self, request: VoiceOutputRequest) -> VoiceOutputResult:
        ...
```

v5.0.0 does not need to finalize every provider abstraction, but it should not expose provider-specific details through the public API.

## Relationship to realtime interruption work

The earlier v5.0.0 roadmap focused on realtime voice interruption, cancellation, TTS stop/flush, and state transitions.

That work remains important, but it should build on top of the public voice output boundary instead of coupling directly to the current ElevenLabs/`ffplay` implementation.

Recommended order:

1. public voice output / TTS boundary
2. import-safe public session contract
3. provider-neutral request/result types
4. lazy provider adapter
5. docs and app integration example
6. then deeper interruption, TTS stop/flush, and realtime runtime behavior

## Documentation targets

Update or add:

- `roadmap_feature_v5.0.0.md`
- `public_facade.md` or app SDK docs
- voice output / TTS boundary docs
- `voice_output_policy.md` if present
- `voice_output_artifact_result_contract.md`
- `advanced_runtime.md` once interruption work resumes
- `RELEASE_NOTES.md`

Docs should clearly distinguish:

- public provider-neutral FW contract
- internal provider-specific implementation
- mock-safe behavior
- real-run behavior
- DRC evidence dependency
- future realtime barge-in work

## Example targets

Possible examples:

- `examples/app_voice_output_integration.py`
- `examples/public_voice_output.py`
- `examples/voice_output_unavailable.py`

Example goals:

- external app creates voice output session
- app passes `VoiceOutputRequest`
- provider details stay hidden
- provider unavailable returns safe result
- import remains lightweight

## Testing targets

Tests should cover:

- `framework.__all__` exposes public voice output API
- `import framework` does not import provider SDKs
- `import framework` does not import `tts.voice_engine`
- voice output session can be created without API keys
- session info hides provider details
- provider unavailable returns a safe public result
- real provider implementation is lazy-loaded only during explicit execution
- examples import without provider credentials
- release package checks pass

Existing smoke scripts to extend:

```powershell
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/check_release_package.py
```

Potential new scripts:

```powershell
python scripts/smoke_voice_output_public_boundary.py
python scripts/smoke_voice_output_unavailable.py
python scripts/smoke_voice_output_import_safety.py
python scripts/smoke_voice_output_artifact_result_contract.py
```

## Suggested small-commit plan

### Commit 1 - Roadmap and scope lock

```text
docs: add v5.0.0 voice output boundary roadmap
```

Acceptance:

- v5.0.0 theme is documented as Public Voice Output / TTS Boundary Foundation.
- DRC feedback is captured.
- v4.0.0 is explicitly frozen as TextChat public facade.
- import boundary, mock-safe, and real-run requirements are documented.

### Commit 2 - Public voice output session contract

```text
feat: add public voice output session contract
```

Candidate changes:

- add `framework/audio/__init__.py`
- add `framework/audio/voice_output.py`
- update `framework/__init__.py`
- update facade/public API aggregation if needed

Acceptance:

- `create_voice_output_session` is public.
- `VoiceOutputSession`, `VoiceOutputSessionInfo`, `VoiceOutputRequest`, and `VoiceOutputResult` are public types.
- API keys are not required for import/session info.
- real synthesis does not need to work yet.

### Commit 3 - Public facade smoke coverage

```text
test: extend public facade smoke for voice output boundary
```

Acceptance:

- public API expected list includes voice output boundary.
- import safety still forbids `tts.voice_engine` and provider SDK imports during `import framework`.
- unavailable provider behavior is safe and public-safe.

### Commit 4 - Lazy TTS provider adapter

```text
feat: add lazy TTS provider adapter
```

Acceptance:

- provider SDK/import is lazy.
- ElevenLabs implementation remains internal.
- provider settings are FW-owned.
- Web-app-friendly result path is introduced or designed.

### Commit 5 - App integration docs/example

```text
docs: add app voice output integration example
```

Acceptance:

- DRC-style host app usage is documented.
- `voice_profile_id`, `text`, and `requested_audio_format` are shown.
- provider secrets and voice IDs stay FW-side.

### Commit 6 - Real TTS opt-in boundary checklist

```text
docs/test: add real TTS opt-in boundary checklist
```

Acceptance:

- real TTS remains default-off.
- provider selection and secrets remain FW-owned.
- unsupported or underconfigured providers return safe `unavailable` results.
- DRC real TTS evidence remains blocked and not accepted.

### Commit 7 - Voice output artifact result contract

```text
feat/test: define voice output artifact result contract
```

Acceptance:

- `VoiceOutputResult` documents and exposes an app-safe handoff contract.
- `audio_ready`, `audio_format`, `audio_url`, and `audio_artifact_ref` semantics are documented.
- unavailable/rejected/failed results do not expose playable handoffs.
- generated results have exactly one public handoff: URL or FW-owned artifact reference.
- mock-safe smoke verifies the result contract without provider credentials.

### Commit 8 - Real provider execution boundary guard

```text
docs/test: add real provider execution boundary guard
```

Acceptance:

- configured providers are guarded by default.
- `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1` is required before real provider SDK import, provider API calls, or artifact writes can proceed.
- configured-but-guarded output returns `request_state="skipped"` and no audio handoff.
- opening the guard with missing FW settings returns safe `unavailable` before provider SDK import.
- mock-safe smoke verifies the guard without provider credentials.

### Commit 6 - Real TTS opt-in boundary checklist

```text
docs/test: add real TTS opt-in boundary checklist
```

Acceptance:

- real TTS enablement is documented as explicit FW-owned opt-in only.
- provider selection, API keys, provider voice IDs, model IDs, and provider-specific parameters remain FW-side.
- a mock-safe smoke check validates default, missing-provider, unsupported-provider, and missing-settings behavior without provider SDK execution.
- unavailable public results are documented as readiness checks, not DRC real Web audio evidence.

## Release acceptance checklist

v5.0.0 is ready when:

- public voice output boundary exists
- host apps can request voice output without provider-specific details
- `import framework` remains lightweight and provider-safe
- API keys are not required for mock-safe public smoke tests
- provider unavailable state is safe and inspectable
- real provider execution is explicit opt-in and requires `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1`
- existing TextChat public facade behavior is not broken
- DRC can integrate through FW public voice output boundary instead of FW internals
- docs clearly explain supported behavior and limitations
- release package checks pass

## Follow-up versions

### v5.1.x candidates

- OpenAI TTS provider adapter
- richer voice profile registry
- better audio artifact management
- provider-specific format negotiation
- realtime TTS stop/flush hardening
- interruption coordinator over voice output sessions

### Future major version candidates

Possible v6.0.0 theme:

```text
Always-on Voice Barge-in / Voice Interaction UX
```

Potential future scope:

- microphone listening while speaking
- VAD-based interruption
- wake word support
- background input monitoring
- more natural turn-taking UX
