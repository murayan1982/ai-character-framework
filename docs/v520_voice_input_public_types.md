# v5.2.0 Public Voice Input Types

This checkpoint adds the first public voice-input / STT contract skeleton.

It is intentionally limited to provider-neutral public request and result types.
It does not yet add `VoiceInputSession` or real STT execution.

## Public symbols

The following symbols are exported from `framework`:

- `VoiceInputOutcome`
- `VoiceInputErrorCode`
- `VoiceInputRequest`
- `VoiceInputResult`

These types are designed for host apps such as DRC to consume without importing
FW internal STT modules or provider SDKs.

## Request contract

`VoiceInputRequest` describes host-app intent:

- `language`
- `timeout_ms`
- `max_duration_ms`
- `vad_enabled`
- `input_device_id`
- `metadata`

The request object validates positive duration values and stores metadata as an
immutable public mapping.

Private-looking metadata keys such as token, secret, password, credential, or
API key fields are redacted.

## Result contract

`VoiceInputResult` describes provider-neutral outcomes:

- `completed`
- `no_input`
- `interrupted`
- `failed`
- `unavailable`
- `closed`

The result object exposes:

- `outcome`
- `text`
- `language`
- `confidence`
- `duration_ms`
- `public_error_code`
- `safe_message`
- `retryable`
- `public_metadata`

The result does not expose raw provider payloads, private token paths, local
audio file paths, microphone internals, or STT provider object types.

## Helper constructors

The public result type includes helper constructors for common app flows:

- `VoiceInputResult.completed(...)`
- `VoiceInputResult.no_input(...)`
- `VoiceInputResult.interrupted(...)`
- `VoiceInputResult.unavailable(...)`
- `VoiceInputResult.failed(...)`
- `VoiceInputResult.closed(...)`

These are mock-safe and provider-neutral.

## Import safety

`import framework` must not eagerly import STT provider modules, microphone
libraries, audio runtimes, or voice provider SDKs.

This checkpoint keeps the public voice-input types in `framework.voice_input`
with no provider imports.

## Next checkpoint

The next implementation checkpoint should add a mock-safe public
`VoiceInputSession` skeleton and factory:

- `create_voice_input_session(...)`
- `VoiceInputSession`
- `VoiceInputSessionInfo`

The session should return provider-neutral `VoiceInputResult` values without
requiring real STT execution by default.
