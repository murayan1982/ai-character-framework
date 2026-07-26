# v5.2.0 Fixed Release Package Builder

This checkpoint adds the fixed release package builder for FW v5.2.0.

The builder prepares the final source release artifact after the source-tree
release readiness gate passes.

## Script

```text
scripts/build_v520_release_package.py
```

Default output:

```text
release/ai-character-framework_v5.2.0.zip
release/ai-character-framework_v5.2.0.sha256.txt
```

## Builder behavior

The builder:

- requires a clean git working tree by default;
- runs `scripts/smoke_v520_release_readiness_gate.py` by default;
- collects release-safe source files;
- excludes `.git`, virtual environments, caches, build output, release output,
  temporary patch scripts, logs, zip files, `.env*`, credentials, and operator
  evidence;
- writes a deterministic zip with sorted files, normalized timestamps, and
  normalized permissions;
- embeds `RELEASE_MANIFEST_v5.2.0.json`;
- writes a SHA-256 sidecar file.

## Dry run

For local validation while this checkpoint is still uncommitted:

```powershell
python scripts/build_v520_release_package.py --dry-run --allow-dirty --skip-checks
```

The actual release package should be built after committing this checkpoint,
without `--allow-dirty` and without `--skip-checks`.

## Actual release package command

```powershell
python scripts/build_v520_release_package.py
```

This should only be run from a clean committed tree.

## Current release status

This checkpoint only adds the builder.

It does not create the final fixed release package, verify the package, create a
tag, push a tag, or publish a release.
