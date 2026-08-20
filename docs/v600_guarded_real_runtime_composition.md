# v6.0.0 guarded real-runtime composition

<!-- FW-RT6-13b-GUARDED-REAL-RUNTIME:BEGIN -->
## FW-RT6-13b final acceptance-sync candidate

FW-RT6-13b adds one explicit-only, provider-neutral composition boundary at
`framework.guarded_real_runtime`. It accepts four host-owned zero-argument
stage factories for real STT, streaming LLM, TTS, and VTube Studio motion. The
module itself contains no provider SDK import and reads no environment variable,
credential, private file, endpoint, model selector, motion selector, or operator
evidence.

Composition requires both of these exact booleans:

```text
real_runtime_enabled: True
allow_provider_execution: True
```

If either opt-in is false, no stage factory is called and every stage result is
`blocked`. If a required factory is missing, composition fails closed before
calling any supplied factory. Only after both opt-ins and complete configuration
are present may the four host-owned factories be called in canonical order:

```text
voice_input
text_generation
voice_output
motion
```

Each constructed object must satisfy its existing provider-neutral stage
protocol, report the exact matching `RealtimeStageKind`, and return the expected
capability from `preflight()`. A ready capability must report a usable real
runtime. Voice input additionally requires final-transcript support, text
generation requires streaming support, and motion requires provider-neutral
intent support. Voice output requires a usable real voice-output capability.

The aggregate result contains one ordered public-safe result for every stage.
It reports only factory/preflight/capability reach booleans, a fixed outcome,
fixed safe text, retryability, and count-only metadata. It never includes a
factory, provider object, capability object, raw exception, credential, private
path, provider payload, model identity, endpoint, hotkey, or selector.

A failed aggregate closes all constructed stages exactly once on a best-effort
basis; cleanup exceptions are reduced to a count. A ready aggregate transfers
the four stages through a representation-hidden `RealtimeSessionConfig`. The
host/session that adopts that config owns subsequent close. `runtime_ready`
means the four-stage composition and preflight handoff is ready; it does not
claim that a provider request, microphone read, playback action, or VTS motion
was executed during composition.

Actual provider imports, client construction, network/device access, provider
requests, and operator evidence remain entirely inside host-owned factories and
stages after double opt-in. FW-RT6-13c separately owns real operator execution
and evidence. Its private values and artifacts must not be added to the source
tree, test output, committed docs, public metadata, results, or exceptions.

```text
checkpoint: FW-RT6-13b
baseline head: 1a1e9ab676caa606ba6bd2741f8c3b9ca1700e0c
status: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH
exact implementation surface: 7 files
exact acceptance-sync surface: 5 files
stable namespace: framework.guarded_real_runtime / EXPLICIT_ONLY
real stages: 4 / STT + STREAMING_LLM + TTS + VTS_MOTION
explicit double opt-in: REQUIRED
factory calls before double opt-in: 0
provider SDK lazy import: PRESERVED
real-run preflight: STAGE_OWNED / AFTER_DOUBLE_OPT_IN
safe failure normalization: FIXED_PROVIDER_NEUTRAL_RESULTS
private configuration/evidence commit: FORBIDDEN
stage capability/reach results: 4 / ORDERED / PUBLIC_SAFE
root-public names: 127 / UNCHANGED
RealtimeSession turn orchestration changed: False
provider/network/microphone/playback/VTS execution in tests: False
dedicated guarded-composition tests: 10 / PASS
related stage/session/integrated/root-public tests: 122 / PASS
full Framework unit suite: 801 / PASS
FW-RT6-13b tasklist state: 10 / 10 ACCEPTED
FW-RT6-13c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
FW-RT6-13c implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-13b-GUARDED-REAL-RUNTIME:END -->


<!-- FW-RT6-13c-REAL-RUNTIME-OPERATOR:BEGIN -->
## FW-RT6-13c operator-tooling relationship

The 13b composition contract remains unchanged. FW-RT6-13c does not add real
execution to `compose_guarded_real_runtime()` or `RealtimeSession`. Instead, an
operator-only script owns the explicit sequence across existing real stage
implementations after it verifies a committed/pushed clean `main`, exact
provider versions, private material outside the repository, and separate real
execution/privacy confirmations.

The real LLM cancellation boundary remains cooperative: future deltas are
suppressed and provider hard cancel remains unclaimed. TTS late-artifact
admission is retired through the accepted generation gate and its private
artifact is invalidated. Host playback stop remains an external observation;
Framework never claims a physical device stop. VTS motion retains the accepted
local-loopback, private-token, configured-binding, and visual-confirmation
requirements from v5.5.

```text
checkpoint: FW-RT6-13c / TOOLING_ONLY
baseline head: cf660a0c4eb4373f21dfdd779a5f98b64457d791
status: IMPLEMENTED / VERIFIED / AWAITING_REVIEW
13b composition source changed: False
RealtimeSession turn orchestration changed: False
production Framework source changes: 0
provider-free dedicated tests: 15 / PASS
related stage/session/provider-neutral tests: 200 / PASS
full Framework unit suite: 816 / PASS
canonical operator scenarios closed: 0 / 9
real provider/network/microphone/playback/VTS execution: NOT_AUTHORIZED
private evidence read/validated: False
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-13c-REAL-RUNTIME-OPERATOR:END -->
