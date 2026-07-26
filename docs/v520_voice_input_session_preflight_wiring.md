# v5.2.0 Voice Input Session Preflight Wiring

This checkpoint wires the public voice-input capability preflight into the
public `VoiceInputSession` skeleton.

It still does not execute real STT providers.

## What changed

`VoiceInputSession` now resolves `get_voice_input_capabilities(...)` during
construction and exposes the result through:

- `session.capabilities`
- `session.info.provider_status`
- `session.info.supports_real_stt`
- `session.info.safe_message`

`listen_result(...)` now returns status-specific provider-neutral unavailable
results instead of a single hardcoded disabled result.

## Public statuses reflected by session

The session can now distinguish:

- `disabled`
- `missing_credentials`
- `provider_execution_not_allowed`
- `unsupported_provider`
- `real_stt_not_implemented`

## Result mapping

`listen_result(...)` maps preflight status to public result fields:

| Preflight status | Result outcome | Public error code |
| --- | --- | --- |
| `disabled` | `unavailable` | `unavailable` |
| `missing_credentials` | `unavailable` | `missing_credentials` |
| `provider_execution_not_allowed` | `unavailable` | `unavailable` |
| `unsupported_provider` | `unavailable` | `invalid_request` |
| `real_stt_not_implemented` | `unavailable` | `unavailable` |

The result metadata includes:

- `boundary=voice_input`
- `provider_status`
- `reason`
- `supports_real_stt`

No credential values, token files, provider payloads, raw audio paths, or
provider SDK objects are exposed.

## Factory inputs

`create_voice_input_session(...)` now accepts the same public preflight controls:

- `provider`
- `real_stt_enabled`
- `allow_provider_execution`
- `credential_env`

`credential_env` is primarily for deterministic smoke tests and host-app
preflight. Real provider execution remains unavailable in this checkpoint.

## Events

`listen_result(...)` still emits provider-neutral events:

- `voice_input.started`
- `voice_input.unavailable`

The unavailable event now includes public-safe `provider_status`, `reason`, and
`provider`.

## Import safety

`import framework` and `create_voice_input_session(...)` must not import STT
provider SDKs, microphone libraries, or audio runtime modules.

## Next checkpoint

The next checkpoint should add public examples for host-app use:

- voice-input capability preflight example
- voice-input session text fallback example
- closed-session behavior example
