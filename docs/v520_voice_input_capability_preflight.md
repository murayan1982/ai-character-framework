# v5.2.0 Voice Input Capability Preflight

This checkpoint adds a public voice-input / STT capability preflight contract.

It does not execute real STT. It only reports whether real STT is disabled,
missing credentials, blocked by provider execution guard, unsupported, or not
implemented yet.

## Public symbols

The following symbols are exported from `framework`:

- `VoiceInputProviderStatus`
- `VoiceInputProviderConfig`
- `VoiceInputCapabilities`
- `resolve_voice_input_provider_config`
- `get_voice_input_capabilities`

## Purpose

DRC and other host apps need to know whether the public voice-input boundary is
available without importing STT internals or constructing provider clients.

This preflight gives host apps a provider-neutral snapshot:

```python
import framework

capabilities = framework.get_voice_input_capabilities()
```

## Status values

`VoiceInputProviderStatus` currently includes:

- `disabled`
- `missing_credentials`
- `provider_execution_not_allowed`
- `unsupported_provider`
- `real_stt_not_implemented`

`real_stt_not_implemented` is intentional at this stage. It prevents the public
contract from claiming real provider readiness before the guarded provider
execution path exists.

## Provider config summary

`resolve_voice_input_provider_config(...)` returns a public-safe
`VoiceInputProviderConfig`.

It reports:

- provider name
- real STT enabled flag
- provider execution guard flag
- credentials availability
- credential source key name only
- public metadata

It must never expose credential values, token files, provider payloads, raw audio
paths, or provider SDK objects.

## Capability snapshot

`get_voice_input_capabilities(...)` returns a public-safe
`VoiceInputCapabilities`.

It reports:

- `supports_voice_input_session`
- `supports_text_fallback`
- `supports_real_stt`
- `provider_status`
- `provider`
- `safe_message`
- `retryable`
- `public_metadata`

At this checkpoint, `supports_real_stt` remains `False` because real STT
execution has not been added.

## Guards

The preflight recognizes public environment intent:

- `FRAMEWORK_VOICE_INPUT_PROVIDER`
- `FRAMEWORK_STT_PROVIDER`
- `FRAMEWORK_VOICE_INPUT_REAL_STT`
- `FRAMEWORK_STT_REAL_STT`
- `FRAMEWORK_VOICE_INPUT_ALLOW_PROVIDER_EXECUTION`

Credential presence is checked only as a boolean/public source key.

Current credential source keys:

- Google: `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Whisper/mock: no credential required by this preflight

## Import safety

`import framework` and `get_voice_input_capabilities(...)` must not import STT
provider SDKs, microphone libraries, or audio runtime modules.

## Next checkpoint

The next checkpoint should wire this capability preflight into
`VoiceInputSessionInfo` / `VoiceInputSession.listen_result(...)` so the session
can return status-specific provider-neutral results.
