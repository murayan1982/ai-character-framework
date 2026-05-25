# AI-Character-Framework v5.0.0 final release commands

This helper creates a fixed `release/ai-character-framework_v5.0.0.zip` from committed `HEAD`, adds explicit release-package extras that are required by `scripts/check_release_package.py`, extracts that fixed zip, and runs the final verification commands against the extracted contents.

## Run

```powershell
powershell -ExecutionPolicy Bypass -File .\create_v500_release_candidate.ps1
```

If `release\ai-character-framework_v5.0.0.zip` already exists and you intentionally want to replace it:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_v500_release_candidate.ps1 -Overwrite
```

## What it verifies

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

The same command set runs twice:

1. against the committed working tree
2. against the extracted fixed release zip contents

## Important

The previous helper used `git archive HEAD` directly. That omitted package-only launcher files such as `install.bat` and `run.bat` when they were present in the working tree but not included in the git archive output. This helper now stages `HEAD` first, explicitly copies those required package extras, then creates the final zip from that staged package.

The helper itself is not included in the release zip.

## Tag after successful verification

The helper does not create or push the tag automatically.

After the fixed release zip passes verification:

```powershell
git tag -a v5.0.0 -m "Release v5.0.0"
git push origin v5.0.0
```
