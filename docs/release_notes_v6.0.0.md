# AI Character Framework v6.0.0 Release Notes

## Provider-neutral realtime lifecycle

v6.0.0 adds a provider-neutral realtime session model while preserving the v5
standalone text, voice-input, voice-output, and motion APIs. The default
`RealtimeSession` profile remains the provider-free `v5_skeleton`; guarded real
composition is selected only by explicit configuration.

## Highlights

- immutable capability snapshots and typed construction results;
- canonical lifecycle, turn, streaming, TTS, playback, motion, interruption,
  recovery, and cleanup events;
- single-active-turn ownership, monotonic sequence numbers, and exactly-once
  terminal outcomes;
- cooperative interruption, stale-result rejection, and generation ownership;
- host-owned playback stop request/acknowledgement boundaries;
- guarded real-runtime composition without enabling provider execution by
  default;
- natural-turn controls with explicit policy and capability truthfulness;
- provider-free aggregate conformance and frozen migration/reference docs;
- deterministic source ZIP generation and SHA-256 verification.

## Compatibility

Existing v5 standalone factories remain supported. Root-public imports remain
provider-safe, the root-public manifest contains 127 names, and provider SDKs
remain optional and lazy. The v6 lifecycle does not claim provider hard cancel
or Framework-owned physical playback stop.

## Security and privacy

Release tooling derives membership from Git, rejects private artifact names
before filtering, excludes generated release output, rejects duplicate or
unsafe ZIP members, and never reads private configuration or evidence. API
keys, tokens, provider identities, audio captures, transcripts, operator
evidence, screenshots, raw payloads, and raw exceptions are not release assets.

## Verification

```powershell
python scripts\check_v600_documentation_freeze.py --source-only
python scripts\check_v600_aggregate_conformance.py
python scripts\check_v600_release_package_smoke.py
python scripts\build_v600_release_package.py
python scripts\check_v600_release_readiness.py --strict-release
```

The official release contains:

```text
ai-character-framework_v6.0.0.zip
ai-character-framework_v6.0.0.zip.sha256
```

The annotated `v6.0.0` tag, tag push, public GitHub Release, asset upload, and
published asset redownload require a separate explicit operator authorization.
