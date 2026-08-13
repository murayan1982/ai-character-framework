"""Provider-free tests for FW-RT6-11c Control A migration examples."""

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
TEXT_EXAMPLE = PROJECT_ROOT / "examples/app_v600_realtime_text_only.py"
FALLBACK_EXAMPLE = (
    PROJECT_ROOT / "examples/app_v600_realtime_unavailable_fallback.py"
)
GUIDE = PROJECT_ROOT / "docs/v600_v5_to_v6_session_migration.md"


def _load(path: Path) -> object:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationExamplesControlATests(unittest.TestCase):
    def test_guide_maps_all_standalone_sessions(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        for name in (
            "TextChatSession",
            "VoiceInputSession",
            "VoiceOutputSession",
            "MotionSession",
        ):
            self.assertIn(name, text)

    def test_guide_distinguishes_three_compatibility_modes(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        self.assertIn("v5_standalone", text)
        self.assertIn("v5_skeleton", text)
        self.assertIn("v6_unified", text)

    def test_guide_preserves_host_and_provider_boundaries(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        for phrase in (
            "playback stay host-owned",
            "motion mapping",
            "provider hard cancel",
            "partial transcript/audio streaming is not invented",
        ):
            self.assertIn(phrase, text)

    def test_examples_import_only_framework_root(self) -> None:
        for path in (TEXT_EXAMPLE, FALLBACK_EXAMPLE):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module or "")
            self.assertEqual(imports, {"__future__", "framework"})

    def test_import_has_no_session_side_effect(self) -> None:
        text_module = _load(TEXT_EXAMPLE)
        fallback_module = _load(FALLBACK_EXAMPLE)
        self.assertTrue(callable(getattr(text_module, "run_text_only")))
        self.assertTrue(
            callable(getattr(fallback_module, "run_with_explicit_fallback"))
        )

    def test_text_only_example_is_provider_free_mock(self) -> None:
        module = _load(TEXT_EXAMPLE)
        mode, outcome, mock_runtime = module.run_text_only("provider free")
        self.assertEqual(mode, "v5_skeleton")
        self.assertEqual(outcome, "completed")
        self.assertTrue(mock_runtime)

    def test_explicit_unified_request_is_truthful_rejection(self) -> None:
        session = framework.create_realtime_session(real_runtime_enabled=True)
        result = session.run_turn(input_text="no silent mock")
        self.assertEqual(session.compatibility_profile.mode.value, "v6_unified")
        self.assertEqual(result.outcome.value, "rejected")
        self.assertIs(result.public_metadata["mock_runtime"], False)

    def test_fallback_is_separate_host_choice(self) -> None:
        module = _load(FALLBACK_EXAMPLE)
        facts = module.run_with_explicit_fallback("host decides")
        self.assertEqual(
            facts,
            (
                "v6_unified",
                "configuration_incomplete",
                "rejected",
                "v5_skeleton",
                True,
            ),
        )

    def test_examples_execute_without_provider_credentials(self) -> None:
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
        code = (
            "import runpy,sys;"
            f"sys.path.insert(0,{str(PROJECT_ROOT)!r});"
            "runpy.run_path(sys.argv[1],run_name='__main__')"
        )
        for path in (TEXT_EXAMPLE, FALLBACK_EXAMPLE):
            result = subprocess.run(
                [sys.executable, "-I", "-c", code, str(path)],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("provider_execution_performed: False", result.stdout)

    def test_docs_record_exact_control_a_surface(self) -> None:
        facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
        app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("exact implementation surface: 7 files", facade)
        self.assertIn("exact implementation surface: 7 files", app)
        self.assertIn("silent unified-to-mock fallback: False", facade)
        self.assertIn("silent unified-to-mock fallback: False", app)

    def test_control_a_does_not_close_aggregate_tasks(self) -> None:
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split(
            "## FW-RT6-11c — Migration guide and examples", 1
        )[1].split("## FW-RT6-12a", 1)[0]
        self.assertEqual(section.count("- [ ]"), 8)
        self.assertEqual(section.count("- [x]"), 0)

    def test_root_public_inventory_remains_frozen(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("run_text_only", framework.__all__)
        self.assertNotIn("run_with_explicit_fallback", framework.__all__)


if __name__ == "__main__":
    unittest.main()
