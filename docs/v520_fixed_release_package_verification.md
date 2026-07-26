# v5.2.0 Fixed Release Package Verification

This checkpoint adds verification for the fixed FW v5.2.0 release package.

It verifies that a built package is deterministic, release-safe, and internally
consistent before tag readiness.

## Script

```text
scripts/verify_v520_release_package.py
```

Default input:

```text
release/ai-character-framework_v5.2.0.zip
release/ai-character-framework_v5.2.0.sha256.txt
```

## Verification behavior

The verifier checks:

- package filename is `ai-character-framework_v5.2.0.zip`;
- SHA-256 sidecar exists and matches the package;
- source zip entries are sorted and unique, with the generated release manifest appended last;
- zip timestamps are normalized;
- unsafe paths are absent;
- `.git`, virtual environments, caches, release output, patch scripts, `.env*`,
  credentials, nested zip files, `.pyc`, and operator evidence are absent;
- `RELEASE_MANIFEST_v5.2.0.json` exists;
- manifest metadata matches v5.2.0;
- manifest file order matches zip order;
- manifest byte counts and SHA-256 values match package contents;
- required public runtime contract files are included.

## Smoke test

```text
scripts/smoke_v520_fixed_release_package_verification.py
```

The smoke test builds a temporary local verification package under
`.release_build/v5.2.0_verification_smoke/` using the builder with local
`--allow-dirty --skip-checks`, then verifies it with
`verify_v520_release_package.py`.

This is only for validating the verification workflow while the checkpoint is
uncommitted.

## Actual release verification command

After the release package is built from a clean committed tree:

```powershell
python scripts/verify_v520_release_package.py
```

## Current release status

This checkpoint only adds package verification.

It does not create the final release package, create a tag, push a tag, or
publish a release.
