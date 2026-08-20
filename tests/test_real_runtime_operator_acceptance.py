"""Provider-free tests for the FW-RT6-13c operator tooling."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPERATOR_PATH = PROJECT_ROOT / "scripts/operator_v600_real_runtime_acceptance.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts/verify_v600_real_runtime_private_evidence.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("test module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


operator = _load(OPERATOR_PATH, "_v600_13c_operator_under_test")
verifier = _load(VERIFIER_PATH, "_v600_13c_verifier_under_test")


def _valid_evidence() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": verifier.EVIDENCE_SCHEMA,
        "run_id": "a" * 32,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "framework_head": "b" * 40,
        "dependency_versions": dict(verifier.EXPECTED_DEPENDENCIES),
    }
    payload.update({field: True for field in verifier.TRUE_FIELDS})
    payload.update({field: False for field in verifier.FALSE_FIELDS})
    payload.update({field: 1 for field in verifier.POSITIVE_COUNT_FIELDS})
    return payload


class RealRuntimeOperatorAcceptanceTests(unittest.TestCase):
    def test_import_is_provider_free(self) -> None:
        source = """
import importlib.util
import pathlib
import sys
before = set(sys.modules)
for index, filename in enumerate((
    'scripts/operator_v600_real_runtime_acceptance.py',
    'scripts/verify_v600_real_runtime_private_evidence.py',
)):
    spec = importlib.util.spec_from_file_location(f'_candidate_{index}', pathlib.Path(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
loaded = set(sys.modules) - before
for name in ('openai', 'elevenlabs', 'pyvts', 'websockets', 'sounddevice', 'pyaudio'):
    if name in loaded:
        raise AssertionError(name)
"""
        completed = subprocess.run(
            [sys.executable, "-c", source],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_operator_help_is_provider_free(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(OPERATOR_PATH), "--help"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("host-owned real-stage", completed.stdout)

    def _private_fixture(self, root: Path) -> tuple[Path, dict[str, object]]:
        audio = root / "private.wav"
        audio.write_bytes(b"RIFFprivate-provider-free-fixture")
        vts = root / "private-vts.json"
        vts.write_text("{}\n", encoding="utf-8")
        artifact_dir = root / "private-artifacts"
        payload: dict[str, object] = {
            "schema": operator.CONFIG_SCHEMA,
            "accepted_framework_head": "c" * 40,
            "voice_input": {
                "audio_file": str(audio),
                "duration_ms": 1000,
                "max_duration_ms": 2000,
                "language": "ja",
                "model": "private-stt-model",
                "credential_env": "PRIVATE_STT_KEY",
            },
            "text_generation": {
                "model": "private-llm-model",
                "system_instruction": "private instruction",
                "interrupt_prompt": "private interrupt prompt",
                "recovery_prompt": "private recovery prompt",
                "credential_env": "PRIVATE_LLM_KEY",
                "max_tokens": 32,
            },
            "voice_output": {
                "voice_profile_id": "private-profile",
                "artifact_dir": str(artifact_dir),
                "credential_env": "PRIVATE_TTS_KEY",
            },
            "motion": {"private_vts_config_file": str(vts)},
        }
        config = root / "private-config.json"
        config.write_text(json.dumps(payload), encoding="utf-8")
        return config, payload

    def test_exact_private_config_is_normalized_without_printing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, _ = self._private_fixture(Path(directory))
            parsed = operator._load_private_config(config, root=PROJECT_ROOT)
        self.assertEqual(parsed["accepted_framework_head"], "c" * 40)
        self.assertEqual(parsed["voice_input"]["duration_ms"], 1000)

    def test_private_config_rejects_unexpected_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, payload = self._private_fixture(Path(directory))
            payload["unexpected_private_value"] = "must-not-be-accepted"
            config.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected fields"):
                operator._load_private_config(config, root=PROJECT_ROOT)

    def test_private_audio_inside_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            path = Path(directory)
            config, _ = self._private_fixture(path)
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                operator._load_private_config(config, root=PROJECT_ROOT)

    def test_confirmation_phrases_are_exact_and_separate(self) -> None:
        phrases = {
            operator.REAL_CONFIRMATION,
            operator.PRIVATE_CONFIRMATION,
            operator.PLAYBACK_CONFIRMATION,
        }
        self.assertEqual(len(phrases), 3)
        self.assertTrue(all(value.startswith("I_") for value in phrases))

    def test_provider_versions_are_exactly_pinned(self) -> None:
        self.assertEqual(
            operator.EXPECTED_DEPENDENCIES,
            {"openai": "2.31.0", "elevenlabs": "2.41.0", "pyvts": "0.3.3"},
        )

    def test_exact_evidence_payload_is_accepted(self) -> None:
        accepted = verifier.validate_payload(_valid_evidence())
        self.assertEqual(accepted["schema"], verifier.EVIDENCE_SCHEMA)

    def test_evidence_missing_scenario_is_rejected(self) -> None:
        payload = _valid_evidence()
        payload.pop("configured_real_motion")
        with self.assertRaisesRegex(AssertionError, "missing or unexpected"):
            verifier.validate_payload(payload)

    def test_evidence_extra_private_field_is_rejected(self) -> None:
        payload = _valid_evidence()
        payload["private_model_name"] = "must-never-be-present"
        with self.assertRaisesRegex(AssertionError, "missing or unexpected"):
            verifier.validate_payload(payload)

    def test_evidence_exposure_marker_is_rejected(self) -> None:
        payload = _valid_evidence()
        payload["raw_exception_exposed"] = True
        with self.assertRaisesRegex(AssertionError, "false marker"):
            verifier.validate_payload(payload)

    def test_boolean_is_not_accepted_as_positive_count(self) -> None:
        payload = _valid_evidence()
        payload["motion_intent_count"] = True
        with self.assertRaisesRegex(AssertionError, "positive count"):
            verifier.validate_payload(payload)

    def test_public_markers_do_not_echo_private_values(self) -> None:
        values = {
            "configured_real_voice_input": True,
            "configured_real_llm_streaming": True,
            "repo_clean_after": True,
        }
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            operator._print_markers(
                status="completed",
                stage="completed",
                values=values,
            )
        output = stream.getvalue()
        for forbidden in (
            "private-stt-model",
            "private-llm-model",
            "private-profile",
            "private.wav",
            "Traceback",
        ):
            self.assertNotIn(forbidden, output)
        self.assertIn("raw_exception_exposed: False", output)

    def test_built_evidence_forbids_unified_real_realtime_session_claim(self) -> None:
        scenario_values = {
            field: True
            for field in verifier.TRUE_FIELDS
            if field
            not in {
                "repo_clean_before",
                "repo_clean_after",
                "private_config_outside_repo",
                "private_audio_outside_repo",
                "private_artifacts_outside_repo",
                "private_evidence_outside_repo",
            }
        }
        scenario_values.update(
            {
                "provider_hard_cancel_claimed": False,
                "framework_physical_playback_stop_claimed": False,
                **{field: 1 for field in verifier.POSITIVE_COUNT_FIELDS},
            }
        )
        payload = operator._build_evidence(
            run_id="d" * 32,
            framework_head="e" * 40,
            dependencies=verifier.EXPECTED_DEPENDENCIES,
            scenario_values=scenario_values,
            repo_clean_after=True,
        )
        verifier.validate_payload(payload)
        self.assertFalse(
            payload["framework_realtime_session_real_orchestration_used"]
        )

    def test_operator_source_has_no_realtime_session_execution(self) -> None:
        source = OPERATOR_PATH.read_text(encoding="utf-8")
        self.assertNotIn("create_realtime_session(", source)
        self.assertNotIn("RealtimeSession(", source)
        self.assertNotIn(".run_turn(", source)
        self.assertIn("framework_realtime_session_real_orchestration_used", source)


if __name__ == "__main__":
    unittest.main()
