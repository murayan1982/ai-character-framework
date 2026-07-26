# v5.1.0 Capability Snapshot Contract

Status: v5.1.0 P0 / FW-F4 implementation checkpoint.

## Purpose

DRC v2.x had to inspect FW checkout files and public symbol candidates to infer
whether voice input, voice output, realtime, and motion boundaries were usable.
That pushed too much FW knowledge into the host app.

v5.1.0 adds a lightweight public capability snapshot:

```python
from framework import get_capabilities

capabilities = get_capabilities()
print(capabilities.text_chat.status)
print(capabilities.voice_output.reason_code)
```

The snapshot is mock-safe and provider-neutral. It must not import provider SDKs
or perform provider API calls.

## Public API

```python
get_capabilities(
    *,
    project_root: str | Path | None = None,
    real_tts_enabled: bool | None = None,
) -> FrameworkCapabilities
```

Public types:

```text
CapabilityStatus
FrameworkCapabilities
```

## Capability fields

Each capability exposes:

```text
name
status
supported
configured
available
blocked
reason_code
safe_message
public_metadata
```

The status vocabulary is:

```text
supported
configured
available
blocked
unavailable
fallback
```

## Important distinctions

```text
Guarded does not mean implemented.
Detected does not mean connected.
Configured does not mean successful.
Fallback does not mean configured-provider success.
```

A capability can be:

```text
supported=True, configured=False, available=False
```

or:

```text
supported=True, configured=True, blocked=True, available=False
```

Host apps should use these fields instead of inspecting FW files or guessing from
provider-specific environment variables.

## v5.1.0 baseline snapshot

```text
text_chat: available
voice_output: supported but unavailable unless real TTS is explicitly configured
voice_input: unavailable / public_boundary_missing
realtime: unavailable / public_boundary_missing
motion: unavailable / public_boundary_missing
```

## Public safety

The capability snapshot must not expose:

```text
API keys
provider raw payloads
provider SDK objects
provider class names
private paths
provider voice IDs
model IDs
```

`public_metadata` may expose provider-neutral booleans such as:

```text
real_tts_enabled=false
provider_configured=false
provider_execution_allowed=false
provider_details_exposed=false
```

## DRC impact

DRC can move from file/symbol scanning and adapter-specific detection toward:

```python
capabilities = framework.get_capabilities()
if capabilities.voice_input.status == "unavailable":
    disable_voice_input_ui(capabilities.voice_input.safe_message)
```

This reduces host-app assumptions and keeps unsupported or guarded features out
of DRC runtime branches.
