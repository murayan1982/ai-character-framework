# Advanced Runtime Behavior

This document describes the advanced runtime behavior introduced for the v3.0 runtime foundation.

These features are intended for developers extending the framework.

## Runtime Conversation State

The framework tracks high-level conversation state during the runtime loop.

Current states:

| State | Meaning |
| --- | --- |
| `idle` | The session is idle between turns. |
| `listening` | The session is collecting user input. |
| `thinking` | The framework is waiting for LLM output. |
| `responding` | The assistant text response is being displayed or streamed. |
| `speaking` | The framework is waiting for queued TTS playback. |
| `interrupted` | A response interruption has been requested or is being handled. |
| `exiting` | The session is shutting down. |
| `error` | The session is handling an error. |

Expected text-only flow:

```text
idle -> listening -> thinking -> responding -> idle
```

Expected voice/TTS flow:

```text
idle -> listening -> thinking -> responding -> speaking -> idle
```

## Runtime State Events

Plugins can observe state changes through:

```python
on_state_change(old_state, new_state)
```

State changes are emitted through the runtime hook registry.

Plugins should treat runtime state as read-only.

For plugin event details, see:

```text
plugin_events.md
```

## Interruption Boundary

The runtime provides an interruption request boundary for future barge-in support.

Current helper behavior:

```python
request_interruption(runtime)
clear_interruption(runtime)
is_interruption_requested(runtime)
```

Current responsibility split:

- `request_interruption(runtime)` requests interruption and transitions to `interrupted`.
- `clear_interruption(runtime)` clears only the pending interruption flag.
- `clear_interruption(runtime)` does not reset runtime state.
- Final state reset is owned by the session loop.

## Manual Interruption Debug Command

The interactive runtime supports a development-only manual interruption command:

```text
/interrupt
```

This command verifies the interruption request/state boundary from user input.

Expected debug flow:

```text
listening -> interrupted -> idle
```

Important:

This is not full concurrent voice barge-in yet.

The command is handled as normal user input before an assistant response starts.
It does not interrupt an already-running response from another thread or audio stream.

## TTS Stop Boundary

TTS playback has a best-effort stop boundary for future interruption handling.

The runtime may call:

```python
tts.stop()
```

Expected behavior:

- stop active local playback when possible
- clear queued speech segments
- clear pending TTS text buffer
- avoid crashing if nothing is playing

Provider-specific hard cancellation is still a future implementation detail.

## Voice Output Policy

When voice/TTS output is enabled, the prompt builder can add a voice-friendly output policy.

The policy is intended to improve TTS readability.

It is separate from:

- output language instruction
- character personality prompt
- provider-specific pronunciation settings

Prompt layer order:

```text
language instruction
voice output policy
emotion tag instruction
character system prompt
```

Text-only sessions do not receive the voice output policy by default.

For details, see:

```text
voice_output_policy.md
```

## Current Limitations

The v3.0 runtime foundation does not yet provide:

- full concurrent voice barge-in
- microphone listening while TTS is speaking
- provider-level LLM request cancellation
- provider-specific TTS cancellation guarantees
- SSML or pronunciation dictionary support
- production-grade interruption UX

These are future v3.x work items.