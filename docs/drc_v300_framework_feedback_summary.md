# DRC v3.0.0 Feedback Summary for AI-Character-Framework

Updated: 2026-07-26

## Summary

Daily Rhythm Companion (DRC) successfully used AI-Character-Framework (FW) v4
and v5 public boundaries in a real app.

Confirmed public boundaries:

```text
FW v4:
- create_text_chat_session()

FW v5:
- create_voice_output_session()
- VoiceOutputRequest
- VoiceOutputResult
```

Confirmed real-app flow:

```text
DRC daily data
→ FW public text chat boundary
→ LLM answer
→ FW public voice output boundary
→ TTS generation
→ DRC-owned opaque audio URL
→ Flutter Web / PC playback
```

DRC did not directly import FW internal TTS modules or provider SDKs for this
path. FW owned provider/TTS generation responsibility, and DRC owned web delivery,
TTL/LRU app policy, HTTP serving, and Flutter playback.

The main problem is not public-boundary failure. The problem is external app
integration cost.

## Positive findings

```text
- v4 text chat public facade survived real app usage
- v5 voice output public boundary survived real app usage
- provider-specific TTS logic did not need to move into DRC
- DRC could keep provider voice IDs/API keys/model IDs out of app requests
- opaque app-owned web URL delivery worked as the host-app responsibility
```

## Highest-impact feedback

### FW-F1 — Remove checkout/CWD/import workarounds

DRC should not need:

```text
- FRAMEWORK_ROOT resolution for normal use
- sys.path mutation
- sys.modules deletion
- import cache invalidation
- temporary CWD changes
```

FW should become a normal installable SDK with package/resource-root based lookup.

### FW-F2 — Stabilize public signatures

Host apps should not need reflection across variants such as:

```text
preset / preset_name / preset_id
character / character_name / character_id
create_output / speak / synthesize / speak_text / generate_audio
```

Docs, examples, and implementation must agree.

### FW-F3 — Add typed results and public error codes

Text chat should return or expose a typed public result rather than forcing host
apps to normalize strings and broad exception messages.

### FW-F4 — Add capability snapshot

Host apps need to know whether a feature is supported, configured, available,
blocked, guarded, or unavailable without scanning FW files or symbols.

### FW-F5 — Centralize provider config responsibility

Provider selection, env aliases, API key lookup, model IDs, voice IDs, SDK calls,
and provider request params should stay inside FW. Host app requests should remain
provider-neutral.

### FW-F6 — Add consistent lifecycle cleanup

All public sessions should have idempotent close/context-manager semantics so
host apps can evict sessions safely.

### FW-F7 — Harden opaque artifact handoff

Voice output results should expose no raw local paths. Generated audio should
have exactly one handoff: `audio_url` or an opaque artifact ref.

### FW-F8 — Add public contract conformance gate

Release readiness should fail when README/docs/examples/public exports/signatures
and real implementation diverge.

## DRC v3.0.0 dependencies not present in FW v5.0.0

```text
- public voice input / STT session
- unified realtime session
- provider-level hard cancellation where supported
- TTS queue / flush / barge-in contract
- public motion / Live2D / VTube Studio adapter
```

These should be pursued only after the P0 SDK integration foundation is stable.

## DRC-side rule

If FW public contracts are missing, DRC should not add new workarounds such as:

```text
- FW internal module imports
- provider-specific STT/LLM/TTS implementation
- direct VTube Studio WebSocket ownership
- new sys.path mutation
- new sys.modules deletion
- new import cache invalidation
- new temporary CWD changes
- new dependencies on FW checkout structure
- private provider payload storage
- provider path UI exposure
```

Missing public contracts should be implemented and released in FW, then consumed
by DRC from a fixed public artifact.
