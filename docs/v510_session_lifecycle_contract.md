# v5.1.0 Session Lifecycle / Close Contract

Status: v5.1.0 P0 / FW-F6 implementation checkpoint.

## Purpose

DRC v2.x owns host-app session TTL and LRU eviction policy, but FW public
sessions still need a stable cleanup boundary so host apps can release framework
resources without inspecting FW internals.

This checkpoint adds a provider-neutral lifecycle surface to existing public
sessions:

```text
close()
dispose()
context manager enter/exit
is_closed
```

## Public contract

Text chat:

```python
session = create_text_chat_session()
try:
    result = session.ask_result("こんにちは")
finally:
    session.close()
```

Voice output:

```python
with create_voice_output_session() as session:
    result = session.speak(request)
```

`close()` is idempotent. Calling it multiple times must be safe.

## Closed-session behavior

After `close()`:

```text
TextChatSession.ask_result(...)
→ TextChatResult(outcome="failed", public_error_code="session_closed")

VoiceOutputSession.speak(...)
→ non-playable VoiceOutputResult with public_error_code="session_closed"
```

The existing text-chat `ask()` method is not changed in this checkpoint.
`ask_result()` is the typed host-app method that can reliably report
`session_closed`.

## Public-safety requirements

Closing a session must remain mock-safe:

```text
- no provider SDK import during import/session creation/close
- no provider API call during close
- no private path exposure
- no API key or provider raw payload exposure
- repeated close calls are safe
- context manager exit calls close
```

## DRC impact

DRC can keep its own TTL/LRU policy, but call `session.close()` when evicting FW
sessions. This avoids DRC needing to know whether a future FW session owns
provider clients, queues, background tasks, microphones, or motion connections.

## Contract phrases

The public session lifecycle contract requires the following:

- close() is idempotent
- dispose() is an alias for close()
- closed sessions return provider-neutral session_closed results
- context manager exit closes the session
- close() must not import provider SDKs
- close() must not call provider APIs in mock-safe checks

## Mock-safe lifecycle smoke

The v5.1.0 lifecycle smoke must not construct a provider-backed text chat
session. It validates lifecycle behavior using a lifecycle-only TextChatSession
instance so release package verification does not require `.env`,
`GOOGLE_API_KEY`, or real provider execution.

