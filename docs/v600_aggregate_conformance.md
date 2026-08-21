<!-- FW-RT6-14a-AGGREGATE-CONFORMANCE:BEGIN -->
# FW-RT6-14a aggregate conformance gate

FW-RT6-14a adds one deterministic, provider-free release-readiness gate over
the already accepted v6 contracts. It does not add runtime behavior. The
separately authorized final acceptance sync records the reviewed implementation
and closes the twelve canonical conformance tasks.

## Frozen candidate boundary

```text
checkpoint: FW-RT6-14a
baseline head: 8f0be2cdcdf92d039c2d957f6d1eaf90e7388298
baseline subject: docs: close FW-RT6-13c
implementation commit: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741
implementation subject: test: add FW-RT6-14a aggregate conformance gate
status: COMPLETED / VERIFIED / COMMITTED / PUSHED / REMOTELY_VERIFIED
exact implementation surface: 6 files
production Framework source changes: 0 files
root-public names: 127 / UNCHANGED
root-public manifest changed: False
factory signature changes: 0
event/result/error shape changes: 0
API/schema version changes: 0
dependency/packaging changes: 0
README changes: 0
real operator/private evidence changes: 0
dedicated aggregate tests: 12 / PASS
full Framework unit suite: 828 / PASS
current-compatible smoke dependencies: 11 / PASS
tracked smoke_v600 files: 93 / CLASSIFIED
historical smoke_v600 files: 91 / SOURCE_EVIDENCE_ONLY
provider/network/microphone/playback/VTS execution: False
private configuration/evidence read or written: False
FW-RT6-14a canonical tasks: 12 / 12 ACCEPTED
FW-RT6-14b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
FW-RT6-14b implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The exact implementation surface is:

- `docs/app_integration_contract.md`
- `docs/public_facade.md`
- `docs/v600_aggregate_conformance.md`
- `docs/v600_tasklist.md`
- `scripts/check_v600_aggregate_conformance.py`
- `tests/test_aggregate_conformance.py`

No file under `framework/` changes. The existing root-public manifest file is
also unchanged; the gate freezes both its byte SHA-256 and its embedded
order-independent 127-name SHA-256.

## Twelve one-to-one gates

`tests/test_aggregate_conformance.py` contains exactly twelve tests, in the
same order as the canonical checklist:

1. root-public manifest: exact file digest, 127 names, source projection, and
   canonical name-set digest;
2. import safety: isolated root, guarded-composition, and aggregate-gate import
   without optional providers or device runtimes;
3. capability truthfulness: mock/default/unsupported/experimental state remains
   explicit and provider execution remains false;
4. event ordering: exact normal-turn type order, monotonic sequence, and stable
   turn/generation correlation;
5. exactly-once terminal: first-terminal ownership and duplicate suppression;
6. stale rejection: retired-generation completion rejection without delivery;
7. interrupt reach: all five provider-neutral subsystem targets and truthful
   unsupported/hard-cancel facts;
8. TTS work-control: bounded admission, overflow, pending clear, and separation
   from active-generation cancellation;
9. security/redaction: recursive credential, private-path, binary, and exception
   redaction without representation leakage;
10. compatibility: five stable profiles, silent warnings, preserved factories,
    and no compatibility-profile execution;
11. full unit suite: exact `test*.py` discovery and 828-test result;
12. full smoke suite: exact current-compatible dependency inventory and complete
    historical classification.

## Current smoke definition

The repository contains 93 tracked `scripts/smoke_v600_*.py` files. Many are
append-only historical acceptance artifacts that deliberately freeze an older
HEAD, file surface, checklist state, or test count. Running every historical
artifact against the current checkout would test those obsolete snapshots,
not current v6 conformance.

For FW-RT6-14a, `full smoke suite` therefore means the following exact eleven
current-compatible, offline/provider-free dependencies:

```text
scripts/smoke_v600_public_api_manifest.py
scripts/smoke_v600_version_metadata.py
scripts/check_v600_root_public_api_cleanup_acceptance.py --source-only
scripts/check_v600_guarded_real_runtime_composition.py --source-only
scripts/check_v600_integrated_fake_runtime_acceptance.py
scripts/check_v600_interrupt_ordering_acceptance.py --source-only
scripts/check_v600_end_to_end_stale_acceptance.py --source-only
scripts/check_v600_interrupt_coordination_acceptance.py --source-only
scripts/check_v600_voice_output_queue_acceptance.py --source-only
scripts/check_v600_session_compatibility_acceptance.py --source-only
scripts/check_v600_real_runtime_operator_acceptance.py --source-only
```

The two standalone current smoke files plus 91 historical `smoke_v600` files
account for the full tracked inventory. The nine current high-level checkers
are additional dependency gates and are not counted among those 93 filenames.
Every subprocess runs with credential-like environment variables removed and
all real-provider/device execution guards forced off. Output is captured and
only fixed public-safe pass/fail markers are emitted.

## Final acceptance sync

```text
acceptance-sync baseline head: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741
implementation commit: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741
implementation: COMPLETED / VERIFIED / COMMITTED / PUSHED / REMOTELY_VERIFIED
final acceptance-sync exact surface: 5 files
final acceptance-sync production Framework source changes: 0 files
final acceptance-sync dedicated test changes: 0 files
dedicated aggregate tests: 12 / PASS
full Framework unit suite: 828 / PASS
current-compatible smoke dependencies: 11 / PASS
tracked smoke_v600 files: 93 / CLASSIFIED
historical smoke_v600 files: 91 / SOURCE_EVIDENCE_ONLY
provider/network/microphone/playback/VTS execution: False
private configuration/evidence read or written: False
FW-RT6-14a tasks: 12 / 12 ACCEPTED
FW-RT6-14a final acceptance sync: PASS
FW-RT6-14a: COMPLETED / VERIFIED / ACCEPTED / CLOSED_AFTER_SYNC_COMMIT_PUSH
FW-RT6-14b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH
FW-RT6-14b implementation: NOT_AUTHORIZED
acceptance-sync commit / push: NOT_AUTHORIZED
```

The sync changes only the three conformance documents, the tasklist state, and
the aggregate checker. It does not change the twelve-test suite or production
Framework source. It records no private evidence and performs no real runtime
or provider/device action.

## Invocation and non-actions

From the repository root:

```powershell
python .\scripts\check_v600_aggregate_conformance.py
```

`--source-only` skips only the Git branch/HEAD/dirty-surface check; it retains
the contract checks, twelve dedicated tests, eleven current smoke dependencies,
and all 828 unit tests.

This gate does not install dependencies, read `.env`, access private operator
state, repeat the real FW-RT6-13c run, read its evidence, contact a provider,
capture audio, perform playback, or connect to VTube Studio. It does not stage,
commit, push, tag, build a package, or publish a release. FW-RT6-14b exact
contract review is authorized only after this sync commit is pushed and
remotely verified; FW-RT6-14b implementation remains separately gated.
<!-- FW-RT6-14a-AGGREGATE-CONFORMANCE:END -->
