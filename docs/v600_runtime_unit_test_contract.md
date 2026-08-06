# FW-RT6-3c Normal Runtime Unit-Test Contract

This document fixes the Control A contract for establishing a fast,
provider-free unit-test layer under `tests/`. Release and aggregate smoke
scripts remain separate gates.

<!-- FW-RT6-3c-A-UNIT-TEST-FOUNDATION:BEGIN -->
## Control A — unit-test foundation, identity/models, and transitions

### Runner

Control A selects the Python standard-library runner:

```text
runner: unittest
command: python scripts/run_v600_unit_tests.py
discovery root: tests
discovery pattern: test_*.py
external test dependency added: False
```

`unittest` is selected because the Framework currently requires Python 3.10+
and has no test-runner dependency in `pyproject.toml`. The normal unit suite
must run without installing provider extras or a third-party test framework.

### Test placement

Control A creates a normal `tests/` package and adds focused tests for:

```text
identity primitives
identity compatibility normalization
EventSequence
immutable realtime event payload models
public-safe payload validation
lifecycle phase transitions
terminal transition classification
```

The tests import provider-neutral Framework modules only. They do not read
credentials, private configuration, audio, transcripts, screenshots, private
paths, LAN addresses, or operator evidence.

### Separation from smoke gates

Existing `scripts/smoke_*.py` and aggregate acceptance scripts remain
unchanged. They continue to validate public/release contracts. The new
`tests/` suite is a faster implementation-level regression layer and does not
replace those gates.

### Deferred Control B scope

The following tasklist categories remain separately authorized:

```text
terminal registry unit tests: DEFERRED / Control B
generation and stale-completion unit tests: DEFERRED / Control B
subscriber/event-hub unit tests: DEFERRED / Control B
deterministic fake-runtime unit tests: DEFERRED / Control B
full FW-RT6-3c aggregate acceptance: DEFERRED / Control C
```

### Safety and compatibility

```text
production runtime source changed: False
framework root-public names: 121 / UNCHANGED
provider SDK import by unit tests: False
network execution: False
microphone execution: False
playback execution: False
real VTube Studio execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
```

### Control A status

```text
checkpoint: FW-RT6-3c Control A
baseline head: 9fe14cb53a4740fea3f7172af36d7052610b215d
baseline subject: docs/test: accept deterministic fake runtime
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 6 files
tests directory non-empty: True
selected runner: unittest
identity/model tests: 12
transition tests: 7
discovered unit tests: 19
production runtime source changed: False
existing smoke scripts changed: False
Control B: NOT_AUTHORIZED
aggregate acceptance: DEFERRED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3c-A-UNIT-TEST-FOUNDATION:END -->

<!-- FW-RT6-3c-B-RUNTIME-UNIT-TEST-COVERAGE:BEGIN -->
## Control B — runtime ownership, stale-result, subscriber, and fake-runtime tests

Control B extends the accepted standard-library `unittest` layer without
changing production runtime source, the selected runner, or existing
aggregate/release smoke scripts.

### Added normal unit-test categories

```text
terminal registry tests: 5
generation / stale-completion tests: 6
subscriber / event-hub tests: 7
deterministic fake-runtime tests: 8
Control B added tests: 26
Control A retained tests: 19
full discovered unit tests: 45
```

The tests cover the implementation contracts directly:

- first-terminal ownership, duplicate/regression suppression, late
  non-terminal rejection, diagnostics, and record order;
- current completion admission, new-turn and explicit retirement, unknown
  generation, turn mismatch, envelope validation, and immutable diagnostics;
- sequence allocation, subscribe/unsubscribe, legacy projection, callback
  failure isolation, deterministic slow-callback accounting, bounded-history
  overflow, and close rejection;
- integer fake time, insertion ordering, pause/resume, cancellation timeout,
  queue overflow, close behavior, exact trace assertions, retired completion,
  and actual terminal-registry duplicate classification.

### Smoke separation

`scripts/run_v600_unit_tests.py` remains unchanged and discovers all normal
tests under `tests/`. Existing `scripts/smoke_*.py` files remain aggregate,
compatibility, and release gates. Control B adds one implementation-time gate
for its exact candidate and does not replace the accepted smoke layer.

### Safety and compatibility

```text
runner changed: False
external test dependency added: False
production runtime source changed: False
existing smoke scripts changed: False
framework root-public names: 121 / UNCHANGED
provider SDK import by unit tests: False
network execution: False
microphone execution: False
playback execution: False
real VTube Studio execution: False
RealtimeSession orchestration changed: False
event-hub projection into fake trace: DEFERRED
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
```

### Control B status

```text
checkpoint: FW-RT6-3c Control B
baseline head: 98b8c5a77f69705096dee316fe7fee35eca9e3b0
baseline subject: test: add realtime unit test foundation
Control A: COMPLETED / VERIFIED / COMMITTED / PUSHED / ACCEPTED / CLOSED
status: IMPLEMENTED / AWAITING_REVIEW
exact change surface: 6 files
Control B added tests: 26
full discovered unit tests: 45
full unit suite: PASS required
production runtime source changed: False
Control C aggregate acceptance: NOT_AUTHORIZED / DEFERRED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3c-B-RUNTIME-UNIT-TEST-COVERAGE:END -->
