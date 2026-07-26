# v5.2.0 Realtime Host-App Examples

This checkpoint adds mock-safe host-app examples for the public realtime
lifecycle / event boundary.

These examples are intended for DRC-style external app integration. They use
only public `framework` imports and do not import FW internals, STT/LLM/TTS
provider SDKs, microphone libraries, VTube Studio internals, websocket handles,
token files, or raw audio paths.

## Examples

### Realtime session event flow

```text
examples/app_realtime_session_event_flow.py
```

Shows how a host app can create a public realtime session, register an event
callback, run a mock-safe turn, and observe the deterministic public event
sequence:

- `realtime.turn.started`
- `realtime.voice_input.started`
- `realtime.voice_input.completed`
- `realtime.text_chat.started`
- `realtime.text_chat.completed`
- `realtime.voice_output.started`
- `realtime.voice_output.completed`
- `realtime.turn.completed`
- `realtime.session.closed`

This example does not execute real STT, LLM, TTS, or motion providers.

### Realtime event payload mapping

```text
examples/app_realtime_event_payload_mapping.py
```

Shows how a host app can convert a public `RealtimeEvent` to a dictionary with
`as_dict()` for UI state updates or logs.

Secret-like metadata keys are redacted.

### Realtime closed-session behavior

```text
examples/app_realtime_closed_session_behavior.py
```

Shows that calling `run_turn(...)` after `close()` returns a typed
provider-neutral `RealtimeTurnResult.closed(...)` result instead of requiring
the host app to depend on internal exceptions or cleanup state.

## Integration rule

Host apps should use:

```python
import framework
```

and public symbols such as:

- `framework.create_realtime_session(...)`
- `framework.RealtimeEvent`
- `framework.RealtimeEventType`
- `framework.RealtimeState`
- `framework.RealtimeTurnResult`

Host apps should not use:

- FW realtime internals
- STT / LLM / TTS provider SDKs
- microphone capture internals
- raw audio paths
- VTube Studio WebSocket internals
- token files
- CWD / sys.path / import cache workarounds

## Real runtime status

These examples intentionally do not execute real realtime providers.

At this checkpoint, the realtime session is a public mock-safe lifecycle and
event contract that DRC can observe without relying on framework internals.
