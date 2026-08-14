# v6.0 Experimental Natural-Turn Extensions

## Status

FW-RT6-12c Control A defines a provider-neutral capability vocabulary only.
It does not implement or activate a natural-turn runtime. These extensions are
not required for v6.0.0 P0 acceptance.

## Independent extensions

The explicit-only `framework.natural_turn` namespace identifies exactly seven
separately gated extensions:

| Extension | Stable value |
| --- | --- |
| Microphone listening while speaking | `microphone_listening_while_speaking` |
| VAD-based automatic detection | `vad_based_automatic_detection` |
| Wake word | `wake_word` |
| Background input monitoring | `background_input_monitoring` |
| Automatic next-turn capture | `automatic_next_turn_capture` |
| Echo cancellation | `echo_cancellation` |
| Noise suppression | `noise_suppression` |

There is no combined `natural_mode` switch. Support for one extension does not
imply support for another. Every extension requires its own future exact
contract, adapter review, lifecycle review, security/privacy review, tests, and
authorization before runtime adoption.

## Default truth

`default_natural_turn_capability_set()` returns all seven capabilities with:

```text
supported: False
experimental: True
owner: host_application
explicit_activation_required: True
microphone_device_access: False
background_execution: False
provider_execution: False
network_execution: False
```

The default therefore grants no microphone, background, provider, or network
authority. An application must not infer runtime support from module presence.

## Ownership boundary

The host application owns permission UI, device selection, physical capture,
background lifecycle, wake-word policy, consent, retention, local audio
processing policy, and physical stop. A future supported capability must be
owned by an explicitly configured adapter; it cannot be silently activated by
Framework import or session creation.

Control A changes no `RealtimeSession`, `VoiceInputSession`, provider adapter,
audio device boundary, event shape, factory signature, or root-public name. It
performs no provider, network, microphone, background, playback, or real VTS
execution.

## Public safety

Capability objects are frozen and data-only. Their public metadata is
recursively sanitized and immutable. Capability projections contain policy and
ownership facts only; they contain no audio bytes, transcript text, provider
objects, credentials, private paths, or device handles.

## Deferred work

Control B runtime adoption is not authorized by this contract. Each extension
remains a separate roadmap/exact-contract item and may be scheduled as a v6.0
experimental extension, v6.1.0 work, or a later v6.x release.
