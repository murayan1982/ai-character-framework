# v6.0.0 real-runtime operator acceptance

<!-- FW-RT6-13c-REAL-RUNTIME-OPERATOR:BEGIN -->
## FW-RT6-13c tooling candidate

FW-RT6-13c is an operator-only acceptance layer over already accepted,
host-owned real stages. It does **not** enable real unified
`RealtimeSession.run_turn()` orchestration. The production Framework source,
root-public 127-name manifest, facade factories, and guarded 13b composition
remain unchanged.

The source-only gate and dedicated tests are provider-free. They do not import
OpenAI, ElevenLabs, pyvts, or websockets; read credentials, private config,
audio, or evidence; use a microphone or playback device; connect to VTube
Studio; or execute a provider. A real operator run is a later, separately
authorized action and must run only from a committed, pushed, remotely verified
`main` checkout with a clean tree.

### Three-phase boundary

1. Review, commit, push, and remotely verify this exact nine-file tooling
   candidate.
2. Separately authorize and perform the private real operator run outside the
   repository. The runner records only a fixed safe evidence schema.
3. Validate that evidence with the independent private verifier, then prepare a
   separately authorized public acceptance-sync candidate. Only phase 3 may
   close the nine canonical tasklist scenarios.

The current tooling candidate therefore retains `0 / 9` closed scenarios.

### Private configuration

The operator accepts one absolute JSON file outside the repository with schema
`ai-character-framework-v600-rt6-13c-private-config-v1`. Its exact top-level
members are `schema`, `accepted_framework_head`, `voice_input`,
`text_generation`, `voice_output`, and `motion`.

The private file supplies an accepted commit SHA, a private WAV and duration,
private STT/LLM model choices and prompts, credential environment-variable
names, a private voice-artifact directory, and a private v5.5 VTube Studio
configuration file. Credential values remain environment-owned. The runner
rejects relative paths, repository-contained paths, unexpected fields,
unbounded text, non-WAV audio, non-loopback VTS configuration, an unclean tree,
a non-`main` branch, or a HEAD that differs from both the private accepted SHA
and `origin/main`.

Provider versions are exact: `openai==2.31.0`, `elevenlabs==2.41.0`, and
`pyvts==0.3.3` (with the repository-pinned `websockets==16.0`). Debug provider
logging is forbidden for the private run.

### Real operator scenarios

The operator coordinates the following host-owned steps:

1. Execute configured real OpenAI STT against the private staged WAV without
   microphone access.
2. Stream a configured real OpenAI LLM response through the injected-client
   provider-neutral adapter.
3. Request cooperative interrupt after a real delta, suppress all future
   delivery, and keep `provider_hard_cancel_claimed=False`.
4. Generate a real ElevenLabs MP3 into a private Framework-owned artifact
   directory.
5. Clear pending TTS work and reject/invalidate a deliberately retired late
   real artifact.
6. Hand the opaque artifact to the host and require operator confirmation of
   playback stop. Framework records request/ack only and never claims the
   physical stop.
7. Execute configured local-loopback real VTube Studio motions using the
   accepted v5.5 private-config and visual-confirmation protocol.
8. Complete a fresh real LLM turn after interruption.
9. Close all owned stages/clients and verify VTS bridge-thread termination and
   a clean repository.

The host owns physical playback, playback stop, VTS observation, credentials,
provider billing, private retention, and deletion. Cooperative interrupt means
future Framework delivery suppression; it is not a provider hard-cancel claim.

### Evidence and redaction

Evidence schema `ai-character-framework-v600-rt6-13c-private-evidence-v1`
contains only the accepted framework SHA, exact dependency versions, booleans,
positive counts, a random run ID, and a UTC timestamp. Its exact allowlist
contains all nine scenario markers plus explicit false markers for credential,
path, raw audio, provider payload, raw exception, transcript/LLM text, private
model, hotkey, selector, microphone, physical playback-stop, unified real
`RealtimeSession`, and DRC-repository exposure.

The verifier rejects missing or extra fields, wrong types, wrong dependency
versions, non-positive counts, any exposure marker, evidence inside the
repository, relative evidence paths, and oversized evidence. It never prints
the evidence path or contents.

```text
checkpoint: FW-RT6-13c
baseline head: cf660a0c4eb4373f21dfdd779a5f98b64457d791
status: IMPLEMENTED / VERIFIED / AWAITING_REVIEW
exact implementation surface: 9 files
production Framework source changes: 0
root-public names: 127 / UNCHANGED
RealtimeSession real orchestration changed/enabled: False
canonical scenarios closed: 0 / 9
dedicated provider-free tests: 15 / PASS
related stage/session/provider-neutral tests: 200 / PASS
full Framework unit suite: 816 / PASS
provider/network/microphone/playback/VTS execution in candidate tests: False
private config/audio/artifacts/evidence committed: False
real operator execution: NOT_AUTHORIZED
private evidence validation: NOT_RUN
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-13c-REAL-RUNTIME-OPERATOR:END -->
