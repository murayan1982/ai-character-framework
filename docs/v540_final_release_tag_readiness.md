# v5.4.0 Final Release Tag Readiness

Status:

```text
v5.4.0 final tag readiness: ACCEPTED
v5.4.0 tag/push: READY after clean committed package rebuild
```

This checkpoint adds the final pre-tag gate for AI-Character-Framework v5.4.0
Real STT Provider Execution.

## Accepted release inputs

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: ACCEPTED
v540_release_readiness_gate_status: accepted
v540_release_package_gate_status: accepted
```

The private REQ-5 run proved actual OpenAI SDK/client/provider execution and a
real transcript, while the API key, private WAV, transcript, provider payload,
private paths, and private evidence remained outside the repository.

## Why the package must be rebuilt

A verified package was generated from commit `3108109`. This checkpoint adds
public tag-readiness documentation, release notes, and smoke coverage. Once this
checkpoint is committed, the tracked source set changes.

Therefore:

```text
v540_final_package_rebuild_required_after_checkpoint_commit: True
```

The existing v5.4.0 ZIP and sidecar must be deleted and regenerated from the
clean commit containing this checkpoint. The strict gate rejects a package that
does not exactly match the current committed package set.

## Local checkpoint mode

Before committing, stage the exact five-file checkpoint and run:

```powershell
python scripts\smoke_v540_final_release_tag_readiness.py --allow-dirty
```

This validates the public docs, Git target, exact checkpoint surface, and the
current staged package set. It intentionally does not accept the ZIP built from
`3108109` as final evidence for the future commit.

## Strict pre-tag mode

After committing this checkpoint:

```powershell
Remove-Item `
  release\ai-character-framework_v5.4.0.zip, `
  release\ai-character-framework_v5.4.0.zip.sha256 `
  -Force

python scripts\build_v540_release_package.py

python scripts\smoke_v540_final_release_tag_readiness.py `
  --require-clean-tree `
  --require-package
```

The strict gate verifies the accepted package gate, clean `main` tree, Framework
`origin`, absent local tag, release notes, ZIP/sidecar SHA-256, ZIP integrity,
exact current-HEAD membership, deterministic bytes, and private exclusions.

Only after the strict gate passes may the operator create and push `v5.4.0`.

## Explicit non-actions

This checkpoint:

- does not create a tag;
- does not push or publish;
- does not create a GitHub Release or upload assets;
- does not import the actual OpenAI SDK;
- does not read an API key;
- does not read private evidence, private transcript text, or private audio;
- does not create a provider client;
- does not execute a real provider or network request;
- does not access the microphone;
- does not modify DRC.

## Accepted checkpoint result

```text
v540_final_tag_readiness_status: accepted
v540_release_notes_present: True
v540_final_package_rebuild_required_after_checkpoint_commit: True
v540_actual_openai_sdk_imported_in_gate: False
v540_provider_execution_executed_in_gate: False
v540_private_evidence_read_in_gate: False
v540_private_audio_read_in_gate: False
v540_private_transcript_read_in_gate: False
v540_microphone_accessed: False
v540_drc_repo_changed: False
v540_tag_created: False
v540_push_performed: False
v540_publish_performed: False
v540_tag_authorization: ready-after-strict-package-verification
```
