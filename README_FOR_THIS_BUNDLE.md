# FW v5.1.0 Commit 12 bundle

Apply from the AI-Character-Framework repository root:

```powershell
python apply_v510_commit12_public_contract_conformance_gate.py
del apply_v510_commit12_public_contract_conformance_gate.py
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
python scripts/smoke_v510_provider_config_ownership.py
python scripts/smoke_v510_session_lifecycle.py
python scripts/smoke_v510_opaque_voice_artifact_contract.py
python scripts/smoke_v510_public_contract_conformance_gate.py
python scripts/check_release_package.py
```

Suggested commit message:

```text
docs/test: add public contract conformance gate for v5.1.0
```
