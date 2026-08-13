"""FW-RT6-11b Control A root-public inventory unit tests."""

from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ROOT_PUBLIC_DIGEST = (
    "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
)
EXPECTED_PROVIDER_COMPATIBILITY = (
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


class RootPublicApiCleanupControlATests(unittest.TestCase):
    def test_root_public_surface_remains_127_unique_names(self) -> None:
        import framework
        from framework.public_api import PUBLIC_API_NAMES

        self.assertEqual(len(PUBLIC_API_NAMES), 127)
        self.assertEqual(len(PUBLIC_API_NAMES), len(set(PUBLIC_API_NAMES)))
        self.assertEqual(tuple(framework.__all__), PUBLIC_API_NAMES)

    def test_v6_inventory_is_canonical_sorted_name_set(self) -> None:
        from framework.public_api import PUBLIC_API_NAMES, V6_ROOT_PUBLIC_EXPORTS

        self.assertEqual(V6_ROOT_PUBLIC_EXPORTS, tuple(sorted(PUBLIC_API_NAMES)))
        self.assertEqual(_digest(V6_ROOT_PUBLIC_EXPORTS), ROOT_PUBLIC_DIGEST)

    def test_provider_classification_partitions_root_inventory(self) -> None:
        from framework.public_api import (
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
            V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
            V6_ROOT_PUBLIC_EXPORTS,
        )

        neutral = set(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS)
        compatibility = set(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS)
        self.assertEqual(len(neutral), 112)
        self.assertEqual(len(compatibility), 15)
        self.assertTrue(neutral.isdisjoint(compatibility))
        self.assertEqual(neutral | compatibility, set(V6_ROOT_PUBLIC_EXPORTS))

    def test_provider_compatibility_inventory_is_exact_and_frozen(self) -> None:
        from framework.public_api import V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS

        self.assertEqual(
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
            EXPECTED_PROVIDER_COMPATIBILITY,
        )

    def test_wildcard_order_is_preserved_but_non_contractual(self) -> None:
        from framework.public_api import (
            PUBLIC_API_NAMES,
            ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT,
            V6_ROOT_PUBLIC_EXPORTS,
        )

        self.assertEqual(ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT, "non_contractual")
        self.assertNotEqual(PUBLIC_API_NAMES, V6_ROOT_PUBLIC_EXPORTS)
        self.assertEqual(set(PUBLIC_API_NAMES), set(V6_ROOT_PUBLIC_EXPORTS))

    def test_machine_manifest_matches_source_and_digests(self) -> None:
        from framework.public_api import (
            ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION,
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
            V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
            V6_ROOT_PUBLIC_EXPORTS,
        )

        manifest = json.loads(
            (PROJECT_ROOT / "docs" / "v600_root_public_api_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            manifest["schema_version"], ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION
        )
        self.assertEqual(manifest["root_public_exports"], list(V6_ROOT_PUBLIC_EXPORTS))
        self.assertEqual(
            manifest["provider_neutral_root_exports"],
            list(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS),
        )
        self.assertEqual(
            manifest["provider_compatibility_root_exports"],
            list(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS),
        )
        self.assertEqual(manifest["root_public_sha256"], ROOT_PUBLIC_DIGEST)
        self.assertEqual(
            manifest["provider_neutral_sha256"],
            _digest(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS),
        )
        self.assertEqual(
            manifest["provider_compatibility_sha256"],
            _digest(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS),
        )

    def test_machine_manifest_records_control_b_provider_namespace(self) -> None:
        manifest = json.loads(
            (PROJECT_ROOT / "docs" / "v600_root_public_api_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            manifest["stable_optional_provider_namespace"],
            "framework.providers.openai.voice_input",
        )
        self.assertFalse(manifest["new_provider_specific_root_exports_allowed"])
        self.assertFalse((PROJECT_ROOT / "framework" / "providers.py").exists())
        self.assertTrue(
            (
                PROJECT_ROOT
                / "framework"
                / "providers"
                / "openai"
                / "voice_input.py"
            ).is_file()
        )

    def test_provider_compatibility_resolution_remains_lazy(self) -> None:
        code = r'''
import sys
import framework
from framework.public_api import V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
assert not any(name in framework.__dict__ for name in V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS)
for name in V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS:
    assert getattr(framework, name) is not None
forbidden = {"openai", "elevenlabs", "pyvts", "websocket", "websockets", "tts.voice_engine", "live2d.vts_client"}
assert not forbidden.intersection(sys.modules), sorted(forbidden.intersection(sys.modules))
'''
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )

    def test_public_api_source_remains_names_only(self) -> None:
        path = PROJECT_ROOT / "framework" / "public_api.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        roots.update(
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertEqual(roots - {"__future__", "types"}, set())

    def test_examples_have_no_wildcard_or_manifest_drift(self) -> None:
        from framework.public_api import V6_ROOT_PUBLIC_EXPORTS

        public_names = set(V6_ROOT_PUBLIC_EXPORTS)
        missing: list[str] = []
        wildcard: list[str] = []
        for path in sorted((PROJECT_ROOT / "examples").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            root_aliases = {"framework"}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "framework":
                            root_aliases.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module == "framework":
                    for alias in node.names:
                        if alias.name == "*":
                            wildcard.append(path.name)
                        elif alias.name not in public_names:
                            missing.append(f"{path.name}:{alias.name}")
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in root_aliases
                    and not node.attr.startswith("__")
                    and node.attr not in public_names
                ):
                    missing.append(f"{path.name}:{node.attr}")
        self.assertEqual(wildcard, [])
        self.assertEqual(missing, [])

    def test_contract_docs_record_exact_inventory(self) -> None:
        required = (
            "FW-RT6-11b-A-ROOT-PUBLIC-CLEANUP:BEGIN",
            "v6.root_public_api_manifest",
            "docs/v600_root_public_api_manifest.json",
            "127",
            "112",
            "15",
            ROOT_PUBLIC_DIGEST,
            "Control B: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        )
        for name in ("public_facade.md", "app_integration_contract.md"):
            text = (PROJECT_ROOT / "docs" / name).read_text(encoding="utf-8")
            for marker in required:
                self.assertIn(marker, text, f"{name}: {marker}")

    def test_control_c_closes_only_the_aggregate_task_boundary(self) -> None:
        tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split(
            "## FW-RT6-11b — Root-public API cleanup", 1
        )[1].split("## FW-RT6-11c", 1)[0]
        self.assertEqual(section.count("- [ ]"), 0)
        self.assertEqual(section.count("- [x]"), 6)
        self.assertTrue(
            (
                PROJECT_ROOT
                / "scripts"
                / "check_v600_root_public_api_cleanup_acceptance.py"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
