# v5.1.0 Public Factory Signature Contract

Status: v5.1.0 P0 / FW-F2 contract checkpoint.

## Purpose

DRC v2.x integration showed that FW public boundaries work in a real host app,
but the host app still had to inspect multiple possible factory and method names
in order to stay compatible with framework boundary differences.

v5.1.0 reduces that integration cost by treating public factory names and
parameter names as a stable SDK contract.

This document records the v5.1.0 transition contract before larger installable
SDK and runtime capability work begins.

## Current stable public factories

The v5.1.0 baseline public factories are:

```python
from framework import create_text_chat_session, create_voice_output_session
```

### Text chat

Current baseline:

```python
create_text_chat_session(
    preset: str | None = None,
    character_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
)
```

Stable public parameter names:

```text
preset
character_name
provider
model
```

`preset`, `character_name`, `provider`, and `model` remain provider-neutral at
the host-app boundary. Provider-specific secrets, raw provider SDK objects, and
private config paths must not be accepted as ad-hoc request arguments.

v5.1.0 may later move this factory toward keyword-only usage, but this checkpoint
records the current signature as a compatibility baseline. Any migration to
keyword-only calls must be explicit, documented, and tested.

### Voice output

Current baseline:

```python
create_voice_output_session(
    *,
    project_root: str | Path | None = None,
    default_voice_profile_id: str = "default",
    real_tts_enabled: bool | None = None,
    artifact_dir: str | Path | None = None,
)
```

Stable public parameter names:

```text
project_root
default_voice_profile_id
real_tts_enabled
artifact_dir
```

The preferred output operation is:

```python
result = session.speak(request)
```

`session.create_output(request)` remains a v5.0 compatibility method.

## Aliases that host apps should not need to inspect

Host apps should not inspect or branch across these alternate names:

```text
preset_name
preset_id
character
character_id
framework_project_root
create_tts_session
create_output vs speak candidate probing
```

Compatibility aliases, if needed, should be handled inside FW with documented
deprecation behavior. DRC and other host apps should import and call the stable
public API directly.

## Future public factories

Future realtime and motion work should follow the same naming policy:

```python
create_voice_input_session(...)
create_realtime_session(...)
create_motion_session(...)
```

Before each future factory is exposed, it should have:

```text
- a documented keyword-only public signature
- provider-neutral request/result types
- provider-neutral public error codes
- mock-safe import/session creation behavior
- public contract conformance smoke coverage
```

## Conformance requirements

```text
- Public factory names are exported from framework.__all__.
- Public factory parameter names are stable and documented.
- Host apps do not need inspect.signature() branching for normal usage.
- README and examples use only preferred public names.
- Deprecated aliases have explicit migration notes.
- Provider-specific implementation details do not appear in public signatures.
- Public signature changes are detected by smoke tests before release.
```

<!-- FW-RT6-0c-B-FACTORY-RESOURCE-ROOT:BEGIN -->
## v6 installable-resource compatibility extension

The accepted v5.1 four-parameter text factory prefix is preserved and one
keyword-only compatibility argument is appended:

```python
create_text_chat_session(
    preset=None,
    character_name=None,
    provider=None,
    model=None,
    *,
    project_root=None,
)
```

`project_root` resolves preset and character resources only. It is not a
provider credential or provider configuration path.
<!-- FW-RT6-0c-B-FACTORY-RESOURCE-ROOT:END -->
