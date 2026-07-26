# v5.1.0 Final Release Tag Readiness

This document defines the final pre-tag readiness checkpoint for
AI-Character-Framework v5.1.0.

The v5.1.0 release is not considered tag-ready unless the following are
true:

- the v5.1.0 release readiness gate passes;
- the fixed release package builder produces local release artifacts;
- the fixed release package verification passes against the generated ZIP;
- the generated ZIP imports and exercises the public API from outside the
  repository root;
- local-only artifacts and private secrets are excluded from the release
  package;
- `.env.example` remains included as the public environment template;
- `scripts/check_release_package.py` passes;
- the working tree is clean before the release tag is created;
- the `v5.1.0` tag does not already exist before tagging.

## Commands

Before committing this checkpoint, run the mock-safe command:

```powershell
python scripts/smoke_v510_final_release_tag_readiness.py
```

After this checkpoint is committed, run the strict pre-tag command from a
clean working tree:

```powershell
python scripts/smoke_v510_final_release_tag_readiness.py --require-clean-tree --expected-tag v5.1.0
```

Then create the tag only if the strict pre-tag command passes:

```powershell
git tag v5.1.0
git push origin v5.1.0
```

## Scope

This is a final release-readiness checkpoint only. It must not:

- call real provider APIs;
- require `.env` or private provider credentials;
- commit generated release ZIPs or release manifests;
- create or push Git tags.

The generated `release/ai-character-framework_v5.1.0.zip` and
`release/ai-character-framework_v5.1.0_manifest.json` are local release
artifacts/evidence unless explicitly attached to a release outside Git.
