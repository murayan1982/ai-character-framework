# FW v5.1.0 Commit 10 session lifecycle fixed helper

The first helper failed because it only matched `VoiceOutputSession.speak` definitions shaped as `def speak(self, request):`.
The current method is return-annotated, so this fixed helper matches `def speak(self, request: ...) -> ...:` safely.

Run from the FW repository root:

```powershell
python apply_v510_commit10_session_lifecycle_fixed.py
del apply_v510_commit10_session_lifecycle_fixed.py
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
python scripts/check_release_package.py
```
