# v5.1.0 Host App SDK Readiness Notes

## Readiness definition

v5.1.0 is not primarily a new provider/runtime release. It is ready when an
external host app can use FW public text chat and voice output boundaries without
process-global import/CWD workarounds and without provider-specific knowledge.

## Expected verification command shape

The exact script names should be finalized during implementation, but v5.1.0
should have a command set similar to:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_installable_sdk_import_boundary.py
python scripts/smoke_public_factory_signatures.py
python scripts/smoke_public_result_error_contract.py
python scripts/smoke_runtime_capabilities.py
python scripts/smoke_provider_config_ownership.py
python scripts/smoke_public_session_lifecycle.py
python scripts/smoke_voice_artifact_opaque_contract.py
python scripts/smoke_public_contract_conformance.py
python scripts/smoke_v510_host_app_sdk_readiness.py
python scripts/check_release_package.py
```

Release verification should run on both the committed working tree and the fixed
release artifact contents.

## Mock-safe first

All readiness checks should pass without:

```text
- provider API keys
- real LLM/TTS/STT provider calls
- VTube Studio connection
- microphone access
- private audio files
- DRC app checkout
```

Real-provider execution can have separate opt-in checks, but those are not the
basis for public SDK boundary readiness.

## Session lifecycle / close contract checkpoint

Public text chat and voice output sessions now expose idempotent `close()`,
`dispose()`, context manager support, and `is_closed`. Host applications can
call these boundaries during session eviction without inspecting FW internals.

