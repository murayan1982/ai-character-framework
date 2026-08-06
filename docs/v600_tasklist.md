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

- [ ] turn terminal registryを追加する。
- [ ] first terminal commitをatomicにする。
- [ ] duplicate terminalを抑止する。
- [ ] late non-terminal eventを拒否する。
- [ ] terminal reason/resultを保持する。
- [ ] stale/duplicate diagnostic counterを追加する。
- [ ] multi-thread race testを追加する。

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

---

## FW-RT6-2d — Generation gate / stale guard

**Purpose:** VTSで実証済みのgeneration-based late suppressionをruntime共通primitiveにする。

**Tasks:**

- [ ] current generation registryを追加する。
- [ ] new turn/interrupt/reset/close時のincrement ruleを固定する。
- [ ] stage completion envelopeへgenerationを付与する。
- [ ] stale completion判定を一箇所に集約する。
- [ ] VTS transportの既存late suppressionと整合させる。
- [ ] stale drop reasonをtyped diagnosticにする。

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

---

## FW-RT6-3a — Stage protocols

**Purpose:** legacy runtime実装をRealtimeSessionへ接続可能なprovider-neutral stageへ分解する。

**Tasks:**

- [ ] `VoiceInputStage` protocolを定義する。
- [ ] `TextGenerationStage` protocolを定義する。
- [ ] `VoiceOutputStage` protocolを定義する。
- [ ] `MotionStage` protocolを定義する。
- [ ] preflight/capability/start/cancel/close contractを統一する。
- [ ] stage result envelopeへcontextを追加する。
- [ ] provider-specific objectsをpublic protocolから除外する。

**Acceptance:**

```text
stage injection:
provider-neutral

fake stage injection:
PASS

provider SDK root import:
False
```

---

## FW-RT6-3b — Deterministic fake runtime controller

**Purpose:** real providerなしでraceとlate resultを再現する。

**Tasks:**

- [ ] fake clock/schedulerを追加する。
- [ ] stage pause/resumeを追加する。
- [ ] artificial delayを追加する。
- [ ] late completion injectionを追加する。
- [ ] duplicate terminal injectionを追加する。
- [ ] cancellation timeout injectionを追加する。
- [ ] queue overflow injectionを追加する。
- [ ] deterministic event trace assertion helperを追加する。

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

---

## FW-RT6-3c — Normal unit-test layer

**Purpose:**release smokeとは別に高速なruntime unit testsを確立する。

**Tasks:**

- [ ] `tests/`へunit test構成を追加する。
- [ ] test runnerを選定する。
- [ ] identity/model testsを追加する。
- [ ] transition testsを追加する。
- [ ] terminal registry testsを追加する。
- [ ] generation/stale testsを追加する。
- [ ] subscriber testsを追加する。
- [ ] fake runtime testsを追加する。
- [ ] smoke scriptはaggregate/release gateとして維持する。

**Acceptance:**

```text
tests directory non-empty:
True

unit tests network-free:
True

full unit suite:
PASS
```

---

## FW-RT6-4a — RealtimeSession construction and config

**Purpose:** unified runtimeのcomposition rootを実装する。

**Tasks:**

- [ ] provider-neutral `RealtimeSessionConfig`を定義する。
- [ ] stage factory/injection pointsを定義する。
- [ ] capability snapshotをsession construction時に固定する。
- [ ] session IDを生成する。
- [ ] subscriber hub/terminal registry/generation gateを所有する。
- [ ] real runtimeはdefault-offにする。
- [ ] configuration不足をtyped resultにする。

**Acceptance:**

```text
mock session creation:
PASS

real provider execution at construction:
False

capability snapshot available:
True
```

---

## FW-RT6-4b — Single-active-turn lifecycle

**Purpose:**turn開始、拒否、完了、失敗を統一する。

**Tasks:**

- [ ] explicit turn start APIを追加する。
- [ ] active turn contextを追加する。
- [ ] active中new turnをtyped rejectionする。
- [ ] turn phase transitionを検証する。
- [ ] normal completionをterminal registryへcommitする。
- [ ] resultへsession/turn/generationを含める。
- [ ] completion後sessionをidle/reusableへ戻す。

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

- [ ] async-first internal runtimeかsync-first runtimeかをexact reviewで決定する。
- [ ] host event loop上で安全なpublic APIを定義する。
- [ ] blocking compatibility wrapperの範囲を決める。
- [ ] callback thread/context guaranteeを文書化する。
- [ ] cancel/closeのthread safetyを定義する。
- [ ] deadlock/reentrancy testsを追加する。

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

---

## FW-RT6-5a — Cancelable text-generation protocol

**Purpose:** `BaseLLM.ask_stream()` generatorからcancel-aware stageへ移行する。

**Tasks:**

- [ ] stream handle/protocolを定義する。
- [ ] cooperative cancellation tokenを追加する。
- [ ] stream close/dispose contractを追加する。
- [ ] response delta envelopeへturn/generationを付与する。
- [ ] completion/interrupt時のconversation history commit ruleを固定する。
- [ ] provider hard-cancel capabilityを報告する。

**Acceptance:**

```text
stop future deltas:
PASS

stream resource cleanup:
PASS

interrupted partial output committed as complete:
False
```

---

## FW-RT6-5b — LLM provider adapters

**Tasks:**

- [ ] OpenAI adapterをcancel-aware protocolへ接続する。
- [ ] Gemini adapterを接続する。
- [ ] xAI adapterを接続する。
- [ ] fallback adapterへcancelを伝播する。
- [ ] router adapterへcancelを伝播する。
- [ ] provider exceptionをsafe classificationへ変換する。
- [ ] provider hard cancel未対応をtruthfulに返す。

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

---

## FW-RT6-5c — TextChatSession compatibility adapter

**Purpose:**既存v4/v5 public APIをv6 runtime primitiveへ接続する。

**Tasks:**

- [ ] `TextChatSession`へsession IDを付与する。
- [ ] ask/ask_streamをturn contextへ関連付ける。
- [ ] interruptをv6 control resultへbridgeする。
- [ ] old boolean return compatibilityを維持する方法を決める。
- [ ] raw exception eventを削除する。
- [ ] v4/v5 event adapterを追加する。

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

- [ ] provider-neutral synthesis work IDを追加する。
- [ ] synthesis start/result/cancel protocolを定義する。
- [ ] generation capabilityを定義する。
- [ ] provider adapterをprotocolへ接続する。
- [ ] active generation stateを観測可能にする。
- [ ] provider hard cancel capabilityをtruthfulにする。

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

- [ ] FW-owned `VoiceArtifactStore` protocolを定義する。
- [ ] opaque artifact IDを発行する。
- [ ] internal pathとpublic refを分離する。
- [ ] resolve/open/delete/expire contractを定義する。
- [ ] URL handoffとartifact refを排他的にする。
- [ ] real provider adapterの`str(artifact_path)`返却を廃止する。
- [ ] lifecycle generationとartifact validityを関連付ける。

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

- [ ] pending synthesis queueを実装する。
- [ ] bounded depthを設定可能にする。
- [ ] queue itemへsession/turn/generation/work IDを付与する。
- [ ] enqueue accepted/rejected resultをtypedにする。
- [ ] pending clearを実装する。
- [ ] active generationとpending queueを別状態にする。
- [ ] overflow eventを追加する。

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

- [ ] active synthesis cooperative cancelを実装する。
- [ ] provider cancel timeoutを実装する。
- [ ] provider hard cancel resultを記録する。
- [ ] completed artifact invalidationを実装する。
- [ ] future delivery suppressionを実装する。
- [ ] late artifactをstale guardで拒否する。
- [ ] duplicate flush/cancelをidempotentにする。

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

- [ ] FW-owned playbackとhost-owned playbackをcapabilityで分離する。
- [ ] `playback_stop_requested_to_host` eventを定義する。
- [ ] host acknowledgementを任意contractとして定義する。
- [ ] host停止未確認をFW停止成功と表現しない。
- [ ] legacy `VoiceEngine`/ffplay pathをinternal compatibilityへ隔離する。
- [ ] legacy local playerのdeprecation方針を決める。

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

- [ ] `VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED`の現状を再評価する。
- [ ] OpenAI real executor availabilityをcapabilityへ反映する。
- [ ] `VoiceInputSessionInfo.api_version`を中央versionへ接続する。
- [ ] session ID/turn/generationを追加する。
- [ ] typed lifecycle eventへ移行する。
- [ ] default fake/real factory selectionをprovider-neutralにする。

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
