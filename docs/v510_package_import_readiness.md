# v5.1.0 Package Import Readiness

Status: v5.1.0 P0 / FW-F1 + FW-F8 implementation checkpoint.

## Purpose

v5.1.0 is focused on making FW easier and safer for host applications to use.
DRC v2.x/v3.x planning showed that the public SDK must be usable without
checkout-layout assumptions, temporary `sys.path` workarounds, import cache
clearing, or changing the host application's current working directory.

This checkpoint adds a mock-safe package-import readiness smoke. The smoke
copies the public `framework` package into a temporary package-like directory,
then runs a child Python process from outside the repository root with only that
temporary package directory on `PYTHONPATH`.

## Checked boundary

The package import readiness smoke checks:

```text
- import framework works from outside the repository root
- public symbols are available from framework.__all__
- public import does not eagerly import provider SDKs
- public data/result types can be constructed outside the repo checkout
- VoiceOutputSession.speak(...) is usable through the package-like import path
- closed/session lifecycle behavior remains provider-neutral
- VoiceArtifactRef remains opaque and rejects local/private path-like IDs
- mock-safe checks do not call provider APIs or create real audio artifacts
```

## Explicit non-goals

This checkpoint does not publish a wheel, upload a package, tag a release, or
validate a real pip install from an artifact. It is a pre-release readiness gate
that verifies the source package can be imported as a host app would import an
SDK package.

## Command

```powershell
python scripts/smoke_v510_package_import_readiness.py
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
python scripts/smoke_v510_package_import_readiness.py
python scripts/check_release_package.py
```

## DRC integration meaning

DRC should be able to depend on FW as a package-like SDK instead of importing
from a local checkout structure. DRC should not need to mutate `sys.path`, delete
`sys.modules`, disable import caches, or temporarily change CWD just to reach FW
public APIs.

This smoke is the v5.1.0 bridge toward that goal. A later release checkpoint can
replace the temporary package-copy import with a fixed wheel/sdist install check.

## v5.1.0 transition note

The package import readiness smoke copies a source-distribution-like tree of
FW-owned importable packages, not only the `framework/` directory. This records
the current transition state where the public facade still references owned
top-level modules such as `llm.*`, while keeping the repository root and host app
CWD out of `PYTHONPATH`.

## Source tree copy rule

The package import readiness smoke copies FW-owned root-level Python source
directories into the temporary source-distribution-like tree. This includes
transition top-level imports such as `llm.*` and `config.*` while still keeping
the repository root and host app CWD out of `PYTHONPATH`.

Local virtual environment directories are excluded from the temporary
source-distribution-like tree.

## Local secret hygiene

Release/package readiness excludes local token and secret artifacts, including
`config/tokens/`, `*_token.json`, `.env`, generated audio files, and runtime
output directories.

