# FW v5.1.0 Commit 9 bundle

Proposed commit:

```text
feat/test: add FW-owned provider config resolution
```

Apply:

```powershell
python apply_v510_commit9_provider_config_ownership.py
del apply_v510_commit9_provider_config_ownership.py
```

Verify:

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/smoke_v510_voice_output_method_contract.py
python scripts/smoke_v510_factory_signature_contract.py
python scripts/smoke_v510_result_error_contract.py
python scripts/smoke_v510_text_chat_result_public_type.py
python scripts/smoke_v510_text_chat_result_runtime_method.py
python scripts/smoke_v510_capability_snapshot.py
python scripts/smoke_v510_provider_config_ownership.py
python scripts/check_release_package.py
```

Commit:

```bash
git add framework/provider_config.py docs/v510_provider_config_ownership.md scripts/smoke_v510_provider_config_ownership.py
git commit -m "feat/test: add FW-owned provider config resolution"
```

This commit is mock-safe. It does not run real providers and does not change DRC.
