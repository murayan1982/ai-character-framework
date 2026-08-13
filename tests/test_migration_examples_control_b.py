"""Provider-free tests for FW-RT6-11c Control B migration examples."""

from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

import framework


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (
    PROJECT_ROOT / "examples/app_v600_host_captured_audio.py",
    PROJECT_ROOT / "examples/app_v600_interrupt_partial_completion.py",
    PROJECT_ROOT / "examples/app_v600_local_playback_boundary.py",
    PROJECT_ROOT / "examples/app_v600_motion_extension_hook.py",
)


def _load(path: Path) -> object:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _credential_free_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    for key in tuple(environment):
        upper_key = key.upper()
        if any(
            marker in upper_key
            for marker in (
                "API_KEY",
                "ACCESS_TOKEN",
                "AUTH_TOKEN",
                "CLIENT_SECRET",
                "PRIVATE_CREDENTIAL",
            )
        ):
            environment.pop(key)
    return environment


class MigrationExamplesControlBTests(unittest.TestCase):
    def test_docs_record_exact_control_b_surface(self) -> None:
        guide = (
            PROJECT_ROOT / "docs/v600_v5_to_v6_session_migration.md"
        ).read_text(encoding="utf-8")
        facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(
            encoding="utf-8"
        )
        app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
            encoding="utf-8"
        )
        for text, marker in (
            (guide, "FW-RT6-11c-B-MIGRATION-EXAMPLES:BEGIN"),
            (facade, "FW-RT6-11c-B-PUBLIC-EXAMPLES:BEGIN"),
            (app, "FW-RT6-11c-B-APP-EXAMPLES:BEGIN"),
        ):
            self.assertEqual(text.count(marker), 1)
            self.assertIn("9 files", text)

    def test_control_b_does_not_close_aggregate_tasks(self) -> None:
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split(
            "## FW-RT6-11c — Migration guide and examples", 1
        )[1].split("## FW-RT6-12a", 1)[0]
        self.assertEqual(section.count("- [ ]"), 8)
        self.assertEqual(section.count("- [x]"), 0)

    def test_examples_import_only_framework_root(self) -> None:
        for path in EXAMPLES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module or "")
            self.assertEqual(imports, {"__future__", "framework"})

    def test_import_has_no_session_side_effect(self) -> None:
        modules = tuple(_load(path) for path in EXAMPLES)
        names = (
            "run_host_captured_audio",
            "run_interrupt_partial_completion",
            "run_local_playback_boundary",
            "run_motion_extension_hook",
        )
        for module, name in zip(modules, names, strict=True):
            self.assertTrue(callable(getattr(module, name)))

    def test_examples_execute_without_provider_credentials(self) -> None:
        code = (
            "import runpy,sys;"
            f"sys.path.insert(0,{str(PROJECT_ROOT)!r});"
            "runpy.run_path(sys.argv[1],run_name='__main__')"
        )
        for path in EXAMPLES:
            result = subprocess.run(
                [sys.executable, "-I", "-c", code, str(path)],
                cwd=PROJECT_ROOT,
                env=_credential_free_environment(),
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("provider_execution_performed: False", result.stdout)

    def test_host_audio_uses_opaque_id_and_fake_transcript(self) -> None:
        module = _load(EXAMPLES[0])
        facts = module.run_host_captured_audio()
        self.assertEqual(facts[:3], ("completed", "host captured fake transcript", "opaque_id"))

    def test_host_audio_reads_no_audio_or_microphone(self) -> None:
        module = _load(EXAMPLES[0])
        facts = module.run_host_captured_audio()
        self.assertEqual(facts[3:], (False, False, False))

    def test_interrupt_partial_is_terminal_aggregate(self) -> None:
        module = _load(EXAMPLES[1])
        facts = module.run_interrupt_partial_completion()
        self.assertEqual(facts[:5], (True, "not_implemented", "partial", True, True))
        self.assertEqual(facts[5:7], (0, 0))

    def test_interrupt_claims_no_hard_cancel_or_partial_transcript(self) -> None:
        module = _load(EXAMPLES[1])
        facts = module.run_interrupt_partial_completion()
        self.assertEqual(facts[7:], (False, False))

    def test_playback_requests_and_acknowledges_host(self) -> None:
        module = _load(EXAMPLES[2])
        facts = module.run_local_playback_boundary()
        self.assertEqual(facts[:3], ("not_implemented", True, True))

    def test_playback_claims_no_physical_stop_or_execution(self) -> None:
        module = _load(EXAMPLES[2])
        facts = module.run_local_playback_boundary()
        self.assertEqual(facts[3:], (False, False))

    def test_motion_hook_maps_signals_to_typed_not_configured(self) -> None:
        module = _load(EXAMPLES[3])
        facts = module.run_motion_extension_hook()
        self.assertEqual(
            facts[1],
            ("listening", "thinking", "speaking", "completed"),
        )
        self.assertEqual(facts[2], ("not_configured", "not_configured"))

    def test_motion_failure_does_not_replace_conversation_terminal(self) -> None:
        module = _load(EXAMPLES[3])
        facts = module.run_motion_extension_hook()
        self.assertEqual(facts[0], "completed")
        self.assertEqual(facts[3:], (1, False))

    def test_root_inventory_and_runtime_surface_remain_frozen(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        for name in (
            "run_host_captured_audio",
            "run_interrupt_partial_completion",
            "run_local_playback_boundary",
            "run_motion_extension_hook",
        ):
            self.assertNotIn(name, framework.__all__)
        expected = {
            "docs/app_integration_contract.md",
            "docs/public_facade.md",
            "docs/v600_v5_to_v6_session_migration.md",
            "examples/app_v600_host_captured_audio.py",
            "examples/app_v600_interrupt_partial_completion.py",
            "examples/app_v600_local_playback_boundary.py",
            "examples/app_v600_motion_extension_hook.py",
            "scripts/smoke_v600_migration_examples_control_b.py",
            "tests/test_migration_examples_control_b.py",
        }
        self.assertFalse(any(path.startswith("framework/") for path in expected))


if __name__ == "__main__":
    unittest.main()
