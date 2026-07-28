\
# v5.4.0 Release Package Gate

Status:

```text
v5.4.0 release package gate: ACCEPTED
v5.4.0 tag/push: READY pending final release package build
```

## Purpose

This checkpoint adds the deterministic v5.4.0 source-package builder and package
gate after acceptance of the v5.4.0 source-tree release-readiness gate.

## Package target

The later final operator build will create:

```text
release/ai-character-framework_v5.4.0.zip
release/ai-character-framework_v5.4.0.zip.sha256
```

The final artifacts are generated files and are not created by this checkpoint.

## Deterministic package boundary

The builder:

- reads the sorted git-tracked source set;
- requires the accepted v5.4.0 public runtime, REQ documents, operator/validator
  tooling, release-readiness gate, package gate, and their smoke scripts;
- writes each ZIP entry with a fixed timestamp and permissions;
- uses deterministic compression and archive ordering;
- writes a SHA-256 sidecar.

The package excludes:

- generated `release/` artifacts;
- `.vscode/settings.json`;
- `.git` internals;
- virtual environments;
- bytecode and cache files;
- `.env` and private environment files;
- `operator_evidence.json`;
- `private_transcript.txt`;
- private staged/source WAV files;
- other tracked WAV files.

## Gate behavior

Run:

```powershell
python scripts\smoke_v540_release_package_gate.py
```

The smoke builds the v5.4.0 ZIP twice in temporary directories, verifies equal
SHA-256 digests, verifies ZIP integrity and exact archive membership, and checks
the public/private exclusion boundary.

It also re-runs:

- `scripts/smoke_v540_release_readiness_gate.py`;
- `scripts/smoke_v530_release_package_gate.py`;
- `scripts/check_release_package.py`.

## Explicit non-actions

This checkpoint:

- does not create the final release package;
- does not write the final SHA-256 sidecar under `release/`;
- does not create a tag;
- does not push or publish;
- does not import the actual OpenAI SDK;
- does not read an API key;
- does not read private evidence, private transcript text, or private audio;
- does not create a provider client;
- does not execute a real provider or network request;
- does not access the microphone;
- does not modify DRC.

## Accepted package-gate result

```text
v540_release_package_gate_status: accepted
v540_release_package_dry_run_succeeded: True
v540_release_package_deterministic: True
v540_release_package_created_in_release_dir: False
v540_release_package_sha256_present: True
v540_release_package_excludes_vscode_settings: True
v540_release_package_excludes_private_evidence: True
v540_release_package_excludes_private_transcript: True
v540_release_package_excludes_private_audio: True
v540_release_package_excludes_env_files: True
v540_actual_openai_sdk_imported_in_gate: False
v540_actual_provider_client_created_in_gate: False
v540_provider_execution_executed_in_gate: False
v540_network_request_executed_in_gate: False
v540_private_credential_read_in_gate: False
v540_private_evidence_read_in_gate: False
v540_private_audio_read_in_gate: False
v540_private_transcript_read_in_gate: False
v540_microphone_accessed: False
v540_drc_repo_changed: False
v540_tag_created: False
v540_push_performed: False
v540_tag_authorization: ready-for-final-release-package-build
```

After this checkpoint is committed from a clean tree, the final package may be
built with:

```powershell
python scripts\build_v540_release_package.py
```

The final ZIP and sidecar must then be verified before any tag, push, or GitHub
Release step.
