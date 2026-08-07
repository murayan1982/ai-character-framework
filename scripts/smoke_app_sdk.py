"""Smoke checks for the app-facing SDK boundary.

This script is offline-safe. It checks public imports, session metadata,
callback registration, interrupt boundaries, and SDK example importability
without calling external LLM provider APIs.

Run:

    python scripts/smoke_app_sdk.py
"""

from __future__ import annotations

import inspect

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


FORBIDDEN_IMPORTS_AFTER_FRAMEWORK_IMPORT = [
    "core.runtime",
    "core.session",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "elevenlabs",
    "live2d.vts_client",
]

PROVIDER_DETAIL_FIELD_NAMES = {
    "api_key",
    "endpoint",
    "model",
    "model_id",
    "provider",
    "provider_name",
    "provider_voice_id",
    "secret",
    "token",
    "voice_id",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _assert_no_forbidden_runtime_imports(context: str) -> None:
    imported_forbidden_modules = [
        module_name
        for module_name in FORBIDDEN_IMPORTS_AFTER_FRAMEWORK_IMPORT
        if module_name in sys.modules
    ]
    _assert(
        not imported_forbidden_modules,
        f"{context} should not load runtime/audio/VTS modules: "
        f"{imported_forbidden_modules}",
    )



def check_public_api_manifest() -> None:
    import framework
    from framework.public_api import (
        PROVIDER_COMPAT_LAZY_EXPORTS,
        PUBLIC_API_NAMES,
    )

    _assert(
        tuple(framework.__all__) == PUBLIC_API_NAMES,
        "framework.__all__ should match the canonical public API manifest",
    )
    _assert(
        len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)),
        "canonical public API manifest should not contain duplicates",
    )

    lazy_names = set(PROVIDER_COMPAT_LAZY_EXPORTS)
    missing_eager_names = sorted(
        name
        for name in PUBLIC_API_NAMES
        if name not in lazy_names and name not in framework.__dict__
    )
    _assert(
        not missing_eager_names,
        f"canonical eager public names should be bound: {missing_eager_names}",
    )
    _assert(
        not [name for name in lazy_names if name in framework.__dict__],
        "provider compatibility exports should remain lazy after root import",
    )

    _assert_no_forbidden_runtime_imports("canonical public API manifest")
    print("[OK] app SDK canonical public API manifest is stable")


def check_version_metadata() -> None:
    import framework
    from framework.capabilities import get_capabilities
    from framework.facade import TextChatSessionInfo
    from framework.audio.voice_output import VoiceOutputSessionInfo
    from framework.motion_session import MotionSessionInfo
    from framework.realtime_session import RealtimeSessionInfo
    from framework.version import (
        CAPABILITIES_SCHEMA_VERSION,
        FRAMEWORK_SOURCE_VERSION,
        LATEST_PUBLISHED_RELEASE,
        MOTION_API_VERSION,
        REALTIME_API_VERSION,
        REALTIME_CAPABILITIES_SCHEMA_VERSION,
        TEXT_CHAT_API_VERSION,
        VOICE_INPUT_API_VERSION,
        VOICE_OUTPUT_BOUNDARY_VERSION,
    )
    from framework.voice_input_session import VoiceInputSessionInfo

    _assert(
        framework.__version__ == FRAMEWORK_SOURCE_VERSION == "6.0.0.dev0",
        "framework source version should identify the v6 development line",
    )
    _assert(
        LATEST_PUBLISHED_RELEASE == "5.5.0",
        "latest published release should remain v5.5.0",
    )
    _assert(
        "__version__" not in framework.__all__,
        "framework.__version__ should not change the wildcard public API",
    )
    _assert(len(framework.__all__) == 127, "canonical public API count should be 127")
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
        tuple(framework.__all__[104:114])
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
        "typed event payload suffix drift",
    )
    _assert(
        tuple(framework.__all__[114:121])
        == (
            "CapabilitySnapshotScope",
            "RuntimeCapabilityState",
            "TextGenerationCapability",
            "RealtimeVoiceInputCapability",
            "RealtimeVoiceOutputCapability",
            "RealtimeMotionCapability",
            "RealtimeCapabilitySnapshot",
        ),
        "detailed capability suffix drift",
    )
    _assert(
        tuple(framework.__all__[121:124])
        == (
            "RealtimeSessionConfig",
            "RealtimeSessionConstructionStatus",
            "RealtimeSessionConstructionResult",
        ),
        "realtime session construction suffix drift",
    )
    _assert(
        tuple(framework.__all__[124:125]) == ("RealtimeTurnStartResult",),
        "realtime turn-start suffix drift",
    )
    _assert(
        tuple(framework.__all__[125:])
        == ("RealtimeExecutionErrorCode", "RealtimeExecutionError"),
        "realtime execution suffix drift",
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
    _assert(text_info.api_version == TEXT_CHAT_API_VERSION == "4.0", "text API version should remain 4.0")
    _assert(
        VoiceOutputSessionInfo().boundary_version
        == VOICE_OUTPUT_BOUNDARY_VERSION
        == "v5.lazy_provider_adapter",
        "voice output boundary version should remain compatible",
    )
    _assert(
        VoiceInputSessionInfo().api_version == VOICE_INPUT_API_VERSION == "5.2.0",
        "voice input API version should remain 5.2.0",
    )
    _assert(
        RealtimeSessionInfo().api_version == REALTIME_API_VERSION == "5.2.0",
        "realtime API version should remain 5.2.0",
    )
    _assert(
        MotionSessionInfo().api_version == MOTION_API_VERSION == "5.5.0",
        "motion API version should remain 5.5.0",
    )
    _assert(
        get_capabilities().schema_version
        == CAPABILITIES_SCHEMA_VERSION
        == "v5.1.capabilities",
        "capability schema should remain v5.1.capabilities",
    )
    _assert(
        REALTIME_CAPABILITIES_SCHEMA_VERSION == "v6.realtime_capabilities",
        "detailed realtime capability schema drift",
    )
    capabilities = get_capabilities()
    _assert(
        capabilities.realtime_snapshot is not None,
        "global detailed realtime capability snapshot should be attached",
    )
    _assert(
        capabilities.realtime_snapshot.snapshot_scope.value == "global",
        "global detailed capability scope drift",
    )
    _assert(
        capabilities.voice_input.reason_code == "mock_voice_input_available",
        "voice input current capability should be truthful",
    )
    _assert(
        capabilities.realtime.reason_code == "mock_realtime_available",
        "realtime current capability should be truthful",
    )
    _assert(
        capabilities.motion.reason_code == "mock_motion_available",
        "motion current capability should be truthful",
    )

    _assert_no_forbidden_runtime_imports("central version metadata")
    print("[OK] app SDK source and public contract version metadata are centralized")



def check_resource_resolution_signature() -> None:
    from framework import create_text_chat_session

    signature = inspect.signature(create_text_chat_session)
    _assert(
        list(signature.parameters)
        == ["preset", "character_name", "provider", "model", "project_root"],
        "text factory resource-root signature drifted",
    )
    for name in ("preset", "character_name", "provider", "model"):
        _assert(
            signature.parameters[name].kind
            is inspect.Parameter.POSITIONAL_OR_KEYWORD,
            f"text factory {name} compatibility changed",
        )
    _assert(
        signature.parameters["project_root"].kind
        is inspect.Parameter.KEYWORD_ONLY,
        "text factory project_root should be keyword-only",
    )
    _assert_no_forbidden_runtime_imports("resource-root signature")
    print("[OK] app SDK resource-root override preserves factory compatibility")

def check_public_sdk_imports() -> None:
    from framework import (
        CapabilitySnapshotScope,
        FacadeConfigError,
        FacadeError,
        FacadeProviderError,
        EventSequence,
        GenerationId,
        LifecycleTransitionError,
        LifecycleTransitionErrorCode,
        RealtimeCapabilitySnapshot,
        RealtimeMotionCapability,
        RealtimePhase,
        RealtimeEventPayloadKind,
        RealtimeVoiceInputCapability,
        RealtimeVoiceOutputCapability,
        RuntimeCapabilityState,
        TranscriptEventPayload,
        RecoveryAction,
        SessionId,
        TurnId,
        TurnOutcome,
        TextChatSession,
        TextGenerationCapability,
        TextChatSessionEvent,
        TextChatSessionInfo,
        TextChatStateChange,
        VoiceOutputRequest,
        VoiceOutputResult,
        VoiceOutputSession,
        VoiceOutputSessionInfo,
        create_text_chat_session,
        create_voice_output_session,
    )

    _assert(issubclass(FacadeConfigError, FacadeError), "config error should be public facade error")
    _assert(SessionId.new().startswith("fw_session_"), "SessionId should be root-public")
    _assert(TurnId.new().startswith("fw_turn_"), "TurnId should be root-public")
    _assert(GenerationId.new().startswith("fw_generation_"), "GenerationId should be root-public")
    _assert(EventSequence.first() == 1, "EventSequence should be root-public")
    _assert(RealtimePhase.IDLE.value == "idle", "RealtimePhase should be root-public")
    _assert(
        RealtimeEventPayloadKind.TRANSCRIPT.value == "transcript",
        "RealtimeEventPayloadKind should be root-public",
    )
    _assert(
        TranscriptEventPayload(text="hello", is_final=True).as_dict()["is_final"] is True,
        "TranscriptEventPayload should be root-public and public-safe",
    )
    fake_runtime = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        fake_runtime=True,
        unavailable_reason=None,
    )
    capability_snapshot = RealtimeCapabilitySnapshot(
        session_id=SessionId.new(),
        snapshot_scope=CapabilitySnapshotScope.SESSION,
        text_generation=TextGenerationCapability(runtime=fake_runtime),
        voice_input=RealtimeVoiceInputCapability(runtime=fake_runtime),
        voice_output=RealtimeVoiceOutputCapability(runtime=fake_runtime),
        motion=RealtimeMotionCapability(runtime=fake_runtime),
    )
    _assert(
        capability_snapshot.schema_version == "v6.realtime_capabilities",
        "RealtimeCapabilitySnapshot should be root-public",
    )
    _assert(TurnOutcome.REJECTED.value == "rejected", "TurnOutcome should be root-public")
    _assert(RecoveryAction.RESET_TURN.value == "reset_turn", "RecoveryAction should be root-public")
    _assert(
        LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION.value
        == "invalid_phase_transition",
        "LifecycleTransitionErrorCode should be root-public",
    )
    _assert(issubclass(LifecycleTransitionError, ValueError), "LifecycleTransitionError should be public")
    _assert(issubclass(FacadeProviderError, FacadeError), "provider error should be public facade error")
    _assert(TextChatSession is not None, "TextChatSession should be importable")
    _assert(TextChatSessionInfo is not None, "TextChatSessionInfo should be importable")
    _assert(TextChatSessionEvent is not None, "TextChatSessionEvent should be importable")
    _assert(TextChatStateChange is not None, "TextChatStateChange should be importable")
    _assert(VoiceOutputRequest is not None, "VoiceOutputRequest should be importable")
    _assert(VoiceOutputResult is not None, "VoiceOutputResult should be importable")
    _assert(VoiceOutputSession is not None, "VoiceOutputSession should be importable")
    _assert(VoiceOutputSessionInfo is not None, "VoiceOutputSessionInfo should be importable")
    _assert(create_text_chat_session is not None, "create_text_chat_session should be importable")
    _assert(create_voice_output_session is not None, "create_voice_output_session should be importable")

    _assert_no_forbidden_runtime_imports("public SDK import")
    print("[OK] app SDK public imports are available")


def check_session_info_contract() -> None:
    from framework.facade import _build_text_chat_info, _load_facade_config

    config = _load_facade_config(
        preset="text_chat",
        character_name="default",
    )
    info = _build_text_chat_info(
        config=config,
        provider=None,
        model=None,
    )

    _assert(info.api_version == "4.0", "SDK info should expose API version")
    _assert(info.session_type == "text_chat", "SDK info should expose text session type")
    _assert(info.supports_streaming, "SDK info should expose streaming support")
    _assert(info.supports_reset, "SDK info should expose reset support")
    _assert(info.supports_interrupt, "SDK info should expose interrupt boundary")
    _assert(info.supports_events, "SDK info should expose app-facing event callbacks")
    _assert(not info.supports_close, "SDK info should not expose close support yet")
    _assert(not info.supports_voice_input, "text SDK should not expose voice input")
    _assert(not info.supports_voice_output, "text SDK should not expose voice output")
    _assert(not info.supports_live2d, "text SDK should not expose Live2D")

    print("[OK] app SDK session info contract is stable")


def check_event_models() -> None:
    from framework import TextChatSessionEvent, TextChatStateChange

    event = TextChatSessionEvent(type="reset", data={})
    state_change = TextChatStateChange(old_state="idle", new_state="responding")

    _assert(event.type == "reset", "event should expose type")
    _assert(event.data == {}, "event should expose data")
    _assert(state_change.old_state == "idle", "state change should expose old state")
    _assert(state_change.new_state == "responding", "state change should expose new state")

    print("[OK] app SDK event models are stable")


def check_session_methods() -> None:
    from framework import RealtimeSession, TextChatSession

    _assert(hasattr(TextChatSession, "ask"), "SDK session should expose ask()")
    _assert(hasattr(TextChatSession, "ask_stream"), "SDK session should expose ask_stream()")
    _assert(hasattr(TextChatSession, "reset"), "SDK session should expose reset()")
    _assert(hasattr(TextChatSession, "interrupt"), "SDK session should expose interrupt()")
    _assert(hasattr(TextChatSession, "on_event"), "SDK session should expose on_event()")
    _assert(
        hasattr(TextChatSession, "on_state_change"),
        "SDK session should expose on_state_change()",
    )
    _assert(
        hasattr(RealtimeSession, "run_turn_async"),
        "realtime SDK should expose run_turn_async()",
    )
    _assert(
        hasattr(RealtimeSession, "run_turn_blocking"),
        "realtime SDK should expose run_turn_blocking()",
    )
    _assert(
        hasattr(RealtimeSession, "run_turn"),
        "realtime SDK should preserve legacy run_turn()",
    )

    print("[OK] app SDK session methods are available")


class _temporary_env:
    def __init__(self, updates: dict[str, str | None]) -> None:
        self._updates = updates
        self._originals: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self._updates.items():
            self._originals[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, exc_type, exc, tb) -> None:
        for key, value in self._originals.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def check_voice_output_boundary_contract() -> None:
    from dataclasses import fields, is_dataclass

    from framework import (
        VoiceOutputRequest,
        VoiceOutputResult,
        VoiceOutputSessionInfo,
        create_voice_output_session,
    )

    session = create_voice_output_session(
        project_root=PROJECT_ROOT,
        default_voice_profile_id="gentle_mina_default",
    )

    _assert(hasattr(session, "info"), "voice output session should expose info()")
    _assert(
        hasattr(session, "create_output"),
        "voice output session should expose create_output()",
    )

    info = session.info()
    _assert(
        isinstance(info, VoiceOutputSessionInfo),
        "voice output info should use public SDK type",
    )
    _assert(is_dataclass(info), "voice output info should be a dataclass model")
    _assert(info.session_type == "voice_output", "voice output info should expose session type")
    _assert(info.boundary_version == "v5.lazy_provider_adapter", "voice output info should expose lazy adapter boundary")
    _assert(info.supports_voice_output, "voice output info should expose voice output support")
    _assert(not info.real_tts_enabled, "mock-safe SDK info should not report real TTS enabled")
    _assert(not info.provider_configured, "mock-safe SDK info should not report provider configured")
    _assert(
        not info.provider_details_exposed,
        "voice output info should not expose provider details",
    )
    _assert(
        info.default_voice_profile_id == "gentle_mina_default",
        "voice output info should expose framework-level voice profile only",
    )

    info_field_names = {field.name for field in fields(info)}
    leaked_field_names = sorted(info_field_names & PROVIDER_DETAIL_FIELD_NAMES)
    _assert(
        not leaked_field_names,
        f"voice output info should not expose provider detail fields: {leaked_field_names}",
    )

    request = VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )
    result = session.create_output(request)
    _assert(
        isinstance(result, VoiceOutputResult),
        "voice output should return the public SDK result type",
    )
    _assert(result.request_state == "unavailable", "mock-safe voice output should be unavailable")
    _assert(not result.audio_ready, "mock-safe voice output should not produce audio")
    _assert(result.audio_format == "mp3", "voice output should preserve requested audio format")
    _assert(result.audio_url is None, "mock-safe voice output should not expose audio URL")
    _assert(
        result.audio_artifact_ref is None,
        "mock-safe voice output should not expose audio artifacts",
    )
    _assert(
        result.public_metadata.get("voice_profile_id") == "gentle_mina_default",
        "voice output result should retain framework-level voice profile metadata",
    )
    _assert(
        result.public_metadata.get("provider_details_exposed") == "false",
        "voice output result should explicitly keep provider details hidden",
    )

    _assert_no_forbidden_runtime_imports("voice output SDK boundary")
    print("[OK] app SDK voice output boundary is mock-safe")


def check_voice_output_session_lifecycle_hygiene() -> None:
    from framework import VoiceOutputRequest, create_voice_output_session

    request = VoiceOutputRequest(
        text="セッション終了後の安全な結果を確認します。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="lifecycle_smoke",
        language_code="ja",
    )

    session = create_voice_output_session(
        project_root=PROJECT_ROOT,
        default_voice_profile_id="gentle_mina_default",
    )
    _assert(callable(session.info), "voice output info must remain a method")
    _assert(not session.is_closed, "new voice output session should be open")

    session.close()
    session.close()
    _assert(session.is_closed, "voice output close() should be idempotent")

    create_result = session.create_output(request)
    speak_result = session.speak(request)
    for label, result in (
        ("create_output", create_result),
        ("speak", speak_result),
    ):
        _assert(
            result.request_state == "failed",
            f"{label} after close should return failed",
        )
        _assert(
            result.public_metadata.get("public_error_code") == "session_closed",
            f"{label} after close should expose session_closed",
        )
        _assert(not result.audio_ready, f"{label} after close must not expose audio")
        _assert(result.audio_url is None, f"{label} after close must not expose URL")
        _assert(
            result.audio_artifact_ref is None,
            f"{label} after close must not expose an artifact",
        )

    with create_voice_output_session(project_root=PROJECT_ROOT) as context_session:
        _assert(
            not context_session.is_closed,
            "context-managed voice output session should start open",
        )
    _assert(
        context_session.is_closed,
        "context manager exit should close voice output session",
    )

    _assert_no_forbidden_runtime_imports("voice output lifecycle hygiene")
    print("[OK] app SDK voice output lifecycle is single-path and idempotent")


def check_voice_output_lazy_provider_adapter() -> None:
    from framework import VoiceOutputRequest, create_voice_output_session

    with _temporary_env(
        {
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
            "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION": None,
            "ELEVENLABS_API_KEY": "",
            "VOICE_MASTER": "[]",
        }
    ):
        session = create_voice_output_session(
            project_root=PROJECT_ROOT,
            default_voice_profile_id="gentle_mina_default",
        )
        info = session.info()
        _assert(info.real_tts_enabled, "env opt-in should enable real TTS intent")
        _assert(info.provider_configured, "FW-owned provider should be considered configured")
        _assert(info.supports_audio_artifact_ref, "configured lazy provider should support artifacts")
        _assert(
            not info.provider_details_exposed,
            "lazy provider info should keep provider details hidden",
        )
        _assert_no_forbidden_runtime_imports("lazy provider info")

        result = session.create_output(
            VoiceOutputRequest(
                text="今日は少し早めに休むとよさそうです。",
                voice_profile_id="gentle_mina_default",
                requested_audio_format="mp3",
                utterance_purpose="daily_advice",
                language_code="ja",
            )
        )
        _assert(
            result.request_state == "skipped",
            "configured provider should stay guarded until execution is explicitly allowed",
        )
        _assert(not result.audio_ready, "guarded real TTS should not produce audio")
        _assert(
            result.public_metadata.get("provider_details_exposed") == "false",
            "lazy provider result should keep provider details hidden",
        )
        _assert_no_forbidden_runtime_imports("lazy provider guarded result")

    print("[OK] app SDK voice output lazy provider execution guard is mock-safe")


def _load_example_module(filename: str, module_name: str):
    import importlib.util

    example_path = PROJECT_ROOT / "examples" / filename
    spec = importlib.util.spec_from_file_location(module_name, example_path)
    _assert(spec is not None and spec.loader is not None, f"Could not load {filename}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def check_sdk_examples_importable() -> None:
    examples = [
        ("minimal_app_text_chat.py", "minimal_app_text_chat_sdk_smoke", "build_app"),
        ("app_error_handling.py", "app_error_handling_sdk_smoke", "run_invalid_preset_demo"),
        ("app_streaming_text_chat.py", "app_streaming_text_chat_sdk_smoke", "build_app"),
        ("app_reset_text_chat.py", "app_reset_text_chat_sdk_smoke", "build_app"),
        ("app_session_info.py", "app_session_info_sdk_smoke", "run_session_info_demo"),
        ("app_state_events.py", "app_state_events_sdk_smoke", "run_state_events_demo"),
        ("app_interrupt_text_chat.py", "app_interrupt_text_chat_sdk_smoke", "run_interrupt_demo"),
        (
            "app_voice_output_integration.py",
            "app_voice_output_integration_sdk_smoke",
            "run_voice_output_integration_demo",
        ),
    ]

    for filename, module_name, expected_attr in examples:
        module = _load_example_module(filename, module_name)
        _assert(
            hasattr(module, expected_attr),
            f"{filename} should expose {expected_attr}",
        )
        _assert_no_forbidden_runtime_imports(f"{filename} import")

    print("[OK] app SDK examples are importable")


def main() -> None:
    check_public_api_manifest()
    check_version_metadata()
    check_resource_resolution_signature()
    check_public_sdk_imports()
    check_session_info_contract()
    check_event_models()
    check_session_methods()
    check_voice_output_boundary_contract()
    check_voice_output_session_lifecycle_hygiene()
    check_voice_output_lazy_provider_adapter()
    check_sdk_examples_importable()


if __name__ == "__main__":
    main()
