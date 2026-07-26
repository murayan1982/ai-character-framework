# FW v5.1.0 Commit 3 - Voice Output speak contract

Purpose: resolve the known v5.1.0 public contract inventory warning where README used `session.speak(...)` but the current `VoiceOutputSession` only exposed `create_output(...)`.

## Apply

Copy `apply_v510_commit3_voice_output_speak_contract.py` to the repository root, then run:

```powershell
python apply_v510_commit3_voice_output_speak_contract.py
```

After the helper modifies the working tree, delete the helper before commit:

```powershell
del apply_v510_commit3_voice_output_speak_contract.py
```

## Expected modified/added files

```text
framework/audio/voice_output.py
examples/app_voice_output_integration.py
docs/v510_voice_output_method_contract.md
scripts/smoke_v510_voice_output_method_contract.py
```

## Verification

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/check_release_package.py
python examples/app_voice_output_integration.py
```

Expected: no README `speak` mismatch WARN should remain in the public contract inventory smoke. The new method contract smoke should end with:

```text
[OK] voice output method contract is aligned for v5.1.0
```

## Commit message

```text
feat/test: align voice output speak method contract
```

## Notes

- `speak(request)` becomes the preferred public host-app method.
- `create_output(request)` remains available as a v5.0 compatibility method.
- Real provider execution remains disabled/guarded.
- No DRC-side changes are included.
