"""Focused FW-RT6-12c Control B session-capability adoption tests."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_EXTENSIONS = (
    "microphone_listening_while_speaking",
    "vad_based_automatic_detection",
    "wake_word",
    "background_input_monitoring",
    "automatic_next_turn_capture",
    "echo_cancellation",
    "noise_suppression",
)
EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "public_metadata",
    "real_runtime_enabled",
    "voice_input_stage",
    "text_generation_stage",
    "voice_output_stage",
    "motion_stage",
    "config",
)


class NaturalTurnControlBTests(unittest.TestCase):
    def test_realtime_session_exposes_one_cached_immutable_snapshot(self) -> None:
        from framework import RealtimeSession
        from framework.natural_turn import NaturalTurnCapabilitySet

        session = RealtimeSession()
        try:
            first = session.natural_turn_capabilities
            second = session.natural_turn_capabilities
            self.assertIs(first, second)
            self.assertIsInstance(first, NaturalTurnCapabilitySet)
            self.assertEqual(first.supported_extensions, ())
        finally:
            session.close()

    def test_snapshot_keeps_exact_seven_independent_default_entries(self) -> None:
        from framework import RealtimeSession

        session = RealtimeSession()
        try:
            snapshot = session.natural_turn_capabilities
            self.assertEqual(
                tuple(item.extension.value for item in snapshot.capabilities),
                EXPECTED_EXTENSIONS,
            )
            for capability in snapshot.capabilities:
                with self.subTest(extension=capability.extension.value):
                    self.assertFalse(capability.supported)
                    self.assertTrue(capability.experimental)
                    self.assertEqual(capability.owner.value, "host_application")
                    self.assertTrue(capability.explicit_activation_required)
                    self.assertFalse(capability.microphone_device_access)
                    self.assertFalse(capability.background_execution)
                    self.assertFalse(capability.provider_execution)
                    self.assertFalse(capability.network_execution)
        finally:
            session.close()

    def test_snapshot_remains_readable_and_identical_after_close(self) -> None:
        from framework import RealtimeSession

        session = RealtimeSession()
        snapshot = session.natural_turn_capabilities
        session.close()
        self.assertIs(session.natural_turn_capabilities, snapshot)
        self.assertEqual(snapshot.supported_extensions, ())

        first_read_after_close = RealtimeSession()
        first_read_after_close.close()
        closed_snapshot = first_read_after_close.natural_turn_capabilities
        self.assertIs(
            first_read_after_close.natural_turn_capabilities,
            closed_snapshot,
        )
        self.assertEqual(closed_snapshot.supported_extensions, ())

    def test_no_configuration_activation_or_combined_mode_api_is_added(self) -> None:
        from framework import RealtimeSession

        self.assertTrue(hasattr(RealtimeSession, "natural_turn_capabilities"))
        for name in (
            "configure_natural_turn",
            "configure_natural_turn_extension",
            "activate_natural_turn",
            "start_natural_turn",
            "stop_natural_turn",
            "natural_mode",
        ):
            self.assertFalse(hasattr(RealtimeSession, name), name)

    def test_voice_input_session_remains_unadopted(self) -> None:
        from framework import VoiceInputSession

        self.assertFalse(hasattr(VoiceInputSession, "natural_turn_capabilities"))
        source = (PROJECT_ROOT / "framework/voice_input_session.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("natural_turn", source)

    def test_root_exports_and_realtime_factory_signature_remain_frozen(self) -> None:
        import framework

        self.assertEqual(len(framework.__all__), 127)
        for name in (
            "NaturalTurnCapability",
            "NaturalTurnCapabilitySet",
            "NaturalTurnExtension",
            "default_natural_turn_capability_set",
        ):
            self.assertNotIn(name, framework.__all__)
            self.assertFalse(hasattr(framework, name))
        self.assertEqual(
            tuple(inspect.signature(framework.create_realtime_session).parameters),
            EXPECTED_FACTORY_PARAMETERS,
        )

    def test_framework_import_construction_and_close_remain_namespace_lazy(self) -> None:
        probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework
assert "framework.natural_turn" not in sys.modules
session = framework.RealtimeSession()
assert "framework.natural_turn" not in sys.modules
assert session.capabilities is session.capabilities
assert "framework.natural_turn" not in sys.modules
session.close()
assert "framework.natural_turn" not in sys.modules
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

    def test_property_access_is_provider_network_device_and_background_safe(self) -> None:
        probe = r'''
import os
import sys
import threading
sys.path.insert(0, os.getcwd())
import framework
session = framework.RealtimeSession()
before = {thread.ident for thread in threading.enumerate()}
snapshot = session.natural_turn_capabilities
after = {thread.ident for thread in threading.enumerate()}
assert before == after
assert not snapshot.supported_extensions
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets", "requests", "httpx",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
session.close()
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

    def test_public_projection_is_immutable_and_payload_free(self) -> None:
        from framework import RealtimeSession

        session = RealtimeSession()
        try:
            projection = session.natural_turn_capabilities.as_dict()
            self.assertIsInstance(projection, MappingProxyType)
            self.assertEqual(projection["api_version"], "6.0")
            self.assertEqual(len(projection["capabilities"]), 7)
            self.assertNotIn("audio", repr(projection).lower())
            self.assertNotIn("transcript", repr(projection).lower())
            with self.assertRaises(TypeError):
                projection["api_version"] = "changed"  # type: ignore[index]
        finally:
            session.close()

    def test_lookup_stays_independent_and_has_no_combined_mode(self) -> None:
        from framework import RealtimeSession

        session = RealtimeSession()
        try:
            snapshot = session.natural_turn_capabilities
            self.assertEqual(snapshot.for_extension("wake_word").extension.value, "wake_word")
            self.assertEqual(snapshot.for_extension("echo_cancellation").extension.value, "echo_cancellation")
            with self.assertRaises(ValueError):
                snapshot.for_extension("natural_mode")
        finally:
            session.close()

    def test_docs_and_tasklist_preserve_capability_only_boundary(self) -> None:
        app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
        facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
        guide = (PROJECT_ROOT / "docs/v600_natural_turn_extensions.md").read_text(encoding="utf-8")
        for source, markers in (
            (app, ("FW-RT6-12c-B-APP-SESSION-CAPABILITIES:BEGIN", "FW-RT6-12c-B-APP-SESSION-CAPABILITIES:END")),
            (facade, ("FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:BEGIN", "FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:END")),
            (guide, ("FW-RT6-12c-B-SESSION-CAPABILITIES:BEGIN", "FW-RT6-12c-B-SESSION-CAPABILITIES:END")),
        ):
            for marker in markers:
                self.assertEqual(source.count(marker), 1, marker)
        combined = "\n".join((app, facade, guide)).lower()
        for phrase in (
            "natural_turn_capabilities",
            "read-only",
            "0 / 7",
            "voiceinputsession",
            "not an activation",
        ):
            self.assertIn(phrase, combined)
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
        section = tasklist.split("## FW-RT6-12c — Experimental natural-turn extensions", 1)[1].split("## FW-RT6-13a", 1)[0]
        self.assertEqual(section.count("- [ ]"), 0)
        self.assertEqual(section.count("- [x]"), 0)
        self.assertIn("各項目は別roadmap/exact contractとする。", section)
        acceptance_marker_count = tasklist.count(
            "FW-RT6-12c-B-ACCEPTANCE-SYNC:BEGIN"
        )
        self.assertLessEqual(acceptance_marker_count, 1)
        if acceptance_marker_count:
            self.assertEqual(
                tasklist.count("FW-RT6-12c-B-ACCEPTANCE-SYNC:END"),
                1,
            )
            for phrase in (
                "Control B: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
                "combined worktree surface: 9 files",
                "FW-RT6-12c roadmap items closed: 0 / 7",
                "aggregate exact contract review: AUTHORIZED_AFTER_COMMIT_PUSH",
            ):
                self.assertIn(phrase, tasklist)

    def test_control_a_source_gate_accepts_control_b_semantic_sync(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/smoke_v600_natural_turn_control_a.py", "--source-only"],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("v600_rt6_12c_extension_execution: False", completed.stdout)


if __name__ == "__main__":
    unittest.main()
