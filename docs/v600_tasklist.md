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

- [ ] host-owned audio sourceをturnへ関連付ける。
- [ ] preflight/start/completed/failed eventを発行する。
- [ ] transcript finalをtyped payloadにする。
- [ ] input abortを実装する。
- [ ] late transcriptをgeneration gateで拒否する。
- [ ] raw audio retention default-offを維持する。
- [ ] FILE_PATH pathをpublic eventへ出さない。

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

- [ ] existing `VoiceInputResult`へcorrelation contextをadditiveに追加する。
- [ ] existing factory methodsを維持する。
- [ ] existing `listen_result` / `transcribe_audio_result` compatibilityを維持する。
- [ ] existing mapping callbacksをv6 event adapterで維持する。
- [ ] close後resultを統一rejectionへ接続する。

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

- [ ] motion requestへoptional turn/generation contextを追加する。
- [ ] result/eventへturn/generationを追加する。
- [ ] existing request_id/session_id compatibilityを維持する。
- [ ] event sequenceをunified sequencerへbridgeする。
- [ ] current VTS generation suppressionをcommon stale guardへ接続する。

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

- [ ] lifecycle-to-motion hook interfaceを追加する。
- [ ] listening/thinking/speaking/interrupted/completed/failed phaseを通知可能にする。
- [ ] Framework coreがcharacter固有mappingを決めない。
- [ ] host/pluginがprovider-neutral intentを返す。
- [ ] unsupported intentをtypedに処理する。
- [ ] hook failureがconversation terminalを必ずしもfailさせないpolicyを固定する。

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

- [ ] pending motion request trackingを追加する。
- [ ] request cancel capabilityを追加する。
- [ ] stop_motion unavailableをtruthfulに返す。
- [ ] whole-turn interruptからmotion reachを返す。
- [ ] duplicate stop/cancelをsafeにする。

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

- [ ] active stage registryを追加する。
- [ ] interrupt target validationを実装する。
- [ ] turn terminal/not-found/closed結果を実装する。
- [ ] LLM cancelを呼ぶ。
- [ ] TTS generation cancel/pending clearを呼ぶ。
- [ ] artifact invalidationを呼ぶ。
- [ ] motion cancel/clearを呼ぶ。
- [ ] aggregate resultを構築する。
- [ ] timeout/partial completionを処理する。

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

- [ ] interrupt request IDを導入するか決定する。
- [ ] duplicate interruptを同じterminal resultへ収束させる。
- [ ] interrupt vs normal completion raceを固定する。
- [ ] interrupt vs close raceを固定する。
- [ ] flush vs interrupt orderingを固定する。
- [ ] new turn request during interruptingをtyped rejectする。
- [ ] deterministic fake race testsを追加する。

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

- [ ] `decide_barge_in()`をpure policy decisionとして維持する。
- [ ] decisionからcontrol planを生成する。
- [ ] actual executionはinterrupt coordinatorへ委譲する。
- [ ] microphone detectionをcore scopeへ入れない。
- [ ] hard-cancel policy選択時もcapability不足を正しくdowngradeする。

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

- [ ] text delta delivery前にgeneration checkする。
- [ ] transcript delivery前にcheckする。
- [ ] TTS artifact publish前にcheckする。
- [ ] motion completion publish前にcheckする。
- [ ] close/reset/new turn後のold callbackをdropする。
- [ ] stale count/drop reasonをdiagnosticsへ記録する。

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

- [ ] turn-only resetを定義する。
- [ ] session resetを定義する。
- [ ] reconnect requiredを定義する。
- [ ] close required/permanently failedを定義する。
- [ ] reset時generation incrementを実装する。
- [ ] resetで失われるprovider contextを文書化する。
- [ ] reset failureをtypedに返す。

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

- [ ]全public session close semanticsを統一する。
- [ ] closeをidempotentにする。
- [ ] active turn closeをterminalへ収束させる。
- [ ] stage cleanup timeoutを実装する。
- [ ] callback/event hubをcloseする。
- [ ] provider/client/bridge cleanup resultをdiagnosticsへ記録する。
- [ ] close後operationをtyped rejectionにする。

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

- [ ] session snapshotを追加する。
- [ ] current phaseを追加する。
- [ ] active turn/generationを追加する。
- [ ] queue depthを追加する。
- [ ] active generation countを追加する。
- [ ] last terminal resultを追加する。
- [ ] last safe error codeを追加する。
- [ ] stale/duplicate/overflow countを追加する。
- [ ] private payload/text/audio/pathを含めない。

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

- [ ] public callback failure policyを定義する。
- [ ] plugin hook failure policyを定義する。
- [ ] motion hook failure policyを定義する。
- [ ] critical/non-critical stage failureを区別する。
- [ ] callback reentrancyを検証する。
- [ ] event callbackがsession lockを保持したまま呼ばれない設計にする。

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

- [ ] TextChatSession compatibility adapterを完成する。
- [ ] VoiceInputSession compatibility adapterを完成する。
- [ ] VoiceOutputSession compatibility adapterを完成する。
- [ ] MotionSession compatibility adapterを完成する。
- [ ] RealtimeSession v5 skeleton behaviorのcompatibility modeを決める。
- [ ] deprecated fields/methodsのwarning policyを決める。

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

- [ ] v6 root-public inventoryを固定する。
- [ ] provider-specific classesのroot exportを再評価する。
- [ ] stable optional provider namespaceを設ける場合はdocumentする。
- [ ] wildcard export ordering依存をなくす。
- [ ] exact public API manifestを生成する。
- [ ] docs/examples/`__all__`の差分gateを追加する。

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

- [ ] v5 standalone sessionからv6 unified sessionへのmigrationを記載する。
- [ ] text-only exampleを追加する。
- [ ] host-captured audio exampleを追加する。
- [ ] interrupt/partial completion exampleを追加する。
- [ ] local playback boundary exampleを追加する。
- [ ] motion extension hook exampleを追加する。
- [ ] unavailable capability fallback exampleを追加する。
- [ ] examplesがprovider credentialなしでimport可能であることを確認する。

---

## FW-RT6-12a — P1 public audio chunk streaming

**Authorization:** P0進捗後に別途判断。

**Tasks:**

- [ ] audio chunk typeを定義する。
- [ ] chunk sequenceを定義する。
- [ ] accepted format/max chunk/max durationをcapability化する。
- [ ] end-of-inputを定義する。
- [ ] input abortを定義する。
- [ ] partial transcript eventを実装する。
- [ ] malformed/out-of-order chunkをtyped rejectする。

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
