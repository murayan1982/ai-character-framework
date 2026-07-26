# v5.1.0 Result / Error Contract

Status: v5.1.0 P0 / FW-F3 contract checkpoint.

## Purpose

DRC v2.x integration showed that FW public boundaries can work in a real host
app, but host-side adapters still needed to normalize several result and error
shapes.

For text chat, DRC currently has to accept values such as:

```text
str
response.message
response.text
response.content
str(response)
```

DRC also has to catch broad exceptions, sanitize private paths and provider
payloads, and infer retryability from exception text.

v5.1.0 should move this responsibility into FW by defining a provider-neutral,
typed result and error contract across public sessions.

This checkpoint records the vocabulary and release expectations before changing
text chat runtime behavior.

## Shared public outcome vocabulary

Public result objects should use a common provider-neutral outcome vocabulary.

```text
completed
interrupted
unavailable
blocked
skipped
rejected
failed
expired
cancelled
```

Meaning:

```text
completed: request completed successfully
interrupted: request stopped by a soft interrupt boundary
unavailable: capability or provider is not available in the current runtime
blocked: request was blocked by a guard, policy, or explicit safety condition
skipped: request was intentionally skipped without being treated as a failure
rejected: request shape or input was rejected before provider execution
failed: request failed after being accepted for processing
expired: request/session/artifact is no longer valid
cancelled: request was cancelled by the caller or lifecycle boundary
```

Voice Output v5.0.0 currently uses `request_state`. v5.1.0 may preserve that
field for compatibility, but new typed contracts should converge on the shared
outcome vocabulary or provide an explicit compatibility mapping.

## Provider-neutral public error codes

Public errors should use stable provider-neutral codes. Host apps must not parse
raw provider exception strings.

Initial public code vocabulary:

```text
configuration_missing
provider_unavailable
authentication_required
rate_limited
request_cancelled
timeout
unsupported_capability
session_closed
invalid_request
artifact_missing
artifact_expired
provider_request_failed
empty_response
unknown_error
```

These codes are public app-facing values. Provider-specific details remain
internal.

## Text chat result target

Target public shape:

```python
TextChatResult(
    outcome="completed",
    text="...",
    public_error_code=None,
    safe_message=None,
    retryable=False,
)
```

Required properties:

```text
outcome: shared public outcome
text: response text when available
public_error_code: provider-neutral public error code when applicable
safe_message: sanitized user/app-facing message
retryable: whether host app may retry without changing request/config
```

The result may also include public metadata, but it must not expose provider
payloads, raw exception strings, private paths, API keys, provider SDK objects,
or provider class names.

## Voice output compatibility

`VoiceOutputResult` already provides a typed public handoff shape. v5.1.0 should
keep it provider-neutral and align it with the shared result vocabulary over
time.

For non-playable states:

```text
unavailable
skipped
rejected
failed
expired
cancelled
blocked
```

Voice Output results should satisfy:

```text
audio_ready=False
audio_url=None
audio_artifact_ref=None
has_audio_handoff=False
audio_handoff_kind=none
is_generated=False
```

For playable generated audio, the public handoff invariant remains:

```text
- exactly one of audio_url or audio_artifact_ref is present
- raw local provider paths are not exposed
- provider details remain hidden
```

## Public-safety requirements

Public result and error surfaces must not expose:

```text
- API key
- provider raw payload
- provider-specific exception message
- private path
- provider SDK object
- provider class name
- provider voice ID
- provider model ID
```

## Conformance requirements

```text
- Shared outcome vocabulary is documented.
- Provider-neutral public error code vocabulary is documented.
- Voice Output result compatibility is checked mock-safely.
- TextChatResult public type is now available as a v5.1.0 implementation checkpoint.
- A runtime text chat method that returns TextChatResult remains a follow-up.
- Host apps should not parse exception text for public control flow.
- Public results must not expose provider-specific/private details.
```

## Follow-up implementation steps

```text
1. Add a non-breaking text chat method that returns TextChatResult.
2. Preserve existing text-return behavior during migration if needed.
3. Add retryable/non-retryable classification at the FW boundary.
4. Promote this checkpoint from WARN inventory to strict conformance gate.
```

## v5.1.0 TextChatResult checkpoint

`TextChatResult` is now part of the public `framework` surface. This makes the
provider-neutral result shape importable and testable before changing existing
text chat runtime return behavior.

The next implementation step is a non-breaking text chat operation that returns
`TextChatResult`, so host apps can stop normalizing raw strings, ad-hoc response
attributes, and exception text.
