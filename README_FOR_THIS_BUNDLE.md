# FW v5.1.0 Commit 4 - Public factory signature contract

Purpose: add a v5.1.0 P0/FW-F2 checkpoint for stable public factory signatures.

## Files

```text
docs/v510_public_factory_signature_contract.md
scripts/smoke_v510_factory_signature_contract.py
```

## Verification

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/smoke_v510_factory_signature_contract.py
python scripts/check_release_package.py
```

Expected behavior:

```text
[OK] v5.1.0 public factory signature contract is mock-safe
```

A warning for `create_text_chat_session` not being keyword-only yet is expected
at this checkpoint. The warning records the current transition baseline; later
FW-F2 work can convert that to a stricter conformance requirement if desired.

## Commit message

```text
docs/test: add public factory signature contract for v5.1.0
```

## Notes

- No runtime behavior is changed.
- No DRC files are changed.
- No provider execution is performed.
- The smoke is mock-safe.
