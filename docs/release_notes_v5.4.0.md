# AI-Character-Framework v5.4.0 Release Notes

## Real STT Provider Execution

v5.4.0 completes the real speech-to-text provider execution boundary introduced
by the v5.3.0 public Voice Input API.

## Highlights

- Explicit provider execution configuration and provider-neutral status.
- Lazy OpenAI adapter/client-injection contract.
- Bounded host-supplied audio execution with a preserved fake path.
- Lazy real-provider runtime that keeps Framework root import provider-safe.
- Safe fixed OpenAI API-status classifications without exposing provider error
  bodies, responses, request IDs, credentials, private paths, raw audio, or
  transcript text.
- Operator-only private real-provider acceptance using an actual OpenAI
  transcription request.
- Deterministic source-package builder and SHA-256 sidecar.

## Accepted requirements

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: ACCEPTED
```

The private acceptance run confirmed actual OpenAI SDK import after explicit
authorization, actual client creation, real provider execution, real transcript
presence, and conversion to a provider-neutral Framework result.

## Privacy and safety boundary

The API key, private WAV, transcript, provider payload, private paths, and
private evidence remained outside the repository. Public console output and
committed source do not contain those values.

Default Framework import and source-tree/package gates do not import the actual
OpenAI SDK, create a provider client, execute a network request, access a
microphone, or read private audio/evidence/transcripts.

## Compatibility

The host-captured Voice Input boundary and fake provider path remain available.
Real provider execution is explicit rather than enabled by default.

DRC was not changed as part of the Framework v5.4.0 release work.

## Verification

The release process requires:

```powershell
python scripts\smoke_v540_release_readiness_gate.py
python scripts\smoke_v540_release_package_gate.py
python scripts\smoke_v540_final_release_tag_readiness.py `
  --require-clean-tree `
  --require-package
```

The final ZIP must match its SHA-256 sidecar, pass ZIP-integrity and exact
membership checks, reproduce byte-for-byte from the clean tagged commit, and
exclude private/local/generated artifacts.
