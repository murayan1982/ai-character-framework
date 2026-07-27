# v5.3.0 Release Package Gate

Status:

```text
v5.3.0 release package gate: ACCEPTED
v5.3.0 tag/push: READY pending final release package build
```

## Purpose

This checkpoint adds the v5.3.0 release package builder and package gate.

The gate verifies that a deterministic source package can be built from
git-tracked files after the v5.3.0 release readiness gate has been accepted.

## Package target

```text
release/ai-character-framework_v5.3.0.zip
release/ai-character-framework_v5.3.0.zip.sha256
```

## Package safety boundary

The release package builder excludes:

- generated release archives;
- `.vscode/settings.json`;
- `.git` internals;
- local virtual environments;
- private/operator evidence;
- `.env` files;
- bytecode/cache files.

## Gate behavior

The smoke gate performs a dry-run package build in a temporary directory. It does
not create `release/ai-character-framework_v5.3.0.zip`.

## Not performed in this checkpoint

This checkpoint does not:

- create the final release package in `release/`;
- create a tag;
- push to remote;
- execute real STT providers;
- read audio files;
- access microphones;
- read API keys;
- change DRC.

## v5.3.0 release package gate acceptance evidence

Local verification accepted the v5.3.0 release package gate with these facts:

```text
v530_release_package_gate_status: accepted
v530_release_package_dry_run_succeeded: True
v530_release_package_created_in_release_dir: False
v530_release_package_sha256_present: True
v530_release_package_excludes_vscode_settings: True
v530_release_package_excludes_private_evidence: True
v530_release_package_excludes_env_files: True
v530_provider_execution_executed: False
v530_microphone_accessed: False
v530_audio_handled: False
v530_tag_authorization: ready-for-final-release-package-build
```

The release package gate also re-ran and passed:

- `smoke_v530_release_readiness_gate.py`
- `smoke_v530_drc_public_handoff_verification.py`
- `smoke_v530_guarded_real_provider_adapter.py`
- `smoke_v530_voice_input_session_adapter_wiring.py`
- `smoke_v530_lazy_provider_adapter_fake.py`
- `smoke_v530_host_audio_source_contract.py`
- `smoke_v530_real_stt_provider_boundary_inventory.py`
- `smoke_v520_voice_input_public_contract_conformance_gate.py`
- `smoke_v520_release_readiness_gate.py`

No final release package in `release/`, tag creation, remote push, DRC repo
change, real provider execution, microphone access, audio read, or API key read
was performed.

`.vscode/settings.json` remained local-only and is not part of this checkpoint.
