# v5.4.0 Candidate Real STT Provider Execution Small Commit Checklist

Status:

```text
requirements definition: ACCEPTED
```

## Guardrails

- Preserve provider-safe `import framework`.
- Preserve v5.3.0 public Voice Input contracts.
- Preserve fake adapter behavior.
- Preserve guarded adapter non-execution behavior until real execution gates are explicitly implemented.
- Do not read audio before execution gates pass.
- Do not create provider clients before execution gates pass.
- Do not read credentials before execution gates pass.
- Do not expose private file paths, raw audio, credentials, or provider payloads.
- Do not modify DRC in Framework commits.
- Keep private operator evidence outside the repository.
- Do not create a release package or tag during requirements definition.

## REQ-0 - Requirements definition

Status:

```text
ACCEPTED
```

Changed files:

```text
README.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_real_stt_provider_execution_requirements.py
```

Acceptance requirements:

- [ ] `python -m compileall -q framework core stt scripts examples`
- [ ] `python scripts/smoke_v540_real_stt_provider_execution_requirements.py`
- [ ] `python scripts/smoke_v530_release_package_gate.py`
- [ ] `python scripts/smoke_v530_release_readiness_gate.py`
- [ ] `python scripts/smoke_v530_drc_public_handoff_verification.py`
- [ ] `python scripts/smoke_v530_guarded_real_provider_adapter.py`
- [ ] `python scripts/smoke_v530_voice_input_session_adapter_wiring.py`
- [ ] `python scripts/smoke_v530_lazy_provider_adapter_fake.py`
- [ ] `python scripts/smoke_v530_host_audio_source_contract.py`
- [ ] `python scripts/smoke_v530_real_stt_provider_boundary_inventory.py`
- [ ] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [ ] `python scripts/smoke_v520_release_readiness_gate.py`
- [ ] `git diff --check` for REQ-0 files
- [ ] no real provider execution
- [ ] no microphone access
- [ ] no audio file read
- [ ] no API key read
- [ ] no DRC repo change
- [ ] no release package creation
- [ ] no tag creation

## REQ-1 - Provider execution configuration and status

Status:

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```

Changed files:

```text
README.md
framework/__init__.py
framework/voice_input_provider_execution.py
docs/v540_provider_execution_configuration_status.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_provider_execution_configuration_status.py
```

Acceptance requirements:

- [x] `python -m compileall -q framework core stt scripts examples`
- [x] `python scripts/smoke_v540_provider_execution_configuration_status.py`
- [x] `python scripts/smoke_v540_real_stt_provider_execution_requirements.py`
- [x] `python scripts/smoke_v530_release_package_gate.py`
- [x] `python scripts/smoke_v530_release_readiness_gate.py`
- [x] `python scripts/smoke_v530_drc_public_handoff_verification.py`
- [x] `python scripts/smoke_v530_guarded_real_provider_adapter.py`
- [x] `python scripts/smoke_v530_voice_input_session_adapter_wiring.py`
- [x] `python scripts/smoke_v530_lazy_provider_adapter_fake.py`
- [x] `python scripts/smoke_v530_host_audio_source_contract.py`
- [x] `python scripts/smoke_v530_real_stt_provider_boundary_inventory.py`
- [x] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [x] `python scripts/smoke_v520_release_readiness_gate.py`
- [x] exact seven-file `git diff --check`
- [x] existing v5.2.0/v5.3.0 gates remain green
- [x] provider-safe public import remains green
- [x] explicit opt-in defaults to false
- [x] provider configuration is explicit-only
- [x] credential availability is boolean-only
- [x] no credential value read or output
- [x] no provider SDK import or client creation
- [x] no provider execution
- [x] no audio file read
- [x] no microphone access
- [x] no DRC repository change
- [x] `.vscode/settings.json` remains local-only and is not included

Stop rule:

```text
REQ-2 may start only in the next small commit.
REQ-1 acceptance does not retroactively add a provider SDK, client factory,
executor, audio reader, microphone path, credential resolver, private
evidence, release package, or tag.
```

## REQ-2 - Safe FILE_PATH validation

Status:

```text
BLOCKED pending REQ-1 acceptance
```

Expected focus: file existence, normal file check, empty/invalid file rejection, size/duration limits, no private path exposure, and no audio read before gates pass.

## REQ-3 - Injectable real-provider client boundary

Status:

```text
BLOCKED pending REQ-2 acceptance
```

Expected focus: fake injected client, provider call shape, model/config propagation, transcript normalization, provider error mapping, and no network in source acceptance.

## REQ-4 - First concrete real-provider adapter

Status:

```text
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```

Changed files:

```text
README.md
framework/__init__.py
framework/openai_voice_input_real_provider.py
docs/v540_openai_real_provider_runtime.md
docs/v540_openai_adapter_client_injection_contract.md
docs/v540_openai_fake_execution_boundary.md
docs/v540_provider_execution_configuration_status.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_openai_fake_execution_boundary.py
scripts/smoke_v540_openai_real_provider_runtime.py
```

Acceptance requirements:

- [x] Python source compiles
- [x] exact eleven-file worktree surface
- [x] REQ-1 through REQ-3 acceptance gates remain green
- [x] framework root import remains provider-safe
- [x] actual `openai` module is not loaded by root import
- [x] SDK import default is false
- [x] client creation default is false
- [x] real provider execution default is false
- [x] private credential is explicit and non-empty
- [x] Framework does not read credential environment variables
- [x] private credential repr/str is redacted
- [x] concrete factory forwards explicit API key, timeout, and retry count
- [x] `client.audio.transcriptions.create(...)` call shape verified
- [x] bounded FILE_PATH/WAV handoff verified
- [x] missing/non-regular/empty/oversized source rejection present
- [x] timeout mapping present
- [x] rate-limit mapping present
- [x] connection/authentication mapping present
- [x] transcript normalization present
- [x] source path not exposed
- [x] raw audio not exposed
- [x] credential value not exposed
- [x] provider payload/exception detail not exposed
- [x] actual OpenAI SDK not imported in smoke
- [x] actual provider client not created in smoke
- [x] real provider execution not performed in smoke
- [x] microphone not accessed
- [x] DRC repository not changed
- [x] exact eleven-file `git diff --check`

Stop rule:

```text
REQ-5 may start only in the next small commit.
REQ-4 acceptance does not use a real credential, import the actual SDK in
acceptance smoke, create an actual provider client, execute a network
request, access a microphone, write private evidence into the repository,
change DRC, build a release package, or create a tag.
```

\
## REQ-5 - Private real-provider operator acceptance

Status:

```text
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

Changed files:

```text
README.md
docs/v540_openai_adapter_client_injection_contract.md
docs/v540_openai_fake_execution_boundary.md
docs/v540_openai_private_real_provider_operator_acceptance.md
docs/v540_openai_real_provider_runtime.md
docs/v540_provider_execution_configuration_status.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/operator_v540_openai_private_real_provider_acceptance.py
scripts/smoke_v540_openai_private_real_provider_operator_acceptance.py
scripts/smoke_v540_openai_real_provider_runtime.py
scripts/verify_v540_openai_private_real_provider_evidence.py
```

Source/tooling acceptance requirements:

- [ ] Python source compiles
- [ ] exact twelve-file worktree surface
- [ ] REQ-1 through REQ-4 acceptance gates remain green
- [ ] operator help is network-free
- [ ] operator help does not read a credential
- [ ] actual OpenAI SDK not imported by source smoke
- [ ] explicit real-execution confirmation required
- [ ] explicit private-data confirmation required
- [ ] private audio must be outside repository
- [ ] private evidence must be outside repository
- [ ] `OPENAI_LOG=debug` is rejected
- [ ] original private WAV is not deleted
- [ ] private staged WAV cleanup is implemented
- [ ] complete transcript is not printed
- [ ] API key/private path/raw audio/provider payload is not printed
- [ ] private evidence validator is present
- [ ] exact twelve-file `git diff --check`

Private operator acceptance requirements:

- [ ] optional OpenAI SDK installed in private operator environment
- [ ] private credential not committed or pasted
- [ ] private WAV outside repository
- [ ] explicit SDK import opt-in
- [ ] explicit client-creation opt-in
- [ ] explicit real-provider execution opt-in
- [ ] actual OpenAI SDK imported
- [ ] actual provider client created
- [ ] actual provider call completed
- [ ] real non-empty transcript obtained
- [ ] public result type is `VoiceInputResult`
- [ ] public result marks real execution
- [ ] public result omits credential/path/audio/payload
- [ ] transcript text omitted from console
- [ ] transcript/evidence remain outside repository
- [ ] private staged WAV cleanup verified
- [ ] repository clean before and after
- [ ] private evidence validator passes
- [ ] explicit operator approval given

Stop rule:

```text
Do not mark REQ-5 accepted from source smoke alone.
Do not paste or commit credential values, private paths, raw audio, complete
transcript text, provider payloads, provider exception details, or private
operator evidence.
Do not begin release readiness, DRC adoption, package creation, tagging, or
release before REQ-5 acceptance.
```

## REQ-6 - DRC released-FW adoption gate

Status:

```text
BLOCKED pending FW release
```

Expected focus: DRC public-only import, DRC private WAV handoff, real transcript handoff, fake path preserved, and RT-3d unblock criteria.

## REQ-2 - OpenAI adapter/config/client-injection contract

Status:

```text
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

Changed files:

```text
README.md
framework/__init__.py
framework/openai_voice_input_provider_adapter.py
docs/v540_openai_adapter_client_injection_contract.md
docs/v540_provider_execution_configuration_status.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_provider_execution_configuration_status.py
scripts/smoke_v540_openai_adapter_client_injection_contract.py
```

Acceptance requirements:

- [x] `python -m compileall -q framework core stt scripts examples`
- [x] `python scripts/smoke_v540_openai_adapter_client_injection_contract.py`
- [x] `python scripts/smoke_v540_provider_execution_configuration_status.py`
- [x] `python scripts/smoke_v540_real_stt_provider_execution_requirements.py`
- [x] `python scripts/smoke_v530_release_package_gate.py`
- [x] `python scripts/smoke_v530_release_readiness_gate.py`
- [x] `python scripts/smoke_v530_guarded_real_provider_adapter.py`
- [x] `python scripts/smoke_v530_drc_public_handoff_verification.py`
- [x] `python scripts/smoke_v520_voice_input_public_contract_conformance_gate.py`
- [x] `python scripts/smoke_v520_release_readiness_gate.py`
- [x] exact nine-file `git diff --check`
- [x] provider-safe `import framework`
- [x] exact OpenAI client protocol is public
- [x] model configuration is explicit
- [x] client and client-factory injection are explicit
- [x] client factory is not invoked
- [x] FILE_PATH-only source metadata
- [x] WAV-only source metadata
- [x] explicit max-duration bound required
- [x] source path is not exposed
- [x] no OpenAI SDK import or dependency change
- [x] no credential value read or output
- [x] no client creation
- [x] no audio file read
- [x] no microphone access
- [x] no provider execution
- [x] no DRC repository change
- [x] `.vscode/settings.json` remains local-only and is not included

Stop rule:

```text
REQ-3 may start only in the next small commit.
REQ-2 acceptance does not add audio-file resolution, fake or real provider
execution, SDK loading, credential resolution, private evidence, DRC changes,
release packages, or tags.
```

## REQ-3 - Bounded audio-file resolution / marked-fake execution

Status:

```text
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

Changed files:

```text
README.md
framework/__init__.py
framework/openai_voice_input_fake_execution.py
docs/v540_openai_fake_execution_boundary.md
docs/v540_openai_adapter_client_injection_contract.md
docs/v540_provider_execution_configuration_status.md
docs/v540_real_stt_provider_execution_requirements.md
docs/v540_real_stt_provider_execution_small_commit_checklist.md
scripts/smoke_v540_openai_adapter_client_injection_contract.py
scripts/smoke_v540_openai_fake_execution_boundary.py
```

Acceptance requirements:

- [x] Python source compiles
- [x] exact ten-file worktree surface
- [x] REQ-1 and REQ-2 acceptance gates remain green
- [x] framework root import remains provider-safe
- [x] direct client injection required
- [x] `OpenAIVoiceInputFakeClientMarker` inheritance required
- [x] fake execution opt-in required
- [x] positive `max_audio_bytes` required
- [x] regular FILE_PATH/WAV source required
- [x] pre-read and during-read byte bounds enforced
- [x] client factory not invoked
- [x] marked fake `create(...)` called exactly once in success smoke
- [x] unmarked client never called
- [x] fake exception converted to safe typed failure
- [x] source path not exposed
- [x] raw audio not exposed
- [x] provider payload not exposed
- [x] no OpenAI SDK import
- [x] no credential-value read
- [x] no provider client creation
- [x] no real provider execution
- [x] no microphone access
- [x] no DRC repository change
- [x] exact ten-file `git diff --check`

Stop rule:

```text
REQ-4 may start only in the next small commit.
REQ-3 acceptance does not add OpenAI SDK loading, credential resolution,
real provider clients or execution, private operator evidence, microphone
capture, DRC changes, release packages, or tags.
```

### REQ-5 acceptance sync completion

- [x] Actual OpenAI SDK imported only after explicit authorization.
- [x] Actual provider client created.
- [x] Real provider execution completed.
- [x] Real transcript obtained.
- [x] Provider-neutral Framework result present.
- [x] API key, private path, raw audio, provider payload, and transcript text
      omitted from public output.
- [x] Private evidence remained outside the repository.
- [x] Private staged audio cleanup verified.
- [x] Worktree clean before and after the operator run.
- [x] Microphone not accessed.
- [x] DRC not changed.
- [x] Private evidence accepted by the public-safe validator.

```text
v540_req5_private_evidence_status: accepted-by-validator
v540_req5_public_acceptance_sync_status: accepted
v540_req5_release_readiness_authorization: ready-for-next-small-commit
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

\
## v5.4.0 release readiness gate

- [x] REQ-1 provider execution configuration/status accepted.
- [x] REQ-2 adapter/client-injection contract accepted.
- [x] REQ-3 bounded fake execution accepted.
- [x] REQ-4 lazy real-provider runtime accepted.
- [x] REQ-5 private real-provider evidence accepted.
- [x] Public REQ-5 acceptance sync committed.
- [x] Framework root import remains provider-safe.
- [x] Accepted v5.4.0 public runtime symbols remain exported.
- [x] v5.3.0 release-readiness regression passes.
- [x] v5.2.0 release-readiness regression passes.
- [x] Baseline release-package check passes.
- [x] Private evidence remained outside the repository.
- [x] No private WAV, transcript, evidence JSON, API key, private path, or
      provider response is committed or read by this gate.
- [x] No actual SDK import, provider-client creation, or network request occurs
      in this gate.
- [x] No microphone access.
- [x] No DRC change.
- [x] No v5.4.0 release package creation.
- [x] No checksum-sidecar creation.
- [x] No v5.4.0 tag creation.
- [x] No push or publication.

```text
v5.4.0 release readiness: ACCEPTED
v5.4.0 release package/tag: READY pending next small commit
v540_release_readiness_gate_status: accepted
v540_req5_private_evidence_status: accepted-by-validator
v540_release_package_authorization: ready-for-release-package-gate
```

The next small commit is the deterministic v5.4.0 release-package gate. The
final package build, checksum verification, tag, push, and publication remain
separate operator steps.

\
## v5.4.0 release package gate

- [x] Add deterministic v5.4.0 source-package builder.
- [x] Package only sorted git-tracked public files.
- [x] Require the v5.4.0 public runtime and accepted REQ/release gate files.
- [x] Use fixed ZIP timestamps, permissions, ordering, and compression.
- [x] Write a SHA-256 sidecar.
- [x] Exclude `release/`, local VS Code settings, environments, caches, and
      bytecode.
- [x] Exclude private operator evidence and transcripts.
- [x] Exclude private staged/source WAV and other WAV files.
- [x] Build twice in temporary directories.
- [x] Verify equal SHA-256 digests.
- [x] Verify ZIP integrity and exact package membership.
- [x] Re-run v5.4.0 release-readiness gate.
- [x] Re-run v5.3.0 release-package regression.
- [x] Re-run baseline release-package check.
- [x] Do not create the final release package.
- [x] Do not create the final checksum sidecar.
- [x] Do not import the actual OpenAI SDK.
- [x] Do not read API credentials/private evidence/audio/transcripts.
- [x] Do not execute a real provider or network request.
- [x] Do not access the microphone.
- [x] Do not modify DRC.
- [x] Do not create a tag, push, or publish.

```text
v5.4.0 release package gate: ACCEPTED
v5.4.0 tag/push: READY pending final release package build
v540_release_package_gate_status: accepted
v540_release_package_dry_run_succeeded: True
v540_release_package_deterministic: True
v540_release_package_created_in_release_dir: False
v540_tag_authorization: ready-for-final-release-package-build
```

After this checkpoint is committed and the tree is clean, build and verify the
final ZIP and checksum as a separate operator step before tag creation.

## v5.4.0 final release tag readiness

- [x] Add v5.4.0 release notes.
- [x] Add final tag-readiness documentation and smoke.
- [x] Require accepted REQ-1 through REQ-5.
- [x] Require accepted release-readiness and package gates.
- [x] Require `main`, Framework `origin`, and a resolved HEAD.
- [x] Require the local `v5.4.0` tag to be absent before tagging.
- [x] Permit only the exact five-file uncommitted checkpoint surface.
- [x] Require a clean worktree in strict pre-tag mode.
- [x] Require the final ZIP and `.zip.sha256` sidecar.
- [x] Verify sidecar filename and SHA-256.
- [x] Verify ZIP integrity, exact current-HEAD membership, and deterministic
      byte-for-byte rebuild.
- [x] Require tag-readiness docs, smoke, and release notes inside the ZIP.
- [x] Exclude private evidence, transcript, audio, credentials, environments,
      local settings, and generated release entries.
- [x] Do not import the actual OpenAI SDK.
- [x] Do not execute a real provider or network request.
- [x] Do not access the microphone.
- [x] Do not modify DRC.
- [x] Do not create a tag.
- [x] Do not push or publish.
- [x] Do not create a GitHub Release or upload assets.

The package already verified from commit `3108109` must be deleted and rebuilt
after this checkpoint is committed because the tracked source set changes.

```text
v5.4.0 final tag readiness: ACCEPTED
v5.4.0 tag/push: READY after clean committed package rebuild
v540_final_tag_readiness_status: accepted
v540_final_package_rebuild_required_after_checkpoint_commit: True
v540_tag_authorization: ready-after-strict-package-verification
```
