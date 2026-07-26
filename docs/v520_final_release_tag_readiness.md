# v5.2.0 Final Release Tag Readiness

This checkpoint adds the final tag-readiness gate for FW v5.2.0.

It verifies that the source tree has all v5.2.0 release gates and fixed package
tooling in place before the final release package is built from a clean committed
tree and the `v5.2.0` tag is created.

## Script

```text
scripts/smoke_v520_final_release_tag_readiness.py
```

## Required dependent scripts

The final tag-readiness gate depends on these source-tree gates and package
workflow smokes:

```text
scripts/smoke_v520_release_readiness_gate.py
scripts/smoke_v520_fixed_release_package_builder.py
scripts/smoke_v520_fixed_release_package_verification.py
scripts/build_v520_release_package.py
scripts/verify_v520_release_package.py
```

These names are intentionally written explicitly so the tag-readiness smoke can
verify the release documentation and script contract stay aligned.

## What this gate checks

The gate verifies:

- the v5.2.0 source-tree release readiness gate passes;
- the fixed release package builder smoke passes;
- the fixed release package verification smoke passes;
- package builder and verifier scripts exist;
- README / checklist / readiness notes track final tag readiness;
- `git` is available;
- current HEAD can be resolved;
- the `v5.2.0` tag does not already exist locally unless `--allow-existing-tag`
  is passed;
- the final package can be optionally required and verified with
  `--require-package`.

## Local checkpoint mode

While this checkpoint is still uncommitted, run:

```powershell
python scripts/smoke_v520_final_release_tag_readiness.py --allow-dirty
```

The local checkpoint mode allows the uncommitted files from this checkpoint but
still executes the dependent readiness, builder, and verifier smokes.

## Final release mode

After committing this checkpoint, build and verify the fixed release package from
a clean committed tree:

```powershell
python scripts/build_v520_release_package.py
python scripts/verify_v520_release_package.py
python scripts/smoke_v520_final_release_tag_readiness.py --require-package
```

Only after those pass should the tag be created:

```powershell
git tag v5.2.0
git push origin main
git push origin v5.2.0
```

## Current release status

This checkpoint does not create the release package, tag, push, or publish a
GitHub release.

It only adds the final tag-readiness gate.

## Generated release artifacts

The final release package and SHA-256 sidecar are generated artifacts and should
not be committed to source control.

The repository ignores:

```text
release/*.zip
release/*.sha256.txt
```

This lets the final release flow build and verify:

```text
release/ai-character-framework_v5.2.0.zip
release/ai-character-framework_v5.2.0.sha256.txt
```

while keeping `git status` clean for source-tree tag readiness.
