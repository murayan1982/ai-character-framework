# v6.0.0 Public Identity Contract

## FW-RT6-1a Control A — provider-neutral identity primitives

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Control A defines four serialization-friendly public scalar types used by later
v6 correlation and stale-result controls.

```text
SessionId
TurnId
GenerationId
EventSequence
```

The identities are Framework-owned. They do not encode or expose provider
request IDs, credentials, user information, timestamps, host paths, model IDs,
or transport identifiers.

## Serialized forms

```text
SessionId: fw_session_<32 lowercase hexadecimal characters>
TurnId: fw_turn_<32 lowercase hexadecimal characters>
GenerationId: fw_generation_<32 lowercase hexadecimal characters>
EventSequence: positive JSON integer, minimum 1
```

The string identity types subclass `str`; `EventSequence` subclasses `int`.
Consequently they are immutable, hashable, and directly JSON-serializable while
still validating kind-specific prefixes.

## Construction and parsing

```python
from framework import EventSequence, GenerationId, SessionId, TurnId

session_id = SessionId.new()
turn_id = TurnId.new()
generation_id = GenerationId.new()
sequence = EventSequence.first()

assert SessionId.parse(session_id.to_json_value()) == session_id
assert TurnId.parse(turn_id.to_json_value()) == turn_id
assert GenerationId.parse(generation_id.to_json_value()) == generation_id
assert EventSequence.parse(sequence.to_json_value()) == sequence
assert sequence.next() == 2
```

Parsing rejects blank values, surrounding whitespace, wrong identity kinds,
wrong prefixes, uppercase or non-hexadecimal suffixes, path-like values, and
non-positive or boolean event sequences. A `TurnId` serialized value cannot be
parsed as a `SessionId`.

## Root-public compatibility

The original v5.5-compatible 95 names remain in the same order. The four
identity names are appended as a new `identity` group.

```text
legacy root-public prefix: 95 names / unchanged order
new identity names: 4
canonical root-public total: 99
provider compatibility exports: preserved / lazy
```

## Correlation policy

Later v6 stage integration may add these optional fields to public stage
results:

```text
TextChatResult: session_id / turn_id / generation_id
VoiceInputResult: session_id / turn_id / generation_id
VoiceOutputResult: session_id / turn_id / generation_id
MotionResult: session_id / turn_id / generation_id
```

Rules:

```text
missing correlation: None
provider request identifiers copied into Framework identity fields: False
public_metadata-only correlation accepted as final v6 contract: False
EventSequence stored on stage result models: False
```

Control A does not add those fields yet. A stage must not invent a fake session
or turn identity when no coordinating session owns one. Realtime adoption is
Control B, Motion adoption is Control C, and typed event sequence/generation
fields remain FW-RT6-1c.

## Non-execution record

```text
runtime session behavior changed: False
terminal semantics changed: False
provider SDK imported: False
provider execution: False
network execution: False
microphone used: False
audio playback: False
VTS execution: False
DRC repository accessed or changed: False
next control: FW-RT6-1a Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```

<!-- FW-RT6-1a-B-REALTIME-IDENTITY-ADOPTION:BEGIN -->
## FW-RT6-1a Control B — realtime identity adoption

Framework-generated realtime sessions and turns now use the root-public
`SessionId` and `TurnId` scalar types. Existing host applications may continue
to pass legacy non-`fw_` string identifiers; those values remain strings. A
valid serialized v6 identity is normalized to its public scalar type, while a
wrong-kind or malformed value in the reserved `fw_` namespace is rejected.

```text
checkpoint: FW-RT6-1a Control B
baseline head: 0b435e407a3fec018dce29b7446082948d1d2307
status: IMPLEMENTED / AWAITING_REVIEW
Framework-generated session identity: SessionId
Framework-generated turn identity: TurnId
legacy host session/turn strings: PRESERVED
valid serialized v6 identities: NORMALIZED
wrong-kind or malformed fw_* identity: REJECTED
root-public names: 99 / UNCHANGED
RealtimeEvent sequence/generation wiring: False
terminal behavior changed: False
provider/network/microphone/playback/VTS execution: False
next control: FW-RT6-1a Control C
next control authorized: False
commit / push: NOT_AUTHORIZED
```

This compatibility path does not promote arbitrary provider request IDs to
Framework-owned identities. Only Framework-generated IDs use the `fw_session_`
and `fw_turn_` formats. Event sequencing, generation correlation, and terminal
model changes remain later controls.
<!-- FW-RT6-1a-B-REALTIME-IDENTITY-ADOPTION:END -->
