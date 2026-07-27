# AI-Character-Framework v5.3.0 Roadmap

## Theme

Public Voice Input / Real STT Provider Boundary.

v5.3.0 starts from the DRC RT-3 blocker:

```text
DRC RT-3: BLOCKED_REAL_STT_NOT_IMPLEMENTED
```

The first real STT route should use host-captured audio handoff. The framework
must not open the device microphone directly for the DRC path.

## Priority order

1. Real STT provider boundary inventory
2. Provider-neutral host-audio source contract
3. Lazy provider adapter protocol and fake adapter
4. Public `VoiceInputSession` adapter wiring
5. First guarded real provider adapter
6. DRC public handoff verification

## Non-goals for STT-1a

STT-1a is documentation and test inventory only.

It does not change runtime code, import provider SDKs, read API keys, handle raw
audio, access microphones, call real STT providers, modify DRC, create a release
package, or create a tag.
