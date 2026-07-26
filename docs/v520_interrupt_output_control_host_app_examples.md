# v5.2.0 Interrupt / Output-Control Host-App Examples

This checkpoint adds mock-safe host-app examples for the public hard cancel /
TTS queue / flush / barge-in control boundary.

These examples are intended for DRC-style external app integration. They use
only public `framework` imports and do not import FW internals, LLM/TTS provider
SDKs, audio playback internals, websocket handles, token files, raw audio paths,
or queue implementation details.

## Examples

### Realtime interrupt handling

```text
examples/app_realtime_interrupt_handling.py
```

Shows how a host app can send a public `InterruptRequest.user_barge_in(...)`
request and receive a typed `InterruptResult`.

The example intentionally reports:

- `outcome=not_implemented`
- `provider_cancel_supported=False`
- `queue_flush_supported=False`

This is the correct current behavior because real hard cancel is not implemented
yet.

### Realtime output flush handling

```text
examples/app_realtime_output_flush_handling.py
```

Shows how a host app can inspect `get_tts_queue_state()` and call
`flush_output(...)`.

The mock-safe session currently returns:

- `queued_count=0`
- `supports_flush=False`
- `supports_provider_cancel=False`
- `flush_outcome=nothing_to_flush`

This gives DRC a stable typed public result without exposing queue internals or
raw audio paths.

### Realtime barge-in policy

```text
examples/app_realtime_barge_in_policy.py
```

Shows how a host app can use:

- `decide_barge_in(...)`
- `set_barge_in_policy(...)`
- `BargeInPolicy.hard_cancel()`

The default disabled policy rejects barge-in. The hard-cancel policy accepts the
decision at policy level and returns public booleans describing what the host
should do:

- `should_stop_output`
- `should_flush_queue`
- `should_cancel_current_turn`

This still does not perform real audio detection or real provider cancellation.

## Integration rule

Host apps should use:

```python
import framework
```

and public symbols such as:

- `framework.InterruptRequest`
- `framework.InterruptResult`
- `framework.OutputFlushRequest`
- `framework.OutputFlushResult`
- `framework.BargeInPolicy`
- `framework.BargeInDecision`
- `framework.create_realtime_session(...)`

Host apps should not use:

- FW realtime internals
- provider SDK cancellation APIs
- TTS queue internals
- raw voice artifact paths
- audio playback handles
- websocket handles
- token files
- CWD / sys.path / import cache workarounds

## Real runtime status

These examples intentionally do not execute real hard cancellation, real TTS
queue flush, playback stop, provider cancellation, or audio barge-in detection.

At this checkpoint, the public control surface exists and reports honest typed
results for not-yet-implemented / no-active-turn / empty-queue / closed-session
cases.
