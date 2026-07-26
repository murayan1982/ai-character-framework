# v5.1.0 Opaque Voice Artifact Contract

Status: v5.1.0 P0 / FW-F7 implementation checkpoint.

## Purpose

FW v5.0.0 introduced a provider-neutral voice output result contract with
`audio_url` and `audio_artifact_ref` as app-safe handoff options.

DRC v2.x proved that this split works:

```text
FW owns voice generation and provider handling.
DRC owns opaque Web URL publication, TTL/LRU policy, HTTP delivery, and Flutter playback.
```

v5.1.0 strengthens that boundary by making `audio_artifact_ref` explicitly
opaque. Host apps must not receive FW local paths, provider paths, provider SDK
objects, or provider payloads through the public voice output result.

## Public type

```python
from framework import VoiceArtifactRef

artifact_ref = VoiceArtifactRef.from_id(
    "voice_artifact_abc123",
    audio_format="mp3",
    content_type="audio/mpeg",
)
```

`VoiceArtifactRef` is provider-neutral and secret-free. It represents a FW-owned
artifact ID, not a local file path.

## Handoff invariant

Playable generated audio should expose exactly one public handoff:

```text
- audio_url
or
- audio_artifact_ref
```

Non-playable states must not expose either handoff:

```text
unavailable
skipped
rejected
failed
expired
cancelled
```

## Public-safety requirements

```text
- artifact ref must not expose raw local paths
- artifact ref must not expose provider IDs or provider SDK objects
- artifact ref must not expose API keys, tokens, secrets, or raw provider payloads
- artifact missing / expired outcomes must be provider-neutral
- cleanup owner must be explicit in docs and host-app integration code
- import framework must not import provider SDKs
- artifact contract checks must be mock-safe
```

## DRC integration expectation

DRC may resolve or copy FW-owned artifacts into DRC-owned temporary Web delivery
storage, then expose only DRC-owned opaque URLs to Flutter.

DRC must not:

```text
- infer local FW paths from artifact IDs
- expose provider paths in UI or marker evidence
- persist provider raw payloads
- treat guarded/unavailable results as real audio evidence
```

This checkpoint does not add real artifact storage or resolver behavior. It adds
and verifies the public opaque reference type so later artifact lifecycle work can
build on a safe contract.
