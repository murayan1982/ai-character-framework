"""Focused FW-RT6-12c Control A natural-turn contract tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_EXPORTS = (
    "NATURAL_TURN_API_VERSION",
    "NaturalTurnExtension",
    "NaturalTurnOwnership",
    "NaturalTurnCapability",
    "NaturalTurnCapabilitySet",
    "default_natural_turn_capability_set",
)
EXPECTED_EXTENSIONS = (
    "microphone_listening_while_speaking",
    "vad_based_automatic_detection",
    "wake_word",
    "background_input_monitoring",
    "automatic_next_turn_capture",
    "echo_cancellation",
    "noise_suppression",
)


class NaturalTurnControlATests(unittest.TestCase):
    def test_explicit_namespace_exports_are_exact(self) -> None:
        import framework.natural_turn as natural_turn

        self.assertEqual(natural_turn.__all__, EXPECTED_EXPORTS)
        self.assertEqual(natural_turn.NATURAL_TURN_API_VERSION, "6.0")
        self.assertEqual(len(set(natural_turn.__all__)), 6)

    def test_framework_root_remains_frozen_and_explicit_only(self) -> None:
        import framework

        self.assertEqual(len(framework.__all__), 127)
        for name in EXPECTED_EXPORTS:
            self.assertNotIn(name, framework.__all__)
            self.assertFalse(hasattr(framework, name))

    def test_extension_vocabulary_is_exact_and_independent(self) -> None:
        from framework.natural_turn import NaturalTurnExtension

        self.assertEqual(
            tuple(extension.value for extension in NaturalTurnExtension),
            EXPECTED_EXTENSIONS,
        )
        self.assertNotIn("natural_mode", EXPECTED_EXTENSIONS)

    def test_default_set_contains_seven_truthful_unsupported_capabilities(self) -> None:
        from framework.natural_turn import NaturalTurnCapabilitySet

        capability_set = NaturalTurnCapabilitySet()
        self.assertEqual(len(capability_set.capabilities), 7)
        self.assertEqual(capability_set.supported_extensions, ())
        for capability in capability_set.capabilities:
            with self.subTest(extension=capability.extension.value):
                self.assertFalse(capability.supported)
                self.assertTrue(capability.experimental)
                self.assertEqual(capability.owner.value, "host_application")
                self.assertTrue(capability.explicit_activation_required)
                self.assertFalse(capability.microphone_device_access)
                self.assertFalse(capability.background_execution)
                self.assertFalse(capability.provider_execution)
                self.assertFalse(capability.network_execution)

    def test_default_factory_returns_fresh_immutable_inventories(self) -> None:
        from framework.natural_turn import default_natural_turn_capability_set

        first = default_natural_turn_capability_set()
        second = default_natural_turn_capability_set()
        self.assertIsNot(first, second)
        self.assertIsNot(first.capabilities, second.capabilities)
        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            first.capabilities = ()  # type: ignore[misc]

    def test_extension_lookup_accepts_enum_or_stable_value(self) -> None:
        from framework.natural_turn import (
            NaturalTurnCapabilitySet,
            NaturalTurnExtension,
        )

        capability_set = NaturalTurnCapabilitySet()
        by_string = capability_set.for_extension("wake_word")
        by_enum = capability_set.for_extension(NaturalTurnExtension.WAKE_WORD)
        self.assertIs(by_string, by_enum)
        with self.assertRaises(ValueError):
            capability_set.for_extension("combined_natural_mode")

    def test_supported_capability_requires_explicit_adapter_ownership(self) -> None:
        from framework.natural_turn import NaturalTurnCapability

        capability = NaturalTurnCapability(
            extension="noise_suppression",
            supported=True,
            owner="explicit_adapter",
            microphone_device_access=True,
        )
        self.assertTrue(capability.supported)
        self.assertEqual(capability.owner.value, "explicit_adapter")
        with self.assertRaises(ValueError):
            NaturalTurnCapability(extension="noise_suppression", supported=True)

    def test_unsupported_capability_cannot_advertise_execution(self) -> None:
        from framework.natural_turn import NaturalTurnCapability

        for field_name in (
            "microphone_device_access",
            "background_execution",
            "provider_execution",
            "network_execution",
        ):
            with self.subTest(field_name=field_name), self.assertRaises(ValueError):
                NaturalTurnCapability(
                    extension="wake_word",
                    **{field_name: True},
                )
        with self.assertRaises(ValueError):
            NaturalTurnCapability(
                extension="wake_word",
                owner="explicit_adapter",
            )

    def test_experimental_and_explicit_activation_are_mandatory(self) -> None:
        from framework.natural_turn import NaturalTurnCapability

        with self.assertRaises(ValueError):
            NaturalTurnCapability(extension="wake_word", experimental=False)
        with self.assertRaises(ValueError):
            NaturalTurnCapability(
                extension="wake_word",
                explicit_activation_required=False,
            )

    def test_boolean_fields_reject_integer_coercion(self) -> None:
        from framework.natural_turn import NaturalTurnCapability

        for field_name in (
            "supported",
            "experimental",
            "explicit_activation_required",
            "microphone_device_access",
            "background_execution",
            "provider_execution",
            "network_execution",
        ):
            with self.subTest(field_name=field_name), self.assertRaises(TypeError):
                NaturalTurnCapability(
                    extension="wake_word",
                    **{field_name: 1},
                )

    def test_capability_set_requires_exact_unique_tuple(self) -> None:
        from framework.natural_turn import (
            NaturalTurnCapability,
            NaturalTurnCapabilitySet,
            NaturalTurnExtension,
        )

        complete = tuple(
            NaturalTurnCapability(extension) for extension in NaturalTurnExtension
        )
        self.assertEqual(len(NaturalTurnCapabilitySet(complete).capabilities), 7)
        with self.assertRaises(TypeError):
            NaturalTurnCapabilitySet(list(complete))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            NaturalTurnCapabilitySet(complete[:-1])
        with self.assertRaises(ValueError):
            NaturalTurnCapabilitySet(complete[:-1] + (complete[0],))
        with self.assertRaises(TypeError):
            NaturalTurnCapabilitySet(complete[:-1] + ("noise_suppression",))  # type: ignore[arg-type]

    def test_public_metadata_is_recursively_sanitized(self) -> None:
        from framework.natural_turn import NaturalTurnCapability
        from framework.public_safety import REDACTED_PATH, REDACTED_VALUE

        capability = NaturalTurnCapability(
            extension="echo_cancellation",
            public_metadata={
                "nested": {
                    "api_key": "private-secret",
                    "path": "C:\\private\\capture.raw",
                }
            },
        )
        nested = capability.public_metadata["nested"]
        self.assertIsInstance(nested, MappingProxyType)
        self.assertEqual(nested["api_key"], REDACTED_VALUE)
        self.assertEqual(nested["path"], REDACTED_PATH)
        self.assertNotIn("private-secret", repr(capability))

    def test_capability_and_projection_are_immutable(self) -> None:
        from framework.natural_turn import NaturalTurnCapability

        capability = NaturalTurnCapability(extension="wake_word")
        projection = capability.as_dict()
        self.assertIsInstance(projection, MappingProxyType)
        with self.assertRaises(TypeError):
            projection["supported"] = True  # type: ignore[index]
        with self.assertRaises(FrozenInstanceError):
            capability.supported = True  # type: ignore[misc]

    def test_capability_set_projection_preserves_separate_entries(self) -> None:
        from framework.natural_turn import NaturalTurnCapabilitySet

        projection = NaturalTurnCapabilitySet().as_dict()
        self.assertIsInstance(projection, MappingProxyType)
        self.assertEqual(projection["api_version"], "6.0")
        entries = projection["capabilities"]
        self.assertEqual(tuple(entry["extension"] for entry in entries), EXPECTED_EXTENSIONS)
        self.assertTrue(all(not entry["supported"] for entry in entries))

    def test_import_is_provider_network_device_and_background_safe(self) -> None:
        probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.natural_turn as natural_turn
assert len(natural_turn.__all__) == 6
assert not natural_turn.default_natural_turn_capability_set().supported_extensions
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets", "requests", "httpx",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe],
            cwd=PROJECT_ROOT,
            env={key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_docs_task_boundary_and_execution_non_adoption_conform(self) -> None:
        app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
            encoding="utf-8"
        )
        facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
        guide = (PROJECT_ROOT / "docs/v600_natural_turn_extensions.md").read_text(
            encoding="utf-8"
        )
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
        for marker in (
            "FW-RT6-12c-A-APP-NATURAL-TURN:BEGIN",
            "FW-RT6-12c-A-APP-NATURAL-TURN:END",
        ):
            self.assertEqual(app.count(marker), 1)
        for marker in (
            "FW-RT6-12c-A-PUBLIC-NATURAL-TURN:BEGIN",
            "FW-RT6-12c-A-PUBLIC-NATURAL-TURN:END",
        ):
            self.assertEqual(facade.count(marker), 1)
        combined = "\n".join((app, facade, guide))
        for phrase in (
            "framework.natural_turn",
            "explicit",
            "host",
            "seven",
            "independent",
            "not required for v6.0.0 P0 acceptance",
        ):
            self.assertIn(phrase.lower(), combined.lower())
        section = tasklist.split(
            "## FW-RT6-12c — Experimental natural-turn extensions", 1
        )[1].split("## FW-RT6-13a", 1)[0]
        self.assertEqual(section.count("- [ ]"), 0)
        self.assertEqual(section.count("- [x]"), 0)
        self.assertIn("各項目は別roadmap/exact contractとする。", section)
        acceptance_marker_count = tasklist.count(
            "FW-RT6-12c-A-ACCEPTANCE-SYNC:BEGIN"
        )
        self.assertLessEqual(acceptance_marker_count, 1)
        if acceptance_marker_count:
            self.assertEqual(
                tasklist.count("FW-RT6-12c-A-ACCEPTANCE-SYNC:END"),
                1,
            )
            self.assertIn(
                "Control A: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
                tasklist,
            )
        self.assertNotIn("natural_turn", (PROJECT_ROOT / "framework/__init__.py").read_text(encoding="utf-8"))
        self.assertNotIn(
            "natural_turn",
            (PROJECT_ROOT / "framework/voice_input_session.py").read_text(
                encoding="utf-8"
            ),
        )
        realtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
            encoding="utf-8"
        )
        control_b_marker = "FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:BEGIN"
        if control_b_marker in facade:
            self.assertIn("natural_turn_capabilities", realtime_source)
            for forbidden_member in (
                "configure_natural_turn",
                "activate_natural_turn",
                "start_natural_turn",
                "natural_mode",
            ):
                self.assertNotIn(forbidden_member, realtime_source)
        else:
            self.assertNotIn("natural_turn", realtime_source)


if __name__ == "__main__":
    unittest.main()
