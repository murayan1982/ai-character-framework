# FW v5.1.0 Commit 6 fix

This is a small fix for the Commit 6 TextChatResult public type smoke.

The implementation and docs are OK, but the smoke expected the phrase
`does not change the existing text chat runtime return behavior yet` as one
physical line. The generated doc wrapped the sentence across lines, so the check
failed even though the content exists.

Apply:

```powershell
python apply_v510_commit6_text_chat_result_public_type_fix.py
del apply_v510_commit6_text_chat_result_public_type_fix.py
```

Then rerun:

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/smoke_v510_factory_signature_contract.py
python scripts/smoke_v510_result_error_contract.py
python scripts/smoke_v510_text_chat_result_public_type.py
python scripts/check_release_package.py
```
