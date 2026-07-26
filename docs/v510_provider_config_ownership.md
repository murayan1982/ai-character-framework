# v5.1.0 Provider Config Ownership Contract

Status: v5.1.0 P0 / FW-F5 implementation checkpoint.

## Purpose

DRC v2.x had to bridge provider-specific environment details while integrating
FW as a local checkout. Examples included compatibility handling around
`GEMINI_API_KEY` / `GOOGLE_API_KEY` and provider-specific key names.

That is the wrong long-term responsibility split. Host apps should pass
provider-neutral intent to FW, while FW owns provider selection, credential alias
resolution, model IDs, voice IDs, provider SDKs, and provider-specific request
parameters.

v5.1.0 starts moving that responsibility into FW by adding a mock-safe provider
environment resolution boundary.

## Public safety rule

The provider config boundary may report whether configuration appears present,
but it must not expose:

```text
API key values
provider raw payloads
provider SDK objects
provider class names
private paths
voice IDs
model IDs
provider-specific request parameters
```

It must also avoid mutating `os.environ`. In particular, FW may treat
`GEMINI_API_KEY` and `GOOGLE_API_KEY` as aliases, but it should not copy one into
the other inside the host application process.

## Initial FW-owned alias rules

The first checkpoint records these FW-owned rules:

```text
gemini / google / google_generative_ai: GEMINI_API_KEY or GOOGLE_API_KEY
xai / grok: XAI_API_KEY
openai: OPENAI_API_KEY
elevenlabs: ELEVENLABS_API_KEY
```

These rules are intentionally inside FW. DRC should not need to bridge the same
provider environment names before importing or calling FW.

## Provider-neutral snapshot

`framework.provider_config.get_provider_environment_snapshot()` returns a
secret-free snapshot with:

```text
schema_version
text_chat
voice_output
public_metadata
```

Each status includes:

```text
area
status
configured
provider_selected
reason_code
safe_message
public_metadata
```

The status vocabulary is:

```text
configured
unavailable
blocked
unsupported
```

The snapshot is a configuration snapshot, not a provider health check. It must
not import provider SDKs or call provider APIs.

## DRC impact

DRC should move away from:

```text
GEMINI_API_KEY -> GOOGLE_API_KEY bridging
provider key-name compatibility code
provider-specific env mutation before FW calls
```

Instead, DRC should call FW public APIs with provider-neutral intent and rely on
FW to resolve provider environment conventions internally.

## Follow-up

Later v5.1.0 work should connect this provider config ownership to:

```text
create_text_chat_session()
create_voice_output_session()
get_capabilities()
typed public error codes
release conformance gates
```

This checkpoint intentionally stays mock-safe and does not run real providers.

## Import safety requirement

Provider config resolution must not import provider SDKs, create provider clients,
validate live credentials, call provider APIs, or mutate `os.environ`.

It may inspect provider-neutral configuration state and environment variable presence,
but public results must remain secret-free and provider-neutral.

