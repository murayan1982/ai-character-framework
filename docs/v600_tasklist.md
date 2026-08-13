# AI Character Framework v6.0.0 Task List — Draft

## Unified Realtime Character Runtime

## 0. 文書情報

```text
Document:
AI Character Framework v6.0.0 Task List

Baseline release:
v5.5.0

Baseline commit supplied by operator:
f56697b6de066b062794ac7bb01330d2d9e91759

Reviewed source bundle:
ai-character-framework.zip

Bundle SHA-256:
13a618f80e3ae81308816e65ab590ca464faaf1dcd596be32a8b871501693179

Status:
IMPLEMENTED_AS_FW-RT6-0a_PLANNING_BASELINE / AWAITING_REVIEW

Implementation:
NOT_AUTHORIZED

Commit / push:
NOT_AUTHORIZED

Scope:
AI Character Framework only

Daily Rhythm Companion:
OUT OF SCOPE
```

このタスクリストは、添付された現行ソースを読んだ結果と、v6.0.0 roadmapの要求を対応付けたもの。

添付bundleには`.git`がなく、release ZIP、`.release_build`、過去のapply helper、`README_FOR_THIS_BUNDLE.md`、root直下の`v6.0.0_roadmap.md`などが含まれる。そのため、**正確なtracked file membershipとworking tree状態はbundle単独では確定しない**。最初のcheckpointでは、実repositoryの`git status`と`git ls-files`をsource of truthとして再固定する。

---

# 1. 現行ソース確認結果

## 1.1 構造

```text
public SDK:
framework/**

legacy/runtime-oriented implementation:
core/**
llm/**
stt/**
tts/**
live2d/**
plugins/**

contract/release verification:
scripts/smoke_*.py
scripts/check_*.py

normal unit-test directory:
tests/ is present but empty
```

確認した主な規模:

```text
framework Python files:
26

scripts Python files:
110

docs Markdown files:
97
```

## 1.2 実行確認

```text
python -m compileall -q framework core llm stt tts scripts:
PASS

scripts/smoke_app_sdk.py:
PASS

v5.2 realtime lifecycle types:
PASS

v5.2 realtime session skeleton:
PASS

v5.2 interrupt/output-control types:
PASS

v5.2 realtime interrupt/output wiring:
PASS

v5.2 realtime public conformance:
PASS

v5.3 VoiceInputSession adapter wiring:
PASS

v5.4 OpenAI real-provider runtime smoke:
PASS

v5.5 MotionSession real-adapter composition smoke:
PASS
```

ただし以下はFAIL。

```text
scripts/smoke_public_facade.py:
FAIL

reason:
EXPECTED_PUBLIC_APIがv4/v5初期surfaceのままで、
現在のframework.__all__と同期していない
```

## 1.3 重要なコードギャップ

### G-01 — RealtimeSessionはskeleton

`framework/realtime_session.py`は、mock eventを順に発行するだけで、real STT / LLM / TTS / motionをcompositionしない。

### G-02 — session identityが分断

- `RealtimeSession`と`MotionSession`にはsession IDがある。
- `TextChatSession`、`VoiceInputSession`、`VoiceOutputSession`には統一されたsession/turn/generation identityがない。
- stage resultを同じturnへ安全に関連付ける共通型がない。

### G-03 — event contractが分断

- `RealtimeEvent`はtypedだが`sequence`、`generation`、typed payload、terminal flagがない。
- `TextChatSession`は独自event class。
- `VoiceInputSession`と`MotionSession`はmapping callback。
- subscriber例外、遅延、overflowの統一policyがない。

### G-04 — exactly-once terminal enforcementがない

`RealtimeTurnResult.is_terminal`は存在するが、turnごとのterminal registry、duplicate suppression、state regression preventionはない。

### G-05 — stale result rejectionがない

Realtime runtimeにはgeneration gateがない。

一方、VTube Studio transport/compositionには以下の先行実装がある。

```text
lifecycle generation
close後のlate completion suppression
persistent async bridge
single-flight enforcement
```

v6ではこの考え方をprovider-neutral primitiveへ抽出できる。

### G-06 — capability情報が古く分散

`framework/capabilities.py`はschema `v5.1.capabilities`のままで、voice input / realtime / motionを未実装として返す。

個別session capabilityとglobal capabilityが一致しない。

### G-07 — VoiceInputSessionとreal STT実装が未統合

- `VoiceInputSession` docstringとpreflightはreal STT未実装扱い。
- real OpenAI STT executorは別moduleに存在。
- public sessionはdefault fake adapterで、real pathはhost側adapter injectionへ依存する。
- provider-neutral factory compositionが未完成。

### G-08 — Text generation cancel protocolがない

`BaseLLM.ask_stream()`は同期generatorのみ。

```text
cancel handle:
none

cooperative cancel protocol:
none

provider hard-cancel capability:
none

stream close result:
none
```

`TextChatSession.interrupt()`はflagを立て、次chunk境界でyieldを止めるだけ。

### G-09 — Voice output generationとqueue/playbackが分離

- `framework/audio/voice_output.py`はper-request artifact生成。
- `tts/voice_engine.py`はElevenLabs、queue、ffplay、local temp fileを一つのclassで所有。
- RealtimeSessionから制御できるprovider-neutral work queueがない。

### G-10 — Voice artifact contractに実装ずれ

`VoiceArtifactRef`はlocal pathを拒否するが、real voice-output adapterは生成file pathを`str`として`audio_artifact_ref`へ返す。

v6ではopaque artifact store/resolverが必須。

### G-11 — VoiceOutputSessionに重複overrideが蓄積

`VoiceOutputSession`内で`close`、`is_closed`、`create_output`、`speak`が複数回定義されている。

互換patchを整理し、一つの明確なlifecycle実装へ統合する必要がある。

### G-12 — public errorでraw exceptionが露出し得る

`TextChatSession.ask_stream()`のerror eventは`str(exc)`とprovider exception typeを公開event dataへ入れる。

v6 security/privacy contractではsafe error normalizationへ置換が必要。

### G-13 — metadata redactionが重複かつshallow

`_public_mapping` / `_redact_mapping`が複数moduleに重複する。

nested mapping/list/object内のsecret-like keyを再帰的にredactしない。

### G-14 — installable SDK/resource rootが未完成

- `pyproject.toml` / setup metadataがない。
- smoke scriptが`sys.path`へrepository rootを挿入する。
- preset/character/temp/outputの解決にCWD相対pathが残る。

v6 root-public contractの前提として通常install可能なpackage構成が必要。

### G-15 — legacy runtimeとpublic SDKが並存

`core.pipeline`には実LLM streaming、TTS queue、interrupt flag、emotion eventがあるが、`framework.RealtimeSession`とは接続されていない。

v6ではlegacy runtimeを直接public化せず、再利用可能なstage adapterへ分解する。

### G-16 — test architectureがsmokeへ偏重

`tests/`は空で、releaseごとのsmoke scriptへ検証が集中している。

race、duplicate terminal、late result、fake clockなどはunit test層が必要。

### G-17 — version情報が分散

```text
TextChatSessionInfo.api_version:
4.0

VoiceInputSessionInfo.api_version:
5.2.0

RealtimeSessionInfo.api_version:
5.2.0

MotionSessionInfo.api_version:
5.5.0

VoiceOutputSessionInfo.boundary_version:
v5.lazy_provider_adapter

FrameworkCapabilities.schema_version:
v5.1.capabilities
```

v6ではpackage version、public schema version、compatibility versionを分離して中央管理する。

---

# 2. 実装順序

```text
Phase 0:
source truth / contract / baseline hygiene

Phase 1:
public identity, event, capability, result models

Phase 2:
runtime safety primitives

Phase 3:
deterministic fake runtime

Phase 4:
unified session and turn lifecycle

Phase 5:
text generation control

Phase 6:
voice output work control

Phase 7:
voice input composition

Phase 8:
motion lifecycle composition

Phase 9:
interrupt coordinator and stale enforcement

Phase 10:
recovery, diagnostics, security hardening

Phase 11:
backward compatibility and SDK migration

Phase 12:
P1 streaming / backpressure extensions

Phase 13:
guarded real-runtime integration acceptance

Phase 14:
aggregate release
```

---

# 3. Task list

## FW-RT6-0a — Exact source inventory and tasklist lock

**Purpose:** 実repositoryのtracked sourceとv6 scopeを固定する。runtimeは変更しない。

**Dependencies:** v5.5.0 complete.

**Candidate exact surface:**

```text
README.md
docs/roadmap_feature_v6.0.0.md
docs/v600_current_source_gap_inventory.md
docs/v600_tasklist.md
scripts/smoke_v600_current_source_gap_inventory.py
scripts/check_v600_tasklist_contract.py
```

**Tasks:**

- [ ] 実repositoryでHEAD / origin/main / clean treeを再確認する。
- [ ] `git ls-files`からtracked source inventoryを作る。
- [ ] bundle内のignored/untracked helperとtracked sourceを区別する。
- [ ] rootの`v6.0.0_roadmap.md`がtrackedか確認する。
- [ ] roadmapを正式docs pathへ固定する。
- [ ] G-01〜G-17をdocsへ記録する。
- [ ] P0 / P1 / experimentalを固定する。
- [ ] 各後続checkpointが自動認可されないことを明記する。
- [ ] runtime Python fileが変わっていないことをgateで確認する。

**Acceptance:**

```text
source baseline fixed:
True

tracked membership known:
True

roadmap path fixed:
True

task dependencies fixed:
True

runtime changed:
False

network/provider/microphone/playback:
False

DRC repository accessed:
False
```

**Status:**

```text
READY_FOR_EXACT_CONTRACT_REVIEW
NOT_AUTHORIZED
```

---

## FW-RT6-0b — Public SDK baseline hygiene

**Purpose:** v6 runtime着手前に、現行public surfaceとverificationの不整合を解消する。

**Source reasons:** G-11, G-14, G-16, G-17.

**Tasks:**

- [x] `scripts/smoke_public_facade.py`の期待surfaceをversion-awareに修正する。
- [x] `framework.__all__`の生成方式を一箇所へ統合する。
- [x] provider-specific lazy root exportsの維持/deprecation方針を決める。
- [x] `VoiceOutputSession`の重複method定義を一つに統合する。
- [x] `info` property/method、`close`、`dispose`、context managerの命名を整合させる。
- [x] package versionとpublic schema versionの中央定義を追加する。
- [x] full public facade smokeをcurrent sourceでPASSさせる。
- [x] v5 compatibility testsを追加する。

**Likely files:**

```text
framework/__init__.py
framework/version.py
framework/audio/voice_output.py
scripts/smoke_public_facade.py
scripts/smoke_app_sdk.py
docs/public_facade.md
docs/app_integration_contract.md
```

**Acceptance:**

```text
compileall:
PASS

smoke_public_facade:
PASS

smoke_app_sdk:
PASS

duplicate VoiceOutputSession methods:
False

root import provider-safe:
True

v5 public compatibility:
PASS
```

---

## FW-RT6-0c — Installable SDK and resource resolution

**Purpose:** checkout/CWD依存をpublic runtimeから除去する。

**Source reasons:** G-14.

**Tasks:**

- [x] `pyproject.toml`を追加する。
- [x] package name/version/dependency groupsを定義する。
- [x] provider SDKをoptional dependencyへ分離できるか検討する。
- [x] preset/character resource resolverを追加する。
- [x] `Path("presets")`、`Path("characters")`をresource-root基準へ置換する。
- [x] artifact/output default pathをCWDから切り離す。
- [x] explicit `project_root` overrideはcompatibilityとして維持する。
- [x] temporary directoryからinstalled packageをimportしてsmokeを実行する。
- [x] `sys.path` mutationなしのpackage-import gateを追加する。

**Acceptance:**

```text
editable install:
PASS

wheel install:
PASS

import outside checkout:
PASS

preset/resource lookup outside CWD:
PASS

sys.path mutation required:
False

temporary CWD change required:
False
```

<!-- FW-RT6-0c-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-0c Control D
baseline head: cf9949579d971de68b2b763928f1c8052cf49921
status: IMPLEMENTED / AWAITING_REVIEW
Control A package metadata: ACCEPTED
Control B resource resolution: ACCEPTED
Control C isolated installation: ACCEPTED
Control D exact change surface: 4 files
editable install: PASS
wheel install: PASS
import outside checkout: PASS
preset/resource lookup outside CWD: PASS
sys.path mutation required: False
temporary CWD change required: False
canonical root-public names: 95
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-1a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-0c-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-1a — Common public identity types

**Purpose:** session/turn/generation/event identityを全stageで共有する。

**Tasks:**

- [x] `SessionId`相当のopaque public typeを定義する。
- [x] `TurnId`相当を定義する。
- [x] `GenerationId`相当を定義する。
- [x] `EventSequence`相当を定義する。
- [x] ID生成/validation/serialization contractを定義する。
- [x] private/provider IDと混同しないことを明記する。
- [x] Text/VoiceInput/VoiceOutput/Motion resultへcorrelation contextを追加する方針を固定する。

**Acceptance:**

```text
stable session identity:
True

stable turn identity:
True

stable generation identity primitive:
True

EventSequence primitive:
True

provider identifier exposed:
False

root-public import:
PASS

root-public count:
99

all-stage runtime correlation wiring:
False / DEFERRED
```


<!-- FW-RT6-1a-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-1a Control D
baseline head: 9d955955d4462006ed8aacc8e4c6e43ae487fb35
status: IMPLEMENTED / AWAITING_REVIEW
Control A public identity primitives: ACCEPTED
Control B Realtime identity adoption: ACCEPTED
Control C Motion identity adoption: ACCEPTED
Control D exact change surface: 4 files
legacy root-public prefix: 95 names / SAME ORDER
canonical root-public total: 99
Framework-generated Realtime session/turn identities: TYPED
Framework-generated Motion session identity: TYPED
provider identifier exposed/promoted: False
all-stage runtime result correlation: DEFERRED
RealtimeEvent sequence/generation: DEFERRED / FW-RT6-1c
phase/outcome/recovery models: DEFERRED / FW-RT6-1b
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-1b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1a-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-1b — Unified phase, terminal, recovery models

**Purpose:** session phase、turn outcome、recovery actionを分離する。

**Tasks:**

- [x] transient phase enumを定義する。
- [x] terminal outcome enumを定義する。
- [x] `rejected`、`cancelled`、`interrupted`の意味を固定する。
- [x] `RecoveryAction`を定義する。
- [x] session stateとturn resultの混用を廃止する。
- [x] state transition matrixをdocs/testへ固定する。

**Acceptance:**

```text
transient phase vs terminal outcome:
separate

invalid transition:
typed failure

terminal state regression:
prohibited

root-public count:
104

legacy RealtimeState compatibility:
preserved

exactly-once terminal registry:
False / DEFERRED
```

<!-- FW-RT6-1b-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-1b Control D
baseline head: 8bc71a990762c8161d262bc7617a44e0dfb2c8e3
status: IMPLEMENTED / AWAITING_REVIEW
Control A lifecycle primitives: ACCEPTED
history baseline corrective: ACCEPTED
Control B turn outcome/recovery adoption: ACCEPTED
Control C RealtimeSession phase adoption: ACCEPTED
Control D exact change surface: 4 files
legacy root-public prefix: 99 names / SAME ORDER
canonical root-public total: 104
RealtimeTurnResult canonical outcome: TurnOutcome
RealtimeTurnResult recovery_action: RecoveryAction
RealtimeSession canonical phase: RealtimePhase | None
legacy RealtimeState compatibility: PRESERVED
invalid transition: TYPED FAILURE
terminal state regression validation: ACCEPTED
per-session terminal registry: DEFERRED
exactly-once terminal enforcement: DEFERRED
RealtimeEvent v6 fields: DEFERRED / FW-RT6-1c
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-1c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1b-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-1c — Typed event model v6

**Purpose:** 全stage eventを一つのordered public contractへ統合する。

**Tasks:**

- [x] `RealtimeEvent`へsequenceを追加する。
- [x] generationを追加する。
- [x] terminal flagを追加する。
- [x] timestamp/monotonic timestamp方針を決める。
- [x] generic `public_metadata`だけに依存しないtyped payload unionを定義する。
- [x] transcript partial/finalを分離する。
- [x] response started/delta/completedを分離する。
- [x] synthesis/audio available/audio invalidatedを定義する。
- [x] stale dropped/event overflowを定義する。
- [x] v5 event mapping adapterを用意する。

**Acceptance:**

```text
session ordering observable:
True

turn ordering observable:
True

partial/final distinction:
True

terminal event identifiable:
True

typed payload:
True

root-public count:
114

legacy root-public prefix:
104 names / SAME ORDER

canonical completed-turn events:
9

legacy projected completed-turn events:
8

terminal registry / exactly-once enforcement:
False / DEFERRED
```

<!-- FW-RT6-1c-E-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-1c Control E
baseline head: 80e5c550bbb994bc8dfc3340340691c881f0449d
status: IMPLEMENTED / AWAITING_REVIEW
Control A typed payload models: ACCEPTED
encoding-corrupt corrective: SUPERSEDED / PRESERVED IN HISTORY
encoding repair: ACCEPTED
Control B RealtimeEvent v6 envelope: ACCEPTED
Control C explicit v5 adapter: ACCEPTED
Control D ordered RealtimeSession adoption: ACCEPTED
Control E exact change surface: 4 files
legacy root-public prefix: 104 names / SAME ORDER
canonical root-public total: 114
canonical completed-turn events: 9
legacy projected completed-turn events: 8
EventSequence starts at 1: True
EventSequence resets between turns: False
GenerationId changes per admitted turn: True
session-only generation: None
rejected-before-admission generation: None
typed payload by canonical runtime category: ACCEPTED
automatic public timestamps: ACCEPTED
authoritative ordering: EventSequence
terminal registry / duplicate suppression: DEFERRED
automatic stale-result rejection: DEFERRED
bounded event queue / overflow runtime: DEFERRED
provider partial transcript / response delta callbacks: DEFERRED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-1d
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1c-E-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-1d — Detailed capability snapshot

**Purpose:** global/session/stage capabilityをtruthfulに統合する。

**Source reasons:** G-06, G-07, G-17.

**Tasks:**

- [x] `FrameworkCapabilities`のv5.1固定実装を置換する。
- [x] session-scoped `RealtimeCapabilitySnapshot`を追加する。
- [x] text generation capabilityを定義する。
- [x] voice input capabilityを定義する。
- [x] voice output capabilityを定義する。
- [x] motion capabilityを定義する。
- [x] configured/runtime_available/guardedを分離する。
- [x] fake runtime/real runtimeを分離する。
- [x] cooperative cancel/provider hard cancelを分離する。
- [x] snapshot generation/scopeを追加する。
- [x] v5 summary booleanをcompatibility fieldとして維持する。

**Acceptance:**

```text
voice input current status accurate:
True

realtime current status accurate:
True

motion current status accurate:
True

unsupported overclaim:
False
```

---

## FW-RT6-1e — Interrupt and output-control result expansion

**Purpose:** aggregate booleanではなくsubsystem reachを表現する。

**Tasks:**

- [ ] stage control outcome enumを定義する。
- [ ] LLM cancel reachを定義する。
- [ ] TTS generation cancel reachを定義する。
- [ ] pending queue clear reachを定義する。
- [ ] audio invalidation reachを定義する。
- [ ] motion cancel/clear reachを定義する。
- [ ] provider hard cancelを独立fieldにする。
- [ ] session reuse/recovery resultを追加する。
- [ ] partial completion aggregate outcomeを定義する。
- [ ] duplicate interrupt resultを定義する。

**Acceptance:**

```text
pending clear != active cancel:
True

cooperative cancel != hard cancel:
True

host playback stop claimed by FW:
False

partial completion observable:
True
```


<!-- FW-RT6-1d-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-1d Control D
baseline head: 753748d463f800647b251c788d217a5c5adc4049
status: IMPLEMENTED / AWAITING_REVIEW
Control A detailed capability models: ACCEPTED
Control B truthful global aggregation: ACCEPTED
Control C session-scoped snapshot adoption: ACCEPTED
Control D exact change surface: 6 files
root-public names: 121 / UNCHANGED
v5 compatibility schema: v5.1.capabilities / PRESERVED
detailed schema: v6.realtime_capabilities
global detailed snapshot: ACCEPTED
session-scoped snapshot: ACCEPTED
snapshot scope / generation: ACCEPTED
configured / runtime_available / guarded separation: ACCEPTED
fake runtime / real runtime separation: ACCEPTED
cooperative cancel / provider hard cancel separation: ACCEPTED
voice input current status accurate: True
realtime current status accurate: True
motion current status accurate: True
unsupported overclaim: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1d-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-2a — Recursive public-safe metadata utility

**Purpose:** redaction実装を統合し、nested data leakを防ぐ。

**Source reasons:** G-12, G-13.

**Tasks:**

- [x] common redaction moduleを追加する。
- [x] mapping/list/tuple/dataclassのrecursive sanitizationを実装する。
- [x] secret-like key policyを一箇所へ固定する。
- [x] raw exception object/stringのpublic metadata投入を禁止する。
- [x] safe error classification helperを追加する。
- [x]既存 `_public_mapping` / `_redact_mapping`を段階的に置換する。
- [x] nested secret testを追加する。

**Acceptance:**

```text
nested credential redaction:
PASS

raw exception exposed:
False

private path exposed:
False
```

<!-- FW-RT6-2a-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-2a Control D
baseline head: 888d689fcf894fa7fa83eb6d0daa18b41f77726a
status: IMPLEMENTED / AWAITING_REVIEW
Control A recursive public-safety primitives: ACCEPTED
Control B core metadata consumer migration: ACCEPTED
Control C TextChat public error safety: ACCEPTED
Control D exact change surface: 6 files
root-public names: 121 / UNCHANGED
recursive mapping/list/tuple/dataclass sanitization: PASS
secret-like key policy centralized: True
core compatibility helpers delegated: 5
nested credential redaction: PASS
raw exception exposed: False
private path exposed: False
TextChat raw exception string exposed: False
TextChat exception class name exposed: False
ask_stream exception re-raise preserved: True
all repository metadata paths claimed migrated: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2a-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-2b — Event sequencer and subscriber hub

**Purpose:** ordered event emissionとsubscriber safetyを実装する。

**Tasks:**

- [x] per-session monotonic sequence generatorを追加する。
- [x] callback registration/unregistration tokenを追加する。
- [x] callback exceptionをruntime failureから隔離する。
- [x] bounded event historyを追加する。
- [x] slow subscriber policyを固定する。
- [x] overflow event/diagnosticsを追加する。
- [x] concurrent emission lockを追加する。
- [x] close後event rejectionを実装する。

**Acceptance:**

```text
sequence monotonic:
PASS

callback exception breaks turn:
False

silent overflow:
False

close後active event:
False
```

<!-- FW-RT6-2b-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-2b Control D
baseline head: d12e562a0c0b0111386776d50286b1a4cbdf54d2
status: IMPLEMENTED / AWAITING_REVIEW
Control A event-hub primitives: ACCEPTED
Control B RealtimeSession hub adoption: ACCEPTED
Control C close/concurrent-operation hardening: ACCEPTED
Control D exact change surface: 6 files
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeSession factory signature changed: False
session-local sequence monotonic: PASS
callback registration/unregistration token: ACCEPTED
callback exception breaks turn: False
bounded event history: ACCEPTED / LIMIT 64
slow subscriber policy: SYNCHRONOUS SERIALIZED / RETAIN AND ACCOUNT
silent overflow: False
typed EVENT_OVERFLOW: ACCEPTED
overflow v5 projection: None
concurrent/reentrant event emission: SERIALIZED
operation-level lock: RLock
concurrent operation event groups interleave: False
reentrant close deferred: True
SESSION_CLOSED emitted once: True
event hub sealed after close: True
close後active event: False
asynchronous subscriber queue: NOT CLAIMED
terminal registry / exactly-once enforcement: DEFERRED / FW-RT6-2c
generation stale-result rejection: DEFERRED / FW-RT6-2d
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2b-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-2c — Terminal registry

**Purpose:** exactly-once terminal semanticsを実装する。

**Tasks:**

- [x] turn terminal registryを追加する。
- [x] first terminal commitをatomicにする。
- [x] duplicate terminalを抑止する。
- [x] late non-terminal eventを拒否する。
- [x] terminal reason/resultを保持する。
- [x] stale/duplicate diagnostic counterを追加する。
- [x] multi-thread race testを追加する。

**Acceptance:**

```text
one terminal event per turn:
PASS

duplicate terminal suppressed:
PASS

state regression:
PASS (rejected)

race deterministic:
PASS
```

<!-- FW-RT6-2c-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-2c Control D
baseline head: 8393c82a312af73f0b18db106b6e32c959f251a2
status: IMPLEMENTED / AWAITING_REVIEW
Control A terminal registry primitives: ACCEPTED
Control B RealtimeSession registry adoption: ACCEPTED
Control C reentrant/concurrent terminal hardening: ACCEPTED
Control D exact change surface: 6 files
runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeTurnResult public model changed: False
RealtimeSession factory signature changed: False
event_diagnostics keys changed: False
terminal_results: READ-ONLY / COMMIT ORDER
terminal_diagnostics: IMMUTABLE / COUNT-ONLY
terminal registry primitive supports terminal outcomes: True
current verified RealtimeSession first-terminal path: TURN_COMPLETED
all provider-driven terminal paths wired: False / NOT CLAIMED
first terminal commit atomic: PASS
one terminal event per current completed turn: PASS
duplicate terminal suppression: PASS
terminal regression rejection: PASS
late non-terminal rejected before mutation: PASS
terminal reason/result retained: PASS
same-turn concurrent lifecycle groups: 1
same-turn terminal events: 1
same-turn terminal records: 1
first committed result identity preserved: True
terminal callback late events: 0
different-turn operation groups serialized: PASS
close contract preserved: PASS
generation stale-result rejection: DEFERRED / FW-RT6-2d
STALE_RESULT_DROPPED runtime use: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2d
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2c-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-2d — Generation gate / stale guard

**Purpose:** VTSで実証済みのgeneration-based late suppressionをruntime共通primitiveにする。

**Tasks:**

- [x] current generation registryを追加する。
- [x] new turn/interrupt/reset/close時のincrement ruleを固定する。
- [x] stage completion envelopeへgenerationを付与する。
- [x] stale completion判定を一箇所に集約する。
- [x] VTS transportの既存late suppressionと整合させる。
- [x] stale drop reasonをtyped diagnosticにする。

**Acceptance:**

```text
old turn delta delivered:
False

old TTS artifact delivered:
False

close後provider completion delivered:
False

stale drop observable:
True
```

<!-- FW-RT6-2d-D-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-2d Control D
baseline head: aee53d77840f49450d9319a1ff5208cec7471757
status: IMPLEMENTED / AWAITING_REVIEW
Control A generation-gate primitives: ACCEPTED
Control B RealtimeSession generation-gate adoption: ACCEPTED
Control C race / VTS alignment: ACCEPTED
Control C corrective 1 terminal callback compatibility: ACCEPTED
Control D initial candidate: ROLLED BACK / PRESERVED IN HISTORY
Control D exact change surface: 6 files
runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeTurnResult public model changed: False
create_realtime_session signature changed: False
generation / event / terminal diagnostics keys changed: False
current generation registry: ACCEPTED
generation retirement reasons: NEW_TURN / INTERRUPT / CANCEL / RESET / SESSION_CLOSED / TURN_TERMINAL
public RealtimeSession reset method: NOT ADDED
central stage completion ingress: ACCEPTED
old turn response delta delivered: False
old TTS artifact delivered: False
interrupt / cancel late audio delivered: False
close-requested / post-close completion delivered: False
open-session stale drop observable: True
close-requested / post-close stale event emitted: False / COUNT-ONLY OBSERVABLE
stale diagnostic legacy projection: None
VTS source changed: False
VTS alignment verification: IN-MEMORY FAKE / PASS
terminal callback interrupt events: 0
terminal callback cancel events: 0
terminal callback state / phase / history mutation: False
normal post-turn no-active interrupt: PRESERVED
all real provider-driven stage paths wired: False / NOT CLAIMED
single-active-turn lifecycle enforcement: DEFERRED / LATER CHECKPOINT
normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
real unified turn orchestration: UNRESOLVED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-2d-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-3a — Stage protocols

**Purpose:** legacy runtime実装をRealtimeSessionへ接続可能なprovider-neutral stageへ分解する。

**Tasks:**

- [x] `VoiceInputStage` protocolを定義する。
- [x] `TextGenerationStage` protocolを定義する。
- [x] `VoiceOutputStage` protocolを定義する。
- [x] `MotionStage` protocolを定義する。
- [x] preflight/capability/start/cancel/close contractを統一する。
- [x] stage result envelopeへcontextを追加する。
- [x] provider-specific objectsをpublic protocolから除外する。

**Acceptance:**

```text
stage injection:
provider-neutral

fake stage injection:
PASS

provider SDK root import:
False
```


<!-- FW-RT6-3a-C-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-3a Control C
baseline head: 8db6a4ff1c9687b9e9d04b2f55a38611e27e0a5e
status: IMPLEMENTED / AWAITING_REVIEW
Control A provider-neutral stage protocols: ACCEPTED
Control B RealtimeSession stage injection: ACCEPTED
Control C exact change surface: 6 files
runtime source changed: False
stable public package: framework.realtime_stage
stage protocol count: 4
common lifecycle methods: preflight / capability / start / cancel / close
stage result context: session / turn / generation
provider-specific public objects: False
factory parameters: 7 / KEYWORD-ONLY
stage injection: provider-neutral
fake stage injection: PASS
constructor stage lifecycle calls: 0
current run_turn injected stage starts: 0 / DEFERRED
session close stage ownership: ONCE PER INJECTED STAGE
stage close exception exposure: False / COUNT-ONLY
root-public names: 121 / UNCHANGED
provider SDK root import: False
real legacy adapter migration: UNRESOLVED / LATER CHECKPOINT
preflight / capability runtime composition: NOT EXECUTED / DEFERRED
real unified turn orchestration: UNRESOLVED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3a-C-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-3b — Deterministic fake runtime controller

**Purpose:** real providerなしでraceとlate resultを再現する。

**Tasks:**

- [x] fake clock/schedulerを追加する。
- [x] stage pause/resumeを追加する。
- [x] artificial delayを追加する。
- [x] late completion injectionを追加する。
- [x] duplicate terminal injectionを追加する。
- [x] cancellation timeout injectionを追加する。
- [x] queue overflow injectionを追加する。
- [x] deterministic event trace assertion helperを追加する。

**Acceptance:**

```text
network:
False

provider SDK:
False

microphone:
False

playback:
False

race reproducible:
True
```


<!-- FW-RT6-3b-C-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-3b Control C
baseline head: 5a565afbb19e81f55d35e89486c2327a47d87ab5
status: IMPLEMENTED / AWAITING_REVIEW
Control A deterministic fake runtime controller: ACCEPTED
Control B generation-gate / terminal-registry adoption: ACCEPTED
Control C exact change surface: 6 files
runtime source changed: False
explicit package: framework.realtime_fake_runtime
deterministic controller: DeterministicFakeRuntimeController
deterministic race harness: DeterministicRealtimeRaceHarness
accepted task count: 8
actual generation gate adoption: True
actual terminal registry adoption: True
race reproducible: True
network: False
provider SDK: False
microphone: False
playback: False
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
event-hub trace projection: DEFERRED
normal unit-test layer: DEFERRED / FW-RT6-3c
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3b-C-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-3c — Normal unit-test layer

**Purpose:**release smokeとは別に高速なruntime unit testsを確立する。

**Tasks:**

- [x] `tests/`へunit test構成を追加する。
- [x] test runnerを選定する。
- [x] identity/model testsを追加する。
- [x] transition testsを追加する。
- [x] terminal registry testsを追加する。
- [x] generation/stale testsを追加する。
- [x] subscriber testsを追加する。
- [x] fake runtime testsを追加する。
- [x] smoke scriptはaggregate/release gateとして維持する。

**Acceptance:**

```text
tests directory non-empty:
True

unit tests network-free:
True

full unit suite:
PASS
```

<!-- FW-RT6-3c-C-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-3c Control C
baseline head: e368a3db3e1ae6160d6a3c3f01929eb6f256c57a
status: IMPLEMENTED / AWAITING_REVIEW
Control A unit-test foundation: ACCEPTED
Control B runtime primitive coverage: ACCEPTED
Control C exact change surface: 6 files
accepted task count: 9
tests directory non-empty: True
selected runner: unittest
identity/model tests: 12
transition tests: 7
terminal registry tests: 5
generation/stale tests: 6
subscriber/event-hub tests: 7
deterministic fake-runtime tests: 8
full discovered unit tests: 45
unit tests network-free: True
full unit suite: PASS
existing smoke/check scripts retained as aggregate/release gates: True
production runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
event-hub projection into deterministic fake trace: DEFERRED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-4a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3c-C-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-4a — RealtimeSession construction and config

**Purpose:** unified runtimeのcomposition rootを実装する。

**Tasks:**

- [x] provider-neutral `RealtimeSessionConfig`を定義する。
- [x] stage factory/injection pointsを定義する。
- [x] capability snapshotをsession construction時に固定する。
- [x] session IDを生成する。
- [x] subscriber hub/terminal registry/generation gateを所有する。
- [x] real runtimeはdefault-offにする。
- [x] configuration不足をtyped resultにする。

**Acceptance:**

```text
mock session creation:
PASS

real provider execution at construction:
False

capability snapshot available:
True
```

<!-- FW-RT6-4a-C-ACCEPTANCE-SYNC:BEGIN -->
**Aggregate status:**

```text
checkpoint: FW-RT6-4a Control C
baseline HEAD / origin/main: 0192f941e3a2009d203535ec0c97a6ceb69050ed
status: IMPLEMENTED / AWAITING_REVIEW
Control A public construction/config models: ACCEPTED
Control B RealtimeSession construction adoption: ACCEPTED
Control C exact change surface: 6 files
combined uncommitted Control A+B+C surface: 18 files
accepted task count: 7
RealtimeSessionConfig: provider-neutral
stage factory/injection points: provider-neutral session factory + four stage slots
capability snapshot fixed at construction: True
session ID generated: True
subscriber hub / terminal registry / generation gate owned: True
real runtime default-off: True
construction_result public property: True
configuration missing typed result: True
mock session creation: PASS
real-request mock fallback: False
real provider execution at construction: False
capability snapshot available: True
focused construction tests: 35 / PASS
full unit suite: 80 / PASS
root-public names: 124 / UNCHANGED FROM CONTROL A
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-4b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-4a-C-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-4a-D-CLOSURE-SYNC:BEGIN -->
## FW-RT6-4a closure sync

```text
checkpoint:
FW-RT6-4a

implementation commit:
dc80d1ade4db539a38d30c74edf73e8ba824531a

commit subject:
feat: implement realtime session construction

status:
COMPLETED / VERIFIED / COMMITTED / PUSHED / ACCEPTED / CLOSED

aggregate tasks:
7 / 7 ACCEPTED

focused construction tests before publish:
35 / PASS

full unit suite before publish:
80 / PASS

real-request mock fallback:
False

real provider execution:
False

next checkpoint:
FW-RT6-4b

next checkpoint status:
EXACT_CONTRACT_REVIEW COMPLETED / CONTROL A AUTHORIZED
```

This closure record supersedes only the checkpoint status. The earlier Control
A/B/C sections remain historical records of their pre-publish states.
<!-- FW-RT6-4a-D-CLOSURE-SYNC:END -->

---

## FW-RT6-4b — Single-active-turn lifecycle

**Purpose:**turn開始、拒否、完了、失敗を統一する。

**Tasks:**

- [x] explicit turn start APIを追加する。
- [x] active turn contextを追加する。
- [x] active中new turnをtyped rejectionする。
- [x] turn phase transitionを検証する。
- [x] normal completionをterminal registryへcommitする。
- [x] resultへsession/turn/generationを含める。
- [x] completion後sessionをidle/reusableへ戻す。

**Acceptance:**

```text
single active turn:
PASS

new turn while active:
typed rejection

normal turn:
exactly one terminal

session reusable:
True
```


<!-- FW-RT6-4b-A-TURN-START-MODELS:BEGIN -->
**Control A status:**

```text
checkpoint:
FW-RT6-4b Control A

baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

status:
IMPLEMENTED / AWAITING_REVIEW

public model:
RealtimeTurnStartResult

RealtimeTurnResult additive identity:
session_id / generation_id

root-public names:
125

start_turn runtime adoption:
DEFERRED / Control B

active-turn context:
DEFERRED / Control B

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4b-A-TURN-START-MODELS:END -->


<!-- FW-RT6-4b-B-TURN-START-ADOPTION:BEGIN -->
**Control B status:**

```text
checkpoint:
FW-RT6-4b Control B

baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

Control A:
ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

explicit start API:
RealtimeSession.start_turn()

structured active-turn context:
IMPLEMENTED

active new-turn rejection:
typed / state-neutral

active new-turn rejection reason:
active_turn_exists

automatic previous-turn replacement on explicit admission:
False

active-generation retirement on rejected start:
0

root-public names:
125 / UNCHANGED FROM CONTROL A

run_turn unified adoption:
DEFERRED / Control C

normal terminal identity population:
DEFERRED / Control C

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4b-B-TURN-START-ADOPTION:END -->

<!-- FW-RT6-4b-C-TURN-LIFECYCLE-ACCEPTANCE:BEGIN -->
**Control C / aggregate acceptance status:**

```text
checkpoint:
FW-RT6-4b Control C

baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

Control A:
ACCEPTED

Control B:
ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

run_turn explicit admission adoption:
PASS

normal result identity:
session_id / turn_id / generation_id / PASS

normal terminal registry commit:
exactly one

active context after completion:
cleared

session after completion:
IDLE / reusable

active new-turn rejection:
typed / state-neutral / no replacement

aggregate tasks:
7 / 7 ACCEPTED-CANDIDATE

focused Control A+B+C tests:
36 / PASS expected

full unit suite:
116 / PASS expected

root-public names:
125

next checkpoint:
FW-RT6-4c / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4b-C-TURN-LIFECYCLE-ACCEPTANCE:END -->


<!-- FW-RT6-4b-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-4b aggregate acceptance sync

```text
checkpoint:
FW-RT6-4b

status:
COMPLETED / VERIFIED / ACCEPTED

accepted combined surface:
16 files

focused Control A+B+C tests:
36 / PASS

full unit suite at acceptance:
116 / PASS

single active turn:
PASS

new turn while active:
typed / state-neutral rejection

normal terminal:
exactly one

session reusable:
True

active generation replacement:
0

root-public names at FW-RT6-4b acceptance:
125

provider / network / microphone / playback / real VTS execution:
False

next checkpoint:
FW-RT6-4c

next checkpoint status:
EXACT_CONTRACT_REVIEW COMPLETED / CONTROL A AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

This acceptance sync supersedes only the aggregate checkpoint status. Earlier
Control A/B/C status blocks remain historical records of their pre-acceptance
states.
<!-- FW-RT6-4b-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-4c — Public execution model decision and implementation

**Purpose:** sync/async混在を解消する。

**Current state:**

```text
legacy core:
async functions

TextChat/VoiceInput/VoiceOutput/Motion public APIs:
mostly sync

VTS:
sync public API + persistent async bridge
```

**Tasks:**

- [x] async-first internal runtimeかsync-first runtimeかをexact reviewで決定する。
- [x] host event loop上で安全なpublic APIを定義する。
- [x] blocking compatibility wrapperの範囲を決める。
- [x] callback thread/context guaranteeを文書化する。
- [x] cancel/closeのthread safetyを定義する。
- [x] deadlock/reentrancy testsを追加する。

**Recommended direction:**

```text
internal orchestration:
async-first

public:
async turn API
plus explicit blocking compatibility wrapper

do not call asyncio.run per stage
```

**Acceptance:**

```text
active host event loop safe:
PASS

deadlock:
False

per-call event loop creation:
False
```


<!-- FW-RT6-4c-A-EXECUTION-MODELS-BRIDGE:BEGIN -->
**Control A status:**

```text
checkpoint:
FW-RT6-4c Control A

baseline HEAD / origin/main:
dc80d1ade4db539a38d30c74edf73e8ba824531a

FW-RT6-4b:
COMPLETED / VERIFIED / ACCEPTED

exact contract review:
COMPLETED

execution decision:
ASYNC-FIRST

public primary turn API:
async / Control B adoption pending

blocking compatibility:
explicit wrapper + legacy run_turn / Control B adoption pending

public execution errors:
RealtimeExecutionErrorCode / RealtimeExecutionError

root-public names:
127

persistent internal event loop bridge:
IMPLEMENTED / session adoption deferred

per-call asyncio.run:
False

per-stage event loop creation:
False

callback context / close safety:
DEFERRED / Control C

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-A-EXECUTION-MODELS-BRIDGE:END -->


<!-- FW-RT6-4c-B-SESSION-EXECUTION-ADOPTION:BEGIN -->
**Control B status:**

```text
checkpoint:
FW-RT6-4c Control B

Control A:
ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control B delta:
9 files

combined working-tree surface:
24 files

focused Control A+B tests:
26 / PASS expected

full unit suite:
142 / PASS expected

public primary turn API:
run_turn_async / IMPLEMENTED

blocking compatibility:
run_turn_blocking + legacy run_turn delegation / IMPLEMENTED

host event-loop blocking call:
typed rejection

runtime-thread blocking call:
typed rejection

session-owned persistent bridge:
IMPLEMENTED / LAZY / REUSED

admission before runtime queue:
True

callback context / close safety:
DEFERRED / Control C

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-B-SESSION-EXECUTION-ADOPTION:END -->

<!-- FW-RT6-4c-C-CALLBACK-CLOSE-ACCEPTANCE:BEGIN -->
**Control C status:**

```text
checkpoint:
FW-RT6-4c Control C

Control A:
ACCEPTED

Control B:
ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control C delta:
8 files

combined working-tree surface:
26 files

callback turn execution context:
session runtime worker thread

direct synchronous control callback context:
caller thread

runtime callback -> blocking turn API:
TYPED_REJECTION / BLOCKING_CALL_FROM_RUNTIME_THREAD

runtime callback -> cancel_current_turn:
REENTRANT / DEADLOCK FALSE

runtime callback -> close:
DEFERRED UNTIL OUTERMOST OPERATION EXIT / DEADLOCK FALSE

bridge shutdown while operation depth > 0:
False

runtime self-join:
False

close before runtime start:
does not start runtime

close after runtime start:
worker / loop stopped

worker / loop leak after final close:
False

close idempotent:
True

focused Control A+B+C tests:
36 / PASS expected

full unit suite:
152 / PASS expected

FW-RT6-4c tasks:
6 / 6 ACCEPTED-CANDIDATE

next checkpoint:
FW-RT6-5a / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-C-CALLBACK-CLOSE-ACCEPTANCE:END -->


<!-- FW-RT6-4c-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-4c post-acceptance source-of-truth sync

This additive block records operator acceptance without rewriting the historical
Control A/B/C pre-acceptance checkpoints above.

```text
checkpoint:
FW-RT6-4c aggregate acceptance

status:
COMPLETED / VERIFIED / ACCEPTED

combined working-tree surface:
26 files

focused Control A+B+C tests:
36 / PASS

full unit suite at acceptance:
152 / PASS

FW-RT6-4c tasks:
6 / 6 ACCEPTED

deadlock:
False

worker / loop leak after final close:
False

next checkpoint:
FW-RT6-5a exact contract review completed / Control A authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-4c-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-5a — Cancelable text-generation protocol

**Purpose:** `BaseLLM.ask_stream()` generatorからcancel-aware stageへ移行する。

**Tasks:**

- [x] stream handle/protocolを定義する。
- [x] cooperative cancellation tokenを追加する。
- [x] stream close/dispose contractを追加する。
- [x] response delta envelopeへturn/generationを付与する。
- [x] completion/interrupt時のconversation history commit ruleを固定する。
- [x] provider hard-cancel capabilityを報告する。

**Acceptance:**

```text
stop future deltas:
PASS

stream resource cleanup:
PASS

interrupted partial output committed as complete:
False
```

<!-- FW-RT6-5a-A-MODEL-TOKEN-CONTRACT:BEGIN -->
**Control A status:**

```text
checkpoint:
FW-RT6-5a Control A

FW-RT6-4c:
COMPLETED / VERIFIED / ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control A delta:
9 files

combined working-tree surface:
30 files

stable explicit package:
framework.realtime_text_generation

cooperative cancellation token:
THREAD-SAFE / IDEMPOTENT / FIRST-REASON-WINS

delta identity:
session / turn / generation / delta_index

typed close-result vocabulary:
DEFINED

conversation history transaction rule:
FIXED / IMPLEMENTATION DEFERRED TO CONTROL B

provider hard-cancel source of truth:
TextGenerationCapability.provider_hard_cancel_supported

root-public names:
127 / UNCHANGED

provider / network / microphone / playback / real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5a-A-MODEL-TOKEN-CONTRACT:END -->


<!-- FW-RT6-5a-B-STREAM-HISTORY-CONTRACT:BEGIN -->
**Control A acceptance / Control B status:**

```text
checkpoint:
FW-RT6-5a Control B

Control A:
COMPLETED / VERIFIED / ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control B delta:
7 files

combined working-tree surface:
32 files

stream protocol:
TextGenerationStream / PASS

provider-neutral reference handle:
ProviderNeutralTextGenerationStream / PASS

cancel after first delta:
future delivered deltas = 0 / PASS

cancel during in-flight source pull:
returned source delta delivered = False / PASS

source cleanup:
at most once / PASS

close / dispose:
typed / idempotent / PASS

normal completed history:
user + full assistant pair / exactly once / PASS

cancel / close / source failure history commit:
False / PASS

provider hard-cancel overclaim:
False

root-public names:
127 / UNCHANGED

provider / network / microphone / playback / real VTS execution:
False

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

Aggregate FW-RT6-5a tasks remain unchecked until Control C completes the
additive stage protocol and aggregate acceptance gate.
<!-- FW-RT6-5a-B-STREAM-HISTORY-CONTRACT:END -->


<!-- FW-RT6-5a-C-STAGE-ACCEPTANCE:BEGIN -->
**Control B acceptance / Control C aggregate status:**

```text
checkpoint:
FW-RT6-5a Control C

Control A:
COMPLETED / VERIFIED / ACCEPTED

Control B:
COMPLETED / VERIFIED / ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control C delta:
7 files

combined working-tree surface:
34 files

CancelableTextGenerationStage:
ADDITIVE / PASS

existing TextGenerationStage:
UNCHANGED / COMPATIBLE / PASS

framework.realtime_stage exports:
7 / UNCHANGED

root-public names:
127 / UNCHANGED

cancel future delivered deltas:
0 / PASS

source cleanup:
at most once / PASS

close / dispose:
typed / idempotent / PASS

normal completed history:
user + full assistant pair / exactly once / PASS

interrupted / cancelled / failed partial history commit:
False / PASS

provider hard-cancel capability source:
TextGenerationCapability.provider_hard_cancel_supported / PASS

provider hard-cancel overclaim:
False

FW-RT6-5a tasks:
6 / 6 ACCEPTED-CANDIDATE

provider / network / microphone / playback / real VTS execution:
False

next checkpoint:
FW-RT6-5b / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5a-C-STAGE-ACCEPTANCE:END -->


---



<!-- FW-RT6-5a-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-5a post-acceptance source-of-truth sync

```text
checkpoint:
FW-RT6-5a aggregate acceptance

status:
COMPLETED / VERIFIED / ACCEPTED

combined working-tree surface:
34 files

focused Control A+B+C tests:
41 / PASS

full unit suite at acceptance:
193 / PASS

FW-RT6-5a tasks:
6 / 6 ACCEPTED

next checkpoint:
FW-RT6-5b exact contract review completed / Control A authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5a-D-ACCEPTANCE-SYNC:END -->

---

## FW-RT6-5b — LLM provider adapters

**Tasks:**

- [x] OpenAI adapterをcancel-aware protocolへ接続する。
- [x] Gemini adapterを接続する。
- [x] xAI adapterを接続する。
- [x] fallback adapterへcancelを伝播する。
- [x] router adapterへcancelを伝播する。
- [x] provider exceptionをsafe classificationへ変換する。
- [x] provider hard cancel未対応をtruthfulに返す。

**Acceptance:**

```text
OpenAI fake stream:
PASS

Gemini fake stream:
PASS

xAI fake stream:
PASS

fallback cancellation:
PASS

raw provider exception public:
False
```


<!-- FW-RT6-5b-A-OPENAI-XAI-ADAPTERS:BEGIN -->
**Control A status:**

```text
checkpoint:
FW-RT6-5b Control A

FW-RT6-5a:
COMPLETED / VERIFIED / ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control A delta:
9 files

combined working-tree surface:
38 files

OpenAI adapter:
OpenAITextGenerationAdapter / PASS expected

xAI adapter:
XAITextGenerationAdapter / PASS expected

transactional committed history:
Framework-owned / normal completion exactly once

cancel / source failure / early close history mutation:
0

provider safe exception:
TextGenerationProviderError

raw provider exception public:
False

provider hard-cancel source:
TextGenerationCapability.provider_hard_cancel_supported

OpenAI / xAI provider hard cancel:
False / truthful

root-public names:
127 / UNCHANGED

Gemini / fallback / router:
DEFERRED / Control B

provider / network / microphone / playback / real VTS execution:
False

Control B:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

Aggregate FW-RT6-5b tasks remain unchecked until later Controls complete the
Gemini, fallback/router, and aggregate acceptance work.
<!-- FW-RT6-5b-A-OPENAI-XAI-ADAPTERS:END -->

<!-- FW-RT6-5b-A-ACCEPTANCE-SYNC:BEGIN -->
**Control A acceptance sync:**

```text
checkpoint:
FW-RT6-5b Control A

status:
COMPLETED / VERIFIED / ACCEPTED

exact Control A delta:
9 files

combined working-tree surface:
38 files

focused tests:
20 / PASS

full unit suite at acceptance:
213 / PASS

next:
FW-RT6-5b Control B authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-A-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-5b-B-GEMINI-FALLBACK-ROUTER:BEGIN -->
**Control B status:**

```text
checkpoint:
FW-RT6-5b Control B

Control A:
COMPLETED / VERIFIED / ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control B delta:
6 files

combined working-tree surface:
40 files

Gemini adapter:
GeminiTextGenerationAdapter / PASS expected

Gemini provider-owned mutable chat dependency:
False

Gemini transactional history:
Framework-owned / normal completion exactly once

fallback adapter:
FallbackTextGenerationAdapter / PASS expected

fallback before first delivered delta:
allowed

fallback after first delivered delta:
False

fallback after cancellation:
False

router adapter:
RouterTextGenerationAdapter / PASS expected

router route selection:
once per stream

context / cancellation token propagation:
same object / PASS expected

provider hard-cancel source:
TextGenerationCapability.provider_hard_cancel_supported

Gemini / fallback / router hard-cancel overclaim:
False

root-public names:
127 / UNCHANGED

provider / network / microphone / playback / real VTS execution:
False

Control C:
NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```

Aggregate FW-RT6-5b tasks remain unchecked until Control C completes fake-provider
aggregate acceptance and source-of-truth task sync.
<!-- FW-RT6-5b-B-GEMINI-FALLBACK-ROUTER:END -->



<!-- FW-RT6-5b-B-ACCEPTANCE-SYNC:BEGIN -->
**Control B acceptance sync:**

```text
checkpoint:
FW-RT6-5b Control B

status:
COMPLETED / VERIFIED / ACCEPTED

exact Control B delta:
6 files

combined working-tree surface:
40 files

focused Control A+B provider-adapter tests:
41 / PASS

full unit suite at acceptance:
234 / PASS

next:
FW-RT6-5b Control C authorized

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-5b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
**Control C status:**

```text
checkpoint:
FW-RT6-5b Control C

Control A:
COMPLETED / VERIFIED / ACCEPTED

Control B:
COMPLETED / VERIFIED / ACCEPTED

status:
IMPLEMENTED / AWAITING_REVIEW

exact Control C delta:
6 files

combined working-tree surface:
42 files

OpenAI fake stream:
PASS expected

Gemini fake stream:
PASS expected

xAI fake stream:
PASS expected

fallback cancellation:
PASS expected

router cancellation:
PASS expected

raw provider exception public:
False expected

provider hard-cancel source:
TextGenerationCapability.provider_hard_cancel_supported

provider hard-cancel overclaim:
False expected

root-public names:
127 / UNCHANGED

provider / network / microphone / playback / real VTS execution:
False

next checkpoint:
FW-RT6-5c / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED
```
<!-- FW-RT6-5b-C-AGGREGATE-ACCEPTANCE:END -->

---

## FW-RT6-5c — TextChatSession compatibility adapter

**Purpose:**既存v4/v5 public APIをv6 runtime primitiveへ接続する。

**Tasks:**

- [x] `TextChatSession`へsession IDを付与する。
- [x] ask/ask_streamをturn contextへ関連付ける。
- [x] interruptをv6 control resultへbridgeする。
- [x] old boolean return compatibilityを維持する方法を決める。
- [x] raw exception eventを削除する。
- [x] v4/v5 event adapterを追加する。

**Acceptance:**

```text
existing ask:
compatible

existing ask_stream:
compatible

existing interrupt:
compatible

safe events:
PASS
```

---

## FW-RT6-6a — Voice output generation protocol

**Purpose:**synthesisをqueue/playbackから分離する。

**Tasks:**

- [x] provider-neutral synthesis work IDを追加する。
- [x] synthesis start/result/cancel protocolを定義する。
- [x] generation capabilityを定義する。
- [x] provider adapterをprotocolへ接続する。
- [x] active generation stateを観測可能にする。
- [x] provider hard cancel capabilityをtruthfulにする。

**Acceptance:**

```text
generation identity:
True

active generation observable:
True

provider details public:
False
```

---

## FW-RT6-6b — Opaque artifact store

**Purpose:**local path exposureをなくす。

**Source reason:** G-10.

**Tasks:**

- [x] FW-owned `VoiceArtifactStore` protocolを定義する。
- [x] opaque artifact IDを発行する。
- [x] internal pathとpublic refを分離する。
- [x] resolve/open/delete/expire contractを定義する。
- [x] URL handoffとartifact refを排他的にする。
- [x] real provider adapterの`str(artifact_path)`返却を廃止する。
- [x] lifecycle generationとartifact validityを関連付ける。

**Acceptance:**

```text
raw local path in VoiceOutputResult:
False

exactly one audio handoff:
PASS

expired/invalidated artifact:
not playable
```

---

## FW-RT6-6c — Bounded voice-output work queue

**Tasks:**

- [x] pending synthesis queueを実装する。
- [x] bounded depthを設定可能にする。
- [x] queue itemへsession/turn/generation/work IDを付与する。
- [x] enqueue accepted/rejected resultをtypedにする。
- [x] pending clearを実装する。
- [x] active generationとpending queueを別状態にする。
- [x] overflow eventを追加する。

**Acceptance:**

```text
bounded queue:
PASS

silent drop:
False

pending clear:
PASS

active cancel overclaim:
False
```

---

## FW-RT6-6d — Generation cancel and artifact invalidation

**Tasks:**

- [x] active synthesis cooperative cancelを実装する。
- [x] provider cancel timeoutを実装する。
- [x] provider hard cancel resultを記録する。
- [x] completed artifact invalidationを実装する。
- [x] future delivery suppressionを実装する。
- [x] late artifactをstale guardで拒否する。
- [x] duplicate flush/cancelをidempotentにする。

**Acceptance:**

```text
late audio delivered:
False

pending clear vs active cancel:
distinguished

duplicate flush:
safe
```

---

## FW-RT6-6e — Host playback boundary

**Tasks:**

- [x] FW-owned playbackとhost-owned playbackをcapabilityで分離する。
- [x] `playback_stop_requested_to_host` eventを定義する。
- [x] host acknowledgementを任意contractとして定義する。
- [x] host停止未確認をFW停止成功と表現しない。
- [x] legacy `VoiceEngine`/ffplay pathをinternal compatibilityへ隔離する。
- [x] legacy local playerのdeprecation方針を決める。

**Acceptance:**

```text
host playback physical stop claimed:
False

artifact invalidation emitted:
True

legacy ffplay root-public:
False
```

---

## FW-RT6-7a — VoiceInputSession capability correction

**Purpose:** v5.4 real STT実装とpublic sessionの古いstatusを同期する。

**Tasks:**

- [x] `VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED`の現状を再評価する。
- [x] OpenAI real executor availabilityをcapabilityへ反映する。
- [x] `VoiceInputSessionInfo.api_version`を中央versionへ接続する。
- [x] session ID/turn/generationを追加する。
- [x] typed lifecycle eventへ移行する。
- [x] default fake/real factory selectionをprovider-neutralにする。

**Acceptance:**

```text
real OpenAI STT status truthful:
True

host constructs provider-specific adapter:
not required for normal public flow

default fake path:
PASS
```

---

## FW-RT6-7b — Voice input stage composition

**Tasks:**

- [x] host-owned audio sourceをturnへ関連付ける。
- [x] preflight/start/completed/failed eventを発行する。
- [x] transcript finalをtyped payloadにする。
- [x] input abortを実装する。
- [x] late transcriptをgeneration gateで拒否する。
- [x] raw audio retention default-offを維持する。
- [x] FILE_PATH pathをpublic eventへ出さない。

**Acceptance:**

```text
voice input real/fake:
stage-composable

late transcript delivered:
False

private audio path event exposure:
False
```

---

## FW-RT6-7c — Voice input result compatibility

**Tasks:**

- [x] existing `VoiceInputResult`へcorrelation contextをadditiveに追加する。
- [x] existing factory methodsを維持する。
- [x] existing `listen_result` / `transcribe_audio_result` compatibilityを維持する。
- [x] existing mapping callbacksをv6 event adapterで維持する。
- [x] close後resultを統一rejectionへ接続する。

**Acceptance:**

```text
v5 public examples:
PASS

v6 correlation:
PASS
```

---

## FW-RT6-8a — Motion correlation context

**Purpose:**既存v5.5 MotionSessionをunified turnへ安全に接続する。

**Tasks:**

- [x] motion requestへoptional turn/generation contextを追加する。
- [x] result/eventへturn/generationを追加する。
- [x] existing request_id/session_id compatibilityを維持する。
- [x] event sequenceをunified sequencerへbridgeする。
- [x] current VTS generation suppressionをcommon stale guardへ接続する。

**Acceptance:**

```text
v5.5 motion behavior:
preserved

turn correlation:
True

late motion completion delivered:
False
```

---

## FW-RT6-8b — Motion lifecycle extension hook

**Tasks:**

- [x] lifecycle-to-motion hook interfaceを追加する。
- [x] listening/thinking/speaking/interrupted/completed/failed phaseを通知可能にする。
- [x] Framework coreがcharacter固有mappingを決めない。
- [x] host/pluginがprovider-neutral intentを返す。
- [x] unsupported intentをtypedに処理する。
- [x] hook failureがconversation terminalを必ずしもfailさせないpolicyを固定する。

**Acceptance:**

```text
product-specific mapping in FW core:
False

provider-neutral intent:
True

motion failure isolation:
documented/tested
```

---

## FW-RT6-8c — Motion cancel/clear capability

**Tasks:**

- [x] pending motion request trackingを追加する。
- [x] request cancel capabilityを追加する。
- [x] stop_motion unavailableをtruthfulに返す。
- [x] whole-turn interruptからmotion reachを返す。
- [x] duplicate stop/cancelをsafeにする。

**Acceptance:**

```text
stop_motion unsupported overclaim:
False

motion reach in interrupt result:
True
```

---

## FW-RT6-9a — Interrupt coordinator

**Purpose:** whole-turn interruptを各stageへ伝播する。

**Tasks:**

- [x] active stage registryを追加する。
- [x] interrupt target validationを実装する。
- [x] turn terminal/not-found/closed結果を実装する。
- [x] LLM cancelを呼ぶ。
- [x] TTS generation cancel/pending clearを呼ぶ。
- [x] artifact invalidationを呼ぶ。
- [x] motion cancel/clearを呼ぶ。
- [x] aggregate resultを構築する。
- [x] timeout/partial completionを処理する。

**Acceptance:**

```text
subsystem reach observable:
True

unsupported overclaim:
False

partial result:
PASS
```

---

## FW-RT6-9b — Duplicate interrupt and race ordering

**Tasks:**

- [x] interrupt request IDを導入するか決定する。
- [x] duplicate interruptを同じterminal resultへ収束させる。
- [x] interrupt vs normal completion raceを固定する。
- [x] interrupt vs close raceを固定する。
- [x] flush vs interrupt orderingを固定する。
- [x] new turn request during interruptingをtyped rejectする。
- [x] deterministic fake race testsを追加する。

**Acceptance:**

```text
duplicate interrupt:
idempotent

multiple turn terminal events:
False

race outcomes deterministic:
PASS
```

---

## FW-RT6-9c — Barge-in decision and execution separation

**Tasks:**

- [x] `decide_barge_in()`をpure policy decisionとして維持する。
- [x] decisionからcontrol planを生成する。
- [x] actual executionはinterrupt coordinatorへ委譲する。
- [x] microphone detectionをcore scopeへ入れない。
- [x] hard-cancel policy選択時もcapability不足を正しくdowngradeする。

**Acceptance:**

```text
barge-in policy triggers microphone:
False

decision != execution:
True

capability downgrade truthful:
True
```

---

## FW-RT6-9d — End-to-end stale enforcement

**Tasks:**

- [x] text delta delivery前にgeneration checkする。
- [x] transcript delivery前にcheckする。
- [x] TTS artifact publish前にcheckする。
- [x] motion completion publish前にcheckする。
- [x] close/reset/new turn後のold callbackをdropする。
- [x] stale count/drop reasonをdiagnosticsへ記録する。

**Acceptance:**

```text
all stage late-result scenarios:
PASS

silent corruption:
False
```

---

## FW-RT6-10a — Recovery/reset semantics

**Tasks:**

- [x] turn-only resetを定義する。
- [x] session resetを定義する。
- [x] reconnect requiredを定義する。
- [x] close required/permanently failedを定義する。
- [x] reset時generation incrementを実装する。
- [x] resetで失われるprovider contextを文書化する。
- [x] reset failureをtypedに返す。

**Acceptance:**

```text
interrupt後reuse:
typed

reset scope:
explicit

old event after reset:
rejected
```

---

## FW-RT6-10b — Close/dispose lifecycle

**Tasks:**

- [x]全public session close semanticsを統一する。
- [x] closeをidempotentにする。
- [x] active turn closeをterminalへ収束させる。
- [x] stage cleanup timeoutを実装する。
- [x] callback/event hubをcloseする。
- [x] provider/client/bridge cleanup resultをdiagnosticsへ記録する。
- [x] close後operationをtyped rejectionにする。

**Acceptance:**

```text
repeated close:
safe

active turn orphan:
False

bridge/thread leak:
False
```

---

## FW-RT6-10c — Public diagnostics

**Tasks:**

- [x] session snapshotを追加する。
- [x] current phaseを追加する。
- [x] active turn/generationを追加する。
- [x] queue depthを追加する。
- [x] active generation countを追加する。
- [x] last terminal resultを追加する。
- [x] last safe error codeを追加する。
- [x] stale/duplicate/overflow countを追加する。
- [x] private payload/text/audio/pathを含めない。

**Acceptance:**

```text
operator state observable:
True

credential/raw payload/transcript exposed:
False
```

---

## FW-RT6-10d — Callback and plugin isolation

**Tasks:**

- [x] public callback failure policyを定義する。
- [x] plugin hook failure policyを定義する。
- [x] motion hook failure policyを定義する。
- [x] critical/non-critical stage failureを区別する。
- [x] callback reentrancyを検証する。
- [x] event callbackがsession lockを保持したまま呼ばれない設計にする。

**Acceptance:**

```text
subscriber exception kills runtime:
False

deadlock via reentrant callback:
False
```

---

## FW-RT6-11a — v5 standalone session compatibility

**Tasks:**

- [x] TextChatSession compatibility adapterを完成する。
- [x] VoiceInputSession compatibility adapterを完成する。
- [x] VoiceOutputSession compatibility adapterを完成する。
- [x] MotionSession compatibility adapterを完成する。
- [x] RealtimeSession v5 skeleton behaviorのcompatibility modeを決める。
- [x] deprecated fields/methodsのwarning policyを決める。

**Acceptance:**

```text
v5 public examples:
PASS

v5 release contract smokes:
PASS or explicitly superseded with migration evidence

breaking change undocumented:
False
```

---

## FW-RT6-11b — Root-public API cleanup

**Tasks:**

- [x] v6 root-public inventoryを固定する。
- [x] provider-specific classesのroot exportを再評価する。
- [x] stable optional provider namespaceを設ける場合はdocumentする。
- [x] wildcard export ordering依存をなくす。
- [x] exact public API manifestを生成する。
- [x] docs/examples/`__all__`の差分gateを追加する。

**Acceptance:**

```text
public manifest:
single source of truth

smoke_public_facade:
PASS

docs/export drift:
FAILS GATE
```

---

## FW-RT6-11c — Migration guide and examples

**Tasks:**

- [x] v5 standalone sessionからv6 unified sessionへのmigrationを記載する。
- [x] text-only exampleを追加する。
- [x] host-captured audio exampleを追加する。
- [x] interrupt/partial completion exampleを追加する。
- [x] local playback boundary exampleを追加する。
- [x] motion extension hook exampleを追加する。
- [x] unavailable capability fallback exampleを追加する。
- [x] examplesがprovider credentialなしでimport可能であることを確認する。

---

## FW-RT6-12a — P1 public audio chunk streaming

**Authorization:** P0進捗後に別途判断。

**Tasks:**

- [x] audio chunk typeを定義する。
- [x] chunk sequenceを定義する。
- [x] accepted format/max chunk/max durationをcapability化する。
- [x] end-of-inputを定義する。
- [x] input abortを定義する。
- [x] partial transcript eventを実装する。
- [x] malformed/out-of-order chunkをtyped rejectする。

---

## FW-RT6-12b — P1 backpressure

**Tasks:**

- [ ] audio input queue backpressureを実装する。
- [ ] response delta subscriber backpressureを実装する。
- [ ] voice output queue backpressureを実装する。
- [ ] max in-flightをcapability化する。
- [ ] retryable rejectionを実装する。
- [ ] silent dropを禁止する。

---

## FW-RT6-12c — Experimental natural-turn extensions

**Not required for v6.0.0 P0 acceptance.**

```text
microphone listening while speaking
VAD-based automatic detection
wake word
background input monitoring
automatic next-turn capture
echo cancellation
noise suppression
```

各項目は別roadmap/exact contractとする。

---

## FW-RT6-13a — Integrated fake-runtime acceptance

**Tasks:**

- [ ] text-only normal turn。
- [ ] host audio -> transcript -> text -> TTS -> motion normal turn。
- [ ] user stop during response stream。
- [ ] user speech interrupt during voice output。
- [ ] duplicate interrupt。
- [ ] late response delta。
- [ ] late TTS artifact。
- [ ] late motion completion。
- [ ] queue overflow。
- [ ] session reset。
- [ ] session close during active turn。
- [ ] close後operation rejection。
- [ ] exact event trace/terminal resultを検証する。

**Acceptance:**

```text
fake-only integrated suite:
PASS

exactly-once terminal:
PASS

stale rejection:
PASS

network/provider/microphone/playback:
False
```

---

## FW-RT6-13b — Guarded real-runtime composition

**Tasks:**

- [ ] real STT composition。
- [ ] real LLM streaming composition。
- [ ] real TTS composition。
- [ ] real VTS motion composition。
- [ ] explicit double opt-in。
- [ ] provider SDK lazy import。
- [ ] real-run preflight。
- [ ] safe failure normalization。
- [ ] private configuration/evidence non-commit policy。
- [ ] stage別capability/reach result verification。

---

## FW-RT6-13c — Operator acceptance

**Requirements:**

```text
private credential values:
not displayed

private paths:
not displayed/committed

raw audio:
not committed

raw provider payload:
not displayed/committed

raw exceptions:
not displayed/committed

private model/hotkey/selector:
not displayed/committed

screenshots/evidence:
operator-only
```

**Acceptance scenarios:**

- [ ] configured real voice input。
- [ ] configured real LLM streaming。
- [ ] cooperative interrupt。
- [ ] real TTS generation。
- [ ] pending clear / late artifact rejection。
- [ ] host playback stop boundary。
- [ ] configured real motion。
- [ ] interrupt recovery / next turn。
- [ ] close cleanup。

---

## FW-RT6-14a — Aggregate conformance gate

**Tasks:**

- [ ] root-public manifest gate。
- [ ] import safety gate。
- [ ] capability truthfulness gate。
- [ ] event ordering gate。
- [ ] exactly-once terminal gate。
- [ ] stale rejection gate。
- [ ] interrupt reach gate。
- [ ] TTS work-control gate。
- [ ] security/redaction gate。
- [ ] compatibility gate。
- [ ] full unit suite。
- [ ] full smoke suite。

---

## FW-RT6-14b — Documentation and migration freeze

**Tasks:**

- [ ] README current release sectionをv6へ更新する。
- [ ] append-only historical READMEを整理する。
- [ ] public facade docsを同期する。
- [ ] app integration contractを同期する。
- [ ] advanced runtime docsをv6へ更新する。
- [ ] migration guideを完成する。
- [ ] capability/event/error referenceを完成する。
- [ ] non-goalsとexperimental scopeを明記する。

---

## FW-RT6-14c — Deterministic package and release

**Tasks:**

- [ ] v6 package builder。
- [ ] exact committed membership。
- [ ] deterministic rebuild。
- [ ] duplicate entry rejection。
- [ ] private artifact rejection。
- [ ] package-import smoke。
- [ ] release notes。
- [ ] strict tag readiness。
- [ ] annotated tag。
- [ ] push。
- [ ] GitHub Release。
- [ ] official ZIP + SHA-256 sidecar。
- [ ] published asset redownload verification。
- [ ] clean tree confirmation。

---

# 4. Critical path

```text
FW-RT6-0a
-> FW-RT6-0b / 0c
-> FW-RT6-1a..1e
-> FW-RT6-2a..2d
-> FW-RT6-3a..3c
-> FW-RT6-4a..4c
-> FW-RT6-5a..5c
-> FW-RT6-6a..6e
-> FW-RT6-7a..7c
-> FW-RT6-8a..8c
-> FW-RT6-9a..9d
-> FW-RT6-10a..10d
-> FW-RT6-11a..11c
-> FW-RT6-13a..13c
-> FW-RT6-14a..14c
```

P1:

```text
FW-RT6-12a / 12b:
P0 stability後に別authorization

FW-RT6-12c:
v6.0.0 core releaseとは分離可能
```

---

# 5. Recommended first implementation checkpoint

## FW-RT6-0a

最初の実装はdocs/test-onlyで行う。

```text
runtime source change:
False

provider execution:
False

network:
False

microphone:
False

playback:
False

private config read:
False
```

まずsource inventoryとtasklistをrepository内の正式source of truthへ固定し、そのcommit受入後に`FW-RT6-0b`のexact contract reviewへ進む。

---

# 6. Current decision state

```text
v5.5.0:
CLOSED / COMPLETE

v6.0.0 roadmap:
DRAFTED

current source:
REVIEWED

v6.0.0 task list:
DRAFTED_FROM_SOURCE

FW-RT6-0a:
IMPLEMENTED / AWAITING_REVIEW

next implementation checkpoint:
FW-RT6-0b READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED

commit / push:
NOT_AUTHORIZED

DRC:
OUT OF SCOPE / NOT_ACCESSED
```

<!-- FW-RT6-0b-D-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-0b aggregate acceptance sync

```text
checkpoint: FW-RT6-0b Control D
baseline head: 136be27c9f6fe62b7753c64f4fed02ae94f98da9
status: IMPLEMENTED / AWAITING_REVIEW
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
Control D exact change surface: 4 files
runtime Python changed by Control D: False
canonical root-public name count: 95
VoiceOutputSession duplicate methods: False
framework source version: 6.0.0.dev0
latest published release: 5.5.0
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-0c
next checkpoint authorized: False
commit / push: NOT_AUTHORIZED
```

FW-RT6-0c remains a separate authorization boundary for installable SDK and
resource resolution. Capability truthfulness and unified realtime composition
remain later tasklist work and are not completed by this sync.
<!-- FW-RT6-0b-D-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-5b-C-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-5b aggregate acceptance sync

```text
checkpoint: FW-RT6-5b Control C
status: COMPLETED / VERIFIED / ACCEPTED
accepted combined surface: 42 files
focused: 51 / PASS
full: 244 / PASS
tasks: 7 / 7 ACCEPTED
root-public: 127 / UNCHANGED
next checkpoint: FW-RT6-5c Control A authorized
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-5b-C-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-5c-A-IDENTITY-EVENT-SCAFFOLD:BEGIN -->
## FW-RT6-5c Control A — TextChatSession identity/event scaffold

```text
status: COMPLETED / VERIFIED / ACCEPTED
exact Control A delta: 7 files
combined working-tree surface: 46 files
TextChatSession stable SessionId: PASS expected
internal TurnId / GenerationId context: PASS expected
session-local canonical EventSequence: PASS expected
on_realtime_event(): additive / PASS expected
ask/ask_stream canonical adoption: DEFERRED / CONTROL B
interrupt typed result bridge: DEFERRED / CONTROL C
TextChatSessionInfo: UNCHANGED
legacy ask/ask_stream/interrupt/events: UNCHANGED
root-public names: 127 / UNCHANGED
provider/network/microphone/playback/real VTS execution: False
Control B: AUTHORIZED / IMPLEMENTED IN NEXT CONTROL
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-5c-A-IDENTITY-EVENT-SCAFFOLD:END -->


<!-- FW-RT6-5c-B-CANONICAL-ADOPTION:BEGIN -->
## FW-RT6-5c Control B — ask/ask_stream canonical adoption

```text
status: COMPLETED / VERIFIED / ACCEPTED
exact Control B delta: 7 files
combined working-tree surface: 48 files
Control A: COMPLETED / VERIFIED / ACCEPTED
ask/ask_stream turn context adoption: PASS expected
canonical normal order: TURN_STARTED -> RESPONSE_STARTED -> DELTA* -> RESPONSE_COMPLETED -> TURN_COMPLETED
canonical interrupt terminal: TURN_INTERRUPTED / EXACTLY_ONCE expected
canonical failure terminal: TURN_FAILED / EXACTLY_ONCE expected
legacy TextChatSessionEvent type/data: UNCHANGED expected
legacy state transitions: UNCHANGED expected
raw exception event exposure: False expected
ask_stream exception re-raise: PRESERVED expected
interrupt_result(): DEFERRED / CONTROL C
legacy interrupt(): BOOL_TRUE / UNCHANGED
TextChatSessionInfo: UNCHANGED / api_version 4.0
root-public names: 127 / UNCHANGED
focused Control A+B: 32 / PASS expected
full: 276 / PASS expected
provider/network/microphone/playback/real VTS execution: False
Control C: AUTHORIZED / IMPLEMENTED IN NEXT CONTROL
commit / push: NOT_AUTHORIZED
```

FW-RT6-5c aggregate six task checkboxes are closed by Control C aggregate acceptance.
<!-- FW-RT6-5c-B-CANONICAL-ADOPTION:END -->

<!-- FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN -->
## FW-RT6-5c Control C — typed interrupt bridge / aggregate acceptance

```text
status: IMPLEMENTED / AWAITING_REVIEW
exact Control C delta: 9 files
combined working-tree surface: 50 files
Control A: COMPLETED / VERIFIED / ACCEPTED
Control B: COMPLETED / VERIFIED / ACCEPTED
interrupt_result() active: ACCEPTED / PASS expected
interrupt_result() idle: NO_ACTIVE_TURN / PASS expected
interrupt_result() closed: ALREADY_CLOSED / PASS expected
legacy interrupt(): BOOL_TRUE / UNCHANGED expected
canonical INTERRUPT_REQUESTED: EXACTLY_ONCE / PASS expected
legacy interrupt_requested event: UNCHANGED expected
provider hard cancel overclaim: False expected
queue flush overclaim: False expected
existing RealtimeEvent.to_v5()/as_v5_dict(): REUSED / PASS expected
raw exception event exposure: False expected
ask/ask_stream compatibility: PASS expected
TextChatSessionInfo: UNCHANGED / api_version 4.0
root-public names: 127 / UNCHANGED
focused Control A+B+C: 46 / PASS expected
full: 290 / PASS expected
tasks: 6 / 6 ACCEPTED-CANDIDATE
provider/network/microphone/playback/real VTS execution: False
next checkpoint: FW-RT6-6a / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-5c-C-INTERRUPT-AGGREGATE:END -->


<!-- FW-RT6-6a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6a Control A — voice-synthesis protocol acceptance sync

```text
checkpoint: FW-RT6-6a Control A
baseline head: 3c40a1bc537aaa9015235b520b3431819ec0381a
implementation commit: 5d6762115b939e30cf942e3ccf2068ed1346fa18
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control A surface: 5 files
dedicated gate: PASS
focused FW-RT6-5a regression: 41 / PASS
focused FW-RT6-5b regression: 51 / PASS
focused FW-RT6-5c regression: 46 / PASS
full Framework unit suite: 290 / PASS
stable package: framework.realtime_voice_output
synthesis work ID: fw_synthesis_<32 lowercase hex>
correlation: session / turn / generation / work
root-public names: 127 / UNCHANGED
provider details public: False
provider hard-cancel overclaim: False
existing voice-output/session/stage contracts changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6a aggregate: NOT_COMPLETED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B: AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the provider-neutral synthesis identity, result/cancel protocol
vocabulary, and capability truthfulness boundary. Existing provider-adapter
adoption and concrete active-generation observability remain Control B work, so
the aggregate FW-RT6-6a task checkboxes above remain open until their owning
controls are accepted.

The roadmap P0-5 TTS Work Control scope is unchanged. FW-RT6-6b through 6e
remain separate authorization boundaries for artifact storage, bounded pending
work, generation cancellation/invalidation, and the host playback boundary.
<!-- FW-RT6-6a-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-6a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6a Control B — provider adoption / active-generation acceptance sync

```text
checkpoint: FW-RT6-6a Control B
baseline head: 5a509c9ddc18cd55dc84b264193bab973c176ee6
implementation commit: 82ca4ee7f4a7105727013b729279b9fe81a74a4c
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control B surface: 6 files
dedicated gate: PASS
Control A regression: PASS
full Framework unit suite: 290 / PASS
provider adapter protocol adoption: True
active generation observable: True
active generation thread-safe: True
stable package exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
generation_cancel_supported: False
provider_hard_cancel_supported: False
pending queue changed: False
artifact invalidation changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6a aggregate: NOT_COMPLETED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C: AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts provider-adapter capability adoption plus concrete, thread-safe
active-generation observability without expanding the accepted stable package or
root-public API. It does not claim active synthesis cancellation or provider hard
cancel support that the current provider boundary cannot perform.

FW-RT6-6a aggregate acceptance remains Control C work. Control C owns the final
identity / observability / privacy / capability aggregate review and may close the
six FW-RT6-6a task checkboxes only if the combined Control A+B contract remains
truthful. Pending queue, artifact invalidation, generation-cancel execution, and
host playback remain FW-RT6-6c/6d/6e boundaries.
<!-- FW-RT6-6a-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-6a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6a Control C — aggregate identity / observability / privacy acceptance

```text
checkpoint: FW-RT6-6a Control C
baseline head: dd34b24faca398a070d1c50681b5e1809c260fb2
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
status: IMPLEMENTED / AWAITING_REVIEW
exact Control C delta: 3 files
Control A dedicated regression: PASS expected
Control B dedicated regression: PASS expected
full Framework unit suite: 290 / PASS expected
generation identity: True / PASS expected
active generation observable: True / PASS expected
active generation thread-safe: True / PASS expected
provider details public: False / PASS expected
provider adapter receives Framework correlation IDs: False / PASS expected
capability source: RealtimeVoiceOutputCapability
generation_cancel_supported: False / truthful
provider_hard_cancel_supported: False / truthful
stable package exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-6a tasks: 6 / 6 ACCEPTED-CANDIDATE
pending queue changed: False
artifact invalidation changed: False
host playback ownership changed: False
provider/network/microphone/playback/real VTS execution: False
next checkpoint: FW-RT6-6b / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C closes the six FW-RT6-6a aggregate task checkboxes only as an
acceptance candidate after the accepted Control A identity/protocol boundary and
Control B provider-adoption/active-generation boundary are reviewed together.
No new runtime behavior is introduced by Control C.

Roadmap P0-5 remains split across later tasks: opaque artifact storage is
FW-RT6-6b, bounded pending work is FW-RT6-6c, active cancellation / artifact
invalidation / future-delivery suppression are FW-RT6-6d, and host playback
coordination is FW-RT6-6e. None of those later capabilities are inferred from
FW-RT6-6a acceptance.
<!-- FW-RT6-6a-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-6a-C-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6a Control C — aggregate acceptance sync

```text
checkpoint: FW-RT6-6a Control C
implementation commit: ee5ce2007856fa27f16ff4edfe17a1106a789e94
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control C surface: 3 files
aggregate gate: PASS
Control A regression: PASS
Control B regression: PASS
full Framework unit suite: 290 / PASS
generation identity: True / PASS
active generation observable: True / PASS
active generation thread-safe: True / PASS
provider details public: False / PASS
provider adapter receives Framework correlation IDs: False / PASS
capability source: RealtimeVoiceOutputCapability
generation_cancel_supported: False / TRUTHFUL
provider_hard_cancel_supported: False / TRUTHFUL
stable package exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-6a tasks: 6 / 6 ACCEPTED
FW-RT6-6a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
later P0-5 capabilities inferred: False
roadmap P0-5 changed: False
next checkpoint: FW-RT6-6b
FW-RT6-6b exact contract review: AUTHORIZED
FW-RT6-6b implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-6a is accepted as the provider-neutral voice-output generation protocol
boundary. This acceptance closes only generation identity, provider-adapter
adoption, active-generation observability, privacy, and truthful capability
reporting. It does not claim opaque artifact storage, pending-queue behavior,
active synthesis cancellation, artifact invalidation, future-delivery
suppression, or host playback control.

The next authorized activity is FW-RT6-6b exact contract review. FW-RT6-6b
implementation remains separately gated until that review is completed and an
implementation control is explicitly authorized.
<!-- FW-RT6-6a-C-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-6b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6b Control A — opaque artifact store acceptance sync

```text
checkpoint: FW-RT6-6b Control A
baseline head: 5318f89aeb524f91f7c388816058bb0e8a3e2fc0
implementation commit: d01cb6bd168b8b542d7cf7dc8f0c396d28aeb937
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control A surface: 5 files
dedicated gate: PASS
existing artifact-result compatibility: PASS
FW-RT6-6a aggregate regression: PASS
full Framework unit suite: 290 / PASS
stable package: framework.voice_artifacts
stable package exports: 4
opaque artifact ID: fw_voice_artifact_<32 lowercase hex>
store lifecycle: resolve / open / delete / expire
generation binding primitive: True
provider adapter receives GenerationId: False
root-public names: 127 / UNCHANGED
real provider path leak corrected: False / CONTROL B
pending queue changed: False
generation cancel / invalidation changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6b aggregate: NOT_COMPLETED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B: AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the provider-neutral artifact-store foundation only. The seven
FW-RT6-6b aggregate task checkboxes remain open until provider adoption and final
aggregate acceptance are completed.

Control B is authorized to replace the real-provider `str(artifact_path)` handoff
with `VoiceArtifactStore` / `VoiceArtifactRef`, enforce the exactly-one generated
audio handoff boundary, and bind returned artifact references to lifecycle
generation at the Framework synthesis-stage side. Provider adapters must continue
to receive no Framework session, turn, generation, or synthesis-work identities.

The roadmap P0-5 split is unchanged. Bounded pending work remains FW-RT6-6c,
active cancellation / interrupt-driven artifact invalidation / future-delivery
suppression remain FW-RT6-6d, and host playback remains FW-RT6-6e.
<!-- FW-RT6-6b-A-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6b Control B — provider artifact-store adoption acceptance sync

```text
checkpoint: FW-RT6-6b Control B
baseline head: d9f4a562728ba1c63b82c83f4ff5826cf900f9b0
implementation commit: 0719880b0caab9c69038b50d000f17a128d5d062
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control B surface: 7 files
dedicated gate: PASS
accepted Control A package/store foundation regression: PASS
artifact-result contract: PASS
FW-RT6-6a aggregate regression: PASS
full Framework unit suite: 290 / PASS
real provider path leak corrected: True
provider result artifact type: VoiceArtifactRef
generated exactly-one audio handoff: ENFORCED
raw local path in VoiceOutputResult: False
stage-side lifecycle generation binding: True
provider adapter receives Framework correlation IDs: False
stable framework.voice_artifacts exports: 4 / UNCHANGED
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
pending queue changed: False
generation cancel / artifact invalidation changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6b aggregate: NOT_COMPLETED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C: AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the real-provider opaque artifact handoff correction and the
Framework synthesis-stage generation-binding boundary. Real provider output no
longer exposes `str(artifact_path)` through `VoiceOutputResult`; generated
artifact handoff uses `VoiceArtifactRef`, and generated results enforce exactly
one public audio handoff.

The accepted FW-RT6-6a provider protocol remains correlation-free. Session,
turn, lifecycle-generation, and synthesis-work identities are not passed into
provider adapters. Lifecycle `GenerationId` binding occurs only after provider
synthesis returns, on the Framework synthesis-stage side.

The seven FW-RT6-6b aggregate task checkboxes remain open. Control C is
authorized for aggregate acceptance only: review accepted Control A+B together,
run the dedicated FW-RT6-6b aggregate gate and regressions, and close the seven
aggregate task checkboxes only if that aggregate review passes. Control C must
not add provider runtime behavior.

The roadmap P0-5 split is unchanged. Bounded pending work remains FW-RT6-6c;
active synthesis cancellation, interrupt-driven artifact invalidation, and
future-delivery suppression remain FW-RT6-6d; host playback coordination remains
FW-RT6-6e.
<!-- FW-RT6-6b-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6b Control C — opaque artifact-store aggregate acceptance

```text
checkpoint: FW-RT6-6b Control C
baseline head: 163ad7c7a611221148dd1bc5a902685615caaf16
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
status: IMPLEMENTED / AWAITING_REVIEW
exact Control C delta: 3 files
Control B dedicated regression: PASS expected
artifact-result contract regression: PASS expected
FW-RT6-6a aggregate regression: PASS expected
full Framework unit suite: 290 / PASS expected
VoiceArtifactStore protocol: PASS expected
opaque artifact ID: PASS expected
internal path / public ref separation: PASS expected
resolve / open / delete / expire: PASS expected
generated exactly-one audio handoff: PASS expected
real provider local-path handoff: False expected
lifecycle generation / artifact validity association: PASS expected
expired/deleted artifact playable: False expected
interrupt-driven artifact invalidation: DEFERRED / FW-RT6-6d
provider adapter receives Framework correlation IDs: False expected
stable framework.voice_artifacts exports: 4 / UNCHANGED
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-6b tasks: 7 / 7 ACCEPTED-CANDIDATE
pending queue changed: False
generation cancel / interrupt invalidation changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
next checkpoint: FW-RT6-6c / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C closes the seven FW-RT6-6b aggregate task checkboxes only as an
acceptance candidate after the accepted Control A artifact-store foundation and
Control B provider-adoption/generation-binding boundary are reviewed together.
No new runtime behavior is introduced by Control C.

The aggregate acceptance treats expired/deleted store records as non-playable
artifact validity states. It does not claim interrupt-driven active artifact
invalidation, synthesis cancellation, or future-delivery suppression; those
remain FW-RT6-6d.

The roadmap P0-5 split is unchanged. Bounded pending work remains FW-RT6-6c,
active synthesis cancellation / interrupt-driven artifact invalidation /
future-delivery suppression remain FW-RT6-6d, and host playback coordination
remains FW-RT6-6e.
<!-- FW-RT6-6b-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6b-C-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6b Control C — aggregate acceptance sync

```text
checkpoint: FW-RT6-6b Control C
implementation commit: 90374b3522d4b5ea590c3a581d20ec36e2a5db7c
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control C surface: 3 files
aggregate gate: PASS
Control B regression: PASS
artifact-result contract regression: PASS
FW-RT6-6a aggregate regression: PASS
full Framework unit suite: 290 / PASS
VoiceArtifactStore protocol: PASS
opaque artifact ID: PASS
internal path / public ref separation: PASS
resolve / open / delete / expire: PASS
generated exactly-one audio handoff: PASS
real provider local-path handoff: False / PASS
lifecycle generation / artifact validity association: PASS
expired/deleted artifact playable: False / PASS
interrupt-driven artifact invalidation: DEFERRED / FW-RT6-6d
provider adapter receives Framework correlation IDs: False / PASS
stable framework.voice_artifacts exports: 4 / UNCHANGED
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-6b tasks: 7 / 7 ACCEPTED
FW-RT6-6b aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
pending queue changed: False
generation cancel / interrupt invalidation changed: False
host playback changed: False
later P0-5 capabilities inferred: False
roadmap P0-5 changed: False
provider/network/microphone/playback/real VTS execution: False
next checkpoint: FW-RT6-6c
FW-RT6-6c exact contract review: AUTHORIZED
FW-RT6-6c implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-6b is accepted as the opaque voice-artifact storage and handoff
boundary. Public voice-output results no longer expose real-provider local
filesystem paths; generated artifact handoff uses opaque `VoiceArtifactRef`,
store lifecycle and validity are explicit, and lifecycle generation association
occurs on the Framework synthesis-stage side without passing Framework
correlation identities into provider adapters.

This acceptance does not claim bounded pending work, active synthesis
cancellation, interrupt-driven artifact invalidation, future-delivery
suppression, or host playback coordination. Those remain separately gated by
FW-RT6-6c, FW-RT6-6d, and FW-RT6-6e.

The next authorized activity is FW-RT6-6c exact contract review. FW-RT6-6c
implementation remains separately gated until that review is completed and an
implementation control is explicitly authorized.
<!-- FW-RT6-6b-C-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6c-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6c Control A — bounded pending queue acceptance sync

```text
checkpoint: FW-RT6-6c Control A
baseline head: 3bdd196c34d2ffd3eaa2dfc30cc39cf22aa34409
implementation commit: b2b516afd1f5102047594e698f3ad9ebc011575c
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control A surface: 5 files
dedicated gate: PASS
accepted FW-RT6-6b aggregate regression: PASS
full Framework unit suite: 290 / PASS
stable package: framework.realtime_voice_output_queue
stable package exports: 8
bounded pending queue: True / PASS
configurable max pending depth: True / PASS
pending item correlation: session / turn / generation / work / PASS
enqueue typed result: True / PASS
silent drop: False / PASS
pending clear: True / PASS
active generation cancelled by pending clear: False / PASS
overflow event: True / PASS
provider pending_flush_supported changed: False
generation cancel changed: False
artifact invalidation changed: False
host playback changed: False
root-public names: 127 / UNCHANGED
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6c aggregate: NOT_COMPLETED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B: AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts only the bounded pending-queue foundation. The seven
FW-RT6-6c aggregate task checkboxes remain open until pending-to-active adoption
and final aggregate acceptance are completed.

Control B is authorized to compose the accepted pending queue with the accepted
voice-synthesis stage boundary. Pending work must leave the queue before it
becomes active, and the enqueue-time `SynthesisWorkId` must be preserved as the
same active work identity rather than allocating a second unrelated work ID.
The active generation remains stage-owned, pending clear must not alter active
generation state, and provider adapters must continue to receive no Framework
session, turn, generation, or synthesis-work identities.

Generation cancellation, interrupt-driven artifact invalidation, future-delivery
suppression, and provider cancel timeout remain FW-RT6-6d. Host playback
coordination remains FW-RT6-6e. Control B is not authorized to claim those later
P0-5 capabilities.
<!-- FW-RT6-6c-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-6c-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6c Control B — pending-to-active handoff acceptance sync

```text
checkpoint: FW-RT6-6c Control B
baseline head: 820056ff897e7bfdcfa20c3f7d4b14df0633c3b1
implementation commit: ae456c2f8ed4ed27c835907ab5f71f495cd5c395
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control B surface: 7 files
dedicated gate: PASS
accepted Control A regression: PASS
accepted FW-RT6-6a active-stage regression: PASS
full Framework unit suite: 290 / PASS
same enqueue/active/result SynthesisWorkId: PRESERVED / PASS
pending state owner: pending queue / PASS
active state owner: synthesis stage / PASS
same work simultaneously pending and active: False / PASS
closed/busy stage claim mutates pending FIFO: False / PASS
provider failure silently requeues claimed work: False / PASS
pending clear changes active generation: False / PASS
provider adapter receives Framework correlation IDs: False / PASS
stable framework.realtime_voice_output_queue exports: 8 / UNCHANGED
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
provider pending_flush_supported changed: False
generation cancel changed: False
artifact invalidation changed: False
future-delivery suppression changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6c aggregate: NOT_COMPLETED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C: AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the pending-to-active ownership transition only. The accepted
bounded queue retains pending ownership, the accepted synthesis stage retains
active ownership, and one enqueue-time `SynthesisWorkId` is preserved through
claim, active observation, and the result envelope without a second work-ID
allocation.

The seven FW-RT6-6c aggregate task checkboxes remain open until Control C reviews
Control A+B together and closes the bounded-queue aggregate. Control C is
therefore authorized as aggregate acceptance work; it is not authorized to add
new runtime capability beyond the accepted Control A+B surface.

Generation cancellation, provider cancel timeout, interrupt-driven artifact
invalidation, and future-delivery suppression remain FW-RT6-6d. Host playback
coordination remains FW-RT6-6e. No later P0-5 capability is inferred by this
acceptance sync.
<!-- FW-RT6-6c-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6c Control C — bounded voice-output queue aggregate acceptance

```text
checkpoint: FW-RT6-6c Control C
baseline head: 647191b7b939587c9977279dd446e16e90bfb4b3
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
status: IMPLEMENTED / AWAITING_REVIEW
exact Control C delta: 3 files
Control A queue regression: PASS expected
Control B handoff regression: PASS expected
FW-RT6-6a active-stage regression: PASS expected
FW-RT6-6b artifact-store aggregate regression: PASS expected
full Framework unit suite: 290 / PASS expected
bounded pending queue: PASS expected
configurable max pending depth: PASS expected
pending item correlation: session / turn / generation / work / PASS expected
enqueue typed accepted/rejected result: PASS expected
silent overflow drop: False expected
overflow event: PASS expected
pending clear: PASS expected
pending / active ownership separation: PASS expected
same enqueue/active/result SynthesisWorkId: PRESERVED expected
same work simultaneously pending and active: False expected
closed/busy stage claim mutates pending FIFO: False expected
provider failure silently requeues claimed work: False expected
pending clear changes active generation: False expected
active cancel overclaim: False expected
provider adapter receives Framework correlation IDs: False expected
stable framework.realtime_voice_output_queue exports: 8 / UNCHANGED
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-6c tasks: 7 / 7 ACCEPTED-CANDIDATE
provider pending_flush_supported changed: False
generation cancel changed: False
artifact invalidation changed: False
future-delivery suppression changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
next checkpoint: FW-RT6-6d / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C closes the seven FW-RT6-6c aggregate task checkboxes only as an
acceptance candidate after the accepted Control A bounded queue and Control B
pending-to-active handoff are reviewed together. No new runtime behavior is
introduced by Control C.

The accepted aggregate distinguishes queue-owned pending clear from stage-owned
active synthesis. The enqueue-time `SynthesisWorkId` remains the same identity
when work becomes active and when the synthesis result envelope is returned.

Active synthesis cancellation, provider cancel timeout, provider hard-cancel
result, interrupt-driven artifact invalidation, future-delivery suppression, and
late-artifact stale rejection remain FW-RT6-6d. Host playback coordination
remains FW-RT6-6e. No later P0-5 capability is inferred by this aggregate.
<!-- FW-RT6-6c-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6c-C-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6c Control C — aggregate acceptance sync

```text
checkpoint: FW-RT6-6c Control C
implementation commit: d6bd0e82f4f21526208fd23bb64f13cce201ed11
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control C surface: 3 files
aggregate gate: PASS
Control A queue regression: PASS
Control B handoff regression: PASS
FW-RT6-6a active-stage regression: PASS
FW-RT6-6b artifact-store aggregate regression: PASS
full Framework unit suite: 290 / PASS
bounded pending queue: PASS
configurable max pending depth: PASS
pending item correlation: session / turn / generation / work / PASS
enqueue typed accepted/rejected result: PASS
silent overflow drop: False / PASS
overflow event: PASS
pending clear: PASS
pending / active ownership separation: PASS
same enqueue/active/result SynthesisWorkId: PRESERVED / PASS
same work simultaneously pending and active: False / PASS
closed/busy stage claim mutates pending FIFO: False / PASS
provider failure silently requeues claimed work: False / PASS
pending clear changes active generation: False / PASS
active cancel overclaim: False / PASS
provider adapter receives Framework correlation IDs: False / PASS
stable framework.realtime_voice_output_queue exports: 8 / UNCHANGED
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-6c tasks: 7 / 7 ACCEPTED
FW-RT6-6c aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
provider pending_flush_supported changed: False
generation cancel changed: False
artifact invalidation changed: False
future-delivery suppression changed: False
host playback changed: False
later P0-5 capabilities inferred: False
roadmap P0-5 changed: False
provider/network/microphone/playback/real VTS execution: False
next checkpoint: FW-RT6-6d
FW-RT6-6d exact contract review: AUTHORIZED
FW-RT6-6d implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-6c is accepted as the bounded voice-output work-queue boundary.
Framework-owned pending work is bounded and non-silent on overflow, pending and
active synthesis ownership are distinct, and the enqueue-time `SynthesisWorkId`
is preserved through pending-to-active handoff and the result envelope.

This acceptance does not claim active synthesis cancellation, provider cancel
timeout or hard-cancel completion, interrupt-driven artifact invalidation,
future-delivery suppression, or late-artifact stale rejection; those remain
FW-RT6-6d. Host playback coordination remains FW-RT6-6e.

The next authorized activity is FW-RT6-6d exact contract review. FW-RT6-6d
implementation remains separately gated until that review is completed and an
implementation control is explicitly authorized.
<!-- FW-RT6-6c-C-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6d-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6d Control A — typed cancel-result foundation acceptance sync

```text
checkpoint: FW-RT6-6d Control A
baseline head: 3613056b798bd0a46ecee87a252ed5f36156a67d
implementation commit: 0bd5d10d0f00f86db5a534b721ee05b1b3c8e22c
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control A surface: 6 files
dedicated gate: PASS
accepted FW-RT6-6a regression: PASS
accepted FW-RT6-6c regression: PASS
full Framework unit suite: 290 / PASS
typed cancel outcomes: REQUESTED / COMPLETED / TIMED_OUT / PASS
cooperative cancel completion fact: TYPED / PASS
provider hard cancel applied/unsupported: DISTINGUISHED / PASS
artifact invalidation result fact: TYPED / PASS
future delivery suppression result fact: TYPED / PASS
active cancel execution changed: False
provider cancel timeout execution changed: False
provider hard cancel execution changed: False
artifact invalidation execution changed: False
future delivery suppression execution changed: False
RealtimeSession changed: False
pending queue changed: False
stable framework.realtime_voice_output exports: 7 / UNCHANGED
root-public names: 127 / UNCHANGED
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6d aggregate: NOT_COMPLETED
FW-RT6-6d tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B: AUTHORIZED
Control B implementation: NOT_STARTED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts only the typed voice-synthesis cancellation-result foundation.
It adds truthful result vocabulary for cooperative request/completion, timeout,
provider hard-cancel applied versus unsupported, artifact invalidation, and
future-delivery suppression without claiming that any of those runtime effects
are executed by the current synthesis stage.

The seven FW-RT6-6d aggregate task checkboxes remain open. Control B is
authorized to implement the runtime adoption boundary: active synthesis
cooperative cancellation, bounded cancellation completion/timeout handling,
truthful provider hard-cancel result recording, completed-artifact invalidation,
future-delivery suppression, stale late-artifact rejection through the existing
generation gate, and idempotent duplicate cancel/flush behavior.

Current provider capability truth remains authoritative. Unsupported provider
hard cancel must remain reported as unsupported rather than inferred from a
cooperative Framework cancellation. Host playback coordination remains
FW-RT6-6e and is not authorized by this acceptance.
<!-- FW-RT6-6d-A-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6d-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6d Control B — cancellation / invalidation runtime adoption acceptance sync

```text
checkpoint: FW-RT6-6d Control B
baseline head: 5e26f29847a357225a29c724c6014aa15ff1c83d
implementation commit: 32c78a4a7b437f11fb41638a08a7b5138bcd01cc
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control B surface: 6 files
dedicated gate: PASS
Control A typed cancel-result foundation: PASS
accepted FW-RT6-6a/6b/6c regressions: PASS
full Framework unit suite: 290 / PASS
active cooperative cancel: PASS
bounded cancel timeout: PASS
provider hard cancel applied: False / TRUTHFUL
provider hard cancel unsupported: True / PASS
completed artifact invalidation: PASS
invalidated artifact playable: False / PASS
future delivery suppression: PASS
late artifact stale guard: existing RealtimeGenerationGate / PASS
new freshness registry: False / PASS
duplicate cancel: IDEMPOTENT / PASS
duplicate flush: IDEMPOTENT / PASS
pending clear vs active cancel: DISTINGUISHED / PASS
provider capability changed: False
RealtimeSession changed: False
host playback changed: False
stable framework.realtime_voice_output exports: 7 / UNCHANGED
stable framework.voice_artifacts exports: 4 / UNCHANGED
stable framework.realtime_voice_output_queue exports: 8 / UNCHANGED
root-public names: 127 / UNCHANGED
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6d aggregate: NOT_COMPLETED
FW-RT6-6d tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C: AUTHORIZED
Control C implementation: NOT_STARTED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the Framework-owned runtime cancellation / invalidation
reference composition. Active synthesis cancellation is cooperative and installs
a one-way future-delivery suppression barrier before the bounded completion wait.
Current provider transport hard cancel remains truthfully unsupported and is not
inferred from Framework-cooperative cancellation.

Completed Framework-owned generation-bound artifacts can be invalidated and
become non-playable. Late synthesis completion reuses the existing
`RealtimeGenerationGate` freshness decision rather than introducing a second
registry. Pending clear remains distinct from active cancellation, and duplicate
cancel / flush behavior is idempotent.

The seven FW-RT6-6d aggregate task checkboxes remain open. Control C is
authorized for aggregate acceptance only: review accepted Control A+B together,
run the dedicated FW-RT6-6d aggregate gate and regressions, and close the seven
aggregate task checkboxes only if that aggregate review passes. Control C must
not add new runtime behavior.

Host playback coordination and physical playback stop remain FW-RT6-6e.
Guarded real-runtime composition remains separately gated by the later roadmap.
<!-- FW-RT6-6d-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6d-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6d Control C — generation cancel / artifact invalidation aggregate acceptance

```text
checkpoint: FW-RT6-6d Control C
baseline head: 663a23b4485a96a75e5a3dfb1ab70c15517e0fc2
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
status: IMPLEMENTED / AWAITING_REVIEW
exact Control C delta: 3 files
aggregate gate: PASS expected
Control A typed-result regression: PASS expected
Control B runtime cancellation regression: PASS expected
FW-RT6-6a synthesis-generation regression: PASS expected
FW-RT6-6b artifact-store regression: PASS expected
FW-RT6-6c bounded-queue regression: PASS expected
full Framework unit suite: 290 / PASS expected
active synthesis cooperative cancel: PASS expected
provider cancel timeout: BOUNDED / PASS expected
provider hard cancel applied: False / TRUTHFUL expected
provider hard cancel unsupported: True / PASS expected
completed artifact invalidation: PASS expected
invalidated artifact playable: False expected
future delivery suppression: PASS expected
late artifact stale guard: existing RealtimeGenerationGate / PASS expected
new freshness registry: False expected
duplicate cancel: IDEMPOTENT / PASS expected
duplicate flush: IDEMPOTENT / PASS expected
pending clear vs active cancel: DISTINGUISHED / PASS expected
stable framework.realtime_voice_output exports: 7 / UNCHANGED
stable framework.voice_artifacts exports: 4 / UNCHANGED
stable framework.realtime_voice_output_queue exports: 8 / UNCHANGED
root-public names: 127 / UNCHANGED
Control C runtime implementation changed: False
provider capability source changed: False
RealtimeSession changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6d tasks: 7 / 7 ACCEPTED-CANDIDATE
FW-RT6-6d aggregate: IMPLEMENTED / AWAITING_REVIEW
next checkpoint: FW-RT6-6e / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C introduces no new runtime behavior. It closes the seven FW-RT6-6d
aggregate task checkboxes only as an acceptance candidate after the accepted
Control A typed-result foundation and Control B cancellation/invalidation runtime
adoption are reviewed together.

The aggregate preserves the distinction between Framework-cooperative synthesis
cancellation and provider transport hard cancel. Current provider hard cancel
remains truthfully unsupported. Cancellation installs a one-way future-delivery
barrier; completed or late generation-bound Framework artifacts become
non-playable when invalidated, and late completion reuses the existing
`RealtimeGenerationGate` freshness source.

Pending clear remains separate from active cancellation. Duplicate cancel and
flush converge idempotently. Host playback coordination and physical playback
stop remain FW-RT6-6e; this aggregate does not claim host playback success.

FW-RT6-6e is not authorized by this candidate. Its exact contract review remains
separately gated after FW-RT6-6d aggregate acceptance and source-of-truth sync.
<!-- FW-RT6-6d-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6d-C-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6d Control C — aggregate acceptance sync

```text
checkpoint: FW-RT6-6d Control C
aggregate implementation commit: 45e9b7d789ae4ae0fc03f4e2ed0956de9195ee5a
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control C surface: 3 files
aggregate gate: PASS
Control A typed-result regression: PASS
Control B runtime cancellation regression: PASS
FW-RT6-6a synthesis-generation regression: PASS
FW-RT6-6b artifact-store regression: PASS
FW-RT6-6c bounded-queue regression: PASS
full Framework unit suite: 290 / PASS
active synthesis cooperative cancel: PASS
provider cancel timeout: BOUNDED / PASS
provider hard cancel applied: False / TRUTHFUL
provider hard cancel unsupported: True / PASS
completed artifact invalidation: PASS
invalidated artifact playable: False / PASS
future delivery suppression: PASS
late artifact stale guard: existing RealtimeGenerationGate / PASS
new freshness registry: False / PASS
duplicate cancel: IDEMPOTENT / PASS
duplicate flush: IDEMPOTENT / PASS
pending clear vs active cancel: DISTINGUISHED / PASS
stable framework.realtime_voice_output exports: 7 / UNCHANGED
stable framework.voice_artifacts exports: 4 / UNCHANGED
stable framework.realtime_voice_output_queue exports: 8 / UNCHANGED
root-public names: 127 / UNCHANGED
Control C runtime implementation changed: False
provider capability source changed: False
RealtimeSession changed: False
host playback changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6d tasks: 7 / 7 ACCEPTED
FW-RT6-6d aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
FW-RT6-6e tasks: 0 / 6 CLOSED
next checkpoint: FW-RT6-6e
FW-RT6-6e exact contract review: AUTHORIZED
FW-RT6-6e implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-6d is accepted as the Framework-owned generation-cancel and artifact-
invalidation boundary. Framework-cooperative cancellation remains distinct from
provider transport hard cancel; current provider hard cancel is truthfully
unsupported and is not inferred from cooperative completion.

Cancellation establishes a one-way future-delivery suppression barrier.
Completed or late generation-bound Framework artifacts become non-playable when
invalidated. Late completion freshness continues to use the existing
`RealtimeGenerationGate` rather than a second registry. Pending clear remains
distinct from active cancellation, and duplicate cancel / flush are idempotent.

This acceptance does not claim host physical playback stop. Host playback
coordination remains FW-RT6-6e. The resulting synchronized state authorizes only
FW-RT6-6e exact contract review; FW-RT6-6e implementation remains separately
gated and not authorized.
<!-- FW-RT6-6d-C-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6e-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6e Control A — host playback foundation acceptance sync

```text
checkpoint: FW-RT6-6e Control A
baseline head: cff06c92cbf1e25e128c02bcbefcc2cfe98d3125
implementation commit: 855cbe09bd9be07f13d02d7a6cb368a11a87714f
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control A surface: 9 files
dedicated gate: PASS
FW-RT6-6d aggregate regression: PASS
full Framework unit suite: 290 / PASS
playback ownership capability: TYPED / PASS
current public playback ownership: host / PASS
host stop request event: PASS
host stop acknowledgement contract: OPTIONAL / PASS
host stop request implies physical stop: False / PASS
host stop acknowledgement implies physical stop: False / PASS
artifact invalidation implies physical stop: False / PASS
legacy VoiceEngine / ffplay root-public: False / PASS
RealtimeSession changed: False
legacy VoiceEngine / ffplay runtime changed: False
framework root-public names: 127 / UNCHANGED
framework.realtime_capabilities exports: 7 / UNCHANGED
framework.realtime_event_payloads exports: 10 / UNCHANGED
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6e aggregate: NOT_COMPLETED
FW-RT6-6e tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B: AUTHORIZED
Control B implementation: NOT_STARTED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the typed playback-ownership and canonical host-stop
coordination vocabulary only. Current public voice-output artifact handoff is
host-owned. A Framework host-stop request and an optional host acknowledgement
are coordination facts and must not be represented as confirmed physical
playback stop.

The legacy `tts.VoiceEngine` / `ffplay` path remains internal compatibility and
is not promoted into the framework root-public API. `RealtimeSession` runtime
host-stop emission, acknowledgement ingestion, legacy-local-player isolation /
deprecation wiring, and any FW-owned playback adapter remain Control B work.

The six FW-RT6-6e aggregate task checkboxes remain open. Control B is authorized
to implement the runtime coordination boundary while preserving the accepted
truthfulness rule that host-owned physical stop success is never inferred.
<!-- FW-RT6-6e-A-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6e-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6e Control B — host playback runtime coordination acceptance sync

```text
checkpoint: FW-RT6-6e Control B
baseline head: 6c1d920fb8c15d3f66eed58a8a35c506224dc66e
implementation commit: 16f88c2e2fe2591c330f446c4808876b86368e9e
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control B surface: 8 files
dedicated gate: PASS
Control A model/event/stable-boundary regression: PASS
FW-RT6-6d aggregate regression: PASS
full Framework unit suite: 290 / PASS
session/global/provider playback ownership: host / PASS
host stop request runtime: PASS
host stop acknowledgement runtime: OPTIONAL / PASS
post-terminal host acknowledgement: PASS
duplicate host acknowledgement: IDEMPOTENT / PASS
empty mock NOTHING_TO_FLUSH behavior: PRESERVED / PASS
artifact invalidation event: AUDIO_INVALIDATED / PASS
host stop request implies physical stop: False / PASS
host stop acknowledgement implies physical stop: False / PASS
artifact invalidation implies physical stop: False / PASS
unsupported queue flush promoted to FLUSHED by host request: False / PASS
legacy VoiceEngine / ffplay root-public: False / PASS
legacy local player status: deprecated_internal_compatibility
legacy v6.0.0 removal: False
legacy future removal policy: future major only with migration notice
physical playback execution: False
provider/network/microphone/real VTS execution: False
FW-RT6-6e aggregate: NOT_COMPLETED
FW-RT6-6e tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C: AUTHORIZED
Control C implementation: NOT_STARTED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the runtime coordination boundary for host-owned playback.
`RealtimeSession` may emit a canonical host-stop request when playback stopping
is actually required by the queue snapshot, and may record an optional host
acknowledgement for that request. Neither fact is represented as confirmed
physical playback stop.

The accepted FW-RT6-6d artifact invalidation result may now be projected as
`AUDIO_INVALIDATED` without creating a second artifact lifecycle registry.
Artifact invalidation remains separate from host physical playback stop.

The existing `tts.VoiceEngine` / `ffplay` path remains usable only as deprecated
internal compatibility for the legacy runtime during v6.0.0. It is not promoted
to the Framework root-public API or used as the v6 playback capability source.

The six FW-RT6-6e aggregate task checkboxes remain open. Control C is authorized
for aggregate acceptance only: review accepted Control A+B together, run the
dedicated aggregate gate and regressions, and close the six aggregate task
checkboxes only if the aggregate review passes. Control C must not add new
runtime behavior.
<!-- FW-RT6-6e-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-6e-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-6e Control C — host playback boundary aggregate acceptance

```text
checkpoint: FW-RT6-6e Control C
baseline head: eefa693ff3453e43d4341270bf92d780f370a477
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
status: IMPLEMENTED / AWAITING_REVIEW
exact Control C surface: 3 files
aggregate gate: PASS expected
Control A model/event/stable-boundary regression: PASS expected
Control B runtime coordination regression: PASS expected
FW-RT6-6d cancellation/invalidation boundary: PRESERVED expected
full Framework unit suite: 290 / PASS expected
FW-owned vs host-owned playback: TYPED / PASS expected
current public playback ownership: host / PASS expected
host stop request event/runtime: PASS expected
host acknowledgement: OPTIONAL / PASS expected
post-terminal host acknowledgement: PASS expected
duplicate host acknowledgement: IDEMPOTENT / PASS expected
empty mock NOTHING_TO_FLUSH behavior: PRESERVED / PASS expected
artifact invalidation emitted: AUDIO_INVALIDATED / PASS expected
host playback physical stop claimed: False expected
host stop request implies physical stop: False expected
host stop acknowledgement implies physical stop: False expected
artifact invalidation implies physical stop: False expected
legacy VoiceEngine / ffplay root-public: False expected
legacy local player status: deprecated_internal_compatibility expected
legacy v6.0.0 removal: False expected
legacy removal policy: future major only with migration notice expected
root-public names: 127 / UNCHANGED
runtime source changed: False
provider capability runtime source changed: False
RealtimeSession runtime source changed: False
legacy VoiceEngine runtime source changed: False
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6e tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-6e aggregate: IMPLEMENTED / AWAITING_REVIEW
FW-RT6-7a tasks: 0 / 6 CLOSED
next checkpoint: FW-RT6-7a / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C introduces no new runtime behavior. The six FW-RT6-6e task checkboxes
are closed only as an aggregate acceptance candidate after the accepted Control A
typed playback-ownership/event foundation and Control B host-playback runtime
coordination are reviewed together.

Host-owned playback remains physically controlled by the host. A Framework
stop-request event, optional host acknowledgement, and Framework artifact
invalidation are separate coordination/lifecycle facts and never imply confirmed
speaker or media-engine stop.

The legacy `tts.VoiceEngine` / `ffplay` path remains deprecated internal
compatibility for v6.0.0, remains outside the Framework root-public API, and is
not the v6 playback capability source. Removal is deferred to a future major
version with migration notice.

FW-RT6-7a remains unopened and unauthorized by this candidate.
<!-- FW-RT6-6e-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-6e-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-6e — host playback boundary final acceptance sync

```text
checkpoint: FW-RT6-6e final acceptance
baseline head: 16880f442c51ead05ed33f613a5c37177fa28cf3
Control A implementation: 855cbe09bd9be07f13d02d7a6cb368a11a87714f
Control A acceptance sync: 6c1d920fb8c15d3f66eed58a8a35c506224dc66e
Control B implementation: 16f88c2e2fe2591c330f446c4808876b86368e9e
Control B acceptance sync: eefa693ff3453e43d4341270bf92d780f370a477
Control C aggregate implementation: 16880f442c51ead05ed33f613a5c37177fa28cf3
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
aggregate gate: PASS
full Framework unit suite: 290 / PASS
root-public names: 127 / UNCHANGED
runtime source changed by Control C: False
FW-owned vs host-owned playback: TYPED / PASS
current public playback ownership: host / PASS
host stop request event/runtime: PASS
host acknowledgement: OPTIONAL / PASS
post-terminal host acknowledgement: PASS
duplicate host acknowledgement: IDEMPOTENT / PASS
empty mock NOTHING_TO_FLUSH behavior: PRESERVED / PASS
artifact invalidation emitted: AUDIO_INVALIDATED / PASS
host playback physical stop claimed: False / PASS
host stop request implies physical stop: False / PASS
host stop acknowledgement implies physical stop: False / PASS
artifact invalidation implies physical stop: False / PASS
legacy VoiceEngine / ffplay root-public: False / PASS
legacy local player status: deprecated_internal_compatibility
legacy v6.0.0 removal: False
legacy removal policy: future major only with migration notice
provider/network/microphone/playback/real VTS execution: False
FW-RT6-6e tasks: 6 / 6 ACCEPTED
FW-RT6-6e aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
FW-RT6-7a tasks: 0 / 6 CLOSED
FW-RT6-7a exact contract review: AUTHORIZED
FW-RT6-7a implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-6e is accepted as a truthful host-playback coordination boundary.
Framework-owned artifact invalidation, a host playback stop request, and an
optional host acknowledgement remain separate facts. None of them is represented
as confirmed physical host playback stop.

The current public voice-output handoff remains host-owned. The legacy
`tts.VoiceEngine` / `ffplay` path remains deprecated internal compatibility for
v6.0.0 and remains outside the Framework root-public API and v6 capability
source.

This sync closes FW-RT6-6e only. It authorizes FW-RT6-7a exact contract review,
not FW-RT6-7a implementation.
<!-- FW-RT6-6e-FINAL-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-7a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7a Control A — acceptance sync

```text
checkpoint: FW-RT6-7a Control A
baseline head: 3c6053c7082c728a58ad35b626cecb30005440fc
implementation commit: 3c6053c7082c728a58ad35b626cecb30005440fc
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control A surface: 6 files
dedicated gate: PASS
FW-RT6-6e regression subset: PASS
full Framework unit suite: 290 / PASS
OpenAI real executor implementation available: True / PASS
OpenAI stale REAL_STT_NOT_IMPLEMENTED removed: True / PASS
OpenAI supports_real_stt: True / PASS
runtime/provider availability probe performed: False / PASS
provider execution performed: False / PASS
network execution performed: False / PASS
audio read performed by Control A verification: False / PASS
microphone access performed: False / PASS
VoiceInputSessionInfo.api_version central connection: PASS
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
stable VoiceInputSession session_id: PASS
turn/generation correlation scaffold: PASS
canonical realtime-event scaffold: PASS
legacy mapping callbacks changed: False / PASS
VoiceInputResult changed: False / PASS
default fake path: PRESERVED / PASS
provider-neutral automatic fake/real composition: DEFERRED_TO_CONTROL_B
framework root-public names: 127 / UNCHANGED
FW-RT6-7a aggregate: NOT_COMPLETED
FW-RT6-7a tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the capability correction and correlation/event foundation only.

For OpenAI, the Framework now truthfully reports that a real STT executor
implementation exists after the explicit public configuration guards pass.
Capability inspection still does not probe the optional SDK, network, provider
service, private credential value, or actual provider runtime.

The public voice-input default remains mock-safe in Control A. Automatic
provider-neutral fake/real composition is explicitly deferred to Control B.

The six FW-RT6-7a aggregate tasks remain open. This sync authorizes only Control
B exact contract review after the sync commit/push is remotely verified.
<!-- FW-RT6-7a-A-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-7a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7a Control B — acceptance sync

```text
checkpoint: FW-RT6-7a Control B
baseline head: 448e792a245aaffa99fefc8cf24726bfc71c623e
implementation commit: 448e792a245aaffa99fefc8cf24726bfc71c623e
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
exact Control B surface: 6 files
Control B dedicated gate: PASS
Control A source-only regression: PASS
FW-RT6-6e regression subset: PASS
full Framework unit suite: 290 / PASS
default fake path: PASS
explicit adapter precedence: PASS
real STT silent fake fallback: False / PASS
host constructs provider-specific adapter: False / PASS
host constructs provider-specific factory: False / PASS
host constructs provider-specific executor: False / PASS
credential_env private value consumed by runtime: False / PASS
provider-specific Framework modules lazy before executor seam: True / PASS
actual OpenAI SDK imported by acceptance verification: False / PASS
actual provider client created by acceptance verification: False / PASS
network execution during acceptance verification: False / PASS
microphone access during acceptance verification: False / PASS
private auth value exposed: False / PASS
VoiceInputResult changed: False / PASS
FW-RT6-7b lifecycle adopted: False / PASS
FW-RT6-7c result correlation adopted: False / PASS
framework root-public names: 127 / UNCHANGED
Corrective 1: ACCEPTED
Corrective 2 + recovery: ACCEPTED
FW-RT6-7a aggregate: NOT_COMPLETED
FW-RT6-7a tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C aggregate exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts provider-neutral default fake/real selection in
`VoiceInputSession` while preserving explicit adapter precedence and the
mock-safe default path.

A real-STT request is not silently represented as a fake success. OpenAI real
composition reuses the accepted v5.4 runtime chain internally and still requires
the separate provider-execution, SDK-import, client-creation, and actual
real-execution opt-ins plus an explicitly supplied private credential.
`credential_env` remains capability/preflight input and its private value is not
consumed by runtime composition.

Control B does not adopt FW-RT6-7b lifecycle/stage semantics or FW-RT6-7c
`VoiceInputResult` correlation semantics. The six FW-RT6-7a aggregate tasks
remain open.

This sync authorizes only FW-RT6-7a Control C aggregate exact contract review
after the sync commit/push is remotely verified.
<!-- FW-RT6-7a-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-7a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-7a Control C — aggregate capability/composition acceptance

```text
checkpoint: FW-RT6-7a Control C
baseline head: 49558876e9301cddb85830b062a9ef56eeb6cb1e
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C status: IMPLEMENTED / AWAITING_REVIEW
exact Control C surface: 3 files
Control A source-only regression: PASS expected
Control B runtime/source regression: PASS expected
full Framework unit suite: 290 / PASS expected
OpenAI real STT status truthful: True / PASS expected
host constructs provider-specific adapter/factory/executor: False / PASS expected
default fake path: PASS expected
explicit adapter precedence: PASS expected
real request silent fake fallback: False / PASS expected
credential_env private value consumed by runtime: False / PASS expected
runtime/provider availability probe performed: False / PASS expected
provider execution performed: False / PASS expected
network execution performed: False / PASS expected
audio read performed: False / PASS expected
microphone access performed: False / PASS expected
VoiceInputResult changed: False / PASS expected
FW-RT6-7b lifecycle/stage semantics adopted: False / PASS expected
FW-RT6-7c result correlation adopted: False / PASS expected
runtime source changed by Control C: False / PASS expected
framework root-public names: 127 / UNCHANGED expected
FW-RT6-7a tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-7b: NOT_AUTHORIZED
FW-RT6-7c: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C introduces no runtime behavior. It accepts the six FW-RT6-7a tasks
only after reviewing the accepted Control A capability/correlation foundation
and Control B provider-neutral composition together.

The accepted typed lifecycle scope is the additive canonical realtime-event
callback and Framework-owned session/turn/generation scaffold. Preflight,
start, completed, failed and transcript lifecycle emission, input abort, late
generation rejection and path-safe payload work remain FW-RT6-7b.
`VoiceInputResult` correlation and the final v5 callback compatibility bridge
remain FW-RT6-7c.

This candidate does not authorize commit/push or any FW-RT6-7b/7c work.
<!-- FW-RT6-7a-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-7a-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7a — voice-input capability/composition final acceptance sync

```text
checkpoint: FW-RT6-7a final acceptance
baseline head: 582a5ac87a6e8cc011c2d0e481a17cb9fd30d3f8
Control A implementation: 3c6053c7082c728a58ad35b626cecb30005440fc
Control A acceptance sync: 20792e4292fa9b62e44d9b117e9b87f3199c01bf
Control B implementation: 448e792a245aaffa99fefc8cf24726bfc71c623e
Control B acceptance sync: 49558876e9301cddb85830b062a9ef56eeb6cb1e
Control C aggregate implementation: 582a5ac87a6e8cc011c2d0e481a17cb9fd30d3f8
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
full Framework unit suite: 290 / PASS
root-public names: 127 / UNCHANGED
runtime source changed by Control C: False
OpenAI real STT status truthful: True / PASS
VoiceInputSessionInfo.api_version central connection: PASS
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
stable VoiceInputSession session_id: PASS
turn/generation correlation scaffold: PASS
canonical realtime-event callback scaffold: PASS
host constructs provider-specific adapter/factory/executor: False / PASS
default fake path: PASS
explicit adapter precedence: PASS
real request silent fake fallback: False / PASS
credential_env private value consumed by runtime: False / PASS
runtime/provider availability probe performed: False / PASS
provider/network/audio/microphone execution: False / PASS
private credential exposed: False / PASS
VoiceInputResult changed: False / PASS
FW-RT6-7b lifecycle/stage semantics adopted: False / PASS
FW-RT6-7c result correlation adopted: False / PASS
FW-RT6-7a tasks: 6 / 6 ACCEPTED
FW-RT6-7a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED
FW-RT6-7b exact contract review: AUTHORIZED
FW-RT6-7b implementation: NOT_AUTHORIZED
FW-RT6-7c: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-7a is accepted as the truthful public voice-input capability and
provider-neutral composition boundary. OpenAI executor implementation
availability remains distinct from runtime/provider availability, and a normal
host flow does not construct provider-specific Framework objects.

The no-real-STT default remains mock-safe. Real intent with a closed guard
returns a typed unavailable result and never a fake success. Private credential
values remain explicit runtime inputs and are not sourced from `credential_env`
or exposed through public metadata, events or results.

This sync closes FW-RT6-7a only. It authorizes FW-RT6-7b exact contract review,
not FW-RT6-7b implementation. FW-RT6-7c remains unauthorized.
<!-- FW-RT6-7a-FINAL-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-7b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7b Control A — lifecycle/privacy foundation acceptance sync

```text
checkpoint: FW-RT6-7b Control A
baseline head: 2feb3150d2850e320b7bd723791a4e5b00d51ac6
implementation commit: 2feb3150d2850e320b7bd723791a4e5b00d51ac6
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 6 files
dedicated gate: PASS
focused lifecycle/privacy tests: 6 / PASS
full Framework unit suite: 296 / PASS
accepted FW-RT6-7a regression: PASS
event order: preflight/start/completed/transcript-final / PASS
typed lifecycle payloads: PASS
typed final transcript: PASS
stable session/turn/generation event correlation: PASS
FILE_PATH value exposed to public event: False / PASS
raw audio retained by session: False / PASS
adapter exception private detail exposed: False / PASS
default fake path: PASS
explicit adapter path: PASS
real provider composition seam: PRESERVED / PASS
legacy mapping callbacks changed: False / PASS
VoiceInputResult changed: False / PASS
input abort implemented: False / DEFERRED_TO_CONTROL_B
generation-gate admission implemented: False / DEFERRED_TO_CONTROL_B
late transcript rejection implemented: False / DEFERRED_TO_CONTROL_B
FW-RT6-7c result correlation adopted: False / PASS
provider/network/audio/microphone execution: False / PASS
framework root-public names: 127 / UNCHANGED
FW-RT6-7b aggregate: NOT_COMPLETED
FW-RT6-7b tasklist: 0 / 7 CLOSED
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-7c: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the additive voice-input lifecycle and audio-privacy
foundation only. Each host-owned audio request receives one Framework-owned
turn/generation context and emits typed preflight, listening and final
transcript events without changing the existing `VoiceInputResult` contract.

The host `FILE_PATH` value and raw audio remain outside public events and
session retention. Input abort, generation-gate admission and late-transcript
rejection remain Control B work, so all seven FW-RT6-7b aggregate tasks remain
open.

This sync authorizes only Control B exact contract review after the sync
commit/push is remotely verified. It does not authorize Control B
implementation or any FW-RT6-7c work.
<!-- FW-RT6-7b-A-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-7b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7b Control B — input-abort/stale-gate acceptance sync

```text
checkpoint: FW-RT6-7b Control B
baseline head: ec014f0c9a7500323b590e85448d53b74519a031
implementation commit: ec014f0c9a7500323b590e85448d53b74519a031
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B surface: 5 files
dedicated gate: PASS
focused Control A lifecycle/privacy tests: 6 / PASS
focused Control B abort/stale/privacy tests: 7 / PASS
full Framework unit suite: 303 / PASS
accepted FW-RT6-7a regression: PASS
Control A lifecycle/privacy regression: PASS
session-owned RealtimeGenerationGate: PASS
abort with active input first call: True / PASS
abort with no active input: False / PASS
duplicate abort: False / PASS
abort meaning: Framework generation invalidation only / PASS
provider hard-cancel claimed: False / PASS
host capture physical stop claimed: False / PASS
late transcript delivered after abort: False / PASS
late transcript delivered after newer input: False / PASS
late adapter exception exposed after abort: False / PASS
stale completion diagnostic: exactly once / PASS
stale completion payload: DiagnosticEventPayload / PASS
waiting caller stale result: existing interrupted VoiceInputResult / PASS
current-generation success path changed: False / PASS
FILE_PATH value exposed to public event/diagnostic: False / PASS
raw audio retained by session: False / PASS
VoiceInputResult changed: False / PASS
FW-RT6-7c result correlation/close semantics adopted: False / PASS
partial transcript/audio streaming adopted: False / DEFERRED_TO_P1
provider/network/audio/microphone execution: False / PASS
framework root-public names: 127 / UNCHANGED
Control A+B aggregate acceptance candidates: 7 / 7
FW-RT6-7b aggregate: NOT_COMPLETED
FW-RT6-7b tasklist: 0 / 7 CLOSED
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-7c: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts cooperative input abort and session-owned generation
admission without claiming provider hard cancellation or physical host-capture
stopping. An abort or a newer input retires the earlier generation; its late
result or exception cannot publish a final transcript and produces one typed,
path-safe stale diagnostic.

The accepted Control A lifecycle/privacy foundation and Control B abort/stale
gate together cover all seven FW-RT6-7b tasks as aggregate acceptance
candidates. The task checkboxes remain `0 / 7 CLOSED` until Control C performs
the aggregate review and closure.

This sync authorizes only Control C exact contract review after the sync
commit/push is remotely verified. It does not authorize Control C
implementation or any FW-RT6-7c work.
<!-- FW-RT6-7b-B-ACCEPTANCE-SYNC:END -->

<!-- FW-RT6-7b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-7b Control C — aggregate stage-composition acceptance

```text
checkpoint: FW-RT6-7b Control C aggregate acceptance
baseline head: bfe15c03bd9759131d7ef1d39378ce949c3f0970
Control A implementation: 2feb3150d2850e320b7bd723791a4e5b00d51ac6
Control A acceptance sync: 1578a5bac8d6b58c66248bf58d9ed9e246218d1b
Control B implementation: ec014f0c9a7500323b590e85448d53b74519a031
Control B acceptance sync: bfe15c03bd9759131d7ef1d39378ce949c3f0970
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: implemented-awaiting-review
Control C exact surface: 3 files
aggregate gate: PASS expected
focused Control A lifecycle/privacy tests: 6 / PASS expected
focused Control B abort/stale/privacy tests: 7 / PASS expected
full Framework unit suite: 303 / PASS expected
accepted FW-RT6-7a regression: PASS expected
host-owned audio turn/generation correlation: PASS expected
typed lifecycle/final transcript events: PASS expected
input abort generation invalidation: PASS expected
provider hard-cancel claimed: False / PASS expected
host capture physical stop claimed: False / PASS expected
late transcript delivered after abort/newer input: False / PASS expected
stale completion diagnostic: exactly once typed / PASS expected
FILE_PATH value exposed publicly: False / PASS expected
raw audio retained by session: False / PASS expected
default fake and explicit adapter paths: PRESERVED / PASS expected
real provider composition seam: PRESERVED / PASS expected
VoiceInputResult changed: False / PASS expected
framework root-public names: 127 / UNCHANGED expected
runtime source changed by Control C: False
provider/network/audio/microphone execution: False / PASS expected
FW-RT6-7b tasks: 7 / 7 ACCEPTED-CANDIDATE
FW-RT6-7b aggregate: IMPLEMENTED_AWAITING_REVIEW
FW-RT6-7b final acceptance sync: NOT_AUTHORIZED
FW-RT6-7c result correlation/close compatibility: NOT_AUTHORIZED
partial transcript/audio streaming: DEFERRED_TO_P1
commit / push: NOT_AUTHORIZED
```

Control C aggregates the already accepted lifecycle/privacy and
abort/stale-generation controls. Only a current voice-input generation may
publish a final transcript; retired completions are rejected without exposing
the host audio path or raw audio and without claiming provider hard
cancellation.

All seven FW-RT6-7b tasks close here as acceptance candidates. Final
COMPLETED/VERIFIED/ACCEPTED/CLOSED status is deferred to the one-file final
acceptance sync after this candidate is reviewed, committed, pushed, and
remotely verified.

This candidate changes no runtime source and does not authorize FW-RT6-7c or P1
streaming work.
<!-- FW-RT6-7b-C-AGGREGATE-ACCEPTANCE:END -->

<!-- FW-RT6-7b-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7b — voice-input stage composition final acceptance sync

```text
checkpoint: FW-RT6-7b final acceptance
baseline head: e631067ec0dca3ee459ea0ac43cd241a46dcdec5
Control A implementation: 2feb3150d2850e320b7bd723791a4e5b00d51ac6
Control A acceptance sync: 1578a5bac8d6b58c66248bf58d9ed9e246218d1b
Control B implementation: ec014f0c9a7500323b590e85448d53b74519a031
Control B acceptance sync: bfe15c03bd9759131d7ef1d39378ce949c3f0970
Control C aggregate implementation: e631067ec0dca3ee459ea0ac43cd241a46dcdec5
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A lifecycle/privacy tests: 6 / PASS
focused Control B abort/stale/privacy tests: 7 / PASS
full Framework unit suite: 303 / PASS
accepted FW-RT6-7a regression: PASS
framework root-public names: 127 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
host-owned audio turn/generation correlation: PASS
typed preflight/start/completed/failed/final events: PASS
input abort generation invalidation: PASS
provider hard-cancel claimed: False / PASS
host capture physical stop claimed: False / PASS
late transcript delivered after abort/newer input: False / PASS
stale completion diagnostic: exactly once typed / PASS
FILE_PATH value exposed publicly: False / PASS
raw audio retained by session: False / PASS
default fake and explicit adapter paths: PRESERVED / PASS
real provider composition seam: PRESERVED / PASS
VoiceInputResult changed: False / PASS
runtime source changed by Control C: False
provider/network/audio/microphone execution: False / PASS
FW-RT6-7b tasks: 7 / 7 ACCEPTED
FW-RT6-7b aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-7c exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-7c implementation: NOT_AUTHORIZED
partial transcript/audio streaming: DEFERRED_TO_P1
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-7b is accepted as the provider-neutral voice-input stage-composition
boundary. Host-owned audio receives Framework turn/generation correlation,
typed lifecycle/final events, cooperative input abort, and stale-completion
rejection while preserving raw-audio and `FILE_PATH` privacy.

Abort remains Framework generation invalidation only. It does not assert
provider hard cancellation or physical stopping of host capture. The existing
`VoiceInputResult` shape and compatibility behavior remain unchanged.

This sync closes FW-RT6-7b only. It authorizes FW-RT6-7c exact contract review
after the sync commit/push is remotely verified, not FW-RT6-7c implementation.
Partial transcript/audio streaming remains P1 scope.
<!-- FW-RT6-7b-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-7c-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7c Control A — result-correlation acceptance sync

```text
checkpoint: FW-RT6-7c Control A
baseline head: 28b298f1ee70bb114f13782d40c54b536a8174a7
implementation commit: 28b298f1ee70bb114f13782d40c54b536a8174a7
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 7 files
dedicated gate: PASS
focused Control A result-compatibility tests: 8 / PASS
focused FW-RT6-7b lifecycle/privacy tests: 6 / PASS
focused FW-RT6-7b abort/stale/privacy tests: 7 / PASS
full Framework unit suite: 311 / PASS
accepted FW-RT6-7b regression: PASS
legacy VoiceInputResult prefix: 9 fields / SAME ORDER / PASS
additive optional correlation suffix: session_id / turn_id / generation_id / PASS
existing factory call compatibility: PASS
typed Framework identity normalization: PASS
legacy non-Framework session/turn strings: PRESERVED / PASS
turn without session accepted: False / PASS
generation without turn accepted: False / PASS
transcribe_audio_result correlation: PASS
result/event session/turn/generation agreement: PASS
adapter-provided correlation overrides session context: False / PASS
stale/interrupted terminal result correlation: PASS
existing listen_result behavior changed: False / PASS
listen_result correlation adoption: DEFERRED_TO_CONTROL_B
text fallback correlation adoption: DEFERRED_TO_CONTROL_B
legacy mapping callback v6 adapter: DEFERRED_TO_CONTROL_B
unified close rejection correlation: DEFERRED_TO_CONTROL_B
framework root-public names: 127 / UNCHANGED
provider/network/audio/microphone execution: False / PASS
FW-RT6-7c aggregate: NOT_COMPLETED
FW-RT6-7c tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the additive `VoiceInputResult` correlation foundation and
the `transcribe_audio_result()` session-owned result wiring. The original nine
fields retain their order, the three correlation fields are optional and
appended, and existing factory calls remain compatible.

Framework-created result correlation uses the same session, turn and generation
context as canonical voice-input events. Adapter-supplied correlation cannot
replace the session-owned context, and interrupted or stale terminal results
retain the admitted request correlation without exposing host audio data.

`listen_result()` correlation, text fallback, the legacy mapping-callback v6
adapter, and unified close rejection remain Control B work. Therefore all five
FW-RT6-7c aggregate task checkboxes remain open.

This sync authorizes only Control B exact contract review after the sync
commit/push is remotely verified. It does not authorize Control B
implementation.
<!-- FW-RT6-7c-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-7c-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7c Control B — result/callback bridge acceptance sync

```text
checkpoint: FW-RT6-7c Control B
baseline head: 60d1f1b1ac770e8b220c7e7488f536f2332acfb7
implementation commit: 60d1f1b1ac770e8b220c7e7488f536f2332acfb7
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B surface: 6 files
dedicated gate: PASS
focused Control B result/callback compatibility tests: 8 / PASS
focused Control A result-correlation compatibility tests: 8 / PASS
focused FW-RT6-7b lifecycle/privacy tests: 6 / PASS
focused FW-RT6-7b abort/stale/privacy tests: 7 / PASS
full Framework unit suite: 319 / PASS
accepted Control A and FW-RT6-7a/7b regressions: PASS
listen_result correlation: session / turn / generation / PASS
text_fallback_result correlation: session / turn / generation / PASS
legacy mapping callback source: selected canonical v6 events / PASS
legacy mapping shape: type / session_type / payload / PRESERVED
listen legacy mapping order: started / unavailable / PRESERVED
text fallback legacy mapping: text_fallback / PRESERVED
host-audio legacy mapping callback changed: False / PASS
close canonical event: SESSION_CLOSED / exactly once / PASS
close legacy mapping event: voice_input.closed / exactly once / PASS
post-close listen/text/audio rejection: unified session-only CLOSED / PASS
post-close turn/generation admitted: False / PASS
framework root-public names: 127 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
provider/network/audio/microphone execution: False / PASS
FW-RT6-7c aggregate: NOT_COMPLETED
FW-RT6-7c tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the remaining result/callback compatibility bridge. Open
`listen_result()` and `text_fallback_result()` operations now carry the same
Framework-owned session/turn/generation context as their canonical v6 events.
The existing mapping callback contract is maintained by an explicit projection
from selected canonical events without adding a host-audio mapping flow.

The first close produces one canonical `SESSION_CLOSED` event and one legacy
`voice_input.closed` projection. Later listen, text-fallback and host-audio
result operations share one safe session-only closed rejection and admit no
turn or generation.

Control A and Control B together satisfy the FW-RT6-7c runtime compatibility
work, but the five aggregate task checkboxes remain open until Control C
aggregate acceptance. This sync authorizes only Control C exact contract review
after the sync commit/push is remotely verified. It does not authorize Control
C implementation or any later FW-RT6-8/P1 work.
<!-- FW-RT6-7c-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-7c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-7c Control C — aggregate result compatibility acceptance

```text
checkpoint: FW-RT6-7c Control C aggregate acceptance
baseline head: dfcdc137ba8d04bde09f62fe0ced04086886dbfe
Control A implementation: 28b298f1ee70bb114f13782d40c54b536a8174a7
Control A acceptance sync: 4dc3d1284f548748e59070bda4e03e8a434d16d8
Control B implementation: 60d1f1b1ac770e8b220c7e7488f536f2332acfb7
Control B acceptance sync: dfcdc137ba8d04bde09f62fe0ced04086886dbfe
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files
aggregate gate: PASS expected
focused Control A result-correlation compatibility tests: 8 / PASS expected
focused Control B result/callback compatibility tests: 8 / PASS expected
focused FW-RT6-7b lifecycle/privacy tests: 6 / PASS expected
focused FW-RT6-7b abort/stale/privacy tests: 7 / PASS expected
full Framework unit suite: 319 / PASS expected
accepted FW-RT6-7a/7b regressions: PASS expected
legacy VoiceInputResult prefix: 9 fields / SAME ORDER / PASS expected
additive optional correlation suffix: session_id / turn_id / generation_id / PASS expected
existing factory compatibility: PASS expected
transcribe/listen/text-fallback result correlation: PASS expected
adapter-provided correlation authority: session-owned / PASS expected
legacy mapping source: selected canonical v6 events / PASS expected
legacy mapping shape and names: PRESERVED / PASS expected
host-audio legacy mapping callback changed: False / PASS expected
post-close listen/text/audio rejection: unified session-only CLOSED / PASS expected
duplicate close events after close: False / PASS expected
framework root-public names: 127 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
runtime source changed by Control C: False
provider/network/audio/microphone execution: False / PASS expected
FW-RT6-7c tasks: 5 / 5 ACCEPTED-CANDIDATE
FW-RT6-7c aggregate: IMPLEMENTED_AWAITING_REVIEW
FW-RT6-7c final acceptance sync: NOT_AUTHORIZED
FW-RT6-8a motion correlation: NOT_AUTHORIZED
partial transcript/audio streaming: DEFERRED_TO_P1
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted additive result-correlation foundation and
the accepted result/callback compatibility bridge. Together they preserve the
legacy result prefix and factory behavior while correlating all open-session
result paths with Framework-owned identities, maintaining selected legacy
mapping callbacks through canonical v6 events, and unifying post-close result
rejection.

All five FW-RT6-7c tasks close here as aggregate acceptance candidates. Final
`COMPLETED / VERIFIED / ACCEPTED / CLOSED` status is deferred to the one-file
final acceptance sync after this candidate is reviewed, committed, pushed, and
remotely verified.

This candidate changes no runtime source. It does not authorize FW-RT6-8a
motion correlation, partial transcript/audio streaming, provider execution, or
any new microphone/audio ownership.
<!-- FW-RT6-7c-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-7c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-7c — voice-input result compatibility final acceptance sync

```text
checkpoint: FW-RT6-7c final acceptance
baseline head: e88be7a138676d1acdadb9c52459902d0864f8ab
Control A implementation: 28b298f1ee70bb114f13782d40c54b536a8174a7
Control A acceptance sync: 4dc3d1284f548748e59070bda4e03e8a434d16d8
Control B implementation: 60d1f1b1ac770e8b220c7e7488f536f2332acfb7
Control B acceptance sync: dfcdc137ba8d04bde09f62fe0ced04086886dbfe
Control C aggregate implementation: e88be7a138676d1acdadb9c52459902d0864f8ab
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A result-correlation compatibility tests: 8 / PASS
focused Control B result/callback compatibility tests: 8 / PASS
focused FW-RT6-7b lifecycle/privacy tests: 6 / PASS
focused FW-RT6-7b abort/stale/privacy tests: 7 / PASS
full Framework unit suite: 319 / PASS
accepted FW-RT6-7a/7b regressions: PASS
legacy VoiceInputResult prefix: 9 fields / SAME ORDER / PASS
additive optional correlation suffix: session_id / turn_id / generation_id / PASS
existing factory compatibility: PASS
transcribe/listen/text-fallback result correlation: PASS
adapter-provided correlation authority: session-owned / PASS
legacy mapping source: selected canonical v6 events / PASS
legacy mapping shape and names: PRESERVED / PASS
host-audio legacy mapping callback changed: False / PASS
post-close listen/text/audio rejection: unified session-only CLOSED / PASS
duplicate close events after close: False / PASS
framework root-public names: 127 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
runtime source changed by Control C: False
provider/network/audio/microphone execution: False / PASS
FW-RT6-7c tasks: 5 / 5 ACCEPTED
FW-RT6-7c aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-8a exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-8a implementation: NOT_AUTHORIZED
partial transcript/audio streaming: DEFERRED_TO_P1
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-7c is accepted as the provider-neutral voice-input result compatibility
boundary. It preserves the original result fields and factories, adds optional
Framework-owned correlation, maintains selected legacy mapping callbacks from
canonical v6 events, and unifies post-close result rejection without adding a
host-audio mapping flow.

This sync closes FW-RT6-7c only. It authorizes FW-RT6-8a exact contract review
after the sync commit/push is remotely verified, not FW-RT6-8a implementation.
Partial transcript/audio streaming remains deferred P1 scope.
<!-- FW-RT6-7c-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8a Control A — motion correlation acceptance sync

```text
checkpoint: FW-RT6-8a Control A
baseline head: f99f540c8534bbfeee8e1be049d3559b81c24b8c
implementation commit: f99f540c8534bbfeee8e1be049d3559b81c24b8c
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 6 files
dedicated gate: PASS
focused Control A motion-correlation tests: 9 / PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
full Framework unit suite: 328 / PASS
legacy MotionRequest prefix: 11 fields / SAME ORDER / PASS
legacy MotionResult prefix: 9 fields / SAME ORDER / PASS
additive optional request suffix: turn_id / generation_id / PASS
additive optional result suffix: turn_id / generation_id / PASS
existing request/result factory compatibility: PASS
typed Framework identity normalization: PASS
legacy non-Framework turn strings: PRESERVED / PASS
generation without turn accepted: False / PASS
correlated result without session accepted: False / PASS
MotionRequest request_id changed: False / PASS
GenerationId promoted from request_id: False / PASS
MotionResult session_id compatibility: PRESERVED / PASS
standalone correlation identity invented: False / PASS
mock result/event correlation: PASS
guarded/unavailable result/event correlation: PASS
closed result/event correlation: PASS
in-memory VTS transport-result correlation: PASS
mapping callback turn/generation serialization: JSON STRING / PASS
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
framework root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
unified EventSequence bridge: DEFERRED_TO_CONTROL_B
common stale guard adoption: DEFERRED_TO_CONTROL_B
VTS lifecycle-generation suppression changed: False / PASS
FW-RT6-8a aggregate: NOT_COMPLETED
FW-RT6-8a tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-8b / FW-RT6-8c: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the additive motion request/result correlation foundation.
The original request/result field prefixes and factories remain compatible,
while an existing unified turn/generation context is preserved through mock,
guarded, closed, and VTube Studio transport-result projection paths. Existing
`request_id` and `session_id` semantics remain independent and unchanged.

Mapping callbacks expose only JSON-safe string correlation when it is present.
A standalone motion operation does not invent a turn or generation, and the
acceptance verification imports no actual VTS/WebSocket runtime and executes no
provider, network, audio, microphone, or real motion operation.

The unified `EventSequence` bridge and common stale guard/VTS suppression
adoption remain Control B work. Therefore all five FW-RT6-8a aggregate task
checkboxes stay open. This sync authorizes only Control B exact contract review
after the sync commit/push is remotely verified; it does not authorize Control
B implementation or FW-RT6-8b/FW-RT6-8c work.
<!-- FW-RT6-8a-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8a Control B — unified motion coordination acceptance sync

```text
checkpoint: FW-RT6-8a Control B
baseline head: a06d7a3371ebeec69bce9a7265a2d01af7b89322
implementation commit: a06d7a3371ebeec69bce9a7265a2d01af7b89322
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B surface: 7 files
dedicated gate: PASS
focused Control A motion-correlation tests: 9 / PASS
focused Control B motion-coordination tests: 8 / PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
full Framework unit suite: 336 / PASS
accepted Control A correlation regression: PASS
shared EventSequence owner: RealtimeEventHub / PASS
separate local motion sequencer: False / PASS
typed canonical motion payload: MotionEventPayload / PASS
canonical motion callback registration before bind: PASS
single shared owner binding: PASS
owner replacement accepted: False / PASS
legacy mapping callback shape/sequence: PRESERVED / PASS
common freshness owner: RealtimeGenerationGate / PASS
MotionSession starts unified generation: False / PASS
MotionSession advances unified generation: False / PASS
unknown generation replaces active owner: False / PASS
retired mock completion delivered: False / PASS
retired VTS completion delivered: False / PASS
stale canonical diagnostic: STALE_RESULT_DROPPED / PASS
stale legacy terminal projection: motion.interrupted / PASS
late motion completed event emitted: False / PASS
VTS transport lifecycle-generation guard preserved: True / PASS
provider hard cancellation claimed: False / PASS
post-close scoped subscriber retained: False / PASS
create_motion_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-8a aggregate: NOT_COMPLETED
FW-RT6-8a tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C aggregate exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-8b / FW-RT6-8c: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the one-owner bridge from the existing v5.5 motion session to
the unified realtime ordering and freshness domains. Canonical motion events use
the shared `RealtimeEventHub` sequence, while the existing mapping callback
remains sequence-free and preserves its public shape. An unbound standalone
session does not create a competing canonical sequence.

The shared `RealtimeGenerationGate` is authoritative for correlated terminal
motion results. `MotionSession` neither starts nor advances that generation and
cannot replace an unknown or retired owner. A rejected mock or VTube Studio
completion becomes one correlated interrupted result, emits the typed stale
diagnostic and legacy interrupted projection, and never emits a completed event.

The accepted VTube Studio lifecycle-generation check remains the transport-local
close defense underneath the common turn-level stale guard. Control B adds no
provider hard cancellation, cancel/clear capability, lifecycle-to-motion hook,
provider execution, network execution, or real motion operation.

Control A and Control B together cover the five FW-RT6-8a runtime tasks as
aggregate acceptance candidates, but the task checkboxes remain `0 / 5 CLOSED`
until Control C aggregate review. This sync authorizes only Control C exact
contract review after the sync commit/push is remotely verified. It does not
authorize Control C implementation or FW-RT6-8b/FW-RT6-8c work.
<!-- FW-RT6-8a-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-8a Control C — aggregate motion correlation acceptance

```text
checkpoint: FW-RT6-8a Control C aggregate acceptance candidate
baseline head: 38405956b1646e33a82b366256c5e95b819d7dc8
Control A implementation: f99f540c8534bbfeee8e1be049d3559b81c24b8c
Control A acceptance sync: d3d4166a99b946c4a5976032bf6580ca821b953f
Control B implementation: a06d7a3371ebeec69bce9a7265a2d01af7b89322
Control B acceptance sync: 38405956b1646e33a82b366256c5e95b819d7dc8
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
focused Control A motion-correlation tests: 9 / PASS
focused Control B motion-coordination tests: 8 / PASS
full Framework unit suite: 336 / PASS
legacy MotionRequest prefix: 11 fields / SAME ORDER / PASS
legacy MotionResult prefix: 9 fields / SAME ORDER / PASS
additive optional correlation suffix: turn_id / generation_id / PASS
existing request_id/session_id compatibility: PRESERVED / PASS
mock result/event correlation: PASS
shared EventSequence owner: RealtimeEventHub / PASS
separate local motion sequencer: False / PASS
typed canonical motion payload: MotionEventPayload / PASS
legacy mapping callback shape/sequence: PRESERVED / PASS
common freshness owner: RealtimeGenerationGate / PASS
MotionSession starts or advances unified generation: False / PASS
retired motion completion delivered: False / PASS
stale canonical diagnostic: STALE_RESULT_DROPPED / PASS
stale legacy terminal projection: motion.interrupted / PASS
late motion completed event emitted: False / PASS
VTS transport lifecycle-generation guard preserved: True / PASS
provider hard cancellation claimed: False / PASS
create_motion_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
FW-RT6-8a tasks: 5 / 5 ACCEPTED-CANDIDATE
FW-RT6-8a final acceptance sync: NOT_AUTHORIZED
FW-RT6-8b lifecycle extension hook: NOT_AUTHORIZED
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted Control A correlation foundation and Control B
unified ordering/freshness bridge. Motion request/result correlation remains
additive, the existing `request_id` and `session_id` meanings remain unchanged,
and canonical motion events use the existing shared realtime owner rather than
a motion-local sequence.

The shared generation gate admits current correlated terminal results and
rejects retired, unknown, or turn-mismatched completions. A rejected completion
remains correlated, normalizes to interrupted, emits the typed stale diagnostic
and legacy interrupted projection, and does not emit a completed event. The
transport-local VTube Studio lifecycle-generation check remains an additional
close defense; no provider hard-cancellation guarantee is introduced.

Control C changes no runtime source. It adds the aggregate regression gate and
closes the five task checkboxes only as aggregate acceptance candidates. Final
`COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED` status remains
deferred to a reviewed, committed, pushed, and remotely verified one-file final
acceptance sync. This control does not authorize FW-RT6-8b or FW-RT6-8c work.
<!-- FW-RT6-8a-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-8a-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8a — motion correlation final acceptance sync

```text
checkpoint: FW-RT6-8a final acceptance
baseline head: dc9c1526d0ab850555e1de96accfd22358fdbb1c
Control A implementation: f99f540c8534bbfeee8e1be049d3559b81c24b8c
Control A acceptance sync: d3d4166a99b946c4a5976032bf6580ca821b953f
Control B implementation: a06d7a3371ebeec69bce9a7265a2d01af7b89322
Control B acceptance sync: 38405956b1646e33a82b366256c5e95b819d7dc8
Control C aggregate implementation: dc9c1526d0ab850555e1de96accfd22358fdbb1c
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A motion-correlation tests: 9 / PASS
focused Control B motion-coordination tests: 8 / PASS
full Framework unit suite: 336 / PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
legacy MotionRequest prefix: 11 fields / SAME ORDER / PASS
legacy MotionResult prefix: 9 fields / SAME ORDER / PASS
additive optional correlation suffix: turn_id / generation_id / PASS
existing request_id/session_id compatibility: PRESERVED / PASS
standalone correlation identity invented: False / PASS
shared EventSequence owner: RealtimeEventHub / PASS
separate local motion sequencer: False / PASS
typed canonical motion payload: MotionEventPayload / PASS
legacy mapping callback shape/sequence: PRESERVED / PASS
common freshness owner: RealtimeGenerationGate / PASS
MotionSession starts or advances unified generation: False / PASS
unknown generation replaces active owner: False / PASS
retired mock completion delivered: False / PASS
retired VTS completion delivered: False / PASS
stale canonical diagnostic: STALE_RESULT_DROPPED / PASS
stale legacy terminal projection: motion.interrupted / PASS
late motion completed event emitted: False / PASS
VTS transport lifecycle-generation guard preserved: True / PASS
provider hard cancellation claimed: False / PASS
create_motion_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
FW-RT6-8a tasks: 5 / 5 ACCEPTED
FW-RT6-8a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-8b exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-8b implementation: NOT_AUTHORIZED
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-8a is accepted as the provider-neutral motion correlation boundary. It
preserves the existing v5.5 request/result and public factory contracts while
carrying optional Framework turn/generation identity through results, canonical
events, and legacy mapping projections.

Canonical motion events join the existing shared realtime sequence and terminal
results use the common generation gate. Late or otherwise stale mock/VTube
Studio completions normalize to correlated interrupted results and never emit a
completed event. The existing VTube Studio lifecycle-generation check remains
the transport-local close defense; this acceptance does not claim provider hard
cancellation.

This sync closes FW-RT6-8a only. It authorizes FW-RT6-8b exact contract review
after the sync commit/push is remotely verified, not FW-RT6-8b implementation.
FW-RT6-8c motion cancel/clear work remains not authorized.
<!-- FW-RT6-8a-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8b Control A — motion lifecycle hook acceptance sync

```text
checkpoint: FW-RT6-8b Control A
baseline head: 6903b5a8ac96ea7e0e7bbd1b0108d7eb9f9f8dd7
implementation commit: 6903b5a8ac96ea7e0e7bbd1b0108d7eb9f9f8dd7
status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 5 files
dedicated gate: PASS
focused Control A motion-lifecycle tests: 13 / PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a aggregate regression: PASS
full Framework unit suite: 349 / PASS
stable explicit package: framework.motion_lifecycle / PASS
explicit-package exports: 6 / PASS
lifecycle signal vocabulary: 6 EXACT / PASS
notification session/turn/generation correlation: PASS
notification source EventSequence: PASS
transient/terminal outcome separation: PASS
provider-neutral hook return: MotionRequest | None / PASS
uncorrelated request context inheritance: PASS
matching request correlation preservation: PASS
partial/mismatched correlation escapes boundary: False / PASS
None hook result: SKIPPED / PASS
malformed hook result: FAILED / PUBLIC-SAFE / PASS
hook exception escapes Framework boundary: False / PASS
raw hook exception public: False / PASS
conversation terminal changed by hook failure: False / PASS
unsupported motion intent channel: MotionOutcome.UNSUPPORTED / PASS
product-specific mapping in Framework core: False / PASS
framework root-public names: 127 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime hook adoption: DEFERRED_TO_CONTROL_B
MotionStage execution: DEFERRED_TO_CONTROL_B
canonical hook/motion event integration: DEFERRED_TO_CONTROL_B
FW-RT6-8b aggregate: NOT_COMPLETED
FW-RT6-8b tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the provider-neutral lifecycle-to-motion extension contract.
The stable explicit `framework.motion_lifecycle` package carries the accepted
session, turn, generation, and canonical source sequence into one of six exact
lifecycle notifications. A host/plugin may return an existing provider-neutral
`MotionRequest` or intentionally skip the signal with `None`; Framework core
does not choose a character, expression, gesture, model, hotkey, or provider.

Uncorrelated requests inherit the notification's existing turn/generation
identity, while partial or mismatched correlation, malformed returns, and hook
exceptions remain inside a typed public-safe hook failure boundary. Hook skip,
hook failure, and adapter-level `MotionOutcome.UNSUPPORTED` remain distinct, and
none of them changes an already established conversation terminal outcome.

Runtime hook adoption, `MotionStage` execution, and canonical hook/motion event
integration remain Control B work. Therefore all six FW-RT6-8b aggregate task
checkboxes stay open. This sync authorizes only Control B exact contract review
after the sync commit/push is remotely verified; it does not authorize Control
B implementation or any FW-RT6-8c motion cancel/clear work.
<!-- FW-RT6-8b-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8b Control B — motion lifecycle runtime adoption acceptance sync

```text
checkpoint: FW-RT6-8b Control B
baseline head: c07d8d23723229118c95b2f2b1a292e6ce3f6129
Control A implementation: 6903b5a8ac96ea7e0e7bbd1b0108d7eb9f9f8dd7
Control A acceptance sync: 7e8afe4955c23d89924227dba269714ad71aed09
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B implementation: c07d8d23723229118c95b2f2b1a292e6ce3f6129
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B surface: 5 files
dedicated Control B gate: PASS
focused Control A motion-lifecycle tests: 13 / PASS
focused Control B motion-lifecycle tests: 15 / PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a aggregate regression: PASS
full Framework unit suite: 364 / PASS
public registration: RealtimeSession.set_motion_lifecycle_hook / PASS
factory/config hook parameter added: False / PASS
lifecycle source mapping: 7 canonical sources / PASS
hook signal vocabulary: 6 EXACT / PASS
source canonical event published before hook: True / PASS
provider-neutral mapped request: MotionRequest / PASS
product-specific mapping in Framework core: False / PASS
hook skip/failure starts MotionStage: False / PASS
mapped request uses injected MotionStage: True / PASS
canonical motion sequence owner: shared RealtimeEventHub / PASS
transient completion freshness owner: shared RealtimeGenerationGate / PASS
motion lifecycle starts/advances generation: False / PASS
terminal motion begins after terminal commit/publication: True / PASS
terminal motion reopens retired generation: False / PASS
conversation terminal replaced/duplicated by motion: False / PASS
missing MotionStage: MotionOutcome.NOT_CONFIGURED / PASS
failed MotionStage preflight: MotionOutcome.UNAVAILABLE / PASS
stage exception/malformed/correlation mismatch: PUBLIC-SAFE FAILED / PASS
unsupported adapter outcome: MotionOutcome.UNSUPPORTED / PRESERVED / PASS
callback/hook close starts MotionStage afterward: False / PASS
MotionStage close ownership: RealtimeSession / IDEMPOTENT / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-8b aggregate: NOT_COMPLETED
FW-RT6-8b tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C aggregate exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts explicit session-owned lifecycle-hook registration and the
runtime bridge from the accepted provider-neutral hook contract to the existing
injected `MotionStage`. Framework core still does not select a character,
expression, emotion, gesture, model, hotkey, or provider-specific mapping.

The hook runs only after its canonical lifecycle source is sequenced and
published. A mapped request emits typed canonical motion events on the existing
shared `RealtimeEventHub`; skipped or failed hook resolution starts no motion.
Missing, unavailable, exceptional, malformed, mismatched, and unsupported stage
results remain typed and public-safe without changing the conversation terminal.

Transient completions are admitted by the existing shared
`RealtimeGenerationGate`. Terminal-triggered motion starts after the terminal
registry commit and canonical terminal publication and remains a post-terminal
side effect. It neither starts nor advances a generation, reopens a retired
generation, replaces the accepted conversation outcome, nor creates a second
conversation terminal.

Control A and Control B together cover the six FW-RT6-8b tasks as aggregate
acceptance candidates, but the task checkboxes remain `0 / 6 CLOSED` until
Control C aggregate review. This sync authorizes only Control C exact contract
review after the sync commit/push is remotely verified. It does not authorize
Control C implementation or any FW-RT6-8c motion cancel/clear work.
<!-- FW-RT6-8b-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-8b Control C — motion lifecycle extension aggregate acceptance

```text
checkpoint: FW-RT6-8b Control C aggregate acceptance candidate
baseline head: a67af1caa45cc3a4f98fb324ce84d5f23ee060c1
Control A implementation: 6903b5a8ac96ea7e0e7bbd1b0108d7eb9f9f8dd7
Control A acceptance sync: 7e8afe4955c23d89924227dba269714ad71aed09
Control B implementation: c07d8d23723229118c95b2f2b1a292e6ce3f6129
Control B acceptance sync: a67af1caa45cc3a4f98fb324ce84d5f23ee060c1
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
focused Control A motion-lifecycle tests: 13 / PASS
focused Control B motion-lifecycle tests: 15 / PASS
full Framework unit suite: 364 / PASS
stable explicit hook package exports: 6 / PASS
public registration: RealtimeSession.set_motion_lifecycle_hook / PASS
factory/config hook parameter added: False / PASS
lifecycle source mapping: 7 canonical sources / PASS
hook signal vocabulary: 6 EXACT / PASS
source canonical event published before hook: True / PASS
provider-neutral mapped request: MotionRequest / PASS
product-specific mapping in Framework core: False / PASS
hook skip/failure starts MotionStage: False / PASS
mapped request uses injected MotionStage: True / PASS
canonical motion sequence owner: shared RealtimeEventHub / PASS
transient completion freshness owner: shared RealtimeGenerationGate / PASS
motion lifecycle starts/advances generation: False / PASS
terminal motion begins after terminal commit/publication: True / PASS
terminal motion reopens retired generation: False / PASS
conversation terminal replaced/duplicated by motion: False / PASS
missing MotionStage: MotionOutcome.NOT_CONFIGURED / PASS
failed MotionStage preflight: MotionOutcome.UNAVAILABLE / PASS
stage exception/malformed/correlation mismatch: PUBLIC-SAFE FAILED / PASS
unsupported adapter outcome: MotionOutcome.UNSUPPORTED / PRESERVED / PASS
callback/hook close starts MotionStage afterward: False / PASS
MotionStage close ownership: RealtimeSession / IDEMPOTENT / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
FW-RT6-8b tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-8b final acceptance sync: NOT_AUTHORIZED
FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted provider-neutral hook contract and runtime
adoption. The hook retains existing session, turn, generation, and canonical
source-sequence correlation while host/plugin code remains the sole owner of
character- or product-specific mapping.

Mapped requests execute through the existing injected `MotionStage`. Canonical
motion events use the session's shared sequencer, and transient completions use
the existing common freshness gate. Terminal-triggered motion remains a
post-terminal side effect validated against the accepted terminal source and
cannot reopen generation ownership or replace/duplicate conversation terminal
state.

Control C changes no runtime source. It adds the aggregate regression gate and
closes the six task checkboxes only as aggregate acceptance candidates. Final
`COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED` status remains
deferred to a reviewed, committed, pushed, and remotely verified one-file final
acceptance sync. FW-RT6-8c motion cancel/clear work remains not authorized.
<!-- FW-RT6-8b-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-8b-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8b — motion lifecycle extension final acceptance sync

```text
checkpoint: FW-RT6-8b final acceptance
baseline head: 6502762f5e320dc6d7e663b431861c61713cb1c4
Control A implementation: 6903b5a8ac96ea7e0e7bbd1b0108d7eb9f9f8dd7
Control A acceptance sync: 7e8afe4955c23d89924227dba269714ad71aed09
Control B implementation: c07d8d23723229118c95b2f2b1a292e6ce3f6129
Control B acceptance sync: a67af1caa45cc3a4f98fb324ce84d5f23ee060c1
Control C aggregate implementation: 6502762f5e320dc6d7e663b431861c61713cb1c4
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A motion-lifecycle tests: 13 / PASS
focused Control B motion-lifecycle tests: 15 / PASS
full Framework unit suite: 364 / PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a aggregate regression: PASS
stable explicit hook package exports: 6 / PASS
public registration: RealtimeSession.set_motion_lifecycle_hook / PASS
factory/config hook parameter added: False / PASS
lifecycle source mapping: 7 canonical sources / PASS
hook signal vocabulary: 6 EXACT / PASS
source canonical event published before hook: True / PASS
provider-neutral mapped request: MotionRequest / PASS
product-specific mapping in Framework core: False / PASS
hook skip/failure starts MotionStage: False / PASS
mapped request uses injected MotionStage: True / PASS
canonical motion sequence owner: shared RealtimeEventHub / PASS
transient completion freshness owner: shared RealtimeGenerationGate / PASS
motion lifecycle starts/advances generation: False / PASS
terminal motion begins after terminal commit/publication: True / PASS
terminal motion reopens retired generation: False / PASS
conversation terminal replaced/duplicated by motion: False / PASS
missing MotionStage: MotionOutcome.NOT_CONFIGURED / PASS
failed MotionStage preflight: MotionOutcome.UNAVAILABLE / PASS
stage exception/malformed/correlation mismatch: PUBLIC-SAFE FAILED / PASS
unsupported adapter outcome: MotionOutcome.UNSUPPORTED / PRESERVED / PASS
callback/hook close starts MotionStage afterward: False / PASS
MotionStage close ownership: RealtimeSession / IDEMPOTENT / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
FW-RT6-8b tasks: 6 / 6 ACCEPTED
FW-RT6-8b aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-8c exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-8c implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-8b is accepted as the provider-neutral lifecycle-to-motion extension
boundary. The stable hook contract preserves existing session, turn,
generation, and source-event sequence correlation while host/plugin code remains
the sole owner of character- and product-specific mapping.

Mapped requests execute through the existing injected `MotionStage`. Canonical
motion events use the session's shared sequencer, and transient completions use
the existing common freshness gate. Terminal-triggered motion remains a
post-terminal side effect and cannot reopen generation ownership or
replace/duplicate the accepted conversation terminal state.

Hook skip, hook failure, missing or unavailable stages, malformed or mismatched
results, and unsupported adapters remain typed and public-safe. The accepted
boundary changes neither the root-public surface nor realtime/motion API
versions and introduces no provider, network, audio, microphone, or real VTube
Studio execution.

This sync closes FW-RT6-8b only. It authorizes FW-RT6-8c exact contract review
after the sync commit/push is remotely verified, not FW-RT6-8c implementation.
<!-- FW-RT6-8b-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8c-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8c Control A — typed motion cancel/stop contract acceptance sync

```text
checkpoint: FW-RT6-8c Control A
baseline head: 1fcff27a9b2f89cd0682cf613b351b3f4b35c60b
Control A implementation: 1fcff27a9b2f89cd0682cf613b351b3f4b35c60b
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 7 files
dedicated Control A gate: PASS
focused Control A motion-control tests: 12 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-8b aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a aggregate regression: PASS
full Framework unit suite: 376 / PASS
explicit package: framework.motion_control / PASS
typed motion-control outcomes: 8 EXACT / PASS
InterruptResult additive motion_result: PASS
legacy InterruptResult positional prefix: UNCHANGED / PASS
RealtimeMotionCapability additive stop_motion_supported: PASS
legacy RealtimeMotionCapability positional prefix: UNCHANGED / PASS
request cancel equals STOP_MOTION: False / PASS
cancel requested equals cancel accepted: False / PASS
cancel accepted equals cancel completed: False / PASS
provider STOP_MOTION overclaim: False / PASS
motion result session/turn/generation/request correlation: PASS
interrupt/motion turn mismatch accepted: False / PASS
motion result public-safe metadata: PASS
root import loads framework.motion_control eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
RealtimeSession runtime motion-control adoption: DEFERRED_TO_CONTROL_B
MotionSession runtime motion-control adoption: DEFERRED_TO_CONTROL_B
active/pending motion tracking: DEFERRED_TO_CONTROL_B
whole-turn aggregate interrupt outcome: DEFERRED_TO_FW_RT6_9A
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-8c aggregate: NOT_COMPLETED
FW-RT6-8c tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-9a aggregate interrupt: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the explicit provider-neutral typed result boundary for
motion request cancellation and explicit `STOP_MOTION` reach. Request cancel,
cancel acceptance, cancel completion, and provider-side stop application remain
separate facts; no provider capability or physical stop is inferred from a
local request alone.

The additive `InterruptResult.motion_result` projection preserves the existing
interrupt positional prefix and rejects conflicting turn identity. The
additive `RealtimeMotionCapability.stop_motion_supported` flag remains distinct
from request-cancel support and preserves its existing positional prefix. The
new contract stays in explicit `framework.motion_control`; root imports, public
names, factory signatures, and realtime/motion API versions remain unchanged.

Runtime active/pending motion tracking and adoption by `RealtimeSession` and
`MotionSession` remain Control B work. Cross-stage aggregation of LLM, TTS,
artifact, and motion interrupt results remains FW-RT6-9a work. Therefore all
five FW-RT6-8c task checkboxes stay open. This sync authorizes only Control B
exact contract review after the sync commit/push is remotely verified; it does
not authorize Control B implementation or FW-RT6-9a aggregate interrupt work.
<!-- FW-RT6-8c-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8c-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8c Control B — RealtimeSession motion-control adoption acceptance sync

```text
checkpoint: FW-RT6-8c Control B
baseline head: 2750fc3c584aa2cca238a10e2ed596639bd113d9
Control A implementation: 1fcff27a9b2f89cd0682cf613b351b3f4b35c60b
Control A acceptance sync: 538b1baae3ff6e0ad2c1add3a8d667f9d107d474
Control B implementation: 2750fc3c584aa2cca238a10e2ed596639bd113d9
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B surface: 5 files
dedicated Control A gate: PASS
dedicated Control B gate: PASS
focused Control A motion-control tests: 12 / PASS
focused Control B motion-control tests: 11 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-8b aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a aggregate regression: PASS
full Framework unit suite: 387 / PASS
active/pending lifecycle motion owner: RealtimeSession / PASS
MotionStage.cancel outside long session operation lock: PASS
accepted cancel late-delivery barrier: PASS
cancel requested equals cancel accepted: False / PASS
cancel accepted equals cancel completed: False / PASS
request cancel equals STOP_MOTION: False / PASS
cached construction preflight owns stop capability: True / PASS
provider STOP_MOTION overclaim: False / PASS
duplicate stage cancel execution: AT_MOST_ONCE / PASS
duplicate provider stop execution: AT_MOST_ONCE / PASS
target mismatch cancels another turn: False / PASS
InterruptResult additive motion_result: PASS
aggregate InterruptResult outcome changed: False / PASS
new public cancel_motion method: False / PASS
standalone MotionSession public contract changed: False / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-8c aggregate: NOT_COMPLETED
FW-RT6-8c tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C aggregate exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-9a aggregate interrupt: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the `RealtimeSession`-owned bridge from the accepted typed
motion-control contract to one correlated pending or active lifecycle motion.
An interrupt reaches motion through the existing additive
`InterruptResult.motion_result`; no new root export, factory argument,
registration callback, or public `cancel_motion()` method is introduced.

The session invokes `MotionStage.cancel` outside the long session operation
lock. Accepted cancellation arms a one-way late-delivery barrier before the
interrupt waits for that lock, so the original in-flight motion cannot publish
a late completion or failure. Request, acceptance, and actual completion remain
separate observed facts.

Explicit provider-neutral `STOP_MOTION` remains independent. The cached
construction preflight is the sole capability source, and provider application
is reported only after a typed, correlated `MotionOutcome.COMPLETED` result.
Unsupported capability, exceptions, malformed or mismatched results, and
non-completed outcomes never overclaim a physical stop. Duplicate stage cancel
and stop execution is linearized per active work item, and a mismatched turn
target never cancels another turn's motion.

Control B intentionally leaves the established aggregate interrupt outcome
unchanged. Cross-stage LLM, TTS, queued output, artifact, partial completion,
timeout, and whole-request duplicate coordination remain FW-RT6-9a/FW-RT6-9b
work. Therefore all five FW-RT6-8c aggregate task checkboxes stay open. This
sync authorizes only Control C aggregate exact contract review after the sync
commit/push is remotely verified; it does not authorize Control C
implementation or FW-RT6-9a aggregate interrupt work.
<!-- FW-RT6-8c-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-8c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-8c Control C — motion cancel/clear aggregate acceptance

```text
checkpoint: FW-RT6-8c Control C aggregate acceptance candidate
baseline head: b1710ba1398cbbaf982d0fa436f41ba43d707e96
Control A implementation: 1fcff27a9b2f89cd0682cf613b351b3f4b35c60b
Control A acceptance sync: 538b1baae3ff6e0ad2c1add3a8d667f9d107d474
Control B implementation: 2750fc3c584aa2cca238a10e2ed596639bd113d9
Control B acceptance sync: b1710ba1398cbbaf982d0fa436f41ba43d707e96
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
focused Control A motion-control tests: 12 / PASS
focused Control B motion-control tests: 11 / PASS
full Framework unit suite: 387 / PASS
typed MotionControlOutcome vocabulary: 8 EXACT / PASS
pending/active lifecycle motion owner: RealtimeSession / PASS
request cancel capability source: cached construction preflight / PASS
MotionStage.cancel outside long session operation lock: PASS
cancel request/accept/completion facts separated: True / PASS
accepted cancel late-delivery barrier: PASS
late motion terminal event delivered: False / PASS
request cancel equals STOP_MOTION: False / PASS
stop_motion unsupported overclaim: False / PASS
provider stop application requires correlated COMPLETED: True / PASS
duplicate stage cancel execution: AT_MOST_ONCE / PASS
duplicate provider stop execution: AT_MOST_ONCE / PASS
turn mismatch cancels another motion: False / PASS
whole-turn motion reach: InterruptResult.motion_result / PASS
aggregate InterruptResult outcome changed: False
no active / terminal / closed outcomes: TYPED / PASS
new public cancel_motion method: False / PASS
standalone MotionSession public contract changed: False / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
FW-RT6-8c tasks: 5 / 5 ACCEPTED-CANDIDATE
FW-RT6-8c final acceptance sync: NOT_AUTHORIZED
FW-RT6-9a aggregate interrupt: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted typed motion-control contract and its
`RealtimeSession` runtime adoption. One session-owned pending or active
lifecycle motion retains the stage and request correlation needed to report
truthful cancel and provider-neutral stop facts through the existing additive
`InterruptResult.motion_result` projection.

Cancellation remains split phase: `MotionStage.cancel` executes outside the
long session operation lock, and accepted cancellation arms a one-way
late-delivery barrier before the interrupt waits for that lock. Request,
acceptance, completion, and explicit provider stop application remain separate
facts. Unsupported capability, exceptions, malformed or mismatched results,
and non-completed stop outcomes never claim provider application.

One active-work owner linearizes duplicate stage cancel and provider stop
execution. Target mismatch cannot cancel another turn. No-active, terminal, and
closed cases remain distinct typed motion-control outcomes. The established
aggregate interrupt outcome is deliberately unchanged; Control C does not
implement the FW-RT6-9a whole-turn coordinator.

Control C changes no runtime source. It adds the aggregate regression gate and
closes the five FW-RT6-8c task checkboxes only as aggregate acceptance
candidates. Final `COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED /
CLOSED` status remains deferred to a reviewed, committed, pushed, and remotely
verified one-file final acceptance sync. FW-RT6-9a remains not authorized.
<!-- FW-RT6-8c-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-8c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-8c — motion cancel/clear final acceptance sync

```text
checkpoint: FW-RT6-8c final acceptance
baseline head: 4dced68bda2b6362b7df1d6ceeaf853cd8881c61
Control A implementation: 1fcff27a9b2f89cd0682cf613b351b3f4b35c60b
Control A acceptance sync: 538b1baae3ff6e0ad2c1add3a8d667f9d107d474
Control B implementation: 2750fc3c584aa2cca238a10e2ed596639bd113d9
Control B acceptance sync: b1710ba1398cbbaf982d0fa436f41ba43d707e96
Control C aggregate implementation: 4dced68bda2b6362b7df1d6ceeaf853cd8881c61
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A motion-control tests: 12 / PASS
focused Control B motion-control tests: 11 / PASS
full Framework unit suite: 387 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
typed MotionControlOutcome vocabulary: 8 EXACT / PASS
pending/active lifecycle motion owner: RealtimeSession / PASS
request cancel capability source: cached construction preflight / PASS
MotionStage.cancel outside long session operation lock: PASS
cancel request/accept/completion facts separated: True / PASS
accepted cancel late-delivery barrier: PASS
late motion terminal event delivered: False / PASS
request cancel equals STOP_MOTION: False / PASS
stop_motion unsupported overclaim: False / PASS
provider stop application requires correlated COMPLETED: True / PASS
duplicate stage cancel execution: AT_MOST_ONCE / PASS
duplicate provider stop execution: AT_MOST_ONCE / PASS
turn mismatch cancels another motion: False / PASS
whole-turn motion reach: InterruptResult.motion_result / PASS
aggregate InterruptResult outcome changed: False
no active / terminal / closed outcomes: TYPED / PASS
new public cancel_motion method: False / PASS
standalone MotionSession public contract changed: False / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
FW-RT6-8c tasks: 5 / 5 ACCEPTED
FW-RT6-8c aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-9a exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-9a implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-8c is accepted as the provider-neutral motion cancel and explicit stop
reach boundary. One `RealtimeSession`-owned pending or active lifecycle motion
retains the correlation required to report typed control facts through the
additive `InterruptResult.motion_result` projection.

`MotionStage.cancel` executes outside the long session operation lock, and an
accepted cancellation arms a one-way late-delivery barrier. Cancel request,
acceptance, actual completion, and explicit provider-neutral stop application
remain distinct observations. Provider-side stop is claimed only after a
typed, correlated completed result; unavailable, exceptional, malformed,
mismatched, and non-completed results remain truthful.

Duplicate stage cancel and provider stop execution is limited to at most once
per active work item. A mismatched target cannot reach another turn's motion,
and no-active, terminal, and closed cases remain distinct typed results. The
accepted boundary does not change the established aggregate interrupt outcome,
add a public `cancel_motion()` method, or change the standalone `MotionSession`
contract.

This sync closes FW-RT6-8c only. It authorizes FW-RT6-9a exact contract review
after the sync commit/push is remotely verified, not FW-RT6-9a implementation.
<!-- FW-RT6-8c-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9a Control A — interrupt coordination contract acceptance sync

```text
checkpoint: FW-RT6-9a Control A
baseline head: 712a03e27db1ea6c2229f6907c54d581680bb208
Control A implementation: 712a03e27db1ea6c2229f6907c54d581680bb208
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 6 files
dedicated Control A gate: PASS
focused Control A interrupt-coordination tests: 17 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
full Framework unit suite: 404 / PASS
explicit package: framework.interrupt_coordination / PASS
interrupt subsystems: 5 EXACT / PASS
typed subsystem outcomes: 8 EXACT / PASS
typed aggregate outcomes: 9 EXACT / PASS
subsystem reach observable: MODEL READY / PASS
aggregate outcome derived from subsystem results: True / PASS
partial result: PASS
unsupported overclaim: False / PASS
cooperative cancel equals provider hard cancel: False / PASS
provider hard cancel application requires advertised support: True / PASS
InterruptRequest additive timeout_seconds: PASS
legacy InterruptRequest positional prefix: UNCHANGED / PASS
InterruptResult additive coordination_result projection: PASS
accepted InterruptResult dataclass fields: UNCHANGED / PASS
aggregate/subsystem session and turn correlation: PASS
duplicate subsystem aggregate entries accepted: False / PASS
root import loads framework.interrupt_coordination eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
active stage registry: DEFERRED_TO_CONTROL_B
interrupt target dispatch and validation: DEFERRED_TO_CONTROL_B
LLM/TTS/artifact/motion runtime coordination: DEFERRED_TO_CONTROL_B
bounded wait and runtime partial completion: DEFERRED_TO_CONTROL_B
whole-request duplicate/race ordering: DEFERRED_TO_FW_RT6_9B
barge-in decision/execution: DEFERRED_TO_FW_RT6_9C
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-9a aggregate: NOT_COMPLETED
FW-RT6-9a tasklist: 0 / 9 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-9b implementation: NOT_AUTHORIZED
FW-RT6-9c implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the explicit provider-neutral result boundary for future
whole-turn interrupt coordination. Each typed result identifies one of text
generation, TTS generation, the TTS pending queue, audio artifacts, or motion
and reports target reach separately from cooperative cancellation, provider
hard cancellation, future-delivery suppression, and affected item count.

`InterruptAggregateResult.from_results(...)` derives its outcome from a
non-empty set containing at most one result for each subsystem. Session and
turn correlation must agree. Uniform observations map to the matching typed
aggregate outcome, while heterogeneous observations map to `PARTIAL`; callers
cannot relabel unsupported or mixed results as completed.

The trailing optional `InterruptRequest.timeout_seconds` preserves the legacy
request prefix and accepts only finite positive values. The optional trailing
`InterruptResult.coordination_result` constructor projection preserves the
accepted dataclass field inventory and existing helper defaults. The explicit
coordination package remains absent from the root-public surface, and realtime
and motion API versions remain unchanged.

Control A adds models and validation only. Active-stage ownership, target
dispatch, LLM/TTS/artifact/motion control calls, bounded waiting, and runtime
aggregate projection remain Control B work. Therefore all nine FW-RT6-9a task
checkboxes stay open. Whole-request duplicate/race ordering remains FW-RT6-9b,
and barge-in decision/execution remains FW-RT6-9c. This sync authorizes only
Control B exact contract review after the sync commit/push is remotely
verified; it does not authorize Control B, FW-RT6-9b, or FW-RT6-9c
implementation.
<!-- FW-RT6-9a-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9a Control B — interrupt coordination runtime adoption acceptance sync

```text
checkpoint: FW-RT6-9a Control B
baseline head: 09752474a3178021a5153f8fdaa94aea59c4e5e8
Control A implementation: 712a03e27db1ea6c2229f6907c54d581680bb208
Control A acceptance sync: 3aaef5e6335c2c184450525a17d36f1783345268
Control B implementation: 09752474a3178021a5153f8fdaa94aea59c4e5e8
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B surface: 5 files
dedicated Control B gate: PASS
focused Control B interrupt-coordination tests: 15 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
full Framework unit suite: 419 / PASS
active-stage registry: RealtimeSession PRIVATE / PASS
interrupt target dispatch and validation: PASS
interrupt subsystems: 5 EXACT / PASS
text-generation cancel reach: True / PASS
TTS-generation cancel reach: True / PASS
TTS pending-queue clear reach: True / PASS
audio-artifact invalidation reach: True / PASS
accepted motion-control projection reused: True / PASS
stage control outside long session operation lock: PASS
short registry locks held across stage calls: False / PASS
accepted cancel late-delivery barrier: PASS
bounded completion wait: PASS
default internal completion bound: 0.25 seconds / PASS
runtime partial result: PASS
unsupported overclaim: False / PASS
aggregate outcome derived from subsystem results: True / PASS
root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
whole-request duplicate/race ordering: DEFERRED_TO_FW_RT6_9B
barge-in decision/execution: DEFERRED_TO_FW_RT6_9C
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-9a aggregate: NOT_COMPLETED
FW-RT6-9a tasklist: 0 / 9 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-9b implementation: NOT_AUTHORIZED
FW-RT6-9c implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts `RealtimeSession` as the private runtime owner of active
text-generation and TTS-generation stage work. Interrupt targets are resolved
in stable `TEXT_GENERATION -> TTS_GENERATION -> TTS_QUEUE -> AUDIO_ARTIFACT ->
MOTION` order, and the accepted motion-control result is reused rather than
duplicated.

Stage cancellation and motion control execute outside the long session
operation lock, and no stage call executes while a short registry lock is
held. Once cooperative cancellation is accepted, the one-way late-delivery
barrier prevents the eventual provider return from reaching Framework output.
An explicit positive request timeout supplies the completion budget; otherwise
the internal 0.25 second safety bound applies without changing the public
request projection.

TTS generation cancellation, pending queue clearing, artifact invalidation,
and motion remain separate capability-gated observations. Their typed results
are combined only through `InterruptAggregateResult.from_results(...)`, so
mixed observations remain truthful `PARTIAL` outcomes and unsupported paths do
not overclaim effects. The existing v5.2 outer interrupt behavior, factory and
root-public surfaces, and realtime and motion API versions remain unchanged.

Control B does not close any of the nine FW-RT6-9a aggregate task checkboxes.
Whole-request duplicate and race convergence remains FW-RT6-9b, while barge-in
decision and execution remains FW-RT6-9c. This sync authorizes only Control C
exact contract review after the sync commit/push is remotely verified; it does
not authorize Control C, FW-RT6-9b, or FW-RT6-9c implementation.
<!-- FW-RT6-9a-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-9a Control C — interrupt coordinator aggregate acceptance

```text
checkpoint: FW-RT6-9a Control C aggregate acceptance candidate
baseline head: a013d04092d04ad94ac9be915da8b93f0e063c01
Control A implementation: 712a03e27db1ea6c2229f6907c54d581680bb208
Control A acceptance sync: 3aaef5e6335c2c184450525a17d36f1783345268
Control B implementation: 09752474a3178021a5153f8fdaa94aea59c4e5e8
Control B acceptance sync: a013d04092d04ad94ac9be915da8b93f0e063c01
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
focused Control A interrupt-coordination tests: 17 / PASS
focused Control B interrupt-coordination tests: 15 / PASS
full Framework unit suite: 419 / PASS
interrupt subsystems: 5 EXACT / PASS
subsystem outcomes: 8 EXACT / PASS
aggregate outcomes: 9 EXACT / PASS
active-stage registry owner: RealtimeSession PRIVATE / PASS
interrupt target dispatch order: STABLE / PASS
turn terminal/not-found/closed outcomes: TYPED / PASS
LLM cooperative cancel reach: PASS
TTS generation cancel reach: PASS
TTS pending clear reach: PASS
audio artifact invalidation reach: PASS
accepted motion-control projection reused: PASS
aggregate result source: InterruptAggregateResult.from_results / PASS
aggregate partial result: PASS
bounded timeout result: PASS
accepted cancel late-delivery barrier: PASS
unsupported overclaim: False / PASS
outer v5.2 interrupt compatibility: PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
whole-request duplicate/race ordering changed: False
barge-in decision/execution changed: False
FW-RT6-9a tasks: 9 / 9 ACCEPTED-CANDIDATE
FW-RT6-9a final acceptance sync: NOT_AUTHORIZED
FW-RT6-9b duplicate/race ordering: NOT_AUTHORIZED
FW-RT6-9c barge-in execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted explicit coordination models and their
`RealtimeSession` runtime adoption. One private active-stage registry owns
in-flight text and TTS generation work, and each public request resolves its
five possible targets in stable text, TTS generation, pending queue, artifact,
and motion order.

Cancellation executes outside the long session operation lock. Accepted
cooperative cancellation arms a one-way late-delivery barrier, while bounded
waiting preserves distinct requested, completed, timed-out, failed, and
unsupported observations. TTS generation, pending clear, artifact
invalidation, and the accepted motion-control projection remain separate
capability-gated facts.

`InterruptAggregateResult.from_results(...)` remains the sole aggregate
outcome source. Uniform subsystem observations map to their corresponding
typed aggregate, while mixed observations remain `PARTIAL`; unsupported or
incomplete work cannot be relabeled completed. Terminal, unknown, inactive,
and closed targets preserve the existing outer v5.2 interrupt compatibility.

Control C changes no runtime source. It adds the aggregate regression gate and
closes the nine FW-RT6-9a task checkboxes only as aggregate acceptance
candidates. Final `COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED /
CLOSED` status remains deferred to a reviewed, committed, pushed, and remotely
verified one-file final acceptance sync. Whole-request duplicate and race
ordering remains FW-RT6-9b, and barge-in decision/execution remains FW-RT6-9c.
<!-- FW-RT6-9a-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-9a-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9a — interrupt coordinator final acceptance sync

```text
checkpoint: FW-RT6-9a final acceptance
baseline head: 5a7908cf3d7604b536277715d47178dd84969c39
Control A implementation: 712a03e27db1ea6c2229f6907c54d581680bb208
Control A acceptance sync: 3aaef5e6335c2c184450525a17d36f1783345268
Control B implementation: 09752474a3178021a5153f8fdaa94aea59c4e5e8
Control B acceptance sync: a013d04092d04ad94ac9be915da8b93f0e063c01
Control C aggregate implementation: 5a7908cf3d7604b536277715d47178dd84969c39
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A interrupt-coordination tests: 17 / PASS
focused Control B interrupt-coordination tests: 15 / PASS
full Framework unit suite: 419 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
interrupt subsystems: 5 EXACT / PASS
subsystem outcomes: 8 EXACT / PASS
aggregate outcomes: 9 EXACT / PASS
active-stage registry owner: RealtimeSession PRIVATE / PASS
interrupt target dispatch order: STABLE / PASS
turn terminal/not-found/closed outcomes: TYPED / PASS
LLM cooperative cancel reach: PASS
TTS generation cancel reach: PASS
TTS pending clear reach: PASS
audio artifact invalidation reach: PASS
accepted motion-control projection reused: PASS
aggregate result source: InterruptAggregateResult.from_results / PASS
aggregate partial result: PASS
bounded timeout result: PASS
accepted cancel late-delivery barrier: PASS
unsupported overclaim: False / PASS
outer v5.2 interrupt compatibility: PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
whole-request duplicate/race ordering changed: False
barge-in decision/execution changed: False
FW-RT6-9a tasks: 9 / 9 ACCEPTED
FW-RT6-9a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-9b exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-9b implementation: NOT_AUTHORIZED
FW-RT6-9c implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-9a is accepted as the provider-neutral whole-turn interrupt
coordinator. `RealtimeSession` privately owns active text and TTS generation
work, validates the requested target, and reaches text generation, TTS
generation, the pending TTS queue, audio artifacts, and motion in stable order.

Stage cancellation and motion control remain outside the long session
operation lock. Accepted cooperative cancellation arms the one-way
late-delivery barrier before bounded completion waiting. Request, acceptance,
completion, provider hard-cancel application, queue clearing, artifact
invalidation, and motion effects remain separate truthful observations.

`InterruptAggregateResult.from_results(...)` derives every aggregate outcome.
Mixed observations remain `PARTIAL`, while inactive, terminal, unknown,
unsupported, timed-out, failed, and closed paths preserve their typed facts and
the accepted outer v5.2 compatibility behavior. No provider capability or
physical effect is inferred without an observed result.

This sync closes FW-RT6-9a only. It changes no runtime source and does not
implement whole-request duplicate convergence, interrupt/completion/close race
ordering, flush ordering, or new-turn-during-interrupt behavior. Those remain
FW-RT6-9b. It authorizes FW-RT6-9b exact contract review after this sync is
committed, pushed, and remotely verified, not FW-RT6-9b implementation.
FW-RT6-9c barge-in execution remains not authorized.
<!-- FW-RT6-9a-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9b Control A — interrupt ordering contract acceptance sync

```text
checkpoint: FW-RT6-9b Control A
baseline head: b2557a6aa08a3af89ea527413dc37ac85f458d05
Control A implementation: b2557a6aa08a3af89ea527413dc37ac85f458d05
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 5 files
dedicated Control A gate: PASS
focused Control A interrupt-ordering tests: 12 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-9a aggregate regression: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
full Framework unit suite: 431 / PASS
explicit package: framework.interrupt_ordering / PASS
explicit package exports: 6 EXACT / PASS
ordering rules: 6 EXACT / PASS
admission outcomes: 5 EXACT / PASS
public interrupt request ID introduced: False / ACCEPTED
idempotency key: (session_id, resolved_turn_id) / ACCEPTED
duplicate result: REPLAY OWNER TERMINAL RESULT / ACCEPTED
normal completion race: FIRST TERMINAL RESERVATION WINS / ACCEPTED
close race: FIRST ADMISSION WINS / ACCEPTED
flush race: OWNER FLUSH BEFORE TERMINAL / ACCEPTED
new turn during interrupt: TYPED REJECT / ACCEPTED
multiple turn terminal events: False / CONTRACT
owner is sole execute/reserve decision: True / PASS
duplicate replay side effects: False / PASS
root import loads framework.interrupt_ordering eagerly: False / PASS
InterruptRequest fields changed: False / PASS
InterruptResult fields changed: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
runtime owner registry: DEFERRED_TO_CONTROL_B
duplicate wait and terminal-result replay: DEFERRED_TO_CONTROL_B
terminal reservation and completion race execution: DEFERRED_TO_CONTROL_B
close/flush/new-turn runtime ordering: DEFERRED_TO_CONTROL_B
deterministic fake race execution: DEFERRED_TO_CONTROL_B
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-9b aggregate: NOT_COMPLETED
FW-RT6-9b tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-9c implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the explicit provider-neutral identity and ordering contract
for future whole-request interrupt convergence. A second public interrupt
request ID is intentionally not introduced. One turn already owns exactly one
Framework terminal boundary, so the accepted idempotency key is the existing
session identity plus the turn resolved once at interrupt admission.

The first admission for that key is the sole owner. A duplicate must reuse the
owner's terminal result and cannot repeat cancellation, queue clearing,
artifact invalidation, motion control, output flush, interrupt events, or the
turn terminal event. Normal completion versus interrupt is fixed by first
terminal reservation, while close versus interrupt is fixed by first
admission. An interrupt-owned flush precedes its terminal, and a new turn
during interrupting receives a typed rejection.

`InterruptOrderingPolicy`, `InterruptOrderingKey`, and
`InterruptOrderingDecision` validate these rules without changing the accepted
root `InterruptRequest` or `InterruptResult` fields. The explicit package stays
lazy and absent from the Framework root; factory signatures, event vocabulary,
root-public names, and realtime and motion API versions remain unchanged.

Control A adds contracts and validation only. The private runtime owner,
duplicate waiting and result replay, terminal reservation, close/flush/turn
admission ordering, and deterministic fake race execution remain Control B
work. Therefore all seven FW-RT6-9b aggregate task checkboxes stay open. This
sync authorizes only Control B exact contract review after the sync commit/push
is remotely verified; it does not authorize Control B implementation or
FW-RT6-9c barge-in execution.
<!-- FW-RT6-9b-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9b Control B — interrupt ordering runtime adoption acceptance sync

```text
checkpoint: FW-RT6-9b Control B
baseline head: 1f05e9d6da9ccbd29c198f577cf8155318b06486
Control A implementation: b2557a6aa08a3af89ea527413dc37ac85f458d05
Control A acceptance sync: e92f6929fd673c1c1b53cbcb19a2c5a23e446e56
Control B implementation: 6b9a9629239f969a51325cbf35d0e4be444c5689
Control B corrective: 1f05e9d6da9ccbd29c198f577cf8155318b06486
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B implementation surface: 5 files
dedicated Control B source gate: PASS
focused Control B interrupt-ordering tests: 11 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-9a aggregate regression: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
full Framework unit suite: 442 / PASS
whole-request owner: RealtimeSession PRIVATE / PASS
idempotency key: (session_id, resolved_turn_id) / PASS
duplicate wait outside operation lock: True / PASS
duplicate result: EXACT OWNER InterruptResult OBJECT / PASS
duplicate subsystem/flush/event effects repeated: False / PASS
same-owner interrupt callback replay: EXACT PREPARED OWNER RESULT / PASS
same-owner interrupt callback self-deadlock: False / PASS
normal completion race: FIRST TERMINAL RESERVATION WINS / PASS
unsupported interrupt overclaims turn terminal: False / PASS
close race: FIRST ADMISSION WINS / PASS
owner flush before terminal: True / PASS
standalone flush repeats owner effect: False / PASS
same-owner reentrant flush: PREPARED RESULT REUSE / PASS
same-owner reentrant flush effect count: 1 / PASS
new turn during interrupt: TYPED REJECT interrupt_in_progress / PASS
multiple turn terminal events: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-9b aggregate: NOT_COMPLETED
FW-RT6-9b tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-9c implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts `RealtimeSession` as the private whole-request interrupt
owner. The first admission for the resolved session and turn key executes the
coordination work and reserves the interrupt terminal. Concurrent and later
duplicates wait outside the operation lock and replay the exact owner
`InterruptResult` without repeating cancellation, queue clearing, artifact
invalidation, motion control, output flush, interrupt events, or the turn
terminal event. `interrupt(...)` and `cancel_current_turn(...)` share this
single admission path.

The owner stores its immutable final result before synchronous Framework
interrupt callbacks run. A same-owner reentrant interrupt or cancel callback
therefore returns that exact prepared object immediately and cannot wait on its
own completion event. The owner also stores its typed flush result before the
synchronous output-flush callback, so a same-owner reentrant flush reuses that
result without recursion, a second flush effect, or a second flush event.

The interrupt reservation participates in the accepted terminal registry.
Normal completion versus interrupt is resolved by first terminal reservation,
while close versus interrupt is resolved by first admission. An owner-requested
flush completes before the interrupt terminal, and a standalone same-turn flush
cannot repeat that owner effect. A genuinely new turn admitted during active
interrupt work is rejected through the existing typed result with public-safe
reason `interrupt_in_progress`.

Control B does not close any of the seven FW-RT6-9b aggregate task checkboxes.
Aggregate acceptance remains Control C work. This sync authorizes only Control
C exact contract review after the sync commit/push is remotely verified; it
does not authorize Control C implementation or FW-RT6-9c barge-in execution.
<!-- FW-RT6-9b-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-9b Control C — interrupt ordering aggregate acceptance

```text
checkpoint: FW-RT6-9b Control C aggregate acceptance candidate
baseline head: 941887a36e530be77aaa2406251913166b976734
Control A implementation: b2557a6aa08a3af89ea527413dc37ac85f458d05
Control A acceptance sync: e92f6929fd673c1c1b53cbcb19a2c5a23e446e56
Control B implementation: 6b9a9629239f969a51325cbf35d0e4be444c5689
Control B corrective: 1f05e9d6da9ccbd29c198f577cf8155318b06486
Control B acceptance sync: 941887a36e530be77aaa2406251913166b976734
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
dedicated Control C aggregate gate: PASS
focused Control A interrupt-ordering tests: 12 / PASS
focused Control B interrupt-ordering tests: 11 / PASS
full Framework unit suite: 442 / PASS
explicit package: framework.interrupt_ordering / PASS
public interrupt request ID introduced: False / ACCEPTED
idempotency key: (session_id, resolved_turn_id) / PASS
whole-request owner: RealtimeSession PRIVATE / PASS
duplicate wait outside operation lock: True / PASS
duplicate result: EXACT OWNER InterruptResult OBJECT / PASS
duplicate subsystem/flush/event effects repeated: False / PASS
same-owner interrupt callback replay: EXACT PREPARED OWNER RESULT / PASS
same-owner interrupt callback self-deadlock: False / PASS
normal completion race: FIRST TERMINAL RESERVATION WINS / PASS
unsupported interrupt overclaims turn terminal: False / PASS
close race: FIRST ADMISSION WINS / PASS
owner flush before terminal: True / PASS
standalone flush repeats owner effect: False / PASS
same-owner reentrant flush: PREPARED RESULT REUSE / PASS
same-owner reentrant flush effect count: 1 / PASS
new turn during interrupt: TYPED REJECT interrupt_in_progress / PASS
multiple turn terminal events: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
FW-RT6-9b tasks: 7 / 7 ACCEPTED-CANDIDATE
FW-RT6-9b final acceptance sync: NOT_AUTHORIZED
FW-RT6-9c implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted explicit interrupt-ordering policy, the
`RealtimeSession` runtime owner, and the reentrant corrective. The existing
session and resolved-turn identity remains the sole idempotency key; no public
interrupt request ID or second ownership path is introduced.

The first admission executes subsystem coordination and owns the interrupt
terminal reservation. Concurrent and later duplicates wait outside the
operation lock and replay the exact owner result without repeating subsystem,
flush, or event effects. Same-owner synchronous interrupt callbacks receive the
prepared immutable owner result without self-wait, while a same-owner reentrant
flush receives the prepared typed flush result with one flush effect.

First terminal reservation continues to resolve normal completion versus
interrupt, and first admission continues to resolve close versus interrupt. An
owner-requested flush precedes the interrupt terminal; a standalone same-turn
flush cannot repeat it. New-turn admission during active interrupt work remains
an immediate typed `interrupt_in_progress` rejection. Unsupported paths do not
claim an unobserved terminal or physical effect.

Control C changes no runtime source. It adds the aggregate regression gate and
closes the seven FW-RT6-9b task checkboxes only as aggregate acceptance
candidates. Final closed status remains deferred to a reviewed, committed,
pushed, and remotely verified one-file final acceptance sync. FW-RT6-9c
barge-in decision and execution remains not authorized.
<!-- FW-RT6-9b-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-9b-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9b — interrupt ordering final acceptance sync

```text
checkpoint: FW-RT6-9b final acceptance
baseline head: 92843ffb559f54e54c8f8b80c87f3fdec981e2aa
Control A implementation: b2557a6aa08a3af89ea527413dc37ac85f458d05
Control A acceptance sync: e92f6929fd673c1c1b53cbcb19a2c5a23e446e56
Control B implementation: 6b9a9629239f969a51325cbf35d0e4be444c5689
Control B corrective: 1f05e9d6da9ccbd29c198f577cf8155318b06486
Control B acceptance sync: 941887a36e530be77aaa2406251913166b976734
Control C aggregate implementation: 92843ffb559f54e54c8f8b80c87f3fdec981e2aa
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A interrupt-ordering tests: 12 / PASS
focused Control B interrupt-ordering tests: 11 / PASS
full Framework unit suite: 442 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-9a aggregate regression: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
explicit package: framework.interrupt_ordering / PASS
ordering rules: 6 EXACT / PASS
admission outcomes: 5 EXACT / PASS
public interrupt request ID introduced: False / ACCEPTED
idempotency key: (session_id, resolved_turn_id) / PASS
whole-request owner: RealtimeSession PRIVATE / PASS
duplicate wait outside operation lock: True / PASS
duplicate result: EXACT OWNER InterruptResult OBJECT / PASS
duplicate subsystem/flush/event effects repeated: False / PASS
same-owner interrupt callback replay: EXACT PREPARED OWNER RESULT / PASS
same-owner interrupt callback self-deadlock: False / PASS
normal completion race: FIRST TERMINAL RESERVATION WINS / PASS
unsupported interrupt overclaims turn terminal: False / PASS
close race: FIRST ADMISSION WINS / PASS
owner flush before terminal: True / PASS
standalone flush repeats owner effect: False / PASS
same-owner reentrant flush: PREPARED RESULT REUSE / PASS
same-owner reentrant flush effect count: 1 / PASS
new turn during interrupt: TYPED REJECT interrupt_in_progress / PASS
multiple turn terminal events: False / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
barge-in decision/execution changed: False
FW-RT6-9b tasks: 7 / 7 ACCEPTED
FW-RT6-9b aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-9c exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-9c implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-9b is accepted as the provider-neutral whole-request interrupt-ordering
boundary. The existing Framework session identity and the turn resolved once at
admission form the sole idempotency key; no second public interrupt request ID
is introduced. The first admission owns subsystem execution and the interrupt
terminal reservation. Concurrent and later duplicates wait outside the
operation lock and replay the exact owner `InterruptResult` without repeating
subsystem, flush, interrupt-event, or turn-terminal effects.

The immutable owner result is prepared before synchronous Framework interrupt
callbacks, so a same-owner reentrant interrupt or cancel returns that exact
result without waiting on its own completion event. The typed owner flush result
is likewise prepared before the synchronous flush callback, so reentrant and
standalone same-turn flush requests cannot repeat the owner effect.

Normal completion versus interrupt remains first terminal reservation wins,
while close versus interrupt remains first admission wins. An owner-requested
flush completes before the interrupt terminal. A genuinely new turn during
active interrupt work receives the existing typed `interrupt_in_progress`
rejection. Unsupported paths do not claim an unobserved terminal or physical
effect, and exactly one turn-terminal event remains authoritative.

This sync closes FW-RT6-9b only. It changes no runtime source and does not add
barge-in decision or execution behavior. It authorizes FW-RT6-9c exact contract
review after this sync is committed, pushed, and remotely verified, not
FW-RT6-9c implementation.
<!-- FW-RT6-9b-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9c-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9c Control A — barge-in control-plan contract acceptance sync

```text
checkpoint: FW-RT6-9c Control A
baseline head: f6921f1933f0d4efa1463bcf23710cd46f528280
FW-RT6-9b final acceptance: 42dcf194909504a1a09ea6612d81db1b56a008f9
Control A implementation: f6921f1933f0d4efa1463bcf23710cd46f528280
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A surface: 5 files
dedicated Control A source gate: PASS
focused Control A barge-in-control tests: 12 / PASS
full Framework unit suite: 454 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-9a aggregate regression: PASS
accepted FW-RT6-9b aggregate regression: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
stable explicit package: framework.barge_in_control / PASS
explicit package exports: 2 EXACT / PASS
decision != execution: True / ACCEPTED
control plan side-effect-free: True / PASS
barge-in policy triggers microphone: False / ACCEPTED
rejected decision executes: False / PASS
unsupported flush execution: False / PASS
unsupported hard cancel effective mode: soft_interrupt / ACCEPTED
capability downgrade truthful: True / ACCEPTED
requested/supported/planned facts separated: True / PASS
coordinator request reason: user_barge_in / PASS
root import loads framework.barge_in_control eagerly: False / PASS
create_realtime_session signature: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
runtime source changed by Control A: False
provider/network/audio/microphone/real VTS execution: False / PASS
RealtimeSession plan adoption: DEFERRED_TO_CONTROL_B
actual execution delegation: DEFERRED_TO_CONTROL_B
interrupt owner/coordinator reuse: DEFERRED_TO_CONTROL_B
execution result and event ordering: DEFERRED_TO_CONTROL_B
FW-RT6-9c aggregate: NOT_COMPLETED
FW-RT6-9c tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-9d implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the explicit provider-neutral boundary between a barge-in
policy decision and its future runtime execution. `BargeInControlPlan` and
`build_barge_in_control_plan(...)` remain explicit-package symbols rather than
Framework root exports. Building or inspecting a plan cannot execute an
interrupt, flush output, stop motion, call a provider, or acquire microphone
input.

One immutable `BargeInDecision` and one immutable
`RealtimeCapabilitySnapshot` determine the exact plan. Requested, supported,
and planned effects remain separate. Rejected and disabled decisions carry no
coordinator request. An unsupported flush-only request becomes non-executing,
while a hard-cancel or turn-takeover request without provider hard-cancel
capability is truthfully downgraded to `soft_interrupt` without claiming a
provider hard-cancel effect. A supported queue flush may remain in that weaker
plan and every generated request retains the existing `user_barge_in` reason
and resolved turn identity.

Control A changes no `RealtimeSession` runtime source, factory signature, root
public surface, event vocabulary, or API version. Host applications remain the
owner of microphone/speech-activity detection. Runtime plan adoption, exact
delegation to the accepted whole-request interrupt owner/coordinator, and
execution result/event ordering remain Control B work. Therefore all five
FW-RT6-9c aggregate task checkboxes stay open.

This sync authorizes only Control B exact contract review after the sync is
committed, pushed, and remotely verified. It does not authorize Control B or
FW-RT6-9d implementation.
<!-- FW-RT6-9c-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9c-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9c Control B — ordered barge-in execution acceptance sync

```text
checkpoint: FW-RT6-9c Control B
baseline head: 99993eaedf9956a87c21799bce090ab224884e50
FW-RT6-9b final acceptance: 42dcf194909504a1a09ea6612d81db1b56a008f9
Control A implementation: f6921f1933f0d4efa1463bcf23710cd46f528280
Control A acceptance sync: 4f1fdc0de949f236703c0e6d23a8d43abf8636e5
Control B implementation: 99993eaedf9956a87c21799bce090ab224884e50
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B implementation surface: 7 files
dedicated Control B source gate: PASS
focused Control B barge-in execution tests: 12 / PASS
focused Control A+B barge-in tests: 24 / PASS
full Framework unit suite: 466 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-9a aggregate regression: PASS
accepted FW-RT6-9b aggregate regression: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
stable explicit plan package: framework.barge_in_control / PASS
RealtimeSession.execute_barge_in(plan): ADOPTED / PASS
decision automatically executes: False / PASS
exact coordinator request delegation: SAME OBJECT / PASS
whole-request ordered interrupt owner reused: True / PASS
second interrupt/terminal/flush owner introduced: False / PASS
plan capability/session mismatch: REJECTED / PASS
non-executing plan result: InterruptOutcome.UNSUPPORTED / PASS
non-executing plan interrupt/flush/event effects: False / PASS
unsupported flush execution: False / PASS
unsupported hard cancel effective mode: soft_interrupt / PASS
duplicate result: EXACT OWNER InterruptResult OBJECT / PASS
duplicate subsystem/flush/event effects repeated: False / PASS
barge-in event order: DECISION BEFORE INTERRUPT BEFORE TERMINAL / PASS
multiple turn terminal events: False / PASS
barge-in policy triggers microphone: False / PASS
BargeInPolicy flush field/factory collision: FIXED / COMPATIBLE / PASS
root import loads framework.barge_in_control eagerly: False / PASS
create_realtime_session signature: UNCHANGED / PASS
InterruptRequest / InterruptResult fields: UNCHANGED / PASS
event vocabulary: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-9c aggregate: NOT_COMPLETED
FW-RT6-9c tasklist: 0 / 5 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-9d implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts `RealtimeSession.execute_barge_in(plan)` as the explicit
provider-neutral execution boundary. Host code remains responsible for
microphone, speech-activity, and barge-in detection. A policy decision and its
immutable control plan do not execute themselves; the host must explicitly
submit the validated plan to the session.

An executing plan hands its exact `coordinator_request` object to the accepted
whole-request ordered interrupt owner. Control B adds no parallel coordinator,
terminal registry, flush owner, or event sequencer. Concurrent and later
execution for the same resolved turn therefore replays the exact owner
`InterruptResult` without repeating stage cancellation, queue/output effects,
interrupt events, or the single turn-terminal event.

The plan's provider-hard-cancel and queue-flush capability facts must agree
with the executing session. A mismatch is rejected rather than reinterpreted.
Rejected, disabled, and unsupported flush-only plans carry no coordinator
request and return a typed unsupported result without interrupt, flush, motion,
terminal, or event effects. Unsupported hard cancel and turn takeover retain
their truthful `soft_interrupt` downgrade and cannot claim provider execution.

Existing barge-in decision events precede the existing ordered interrupt event
sequence and its terminal event. No event type, root export, factory parameter,
`InterruptRequest`/`InterruptResult` field, or API version changes. The
`BargeInPolicy.flush_output()` factory remains compatible while its colliding
instance field is restored to a truthful boolean default.

Control B does not close any of the five FW-RT6-9c aggregate task checkboxes.
Aggregate acceptance remains Control C work. This sync authorizes only Control
C exact contract review after the sync is committed, pushed, and remotely
verified; it does not authorize Control C or FW-RT6-9d implementation.
<!-- FW-RT6-9c-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-9c Control C — barge-in decision/execution aggregate acceptance

```text
checkpoint: FW-RT6-9c Control C aggregate acceptance candidate
baseline head: 080070b740c7178623f578b134945df3c0dd513f
FW-RT6-9b final acceptance: 42dcf194909504a1a09ea6612d81db1b56a008f9
Control A implementation: f6921f1933f0d4efa1463bcf23710cd46f528280
Control A acceptance sync: 4f1fdc0de949f236703c0e6d23a8d43abf8636e5
Control B implementation: 99993eaedf9956a87c21799bce090ab224884e50
Control B acceptance sync: 080070b740c7178623f578b134945df3c0dd513f
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
dedicated Control C aggregate gate: PASS
focused Control A barge-in tests: 12 / PASS
focused Control B barge-in tests: 12 / PASS
focused Control A+B barge-in tests: 24 / PASS
full Framework unit suite: 466 / PASS
stable explicit plan package: framework.barge_in_control / PASS
decide_barge_in policy/execution effects: False / PASS
decision automatically executes: False / PASS
control plan side effects: False / PASS
decision to control plan: EXPLICIT HOST STEP / PASS
RealtimeSession.execute_barge_in(plan): ADOPTED / PASS
exact coordinator request delegation: SAME OBJECT / PASS
whole-request ordered interrupt owner reused: True / PASS
second interrupt/terminal/flush owner introduced: False / PASS
duplicate result: EXACT OWNER InterruptResult OBJECT / PASS
duplicate subsystem/flush/event effects repeated: False / PASS
barge-in event order: DECISION BEFORE INTERRUPT BEFORE TERMINAL / PASS
multiple turn terminal events: False / PASS
microphone detection in core: False / PASS
barge-in policy triggers microphone: False / PASS
provider hard cancel without capability: NOT_PLANNED / PASS
unsupported hard cancel effective mode: soft_interrupt / PASS
unsupported flush execution: False / PASS
capability mismatch execution: REJECTED / PASS
BargeInPolicy flush field/factory compatibility: PASS
root import loads framework.barge_in_control eagerly: False / PASS
create_realtime_session signature: UNCHANGED / PASS
InterruptRequest / InterruptResult fields: UNCHANGED / PASS
event vocabulary: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
existing tests changed by Control C: False
FW-RT6-9c tasks: 5 / 5 ACCEPTED-CANDIDATE
FW-RT6-9c final acceptance sync: NOT_AUTHORIZED
FW-RT6-9d implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted provider-neutral decision model, immutable
control-plan projection, and ordered runtime execution boundary. The host
remains responsible for observing microphone or speech activity, explicitly
requesting a policy decision, building a plan from the session capability
snapshot, and submitting that plan for execution.

Decision and planning remain non-executing. `decide_barge_in(...)` emits only
the accepted decision events and does not interrupt, flush, cancel, stop
motion, or reserve a terminal. Building `BargeInControlPlan` is a side-effect-
free projection. Runtime work begins only when the host explicitly calls
`execute_barge_in(plan)`.

An executing plan hands its exact immutable `coordinator_request` to the sole
whole-request ordered interrupt owner. Existing duplicate convergence, flush
ordering, terminal reservation, close ordering, and event sequencing remain
authoritative. No second coordinator, terminal registry, flush owner, or event
sequencer is introduced.

Capability downgrade remains truthful and monotonic. Unsupported provider hard
cancel and turn takeover become `soft_interrupt` without provider-cancel or
unsupported queue claims. An unsupported flush-only plan remains non-executing,
and a plan whose capability facts disagree with the executing session is
rejected before effects.

Control C changes no runtime source or existing test. It adds the aggregate
regression gate and closes the five FW-RT6-9c task checkboxes only as aggregate
acceptance candidates. Final closed status remains deferred to a reviewed,
committed, pushed, and remotely verified one-file final acceptance sync.
FW-RT6-9d implementation remains not authorized.
<!-- FW-RT6-9c-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-9c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9c — barge-in decision/execution final acceptance sync

```text
checkpoint: FW-RT6-9c final acceptance
baseline head: 1ad274a10d861fbd35c2933d0c78cbcc1ea5a4ca
FW-RT6-9b final acceptance: 42dcf194909504a1a09ea6612d81db1b56a008f9
Control A implementation: f6921f1933f0d4efa1463bcf23710cd46f528280
Control A acceptance sync: 4f1fdc0de949f236703c0e6d23a8d43abf8636e5
Control B implementation: 99993eaedf9956a87c21799bce090ab224884e50
Control B acceptance sync: 080070b740c7178623f578b134945df3c0dd513f
Control C aggregate implementation: 1ad274a10d861fbd35c2933d0c78cbcc1ea5a4ca
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A barge-in tests: 12 / PASS
focused Control B barge-in tests: 12 / PASS
focused Control A+B barge-in tests: 24 / PASS
full Framework unit suite: 466 / PASS
v5.2 interrupt/output-control public-contract gate: PASS
accepted FW-RT6-9a aggregate regression: PASS
accepted FW-RT6-9b aggregate regression: PASS
accepted FW-RT6-8c aggregate regression: PASS
accepted FW-RT6-8b lifecycle aggregate regression: PASS
v5.2 motion public-contract gate: PASS
v5.5 MotionSession real-adapter composition regression: PASS
accepted FW-RT6-8a correlation regression: PASS
stable explicit plan package: framework.barge_in_control / PASS
decision != execution: True / PASS
decision automatically executes: False / PASS
control plan side effects: False / PASS
decision to control plan: EXPLICIT HOST STEP / PASS
execution boundary: RealtimeSession.execute_barge_in(plan) / PASS
exact coordinator request delegation: SAME OBJECT / PASS
whole-request ordered interrupt owner reused: True / PASS
second interrupt/terminal/flush owner introduced: False / PASS
duplicate result: EXACT OWNER InterruptResult OBJECT / PASS
duplicate subsystem/flush/event effects repeated: False / PASS
barge-in event order: DECISION BEFORE INTERRUPT BEFORE TERMINAL / PASS
multiple turn terminal events: False / PASS
microphone detection in core: False / PASS
barge-in policy triggers microphone: False / PASS
provider hard cancel without capability: NOT_PLANNED / PASS
unsupported hard cancel effective mode: soft_interrupt / PASS
unsupported flush execution: False / PASS
capability mismatch execution: REJECTED / PASS
BargeInPolicy flush field/factory compatibility: PASS
root import loads framework.barge_in_control eagerly: False / PASS
create_realtime_session signature: UNCHANGED / PASS
InterruptRequest / InterruptResult fields: UNCHANGED / PASS
event vocabulary: UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
actual pyvts/WebSocket/microphone import: False / PASS
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
existing tests changed by Control C/final sync: False
FW-RT6-9c tasks: 5 / 5 ACCEPTED
FW-RT6-9c aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-9d exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-9d implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-9c is accepted as the provider-neutral separation between host-observed
barge-in detection, policy decision, immutable control planning, and ordered
runtime execution. Framework core does not open a microphone or detect speech
activity. The host explicitly requests a decision, builds a plan from the
session capability snapshot, and chooses whether to submit it for execution.

Decision and planning remain non-executing. `decide_barge_in(...)` emits only
the existing decision events and does not interrupt, flush, cancel a stage,
stop motion, or reserve a terminal. Building `BargeInControlPlan` remains a
side-effect-free projection with requested, supported, effective, and planned
facts kept distinct.

Execution begins only at `RealtimeSession.execute_barge_in(plan)`. The exact
plan-owned `coordinator_request` is delegated to the existing whole-request
ordered interrupt owner. Existing session/turn idempotency, duplicate replay,
flush ordering, terminal reservation, close ordering, and event sequencing
remain authoritative, with no second coordinator or effect owner.

Capability downgrade remains truthful. Unsupported provider hard cancel and
turn takeover execute only the supported `soft_interrupt` request. Unsupported
flush-only plans remain non-executing, and capability-mismatched plans are
rejected before effects. No provider, queue, motion, terminal, or microphone
effect is claimed unless the accepted capability and execution path support it.

This sync closes FW-RT6-9c only. It changes no runtime source or existing test
and introduces no FW-RT6-9d stale-result enforcement. It authorizes FW-RT6-9d
exact contract review after this one-file sync is committed, pushed, and
remotely verified; it does not authorize FW-RT6-9d implementation.
<!-- FW-RT6-9c-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9d-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9d Control A — atomic stale-delivery ingress acceptance sync

```text
checkpoint: FW-RT6-9d Control A
baseline head: b3fe5c29eafad281c1887dc6989627fba74f6fd0
FW-RT6-9c final acceptance: 9bb6571d3c29a2c5be444cc1b6a49a3ef94225ef
Control A implementation: b3fe5c29eafad281c1887dc6989627fba74f6fd0
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A implementation surface: 5 files
dedicated Control A source gate: PASS
focused Control A stale-delivery tests: 13 / PASS
full Framework unit suite: 479 / PASS
existing freshness owner: RealtimeGenerationGate / REUSED / PASS
second freshness registry introduced: False / PASS
atomic operation: RealtimeGenerationGate.apply_completion / PASS
freshness check and bounded delivery lock section: SAME / PASS
current completion delivery: EXACTLY ONCE / PASS
retired completion delivered: False / PASS
unknown completion delivered: False / PASS
turn-mismatched completion delivered: False / PASS
competing generation advance during delivery: EXCLUDED / PASS
reentrant generation advance: SAFE / PASS
delivery callback failure automatically retried: False / PASS
delivery callback failure relabeled stale: False / PASS
stale count: EXISTING stale_completion_count / PASS
drop reason: EXISTING typed GenerationAdmissionDecision / PASS
generation diagnostics keys changed: False / PASS
admit_completion behavior changed: False / PASS
Control A delivery vocabulary: 4 EXACT / PASS
text_generation_delta primitive: READY / PASS
voice_input_transcript primitive: READY / PASS
voice_output_artifact primitive: READY / PASS
motion_completion primitive: READY / PASS
root-public generation-gate names added: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
runtime stage delivery paths changed by acceptance sync: False
existing tests changed by acceptance sync: False
FW-RT6-9d aggregate: NOT_COMPLETED
FW-RT6-9d tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-10a implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the atomic application ingress on the existing
`RealtimeGenerationGate`. Freshness classification and one bounded internal
delivery callback execute in the same reentrant gate lock section. A current
completion is applied once before a competing generation advance can proceed;
if a new turn, interrupt, cancel, reset, close, or terminal retirement wins
first, the rejected completion cannot call the delivery callback.

The existing gate remains the sole freshness registry and decision owner.
Control A adds no second generation registry, event sequencer, callback queue,
terminal registry, or provider owner. The existing count-only diagnostics keys
remain unchanged: accepted application uses `accepted_completion_count`, stale
application uses `stale_completion_count`, and the returned typed admission
decision retains the exact stale and retirement reasons.

The accepted primitive fixes four later runtime delivery labels:
`text_generation_delta`, `voice_input_transcript`, `voice_output_artifact`, and
`motion_completion`. Control A does not yet replace those existing stage
delivery paths. Exact adoption by text, transcript, TTS-artifact, and motion
owners remains separately reviewed Control B work.

Therefore Control A closes none of the six FW-RT6-9d aggregate task
checkboxes. This one-file sync authorizes only Control B exact contract review
after it is committed, pushed, and remotely verified. It does not authorize
Control B implementation or FW-RT6-10a recovery/reset implementation.
<!-- FW-RT6-9d-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9d-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9d Control B — end-to-end stale-delivery runtime acceptance sync

```text
checkpoint: FW-RT6-9d Control B
baseline head: c09aa53d262308ceeb8652c29b198898cb94c9c6
FW-RT6-9c final acceptance: 9bb6571d3c29a2c5be444cc1b6a49a3ef94225ef
Control A implementation: b3fe5c29eafad281c1887dc6989627fba74f6fd0
Control A acceptance sync: d01476a02586940dc7950ae18f7c8f2e96f706fe
Control B implementation: c09aa53d262308ceeb8652c29b198898cb94c9c6
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B implementation surface: 10 files
dedicated Control B source gate: PASS
focused Control B stale-delivery tests: 14 / PASS
accepted Control A atomic-ingress regression: 13 / PASS
full Framework unit suite: 493 / PASS
existing freshness owner: RealtimeGenerationGate / REUSED / PASS
second freshness registry introduced: False / PASS
atomic text delta application: PASS
atomic voice-input transcript application: PASS
atomic voice-output artifact application: PASS
atomic motion completion application: PASS
exact delivery vocabulary: 4 / PASS
text_generation_delta: ADOPTED / PASS
voice_input_transcript: ADOPTED / PASS
voice_output_artifact: ADOPTED / PASS
motion_completion: ADOPTED / PASS
generation check and bounded application lock section: SAME / PASS
competing generation advance during application: EXCLUDED / PASS
new turn old text delta delivered: False / PASS
abort/close old transcript delivered: False / PASS
retired TTS audio handoff exposed: False / PASS
retired motion completed event published: False / PASS
provider-created stale FW artifact invalidated: True / PASS
stale count: EXISTING stale_completion_count / PASS
drop reason: EXISTING typed GenerationAdmissionDecision / PASS
generation diagnostics keys changed: False / PASS
event vocabulary changed: False / PASS
root-public generation-gate names added: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by acceptance sync: False
existing tests changed by acceptance sync: False
FW-RT6-9d aggregate: NOT_COMPLETED
FW-RT6-9d tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-10a implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the existing four runtime delivery owners as exact adopters
of the Control A atomic application ingress. Text delta, final transcript,
voice-output artifact, and motion completion delivery all reuse the
session-owned `RealtimeGenerationGate`; no second freshness registry, event
sequencer, terminal owner, provider owner, artifact store, or motion
coordinator is introduced.

For a current generation, the bounded owner-state application completes under
the same gate lock before a competing generation advance can proceed. If a new
turn, abort, close, interrupt, cancel, reset, or terminal retirement wins
first, the exact typed admission decision rejects the envelope and the stale
value cannot cross its existing host-visible boundary.

The provider-neutral text stream preserves standalone gate-less composition.
When composed with the common gate, only accepted deltas update indexing,
delivery counts, and completed history. Voice input keeps provider and
microphone execution outside the gate and guards only final transcript
application; session close retires any in-flight generation before a late
provider result can emit `TRANSCRIPT_FINAL`.

Voice synthesis likewise keeps provider work and playback outside the gate.
The bounded callback publishes only an accepted FW-owned artifact handoff; an
already-created stale artifact is bound only for deterministic invalidation
and is never exposed. Motion reuses the existing state and event owners, so a
rejected result cannot change the motion to completed or publish
`MOTION_COMPLETED`.

The existing completion counters, generation-diagnostic keys, typed stale and
retirement reasons, event vocabulary, result fields, root exports, factory
parameters, and API versions remain unchanged. Control B introduces no
reset/recovery API and closes none of the six FW-RT6-9d aggregate task
checkboxes.

This one-file sync authorizes only Control C exact contract review after it is
committed, pushed, and remotely verified. It does not authorize Control C
implementation or FW-RT6-10a recovery/reset implementation.
<!-- FW-RT6-9d-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-9d-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-9d Control C — end-to-end stale enforcement aggregate acceptance

```text
checkpoint: FW-RT6-9d Control C aggregate acceptance candidate
baseline head: 41ec997f1060a010e9f8d9339f0d9e40177c989f
FW-RT6-9c final acceptance: 9bb6571d3c29a2c5be444cc1b6a49a3ef94225ef
Control A implementation: b3fe5c29eafad281c1887dc6989627fba74f6fd0
Control A acceptance sync: d01476a02586940dc7950ae18f7c8f2e96f706fe
Control B implementation: c09aa53d262308ceeb8652c29b198898cb94c9c6
Control B acceptance sync: 41ec997f1060a010e9f8d9339f0d9e40177c989f
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
dedicated Control C aggregate gate: PASS
focused Control A stale-delivery tests: 13 / PASS
focused Control B stale-delivery tests: 14 / PASS
focused Control A+B stale-delivery tests: 27 / PASS
full Framework unit suite: 493 / PASS
existing freshness owner: RealtimeGenerationGate / REUSED / PASS
second freshness registry introduced: False / PASS
atomic operation: RealtimeGenerationGate.apply_completion / PASS
generation check and bounded application lock section: SAME / PASS
four runtime delivery owners adopted: 4 / 4 / PASS
text delta delivery before generation check: False / PASS
transcript delivery before generation check: False / PASS
TTS artifact publication before generation check: False / PASS
motion completion publication before generation check: False / PASS
new turn old text delta delivered: False / PASS
abort/close old transcript delivered: False / PASS
retired TTS audio handoff exposed: False / PASS
retired motion completed event published: False / PASS
provider-created stale FW artifact invalidated: True / PASS
close/reset/new turn old callback drop: PASS
all stage late-result scenarios: PASS
silent corruption: False / PASS
stale count: EXISTING stale_completion_count / PASS
drop reason: EXISTING typed GenerationAdmissionDecision / PASS
generation diagnostics keys changed: False / PASS
event vocabulary changed: False / PASS
root-public generation-gate names added: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C: False
existing tests changed by Control C: False
FW-RT6-9d tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-9d final acceptance sync: NOT_AUTHORIZED
FW-RT6-10a implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted atomic freshness/application boundary and
its four exact runtime owners. `RealtimeGenerationGate` remains the sole
generation registry and admission owner. Text delta, final transcript,
voice-output artifact, and motion completion values cross their existing
host-visible boundaries only through the accepted `apply_completion(...)`
operation.

For a current generation, one bounded owner-state application completes while
the gate lock still excludes a competing generation advance. If a new turn,
abort, close, interrupt, cancel, reset, or terminal retirement wins first, the
exact typed decision rejects the stale envelope before its value can change
stream history, emit a final transcript, expose an audio handoff, or publish a
completed motion event.

Provider, network, microphone, playback, and VTube Studio work remain outside
the bounded gate callback. A provider-created stale FW voice artifact is
invalidated without exposing its handoff. Existing standalone text-stream
composition remains compatible when no common gate is supplied.

The existing accepted/stale completion counters and typed drop facts remain
authoritative. No generation-diagnostic key, event type, result field, root
export, factory parameter, or API version changes. Control C adds no second
freshness owner and no recovery/reset API.

Control C changes no runtime source or existing test. It adds the aggregate
regression gate and marks the six FW-RT6-9d tasks as acceptance candidates.
Final closed status remains deferred to a reviewed, committed, pushed, and
remotely verified one-file final acceptance sync. FW-RT6-10a implementation
remains not authorized.
<!-- FW-RT6-9d-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-9d-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-9d — end-to-end stale enforcement final acceptance sync

```text
checkpoint: FW-RT6-9d final acceptance
baseline head: b88cf455ca9bc6a458a7cce6d5cea8a153d53495
FW-RT6-9c final acceptance: 9bb6571d3c29a2c5be444cc1b6a49a3ef94225ef
Control A implementation: b3fe5c29eafad281c1887dc6989627fba74f6fd0
Control A acceptance sync: d01476a02586940dc7950ae18f7c8f2e96f706fe
Control B implementation: c09aa53d262308ceeb8652c29b198898cb94c9c6
Control B acceptance sync: 41ec997f1060a010e9f8d9339f0d9e40177c989f
Control C aggregate implementation: b88cf455ca9bc6a458a7cce6d5cea8a153d53495
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A+B stale-delivery tests: 27 / PASS
full Framework unit suite: 493 / PASS
existing freshness owner: RealtimeGenerationGate / REUSED / PASS
second freshness registry introduced: False / PASS
atomic generation check and bounded application: PASS
four runtime delivery owners adopted: 4 / 4 / PASS
text delta late delivery: False / PASS
final transcript late delivery: False / PASS
TTS artifact late handoff: False / PASS
motion completion late publication: False / PASS
close/reset/new turn old callback drop: PASS
all stage late-result scenarios: PASS
silent corruption: False / PASS
stale count and typed drop reason retained: PASS
generation diagnostics keys changed: False / PASS
event vocabulary changed: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
existing tests changed by Control C/final sync: False
FW-RT6-9d tasks: 6 / 6 ACCEPTED
FW-RT6-9d aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-10a exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-10a implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-9d closes the provider-neutral end-to-end stale-result enforcement
boundary. `RealtimeGenerationGate` remains the sole freshness owner, and the
accepted text, transcript, voice-output, and motion delivery owners remain the
only runtime application boundaries.

Every correlated value reaches its existing host-visible boundary only after
the accepted atomic generation check and bounded owner-state application. A
retired generation therefore cannot mutate stream history, emit a final
transcript, expose an audio handoff, or publish a completed motion event.

Existing accepted and stale counters, typed drop reasons, generation
diagnostics, event vocabulary, public exports, factory parameters, and API
versions remain authoritative and unchanged. Provider, network, microphone,
playback, and VTube Studio execution remain outside the bounded gate callback.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source or existing test. It formally completes, verifies, accepts, commits,
pushes, and closes all three controls and all six FW-RT6-9d aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely
verified, FW-RT6-10a exact contract review is authorized. This sync does not
authorize FW-RT6-10a implementation.
<!-- FW-RT6-9d-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10a Control A — recovery/reset control-plan acceptance sync

```text
checkpoint: FW-RT6-10a Control A
baseline head: dddcd3434bbb43be1c55c9d8a22b53d9ebddb6a0
FW-RT6-9d final acceptance: 48b6554d79c78af95f825639e2a68e7a2f7493b3
Control A implementation: dddcd3434bbb43be1c55c9d8a22b53d9ebddb6a0
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A implementation surface: 5 files
dedicated Control A source gate: PASS
focused Control A recovery/reset tests: 13 / PASS
accepted FW-RT6-9d aggregate regression: 27 / PASS
full Framework unit suite: 506 / PASS
stable explicit package: framework.recovery_control / PASS
existing recovery vocabulary: RecoveryAction / REUSED / PASS
second recovery owner introduced: False / PASS
turn-only reset scope: turn_only / PASS
session reset scope: session / PASS
reset planning requires generation advance: True / PASS
turn reset provider-context loss: DOCUMENTED / PASS
session reset provider-context loss: DOCUMENTED / PASS
reconnect required disposition: TYPED / PASS
close required disposition: TYPED / PASS
permanently failed disposition: TYPED / PASS
reset failure result: RecoveryResetResult / TYPED / PASS
reset failure error: RecoveryResetErrorCode / PUBLIC_SAFE / PASS
applied reset distinct generations required: True / PASS
failed reset claims generation advance: False / PASS
decision automatically executes: False / PASS
RealtimeSession.reset exists: False / PASS
root import loads framework.recovery_control eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/real VTS execution: False / PASS
FW-RT6-10a aggregate: NOT_COMPLETED
FW-RT6-10a tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
FW-RT6-10b implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts `framework.recovery_control` as the stable explicit planning
package. The existing root-public `RecoveryAction` remains the sole recovery
decision vocabulary; the plan adds no parallel recovery owner and does not
reinterpret a terminal turn result.

`reset_turn` and `reset_session` project to the explicit `turn_only` and
`session` scopes. Both plans truthfully require a generation advance before a
new correlated value may be accepted. Control A does not perform that advance,
allocate a replacement generation, mutate session state, call a provider, or
add `RealtimeSession.reset()`.

Turn-only reset documents loss of active-turn provider and in-flight stage
context. Session reset additionally documents loss of provider conversation
and provider-session context. Reconnect, close, and permanent failure retain
separate typed dispositions and cannot be relabeled as successful reset.

`RecoveryResetResult` fixes the later execution result vocabulary. Applied
reset requires distinct previous/current generation identities. Failed reset
requires a public-safe `RecoveryResetErrorCode` and cannot claim generation
advance. No raw provider exception, payload, credential, transcript, path, or
application-private value is retained.

Control A closes none of the seven FW-RT6-10a aggregate task checkboxes. This
one-file sync authorizes only Control B exact contract review after it is
committed, pushed, and remotely verified. It does not authorize Control B
runtime implementation or FW-RT6-10b implementation.
<!-- FW-RT6-10a-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10a Control B — recovery/reset execution acceptance sync

```text
checkpoint: FW-RT6-10a Control B
baseline head: d91430aff9aba804b37f3849fc7134e1eda19c6f
FW-RT6-9d final acceptance: 48b6554d79c78af95f825639e2a68e7a2f7493b3
Control A implementation: dddcd3434bbb43be1c55c9d8a22b53d9ebddb6a0
Control A acceptance sync: 2fe31e3c6a18f62696cd12f4f153c026d6f113a6
Control B implementation: d91430aff9aba804b37f3849fc7134e1eda19c6f
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control B implementation surface: 10 files
dedicated Control B source gate: PASS
focused Control B recovery/reset tests: 14 / PASS
focused Control A+B recovery/reset tests: 27 / PASS
accepted FW-RT6-9d aggregate regression: 27 / PASS
full Framework unit suite: 520 / PASS
stable explicit package: framework.recovery_control / PASS
existing recovery vocabulary: RecoveryAction / REUSED / PASS
second recovery owner introduced: False / PASS
existing generation owner: RealtimeGenerationGate / REUSED / PASS
second generation registry introduced: False / PASS
explicit execution boundary: RealtimeSession.reset(plan) / ADOPTED / PASS
decision automatically executes: False / PASS
non-reset plan side effects: False / PASS
turn-only reset scope: turn_only / PASS
session reset scope: session / PASS
applied reset replacement generations: EXACTLY 1 / PASS
active nonterminal turn replacement binding: SAME TURN / PASS
terminal turn replacement handoff: NEXT TURN / EXACT / PASS
reset-retired old completion delivered: False / PASS
reset retirement reason: GenerationRetirementReason.RESET / PASS
completion/reset race: LINEARIZED / PASS
missing generation reset failure: TYPED / PASS
closed session reset failure: TYPED / PASS
active operation reset failure: TYPED / PASS
failed reset claims generation advance: False / PASS
generation diagnostics keys changed: False / PASS
event vocabulary changed: False / PASS
root import loads framework.recovery_control eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-10a aggregate: NOT_COMPLETED
FW-RT6-10a tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-10b implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts `RealtimeSession.reset(plan)` as the explicit typed execution
boundary for the accepted Control A recovery plan. A recovery decision and its
immutable plan still do not execute themselves; host code must explicitly
submit the plan to the session.

The session reuses its sole `RealtimeGenerationGate`. Each applied reset
retires the previous generation with the existing typed `RESET` reason and
reserves exactly one replacement generation. An active nonterminal turn is
rebound to that replacement; after a terminal turn, the exact replacement is
held for and consumed by the next turn.

Reset execution and completion admission share the existing serialized session
operation boundary. A completion from the reset-retired generation therefore
cannot cross its owner delivery boundary. The existing stale counter, typed
drop reason, retirement facts, and generation diagnostics remain authoritative.

Non-reset plans return their typed non-reset result without session effects.
Missing generation context, closed-session admission, and active-operation
conflicts return typed reset failures and cannot claim a generation advance.
Control B adds no provider call, reconnect, close/dispose implementation,
playback action, microphone action, or VTube Studio execution.

No second recovery owner, generation registry, event type, root export, factory
parameter, result field, or API version is introduced. The recovery package
remains an explicit lazy import and the existing root-public surface remains
unchanged.

Control B closes none of the seven FW-RT6-10a aggregate task checkboxes. This
one-file sync authorizes only Control C exact contract review after it is
committed, pushed, and remotely verified. It does not authorize Control C
aggregate implementation or FW-RT6-10b implementation.
<!-- FW-RT6-10a-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-10a Control C — recovery/reset aggregate acceptance

```text
checkpoint: FW-RT6-10a Control C aggregate acceptance candidate
baseline head: bcfb77922d219da56697430e42e21e95c3b6cd62
FW-RT6-9d final acceptance: 48b6554d79c78af95f825639e2a68e7a2f7493b3
Control A implementation: dddcd3434bbb43be1c55c9d8a22b53d9ebddb6a0
Control A acceptance sync: 2fe31e3c6a18f62696cd12f4f153c026d6f113a6
Control B implementation: d91430aff9aba804b37f3849fc7134e1eda19c6f
Control B acceptance sync: bcfb77922d219da56697430e42e21e95c3b6cd62
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
dedicated Control C aggregate gate: PASS
focused Control A recovery/reset tests: 13 / PASS
focused Control B recovery/reset tests: 14 / PASS
focused Control A+B recovery/reset tests: 27 / PASS
accepted FW-RT6-9d aggregate regression: 27 / PASS
full Framework unit suite: 520 / PASS
stable explicit package: framework.recovery_control / PASS
existing recovery vocabulary: RecoveryAction / REUSED / PASS
second recovery owner introduced: False / PASS
existing generation owner: RealtimeGenerationGate / REUSED / PASS
second generation registry introduced: False / PASS
interrupt recovery action: RecoveryAction.RESET_TURN / TYPED / PASS
reusable disposition: not_required / TYPED / PASS
turn-only reset scope: turn_only / PASS
session reset scope: session / PASS
reconnect required disposition: TYPED / PASS
close required disposition: TYPED / PASS
permanently failed disposition: TYPED / PASS
reset provider-context loss: DOCUMENTED / PASS
reset generation advance: EXACTLY 1 / PASS
active nonterminal turn replacement binding: SAME TURN / PASS
terminal turn replacement handoff: NEXT TURN / EXACT / PASS
old completion after reset delivered: False / PASS
reset retirement reason: GenerationAdvanceReason.RESET / PASS
completion/reset race: LINEARIZED / PASS
reset failure: TYPED / PASS
failed reset claims generation advance: False / PASS
non-reset disposition side effects: False / PASS
provider reset/reconnect/close execution: False / PASS
generation diagnostics keys changed: False / PASS
event vocabulary changed: False / PASS
new reset event type: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C: False
existing tests changed by Control C: False
FW-RT6-10a tasks: 7 / 7 ACCEPTED-CANDIDATE
FW-RT6-10a final acceptance sync: NOT_AUTHORIZED
FW-RT6-10b implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted recovery planning and session-owned reset
execution contracts without changing runtime source. The existing root-public
`RecoveryAction` remains the sole recovery decision vocabulary, and
`framework.recovery_control` remains the stable explicit package for immutable
plans and typed results.

`reset_turn` and `reset_session` retain the explicit `turn_only` and `session`
scopes. Turn reset documents loss of active-turn provider and in-flight stage
context. Session reset additionally documents loss of provider conversation
and provider-session context. `reconnect`, `close_session`, and
`permanent_failure` remain typed non-reset dispositions and are not executed or
relabeled as successful reset.

`RealtimeSession.reset(plan)` reuses the sole `RealtimeGenerationGate`. One
accepted reset retires the previous generation with the existing `RESET`
reason and creates exactly one distinct replacement generation. A nonterminal
turn is rebound to that replacement; after a terminal turn, the exact
replacement is consumed by the next explicitly admitted turn.

Reset and completion application remain serialized by the existing session
operation boundary. A reset-retired completion cannot reach its delivery
callback. Missing generation context, closed-session admission, and active
operation conflicts retain public-safe typed failures and never claim a
generation advance.

Control C changes no runtime source or existing test. It adds the aggregate
regression gate and marks all seven FW-RT6-10a tasks as acceptance candidates.
Final closed status remains deferred to a reviewed, committed, pushed, and
remotely verified one-file final acceptance sync. FW-RT6-10b implementation
remains not authorized.
<!-- FW-RT6-10a-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-10a-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10a — recovery/reset semantics final acceptance sync

```text
checkpoint: FW-RT6-10a final acceptance
baseline head: d5738f6e7c24caa508cd82b63a772d662b0bdf73
FW-RT6-9d final acceptance: 48b6554d79c78af95f825639e2a68e7a2f7493b3
Control A implementation: dddcd3434bbb43be1c55c9d8a22b53d9ebddb6a0
Control A acceptance sync: 2fe31e3c6a18f62696cd12f4f153c026d6f113a6
Control B implementation: d91430aff9aba804b37f3849fc7134e1eda19c6f
Control B acceptance sync: bcfb77922d219da56697430e42e21e95c3b6cd62
Control C aggregate implementation: d5738f6e7c24caa508cd82b63a772d662b0bdf73
Control C remote verification: PASS
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C exact surface: 3 files / PASS
aggregate gate: PASS
focused Control A+B recovery/reset tests: 27 / PASS
accepted FW-RT6-9d aggregate regression: 27 / PASS
full Framework unit suite: 520 / PASS
stable explicit package: framework.recovery_control / PASS
existing recovery vocabulary: RecoveryAction / REUSED / PASS
second recovery owner introduced: False / PASS
existing generation owner: RealtimeGenerationGate / REUSED / PASS
second generation registry introduced: False / PASS
interrupt recovery action: RecoveryAction.RESET_TURN / TYPED / PASS
reusable disposition: not_required / TYPED / PASS
turn-only reset scope: turn_only / PASS
session reset scope: session / PASS
reconnect required disposition: TYPED / PASS
close required disposition: TYPED / PASS
permanently failed disposition: TYPED / PASS
reset provider-context loss: DOCUMENTED / PASS
reset generation advance: EXACTLY 1 / PASS
active nonterminal turn replacement binding: SAME TURN / PASS
terminal turn replacement handoff: NEXT TURN / EXACT / PASS
old completion after reset delivered: False / PASS
reset retirement reason: GenerationAdvanceReason.RESET / PASS
completion/reset race: LINEARIZED / PASS
reset failure: TYPED / PASS
failed reset claims generation advance: False / PASS
non-reset disposition side effects: False / PASS
provider reset/reconnect/close execution: False / PASS
generation diagnostics keys changed: False / PASS
event vocabulary changed: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
existing tests changed by Control C/final sync: False
FW-RT6-10a tasks: 7 / 7 ACCEPTED
FW-RT6-10a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-10b exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-10b implementation: NOT_AUTHORIZED
final acceptance-sync exact surface: 1 file
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-10a closes the provider-neutral recovery/reset boundary. The existing
root-public `RecoveryAction` remains the sole recovery decision vocabulary,
`framework.recovery_control` remains the stable explicit planning and result
package, and `RealtimeGenerationGate` remains the sole generation owner.

Turn-only and session reset retain their accepted explicit scopes and provider
context-loss documentation. Reconnect, close, and permanent failure remain
typed non-reset dispositions. One applied reset creates exactly one distinct
replacement generation, and a reset-retired completion cannot reach its
delivery boundary. Reset failure remains public-safe and cannot claim a
generation advance.

Existing diagnostics, event vocabulary, root exports, factory parameters, and
API versions remain unchanged. Provider, network, audio, microphone, playback,
and real VTube Studio execution remain outside this contract.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, aggregate gate, or existing test. It formally completes, verifies,
accepts, commits, pushes, and closes all three controls and all seven
FW-RT6-10a aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-10b exact contract review is authorized. This sync does not authorize
FW-RT6-10b implementation.
<!-- FW-RT6-10a-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10b Control A — session close/dispose control-plan acceptance sync

```text
checkpoint: FW-RT6-10b Control A
baseline head: d0e977193faafbcc60e17436f4c2b5bb5547683a
FW-RT6-10a final acceptance: ffb67d8cf089cf0b9e0d0c517614517186201a17
Control A implementation: d0e977193faafbcc60e17436f4c2b5bb5547683a
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A implementation surface: 5 files
dedicated Control A source gate: PASS
focused Control A session-close tests: 12 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 532 / PASS
stable explicit package: framework.session_close / PASS
session close owner: public session / REUSED / PASS
second close owner introduced: False / PASS
active turn terminal outcome: TurnOutcome.CLOSED / TYPED / PASS
cleanup targets: 5 / TYPED / PASS
stage cleanup timeout: PLANNED / NOT_EXECUTED
provider-client cleanup timeout: PLANNED / NOT_EXECUTED
execution-bridge cleanup timeout: PLANNED / NOT_EXECUTED
callback-hub cleanup: TYPED / NOT_EXECUTED
duplicate close outcome: already_closed / PASS
duplicate close re-runs cleanup: False / PASS
cleanup failure reopens session: False / PASS
cleanup diagnostics: COUNT_ONLY / PUBLIC_SAFE / PASS
plan automatically executes: False / PASS
runtime close/dispose adoption: DEFERRED_TO_CONTROL_B
root import loads framework.session_close eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-10b aggregate: NOT_COMPLETED
FW-RT6-10b tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
Control C: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts `framework.session_close` as the stable explicit planning
and result package for unified close/dispose semantics. The public session
remains the lifecycle owner. The plan does not introduce a second close owner,
invoke a session method, terminate a turn, close a callback hub, call a
provider, or shut down an execution bridge.

An active nonterminal turn is planned to reach the existing typed
`TurnOutcome.CLOSED` terminal outcome before session cleanup completes. Stage,
provider-client, callback-hub, and execution-bridge cleanup remain distinct
typed targets. Stage, provider-client, and bridge cleanup carry finite planned
deadlines, while actual timeout enforcement remains deferred to Control B.

A successful first close is distinct from `already_closed`. Repeated close is
idempotent and plans no repeated cleanup. Cleanup timeout or failure remains a
truthful typed result but never reopens the session. Diagnostics retain only
bounded public-safe counts and messages; they retain no raw provider exception,
payload, credential, transcript, path, or application-private value.

Control A changes no existing runtime close path and closes none of the seven
FW-RT6-10b aggregate task checkboxes. This one-file sync authorizes only
Control B exact contract review after it is committed, pushed, and remotely
verified. It does not authorize Control B runtime implementation or Control C.
<!-- FW-RT6-10b-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10b Control B — unified close/dispose runtime acceptance sync

```text
checkpoint: FW-RT6-10b Control B
baseline head: 98c6455640be1eed737478c195616b2ff12840bb
Control A implementation: d0e977193faafbcc60e17436f4c2b5bb5547683a
Control A acceptance sync: 6153661b3960fbfa1130b2caef39e48717ad8e80
Control B implementation: 98c6455640be1eed737478c195616b2ff12840bb
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control B implementation surface: 11 files
dedicated Control B source gate: PASS
focused Control B session-close tests: 13 / PASS
focused Control A+B session-close tests: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 545 / PASS
public session adoption: 5 / 5 PASS
last close result: last_close_result / READ-ONLY / PASS
ambiguous close_result property introduced: False / PASS
active realtime terminal: TurnOutcome.CLOSED / EXISTING REGISTRY / PASS
generation retirement owner: RealtimeGenerationGate / REUSED / PASS
SESSION_CLOSED event: EXACTLY 1 / FINAL DELIVERY BEFORE HUB CLOSE / PASS
stage cleanup: PARALLEL / ONE FINITE COMMON DEADLINE / PASS
stage timeout isolation: DAEMON / LATE SESSION MUTATION FALSE / PASS
Framework persistent cleanup thread added: False / PASS
execution bridge completed only after confirmed stop: True / PASS
persistent provider cleanup: TRUTHFUL / TYPED / PASS
voice-output persistent provider target: not_required / PASS
callback/subscription release: AFTER FINAL DELIVERY / PASS
cleanup failure reopens session: False / PASS
duplicate close outcome: already_closed / PASS
duplicate close re-runs cleanup: False / PASS
duplicate close emits another close event: False / PASS
post-close typed compatibility: RETAINED / PASS
cleanup diagnostics: COUNT_ONLY / PUBLIC_SAFE / PASS
raw exception/private value retained: False / PASS
root import loads framework.session_close eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
existing tests changed by Control B: False
docs/v600_tasklist.md changed by Control B implementation: False
FW-RT6-10b aggregate: NOT_COMPLETED
FW-RT6-10b tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B adopts the accepted `framework.session_close` vocabulary through the
existing public-session lifecycle owners. `RealtimeSession`,
`TextChatSession`, `VoiceInputSession`, `VoiceOutputSession`, and
`MotionSession` retain compatible `close()`, `dispose()`, and context-manager
signatures while exposing the immutable read-only `last_close_result`.

An active realtime turn reaches `TurnOutcome.CLOSED` through the existing
terminal registry and its current generation is retired by the existing
generation owner. The single final `SESSION_CLOSED` event retains active
turn/generation context and is delivered before the callback hub is sealed.

Injected stages close concurrently under one finite common deadline. An
external synchronous stage that exceeds the deadline is isolated by a daemon
worker and reported `timed_out`; a late return cannot mutate the published
session result, event hub, or callback collections. Bridge cleanup reports
`completed` only after the worker is confirmed stopped. Cleanup failure or
timeout never reopens the session.

Persistent provider cleanup is reported only where a session owns a persistent
provider composition. Voice output therefore reports its provider target as
`not_required`, while motion maps its persistent VTube Studio composition and
bridge outcomes without executing a real provider or network operation.

Repeated close remains idempotent, records `already_closed`, and repeats no
cleanup or final event. Existing post-close typed compatibility behavior,
root-public exports, factory signatures, event vocabulary, and API versions
remain unchanged. Diagnostics retain no raw exception, credential, provider
payload, transcript, audio, private path, callback, thread, or client identity.

This one-file acceptance sync changes no runtime source or existing test and
closes none of the seven FW-RT6-10b aggregate tasks. After this sync is
reviewed, committed, pushed, and remotely verified, only Control C exact
contract review becomes authorized. Control C implementation remains separately
gated.
<!-- FW-RT6-10b-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-10b Control C — close/dispose aggregate acceptance

```text
checkpoint: FW-RT6-10b Control C aggregate acceptance candidate
baseline head: b7ae54f7a948704456ddd446f9ddc631b0d3d4ad
FW-RT6-10a final acceptance: ffb67d8cf089cf0b9e0d0c517614517186201a17
Control A implementation: d0e977193faafbcc60e17436f4c2b5bb5547683a
Control A acceptance sync: 6153661b3960fbfa1130b2caef39e48717ad8e80
Control B implementation: 98c6455640be1eed737478c195616b2ff12840bb
Control B acceptance sync: b7ae54f7a948704456ddd446f9ddc631b0d3d4ad
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact surface: 3 files
dedicated Control C aggregate gate: PASS
focused Control A session-close tests: 12 / PASS
focused Control B session-close tests: 13 / PASS
focused Control A+B session-close tests: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 545 / PASS
stable explicit package: framework.session_close / PASS
public close owner: PUBLIC SESSION / REUSED / PASS
public session adoption: 5 / 5 PASS
last close result: last_close_result / READ-ONLY / PASS
ambiguous close_result property introduced: False / PASS
active realtime terminal: TurnOutcome.CLOSED / EXISTING REGISTRY / PASS
active turn orphan after close: False / PASS
generation retirement owner: RealtimeGenerationGate / REUSED / PASS
SESSION_CLOSED event: EXACTLY 1 / FINAL DELIVERY BEFORE HUB CLOSE / PASS
stage cleanup: PARALLEL / ONE FINITE COMMON DEADLINE / PASS
stage timeout isolation: DAEMON / LATE SESSION MUTATION FALSE / PASS
Framework persistent non-daemon cleanup thread added: False / PASS
execution bridge completed only after confirmed stop: True / PASS
persistent provider cleanup: TRUTHFUL / TYPED / PASS
voice-output persistent provider target: not_required / PASS
callback/subscription release: AFTER FINAL DELIVERY / PASS
cleanup failure reopens session: False / PASS
duplicate close outcome: already_closed / PASS
duplicate close re-runs cleanup: False / PASS
duplicate close emits another close event: False / PASS
post-close typed rejection: RETAINED / PASS
cleanup diagnostics: COUNT_ONLY / PUBLIC_SAFE / PASS
raw exception/private value retained: False / PASS
root import loads framework.session_close eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C: False
existing tests changed by Control C: False
FW-RT6-10b tasks: 7 / 7 ACCEPTED-CANDIDATE
FW-RT6-10b final acceptance sync: NOT_AUTHORIZED
FW-RT6-10c implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted close planning and public-session runtime
adoption contracts without changing runtime source. `framework.session_close`
remains the stable explicit package, while each existing public session remains
its sole close execution owner and exposes only the read-only
`last_close_result` observation.

An active realtime turn reaches `TurnOutcome.CLOSED` through the existing
terminal registry and its generation is retired by the existing generation
owner. The one correlated `SESSION_CLOSED` event is delivered before the event
hub and callback collections are sealed, so no active turn is orphaned and no
post-close payload can cross the existing host-visible boundary.

Injected stages close concurrently under one finite common deadline. A slow
external synchronous cleanup is isolated in a daemon worker and is reported
`timed_out`; its late return cannot mutate the immutable published result,
event hub, or callbacks. The execution bridge reports `completed` only after
its worker is confirmed stopped, and Framework adds no persistent non-daemon
cleanup worker.

Provider/client and bridge results remain truthful typed observations.
Voice output owns no persistent provider target, while motion maps the
persistent VTube Studio composition and bridge state without performing a real
provider or network operation. Failure or timeout never reopens the session.

Repeated close remains side-effect-free, records `already_closed`, repeats no
cleanup, and emits no second final event. Existing operation-specific
post-close typed rejection, root-public exports, factory signatures, event
vocabulary, and API versions remain unchanged. Diagnostics retain no raw
exception, credential, provider payload, transcript, audio, private path,
callback, thread, or client identity.

Control C changes no runtime source or existing test. It adds the aggregate
regression gate and marks all seven FW-RT6-10b tasks as acceptance candidates.
Final closed status remains deferred to a reviewed, committed, pushed, and
remotely verified one-file final acceptance sync. FW-RT6-10c implementation
remains not authorized.
<!-- FW-RT6-10b-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-10b-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10b — close/dispose lifecycle final acceptance sync

```text
checkpoint: FW-RT6-10b final acceptance sync
baseline head: d226102aab07a70de1b71dab4070a63c375d2bfc
FW-RT6-10a final acceptance: ffb67d8cf089cf0b9e0d0c517614517186201a17
Control A implementation: d0e977193faafbcc60e17436f4c2b5bb5547683a
Control A acceptance sync: 6153661b3960fbfa1130b2caef39e48717ad8e80
Control B implementation: 98c6455640be1eed737478c195616b2ff12840bb
Control B acceptance sync: b7ae54f7a948704456ddd446f9ddc631b0d3d4ad
Control C aggregate acceptance: d226102aab07a70de1b71dab4070a63c375d2bfc
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
exact Control B implementation surface: 11 files
exact Control C aggregate surface: 3 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A session-close tests: 12 / PASS
focused Control B session-close tests: 13 / PASS
focused Control A+B session-close tests: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 545 / PASS
stable explicit package: framework.session_close / PASS
public close owner: PUBLIC SESSION / REUSED / PASS
public session adoption: 5 / 5 PASS
last close result: last_close_result / READ-ONLY / PASS
ambiguous close_result property introduced: False / PASS
active realtime terminal: TurnOutcome.CLOSED / EXISTING REGISTRY / PASS
active turn orphan after close: False / PASS
generation retirement owner: RealtimeGenerationGate / REUSED / PASS
SESSION_CLOSED event: EXACTLY 1 / FINAL DELIVERY BEFORE HUB CLOSE / PASS
stage cleanup: PARALLEL / ONE FINITE COMMON DEADLINE / PASS
stage timeout isolation: DAEMON / LATE SESSION MUTATION FALSE / PASS
Framework persistent non-daemon cleanup thread added: False / PASS
execution bridge completed only after confirmed stop: True / PASS
persistent provider cleanup: TRUTHFUL / TYPED / PASS
voice-output persistent provider target: not_required / PASS
callback/subscription release: AFTER FINAL DELIVERY / PASS
cleanup failure reopens session: False / PASS
duplicate close outcome: already_closed / PASS
duplicate close re-runs cleanup: False / PASS
duplicate close emits another close event: False / PASS
post-close typed rejection: RETAINED / PASS
cleanup diagnostics: COUNT_ONLY / PUBLIC_SAFE / PASS
raw exception/private value retained: False / PASS
root import loads framework.session_close eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
aggregate gate changed by final sync: False
existing tests changed by Control C/final sync: False
FW-RT6-10b tasks: 7 / 7 ACCEPTED
FW-RT6-10b aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-10c exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-10c implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-10b closes the provider-neutral public-session close/dispose lifecycle.
`framework.session_close` remains the stable explicit planning and result
package, while each existing public session remains its sole close execution
owner and exposes the immutable read-only `last_close_result`.

An active realtime turn reaches `TurnOutcome.CLOSED` through the existing
terminal registry, and `RealtimeGenerationGate` remains the sole generation
retirement owner. Exactly one correlated `SESSION_CLOSED` event is delivered
before callback collections and the event hub are sealed. No active turn is
orphaned and no late result crosses its existing host-visible boundary.

Injected stages close concurrently under one finite common deadline. Slow
external synchronous cleanup is daemon-isolated and reported `timed_out`; its
late return cannot alter the immutable result, callbacks, or event hub. The
execution bridge reports completion only after confirmed stop, and Framework
adds no persistent non-daemon cleanup worker.

Provider/client and bridge observations remain truthful and typed. Voice
output has no persistent provider target, while motion maps its persistent
VTube Studio composition and bridge result without performing a real provider
or network operation. Cleanup failure or timeout never reopens the session.

Repeated close remains `already_closed`, repeats no cleanup, and emits no
second final event. Existing operation-specific post-close typed rejection,
root-public exports, factory signatures, event vocabulary, and API versions
remain unchanged. Public diagnostics retain no raw exception, credential,
provider payload, transcript, audio, private path, callback, thread, or client
identity.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade contract, aggregate gate, or existing test. It formally
completes, verifies, accepts, commits, pushes, and closes all three controls and
all seven FW-RT6-10b aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-10c exact contract review is authorized. This sync does not authorize
FW-RT6-10c implementation.
<!-- FW-RT6-10b-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10c-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10c Control A — immutable public diagnostics acceptance sync

```text
checkpoint: FW-RT6-10c Control A
baseline head: 53023cca67f0865f6454a311517889fdf26f91ab
FW-RT6-10b final acceptance: 3fe21fd1aec9f38019e1bfadb946f3246edc7799
Control A implementation: 53023cca67f0865f6454a311517889fdf26f91ab
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
exact Control A implementation surface: 5 files
dedicated Control A source gate: PASS
focused Control A diagnostics tests: 12 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 557 / PASS
stable explicit package: framework.session_diagnostics / PASS
explicit package exports: 4 / PASS
terminal model: SessionTerminalSnapshot / FROZEN / SLOTTED / PASS
session model: SessionDiagnosticsSnapshot / FROZEN / SLOTTED / PASS
terminal projection retains source result: False / PASS
session snapshot fields: 13 / TYPED / PASS
active turn/generation pairing: ENFORCED / PASS
closed active context: REJECTED / PASS
active generation count: 0_OR_1 / PASS
count booleans accepted: False / PASS
negative counts accepted: False / PASS
last safe error code: DERIVED / PASS
no terminal safe error code: none / PASS
as_dict output: PUBLIC_PRIMITIVES_ONLY / PASS
private text/audio/provider payload/path retained: False / PASS
runtime diagnostics_snapshot property: DEFERRED_TO_CONTROL_B
existing lifecycle/counter owners changed: False / PASS
root import loads framework.session_diagnostics eagerly: False / PASS
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-10c aggregate: NOT_COMPLETED
FW-RT6-10c tasklist: 0 / 9 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
Control C: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts `framework.session_diagnostics` as the stable explicit
provider-neutral model and privacy-projection package for public diagnostics.
It introduces no root export, runtime execution owner, provider dependency, or
session mutation path.

`SessionTerminalSnapshot` projects only public correlation IDs, terminal
outcome, public error code, retryability, and recovery action. It never retains
the source `RealtimeTurnResult`, so input/output text, transcripts, audio,
artifacts, metadata, safe messages, raw exceptions, credentials, provider
payloads, private paths, callbacks, threads, clients, and private identities
cannot enter the terminal or session snapshot.

`SessionDiagnosticsSnapshot` is frozen and slotted. It validates paired active
turn/generation IDs, prohibits active context after close, restricts active
generation count to zero or one, rejects boolean and negative counts, and
derives the last safe error code from the redacted terminal projection.
`as_dict()` exposes only JSON-friendly public primitives.

Control A does not add `RealtimeSession.diagnostics_snapshot` and changes no
existing registry or counter owner. Coherent runtime capture under the existing
serialized session boundary remains deferred to Control B. None of the nine
FW-RT6-10c aggregate task checkboxes close in this acceptance sync.

This exact one-file sync authorizes only Control B exact contract review after
it is reviewed, committed, pushed, and remotely verified. It does not authorize
Control B implementation, Control C, or either later commit/push.
<!-- FW-RT6-10c-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10c-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10c Control B — coherent runtime diagnostics acceptance sync

```text
checkpoint: FW-RT6-10c Control B
baseline head: ba1c193f1d90e632d727b4f2697302f5f99d167d
FW-RT6-10b final acceptance: 3fe21fd1aec9f38019e1bfadb946f3246edc7799
Control A implementation: 53023cca67f0865f6454a311517889fdf26f91ab
Control A acceptance sync: 3566ed618161b1212fb1a193cb4e27f663303863
Control B implementation: ba1c193f1d90e632d727b4f2697302f5f99d167d
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact corrective Control B implementation surface: 7 files
dedicated Control B source gate: PASS
focused Control A diagnostics tests: 12 / PASS
focused Control B diagnostics tests: 13 / PASS
focused Control A+B diagnostics tests: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 570 / PASS
stable explicit package: framework.session_diagnostics / PASS
public runtime observation: RealtimeSession.diagnostics_snapshot / READ_ONLY
snapshot mutability: FROZEN / FRESH_PER_READ
idle/active/terminal/closed reads: PASS
active identity owner: RealtimeGenerationGate / REUSED
terminal owner: RealtimeTerminalRegistry / REUSED
queue depth owner: TTSQueueState.queued_count / REUSED
stale count owner: RealtimeGenerationGate / REUSED
duplicate count owner: RealtimeTerminalRegistry / REUSED
overflow count owner: RealtimeEventHub / REUSED
capture locks: EXISTING OPERATION + TURN ADMISSION / REUSED
lock-order wait while holding operation lock: False / PASS
reentrant callback diagnostics read: PASS
new diagnostics lock/thread/registry/execution owner: False / PASS
legacy host session/turn IDs: PRESERVED / PASS
Framework-owned session/turn IDs: NORMALIZED / PASS
GenerationId validation: STRICT / PASS
malformed reserved fw_* IDs accepted: False / PASS
private-rich runtime value retained: False / PASS
root diagnostics exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by acceptance sync: False
existing tests changed by acceptance sync: False
FW-RT6-10c aggregate: NOT_COMPLETED
FW-RT6-10c tasklist: 0 / 9 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
acceptance-sync exact surface: 1 file
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B adopts the accepted immutable diagnostics model as one coherent,
read-only `RealtimeSession.diagnostics_snapshot` observation. Each read returns
a fresh frozen public value and remains available while idle, during the active
generation, from reentrant terminal callbacks, and after session close.

The public session reuses its established owners. Active turn and generation
identity come from `RealtimeGenerationGate`; last terminal result and duplicate
count come from `RealtimeTerminalRegistry`; stale count comes from the
generation gate; overflow count comes from `RealtimeEventHub`; and queue depth
comes from the existing public queue-state count. A retired generation is not
reported as active through temporary compatibility context.

Snapshot capture reuses the existing operation and turn-admission locks. When
the turn-admission lock cannot be acquired immediately, capture releases the
operation lock, yields, and retries. This preserves reentrant and inverted-lock
progress without adding a lock, thread, timeout worker, registry, execution
owner, provider call, or network operation.

Legacy host session and turn strings remain compatible. Framework-owned IDs
normalize through the existing public identity helpers, generation identity
remains strict, and malformed reserved framework IDs remain rejected. The
snapshot and `as_dict()` retain no prompt, response, transcript, audio, queue
item identity, artifact, provider payload, metadata, safe message, credential,
exception, private path, callback, thread, client, or private object identity.

This one-file acceptance sync changes no runtime source, public contract, gate,
or existing test and closes none of the nine FW-RT6-10c aggregate tasks. After
this sync is reviewed, committed, pushed, and remotely verified, only Control C
exact contract review becomes authorized. Control C implementation remains
separately gated.
<!-- FW-RT6-10c-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-10c Control C — public diagnostics aggregate acceptance

```text
checkpoint: FW-RT6-10c Control C aggregate acceptance candidate
baseline head: 0427a5446cad52706d10396f2a91ba207eef2911
FW-RT6-10b final acceptance: 3fe21fd1aec9f38019e1bfadb946f3246edc7799
Control A implementation: 53023cca67f0865f6454a311517889fdf26f91ab
Control A acceptance sync: 3566ed618161b1212fb1a193cb4e27f663303863
Control B implementation: ba1c193f1d90e632d727b4f2697302f5f99d167d
Control B acceptance sync: 0427a5446cad52706d10396f2a91ba207eef2911
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact corrective surface: 4 files
dedicated Control C aggregate gate: PASS
focused Control A diagnostics tests: 12 / PASS
focused Control B diagnostics tests: 13 / PASS
focused Control A+B diagnostics tests: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 570 / PASS
stable explicit package: framework.session_diagnostics / PASS
explicit diagnostics exports: 4 / UNCHANGED
public property: RealtimeSession.diagnostics_snapshot / READ_ONLY / PASS
snapshot mutability: FROZEN / FRESH_PER_READ / PASS
idle/active/terminal/closed reads: PASS
current phase observation: PASS
active identity owner: RealtimeGenerationGate / REUSED / PASS
queue depth owner: TTSQueueState.queued_count / REUSED / PASS
active generation count owner: RealtimeGenerationGate / REUSED / PASS
last terminal owner: RealtimeTerminalRegistry / REUSED / PASS
last safe error derivation: TERMINAL PUBLIC ERROR / PASS
stale count owner: RealtimeGenerationGate / REUSED / PASS
duplicate count owner: RealtimeTerminalRegistry / REUSED / PASS
overflow count owner: RealtimeEventHub / REUSED / PASS
capture locks: EXISTING OPERATION + TURN ADMISSION / REUSED / PASS
lock-order wait while holding operation lock: False / PASS
reentrant callback diagnostics read: PASS
new diagnostics lock/thread/registry/execution owner: False / PASS
legacy host session/turn IDs: PRESERVED / PASS
Framework-owned IDs: NORMALIZED / PASS
GenerationId validation: STRICT / PASS
malformed reserved fw_* IDs accepted: False / PASS
private-rich runtime value retained: False / PASS
root import loads framework.session_diagnostics eagerly: False / PASS
root diagnostics exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C: False
existing Control B test semantic sync: 1 file / TASK BOUNDARY ONLY
FW-RT6-10c tasks: 9 / 9 ACCEPTED-CANDIDATE
FW-RT6-10c final acceptance sync: NOT_AUTHORIZED
FW-RT6-10d: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted immutable model and coherent runtime
observation contracts without changing runtime source. The explicit lazy
`framework.session_diagnostics` package remains the only diagnostics model and
projection vocabulary, while the existing public `RealtimeSession` remains the
sole snapshot capture owner through its read-only `diagnostics_snapshot`.

Each read returns a fresh frozen snapshot for idle, active, terminal callback,
and closed states. Active turn/generation and active count come from the
existing generation gate. Queue depth uses only the existing queued count. The
terminal registry owns the redacted last result and duplicate count, the
generation gate owns stale count, and the event hub owns overflow count.

Capture reuses the existing operation and turn-admission locks. It never waits
for turn admission while retaining the operation lock, preserving callback and
inverted-lock progress without a new lock, worker, registry, timeout service,
or execution owner.

Legacy host session and turn strings remain compatible, Framework-owned IDs
normalize through the existing public identity helpers, generation IDs remain
strict, and malformed reserved framework IDs remain rejected. The model,
projection, repr, and `as_dict()` retain no prompt, response, transcript,
audio, queue-item identity, artifact, provider payload, metadata, safe message,
credential, exception, private path, callback, thread, client, or private
object identity.

Control C changes no runtime source. It adds the aggregate regression gate,
marks all nine FW-RT6-10c tasks as acceptance candidates, and updates one
accepted Control B test only to replace the pre-Control-C `0 / 9` task boundary
with the aggregate `9 / 9 ACCEPTED-CANDIDATE` boundary. API-version, provider
isolation, and runtime assertions in that test remain unchanged. Final closed
status remains deferred to a reviewed, committed, pushed, and remotely verified
one-file final acceptance sync. FW-RT6-10d remains outside this authorization.
<!-- FW-RT6-10c-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-10c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10c — public diagnostics final acceptance sync

```text
checkpoint: FW-RT6-10c final acceptance sync
baseline head: d40b9cf6a5cd1952d1d6a4ba70b1252830e12644
FW-RT6-10b final acceptance: 3fe21fd1aec9f38019e1bfadb946f3246edc7799
Control A implementation: 53023cca67f0865f6454a311517889fdf26f91ab
Control A acceptance sync: 3566ed618161b1212fb1a193cb4e27f663303863
Control B implementation: ba1c193f1d90e632d727b4f2697302f5f99d167d
Control B acceptance sync: 0427a5446cad52706d10396f2a91ba207eef2911
Control C aggregate acceptance: d40b9cf6a5cd1952d1d6a4ba70b1252830e12644
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
exact corrective Control B implementation surface: 7 files
exact corrective Control C aggregate surface: 4 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A diagnostics tests: 12 / PASS
focused Control B diagnostics tests: 13 / PASS
focused Control A+B diagnostics tests: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 570 / PASS
stable explicit package: framework.session_diagnostics / PASS
explicit diagnostics exports: 4 / UNCHANGED
public property: RealtimeSession.diagnostics_snapshot / READ_ONLY / PASS
snapshot mutability: FROZEN / FRESH_PER_READ / PASS
idle/active/terminal/closed observations: PASS
active identity and count owner: RealtimeGenerationGate / REUSED / PASS
queue depth owner: TTSQueueState.queued_count / REUSED / PASS
last terminal and duplicate owner: RealtimeTerminalRegistry / REUSED / PASS
stale owner: RealtimeGenerationGate / REUSED / PASS
overflow owner: RealtimeEventHub / REUSED / PASS
safe error derivation: REDACTED TERMINAL PUBLIC ERROR / PASS
capture locks: EXISTING OPERATION + TURN ADMISSION / REUSED / PASS
lock-order wait while holding operation lock: False / PASS
reentrant callback diagnostics read: PASS
new diagnostics lock/thread/registry/execution owner: False / PASS
legacy host session/turn IDs: PRESERVED / PASS
Framework-owned IDs: NORMALIZED / PASS
GenerationId validation: STRICT / PASS
malformed reserved fw_* IDs accepted: False / PASS
private-rich runtime value retained: False / PASS
root import loads framework.session_diagnostics eagerly: False / PASS
root diagnostics exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
aggregate gate changed by final sync: False
existing tests changed by final sync: False
FW-RT6-10c tasks: 9 / 9 ACCEPTED
FW-RT6-10c aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-10d exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-10d implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-10c closes the provider-neutral public diagnostics contract. The
explicit lazy `framework.session_diagnostics` package remains the sole
immutable model and projection vocabulary, while the existing public
`RealtimeSession` remains the sole coherent snapshot capture owner through its
read-only `diagnostics_snapshot` property.

Each read remains a fresh frozen observation for idle, active, terminal
callback, and closed states. The existing generation gate owns active identity,
active count, and stale count; the public queue snapshot supplies only queue
depth; the terminal registry owns the redacted last result and duplicate count;
and the event hub owns overflow count. Safe error state remains derived from
the public terminal projection.

Capture retains the accepted non-deadlocking use of the existing operation and
turn-admission locks. Legacy host session and turn IDs remain compatible,
Framework-owned IDs remain normalized, generation IDs remain strict, and
malformed reserved framework IDs remain rejected. No private-rich runtime value
can enter the immutable snapshot or its JSON-friendly projection.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade contract, aggregate gate, or existing test. It formally
completes, verifies, accepts, commits, pushes, and closes all three controls and
all nine FW-RT6-10c aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-10d exact contract review is authorized. This sync does not authorize
FW-RT6-10d implementation.
<!-- FW-RT6-10c-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10d-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10d Control A — callback and plugin isolation acceptance sync

```text
checkpoint: FW-RT6-10d Control A
baseline head: a6ffae7e035d4a6761edd2a75afc1a0e77bbd4b9
FW-RT6-10c final acceptance: ac729f10f4875347f7b222ef55ac560ac9d76eb2
Control A implementation baseline: ac729f10f4875347f7b222ef55ac560ac9d76eb2
Control A implementation: a6ffae7e035d4a6761edd2a75afc1a0e77bbd4b9
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
acceptance-sync exact surface: 1 file
dedicated Control A source gate: PASS
focused Control A callback-isolation tests: 13 / PASS
full Framework unit suite: 583 / PASS
stable explicit package: framework.callback_isolation / PASS
explicit package exports: 12 / PASS
callback boundaries: public_callback / plugin_hook / motion_hook / PASS
public callback failure: ISOLATED / CONTINUE / PASS
plugin hook failure: ISOLATED / CONTINUE / PASS
sync and async hook dispatch: ORDERED / ISOLATED / PASS
motion hook resolver: invoke_motion_lifecycle_hook / REUSED / PASS
motion hook failure: SKIP_MOTION / CONVERSATION_UNCHANGED / PASS
callback registry snapshot: STABLE / PASS
callback invocation under session or registry lock: False / CONTRACT
callback reentrancy: REQUIRED / DEADLOCK_FALSE / REFERENCE_PASS
dispatch result retains callback or exception identity: False / PASS
critical stages: voice_input + text_generation / PASS
non-critical stages: voice_output + motion / PASS
critical failure action: FAIL_CURRENT_OPERATION / TYPED
non-critical failure action: CONTINUE_DEGRADED / TYPED
stage failure kills session/runtime: False / PASS
stage failure replaces existing terminal: False / PASS
runtime adoption: DEFERRED_TO_CONTROL_B
runtime source changed by acceptance sync: False
existing tests changed by acceptance sync: False
root import loads framework.callback_isolation eagerly: False / PASS
root isolation exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-10d aggregate: NOT_COMPLETED
FW-RT6-10d tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
Control C: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts `framework.callback_isolation` as the stable explicit
provider-neutral policy and reference-dispatch package for public callbacks,
legacy plugin hooks, motion-hook failure, and realtime stage criticality. It
adds no root export and does not adopt the policy into an existing runtime
owner.

Public callback and legacy plugin-hook failures remain isolated per handler.
The stable handler snapshot continues in registration order for both sync and
async dispatch. The public-safe result retains counts and policy identity only;
it retains no callback, return value, raw exception, credential, provider
payload, transcript, audio, private path, thread, client, or private identity.

The existing `invoke_motion_lifecycle_hook` remains the sole typed motion-hook
resolver. A failed hook skips motion without changing the conversation
terminal. Voice input and text generation remain critical to their current
primary operation, while voice output and motion remain non-critical side
effects. Every failure policy preserves the session and runtime and cannot
replace an already committed terminal.

Runtime adopters must snapshot callback state under the appropriate existing
registry lock, release registry, session-operation, and turn-admission locks,
and only then invoke handlers. The reference dispatchers own no lock or mutable
registry and demonstrate reentrant operation without deadlock. Exact adoption
by TextChat, VoiceInput, Motion, unified RealtimeSession, and legacy plugin-hook
owners remains deferred to Control B.

This exact one-file sync changes only `docs/v600_tasklist.md`. None of the six
FW-RT6-10d aggregate task checkboxes close here. After this sync is reviewed,
committed, pushed, and remotely verified, only Control B exact contract review
is authorized; Control B implementation, Control C, and their commit/push
remain separately gated.
<!-- FW-RT6-10d-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10d-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10d Control B — callback and plugin runtime-adoption acceptance sync

```text
checkpoint: FW-RT6-10d Control B
baseline head: b7dfeab05a1a9e87042f9a8e960d53be6da5c5b8
Control A implementation: a6ffae7e035d4a6761edd2a75afc1a0e77bbd4b9
Control A acceptance sync: 5fd2f84b74a769d9158ca7785f98e3ea88f42a5a
Control B implementation baseline: 5fd2f84b74a769d9158ca7785f98e3ea88f42a5a
Control B implementation: b7dfeab05a1a9e87042f9a8e960d53be6da5c5b8
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
exact Control B implementation surface: 9 files
acceptance-sync exact surface: 1 file
dedicated Control B source gate: PASS
focused Control A callback-isolation tests: 13 / PASS
focused Control B callback-isolation tests: 12 / PASS
focused Control A+B callback-isolation tests: 25 / PASS
accepted FW-RT6-10c diagnostics regression: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 595 / PASS
stable explicit policy package: framework.callback_isolation / REUSED / PASS
event sequencer and subscriber owner: RealtimeEventHub / REUSED / PASS
legacy plugin registry: runtime[hooks] / REUSED / PASS
public session adopters: TextChat / VoiceInput / Motion / Realtime / PASS
legacy plugin hook adopter: core.events.emit / PASS
public callback failure: ISOLATED / CONTINUE / PASS
sync and async plugin hook failure: ISOLATED / CONTINUE / PASS
callback registration snapshot: STABLE / PASS
callback invocation under registry lock: False / PASS
callback invocation under RealtimeSession operation lock: False / PASS
cross-thread operation ordering: PRESERVED / PASS
same-thread callback reentrancy deadlock: False / PASS
new callback or event registry: False / PASS
new dispatcher or background thread: False / PASS
critical stage failure: TYPED / FAIL_CURRENT_OPERATION / PASS
non-critical stage failure: TYPED / CONTINUE_DEGRADED / PASS
stage failure kills session/runtime: False / PASS
stage failure replaces an existing terminal: False / PASS
close callback failure: TYPED CLEANUP FAILURE / SESSION CLOSED / PASS
raw exception/callback/thread/client identity retained: False / PASS
runtime source changed by acceptance sync: False
existing tests changed by acceptance sync: False
root import loads framework.callback_isolation eagerly: False / PASS
root isolation exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-10d aggregate: NOT_COMPLETED
FW-RT6-10d tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts coherent runtime adoption of the stable explicit
`framework.callback_isolation` policy without creating a second callback,
event, stage, or execution owner. TextChat, VoiceInput, Motion, unified
RealtimeSession, and legacy `core.events.emit` keep their existing registries,
signatures, return values, ordering, and public lifecycle contracts.

Every public callback and sync/async plugin hook is invoked from a stable
registration snapshot. One ordinary handler exception is isolated and later
handlers continue. Text, voice-input, motion, and realtime success truth cannot
be corrupted by an observer failure. The existing RealtimeEventHub remains the
sole event sequencing and subscriber owner.

Realtime callback delivery releases the physical operation lock while
retaining logical operation ownership and cross-thread serialization. Existing
same-thread registration, unregistration, cancellation, diagnostics, and
deferred-close reentrancy retain progress without a dispatcher thread or a new
public lock owner.

Unexpected critical text-generation failure becomes the existing typed failed
result for the current operation. Voice-output and motion failure remain typed
non-critical degraded results and cannot erase or replace an established
conversation terminal. Callback failure during final close delivery remains a
typed cleanup failure while the session stays closed and releases callbacks.
No public result retains a raw exception, callback identity, credential,
provider payload, transcript, audio, private path, thread, client, or private
runtime object.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes no
runtime source, public-facade contract, dedicated gate, or existing test. None
of the six FW-RT6-10d aggregate task checkboxes close here. After this sync is
reviewed, committed, pushed, and remotely verified, only Control C exact
contract review is authorized; Control C implementation and commit/push remain
separately gated.
<!-- FW-RT6-10d-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-10d-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-10d Control C — callback and plugin isolation aggregate acceptance

```text
checkpoint: FW-RT6-10d Control C aggregate acceptance candidate
baseline head: 0b5faf96d2886d9372bab5a51ddc68b9da2515a3
FW-RT6-10c final acceptance: ac729f10f4875347f7b222ef55ac560ac9d76eb2
Control A implementation: a6ffae7e035d4a6761edd2a75afc1a0e77bbd4b9
Control A acceptance sync: 5fd2f84b74a769d9158ca7785f98e3ea88f42a5a
Control B implementation: b7dfeab05a1a9e87042f9a8e960d53be6da5c5b8
Control B acceptance sync: 0b5faf96d2886d9372bab5a51ddc68b9da2515a3
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
Control C exact corrective surface: 5 files
dedicated Control C aggregate gate: PASS
focused Control A callback-isolation tests: 13 / PASS
focused Control B callback-isolation tests: 12 / PASS
focused Control A+B callback-isolation tests: 25 / PASS
accepted FW-RT6-10c diagnostics regression: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 595 / PASS
stable explicit policy package: framework.callback_isolation / REUSED / PASS
explicit isolation exports: 12 / UNCHANGED
callback boundaries: public_callback / plugin_hook / motion_hook / PASS
public callback failure: ISOLATED / CONTINUE / PASS
plugin sync + async hook failure: ISOLATED / CONTINUE / PASS
motion hook resolver: invoke_motion_lifecycle_hook / REUSED / PASS
motion hook failure: SKIP MOTION / TERMINAL UNCHANGED / PASS
public session adopters: TextChat / VoiceInput / Motion / Realtime / PASS
legacy plugin hook adopter: core.events.emit / PASS
event sequencer and subscriber owner: RealtimeEventHub / REUSED / PASS
callback registration snapshot: STABLE / PASS
callback invocation under registry/session lock: False / PASS
same-thread callback reentrancy deadlock: False / PASS
cross-thread operation ordering: PRESERVED / PASS
new callback/event registry or dispatcher thread: False / PASS
critical stages: voice_input + text_generation / PASS
non-critical stages: voice_output + motion / PASS
critical stage failure: TYPED / FAIL CURRENT OPERATION / PASS
non-critical stage failure: TYPED / CONTINUE DEGRADED / PASS
stage failure kills session/runtime: False / PASS
stage failure replaces existing terminal: False / PASS
close callback failure: TYPED CLEANUP FAILURE / SESSION CLOSED / PASS
raw exception/callback/thread/client identity retained: False / PASS
root import loads framework.callback_isolation eagerly: False / PASS
root isolation exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C: False
existing Control A+B test semantic sync: 2 files / TASK BOUNDARY ONLY
FW-RT6-10d tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-10d final acceptance sync: NOT_AUTHORIZED
FW-RT6-11a: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted explicit provider-neutral isolation policy
and its coherent runtime adoption without changing runtime source. The stable
lazy `framework.callback_isolation` package remains the sole callback, plugin,
motion-hook, and stage-failure policy vocabulary. TextChat, VoiceInput,
Motion, unified RealtimeSession, and legacy `core.events.emit` continue to use
their existing registries, sequencing, lifecycle owners, and return contracts.

Public callbacks and synchronous or asynchronous plugin hooks use stable
registration snapshots and isolate each ordinary handler exception. Later
handlers continue in order, observer failure does not corrupt primary success,
and no callback is invoked while its registry or public session operation lock
is retained. Existing reentrant cancellation, registration, diagnostics, and
deferred-close paths retain progress without a new dispatcher thread, event
registry, or lock owner. Cross-thread operation ordering remains preserved.

The existing `invoke_motion_lifecycle_hook` remains the only motion-hook
resolver. Hook failure skips motion without changing the conversation
terminal. Voice input and text generation remain critical to the current
operation; voice output and motion remain non-critical effects. Typed failures
keep the session and runtime truthful and cannot replace an already committed
terminal. A callback failure during final close delivery remains a typed
cleanup failure while the session stays closed and callbacks are released.

No public policy, dispatch, stage, or close result retains a callback, return
value, raw exception, credential, provider payload, transcript, audio, private
path, thread, client, or private runtime identity. Root exports, factory
signatures, API versions, provider isolation, and existing post-close typed
rejection remain unchanged.

Control C adds the aggregate regression gate, marks all six FW-RT6-10d tasks
as acceptance candidates, and updates one accepted task-boundary test in each
of Control A and Control B to replace the pre-Control-C `0 / 6` task boundary
with the aggregate `6 / 6 ACCEPTED-CANDIDATE` boundary. Its runtime,
API-version, provider-isolation, and
privacy assertions remain unchanged. Final closed status requires a separately
reviewed, committed, pushed, and remotely verified one-file final acceptance
sync. FW-RT6-11a remains outside this authorization.
<!-- FW-RT6-10d-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-10d-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-10d — callback and plugin isolation final acceptance sync

```text
checkpoint: FW-RT6-10d final acceptance sync
baseline head: 19946d9487671c511b0df3d2861fca7b076c6e68
FW-RT6-10c final acceptance: ac729f10f4875347f7b222ef55ac560ac9d76eb2
Control A implementation: a6ffae7e035d4a6761edd2a75afc1a0e77bbd4b9
Control A acceptance sync: 5fd2f84b74a769d9158ca7785f98e3ea88f42a5a
Control B implementation: b7dfeab05a1a9e87042f9a8e960d53be6da5c5b8
Control B acceptance sync: 0b5faf96d2886d9372bab5a51ddc68b9da2515a3
Control C aggregate acceptance: 19946d9487671c511b0df3d2861fca7b076c6e68
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
exact Control B implementation surface: 9 files
exact corrective Control C aggregate surface: 5 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A callback-isolation tests: 13 / PASS
focused Control B callback-isolation tests: 12 / PASS
focused Control A+B callback-isolation tests: 25 / PASS
accepted FW-RT6-10c diagnostics regression: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 595 / PASS
stable explicit policy package: framework.callback_isolation / PASS
explicit isolation exports: 12 / UNCHANGED
callback boundaries: public_callback / plugin_hook / motion_hook / PASS
public callback failure: ISOLATED / CONTINUE / PASS
plugin sync + async hook failure: ISOLATED / CONTINUE / PASS
motion hook resolver: invoke_motion_lifecycle_hook / REUSED / PASS
motion hook failure: SKIP MOTION / TERMINAL UNCHANGED / PASS
public session adopters: TextChat / VoiceInput / Motion / Realtime / PASS
legacy plugin hook adopter: core.events.emit / PASS
event sequencer and subscriber owner: RealtimeEventHub / REUSED / PASS
callback registration snapshot: STABLE / PASS
callback invocation under registry/session lock: False / PASS
same-thread callback reentrancy deadlock: False / PASS
cross-thread operation ordering: PRESERVED / PASS
new callback/event registry or dispatcher thread: False / PASS
critical stages: voice_input + text_generation / PASS
non-critical stages: voice_output + motion / PASS
critical stage failure: TYPED / FAIL CURRENT OPERATION / PASS
non-critical stage failure: TYPED / CONTINUE DEGRADED / PASS
stage failure kills session/runtime: False / PASS
stage failure replaces existing terminal: False / PASS
close callback failure: TYPED CLEANUP FAILURE / SESSION CLOSED / PASS
raw exception/callback/thread/client identity retained: False / PASS
root import loads framework.callback_isolation eagerly: False / PASS
root isolation exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
aggregate gate changed by final sync: False
existing tests changed by final sync: False
FW-RT6-10d tasks: 6 / 6 ACCEPTED
FW-RT6-10d aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-11a exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-11a implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-10d closes the provider-neutral callback and plugin isolation contract.
The explicit lazy `framework.callback_isolation` package remains the sole
immutable policy vocabulary. TextChat, VoiceInput, Motion, unified
RealtimeSession, and legacy `core.events.emit` retain their existing callback
registries, event sequencing, lifecycle owners, signatures, and return values.

Public callbacks and synchronous or asynchronous plugin hooks continue from a
stable registration snapshot, isolate each ordinary handler exception, and
preserve later-handler ordering. Callback delivery remains outside registry and
session-operation locks. Same-thread reentrancy and cross-thread operation
ordering retain the accepted behavior without a new dispatcher thread, event
registry, callback service, or public lock owner.

The existing `invoke_motion_lifecycle_hook` remains the sole typed motion-hook
resolver. Voice input and text generation remain critical to their current
operation; voice output and motion remain non-critical. Typed stage and close
failures preserve session, runtime, and terminal truth and retain no callback,
return value, raw exception, credential, provider payload, transcript, audio,
private path, thread, client, or private runtime identity.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade contract, aggregate gate, or existing test. It formally
completes, verifies, accepts, commits, pushes, and closes all three controls and
all six FW-RT6-10d aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-11a exact contract review is authorized. This sync does not authorize
FW-RT6-11a implementation.
<!-- FW-RT6-10d-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11a Control A — standalone-session compatibility acceptance sync

```text
checkpoint: FW-RT6-11a Control A
baseline head: cc7ba3b2a550e465e51227462a4158ebebde67fc
FW-RT6-10d final acceptance: 182335063eabdd901095b4184f097e095eb7021d
Control A implementation baseline: 182335063eabdd901095b4184f097e095eb7021d
Control A implementation: cc7ba3b2a550e465e51227462a4158ebebde67fc
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
acceptance-sync exact surface: 1 file
dedicated Control A source gate: PASS
focused Control A compatibility tests: 14 / PASS
accepted v5 compatibility regressions: 62 / PASS
full Framework unit suite: 609 / PASS
stable explicit package: framework.session_compatibility / PASS
explicit package exports: 10 / PASS
session compatibility profiles: 5 / TYPED / PASS
standalone compatibility mode: v5_standalone / PASS
RealtimeSession default mode: v5_skeleton / PASS
RealtimeSession explicit unified request: v6_unified / PASS
silent fallback from v6_unified to v5 mock: False / CONTRACT
existing compatibility members warning: SILENT / PASS
future deprecated member warning: DeprecationWarning / stacklevel=2 / POLICY_ONLY
warning on import or construction: False / PASS
earliest removal major: 7 / PASS
migration evidence before removal: REQUIRED / PASS
historical v5 release gates rewritten: False / PASS
runtime adoption: DEFERRED_TO_CONTROL_B
runtime source changed by acceptance sync: False
existing tests changed by acceptance sync: False
root import loads framework.session_compatibility eagerly: False / PASS
root compatibility exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
TEXT_CHAT_API_VERSION: 4.0 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
VOICE_OUTPUT_BOUNDARY_VERSION: v5.lazy_provider_adapter / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-11a aggregate: NOT_COMPLETED
FW-RT6-11a tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
Control C aggregate acceptance: NOT_AUTHORIZED
FW-RT6-11b root-public cleanup: NOT_AUTHORIZED
FW-RT6-11c migration guide and examples: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the explicit-only `framework.session_compatibility` package
as the stable provider-neutral contract for the five existing public sessions.
The four standalone facades preserve their `v5_standalone` mode, public
execution owner, method and return shapes, factory signature, and frozen
contract label. The existing `RealtimeSession` remains the owner for both its
default `v5_skeleton` compatibility mode and an explicit `v6_unified` request.

Compatibility remains distinct from deprecation. Existing v4/v5 entry points,
including every `dispose()` alias, remain warning-free. A future true
deprecation requires a replacement, `DeprecationWarning`, application-call-site
`stacklevel=2`, no import-time or construction-time warning, no removal before
v7, and migration evidence before removal. Control A registers and emits no
public-member warning.

The superseded v5.1 factory, v5.1 uninitialized TextChat fixture, and v5.2
pre-real-STT assertions remain historical evidence and are not rewritten.
Current TextChat, VoiceInput, VoiceOutput, Realtime, and Motion compatibility
regressions remain executable acceptance inputs. Control A performs no
provider, network, audio, microphone, playback, or real VTube Studio work and
adds no root-public name.

This exact one-file sync changes only `docs/v600_tasklist.md`. None of the six
FW-RT6-11a aggregate task checkboxes close here. After this sync is reviewed,
committed, pushed, and remotely verified, only Control B exact contract review
is authorized; Control B implementation, Control C, FW-RT6-11b, FW-RT6-11c,
and their commit/push remain separately gated.
<!-- FW-RT6-11a-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11a Control B — public session compatibility adoption acceptance sync

```text
checkpoint: FW-RT6-11a Control B
baseline head: 675c4b895f424b75301a5eea5593a75e0349b661
Control A implementation: cc7ba3b2a550e465e51227462a4158ebebde67fc
Control A acceptance sync: 149edb89e65409ce9c6854b39449d05e9ecfeb98
Control B implementation baseline: 149edb89e65409ce9c6854b39449d05e9ecfeb98
Control B implementation: 675c4b895f424b75301a5eea5593a75e0349b661
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
exact corrective Control B implementation surface: 11 files
acceptance-sync exact surface: 1 file
dedicated Control B source gate: PASS
focused Control A compatibility tests: 14 / PASS
focused Control B compatibility tests: 16 / PASS
focused Control A+B compatibility tests: 30 / PASS
accepted v5 compatibility regressions: 62 / PASS
accepted FW-RT6-10d callback-isolation regression: 25 / PASS
accepted FW-RT6-10c diagnostics regression: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 625 / PASS
stable explicit package: framework.session_compatibility / REUSED / PASS
canonical profile builder: build_session_compatibility_profile / REUSED / PASS
public session properties: 5 / READ_ONLY / PASS
property package loading: LAZY / PROPERTY_ACCESS_ONLY / PASS
standalone session modes: 4 / v5_standalone / PASS
RealtimeSession default mode: v5_skeleton / PASS
RealtimeSession explicit-false mode: v5_skeleton / PASS
RealtimeSession explicit-true mode: v6_unified / REQUEST_TRUTH / PASS
RealtimeSession config explicit-true mode: v6_unified / REQUEST_TRUTH / PASS
stage binding alone selects unified: False / PASS
unavailable unified request falls back to mock: False / PASS
profile equality across reads: STABLE / PASS
profile object identity: NOT_CONTRACTED
profile readable after close: True / PASS
compatibility warning: SILENT / PASS
provider/runtime work during profile access: False / PASS
private/provider identity retained by profile: False / PASS
factory signatures and legacy return/event shapes: UNCHANGED
runtime source changed by acceptance sync: False
dedicated gate changed by acceptance sync: False
existing tests changed by acceptance sync: False
root import loads framework.session_compatibility eagerly: False / PASS
root compatibility exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
TEXT_CHAT_API_VERSION: 4.0 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
VOICE_OUTPUT_BOUNDARY_VERSION: v5.lazy_provider_adapter / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
FW-RT6-11a aggregate: NOT_COMPLETED
FW-RT6-11a tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
FW-RT6-11b root-public cleanup: NOT_AUTHORIZED
FW-RT6-11c migration guide and examples: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts the five read-only public-session compatibility-profile
properties as the exact runtime adoption of the stable explicit
`framework.session_compatibility` contract. The existing TextChat, VoiceInput,
VoiceOutput, Motion, and Realtime sessions remain the sole public owners. No
second session, profile registry, execution owner, warning service, or root
export is introduced.

The four standalone sessions preserve `v5_standalone` and their frozen
contract labels. Default and explicit-false `RealtimeSession` construction
preserve `v5_skeleton`. An explicit true request, whether direct or supplied by
`RealtimeSessionConfig`, reports `v6_unified` from the existing request truth.
Injected stages alone do not select unified mode, and an unavailable explicit
unified request does not manufacture a deterministic mock fallback.

The property remains lazy, read-only, immutable, warning-free, and readable
after close. Repeated reads return equal public facts without contracting
object identity. Profile access performs no provider, network, audio,
microphone, playback, VTube Studio, callback, event, or turn work and retains
no credential, provider payload, transcript, audio, private path, callback,
thread, client, or private runtime identity.

Factory and constructor signatures, legacy methods, return and event shapes,
close/dispose/context-manager behavior, root exports, and all five public
version labels remain unchanged. Historical v5 gate files remain unchanged;
the accepted Control A test and source gate contain only the reviewed Control B
boundary synchronization.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes no
runtime source, public-facade contract, dedicated gate, or existing test. None
of the six FW-RT6-11a aggregate task checkboxes close here. After this sync is
reviewed, committed, pushed, and remotely verified, only Control C exact
contract review is authorized; Control C implementation, FW-RT6-11b,
FW-RT6-11c, and their commit/push remain separately gated.
<!-- FW-RT6-11a-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-11a Control C — aggregate standalone-session compatibility acceptance

```text
checkpoint: FW-RT6-11a Control C
baseline head: f79dfa6794138654c5f89a212b32ecd7f58399af
Control A implementation: cc7ba3b2a550e465e51227462a4158ebebde67fc
Control A acceptance sync: 149edb89e65409ce9c6854b39449d05e9ecfeb98
Control B implementation: 675c4b895f424b75301a5eea5593a75e0349b661
Control B acceptance sync: f79dfa6794138654c5f89a212b32ecd7f58399af
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
exact corrective Control C surface: 4 files
runtime source changed by Control C: False
existing Control B test semantic sync: 1 file / TASK BOUNDARY ONLY
stable explicit package: framework.session_compatibility / REUSED / PASS
canonical profile builder: build_session_compatibility_profile / REUSED / PASS
public compatibility properties: 5 / READ_ONLY / LAZY / PASS
standalone modes: 4 / v5_standalone / PASS
Realtime default mode: v5_skeleton / PASS
Realtime explicit-false mode: v5_skeleton / PASS
Realtime explicit-true mode: v6_unified / REQUEST TRUTH / PASS
Realtime config explicit-true mode: v6_unified / REQUEST TRUTH / PASS
stage binding alone selects unified: False / PASS
unavailable unified request falls back to mock: False / PASS
profile equality across reads: STABLE / PASS
profile object identity: NOT_CONTRACTED
profile readable after close: True / PASS
compatibility warning: SILENT / PASS
deprecated warning category: DeprecationWarning / POLICY_ONLY / PASS
warning stacklevel: 2 / PASS
import or construction warning: False / PASS
earliest removal major: 7 / PASS
migration evidence before removal: REQUIRED / PASS
deprecated public fields or methods introduced: 0
accepted TextChat/VoiceInput regressions: PASS
current VoiceOutput/Realtime/Motion release gates: PASS
historical superseded gate files changed: False
provider/network/audio/microphone/playback/real VTS execution: False / PASS
private/provider identity retained by profile: False / PASS
root import loads framework.session_compatibility eagerly: False / PASS
root compatibility exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
TEXT_CHAT_API_VERSION: 4.0 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
VOICE_OUTPUT_BOUNDARY_VERSION: v5.lazy_provider_adapter / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
FW-RT6-11a tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-11a aggregate: IMPLEMENTED / AWAITING_REVIEW
FW-RT6-11a final acceptance sync: NOT_AUTHORIZED
FW-RT6-11b root-public cleanup: NOT_AUTHORIZED
FW-RT6-11c migration guide and examples: NOT_AUTHORIZED
Control C commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted Control A compatibility vocabulary and
Control B public-session adoption. The lazy explicit-only
`framework.session_compatibility` package remains the sole compatibility and
future-deprecation policy owner; the five existing public sessions remain the
sole execution and lifecycle owners.

The four standalone profiles remain `v5_standalone`. Default and explicit-false
Realtime profiles remain `v5_skeleton`; explicit-true requests remain
`v6_unified` request truth without provider-availability claims or mock
fallback. Profiles remain read-only, lazy, immutable, warning-free,
provider-neutral, private-data-free, stable across equal reads, and readable
after close.

Existing compatibility members remain silent. The explicit
`DeprecatedMemberPolicy` remains future-facing policy only and introduces no
deprecated public member. Current v5 regressions and release-contract smokes
remain executable; historical superseded assertions retain their recorded
migration evidence and are not rewritten.

This exact four-file aggregate changes no runtime source. Besides this tasklist,
the public contract, and the new dedicated gate, it updates only the accepted
Control B task-boundary test from the pre-Control-C `0 / 6` state to
`6 / 6 ACCEPTED-CANDIDATE`. Control A tests, Control A/B source gates,
application-integration docs, historical v5 gates, examples, README, root
exports, signatures, return/event shapes, and version labels remain unchanged.

All six FW-RT6-11a tasks are acceptance candidates. Final closed status
requires a separately reviewed, committed, pushed, and remotely verified
one-file final acceptance sync. FW-RT6-11b and FW-RT6-11c remain separately
gated.
<!-- FW-RT6-11a-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-11a-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11a — standalone-session compatibility final acceptance sync

```text
checkpoint: FW-RT6-11a final acceptance sync
baseline head: 0eb039718aa8f3b22f9e4ad1956b697d325a685b
FW-RT6-10d final acceptance: 182335063eabdd901095b4184f097e095eb7021d
Control A implementation: cc7ba3b2a550e465e51227462a4158ebebde67fc
Control A acceptance sync: 149edb89e65409ce9c6854b39449d05e9ecfeb98
Control B implementation: 675c4b895f424b75301a5eea5593a75e0349b661
Control B acceptance sync: f79dfa6794138654c5f89a212b32ecd7f58399af
Control C aggregate acceptance: 0eb039718aa8f3b22f9e4ad1956b697d325a685b
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 5 files
exact corrective Control B implementation surface: 11 files
exact corrective Control C aggregate surface: 4 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A compatibility tests: 14 / PASS
focused Control B compatibility tests: 16 / PASS
focused Control A+B compatibility tests: 30 / PASS
accepted v5 compatibility regressions: 62 / PASS
accepted FW-RT6-10d callback-isolation regression: 25 / PASS
accepted FW-RT6-10c diagnostics regression: 25 / PASS
accepted FW-RT6-10b close/dispose regression: 25 / PASS
accepted FW-RT6-10a recovery/reset regression: 27 / PASS
accepted FW-RT6-9d stale-delivery regression: 27 / PASS
v5.2.0 realtime public contract conformance gate: PASS
full Framework unit suite: 625 / PASS
stable explicit package: framework.session_compatibility / REUSED / PASS
explicit compatibility exports: 10 / UNCHANGED
canonical profile builder: build_session_compatibility_profile / REUSED / PASS
public compatibility properties: 5 / READ_ONLY / LAZY / PASS
standalone modes: 4 / v5_standalone / PASS
Realtime default mode: v5_skeleton / PASS
Realtime explicit-false mode: v5_skeleton / PASS
Realtime explicit-true mode: v6_unified / REQUEST TRUTH / PASS
Realtime config explicit-true mode: v6_unified / REQUEST TRUTH / PASS
stage binding alone selects unified: False / PASS
unavailable unified request falls back to mock: False / PASS
profile equality across reads: STABLE / PASS
profile object identity: NOT_CONTRACTED
profile readable after close: True / PASS
compatibility warning: SILENT / PASS
deprecated warning category: DeprecationWarning / POLICY_ONLY / PASS
warning stacklevel: 2 / PASS
import or construction warning: False / PASS
earliest removal major: 7 / PASS
migration evidence before removal: REQUIRED / PASS
deprecated public fields or methods introduced: 0
accepted TextChat/VoiceInput regressions: PASS
current VoiceOutput/Realtime/Motion release gates: PASS
historical superseded gate files changed: False
provider/network/audio/microphone/playback/real VTS execution: False / PASS
private/provider identity retained by profile: False / PASS
root import loads framework.session_compatibility eagerly: False / PASS
root compatibility exports: 0 / UNCHANGED
framework root-public names: 127 / UNCHANGED
TEXT_CHAT_API_VERSION: 4.0 / UNCHANGED
VOICE_INPUT_API_VERSION: 5.2.0 / UNCHANGED
VOICE_OUTPUT_BOUNDARY_VERSION: v5.lazy_provider_adapter / UNCHANGED
REALTIME_API_VERSION: 5.2.0 / UNCHANGED
MOTION_API_VERSION: 5.5.0 / UNCHANGED
runtime source changed by Control C/final sync: False
public-facade contract changed by final sync: False
aggregate gate changed by final sync: False
existing tests changed by final sync: False
FW-RT6-11a tasks: 6 / 6 ACCEPTED
FW-RT6-11a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-11b exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-11b implementation: NOT_AUTHORIZED
FW-RT6-11c implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-11a closes the v5 standalone-session compatibility contract. The lazy
explicit-only `framework.session_compatibility` package remains the sole
immutable compatibility-profile, member-status, warning-policy, and future
deprecation vocabulary. TextChat, VoiceInput, VoiceOutput, Motion, and Realtime
retain their existing public session, execution, lifecycle, event, and close
owners; no second session or compatibility registry is introduced.

The four standalone sessions preserve `v5_standalone` and their frozen contract
labels. Default and explicit-false Realtime construction preserve
`v5_skeleton`; explicit-true construction preserves `v6_unified` request truth
without provider-availability claims or silent deterministic-mock fallback.
All five public compatibility properties remain read-only, lazy, immutable,
warning-free, provider-neutral, private-data-free, stable across equal reads,
and readable after close.

Compatibility remains distinct from deprecation. Accepted v4/v5 members stay
silent. The explicit future policy requires a replacement,
`DeprecationWarning`, application-call-site `stacklevel=2`, no import or
construction warning, no removal before v7, and migration evidence before
removal. No public field or method is deprecated by FW-RT6-11a. Current v5
regressions and release-contract smokes remain executable; historical
superseded assertions remain unchanged with their recorded migration evidence.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade or application-integration contract, aggregate gate,
existing test, historical release gate, README, example, root export, factory
signature, return/event shape, or API version. It formally completes, verifies,
accepts, commits, pushes, and closes all three controls and all six FW-RT6-11a
aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-11b exact contract review is authorized. This sync does not authorize
FW-RT6-11b implementation or any FW-RT6-11c work.
<!-- FW-RT6-11a-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11b-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11b Control A — frozen root-public inventory acceptance sync

```text
checkpoint: FW-RT6-11b Control A
baseline head: ffaaa167aae595d315995ce307f44b24ac1ef37c
FW-RT6-11a final acceptance: 06e98b0024c2bafc1581d5e3349eae01c1929a8f
Control A implementation baseline: 06e98b0024c2bafc1581d5e3349eae01c1929a8f
Control A implementation: ffaaa167aae595d315995ce307f44b24ac1ef37c
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 6 files
acceptance-sync exact surface: 1 file
dedicated Control A root-public gate: PASS
focused Control A root-public tests: 12 / PASS
canonical root-public manifest gate: PASS
focused FW-RT6-11a compatibility tests: 30 / PASS
accepted v5 compatibility regressions: 62 / PASS
v5.3 lazy provider adapter gate: PASS
v5.4 client-injection / fake / real-runtime gates: PASS
full Framework unit suite: 637 / PASS
canonical runtime source: framework.public_api.PUBLIC_API_NAMES / REUSED / PASS
machine-readable projection: docs/v600_root_public_api_manifest.json / PASS
manifest schema: v6.root_public_api_manifest / PASS
framework root-public names: 127 / UNCHANGED / PASS
provider-neutral root exports: 112 / PASS
v5 provider compatibility root exports: 15 / PRESERVED / LAZY / PASS
root-public unordered SHA-256: 4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0
wildcard runtime order: PRESERVED / NON-CONTRACTUAL / PASS
stable optional provider namespace: NONE / DELIBERATE / PASS
new provider-specific root exports: 0 / PASS
provider compatibility deprecations: 0 / PASS
docs/example/export drift: PASS
factory signatures and return/event shapes: UNCHANGED
API and schema version labels: UNCHANGED
provider/network/audio/microphone/playback/real VTS execution: False / PASS
runtime source changed by acceptance sync: False
public-facade contract changed by acceptance sync: False
application-integration contract changed by acceptance sync: False
machine-readable manifest changed by acceptance sync: False
dedicated gate changed by acceptance sync: False
existing tests changed by acceptance sync: False
FW-RT6-11b aggregate: NOT_COMPLETED
FW-RT6-11b tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control B implementation: NOT_AUTHORIZED
aggregate acceptance: NOT_AUTHORIZED
FW-RT6-11c migration guide and examples: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the frozen v6 root-public inventory as an unordered 127-name
contract. `framework.public_api.PUBLIC_API_NAMES` remains the canonical runtime
source, and `docs/v600_root_public_api_manifest.json` remains its deterministic
machine-readable projection. The inventory contains 112 provider-neutral names
and 15 lazy v5 OpenAI voice-input compatibility names.

Wildcard runtime order is preserved only for compatibility and is not a v6
contract. No stable optional-provider namespace is introduced, no new
provider-specific root export is allowed, and no retained compatibility export
is deprecated or removed. Public examples and contract documentation remain
aligned with the sorted manifest name set.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes no
runtime source, public-facade or application-integration contract,
machine-readable manifest, dedicated gate, existing test, example, factory
signature, return/event shape, or API version. None of the six FW-RT6-11b
aggregate task checkboxes close here.

After this sync is reviewed, committed, pushed, and remotely verified, only
Control B exact contract review is authorized. Control B implementation,
aggregate acceptance, FW-RT6-11c, and their commit/push remain separately
gated.
<!-- FW-RT6-11b-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11b-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11b Control B — optional-provider namespace acceptance sync

```text
checkpoint: FW-RT6-11b Control B
baseline head: 6cdb08ac35f2c7f4baa0b8b2a61d8e78a33b0c02
Control A implementation: ffaaa167aae595d315995ce307f44b24ac1ef37c
Control A acceptance sync: 644350479aa3dde264627978d555ef47a432cd3f
Control B implementation baseline: 644350479aa3dde264627978d555ef47a432cd3f
Control B implementation: 6cdb08ac35f2c7f4baa0b8b2a61d8e78a33b0c02
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control B implementation surface: 11 files
acceptance-sync exact surface: 1 file
dedicated Control B namespace gate: PASS
focused Control B namespace tests: 12 / PASS
dedicated Control A root-public gate: PASS
focused Control A root-public tests: 12 / PASS
focused Control A+B root-public tests: 24 / PASS
canonical root-public manifest gate: PASS
focused FW-RT6-11a compatibility tests: 30 / PASS
accepted v5 compatibility regressions: 62 / PASS
v5.3 lazy provider adapter gate: PASS
v5.4 client-injection / fake / real-runtime gates: PASS
full Framework unit suite: 649 / PASS
offline wheel provider-namespace membership: PASS
stable optional provider namespace: framework.providers.openai.voice_input / PASS
namespace exact exports: 15 / PASS
namespace container exports: 0 / EXPLICIT MODULE ONLY / PASS
root and namespace object identity: SAME / PASS
framework root-public names: 127 / UNCHANGED / PASS
provider-neutral root exports: 112 / UNCHANGED / PASS
v5 provider compatibility root exports: 15 / PRESERVED / LAZY / SILENT / PASS
root-public unordered SHA-256: 4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0
wildcard runtime order: PRESERVED / NON-CONTRACTUAL / PASS
new provider-specific root exports: 0 / PASS
provider compatibility deprecations: 0 / PASS
namespace import loads OpenAI SDK: False / PASS
provider/network/audio/microphone/playback/real VTS execution: False / PASS
factory signatures and return/event shapes: UNCHANGED
API and schema version labels: UNCHANGED
runtime source changed by acceptance sync: False
public-facade contract changed by acceptance sync: False
application-integration contract changed by acceptance sync: False
machine-readable manifest changed by acceptance sync: False
Control A/B gates changed by acceptance sync: False
existing tests changed by acceptance sync: False
FW-RT6-11b aggregate: NOT_COMPLETED
FW-RT6-11b tasklist: 0 / 6 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
Control C implementation: NOT_AUTHORIZED
aggregate acceptance: NOT_AUTHORIZED
FW-RT6-11c migration guide and examples: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts `framework.providers.openai.voice_input` as the stable
explicit optional-provider namespace for the 15 frozen v5.4 OpenAI voice-input
contracts. The intermediate `framework.providers` and
`framework.providers.openai` packages remain empty containers. Each namespace
export is the same object as its retained lazy root compatibility export.

The unordered 127-name root contract and its digest remain unchanged. All 15
root compatibility exports remain lazy, warning-free, and supported throughout
v6; no new provider-specific root export or deprecation is introduced. Normal
host integration continues to use provider-neutral session, request, result,
capability, configuration, and adapter boundaries.

Importing the explicit namespace loads no OpenAI SDK and performs no provider,
network, audio, microphone, playback, or real VTube Studio work. The stable
namespace is present in the offline wheel and retains all existing explicit
runtime-policy gates before provider work can occur.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes no
runtime source, public-facade or application-integration contract,
machine-readable manifest, dedicated gate, existing test, README, example,
factory signature, return/event shape, or API version. None of the six
FW-RT6-11b aggregate task checkboxes close here.

After this sync is reviewed, committed, pushed, and remotely verified, only
Control C aggregate exact contract review is authorized. Control C
implementation, aggregate acceptance, FW-RT6-11c, and their commit/push remain
separately gated.
<!-- FW-RT6-11b-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11b-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-11b Control C — aggregate root-public cleanup acceptance

```text
checkpoint: FW-RT6-11b Control C
baseline head: 727d999fd012731088fd3261c6e5b0e4bb161e94
Control A implementation: ffaaa167aae595d315995ce307f44b24ac1ef37c
Control A acceptance sync: 644350479aa3dde264627978d555ef47a432cd3f
Control B implementation: 6cdb08ac35f2c7f4baa0b8b2a61d8e78a33b0c02
Control B acceptance sync: 727d999fd012731088fd3261c6e5b0e4bb161e94
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
exact corrective Control C surface: 7 files
runtime source changed by Control C: False
machine-readable manifest changed by Control C: False
application-integration contract changed by Control C: False
Control A/B gate/test semantic sync: 4 files / CONTROL_C BOUNDARY ONLY
canonical runtime source: framework.public_api.PUBLIC_API_NAMES / REUSED / PASS
machine-readable projection: docs/v600_root_public_api_manifest.json / REUSED / PASS
manifest schema: v6.root_public_api_manifest / PASS
framework root-public names: 127 / UNCHANGED / PASS
provider-neutral root exports: 112 / UNCHANGED / PASS
v5 provider compatibility root exports: 15 / PRESERVED / LAZY / SILENT / PASS
root-public unordered SHA-256: 4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0
provider-neutral SHA-256: c75717d89860716610c539d0ba6411259b3b9dd77349fd7b8c17bcdf2bdb2c3e
provider-compatibility SHA-256: 4f8dd7bc622270fd5f4cbdae80d656cf21c6aed2604b5e73f465f51e457fa996
wildcard runtime order: PRESERVED / NON-CONTRACTUAL / PASS
stable optional provider namespace: framework.providers.openai.voice_input / PASS
namespace exact exports: 15 / PASS
namespace container exports: 0 / EXPLICIT MODULE ONLY / PASS
root and namespace object identity: SAME / PASS
new provider-specific root exports: 0 / PASS
provider compatibility deprecations: 0 / PASS
docs/example/export drift: PASS
offline wheel provider-namespace membership: PASS
namespace import loads OpenAI SDK: False / PASS
provider/network/audio/microphone/playback/real VTS execution: False / PASS
factory signatures and return/event shapes: UNCHANGED
API and schema version labels: UNCHANGED
focused Control A root-public tests: 12 / PASS
focused Control B namespace tests: 12 / PASS
focused Control A+B root-public tests: 24 / PASS
canonical root-public manifest gate: PASS
focused FW-RT6-11a compatibility tests: 30 / PASS
accepted v5 compatibility regressions: 62 / PASS
v5.3 lazy provider adapter gate: PASS
v5.4 client-injection / fake / real-runtime gates: PASS
full Framework unit suite: 649 / PASS
FW-RT6-11b tasks: 6 / 6 ACCEPTED-CANDIDATE
FW-RT6-11b aggregate: IMPLEMENTED / AWAITING_REVIEW
FW-RT6-11b final acceptance sync: NOT_AUTHORIZED
FW-RT6-11c migration guide and examples: NOT_AUTHORIZED
Control C commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted frozen root-public inventory and stable
optional-provider namespace. `framework.public_api.PUBLIC_API_NAMES` remains
the single runtime source, and `docs/v600_root_public_api_manifest.json`
remains its deterministic sorted projection. The root stays an unordered
127-name v6 contract partitioned into 112 provider-neutral names and 15 lazy,
silent v5 OpenAI voice-input compatibility names.

The stable explicit `framework.providers.openai.voice_input` module retains the
same exact 15 objects as the root compatibility surface. The intermediate
containers remain empty. Root import and explicit namespace import remain free
of provider SDK, client, credential, network, audio, microphone, playback, and
real VTube Studio execution. No new provider-specific root export or
deprecation is introduced.

This exact seven-file aggregate changes no runtime source, machine-readable
manifest, provider namespace implementation, application-integration contract,
historical v5 gate, README, example, factory signature, return/event shape, or
API version. Besides this tasklist, the public contract, and the new dedicated
aggregate gate, it synchronizes only the pre-Control-C `0 / 6` task boundary
and status output in the accepted Control A/B source gates and unit tests.

All six FW-RT6-11b tasks are acceptance candidates, not final closed status.
Final completion requires a separately reviewed, committed, pushed, and
remotely verified one-file final acceptance sync. FW-RT6-11c remains outside
this authorization.
<!-- FW-RT6-11b-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-11b-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11b — root-public API cleanup final acceptance sync

```text
checkpoint: FW-RT6-11b final acceptance sync
baseline head: 9a16cc8ed92305bdeabf53c67c1db0f49bc28725
FW-RT6-11a final acceptance: 06e98b0024c2bafc1581d5e3349eae01c1929a8f
Control A implementation: ffaaa167aae595d315995ce307f44b24ac1ef37c
Control A acceptance sync: 644350479aa3dde264627978d555ef47a432cd3f
Control B implementation: 6cdb08ac35f2c7f4baa0b8b2a61d8e78a33b0c02
Control B acceptance sync: 727d999fd012731088fd3261c6e5b0e4bb161e94
Control C aggregate acceptance: 9a16cc8ed92305bdeabf53c67c1db0f49bc28725
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation surface: 6 files
exact Control B implementation surface: 11 files
exact corrective Control C aggregate surface: 7 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A root-public tests: 12 / PASS
focused Control B namespace tests: 12 / PASS
focused Control A+B root-public tests: 24 / PASS
canonical root-public manifest gate: PASS
focused FW-RT6-11a compatibility tests: 30 / PASS
accepted v5 compatibility regressions: 62 / PASS
v5.3 lazy provider adapter gate: PASS
v5.4 client-injection / fake / real-runtime gates: PASS
full Framework unit suite: 649 / PASS
canonical runtime source: framework.public_api.PUBLIC_API_NAMES / REUSED / PASS
machine-readable projection: docs/v600_root_public_api_manifest.json / REUSED / PASS
manifest schema: v6.root_public_api_manifest / PASS
framework root-public names: 127 / UNCHANGED / PASS
provider-neutral root exports: 112 / UNCHANGED / PASS
v5 provider compatibility root exports: 15 / PRESERVED / LAZY / SILENT / PASS
root-public unordered SHA-256: 4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0
provider-neutral SHA-256: c75717d89860716610c539d0ba6411259b3b9dd77349fd7b8c17bcdf2bdb2c3e
provider-compatibility SHA-256: 4f8dd7bc622270fd5f4cbdae80d656cf21c6aed2604b5e73f465f51e457fa996
wildcard runtime order: PRESERVED / NON-CONTRACTUAL / PASS
stable optional provider namespace: framework.providers.openai.voice_input / PASS
namespace exact exports: 15 / PASS
namespace container exports: 0 / EXPLICIT MODULE ONLY / PASS
root and namespace object identity: SAME / PASS
new provider-specific root exports: 0 / PASS
provider compatibility deprecations: 0 / PASS
docs/example/export drift: PASS
offline wheel provider-namespace membership: PASS
namespace import loads OpenAI SDK: False / PASS
provider/network/audio/microphone/playback/real VTS execution: False / PASS
factory signatures and return/event shapes: UNCHANGED
API and schema version labels: UNCHANGED
runtime source changed by Control C/final sync: False
public-facade contract changed by final sync: False
application-integration contract changed by final sync: False
machine-readable manifest changed by final sync: False
provider namespace source changed by final sync: False
aggregate gate changed by final sync: False
existing tests changed by final sync: False
README or example changed by final sync: False
FW-RT6-11b tasks: 6 / 6 ACCEPTED
FW-RT6-11b aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-11c exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-11c implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-11b closes the v6 root-public API cleanup boundary.
`framework.public_api.PUBLIC_API_NAMES` remains the single runtime source,
and `docs/v600_root_public_api_manifest.json` remains its deterministic
machine-readable projection. The Framework root remains an unordered
127-name contract containing 112 preferred provider-neutral exports and 15
lazy, silent v5 OpenAI voice-input compatibility exports.

`framework.providers.openai.voice_input` remains the sole stable explicit
optional-provider namespace and exposes the same exact 15 objects as the
retained root compatibility surface. The intermediate
`framework.providers` and `framework.providers.openai` containers remain
empty. Root and namespace imports remain free of provider SDK, client,
credential, network, audio, microphone, playback, and real VTube Studio work.

Wildcard runtime order remains observable only for compatibility and is not
part of the v6 contract. No root export, compatibility guarantee, factory
signature, return or event shape, API version, provider execution boundary,
or application-integration contract changes in this final sync.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade or application-integration contract, machine-readable
manifest, provider namespace source, aggregate gate, existing test, historical
v5 gate, README, or example. It formally completes, verifies, accepts, commits,
pushes, and closes all three controls and all six FW-RT6-11b aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-11c exact contract review is authorized. This sync does not authorize
FW-RT6-11c implementation.
<!-- FW-RT6-11b-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11c-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11c Control A — migration foundation acceptance sync

```text
checkpoint: FW-RT6-11c Control A
baseline head: 7f0f66b11347257ac239982c4118fe8277c2a1e3
FW-RT6-11b final acceptance: 7f0f66b11347257ac239982c4118fe8277c2a1e3
Control A implementation baseline: 7f0f66b11347257ac239982c4118fe8277c2a1e3
Control A implementation candidate: WORKTREE / VERIFIED
Control A: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH
exact Control A implementation surface: 7 files
corrective-r2 replacement: tests/test_migration_examples_control_a.py / INCLUDED_IN_7
acceptance-sync exact surface: 1 file
combined worktree surface: 8 files
dedicated Control A migration/example gate: PASS
focused Control A migration/example tests: 12 / PASS
accepted FW-RT6-11a compatibility gate: PASS
accepted FW-RT6-11b root-public cleanup gate: PASS
full Framework unit suite: 661 / PASS
migration guide: docs/v600_v5_to_v6_session_migration.md / PASS
new examples: 2 / PROVIDER-FREE / PASS
text-only example: PASS
explicit unavailable/fallback example: PASS
example import surface: framework root only / PASS
example main guards: PASS
provider credentials required: False / PASS
optional provider SDK import: False / PASS
provider/network/audio/microphone/playback/real VTS execution: False / PASS
credential-free subprocess preserves Windows/Python system environment: True / PASS
default RealtimeSession compatibility mode: v5_skeleton / PASS
explicit real-runtime request mode: v6_unified / PASS
production unified orchestration available: False / TRUTHFUL
explicit unified request outcome: REJECTED / PASS
silent unified-to-mock fallback: False / PASS
fallback selection: EXPLICIT_HOST_ACTION / PASS
v5 standalone sessions: SUPPORTED / UNCHANGED
framework runtime source changed by Control A: False
framework root-public names: 127 / UNCHANGED
factory signatures and API/schema version labels: UNCHANGED
runtime source changed by acceptance sync: False
public-facade contract changed by acceptance sync: False
application-integration contract changed by acceptance sync: False
migration guide or example changed by acceptance sync: False
dedicated gate or existing test changed by acceptance sync: False
FW-RT6-11c aggregate: NOT_COMPLETED
FW-RT6-11c tasklist: 0 / 8 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
Control B implementation: NOT_AUTHORIZED
aggregate acceptance: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the migration foundation for moving host applications from
the supported v5 standalone sessions toward the v6 unified-session contract.
The guide keeps `TextChatSession`, `VoiceInputSession`, `VoiceOutputSession`,
and `MotionSession` support explicit and distinguishes `v5_standalone`, the
provider-free deterministic `v5_skeleton`, and the requested `v6_unified`
compatibility profiles.

The two executable examples import only the public `framework` root and require
no provider credential or optional provider SDK. The text-only example remains
an explicitly marked deterministic mock. The unavailable-capability example
truthfully rejects an explicit unified-runtime request and performs fallback
only after a separate host decision; it never silently substitutes mock work.

Corrective-r2 changes only the credential-free subprocess test harness. It
preserves Windows and Python system environment required by `asyncio` while
removing credential-bearing variables. It changes no example, runtime source,
public contract, provider boundary, or execution behavior.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes none
of the seven accepted Control A implementation files, any runtime source,
root-public inventory, factory signature, API/schema version, dedicated gate,
existing test, migration guide, or example. None of the eight FW-RT6-11c
aggregate task checkboxes close here.

After the combined eight-file worktree is reviewed, committed, pushed, and
remotely verified, only Control B exact contract review is authorized. Control
B implementation, aggregate acceptance, and their commit/push remain
separately gated.
<!-- FW-RT6-11c-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11c-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11c Control B — provider-free migration examples acceptance sync

```text
checkpoint: FW-RT6-11c Control B
baseline head: 5cec4e338688724ee43157b7ccbf75deb67cf70e
Control A implementation and acceptance sync: 5cec4e338688724ee43157b7ccbf75deb67cf70e
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B implementation baseline: 5cec4e338688724ee43157b7ccbf75deb67cf70e
Control B implementation candidate: WORKTREE / VERIFIED
Control B: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH
exact Control B implementation surface: 9 files
acceptance-sync exact surface: 1 file
combined worktree surface: 10 files
dedicated Control B migration/example gate: PASS
focused Control B migration/example tests: 14 / PASS
dedicated Control A migration/example source gate: PASS
focused Control A migration/example tests: 12 / PASS
accepted FW-RT6-11a compatibility gate: PASS
accepted FW-RT6-11b root-public cleanup gate: PASS
full Framework unit suite: 675 / PASS
new Control B examples: 4 / PROVIDER-FREE / PASS
all migration examples: 6 / FRAMEWORK_ROOT_ONLY / PASS
host-captured audio handoff: OPAQUE_ID / FAKE_ADAPTER / PASS
host microphone or audio-file read: False / PASS
partial transcript/audio streaming claimed: False / PASS
interrupt aggregate status: partial / TERMINAL / PASS
interrupt hard cancellation claimed: False / PASS
local playback ownership: HOST / PASS
playback acknowledgement confirms physical stop: False / PASS
motion lifecycle mapping: listening / thinking / speaking / completed / PASS
missing motion stage: not_configured / TYPED / PASS
conversation terminal completion count: 1 / PASS
provider credentials required: False / PASS
optional provider SDK import: False / PASS
provider/network/audio/microphone/playback/real VTS execution: False / PASS
framework runtime source changed by Control B: False
framework root-public names: 127 / UNCHANGED
factory signatures and API/schema version labels: UNCHANGED
runtime source changed by acceptance sync: False
public-facade contract changed by acceptance sync: False
application-integration contract changed by acceptance sync: False
migration guide or example changed by acceptance sync: False
dedicated gate or existing test changed by acceptance sync: False
FW-RT6-11c aggregate: NOT_COMPLETED
FW-RT6-11c tasklist: 0 / 8 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C aggregate acceptance exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
Control C aggregate implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts four provider-free executable examples that complete the
reviewed host-integration boundary without adding runtime source or root-public
API. Every example imports only the public `framework` root, runs without
provider credentials or optional provider SDKs, and performs no provider,
network, microphone, playback, audio-file, or real VTube Studio work.

The host-captured-audio example retains a `VoiceInputSession` and hands an
opaque host input identifier to `FakeVoiceInputProviderAdapter`; it does not
claim unified streaming input. The interrupt example keeps
`coordination_result.partial` as heterogeneous terminal subsystem observations,
not partial transcript or audio streaming, and does not claim hard provider
cancellation.

The local-playback example leaves playback ownership with the host. A flush
request and acknowledgement remain protocol observations and never confirm a
physical stop. The motion-extension example maps lifecycle observations into
typed motion requests; an absent motion stage returns `not_configured` while
the conversation reaches its terminal completion exactly once.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes none
of the nine accepted Control B implementation files, any runtime source,
root-public inventory, factory signature, API/schema version, dedicated gate,
existing test, migration guide, or example. None of the eight FW-RT6-11c
aggregate task checkboxes close here.

After the combined ten-file worktree is reviewed, committed, pushed, and
remotely verified, only the Control C aggregate-acceptance exact contract
review is authorized. Aggregate implementation and its commit/push remain
separately gated.
<!-- FW-RT6-11c-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-11c Control C — migration guide and examples aggregate acceptance

```text
checkpoint: FW-RT6-11c Control C
baseline head: 69c47486f9abda234accd6838e2c78726cb5c65f
Control A implementation and acceptance: 5cec4e338688724ee43157b7ccbf75deb67cf70e
Control B implementation and acceptance: 69c47486f9abda234accd6838e2c78726cb5c65f
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
exact Control C surface: 7 files
Control A/B gate/test semantic sync: 4 files / CONTROL_C TASK BOUNDARY ONLY
dedicated aggregate acceptance gate: scripts/check_v600_migration_examples_acceptance.py / PASS
focused Control A+B tests: 26 / PASS
full Framework unit suite: 675 / PASS
migration guide: PASS
v5 standalone sessions retained: 4 / PASS
all migration examples: 6 / PROVIDER-FREE / PUBLIC ROOT ONLY / PASS
text-only example: PASS
explicit unavailable/fallback example: PASS
host-captured audio example: PASS
interrupt/partial completion example: PASS
local playback boundary example: PASS
motion extension hook example: PASS
example imports without provider credentials: PASS
optional provider SDK import: False / PASS
provider/network/audio-read/microphone/playback/real VTS execution: False / PASS
partial transcript/audio streaming claimed: False / PASS
provider hard cancellation claimed: False / PASS
physical playback stop claimed: False / PASS
conversation terminal replacement or duplication by motion: False / PASS
framework runtime source changed by Control C: False
application-integration contract changed by Control C: False
migration guide changed by Control C: False
examples changed by Control C: False
framework root-public names: 127 / UNCHANGED
factory signatures and API/schema version labels: UNCHANGED
FW-RT6-11c tasks: 8 / 8 ACCEPTED-CANDIDATE
FW-RT6-11c final acceptance sync: NOT_AUTHORIZED
FW-RT6-12a exact contract review: NOT_AUTHORIZED
Control C commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted migration guide and all six provider-free
examples. It closes only the eight FW-RT6-11c task checkboxes as
acceptance-candidates and adds a dedicated offline aggregate gate. The four
accepted Control A/B gate and test files receive only the reviewed Control C
task-boundary and status synchronization.

The aggregate preserves the existing application boundaries. The Framework
does not acquire host audio capture or local playback ownership, does not
invent partial transcript/audio streaming or provider hard cancellation, and
does not treat playback acknowledgement as physical-stop confirmation. Motion
mapping remains host/plugin-owned and cannot replace or duplicate the
conversation terminal.

This exact seven-file Control C changes only `docs/public_facade.md`, this
tasklist, the new aggregate gate, and four accepted Control A/B gate/test
files. It changes no runtime source, application-integration contract,
migration guide, example, root export, factory signature, return/event shape,
API/schema version, provider namespace, historical v5 gate, or README.

The eight tasks are acceptance-candidates rather than final CLOSED state.
Final completion requires a separately reviewed one-file acceptance sync,
commit, push, and remote verification. FW-RT6-12a remains separately gated.
<!-- FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-11c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-11c — migration guide and examples final acceptance sync

```text
checkpoint: FW-RT6-11c final acceptance sync
baseline head: e3e0b1968784fcb780e7a9da67f6590f882c2a29
FW-RT6-11b final acceptance: 7f0f66b11347257ac239982c4118fe8277c2a1e3
Control A implementation and acceptance: 5cec4e338688724ee43157b7ccbf75deb67cf70e
Control B implementation and acceptance: 69c47486f9abda234accd6838e2c78726cb5c65f
Control C aggregate acceptance: e3e0b1968784fcb780e7a9da67f6590f882c2a29
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation and acceptance surface: 8 files
exact Control B implementation and acceptance surface: 10 files
exact Control C aggregate surface: 7 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A migration/example tests: 12 / PASS
focused Control B migration/example tests: 14 / PASS
focused Control A+B migration/example tests: 26 / PASS
accepted FW-RT6-11a compatibility gate: PASS
accepted FW-RT6-11b root-public cleanup gate: PASS
full Framework unit suite: 675 / PASS
migration guide: docs/v600_v5_to_v6_session_migration.md / ACCEPTED
v5 standalone sessions retained: 4 / PASS
all migration examples: 6 / PROVIDER-FREE / PUBLIC ROOT ONLY / ACCEPTED
text-only example: ACCEPTED
explicit unavailable/fallback example: ACCEPTED
host-captured audio example: ACCEPTED
interrupt/partial completion example: ACCEPTED
local playback boundary example: ACCEPTED
motion extension hook example: ACCEPTED
default realtime compatibility mode: v5_skeleton / PASS
explicit unified request mode: v6_unified / TRUTHFUL
production unified orchestration available: False / TRUTHFUL
silent unified-to-mock fallback: False / PASS
host audio capture ownership: APPLICATION / UNCHANGED
local playback ownership: APPLICATION / UNCHANGED
partial transcript/audio streaming claimed: False / PASS
provider hard cancellation claimed: False / PASS
physical playback stop confirmed by acknowledgement: False / PASS
motion mapping ownership: APPLICATION_OR_PLUGIN / UNCHANGED
motion side effect replaces or duplicates conversation terminal: False / PASS
example imports without provider credentials: PASS
optional provider SDK import: False / PASS
provider/network/audio-read/microphone/playback/real VTS execution: False / PASS
framework root-public names: 127 / UNCHANGED
factory signatures and return/event shapes: UNCHANGED
API and schema version labels: UNCHANGED
runtime source changed by Control C/final sync: False
public-facade contract changed by final sync: False
application-integration contract changed by final sync: False
migration guide changed by final sync: False
example changed by final sync: False
aggregate gate changed by final sync: False
existing test changed by final sync: False
README changed by final sync: False
FW-RT6-11c tasks: 8 / 8 ACCEPTED
FW-RT6-11c aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-12a exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-12a implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-11c closes the v6 migration-guide and provider-free example boundary.
The canonical guide preserves the supported v5 standalone sessions and
truthfully distinguishes the provider-free `v5_skeleton` path from an explicit
but currently unavailable `v6_unified` production-orchestration request.

All six examples remain public-root-only and credential-free. Audio capture
and physical playback stay application-owned; interrupt `partial` remains a
terminal subsystem aggregate rather than transcript/audio streaming; provider
hard cancellation is not claimed; motion mapping remains host/plugin-owned and
cannot replace or duplicate the conversation terminal.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade or application-integration contract, migration guide,
example, aggregate gate, existing test, root export, provider namespace,
factory signature, return/event shape, API/schema version, historical v5 gate,
or README. It formally completes, verifies, accepts, commits, pushes, and
closes all three controls and all eight FW-RT6-11c aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-12a exact contract review is authorized. This sync does not authorize
FW-RT6-12a implementation.
<!-- FW-RT6-11c-FINAL-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-12a-A-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-12a Control A — public audio-chunk contract acceptance sync

```text
checkpoint: FW-RT6-12a Control A
baseline head: d5e707fa4bca34322b9a2319696273b129b6f395
FW-RT6-11c final acceptance: d5e707fa4bca34322b9a2319696273b129b6f395
Control A implementation baseline: d5e707fa4bca34322b9a2319696273b129b6f395
Control A implementation candidate: WORKTREE / VERIFIED
Control A: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH
exact Control A implementation surface: 6 files
acceptance-sync exact surface: 1 file
combined worktree surface: 7 files
dedicated Control A audio-chunk contract gate: PASS
focused Control A audio-chunk tests: 15 / PASS
accepted FW-RT6-11a compatibility gate: PASS
accepted FW-RT6-11b root-public cleanup gate: PASS
accepted FW-RT6-11c migration/examples gate: PASS
full Framework unit suite: 690 / PASS
stable explicit namespace: framework.voice_input_streaming / PASS
namespace exports: 9 / EXACT / EXPLICIT_ONLY / PASS
streaming API version: 6.0 / PASS
audio chunk type: VoiceInputAudioChunk / DATA_ONLY / PASS
chunk sequence: ZERO_BASED / STRICTLY_ORDERED CONTRACT / PASS
end-of-input marker: VoiceInputStreamEnd / NEXT_EXPECTED_SEQUENCE / PASS
input-abort marker: VoiceInputStreamAbort / OUT_OF_BAND / PASS
typed operation result: VoiceInputStreamOperationResult / PASS
typed result codes: 11 / INCLUDING_NONE / PASS
accepted audio format capability: PASS
maximum chunk-size capability: PASS
maximum duration capability: PASS
raw audio present in repr/public projection: False / PASS
private path or URL accepted as stream ID: False / PASS
default chunk-input support: False / TRUTHFUL / PASS
current runtime chunk-input support: False / UNCHANGED / PASS
session streaming methods added by Control A: False / PASS
partial transcript event delivery: False / DEFERRED_TO_CONTROL_B
provider hard-cancel proof from input abort: False / PASS
backpressure implementation: False / DEFERRED_TO_FW-RT6-12b
framework root-public names: 127 / UNCHANGED
factory signatures and API/schema version labels: UNCHANGED
provider credential required: False / PASS
optional provider SDK import: False / PASS
provider/network/audio-read/microphone/playback/real VTS execution: False / PASS
runtime source changed by acceptance sync: False
public-facade contract changed by acceptance sync: False
application-integration contract changed by acceptance sync: False
streaming contract module or guide changed by acceptance sync: False
dedicated gate or existing test changed by acceptance sync: False
FW-RT6-12a aggregate: NOT_COMPLETED
FW-RT6-12a tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_A
Control B exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
Control B implementation: NOT_AUTHORIZED
aggregate acceptance: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control A accepts the provider-neutral, immutable data vocabulary for future
public audio-chunk input. The stable explicit namespace
`framework.voice_input_streaming` contains the exact nine reviewed exports and
does not enlarge the frozen 127-name Framework root-public inventory.

`VoiceInputAudioChunk` carries non-empty raw bytes only as explicit input. Its
representation and public projection expose the byte count but never the raw
payload. Zero-based sequence numbers, the next-sequence end marker, the
out-of-band abort marker, truthful format and size/duration capability limits,
and typed rejection results form the accepted Control A contract.

Control A remains data-only. It adds no streaming method to
`VoiceInputSession` or `RealtimeSession`, and the current runtime continues to
report `audio_chunk_input_supported=False`. Partial-transcript event delivery
and session/runtime adoption remain deferred to Control B. Input abort is not
evidence of provider hard cancellation, and queue backpressure remains a
separate FW-RT6-12b boundary.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes none
of the six accepted Control A implementation files, any runtime source,
root-public inventory, factory signature, API/schema version, public-facade or
application-integration contract, streaming guide, dedicated gate, or existing
test. None of the seven FW-RT6-12a aggregate task checkboxes close here.

After the combined seven-file worktree is reviewed, committed, pushed, and
remotely verified, only Control B exact contract review is authorized. Control
B implementation, aggregate acceptance, and their commit/push remain
separately gated.
<!-- FW-RT6-12a-A-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-12a-B-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-12a Control B — VoiceInputSession streaming acceptance sync

```text
checkpoint: FW-RT6-12a Control B
baseline head: f07105742ea6068a6d1655d737c160a5f3487dd5
Control A implementation and acceptance: f07105742ea6068a6d1655d737c160a5f3487dd5
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B implementation candidate: WORKTREE / VERIFIED
Control B: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH
exact Control B implementation surface: 10 files
acceptance-sync exact surface: 1 file
combined worktree surface: 11 files
dedicated Control B audio-chunk streaming gate: PASS
focused Control B audio-chunk streaming tests: 21 / PASS
focused Control A audio-chunk contract tests: 15 / PASS
focused Control A+B tests: 36 / PASS
accepted FW-RT6-11a compatibility gate: PASS
accepted FW-RT6-11b root-public cleanup gate: PASS
accepted FW-RT6-11c migration/examples gate: PASS
full Framework unit suite: 711 / PASS
stable contract namespace: framework.voice_input_streaming / 9 EXACT / PASS
stable adapter namespace: framework.voice_input_streaming_adapter / 2 EXACT / PASS
adapter namespace root exports: 0 / EXPLICIT_ONLY / PASS
session runtime adoption: VoiceInputSession / PASS
RealtimeSession streaming adoption: False / UNCHANGED / PASS
factory signature changed: False / PASS
framework root-public names: 127 / UNCHANGED
default VoiceInputSession chunk-input support: False / TRUTHFUL / PASS
explicit deterministic fake capability: True / PASS
supported encoding: pcm16 / PASS
maximum chunk-size enforcement: PASS
maximum cumulative-duration enforcement: PASS
zero-based strict sequence enforcement: PASS
out-of-order retry without sequence consumption: PASS
ordered end-of-input enforcement: PASS
partial transcript delivery: CANONICAL_V6 / CORRELATED / PASS
final transcript delivery: VoiceInputSession.last_stream_result / PASS
legacy mapping callback expansion: False / PASS
cooperative stream abort: PASS
provider hard-cancel claimed: False / PASS
host capture physical-stop claimed: False / PASS
active-stream close terminalization: PASS
adapter exception private detail exposed: False / PASS
raw audio present in repr/event/result/public projection: False / PASS
deterministic fake reads or decodes raw audio: False / PASS
backpressure queue implementation: False / DEFERRED_TO_FW-RT6-12b
provider credential required: False / PASS
optional provider SDK import: False / PASS
provider/network/audio-file/microphone/playback/real VTS execution: False / PASS
runtime source changed by acceptance sync: False
public-facade contract changed by acceptance sync: False
application-integration contract changed by acceptance sync: False
streaming contract guide changed by acceptance sync: False
dedicated gate or existing test changed by acceptance sync: False
FW-RT6-12a aggregate: NOT_COMPLETED
FW-RT6-12a tasklist: 0 / 7 CLOSED
tasklist aggregate checkboxes: NOT_CLOSED_BY_CONTROL_B
Control C aggregate exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
Control C implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

Control B accepts explicit, provider-neutral audio-chunk streaming adoption on
`VoiceInputSession`. The default session remains truthfully unsupported. A host
must explicitly configure an adapter before beginning a stream, and
`RealtimeSession` remains unchanged.

Framework validates stream identity, explicit audio encoding, maximum chunk
bytes, cumulative duration, zero-based ordering, ordered end-of-input, and
typed retry or terminal rejection. The deterministic fake adapter supplies
offline partial and final transcript observations without reading or decoding
the raw chunk bytes.

Partial and final transcripts use the existing canonical v6 realtime event
types with one Framework-owned session, turn, generation, and event sequence.
Streaming observations do not expand the retained v5 mapping-callback shapes.
The final typed result is available from `VoiceInputSession.last_stream_result`.

Abort is cooperative generation invalidation only. It does not claim provider
hard cancellation or physical termination of application-owned capture.
Backpressure and queue policy remain deferred to FW-RT6-12b. Control B performs
no provider, network, audio-file, microphone, playback, or real VTS execution.

This exact one-file sync changes only `docs/v600_tasklist.md`; it changes none
of the ten accepted Control B implementation files, any runtime source,
root-public inventory, factory signature, API/schema version, public-facade or
application-integration contract, streaming guide, dedicated gate, or existing
test. None of the seven FW-RT6-12a aggregate task checkboxes close here.

After the combined eleven-file worktree is reviewed, committed, pushed, and
remotely verified, only the Control C aggregate-acceptance exact contract
review is authorized. Control C implementation and its commit/push remain
separately gated.
<!-- FW-RT6-12a-B-ACCEPTANCE-SYNC:END -->


<!-- FW-RT6-12a-C-AGGREGATE-ACCEPTANCE:BEGIN -->
## FW-RT6-12a Control C — public audio-chunk streaming aggregate acceptance

```text
checkpoint: FW-RT6-12a Control C
baseline head: 1b829c092ddb4651c3d5cdea687bbffa645ee6c5
Control A implementation and acceptance: f07105742ea6068a6d1655d737c160a5f3487dd5
Control B implementation and acceptance: 1b829c092ddb4651c3d5cdea687bbffa645ee6c5
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: IMPLEMENTED / AWAITING_REVIEW
exact Control C surface: 7 files
Control A/B gate/test semantic sync: 4 files / CONTROL_C TASK BOUNDARY ONLY
dedicated aggregate acceptance gate: scripts/check_v600_public_audio_chunk_streaming_acceptance.py / PASS
focused Control A tests: 15 / PASS
focused Control B tests: 21 / PASS
focused Control A+B tests: 36 / PASS
full Framework unit suite: 711 / PASS
stable contract namespace: framework.voice_input_streaming / 9 EXACT / PASS
stable adapter namespace: framework.voice_input_streaming_adapter / 2 EXACT / PASS
adapter namespace root exports: 0 / EXPLICIT_ONLY / PASS
session runtime adoption: VoiceInputSession / PASS
RealtimeSession streaming adoption: False / UNCHANGED / PASS
factory signature changed by Control C: False / PASS
framework root-public names: 127 / UNCHANGED
default VoiceInputSession chunk-input support: False / TRUTHFUL / PASS
explicit deterministic fake capability: True / PASS
audio chunk type: VoiceInputAudioChunk / ACCEPTED
chunk sequence: ZERO_BASED / STRICT_NEXT_EXPECTED / ACCEPTED
format/chunk-size/duration capability: ACCEPTED
end-of-input: ORDERED_NEXT_SEQUENCE / ACCEPTED
input abort: COOPERATIVE / ACCEPTED
partial transcript event: CANONICAL_V6 / CORRELATED / ACCEPTED
malformed/out-of-order chunk: TYPED_REJECTION / ACCEPTED
legacy mapping callback expansion: False / PASS
provider hard-cancel claimed: False / PASS
host capture physical-stop claimed: False / PASS
raw audio present in repr/event/result/public projection: False / PASS
backpressure queue implementation: False / DEFERRED_TO_FW-RT6-12b
provider credential required: False / PASS
optional provider SDK import: False / PASS
provider/network/audio-file/microphone/playback/real VTS execution: False / PASS
framework runtime source changed by Control C: False
application-integration contract changed by Control C: False
streaming guide changed by Control C: False
root API manifest changed by Control C: False
FW-RT6-12a tasks: 7 / 7 ACCEPTED-CANDIDATE
FW-RT6-12a final acceptance sync: NOT_AUTHORIZED
FW-RT6-12b exact contract review: NOT_AUTHORIZED
Control C commit / push: NOT_AUTHORIZED
```

Control C aggregates the accepted provider-neutral audio-chunk vocabulary and
the explicit `VoiceInputSession` runtime adoption. It closes only the seven
FW-RT6-12a task checkboxes as acceptance-candidates and adds a dedicated
offline aggregate gate. The four accepted Control A/B gate and test files
receive only the reviewed Control C task-boundary and status synchronization.

The aggregate preserves the frozen application boundaries. Streaming remains
default-off and requires an explicit adapter. `RealtimeSession`, the 127-name
Framework root, factory signatures, and API/schema version labels stay
unchanged. Partial and final text remain canonical v6 events correlated to one
Framework-owned session, turn, generation, and event sequence; the retained v5
mapping callbacks are not expanded.

Abort remains cooperative and does not prove provider hard cancellation or
physical termination of application-owned capture. Raw audio remains absent
from public projections, results, events, and representations. Backpressure
and queue policy remain FW-RT6-12b work. The aggregate performs no provider,
network, audio-file, microphone, playback, or real VTS execution.

This exact seven-file Control C changes only `docs/public_facade.md`, this
tasklist, the new aggregate gate, and four accepted Control A/B gate/test
files. It changes no Framework runtime source, application-integration
contract, streaming guide, root API manifest, factory signature, public return
or event shape, provider namespace, example, README, or historical v5 gate.

The seven tasks are acceptance-candidates rather than final CLOSED state.
Final completion requires a separately reviewed one-file acceptance sync,
commit, push, and remote verification. FW-RT6-12b remains separately gated.
<!-- FW-RT6-12a-C-AGGREGATE-ACCEPTANCE:END -->


<!-- FW-RT6-12a-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## FW-RT6-12a — public audio-chunk streaming final acceptance sync

```text
checkpoint: FW-RT6-12a final acceptance sync
baseline head: 164da2bff3b8b3329a0063d049031960d4d9bdae
FW-RT6-11c final acceptance: d5e707fa4bca34322b9a2319696273b129b6f395
Control A implementation and acceptance: f07105742ea6068a6d1655d737c160a5f3487dd5
Control B implementation and acceptance: 1b829c092ddb4651c3d5cdea687bbffa645ee6c5
Control C aggregate acceptance: 164da2bff3b8b3329a0063d049031960d4d9bdae
Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
Control C: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED
exact Control A implementation and acceptance surface: 7 files
exact Control B implementation and acceptance surface: 11 files
exact Control C aggregate surface: 7 files
final acceptance-sync exact surface: 1 file
dedicated Control C aggregate gate: PASS
focused Control A tests: 15 / PASS
focused Control B tests: 21 / PASS
focused Control A+B tests: 36 / PASS
accepted FW-RT6-11a compatibility gate: PASS
accepted FW-RT6-11b root-public cleanup gate: PASS
accepted FW-RT6-11c migration/examples gate: PASS
full Framework unit suite: 711 / PASS
stable contract namespace: framework.voice_input_streaming / 9 EXACT / ACCEPTED
stable adapter namespace: framework.voice_input_streaming_adapter / 2 EXACT / ACCEPTED
adapter namespace root exports: 0 / EXPLICIT_ONLY / PASS
session runtime adoption: VoiceInputSession / ACCEPTED
RealtimeSession streaming adoption: False / UNCHANGED / PASS
framework root-public names: 127 / UNCHANGED
factory signatures and return/event shapes: UNCHANGED
API and schema version labels: UNCHANGED
default VoiceInputSession chunk-input support: False / TRUTHFUL / PASS
explicit deterministic fake capability: True / PASS
audio chunk type: VoiceInputAudioChunk / ACCEPTED
chunk sequence: ZERO_BASED / STRICT_NEXT_EXPECTED / ACCEPTED
format/chunk-size/duration capability: ACCEPTED
end-of-input: ORDERED_NEXT_SEQUENCE / ACCEPTED
input abort: COOPERATIVE / ACCEPTED
partial transcript event: CANONICAL_V6 / CORRELATED / ACCEPTED
malformed/out-of-order chunk: TYPED_REJECTION / ACCEPTED
legacy mapping callback expansion: False / PASS
provider hard-cancel claimed: False / PASS
host capture physical-stop claimed: False / PASS
raw audio present in repr/event/result/public projection: False / PASS
backpressure queue implementation: False / DEFERRED_TO_FW-RT6-12b
provider credential required: False / PASS
optional provider SDK import: False / PASS
provider/network/audio-file/microphone/playback/real VTS execution: False / PASS
runtime source changed by Control C/final sync: False
public-facade contract changed by final sync: False
application-integration contract changed by final sync: False
streaming guide changed by final sync: False
root API manifest changed by final sync: False
aggregate gate changed by final sync: False
existing gate/test changed by final sync: False
example changed by final sync: False
README changed by final sync: False
FW-RT6-12a tasks: 7 / 7 ACCEPTED
FW-RT6-12a aggregate: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / CLOSED
FW-RT6-12b exact contract review: AUTHORIZED_AFTER_SYNC_PUSH
FW-RT6-12b implementation: NOT_AUTHORIZED
final acceptance-sync commit / push: NOT_AUTHORIZED
```

FW-RT6-12a closes the provider-neutral public audio-chunk streaming boundary.
The accepted contract keeps both streaming namespaces explicit-only, preserves
the frozen 127-name Framework root, and adopts streaming only through an
explicitly configured `VoiceInputSession` adapter. Default capability remains
truthfully unsupported and `RealtimeSession` remains unchanged.

Ordered audio chunks, typed retry/rejection, ordered end-of-input, cooperative
abort, and correlated canonical partial/final transcript events are accepted.
Raw audio remains absent from representations, events, results, and public
projections. Neither provider hard cancellation nor physical termination of
application-owned capture is claimed. Backpressure and queue policy remain a
separate FW-RT6-12b boundary.

This final sync changes only `docs/v600_tasklist.md`; it changes no runtime
source, public-facade or application-integration contract, streaming guide,
root API manifest, aggregate gate, existing gate/test, provider namespace,
factory signature, return/event shape, API/schema version, example, historical
v5 gate, or README. It formally completes, verifies, accepts, commits, pushes,
and closes all three controls and all seven FW-RT6-12a aggregate tasks.

After this one-file sync is reviewed, committed, pushed, and remotely verified,
FW-RT6-12b exact contract review is authorized. This sync does not authorize
FW-RT6-12b implementation.
<!-- FW-RT6-12a-FINAL-ACCEPTANCE-SYNC:END -->
