"""Runtime-adoption tests for FW-RT6-11a Control B compatibility profiles."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest
import warnings

import framework
from framework.audio.voice_output import VoiceOutputSession
from framework.facade import TextChatSession, TextChatSessionInfo
from framework.lifecycle import TurnOutcome
from framework.motion_session import MotionSession
from framework.realtime_session import RealtimeSession
from framework.realtime_session_config import RealtimeSessionConfig
from framework.realtime_stage import RealtimeStageKind
from framework.session_compatibility import (
    CompatibilityWarningMode,
    SessionCompatibilityMode,
    SessionCompatibilityProfile,
    StandaloneSessionKind,
)
from framework.voice_input_session import VoiceInputSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ADOPTION_FILES = (
    "framework/facade.py",
    "framework/voice_input_session.py",
    "framework/audio/voice_output.py",
    "framework/motion_session.py",
    "framework/realtime_session.py",
)


def _text_chat_session() -> TextChatSession:
    return TextChatSession(
        object(),  # type: ignore[arg-type]
        TextChatSessionInfo(
            preset="control_b",
            character_name="Control B",
            input_language_code="en",
            output_language_code="en",
            llm_mode="test",
            provider=None,
            model=None,
            route_name=None,
        ),
    )


def _standalone_sessions() -> tuple[object, ...]:
    return (
        _text_chat_session(),
        VoiceInputSession(),
        VoiceOutputSession(),
        MotionSession(),
    )


class _NonExecutingTextStage:
    stage_kind = RealtimeStageKind.TEXT_GENERATION

    def preflight(self) -> object:
        return object()

    def capability(self) -> object:
        return object()

    def start(self, *, context: object, request: object) -> object:
        raise AssertionError("stage execution is outside this compatibility probe")

    def cancel(self, *, context: object) -> bool:
        return False

    def close(self) -> None:
        return None


class SessionCompatibilityControlBTests(unittest.TestCase):
    def test_five_public_sessions_expose_read_only_properties(self) -> None:
        for session_type in (
            TextChatSession,
            VoiceInputSession,
            VoiceOutputSession,
            MotionSession,
            RealtimeSession,
        ):
            with self.subTest(session_type=session_type.__name__):
                descriptor = inspect.getattr_static(
                    session_type,
                    "compatibility_profile",
                )
                self.assertIsInstance(descriptor, property)
                self.assertIsNone(descriptor.fset)
                self.assertIsNone(descriptor.fdel)

    def test_four_standalone_sessions_return_canonical_profiles(self) -> None:
        expected = (
            (StandaloneSessionKind.TEXT_CHAT, "4.0", "TextChatSession"),
            (StandaloneSessionKind.VOICE_INPUT, "5.2.0", "VoiceInputSession"),
            (
                StandaloneSessionKind.VOICE_OUTPUT,
                "v5.lazy_provider_adapter",
                "VoiceOutputSession",
            ),
            (StandaloneSessionKind.MOTION, "5.5.0", "MotionSession"),
        )
        sessions = _standalone_sessions()
        self.addCleanup(lambda: [session.close() for session in sessions])

        for session, (kind, version, owner) in zip(sessions, expected):
            with self.subTest(kind=kind.value):
                profile = session.compatibility_profile
                self.assertIsInstance(profile, SessionCompatibilityProfile)
                self.assertIs(profile.session_kind, kind)
                self.assertIs(
                    profile.mode,
                    SessionCompatibilityMode.V5_STANDALONE,
                )
                self.assertEqual(profile.contract_version, version)
                self.assertEqual(profile.execution_owner, owner)
                self.assertIs(
                    profile.warning_mode,
                    CompatibilityWarningMode.SILENT,
                )
                self.assertFalse(profile.runtime_execution_performed)

    def test_profile_reads_are_stable_and_immutable(self) -> None:
        session = VoiceOutputSession()
        self.addCleanup(session.close)
        first = session.compatibility_profile
        second = session.compatibility_profile

        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            first.mode = SessionCompatibilityMode.V6_UNIFIED  # type: ignore[misc]
        with self.assertRaises(AttributeError):
            session.compatibility_profile = first  # type: ignore[misc]

    def test_compatibility_package_loads_only_when_property_is_read(self) -> None:
        code = "\n".join(
            (
                "import sys",
                "import framework",
                "assert 'framework.session_compatibility' not in sys.modules",
                "session = framework.VoiceOutputSession()",
                "assert 'framework.session_compatibility' not in sys.modules",
                "profile = session.compatibility_profile",
                "assert profile.mode.value == 'v5_standalone'",
                "assert 'framework.session_compatibility' in sys.modules",
                "session.close()",
            )
        )
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            check=True,
        )

    def test_construction_and_profile_reads_emit_no_warnings(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sessions = (*_standalone_sessions(), RealtimeSession())
            try:
                for session in sessions:
                    self.assertIsNotNone(session.compatibility_profile)
            finally:
                for session in sessions:
                    session.close()
        self.assertEqual(caught, [])

    def test_realtime_default_and_explicit_false_select_v5_skeleton(self) -> None:
        sessions = (RealtimeSession(), RealtimeSession(real_runtime_enabled=False))
        self.addCleanup(lambda: [session.close() for session in sessions])
        for session in sessions:
            with self.subTest(session=session):
                profile = session.compatibility_profile
                self.assertIs(profile.session_kind, StandaloneSessionKind.REALTIME)
                self.assertIs(profile.mode, SessionCompatibilityMode.V5_SKELETON)

    def test_realtime_explicit_true_selects_v6_unified_by_request_truth(self) -> None:
        sessions = (
            RealtimeSession(real_runtime_enabled=True),
            RealtimeSession(config=RealtimeSessionConfig(real_runtime_enabled=True)),
        )
        self.addCleanup(lambda: [session.close() for session in sessions])
        for session in sessions:
            with self.subTest(session=session):
                profile = session.compatibility_profile
                self.assertIs(profile.mode, SessionCompatibilityMode.V6_UNIFIED)
                self.assertEqual(profile.contract_version, "5.2.0")

    def test_stage_binding_alone_does_not_select_unified_mode(self) -> None:
        session = RealtimeSession(text_generation_stage=_NonExecutingTextStage())
        self.addCleanup(session.close)
        self.assertIs(
            session.compatibility_profile.mode,
            SessionCompatibilityMode.V5_SKELETON,
        )

    def test_explicit_unified_request_rejects_without_mock_fallback(self) -> None:
        session = RealtimeSession(real_runtime_enabled=True)
        self.addCleanup(session.close)

        result = session.run_turn(input_text="must not execute")

        self.assertIs(session.compatibility_profile.mode, SessionCompatibilityMode.V6_UNIFIED)
        self.assertIs(result.outcome, TurnOutcome.REJECTED)
        self.assertFalse(result.public_metadata["mock_runtime"])
        self.assertFalse(result.public_metadata["provider_execution_performed"])

    def test_default_realtime_keeps_existing_mock_turn_behavior(self) -> None:
        session = RealtimeSession()
        self.addCleanup(session.close)

        result = session.run_turn(input_text="compatibility")

        self.assertIs(result.outcome, TurnOutcome.COMPLETED)
        self.assertTrue(result.public_metadata["mock_runtime"])
        self.assertIs(
            session.compatibility_profile.mode,
            SessionCompatibilityMode.V5_SKELETON,
        )

    def test_profiles_remain_readable_and_equal_after_close(self) -> None:
        sessions = (*_standalone_sessions(), RealtimeSession(real_runtime_enabled=True))
        for session in sessions:
            with self.subTest(session=type(session).__name__):
                before = session.compatibility_profile
                session.close()
                self.assertEqual(session.compatibility_profile, before)

    def test_factory_signatures_and_root_exports_remain_unchanged(self) -> None:
        expected_parameters = {
            framework.create_text_chat_session: (
                "preset",
                "character_name",
                "provider",
                "model",
                "project_root",
            ),
            framework.create_voice_input_session: (
                "project_root",
                "provider",
                "language",
                "real_stt_enabled",
                "allow_provider_execution",
                "credential_env",
                "private_credential",
                "allow_provider_sdk_import",
                "allow_provider_client_creation",
                "allow_real_provider_execution",
                "max_audio_bytes",
                "provider_timeout_seconds",
                "provider_max_retries",
                "public_metadata",
            ),
            framework.create_voice_output_session: (
                "project_root",
                "default_voice_profile_id",
                "real_tts_enabled",
                "artifact_dir",
            ),
            framework.create_motion_session: (
                "project_root",
                "adapter",
                "real_adapter_enabled",
                "allow_provider_execution",
                "runtime_available",
                "model_selected",
                "vts_endpoint_host",
                "vts_endpoint_port",
                "vts_authentication_token",
                "vts_hotkey_bindings",
                "vts_connect_timeout_seconds",
                "vts_authenticate_timeout_seconds",
                "vts_request_timeout_seconds",
                "vts_close_timeout_seconds",
                "public_metadata",
            ),
            framework.create_realtime_session: (
                "project_root",
                "public_metadata",
                "real_runtime_enabled",
                "voice_input_stage",
                "text_generation_stage",
                "voice_output_stage",
                "motion_stage",
                "config",
            ),
        }
        for factory, expected in expected_parameters.items():
            with self.subTest(factory=factory.__name__):
                self.assertEqual(tuple(inspect.signature(factory).parameters), expected)
                self.assertNotIn(
                    "compatibility_profile",
                    inspect.signature(factory).parameters,
                )
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("SessionCompatibilityProfile", framework.__all__)

    def test_public_version_labels_are_frozen(self) -> None:
        self.assertEqual(
            framework.TextChatSessionInfo.__dataclass_fields__["api_version"].default,
            "4.0",
        )
        self.assertEqual(
            framework.VoiceInputSessionInfo.__dataclass_fields__["api_version"].default,
            "5.2.0",
        )
        self.assertEqual(
            framework.VoiceOutputSessionInfo.__dataclass_fields__["boundary_version"].default,
            "v5.lazy_provider_adapter",
        )
        self.assertEqual(
            framework.MotionSessionInfo.__dataclass_fields__["api_version"].default,
            "5.5.0",
        )
        self.assertEqual(
            framework.RealtimeSessionInfo.__dataclass_fields__["api_version"].default,
            "5.2.0",
        )

    def test_exact_runtime_adoption_reuses_the_canonical_builder(self) -> None:
        for relative in RUNTIME_ADOPTION_FILES:
            with self.subTest(relative=relative):
                source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
                self.assertEqual(source.count("def compatibility_profile"), 1)
                self.assertEqual(source.count("build_session_compatibility_profile("), 1)
                self.assertNotIn("warnings.warn", source)

    def test_profiles_cannot_retain_private_or_provider_objects(self) -> None:
        session = RealtimeSession(
            real_runtime_enabled=True,
            public_metadata={
                "credential": "secret",
                "provider_payload": object(),
                "private_path": "C:/private/file",
            },
        )
        self.addCleanup(session.close)
        serialized = json.dumps(session.compatibility_profile.as_dict(), sort_keys=True)
        for forbidden in (
            "secret",
            "credential",
            "provider_payload",
            "private_path",
            "c:/private/file",
        ):
            self.assertNotIn(forbidden, serialized.lower())

    def test_control_c_closes_only_the_aggregate_task_boundary(self) -> None:
        for relative in (
            "docs/public_facade.md",
            "docs/app_integration_contract.md",
        ):
            text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            self.assertIn(
                "FW-RT6-11a-B-SESSION-COMPATIBILITY-ADOPTION:BEGIN",
                text,
            )
            self.assertIn(
                "five read-only `compatibility_profile` properties",
                normalized.lower(),
            )
            self.assertIn("FW-RT6-11a", text)
        tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
            encoding="utf-8"
        )
        section = tasklist.split(
            "## FW-RT6-11a — v5 standalone session compatibility",
            1,
        )[1].split("## FW-RT6-11b", 1)[0]
        self.assertEqual(section.count("- [ ]"), 0)
        self.assertEqual(section.count("- [x]"), 6)
        self.assertIn(
            "check_v600_session_compatibility_acceptance",
            "\n".join(
                str(path.relative_to(PROJECT_ROOT))
                for path in PROJECT_ROOT.glob("scripts/*session_compatibility*")
            ),
        )


if __name__ == "__main__":
    unittest.main()
