# AI Character Framework v6.0.0 Roadmap

## Unified Realtime Character Runtime

## 0. 文書情報

```text
Document:
AI Character Framework v6.0.0 Roadmap

Working title:
Unified Realtime Character Runtime

Baseline release:
v5.5.0

Baseline commit:
f56697b6de066b062794ac7bb01330d2d9e91759

Status:
PLANNING_BASELINE_RECORDED / AWAITING_REVIEW

Implementation:
NOT_AUTHORIZED

Commit / push:
NOT_AUTHORIZED
```

本roadmapは、AI Character Frameworkの既存未完了課題と、外部host applicationから得られたrealtime public contract feedbackを統合し、v6.0.0で完成させるFramework側の公開runtime境界を定義する。

外部アプリケーションのrepository、UI、端末処理、永続化、product-specific orchestrationは本roadmapの変更対象ではない。

---

## 1. v6.0.0へ移行する理由

v5系では、以下の公開境界を段階的に構築した。

```text
v5.0.0:
Public Voice Output / TTS Boundary

v5.1.0:
Real Voice Output Provider Boundary

v5.2.0:
Public Voice Input / Realtime Contract Foundation

v5.3.0:
Real Voice Input / STT Boundary

v5.4.0:
Realtime integration and public runtime expansion

v5.5.0:
Real Motion Adapter / VTube Studio
```

この結果、text、voice input、voice output、realtime、motionのroot-public API foundationは存在する。

一方、現在の`RealtimeSession`はmock-safe skeletonであり、実STT、LLM、TTS、motionを統一turnとして実行するruntimeではない。

また、現在のinterrupt、output flush、barge-inはpublic contract foundationであり、以下は未完成である。

```text
real unified turn orchestration
real cooperative cancellation composition
provider hard-cancel reporting
TTS pending queue control
active synthesis cancellation
artifact invalidation
late-result rejection
exactly-once terminal enforcement
monotonic event sequence
generation identity
automatic stale-event suppression
detailed capability snapshot
```

これらは単一機能の追加ではなく、session、turn、event、resultの意味を統合するruntime architecture変更である。

したがって次releaseはminor extensionではなく、次のmajor releaseとする。

```text
Target:
v6.0.0
```

---

## 2. Release theme

```text
Unified Realtime Character Runtime
```

Framework v6.0.0は、host applicationがprovider固有clientやFramework内部moduleを扱わずに、以下を一つの公開session contractとして制御・観測できる状態を目指す。

```text
voice input
transcription
text generation
response streaming
voice synthesis
output invalidation
interrupt
motion request
turn completion
failure and recovery
```

基本フロー：

```text
host input
-> RealtimeSession
-> RealtimeTurn
-> voice / text / output / motion stages
-> ordered typed events
-> exactly one terminal result
```

---

## 3. Design principles

### 3.1 Root-public only

host applicationは、Framework root-public APIまたは明示されたstable public packageのみを使用する。

禁止：

```text
Framework internal-module import
provider client direct construction
provider-specific cancel handle access
raw provider payload parsing
runtime checkout path dependency
CWD or sys.path workaround
```

### 3.2 Provider-neutral

provider差分はFramework内部に閉じ込める。

公開境界では以下のみを返す。

```text
typed capability
typed lifecycle event
typed stage result
typed failure
safe diagnostics
```

### 3.3 Truthful capability

未対応機能を成功扱いしない。

```text
cooperative cancellation
provider hard cancellation
pending queue clear
active synthesis cancellation
audio artifact invalidation
host playback stop
motion cancellation
```

これらは独立したcapabilityおよびresultとして表現する。

### 3.4 Exactly-once terminal semantics

各turnは、公開event上で正確に一つのterminal stateへ到達する。

候補terminal state：

```text
completed
interrupted
cancelled
failed
rejected
closed
```

同じturnについて複数のterminal eventを発行してはならない。

### 3.5 Stale-safe by default

interrupt、reset、new turn、close後に返った旧結果は、current turnへ流してはならない。

Frameworkは次を使用してstale resultを判定する。

```text
session_id
turn_id
generation
sequence
```

---

## 4. P0 release requirements

P0はv6.0.0 releaseに必須とする。

## P0-1. Unified Realtime Session

Frameworkは、一つのsession identityのもとでrealtime stagesを扱う。

必須public concepts：

```text
RealtimeSession
RealtimeSessionInfo
RealtimeTurn
RealtimeTurnResult
RealtimeCapabilitySnapshot
```

必須保証：

```text
stable session_id
stable turn_id
single active turn per session
explicit turn start
typed active-turn rejection
close後操作のtyped rejection
interrupt後のsession reuse条件
capability不足時のtyped rejection
```

初期concurrency policy：

```text
single active turn per session
new turn while active:
REJECTED

automatic previous-turn replacement:
False

required replacement sequence:
interrupt -> terminal -> new turn
```

---

## P0-2. Typed Lifecycle Events

各eventは最低限以下を持つ。

```text
session_id
turn_id
event_type
sequence
generation
typed payload
terminal flag
```

必要に応じて以下を追加する。

```text
timestamp
monotonic timestamp
error code
recoverability
cancel reason
capability source
drop reason
```

必須event categories：

```text
session started / closed
turn started / completed / interrupted / failed / rejected

listening started / completed
speech started / ended
transcript partial / final

response started / delta / completed

synthesis started / completed
audio available / invalidated

motion requested / completed / failed

interrupt requested / completed
stale result dropped
event overflow
```

event orderingはsession単位のmonotonic sequenceで判定可能にする。

---

## P0-3. Terminal Registry

Frameworkはsession内部にturn terminal registryを所有する。

必須動作：

```text
first terminal result:
accepted

duplicate terminal result:
suppressed

late non-terminal event:
dropped

state regression:
prohibited

drop:
typed diagnosticを記録
```

terminal registryはprovider callback、future、thread、async taskの完了順序に依存せず、決定的に動作しなければならない。

---

## P0-4. Interrupt Coordinator

`interrupt()`は単一booleanではなく、subsystem別の到達結果を返す。

必須結果surface：

```text
turn status
LLM generation status
TTS generation status
TTS pending status
audio invalidation status
motion status
session recovery status
```

各subsystem resultは最低限以下を区別する。

```text
requested
completed
not_active
already_terminal
unsupported
timed_out
failed
```

以下は別項目として表現する。

```text
cooperative cancel requested
cooperative cancel completed
provider hard cancel applied
provider hard cancel unsupported
```

duplicate interruptは安全かつ決定的でなければならない。

---

## P0-5. TTS Work Control

Frameworkが所有するvoice output workについて、次を公開制御できるようにする。

```text
generation start
generation active
pending work
pending clear
generation cancel
artifact invalidation
future delivery suppression
completion
failure
```

必須区別：

```text
pending request cleared
active synthesis cancel requested
active synthesis cancelled
provider hard cancel applied
provider hard cancel unsupported
completed artifact invalidated
future delivery suppressed
nothing active
```

pending queueをclearしただけの場合、active synthesis cancellation成功としてはならない。

### Host playback boundary

端末上のaudio playbackはhost application責務である。

Frameworkは以下を通知できる。

```text
active_audio_invalidated
playback_stop_requested_to_host
```

Frameworkは、host-owned playerの物理的停止完了を自身の成功として報告してはならない。

---

## P0-6. Stale Result Rejection

Frameworkは以下を自動的に拒否する。

```text
old-turn response delta
old-generation TTS result
interrupt後のlate synthesis result
reset前session generation result
close後のprovider completion
duplicate terminal callback
```

拒否はsilent corruptionにしてはならない。

public-safe diagnosticsとして以下を取得可能にする。

```text
stale result count
drop category
session_id
turn_id
generation
stage
```

transcript本文、raw payload、private pathはdiagnosticsに含めない。

---

## P0-7. Truthful Capability Snapshot

capabilityはsession-scoped snapshotとして返す。

### Text generation

```text
configured
runtime_available
streaming_supported
cooperative_cancel_supported
provider_hard_cancel_supported
```

### Voice input

```text
configured
runtime_available
audio_chunk_input_supported
partial_transcript_supported
final_transcript_supported
input_abort_supported
backpressure_supported
accepted_audio_formats
maximum_chunk_size
maximum_duration
```

### Voice output

```text
configured
runtime_available
streaming_audio_supported
generation_cancel_supported
provider_hard_cancel_supported
pending_flush_supported
active_audio_invalidation_supported
audio_formats
maximum_text_size
```

### Motion

```text
configured
runtime_available
request_cancel_supported
completion_event_supported
provider_neutral_intent_supported
```

共通項目：

```text
fake_runtime
real_runtime
unavailable_reason
snapshot_scope
snapshot_generation
```

---

## P0-8. Recovery / Reset / Close

失敗またはinterrupt後のsession状態をtyped resultで表現する。

```text
reusable
turn_reset_required
session_reset_required
reconnect_required
close_required
permanently_failed
```

必須保証：

```text
reset対象がturnかsessionか明確
reset後はold generationを拒否
closeはidempotent
close後は新eventをactive eventとして配信しない
close後操作はtyped rejection
```

---

## P0-9. Deterministic Fake Runtime

real providerなしで、すべてのP0 contractを検証可能にする。

fake runtimeで再現するケース：

```text
normal completion
partial transcript
response delta
TTS generation
audio available
user interrupt
duplicate interrupt
late response
late audio
stale generation
pending flush
unsupported active cancel
provider hard cancel unsupported
motion failure
session reset
session close
close後操作
```

テスト制御：

```text
artificial delay
stage pause / resume
late callback injection
cancel race injection
terminal duplication injection
queue overflow injection
```

network、provider、microphone、playbackを使用せずに完結すること。

---

## 5. P1 release candidates

P1はP0完成後に個別authorizationする。

未完成でもP0 releaseを妨げない。

## P1-1. Public Voice Input Streaming

host applicationが取得したaudio chunkをstable public APIへ送信できるようにする。

```text
ordered audio chunks
end-of-input
input abort
partial transcript
final transcript
format validation
chunk limits
duration limits
```

Frameworkはマイクデバイスを直接所有しなくてよい。

---

## P1-2. Backpressure / Flow Control

対象：

```text
audio input
response delta
audio output
event subscriber
```

候補contract：

```text
bounded queue
accepted / rejected result
retryable backpressure
maximum in-flight count
pause / resume
explicit drop policy
overflow event
```

silent dropは禁止する。

---

## P1-3. Motion Lifecycle Integration

conversation lifecycleからprovider-neutral motion intentへ接続できるextension pointを追加する。

候補phase：

```text
listening
thinking
speaking
interrupted
completed
failed
```

Frameworkが所有する範囲：

```text
provider-neutral intent
request identity
adapter routing
completion / failure
cancellation capability
```

character固有演出やproduct policyをFramework coreへ固定しない。

---

## 6. Experimental / follow-up scope

元々のfuture major候補であった以下は、v6.0.0 core acceptanceとは分離する。

```text
microphone listening while speaking
VAD-based automatic barge-in
wake word
background input monitoring
automatic next-turn capture
echo cancellation
noise suppression
```

これらはv6.0.0のP0 runtimeを土台として、以下のいずれかで扱う。

```text
v6.0 experimental extension
v6.1.0
later v6.x release
```

常時マイクやbackground microphoneを、統一session contract完成前に導入してはならない。

---

## 7. Explicit non-goals

```text
Flutter UI
Android / iOS permission UI
microphone device implementation
platform-specific audio player
application persistence
application-specific prompt
emotion inference algorithm
automatic emotion-to-motion policy
production hosting
store distribution
provider-specific public client
raw provider payload exposure
credential exposure
```

---

## 8. Compatibility policy

既存v5 root-public APIsは可能な限り維持する。

```text
create_text_chat_session
create_voice_input_session
create_voice_output_session
create_realtime_session
create_motion_session
```

既存sessionはv6 runtimeへのadapterとして維持できる。

```text
v5 standalone session APIs:
compatibility facade

v6 RealtimeSession:
unified orchestration owner
```

既存propertyはsummary compatibility fieldとして残し、新しい詳細capabilityを追加する。

破壊的変更が必要な場合は、release notesとmigration guideへ明記する。

---

## 9. Security / privacy

以下をevent、result、exception、diagnostics、release packageへ含めない。

```text
credential values
authorization headers
token values or paths
private configuration
private selector values
private model identity
private hotkey names or IDs
raw provider requests
raw provider responses
raw exceptions
raw audio
transcript本文の無断記録
private file paths
endpoint values
LAN IP
operator evidence
screenshots
```

通常import、fake runtime、closed guard、capability inspectionではprovider executionを発生させない。

---

## 10. Workstream split

### FW-RT6-0a — Roadmap and gap inventory

```text
docs/test only
current public surface inventory
v5.5.0 gap classification
P0 / P1 / experimental scope lock
runtime unchanged
```

### FW-RT6-0b — Public identity and capability models

```text
session identity
turn identity
generation identity
capability snapshot
recovery result
root-public exports
```

### FW-RT6-0c — Event sequence and terminal semantics

```text
monotonic sequence
typed payload
terminal flag
terminal registry
duplicate suppression
event history / diagnostics
```

### FW-RT6-0d — Deterministic fake runtime

```text
stage controller
delay injection
late-result injection
cancel races
terminal duplication
network-free conformance tests
```

### FW-RT6-0e — Unified turn lifecycle

```text
single active turn
stage orchestration
turn start / complete / fail
typed rejection
reset / close
```

### FW-RT6-0f — Interrupt coordinator

```text
whole-turn interrupt
subsystem reach result
cooperative cancellation
hard-cancel capability reporting
duplicate interrupt
session reuse result
```

### FW-RT6-0g — TTS work control

```text
pending queue
active generation
pending clear
generation cancel
artifact invalidation
late-audio suppression
host playback boundary
```

### FW-RT6-0h — Stale-result enforcement

```text
generation invalidation
late event rejection
terminal regression prevention
drop diagnostics
race gates
```

### FW-RT6-0i — Voice-input streaming and backpressure

```text
P1 authorization required
audio chunk input
partial transcript
input abort
flow control
```

### FW-RT6-0j — Motion lifecycle extension

```text
P1 authorization required
phase extension hooks
request identity
completion / failure
cancel capability
```

### FW-RT6-0k — Guarded real-runtime composition

```text
real STT
real LLM streaming
real TTS
real motion

explicit provider execution guards
operator-safe verification
no private evidence committed
```

### FW-RT6-0l — Aggregate acceptance and release

```text
dedicated gates
full test suite
documentation
migration guide
deterministic package
private artifact rejection
tag
push
GitHub Release
asset redownload verification
```

各checkpointは独立したexact contract reviewとauthorizationを必要とする。

前checkpointのacceptanceは次checkpointの自動認可を意味しない。

---

## 11. v6.0.0 acceptance conditions

### Public surface

```text
root-public usage only
documented models
documented lifecycle
documented capability
no provider-client exposure
```

### Session / turn

```text
stable session_id
stable turn_id
stable generation
single active turn policy
exactly-once terminal
close後 rejection
```

### Events

```text
typed event
monotonic sequence
partial / final distinction
terminal distinction
stale rejection
duplicate suppression
```

### Interrupt

```text
whole-turn public interrupt
subsystem reach result
truthful hard-cancel result
duplicate safety
late-result suppression
typed recovery state
```

### TTS

```text
pending clear semantics
active cancel semantics
artifact invalidation
late-audio suppression
host playback boundary
```

### Test

```text
fake-only contract suite:
PASS

race / stale / duplicate suite:
PASS

full Framework suite:
PASS

root-public import safety:
PASS

provider execution during fake tests:
False
```

### Package / release

```text
deterministic package:
PASS

exact committed membership:
PASS

private artifacts:
ABSENT

release documentation:
SYNCED

tag:
CREATED / PUSHED

GitHub Release:
PUBLISHED

official assets:
REDOWNLOADED / VERIFIED

working tree:
CLEAN
```

---

## 12. Release decision

```text
v5.5.0:
CLOSED / COMPLETE

v5.6.0 output-control-only proposal:
SUPERSEDED

Next Framework milestone:
v6.0.0

Theme:
Unified Realtime Character Runtime

Workstream:
FW-RT6

FW-RT6-0a:
READY_FOR_EXACT_CONTRACT_REVIEW

Implementation:
NOT_AUTHORIZED

Commit / push:
NOT_AUTHORIZED
```


---

## FW-RT6-0a source-review checkpoint

```text
checkpoint: FW-RT6-0a
baseline head: f56697b6de066b062794ac7bb01330d2d9e91759
status: IMPLEMENTED / AWAITING_REVIEW
source inventory: RECORDED
v6.0.0 roadmap: RECORDED
v6.0.0 tasklist: RECORDED
runtime Python changed: False
provider execution: False
network execution: False
microphone use: False
audio playback: False
DRC repository accessed or changed: False
next implementation checkpoint: FW-RT6-0b
FW-RT6-0b implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

This checkpoint records the planning baseline only. It does not implement the
unified runtime, change public runtime behavior, execute a provider, access an
application repository, create a release package, tag, push, or publish.
