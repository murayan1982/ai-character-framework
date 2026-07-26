# AI-Character-Framework v5.1.0 Release Notes

Status: released as `v5.1.0`.

Theme: **Installable SDK / Stable Host App Integration Boundary**.

v5.1.0 turns the v5.0.0 public Voice Output foundation and the v4.0.0
Text Chat session foundation into a more stable host-app integration surface.
The release focuses on reducing integration cost for external apps while
keeping provider execution guarded and mock-safe by default.

## Highlights

### Public contract inventory and conformance gate

v5.1.0 records and validates the public API baseline exported from
`framework.__all__`.

Baseline public symbols include:

- `create_text_chat_session`
- `TextChatSessionInfo`
- `TextChatResult`
- `CapabilityStatus`
- `FrameworkCapabilities`
- `get_capabilities`
- `create_voice_output_session`
- `VoiceOutputSession`
- `VoiceOutputSessionInfo`
- `VoiceOutputRequest`
- `VoiceArtifactRef`
- `VoiceOutputResult`

The public contract conformance gate checks README usage, examples, public
factory signatures, Text Chat typed results, Voice Output request/result
contracts, capability snapshots, session lifecycle behavior, and opaque voice
artifacts.

### Text Chat typed result boundary

v5.1.0 adds the public `TextChatResult` type and the
`TextChatSession.ask_result(message)` companion method.

`ask()` remains available for existing callers. `ask_result()` gives host apps a
provider-neutral typed outcome with safe public error information for completed,
failed, and interrupted results.

### Voice Output method contract

`VoiceOutputSession.speak(request)` is the preferred app-facing method.

`create_output(request)` remains available as a compatibility alias, but README
and examples now prefer `speak()` for host-app integration.

### Capability snapshot API

v5.1.0 adds the public capability snapshot API:

- `CapabilityStatus`
- `FrameworkCapabilities`
- `get_capabilities()`

Host apps can inspect available or guarded capabilities without importing
provider-specific internals.

### FW-owned provider config resolution

Provider configuration responsibility is clarified inside FW. The public checks
cover provider-neutral handling of missing credentials, Gemini/Google API key
alias resolution, voice-output config resolution, and secret-free public status
reporting.

Real provider execution remains guarded and must not happen during mock-safe
release checks.

### Public session lifecycle

Text Chat and Voice Output public sessions now expose lifecycle behavior for
host apps:

- `close()`
- `dispose()`
- `is_closed`
- context manager support

Closed-session behavior is provider-neutral and mock-safe:

- closed Text Chat `ask_result()` returns a `session_closed` typed result;
- closed Voice Output `speak()` returns a non-playable provider-neutral result.

### Opaque voice artifact contract

v5.1.0 adds `VoiceArtifactRef` as an opaque public artifact reference.

Host apps should treat voice artifacts as framework-owned references or handoff
tokens. The public result surface must not expose private local provider paths,
raw provider payloads, tokens, or other local-only details.

### Package import readiness

The v5.1.0 package import readiness smoke validates that the framework package
can be imported and exercised from outside the repository root.

This checkpoint is intended to reduce host-app integration workarounds such as
temporary CWD changes, checkout-layout assumptions, and direct internal imports.

### Fixed release package builder and verification

v5.1.0 adds a fixed release package builder and verification flow for:

- `release/ai-character-framework_v5.1.0.zip`
- `release/ai-character-framework_v5.1.0_manifest.json`

The fixed release verification extracts the ZIP and re-runs package/public API
checks from outside the repository root.

Local release artifacts are not intended to be committed.

### Release package secret hygiene

The fixed release package excludes local-only/private artifacts such as:

- `config/tokens/`
- `*_token.json`
- private `.env` files
- generated audio artifacts
- runtime output directories
- temporary patch/application files

`.env.example` remains included because it is a public configuration template
and is required by release package checks.

## Validation summary

The final v5.1.0 release readiness flow covered:

- Python compileall
- public contract inventory smoke
- Voice Output method contract smoke
- public factory signature contract smoke
- result/error contract smoke
- TextChatResult public type smoke
- TextChatResult runtime method smoke
- capability snapshot smoke
- provider config ownership smoke
- session lifecycle smoke
- opaque voice artifact smoke
- public contract conformance gate
- package import readiness smoke
- fixed release package builder
- fixed release package verification
- release package check
- final release tag readiness gate

The final fixed release package verification confirmed that the generated ZIP
imports from outside the repository root, exercises the public API
provider-neutrally, and excludes local-only/private artifacts.

Final local fixed-release artifact evidence from the tag-readiness run:

```text
release/ai-character-framework_v5.1.0.zip
sha256=137f9f85602957b068881d8d26e34570bafa8e000c4a624fc19871b313612545
```

## Migration notes for host apps

Prefer public framework imports only:

```python
import framework
```

Use `ask_result()` when a typed Text Chat result is useful:

```python
session = framework.create_text_chat_session()
result = session.ask_result("Hello")
```

Use `speak()` for Voice Output:

```python
voice = framework.create_voice_output_session()
result = voice.speak(framework.VoiceOutputRequest(text="Hello"))
```

Use capability snapshots instead of probing internals:

```python
capabilities = framework.get_capabilities()
```

Use lifecycle cleanup in host apps:

```python
with framework.create_voice_output_session() as voice:
    result = voice.speak(framework.VoiceOutputRequest(text="Hello"))
```

## Known transition baseline

`create_text_chat_session(...)` remains on the v5.1.0 transition signature
baseline and is not keyword-only yet.

This is documented and covered by the public factory signature smoke. It is not
a v5.1.0 release blocker.

## Not included in v5.1.0

The following remain future work:

- public STT / Voice Input session;
- unified realtime voice lifecycle;
- hard LLM/TTS cancellation and barge-in;
- public motion / Live2D / VTube Studio adapter;
- DRC app-side v3.0.0 integration changes.

## Release artifact policy

Generated release ZIPs and manifests are local release artifacts/evidence unless
attached to an external release. They are intentionally ignored by Git and are
not committed to the repository.
