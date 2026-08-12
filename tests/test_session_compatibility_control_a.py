"""Provider-free tests for FW-RT6-11a Control A compatibility contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

import framework
from framework.session_compatibility import (
    CompatibilityMemberStatus,
    CompatibilityWarningMode,
    DeprecatedMemberPolicy,
    SessionCompatibilityMode,
    SessionCompatibilityProfile,
    StandaloneSessionKind,
    build_deprecated_member_policy,
    build_session_compatibility_profile,
    compatibility_members,
    warning_mode_for_member,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SessionCompatibilityControlATests(unittest.TestCase):
    def test_explicit_exports_are_exact_and_root_surface_is_unchanged(self) -> None:
        import framework.session_compatibility as compatibility

        self.assertEqual(
            tuple(compatibility.__all__),
            (
                "StandaloneSessionKind",
                "SessionCompatibilityMode",
                "CompatibilityMemberStatus",
                "CompatibilityWarningMode",
                "SessionCompatibilityProfile",
                "DeprecatedMemberPolicy",
                "build_session_compatibility_profile",
                "build_deprecated_member_policy",
                "compatibility_members",
                "warning_mode_for_member",
            ),
        )
        self.assertNotIn("SessionCompatibilityProfile", framework.__all__)
        self.assertFalse(hasattr(framework, "SessionCompatibilityProfile"))
        self.assertEqual(len(framework.__all__), 127)

    def test_enum_vocabularies_are_exact(self) -> None:
        self.assertEqual(
            tuple(value.value for value in StandaloneSessionKind),
            ("text_chat", "voice_input", "voice_output", "motion", "realtime"),
        )
        self.assertEqual(
            tuple(value.value for value in SessionCompatibilityMode),
            ("v5_standalone", "v5_skeleton", "v6_unified"),
        )
        self.assertEqual(
            tuple(value.value for value in CompatibilityMemberStatus),
            ("stable", "compatibility", "deprecated"),
        )
        self.assertEqual(
            tuple(value.value for value in CompatibilityWarningMode),
            ("silent", "deprecation_warning"),
        )

    def test_four_standalone_profiles_preserve_frozen_versions_and_owners(self) -> None:
        expected = {
            StandaloneSessionKind.TEXT_CHAT: ("4.0", "TextChatSession"),
            StandaloneSessionKind.VOICE_INPUT: ("5.2.0", "VoiceInputSession"),
            StandaloneSessionKind.VOICE_OUTPUT: (
                "v5.lazy_provider_adapter",
                "VoiceOutputSession",
            ),
            StandaloneSessionKind.MOTION: ("5.5.0", "MotionSession"),
        }
        for kind, (version, owner) in expected.items():
            with self.subTest(kind=kind):
                profile = build_session_compatibility_profile(kind)
                self.assertIs(profile.mode, SessionCompatibilityMode.V5_STANDALONE)
                self.assertEqual(profile.contract_version, version)
                self.assertEqual(profile.execution_owner, owner)
                self.assertTrue(profile.legacy_methods_preserved)
                self.assertTrue(profile.legacy_return_shapes_preserved)
                self.assertTrue(profile.legacy_event_shapes_preserved)
                self.assertTrue(profile.factory_signature_preserved)
                self.assertIs(profile.warning_mode, CompatibilityWarningMode.SILENT)
                self.assertFalse(profile.runtime_execution_performed)

    def test_realtime_default_and_explicit_unified_modes_are_distinct(self) -> None:
        legacy = build_session_compatibility_profile("realtime")
        unified = build_session_compatibility_profile(
            StandaloneSessionKind.REALTIME,
            unified_runtime_requested=True,
        )

        self.assertIs(legacy.mode, SessionCompatibilityMode.V5_SKELETON)
        self.assertIs(unified.mode, SessionCompatibilityMode.V6_UNIFIED)
        self.assertEqual(legacy.contract_version, "5.2.0")
        self.assertEqual(unified.contract_version, "5.2.0")
        self.assertEqual(legacy.execution_owner, "RealtimeSession")
        self.assertEqual(unified.execution_owner, "RealtimeSession")
        self.assertTrue(legacy.legacy_event_shapes_preserved)
        self.assertTrue(unified.legacy_event_shapes_preserved)
        self.assertFalse(legacy.runtime_execution_performed)
        self.assertFalse(unified.runtime_execution_performed)

    def test_non_realtime_profile_rejects_unified_runtime_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "only RealtimeSession"):
            build_session_compatibility_profile(
                StandaloneSessionKind.TEXT_CHAT,
                unified_runtime_requested=True,
            )
        with self.assertRaisesRegex(TypeError, "boolean"):
            build_session_compatibility_profile(
                StandaloneSessionKind.REALTIME,
                unified_runtime_requested=1,  # type: ignore[arg-type]
            )

    def test_profile_rejects_contract_breakage_or_execution(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot describe breakage"):
            SessionCompatibilityProfile(
                session_kind="voice_output",
                mode="v5_standalone",
                contract_version="v5.lazy_provider_adapter",
                execution_owner="VoiceOutputSession",
                legacy_return_shapes_preserved=False,
            )
        with self.assertRaisesRegex(ValueError, "cannot perform runtime execution"):
            SessionCompatibilityProfile(
                session_kind="motion",
                mode="v5_standalone",
                contract_version="5.5.0",
                execution_owner="MotionSession",
                runtime_execution_performed=True,
            )
        with self.assertRaisesRegex(ValueError, "warning-free"):
            SessionCompatibilityProfile(
                session_kind="voice_input",
                mode="v5_standalone",
                contract_version="5.2.0",
                execution_owner="VoiceInputSession",
                warning_mode="deprecation_warning",
            )

    def test_profiles_are_frozen_and_json_safe(self) -> None:
        profile = build_session_compatibility_profile("text_chat")
        with self.assertRaises(FrozenInstanceError):
            profile.mode = SessionCompatibilityMode.V6_UNIFIED  # type: ignore[misc]
        serialized = json.dumps(profile.as_dict(), sort_keys=True)
        self.assertIn('"contract_version": "4.0"', serialized)
        self.assertNotIn("credential", serialized.lower())
        self.assertNotIn("provider_payload", serialized.lower())

    def test_compatibility_member_inventories_cover_existing_v5_entry_points(self) -> None:
        expected = {
            StandaloneSessionKind.TEXT_CHAT: {"ask", "ask_stream", "interrupt"},
            StandaloneSessionKind.VOICE_INPUT: {
                "listen_result",
                "text_fallback_result",
                "transcribe_audio_result",
            },
            StandaloneSessionKind.VOICE_OUTPUT: {"speak", "create_output"},
            StandaloneSessionKind.MOTION: {"preflight", "apply_motion"},
            StandaloneSessionKind.REALTIME: {"run_turn", "on_legacy_event"},
        }
        for kind, required in expected.items():
            with self.subTest(kind=kind):
                members = compatibility_members(kind)
                self.assertIsInstance(members, tuple)
                self.assertTrue(required.issubset(members))
                self.assertIn("dispose", members)
                self.assertEqual(len(members), len(set(members)))

    def test_stable_and_compatibility_members_are_silent(self) -> None:
        self.assertIs(
            warning_mode_for_member(CompatibilityMemberStatus.STABLE),
            CompatibilityWarningMode.SILENT,
        )
        self.assertIs(
            warning_mode_for_member("compatibility"),
            CompatibilityWarningMode.SILENT,
        )
        self.assertIs(
            warning_mode_for_member(CompatibilityMemberStatus.DEPRECATED),
            CompatibilityWarningMode.DEPRECATION_WARNING,
        )

    def test_accepted_compatibility_member_cannot_be_declared_deprecated(self) -> None:
        for kind, member in (
            (StandaloneSessionKind.TEXT_CHAT, "ask"),
            (StandaloneSessionKind.VOICE_INPUT, "listen_result"),
            (StandaloneSessionKind.VOICE_OUTPUT, "create_output"),
            (StandaloneSessionKind.MOTION, "apply_motion"),
            (StandaloneSessionKind.REALTIME, "run_turn"),
        ):
            with self.subTest(kind=kind, member=member):
                with self.assertRaisesRegex(ValueError, "cannot be deprecated"):
                    build_deprecated_member_policy(
                        kind,
                        member,
                        replacement="replacement_method",
                    )

    def test_future_deprecation_policy_is_explicit_call_site_only(self) -> None:
        policy = build_deprecated_member_policy(
            StandaloneSessionKind.REALTIME,
            "future_legacy_method",
            replacement="replacement_method",
        )

        self.assertIs(policy.warning_mode, CompatibilityWarningMode.DEPRECATION_WARNING)
        self.assertEqual(policy.warning_category, "DeprecationWarning")
        self.assertEqual(policy.stacklevel, 2)
        self.assertFalse(policy.warn_on_import)
        self.assertFalse(policy.warn_on_construction)
        self.assertEqual(policy.earliest_removal_major_version, 7)
        self.assertTrue(policy.migration_evidence_required)
        self.assertNotIn("warning object", json.dumps(policy.as_dict()))

    def test_deprecation_policy_rejects_unsafe_warning_or_removal_rules(self) -> None:
        base = {
            "session_kind": StandaloneSessionKind.MOTION,
            "member_name": "future_legacy_method",
            "replacement": "replacement_method",
        }
        with self.assertRaisesRegex(ValueError, "DeprecationWarning"):
            DeprecatedMemberPolicy(**base, warning_category="FutureWarning")
        with self.assertRaisesRegex(ValueError, "application call site"):
            DeprecatedMemberPolicy(**base, stacklevel=1)
        with self.assertRaisesRegex(ValueError, "only on member use"):
            DeprecatedMemberPolicy(**base, warn_on_import=True)
        with self.assertRaisesRegex(ValueError, "before v7"):
            DeprecatedMemberPolicy(**base, earliest_removal_major_version=6)
        with self.assertRaisesRegex(ValueError, "requires migration evidence"):
            DeprecatedMemberPolicy(**base, migration_evidence_required=False)

    def test_control_a_is_provider_free_and_does_not_adopt_runtime(self) -> None:
        source = (PROJECT_ROOT / "framework/session_compatibility.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "import openai",
            "import pyvts",
            "import websocket",
            "import pyaudio",
            "warnings.warn",
            "thread",
            "subprocess",
        ):
            self.assertNotIn(forbidden, source)
        for relative in (
            "framework/facade.py",
            "framework/voice_input_session.py",
            "framework/audio/voice_output.py",
            "framework/motion_session.py",
            "framework/realtime_session.py",
        ):
            runtime_source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("session_compatibility", runtime_source)

    def test_public_versions_remain_unchanged(self) -> None:
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
        self.assertEqual(len(framework.__all__), 127)


if __name__ == "__main__":
    unittest.main()
