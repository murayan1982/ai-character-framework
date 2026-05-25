"""Smoke checks for the app-facing SDK boundary.

This script is offline-safe. It checks public imports, session metadata,
callback registration, interrupt boundaries, and SDK example importability
without calling external LLM provider APIs.

Run:

    python scripts/smoke_app_sdk.py
"""

from __future__ import annotations

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


def check_public_sdk_imports() -> None:
    from framework import (
        FacadeConfigError,
        FacadeError,
        FacadeProviderError,
        TextChatSession,
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
    from framework import TextChatSession

    _assert(hasattr(TextChatSession, "ask"), "SDK session should expose ask()")
    _assert(hasattr(TextChatSession, "ask_stream"), "SDK session should expose ask_stream()")
    _assert(hasattr(TextChatSession, "reset"), "SDK session should expose reset()")
    _assert(hasattr(TextChatSession, "interrupt"), "SDK session should expose interrupt()")
    _assert(hasattr(TextChatSession, "on_event"), "SDK session should expose on_event()")
    _assert(
        hasattr(TextChatSession, "on_state_change"),
        "SDK session should expose on_state_change()",
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


def check_voice_output_lazy_provider_adapter() -> None:
    from framework import VoiceOutputRequest, create_voice_output_session

    with _temporary_env(
        {
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
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
            result.request_state == "unavailable",
            "missing provider settings should produce safe unavailable result",
        )
        _assert(not result.audio_ready, "unconfigured real TTS should not produce audio")
        _assert(
            result.public_metadata.get("provider_details_exposed") == "false",
            "lazy provider result should keep provider details hidden",
        )
        _assert_no_forbidden_runtime_imports("lazy provider unavailable result")

    print("[OK] app SDK voice output lazy provider adapter is mock-safe")


def _load_example_module(filename: str, module_name: str):
    import importlib.util

    example_path = PROJECT_ROOT / "examples" / filename
    spec = importlib.util.spec_from_file_location(module_name, example_path)
    _assert(spec is not None and spec.loader is not None, f"Could not load {filename}")

    module = importlib.util.module_from_spec(spec)
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
    check_public_sdk_imports()
    check_session_info_contract()
    check_event_models()
    check_session_methods()
    check_voice_output_boundary_contract()
    check_voice_output_lazy_provider_adapter()
    check_sdk_examples_importable()


if __name__ == "__main__":
    main()