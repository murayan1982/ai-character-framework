# Release Package Policy

This document defines which files should be included in public release packages and which files should stay internal or local.

## Goals

Public release packages should be:

- easy to run
- easy to inspect
- free from local secrets
- free from generated cache files
- free from internal release-operation notes
- consistent with public documentation links

## Public release package

The public release package is intended for users who want to try or build on the current version of the framework.

It should contain the files needed to install, run, inspect, and integrate with the framework.

## Include

Public release packages should include:

```text
README.md
LICENSE.txt
.env.example
requirements.txt
install.bat
run.bat
main.py

characters/
config/
core/
docs/
examples/
framework/
live2d/
llm/
plugins/
presets/
registry/
scripts/
stt/
tts/
utils/
```

## Exclude

Public release packages should not include:

```text
.env
.git/
.github/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
dist/
build/
*.log
release_checklist_*.md
local test output
temporary working notes
```

## Documentation rules

Files included in the public package should not link to files that are intentionally excluded.

Public docs should not link to:

```text
release_checklist_*.md
old version-specific release notes
local-only files
private notes
```

Current release notes should use the stable path:

```text
RELEASE_NOTES.md
```

Historical release notes are preserved by Git tags and GitHub Releases.

## Release checklist files

Release checklist files are internal working files.

They may exist during release preparation, but they should not be required by public documentation and should not be included in public release packages.

## Sanity check expectations

Before publishing a release package, check that:

```text
required files exist
required directories exist
forbidden files are absent
public Markdown links point to included files
public docs do not reference internal release checklist files
.env is not included
cache files are not included
```

## Recommended verification

For the current v5.0.0 mock-safe package verification, run:

```powershell
python -m compileall -q .
python scripts/smoke_public_facade.py
python scripts/smoke_app_sdk.py
python scripts/smoke_voice_output_real_tts_opt_in_boundary.py
python scripts/smoke_voice_output_artifact_result_contract.py
python scripts/smoke_voice_output_real_provider_execution_guard.py
python scripts/smoke_voice_output_host_app_handoff.py
python scripts/smoke_voice_output_v500_release_readiness.py
python scripts/smoke_voice_output_v500_package_readiness.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

Legacy text-chat examples may also be run as optional smoke checks:

```powershell
python examples/app_error_handling.py
python examples/public_text_chat.py
python examples/minimal_app_text_chat.py
```

## Local build workflow

Release packages may be created with a local build script outside Git management.

The local build script is treated as a maintainer-side tool and is not included in the repository or public release package.

Generated release packages may be stored locally under a versioned `release/` directory.

The `release/` directory is a local artifact archive and should not be committed to Git.