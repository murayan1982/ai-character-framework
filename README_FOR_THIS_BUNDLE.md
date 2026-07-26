# FW v5.1.0 Commit 8 capability snapshot bundle

Apply from repository root:

```powershell
python apply_v510_commit8_capability_snapshot.py
del apply_v510_commit8_capability_snapshot.py
```

Then verify:

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/smoke_v510_factory_signature_contract.py
python scripts/smoke_v510_result_error_contract.py
python scripts/smoke_v510_text_chat_result_public_type.py
python scripts/smoke_v510_text_chat_result_runtime_method.py
python scripts/smoke_v510_capability_snapshot.py
python scripts/check_release_package.py
```

Suggested commit:

```bash
git add framework/capabilities.py framework/__init__.py docs/v510_capability_snapshot_contract.md scripts/smoke_v510_capability_snapshot.py scripts/smoke_v510_public_contract_inventory.py
git commit -m "feat/test: add capability snapshot public API"
```
