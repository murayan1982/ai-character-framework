# v5.1.0 TextChatResult Runtime Method

Status: v5.1.0 P0 / FW-F3 implementation checkpoint.

## Purpose

`TextChatResult` is now public. This checkpoint adds a non-breaking runtime
method so host applications can receive that typed result without changing the
existing `ask()` contract.

## Public method

```python
result = session.ask_result("こんにちは。短く返して")
```

`ask_result()` returns:

```python
TextChatResult(
    outcome="completed",
    text="...",
    public_error_code=None,
    safe_message=None,
    retryable=False,
)
```

on success, and a provider-neutral failed result on error.

## Compatibility

Existing v4/v5 behavior is preserved:

```python
text = session.ask("こんにちは。短く返して")
```

`ask()` remains the string-oriented public text chat method. `ask_result()` is the
new typed-result companion method for host apps that need stable outcome and
error handling.

## Public-safety rules

`ask_result()` must not expose:

```text
API keys
provider raw payloads
provider-specific exception messages
private local paths
provider SDK objects
provider class names
```

Errors are converted to provider-neutral fields:

```text
outcome
public_error_code
safe_message
retryable
```

## DRC impact

DRC can move from broad response normalization:

```text
str
response.message
response.text
response.content
str(response)
exception string parsing
```

toward:

```python
result = session.ask_result(message)
if result.is_completed:
    text = result.text
else:
    handle(result.public_error_code, result.safe_message, result.retryable)
```

## Follow-up

This checkpoint does not remove or change `ask()`. Future conformance gates can
require host-app examples to prefer `ask_result()` when typed error handling is
needed.

## Mock-safe runtime smoke

The v5.1.0 runtime smoke for `ask_result()` must not construct a
provider-backed text chat session. It validates the public method using fake
session objects so the check does not require `.env`, `GOOGLE_API_KEY`, or any
real provider execution.

