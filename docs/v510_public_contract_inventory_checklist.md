# v5.1.0 Public Contract Inventory Checklist

Updated: 2026-07-26

This checklist is the handoff between the v5.1.0 roadmap and the first code
changes.

## Baseline checks

Run from the FW repository root:

```powershell
python -m compileall -q .
python scripts/smoke_v510_public_contract_inventory.py
python scripts/check_release_package.py
```

## Expected behavior

```text
- no provider credentials are required
- real TTS execution remains disabled by default
- provider SDKs are not imported by `import framework`
- FW internal TTS modules are not imported by `import framework`
- public voice output session creation is mock-safe
- VoiceOutputResult stays provider-neutral
- docs/API mismatches are recorded as inventory findings, not fixed by this commit
```

## Things this checkpoint must not do

```text
- do not call real LLM/TTS/STT providers
- do not change DRC
- do not import FW internal modules from DRC
- do not add new sys.path/sys.modules/CWD workarounds
- do not create a release artifact
- do not mark DRC real_tts_web_audio_output as accepted
```

## Finding categories

The inventory smoke may print finding lines:

```text
[OK]      required current public contract is present
[INFO]    current baseline information or non-failing observation
[WARN]    known mismatch or future conformance issue
```

Commit 2 should fail only on missing baseline public exports, unsafe eager
provider/internal imports, or a broken mock-safe Voice Output result path.

Later v5.1.0 conformance gates should convert selected `[WARN]` findings into
release-blocking failures after the corresponding implementation commits land.
