# v6.0.0 integrated fake-runtime acceptance

<!-- FW-RT6-13a-INTEGRATED-FAKE-RUNTIME:BEGIN -->
## FW-RT6-13a implementation candidate

FW-RT6-13a adds one provider-free integration suite over the accepted session,
generation-gate, terminal-registry, interrupt, recovery, close, and
deterministic fake-runtime boundaries. It is validation-only: production
`RealtimeSession` orchestration, the Framework root API, provider composition,
and host-owned device behavior are unchanged.

The scenario matrix is exact:

| Roadmap scenario | Acceptance observation |
|---|---|
| text-only normal turn | exact nine-event lifecycle and one completed terminal |
| host audio -> transcript -> text -> TTS -> motion | typed fake transcript, mock realtime result, in-memory TTS handoff, mock motion completion |
| user stop during response stream | active fake text stage is cancelled and one interrupted terminal is retained |
| user speech interrupt during voice output | active fake voice-output stage is cancelled and one interrupted terminal is retained |
| duplicate interrupt | later request returns the exact owner result with no repeated cancel/event/terminal |
| late response delta | retired-generation completion is rejected by the accepted generation gate |
| late TTS artifact | retired-generation completion is rejected by the accepted generation gate |
| late motion completion | retired-generation completion is rejected by the accepted generation gate |
| queue overflow | fixed-capacity scheduler raises the typed overflow and retains queued work |
| session reset | the previous generation is retired and its completion is rejected |
| session close during active turn | close retains exactly one correlated closed terminal |
| post-close operation rejection | a new turn returns one typed rejected result without reopening the session |
| exact event trace / terminal result | deterministic trace signature is exact and duplicate terminal attempts retain one record |

`tests/test_integrated_fake_runtime_acceptance.py` owns the executable matrix.
`scripts/check_v600_integrated_fake_runtime_acceptance.py` verifies the document,
task-state, source-safety, test-count, scenario, trace, terminal, and stale gates.
The suite may use in-process test doubles and deterministic scheduler callbacks;
it performs no external or device execution.

```text
checkpoint: FW-RT6-13a
baseline head: 888e17685f71688f038bbed1a113c4b317b057dd
status: IMPLEMENTED / AWAITING_REVIEW
exact implementation surface: 5 files
integrated scenario groups: 10
roadmap scenarios covered: 13 / 13
fake-only integrated suite: PASS_REQUIRED
exactly-once terminal: PASS_REQUIRED
stale rejection: PASS_REQUIRED
network/provider/microphone/playback: False
real VTS execution: False
raw audio retained: False
production Framework source changed: False
RealtimeSession production orchestration changed: False
Framework root exports changed: False
framework root-public names: 127 / UNCHANGED
FW-RT6-13a tasklist state: 0 / 13 CLOSED / UNCHANGED
acceptance sync / commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-13a-INTEGRATED-FAKE-RUNTIME:END -->
