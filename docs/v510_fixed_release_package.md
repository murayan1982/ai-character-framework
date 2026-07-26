# v5.1.0 Fixed Release Package Builder

This document records the v5.1.0 fixed release package build boundary.

## Purpose

v5.1.0 focuses on the installable SDK / stable host app integration boundary.
Before creating a release tag, the framework must be able to build a fixed
source package from the current committed tree and verify that the extracted
package still passes the v5.1.0 release readiness gate.

## Contract

The fixed release package builder must:

- create `release/ai-character-framework_v5.1.0.zip`
- stage the source tree under `ai-character-framework_v5.1.0/`
- exclude local-only or generated directories such as `.git`, `.venv`, `venv`,
  `__pycache__`, `build`, `dist`, `tmp`, and existing `release` output
- exclude transient patch helpers such as `apply_*.py`
- run the v5.1.0 release readiness gate before packaging
- extract the generated ZIP into a temporary directory
- run the v5.1.0 release readiness gate again from the extracted tree
- remain mock-safe
- not call provider APIs
- not create real voice/audio artifacts
- not create or push a git tag

## Output

The builder writes:

```text
release/ai-character-framework_v5.1.0.zip
release/ai-character-framework_v5.1.0_manifest.json
```

The manifest is local release evidence for the generated artifact. It includes
version, archive name, SHA-256, size, and a small set of required public release
files verified inside the archive.

## Required verification

```powershell
python scripts/smoke_v510_release_readiness_gate.py
python scripts/build_v510_fixed_release_package.py
```

Passing the builder means the current source tree and extracted release ZIP both
pass the v5.1.0 release readiness gate. It does not mean a tag has been created.

## Local secret hygiene

Release/package readiness excludes local token and secret artifacts, including
`config/tokens/`, `*_token.json`, `.env`, generated audio files, and runtime
output directories.

## Environment template hygiene

`.env` and private environment files are excluded from fixed release packages.
`.env.example` remains included because it is a public configuration template
and is required by release package checks.

