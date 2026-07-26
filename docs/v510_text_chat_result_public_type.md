# v5.1.0 TextChatResult Public Type

Status: v5.1.0 P0 / FW-F3 implementation checkpoint.

## Purpose

DRC v2.x had to normalize text chat outputs from strings, ad-hoc response
attributes, and broad exception handling. v5.1.0 starts moving that adapter cost
into FW by exposing a provider-neutral public text chat result type.

This checkpoint adds:

```python
TextChatResult
```

as a public type exported from `framework`.

## Public shape

```python
TextChatResult(
    outcome="completed",
    text="...",
    public_error_code=None,
    safe_message=None,
    retryable=False,
)
```

Required public fields:

```text
outcome
text
public_error_code
safe_message
retryable
public_metadata
```

Convenience helpers are also public:

```text
is_completed
is_interrupted
is_failed
has_text
TextChatResult.completed(...)
TextChatResult.failed(...)
TextChatResult.interrupted(...)
```

## Public outcome vocabulary

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

## Public error code vocabulary

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
provider_request_failed
empty_response
unknown_error
```

## Public-safety requirements

`TextChatResult` must not expose provider-specific or private details such as:

```text
API keys
provider raw payloads
provider-specific exception objects
private local paths
provider SDK objects
provider class names
```

## Compatibility note

This commit only makes the public result type available. It does not change the
existing text chat runtime return behavior yet.

Follow-up work should add a non-breaking text chat method that returns
`TextChatResult`, while preserving existing string-return behavior during the
migration window.
