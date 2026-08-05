"""FW-RT6-0b Control C central version metadata smoke.

This smoke is offline-safe. It verifies that source/development version
metadata and frozen v4/v5 public contract versions are defined centrally
while preserving the original 95-name prefix or importing provider/runtime
implementations.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FORBIDDEN_IMPORTS = (
    "core.runtime",
    "core.session",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "elevenlabs",
    "live2d.vts_client",
    "pyvts",
    "websockets",
)

VERSION_LITERAL_TARGETS = {
    "framework/facade.py": ("TextChatSessionInfo", "api_version", "TEXT_CHAT_API_VERSION"),
    "framework/audio/voice_output.py": (
        "VoiceOutputSessionInfo",
        "boundary_version",
        "VOICE_OUTPUT_BOUNDARY_VERSION",
    ),
    "framework/voice_input_session.py": (
        "VoiceInputSessionInfo",
        "api_version",
        "VOICE_INPUT_API_VERSION",
    ),
    "framework/realtime_session.py": (
        "RealtimeSessionInfo",
        "api_version",
        "REALTIME_API_VERSION",
    ),
    "framework/motion_session.py": (
        "MotionSessionInfo",
        "api_version",
        "MOTION_API_VERSION",
    ),
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _class_field_default_name(
    source_path: Path,
    class_name: str,
    field_name: str,
) -> str | None:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            if not isinstance(statement.target, ast.Name):
                continue
            if statement.target.id != field_name:
                continue
            if isinstance(statement.value, ast.Name):
                return statement.value.id
            return None
    raise AssertionError(f"{class_name}.{field_name} was not found in {source_path}")


def check_central_module() -> None:
    from framework.version import (
        CAPABILITIES_SCHEMA_VERSION,
        FRAMEWORK_SOURCE_VERSION,
        LATEST_PUBLISHED_RELEASE,
        MOTION_API_VERSION,
        REALTIME_API_VERSION,
        TEXT_CHAT_API_VERSION,
        VOICE_INPUT_API_VERSION,
        VOICE_OUTPUT_BOUNDARY_VERSION,
    )

    _assert(FRAMEWORK_SOURCE_VERSION == "6.0.0.dev0", "source version should be v6 dev")
    _assert(LATEST_PUBLISHED_RELEASE == "5.5.0", "latest release should remain v5.5.0")
    _assert(TEXT_CHAT_API_VERSION == "4.0", "text API version changed")
    _assert(
        VOICE_OUTPUT_BOUNDARY_VERSION == "v5.lazy_provider_adapter",
        "voice output boundary version changed",
    )
    _assert(VOICE_INPUT_API_VERSION == "5.2.0", "voice input API version changed")
    _assert(REALTIME_API_VERSION == "5.2.0", "realtime API version changed")
    _assert(MOTION_API_VERSION == "5.5.0", "motion API version changed")
    _assert(
        CAPABILITIES_SCHEMA_VERSION == "v5.1.capabilities",
        "capability schema version changed",
    )
    print("[OK] central version module preserves source and compatibility values")


def check_module_defaults_use_constants() -> None:
    for relative_path, (class_name, field_name, constant_name) in VERSION_LITERAL_TARGETS.items():
        actual_name = _class_field_default_name(
            PROJECT_ROOT / relative_path,
            class_name,
            field_name,
        )
        _assert(
            actual_name == constant_name,
            f"{class_name}.{field_name} should use {constant_name}, got {actual_name}",
        )

    capabilities_source = (PROJECT_ROOT / "framework/capabilities.py").read_text(
        encoding="utf-8"
    )
    _assert(
        "schema_version=CAPABILITIES_SCHEMA_VERSION" in capabilities_source,
        "capability snapshot should use the central schema constant",
    )
    print("[OK] public session and capability defaults use central constants")


def check_runtime_values() -> None:
    import framework
    from framework.audio.voice_output import VoiceOutputSessionInfo
    from framework.capabilities import get_capabilities
    from framework.facade import TextChatSessionInfo
    from framework.motion_session import MotionSessionInfo
    from framework.realtime_session import RealtimeSessionInfo
    from framework.voice_input_session import VoiceInputSessionInfo

    _assert(framework.__version__ == "6.0.0.dev0", "framework.__version__ mismatch")
    _assert("__version__" not in framework.__all__, "__version__ changed wildcard API")
    _assert(len(framework.__all__) == 114, "root-public name count drift")
    _assert(
        tuple(framework.__all__[95:99])
        == ("SessionId", "TurnId", "GenerationId", "EventSequence"),
        "public identity position drift",
    )
    _assert(
        tuple(framework.__all__[99:104])
        == (
            "RealtimePhase",
            "TurnOutcome",
            "RecoveryAction",
            "LifecycleTransitionErrorCode",
            "LifecycleTransitionError",
        ),
        "public lifecycle position drift",
    )
    _assert(
        tuple(framework.__all__[104:])
        == (
            "RealtimeEventPayloadKind",
            "LifecycleEventPayload",
            "TranscriptEventPayload",
            "ResponseEventPayload",
            "SynthesisEventPayload",
            "AudioEventPayload",
            "MotionEventPayload",
            "InterruptEventPayload",
            "DiagnosticEventPayload",
            "RealtimeEventPayload",
        ),
        "typed realtime event payload suffix drift",
    )

    text_info = TextChatSessionInfo(
        preset="text_chat",
        character_name="default",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="default_route",
        provider=None,
        model=None,
        route_name="chat",
    )
    _assert(text_info.api_version == "4.0", "text API version changed")
    _assert(
        VoiceOutputSessionInfo().boundary_version == "v5.lazy_provider_adapter",
        "voice output boundary version changed",
    )
    _assert(VoiceInputSessionInfo().api_version == "5.2.0", "voice input API changed")
    _assert(RealtimeSessionInfo().api_version == "5.2.0", "realtime API changed")
    _assert(MotionSessionInfo().api_version == "5.5.0", "motion API changed")
    _assert(
        get_capabilities().schema_version == "v5.1.capabilities",
        "capability schema changed",
    )

    imported = [name for name in FORBIDDEN_IMPORTS if name in sys.modules]
    _assert(not imported, f"version inspection imported forbidden modules: {imported}")
    print("[OK] runtime metadata values are unchanged and lifecycle exports are additive")


def check_docs() -> None:
    for relative_path in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-0b-C-VERSION-METADATA:BEGIN" in text,
            f"{relative_path} should record Control C",
        )
        _assert(
            "6.0.0.dev0" in text and "5.5.0" in text,
            f"{relative_path} should distinguish source and published versions",
        )
    print("[OK] public docs distinguish source version from frozen API versions")


def main() -> None:
    check_central_module()
    check_module_defaults_use_constants()
    check_runtime_values()
    check_docs()

    print("v600_version_metadata_status: implemented-awaiting-review")
    print("v600_framework_source_version: 6.0.0.dev0")
    print("v600_latest_published_release: 5.5.0")
    print("v600_root_public_name_count: 114")
    print("v600_public_api_values_changed: additive-identity-lifecycle-and-event-payloads-only")
    print("v600_capability_truthfulness_changed: False")
    print("v600_provider_sdk_imported: False")
    print("v600_network_execution: False")
    print("v600_provider_execution: False")
    print("v600_next_control: FW-RT6-1c Control B")
    print("v600_next_control_authorized: False")
    print("[OK] central version metadata smoke passed with additive typed event payload models")


if __name__ == "__main__":
    main()
