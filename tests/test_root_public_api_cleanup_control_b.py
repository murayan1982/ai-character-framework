"""FW-RT6-11b Control B stable optional-provider namespace tests."""

from __future__ import annotations

from hashlib import sha256
import importlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import warnings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_NAMESPACE = "framework.providers.openai.voice_input"
ROOT_PUBLIC_DIGEST = (
    "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
)
EXPECTED_EXPORTS = (
    "OpenAIVoiceInputClient",
    "OpenAIVoiceInputClientFactory",
    "OpenAIVoiceInputFakeClientMarker",
    "OpenAIVoiceInputFakeExecutionPolicy",
    "OpenAIVoiceInputFakeExecutionStatus",
    "OpenAIVoiceInputFakeExecutor",
    "OpenAIVoiceInputPreflight",
    "OpenAIVoiceInputPreflightStatus",
    "OpenAIVoiceInputPrivateCredential",
    "OpenAIVoiceInputProviderAdapter",
    "OpenAIVoiceInputRealClientFactory",
    "OpenAIVoiceInputRealProviderExecutor",
    "OpenAIVoiceInputRealProviderPolicy",
    "OpenAIVoiceInputRealProviderStatus",
    "OpenAIVoiceInputRuntimeMode",
)


def _digest(names: tuple[str, ...]) -> str:
    return sha256(
        "".join(f"{name}\n" for name in names).encode("utf-8")
    ).hexdigest()


class RootPublicApiCleanupControlBTests(unittest.TestCase):
    def test_root_import_does_not_load_provider_namespace(self) -> None:
        code = r'''
import sys
import framework
assert len(framework.__all__) == 127
assert "framework.providers" not in sys.modules
assert "framework.providers.openai.voice_input" not in sys.modules
assert "framework.openai_voice_input_real_provider" not in sys.modules
assert not any(name == "openai" or name.startswith("openai.") for name in sys.modules)
'''
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_namespace_containers_export_no_objects(self) -> None:
        import framework.providers as providers
        import framework.providers.openai as openai_namespace

        self.assertEqual(providers.__all__, ())
        self.assertEqual(openai_namespace.__all__, ())

    def test_voice_input_namespace_has_exact_exports(self) -> None:
        namespace = importlib.import_module(EXPECTED_NAMESPACE)

        self.assertEqual(tuple(namespace.__all__), EXPECTED_EXPORTS)
        self.assertEqual(len(namespace.__all__), len(set(namespace.__all__)))

    def test_namespace_exports_are_root_compatibility_objects(self) -> None:
        import framework
        from framework.public_api import V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS

        namespace = importlib.import_module(EXPECTED_NAMESPACE)
        self.assertEqual(tuple(namespace.__all__), V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS)
        for name in EXPECTED_EXPORTS:
            with self.subTest(name=name):
                self.assertIs(getattr(namespace, name), getattr(framework, name))

    def test_root_inventory_and_digest_remain_frozen(self) -> None:
        import framework
        from framework.public_api import V6_ROOT_PUBLIC_EXPORTS

        self.assertEqual(len(framework.__all__), 127)
        self.assertEqual(tuple(sorted(framework.__all__)), V6_ROOT_PUBLIC_EXPORTS)
        self.assertEqual(_digest(V6_ROOT_PUBLIC_EXPORTS), ROOT_PUBLIC_DIGEST)

    def test_provider_classification_remains_112_plus_15(self) -> None:
        from framework.public_api import (
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
            V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
            V6_ROOT_PUBLIC_EXPORTS,
        )

        self.assertEqual(len(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS), 112)
        self.assertEqual(len(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS), 15)
        self.assertEqual(
            set(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS)
            | set(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS),
            set(V6_ROOT_PUBLIC_EXPORTS),
        )

    def test_machine_manifest_records_stable_namespace(self) -> None:
        manifest = json.loads(
            (PROJECT_ROOT / "docs/v600_root_public_api_manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(manifest["stable_optional_provider_namespace"], EXPECTED_NAMESPACE)
        self.assertEqual(manifest["root_public_sha256"], ROOT_PUBLIC_DIGEST)
        self.assertEqual(
            tuple(manifest["provider_compatibility_root_exports"]),
            EXPECTED_EXPORTS,
        )
        self.assertFalse(manifest["new_provider_specific_root_exports_allowed"])

    def test_namespace_import_does_not_load_provider_sdk(self) -> None:
        code = r'''
import sys
import framework.providers.openai.voice_input as voice_input
assert len(voice_input.__all__) == 15
forbidden = {"openai", "elevenlabs", "pyvts", "websocket", "websockets"}
assert not forbidden.intersection(sys.modules)
assert not any(name.startswith("openai.") for name in sys.modules)
'''
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_public_api_records_exact_namespace_without_runtime_imports(self) -> None:
        from framework.public_api import STABLE_OPTIONAL_PROVIDER_NAMESPACE

        self.assertEqual(STABLE_OPTIONAL_PROVIDER_NAMESPACE, EXPECTED_NAMESPACE)
        source = (PROJECT_ROOT / "framework/public_api.py").read_text(encoding="utf-8")
        for forbidden in (
            "import openai",
            "import pyvts",
            "import websocket",
            "import pyaudio",
        ):
            self.assertNotIn(forbidden, source.lower())

    def test_root_compatibility_access_remains_warning_free(self) -> None:
        import framework

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for name in EXPECTED_EXPORTS:
                self.assertIsNotNone(getattr(framework, name))
        self.assertEqual(caught, [])

    def test_contract_docs_record_namespace_lifecycle(self) -> None:
        required = (
            "FW-RT6-11b-B-OPTIONAL-PROVIDER-NAMESPACE:BEGIN",
            EXPECTED_NAMESPACE,
            "127 / UNCHANGED",
            "15 / PRESERVED / LAZY / SILENT",
            "Control C aggregate acceptance: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        )
        for name in ("public_facade.md", "app_integration_contract.md"):
            text = (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
            for phrase in required:
                self.assertIn(phrase, text, f"{name}: {phrase}")

    def test_control_b_does_not_close_aggregate_tasks(self) -> None:
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
        section = tasklist.split("## FW-RT6-11b — Root-public API cleanup", 1)[1].split(
            "## FW-RT6-11c", 1
        )[0]

        self.assertEqual(section.count("- [ ]"), 6)
        self.assertEqual(section.count("- [x]"), 0)


if __name__ == "__main__":
    unittest.main()
