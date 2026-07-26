# FW v5.1.0 Commit 5 - Result / error contract checkpoint

Purpose: add a v5.1.0 P0/FW-F3 checkpoint for typed public results and provider-neutral public error codes.

## Files

```text
docs/v510_result_error_contract.md
scripts/smoke_v510_result_error_contract.py
```

## Verification

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/smoke_v510_factory_signature_contract.py
python scripts/smoke_v510_result_error_contract.py
python scripts/check_release_package.py
```

Expected behavior:

```text
[OK] v5.1.0 result/error contract checkpoint is mock-safe
```

A warning that `TextChatResult` is not public yet is expected at this checkpoint.
This commit records FW-F3 vocabulary and checks the existing Voice Output result
contract before changing text chat runtime behavior.

## Commit message

```text
docs/test: add result and error contract for v5.1.0
```

## Notes

- No text chat runtime behavior is changed.
- No DRC files are changed.
- No provider execution is performed.
- The smoke is mock-safe.
