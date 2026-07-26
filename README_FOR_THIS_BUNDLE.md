# FW v5.1.0 Commit 15 - Fixed Release Package Builder

## Apply

```powershell
python apply_v510_commit15_fixed_release_package_builder.py
del apply_v510_commit15_fixed_release_package_builder.py
```

## Verify

```powershell
python scripts/smoke_v510_release_readiness_gate.py
python scripts/build_v510_fixed_release_package.py
```

The builder writes `release/ai-character-framework_v5.1.0.zip` and
`release/ai-character-framework_v5.1.0_manifest.json`.

## Commit

```bash
git add docs/v510_fixed_release_package.md docs/v510_host_app_sdk_readiness_notes.md scripts/build_v510_fixed_release_package.py
git commit -m "docs/test: add fixed release package builder for v5.1.0"
```

Do not add the generated `release/*.zip` or manifest unless you intentionally
want release evidence tracked in git.
