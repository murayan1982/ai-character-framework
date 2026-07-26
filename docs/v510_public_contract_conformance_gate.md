# v5.1.0 Public Contract Conformance Gate

Status: v5.1.0 P0 / FW-F8 implementation checkpoint.

## Purpose

v5.1.0 reduces host-app integration cost after DRC v2.x real-app feedback.
The conformance gate makes the public SDK surface checkable before release.
It guards against docs/API drift, accidental legacy aliases, eager provider
imports, and provider/private detail leakage through public results.

This gate is intentionally mock-safe. It must not require provider credentials,
provider SDKs, network access, real LLM calls, real TTS calls, real audio
artifacts, DRC runtime state, or VTube Studio/Live2D connections.

## Checked public surface

The gate checks that the following public symbols are exported by
`framework.__all__` and are importable from `framework`:

```text
create_text_chat_session
TextChatSessionInfo
TextChatResult
CapabilityStatus
FrameworkCapabilities
get_capabilities
create_voice_output_session
VoiceOutputSession
VoiceOutputSessionInfo
VoiceOutputRequest
VoiceArtifactRef
VoiceOutputResult
```

The gate also checks that legacy or speculative factory aliases are not exported
as public API:

```text
create_tts_session
create_output_session
create_voice_session
create_realtime_voice_session
```

## Checked method and result contracts

The gate checks the current v5.1.0 public contract baseline:

```text
TextChatSession.ask_result(message) returns a TextChatResult-compatible typed result.
VoiceOutputSession.speak(request) is the preferred voice output method.
VoiceOutputSession.create_output(request) remains a v5.0 compatibility alias.
VoiceArtifactRef is opaque and rejects raw local/private paths.
VoiceOutputResult non-playable states do not expose playable handoffs.
get_capabilities() returns provider-neutral capability state.
Public sessions expose close()/dispose()/context manager/is_closed behavior.
```

## Import safety

The gate must preserve the lightweight public import contract:

```text
import framework must not import provider SDKs
import framework must not import tts.voice_engine
mock-safe public checks must not validate live credentials
mock-safe public checks must not call provider APIs
mock-safe public checks must not create real audio artifacts
```

## Docs and examples

The gate checks that the v5.1.0 public contract docs and examples exist and
remain aligned with the public API. README examples should use `session.speak(...)`
for voice output. The typed text chat example should use `ask_result(...)` rather
than forcing host apps to parse exception strings.

## Command

```powershell
python scripts/smoke_v510_public_contract_conformance_gate.py
```

Recommended v5.1.0 local verification sequence after this checkpoint:

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/smoke_v510_factory_signature_contract.py
python scripts/smoke_v510_result_error_contract.py
python scripts/smoke_v510_text_chat_result_public_type.py
python scripts/smoke_v510_text_chat_result_runtime_method.py
python scripts/smoke_v510_capability_snapshot.py
python scripts/smoke_v510_provider_config_ownership.py
python scripts/smoke_v510_session_lifecycle.py
python scripts/smoke_v510_opaque_voice_artifact_contract.py
python scripts/smoke_v510_public_contract_conformance_gate.py
python scripts/check_release_package.py
```

## DRC integration meaning

DRC should not need to scan FW checkout files, inspect multiple factory alias
names, parse provider exception strings, or import FW internals in order to use
stable public contracts. This gate is the release-time backstop for that goal.
