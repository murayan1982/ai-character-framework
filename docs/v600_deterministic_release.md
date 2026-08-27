# FW-RT6-14c Deterministic Package and Release Contract

## Candidate status

```text
checkpoint: FW-RT6-14c
baseline head: 799589526aef1a9d903fe4da4c23550b5c12ca38
exact contract review: COMPLETED
implementation: IMPLEMENTED / VERIFIED / AWAITING_REVIEW
exact implementation surface: 18 files
source version metadata: 6.0.0
latest published release: 5.5.0 / UNCHANGED
runtime behavior changes: 0
root-public names: 127 / UNCHANGED
FW-RT6-14c canonical tasks: 0 / 14 CLOSED / UNCHANGED
tag / push / GitHub Release: NOT_AUTHORIZED
official ZIP + SHA-256 sidecar: NOT_AUTHORIZED / NOT_WRITTEN
```

Changing source metadata to `6.0.0` makes the later official ZIP identical to
the release commit. It does not claim publication: `LATEST_PUBLISHED_RELEASE`
remains `5.5.0` until the public GitHub Release has been independently verified.

## Exact eighteen-file implementation surface

1. `README.md`
2. `docs/RELEASE_NOTES.md`
3. `docs/advanced_runtime.md`
4. `docs/app_integration_contract.md`
5. `docs/public_facade.md`
6. `docs/release_notes_v6.0.0.md`
7. `docs/release_package_policy.md`
8. `docs/v600_capability_event_error_reference.md`
9. `docs/v600_deterministic_release.md`
10. `docs/v600_tasklist.md`
11. `docs/v600_v5_to_v6_session_migration.md`
12. `framework/version.py`
13. `scripts/build_v600_release_package.py`
14. `scripts/check_v600_documentation_freeze.py`
15. `scripts/check_v600_release_readiness.py`
16. `scripts/operator_v600_github_release.py`
17. `scripts/check_v600_release_package_smoke.py`
18. `scripts/smoke_v600_version_metadata.py`

No session, event, result, error, provider, adapter, playback, motion, or root
facade implementation changes.

## Provider-free implementation verification

```powershell
python scripts\check_v600_release_readiness.py
```

This exact candidate mode verifies Git surface, release docs, builder/operator
source safety, two byte-identical temporary rebuilds, exact membership, ZIP
integrity, duplicate entry rejection, private artifact rejection, unsafe member
rejection, SHA-256 sidecar, isolated package-import smoke, the accepted 14b
documentation gate, and the 14a aggregate gate. It writes no official artifact.

## Strict tag readiness

After the implementation and a separately reviewed release-status sync are
committed and pushed, build from the clean commit and run:

```powershell
python scripts\build_v600_release_package.py
python scripts\check_v600_release_readiness.py --strict-release
```

Strict mode requires clean `main`, `HEAD == origin/main`, absent local tag,
exact committed membership, the official ZIP/sidecar, and a byte-identical
temporary rebuild.

## Explicit public-release operator

Planning is read-only:

```powershell
python scripts\operator_v600_github_release.py --plan
```

`--execute` additionally requires these exact separate confirmations:

```text
I_AUTHORIZE_CREATE_AND_PUSH_V600_ANNOTATED_TAG
I_AUTHORIZE_PUBLIC_GITHUB_RELEASE_AND_ASSET_UPLOAD
I_ACCEPT_PUBLIC_RELEASE_ACTIONS_ARE_IRREVERSIBLE
```

Only then may the operator create the annotated `v6.0.0` tag, push the tag,
create the public GitHub Release, upload the official ZIP and SHA-256 sidecar,
redownload both assets, verify their bytes, and confirm a clean working tree.

## Acceptance boundary

The implementation candidate proves that all fourteen controls exist. It does
not close any canonical task. Annotated tag creation, push, GitHub Release,
official asset publication, redownload verification, and final clean-tree
acceptance require separate review and explicit execution authorization.

<!-- FW-RT6-14c-RELEASE-STATUS-SYNC:BEGIN -->
## Release-status acceptance sync

```text
sync baseline: 9ffa623d21e6096213c9beb504f4c06150aeba8f
implementation commit: 9ffa623d21e6096213c9beb504f4c06150aeba8f
implementation: COMMITTED / PUSHED / REMOTELY_VERIFIED
release-status sync exact surface: 7 files
v6 package builder: ACCEPTED
exact committed membership: ACCEPTED
deterministic rebuild: ACCEPTED
duplicate entry rejection: ACCEPTED
private artifact rejection: ACCEPTED
package-import smoke: ACCEPTED
release notes: ACCEPTED
strict tag readiness: NOT_RUN / OPEN
annotated tag: NOT_RUN / OPEN
tag push: NOT_RUN / OPEN
GitHub Release: NOT_RUN / OPEN
official ZIP + SHA-256 sidecar: NOT_WRITTEN / OPEN
published asset redownload verification: NOT_RUN / OPEN
final clean tree confirmation: NOT_RUN / OPEN
FW-RT6-14c canonical tasks: 7 / 14 ACCEPTED
tag / push / GitHub Release: NOT_AUTHORIZED
sync commit / push: NOT_AUTHORIZED
```

This provider-free sync records reviewed results only. It does not create the
official package or execute strict/public-release operations. After this exact
sync is committed, pushed, and remotely verified, official package creation and
strict tag readiness may be separately authorized from that clean commit.
<!-- FW-RT6-14c-RELEASE-STATUS-SYNC:END -->

<!-- FW-RT6-14c-PRE-TAG-READINESS:BEGIN -->
## Pre-tag readiness checkpoint

```text
pre-tag baseline: 6d83dac01ff406b258e611447ade4c03191b7c95
implementation commit: 9ffa623d21e6096213c9beb504f4c06150aeba8f / REMOTELY_VERIFIED
release-status sync commit: 6d83dac01ff406b258e611447ade4c03191b7c95 / REMOTELY_VERIFIED
pre-tag exact surface: 7 files
production Framework behavior changes: 0
source version metadata: 6.0.0
latest published release: 5.5.0 / UNCHANGED
root-public names: 127 / UNCHANGED
FW-RT6-14c canonical tasks: 7 / 14 ACCEPTED
pre-tag readiness: READY_FOR_OFFICIAL_PACKAGE_BUILD_AND_STRICT_CHECK
strict tag readiness: NOT_RUN / OPEN
official ZIP + SHA-256 sidecar: NOT_WRITTEN / OPEN
annotated tag / push / GitHub Release: NOT_AUTHORIZED / NOT_RUN
published asset redownload verification: NOT_RUN / OPEN
final clean tree confirmation: NOT_RUN / OPEN
```

This exact checkpoint removes the obsolete awaiting-sync state from the source
that will be packaged. It does not create release assets or accept any of the
remaining seven canonical tasks. Official package generation and strict
readiness are the next separate execution boundary; public release operations
remain separately authorized.
<!-- FW-RT6-14c-PRE-TAG-READINESS:END -->

<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:BEGIN -->
## Final published-release acceptance sync

```text
final-sync baseline: 61e15f62d1ecc5faee016abae82200f8de56c5dd
release commit: 61e15f62d1ecc5faee016abae82200f8de56c5dd / REMOTELY_VERIFIED
release tag: v6.0.0 / ANNOTATED / PUSHED / VERIFIED
strict tag readiness: PASS
GitHub Release: PUBLIC / VERIFIED
official asset membership: 2 / EXACT
official ZIP: ai-character-framework_v6.0.0.zip
official sidecar: ai-character-framework_v6.0.0.zip.sha256
official ZIP SHA-256: 6b303dba53830dc9bd65ec881bac6f498dbf80f0d0adf1385cea728a86e066f2
published asset redownload: VERIFIED
final clean tree confirmation: VERIFIED
source version metadata: 6.0.0
latest published release: 6.0.0
root-public names: 127 / UNCHANGED
production Framework behavior changes: 0
FW-RT6-14c canonical tasks: 14 / 14 ACCEPTED
FW-RT6-14c final acceptance sync: PASS / AWAITING_SYNC_COMMIT_PUSH
final-sync commit / push: NOT_AUTHORIZED
```

The published asset remains the exact package built from the tagged release
commit. This post-release sync records public facts and updates current metadata;
it is not a replacement package and performs no tag, Release, or asset mutation.
<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:END -->
