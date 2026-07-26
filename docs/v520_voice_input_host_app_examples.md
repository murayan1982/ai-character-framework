# v5.2.0 Voice Input Host-App Examples

This checkpoint adds mock-safe host-app examples for the public voice-input /
STT boundary.

These examples are intended for DRC-style external app integration. They use
only public `framework` imports and do not import FW internals, STT provider
SDKs, microphone libraries, token files, or raw audio paths.

## Examples

### Capability preflight

```text
examples/app_voice_input_capability_preflight.py
```

Shows how a host app can inspect public voice-input capability status:

- `supports_voice_input_session`
- `supports_text_fallback`
- `supports_real_stt`
- `provider_status`
- `safe_message`

### Session text fallback

```text
examples/app_voice_input_session_text_fallback.py
```

Shows how a host app can create a public voice-input session, receive
provider-neutral unavailable status from `listen_result(...)`, and still produce
a completed `VoiceInputResult` through `text_fallback_result(...)`.

This is useful for DRC integration tests before real STT execution is available.

### Missing credentials

```text
examples/app_voice_input_missing_credentials.py
```

Shows how missing real STT credentials are returned as a typed public result:

- `outcome=unavailable`
- `public_error_code=missing_credentials`
- `retryable=True`

The example uses `credential_env={}` to keep the result deterministic and
mock-safe.

## Integration rule

Host apps should use:

```python
import framework
```

and public symbols such as:

- `framework.get_voice_input_capabilities(...)`
- `framework.create_voice_input_session(...)`
- `framework.VoiceInputResult`

Host apps should not use:

- `stt.*` internals
- provider SDK classes
- microphone capture internals
- token files
- local raw audio paths
- CWD / sys.path / import cache workarounds

## Real STT status

These examples intentionally do not execute real STT.

At this checkpoint, real STT remains represented by public-safe statuses such as
`disabled`, `missing_credentials`, `provider_execution_not_allowed`,
`unsupported_provider`, and `real_stt_not_implemented`.
