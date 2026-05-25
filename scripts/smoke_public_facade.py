"""Smoke checks for the public framework facade.

Default mode is offline-safe and does not call an LLM provider API:

    python scripts/smoke_public_facade.py

Optional live LLM check, requiring API keys in .env:

    python scripts/smoke_public_facade.py --ask "こんにちは。短く返して"

Optional live LLM check with direct provider mode:

    python scripts/smoke_public_facade.py --provider openai --model gpt-4o-mini --ask "こんにちは。短く返して"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_PUBLIC_API = [
    "FacadeConfigError",
    "FacadeError",
    "FacadeProviderError",
    "TextChatSession",
    "TextChatSessionEvent",
    "TextChatSessionInfo",
    "TextChatStateChange",
    "VoiceOutputRequest",
    "VoiceOutputResult",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceSynthesisRequest",
    "VoiceSynthesisResult",
    "create_text_chat_session",
    "create_voice_output_session",
]

FORBIDDEN_IMPORTS_AFTER_FRAMEWORK_IMPORT = [
    "core.runtime",
    "core.session",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "live2d.vts_client",
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_import_boundary() -> None:
    import framework

    _assert(
        list(framework.__all__) == EXPECTED_PUBLIC_API,
        f"Unexpected framework.__all__: {framework.__all__!r}",
    )

    imported_forbidden_modules = [
        module_name
        for module_name in FORBIDDEN_IMPORTS_AFTER_FRAMEWORK_IMPORT
        if module_name in sys.modules
    ]
    _assert(
        not imported_forbidden_modules,
        "framework import should not load runtime/audio/VTS modules: "
        f"{imported_forbidden_modules}",
    )

    print("[OK] import framework exposes the expected public API")
    print("[OK] import framework does not load runtime/audio/VTS modules")


def check_text_only_config_boundary() -> None:
    # This intentionally checks the internal facade boundary without creating an
    # actual LLM instance, so it can run without provider API keys.
    from framework.facade import FacadeConfigError, _load_facade_config

    text_config = _load_facade_config(
        preset="text_chat",
        character_name="default",
    )
    _assert(text_config.app_preset == "text_chat", "text_chat preset was not loaded")
    _assert(not text_config.input_voice_enabled, "text_chat should not enable voice input")
    _assert(not text_config.output_voice_enabled, "text_chat should not enable voice output")
    _assert(not text_config.vts_enabled, "text_chat should not enable VTS")
    _assert(text_config.tts_provider == "none", "text_chat should not enable TTS")

    try:
        _load_facade_config(
            preset="voice_vts",
            character_name="default",
        )
    except FacadeConfigError as e:
        _assert(
            "text-only presets only" in str(e),
            f"Unexpected voice_vts validation error: {e}",
        )
    else:
        raise AssertionError("voice_vts should be rejected by the text facade")

    print("[OK] text_chat is accepted by the text facade boundary")
    print("[OK] voice_vts is rejected by the text facade boundary")


def check_provider_model_resolution() -> None:
    # This checks facade provider/model argument handling without creating
    # provider clients or requiring API keys.
    from framework.facade import FacadeProviderError, _resolve_provider_model

    _assert(
        _resolve_provider_model("openai", None) == ("openai", "gpt-4o-mini"),
        "openai should resolve to the registered default model",
    )
    _assert(
        _resolve_provider_model("gemini", "custom-gemini-model")
        == ("google", "custom-gemini-model"),
        "gemini alias should resolve to internal google provider",
    )
    _assert(
        _resolve_provider_model("grok", "custom-grok-model")
        == ("xai", "custom-grok-model"),
        "grok alias should resolve to internal xai provider",
    )

    try:
        _resolve_provider_model("unknown-provider", None)
    except FacadeProviderError as e:
        _assert(
            "Unsupported facade provider" in str(e),
            f"Unexpected provider validation error: {e}",
        )
    else:
        raise AssertionError("unknown provider should be rejected")

    print("[OK] facade provider/model arguments resolve without creating clients")


def check_session_info_model() -> None:
    # Session info is built from facade arguments and RuntimeConfig without
    # creating provider clients or exposing the internal RuntimeConfig object.
    from framework import (
        TextChatSession,
        TextChatSessionEvent,
        TextChatSessionInfo,
        TextChatStateChange,
    )
    from framework.facade import _build_text_chat_info, _load_facade_config

    _assert(hasattr(TextChatSession, "interrupt"), "text session should expose interrupt()")
    _assert(hasattr(TextChatSession, "on_event"), "text session should expose on_event()")
    _assert(
        hasattr(TextChatSession, "on_state_change"),
        "text session should expose on_state_change()",
    )

    event = TextChatSessionEvent(type="reset", data={})
    state_event = TextChatStateChange(old_state="idle", new_state="responding")
    _assert(event.type == "reset", "event type should be public")
    _assert(event.data == {}, "event data should be public")
    _assert(state_event.old_state == "idle", "state change should expose old state")
    _assert(
        state_event.new_state == "responding",
        "state change should expose new state",
    )

    config = _load_facade_config(
        preset="text_chat",
        character_name="default",
    )

    default_info = _build_text_chat_info(
        config=config,
        provider=None,
        model=None,
    )
    _assert(isinstance(default_info, TextChatSessionInfo), "info should use public type")
    _assert(default_info.preset == "text_chat", "info should expose preset")
    _assert(default_info.character_name == "default", "info should expose character")
    _assert(default_info.llm_mode == "default_route", "default mode should use route")
    _assert(default_info.route_name == "chat", "default route name should be chat")
    _assert(default_info.provider is None, "default route should hide provider")
    _assert(default_info.model is None, "default route should hide model")
    _assert(default_info.api_version == "4.0", "info should expose API version")
    _assert(default_info.session_type == "text_chat", "info should expose session type")
    _assert(default_info.supports_streaming, "text facade should support streaming")
    _assert(default_info.supports_reset, "text facade should support reset")
    _assert(default_info.supports_interrupt, "text facade should expose interrupt boundary")
    _assert(default_info.supports_events, "text facade should expose event callbacks")
    _assert(not default_info.supports_close, "text facade should not expose close support yet")
    _assert(not default_info.supports_voice_input, "text facade should not expose voice input support")
    _assert(not default_info.supports_voice_output, "text facade should not expose voice output support")
    _assert(not default_info.supports_live2d, "text facade should not expose Live2D support")
    
    direct_info = _build_text_chat_info(
        config=config,
        provider="gemini",
        model="custom-gemini-model",
    )
    _assert(isinstance(direct_info, TextChatSessionInfo), "info should use public type")
    _assert(direct_info.llm_mode == "direct_provider", "direct mode should be explicit")
    _assert(direct_info.provider == "google", "provider aliases should be normalized")
    _assert(direct_info.model == "custom-gemini-model", "model override should be exposed")
    _assert(direct_info.route_name is None, "direct provider mode should not expose route")
    _assert(direct_info.api_version == "4.0", "direct info should expose API version")
    _assert(direct_info.session_type == "text_chat", "direct info should expose session type")
    _assert(direct_info.supports_streaming, "direct info should support streaming")
    _assert(direct_info.supports_reset, "direct info should support reset")
    _assert(direct_info.supports_interrupt, "direct info should expose interrupt boundary")
    _assert(direct_info.supports_events, "direct info should expose event callbacks")
    _assert(not direct_info.supports_voice_input, "direct info should not expose voice input support")
    _assert(not direct_info.supports_voice_output, "direct info should not expose voice output support")
    _assert(not direct_info.supports_live2d, "direct info should not expose Live2D support")

    print("[OK] TextChatSessionInfo exposes stable public session metadata")


def check_voice_output_public_contract() -> None:
    # The voice output boundary should be public and mock-safe without loading
    # provider-specific TTS implementations or requiring API keys.
    from framework import (
        VoiceOutputRequest,
        VoiceOutputResult,
        VoiceOutputSession,
        VoiceOutputSessionInfo,
        VoiceSynthesisRequest,
        VoiceSynthesisResult,
        create_voice_output_session,
    )

    _assert(
        hasattr(VoiceOutputSession, "info"),
        "voice output session should expose info()",
    )
    _assert(
        hasattr(VoiceOutputSession, "create_output"),
        "voice output session should expose create_output()",
    )

    session = create_voice_output_session()
    info = session.info()
    _assert(
        isinstance(info, VoiceOutputSessionInfo),
        "voice output info should use public type",
    )
    _assert(info.session_type == "voice_output", "voice output info should expose session type")
    _assert(
        info.provider_details_exposed is False,
        "voice output info should not expose provider details",
    )

    request = VoiceOutputRequest(
        text="こんにちは。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="demo",
        language_code="ja",
    )
    result = session.create_output(request)
    _assert(
        isinstance(result, VoiceOutputResult),
        "voice output result should use public type",
    )
    _assert(result.request_state == "unavailable", "mock-safe TTS should be unavailable")
    _assert(not result.audio_ready, "mock-safe TTS should not report audio ready")
    _assert(result.audio_format == "mp3", "voice output result should preserve requested format")
    _assert(result.audio_url is None, "mock-safe TTS should not expose an audio URL")
    _assert(result.audio_artifact_ref is None, "mock-safe TTS should not expose an audio artifact")

    synthesis_request = VoiceSynthesisRequest(
        text=request.text,
        voice_profile_id=request.voice_profile_id,
        requested_audio_format=request.requested_audio_format,
        utterance_purpose=request.utterance_purpose,
        language_code=request.language_code,
    )
    synthesis_result = VoiceSynthesisResult(
        request_state=result.request_state,
        audio_ready=result.audio_ready,
        audio_format=result.audio_format,
        audio_url=result.audio_url,
        audio_artifact_ref=result.audio_artifact_ref,
    )
    _assert(
        synthesis_request.text == request.text,
        "voice synthesis request should expose text",
    )
    _assert(
        synthesis_result.request_state == result.request_state,
        "voice synthesis result should expose request state",
    )

    _assert_no_forbidden_runtime_imports("voice output public contract")
    print("[OK] voice output public contract is mock-safe")


def _load_example_module(filename: str, module_name: str):
    """Import an example file by path without running it as a script."""
    import importlib.util

    example_path = PROJECT_ROOT / "examples" / filename
    spec = importlib.util.spec_from_file_location(module_name, example_path)
    _assert(spec is not None and spec.loader is not None, "Could not load example spec")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def check_minimal_app_example_import() -> None:
    # The app integration example should be importable without creating an LLM
    # client or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "minimal_app_text_chat.py",
        "minimal_app_text_chat_smoke",
    )

    _assert(
        hasattr(module, "MinimalTextChatApp"),
        "minimal app example should expose MinimalTextChatApp",
    )
    _assert(
        hasattr(module, "build_app"),
        "minimal app example should expose build_app",
    )

    _assert_no_forbidden_runtime_imports("minimal app example import")
    print("[OK] minimal app integration example is importable")


def check_error_handling_example_import() -> None:
    # The error handling example should also be importable without creating
    # provider clients or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "app_error_handling.py",
        "app_error_handling_smoke",
    )

    _assert(
        hasattr(module, "run_invalid_preset_demo"),
        "error handling example should expose run_invalid_preset_demo",
    )
    _assert(
        hasattr(module, "run_invalid_provider_demo"),
        "error handling example should expose run_invalid_provider_demo",
    )

    _assert_no_forbidden_runtime_imports("error handling example import")
    print("[OK] error handling example is importable")


def check_streaming_example_import() -> None:
    # The streaming example should be importable without creating provider
    # clients or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "app_streaming_text_chat.py",
        "app_streaming_text_chat_smoke",
    )

    _assert(
        hasattr(module, "StreamingTextChatApp"),
        "streaming example should expose StreamingTextChatApp",
    )
    _assert(
        hasattr(module, "build_app"),
        "streaming example should expose build_app",
    )

    _assert_no_forbidden_runtime_imports("streaming example import")
    print("[OK] streaming text chat example is importable")


def check_reset_example_import() -> None:
    # The reset example should be importable without creating provider clients
    # or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "app_reset_text_chat.py",
        "app_reset_text_chat_smoke",
    )

    _assert(
        hasattr(module, "ResettableTextChatApp"),
        "reset example should expose ResettableTextChatApp",
    )
    _assert(
        hasattr(module, "build_app"),
        "reset example should expose build_app",
    )

    _assert_no_forbidden_runtime_imports("reset example import")
    print("[OK] reset text chat example is importable")


def check_session_info_example_import() -> None:
    # The session info example should be importable without creating provider
    # clients or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "app_session_info.py",
        "app_session_info_smoke",
    )

    _assert(
        hasattr(module, "run_session_info_demo"),
        "session info example should expose run_session_info_demo",
    )

    _assert_no_forbidden_runtime_imports("session info example import")
    print("[OK] session info example is importable")


def check_state_events_example_import() -> None:
    # The state/events example should be importable without creating provider
    # clients or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "app_state_events.py",
        "app_state_events_smoke",
    )

    _assert(
        hasattr(module, "run_state_events_demo"),
        "state/events example should expose run_state_events_demo",
    )

    _assert_no_forbidden_runtime_imports("state/events example import")
    print("[OK] state/events example is importable")


def check_interrupt_example_import() -> None:
    # The interrupt example should be importable without creating provider
    # clients or loading the full runtime/audio/VTS stack.
    module = _load_example_module(
        "app_interrupt_text_chat.py",
        "app_interrupt_text_chat_smoke",
    )

    _assert(
        hasattr(module, "run_interrupt_demo"),
        "interrupt example should expose run_interrupt_demo",
    )

    _assert_no_forbidden_runtime_imports("interrupt example import")
    print("[OK] interrupt example is importable")


def check_live_text_turn(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    from framework import create_text_chat_session

    session = create_text_chat_session(
        preset="text_chat",
        character_name="default",
        provider=provider,
        model=model,
    )
    response = session.ask(prompt)

    _assert(response.strip() != "", "LLM response was empty")
    print(f"[OK] facade returned one live text response: {session.info}")
    print(response)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run smoke checks for the public framework facade.",
    )
    parser.add_argument(
        "--ask",
        metavar="TEXT",
        help="Run an optional live LLM check with the provided prompt.",
    )
    parser.add_argument(
        "--provider",
        help="Optional provider override for the live LLM check.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override for the live LLM check.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])

    check_import_boundary()
    check_text_only_config_boundary()
    check_provider_model_resolution()
    check_session_info_model()
    check_voice_output_public_contract()
    check_minimal_app_example_import()
    check_error_handling_example_import()
    check_streaming_example_import()
    check_reset_example_import()
    check_session_info_example_import()
    check_state_events_example_import()
    check_interrupt_example_import()
    if args.ask:
        check_live_text_turn(
            args.ask,
            provider=args.provider,
            model=args.model,
        )
    else:
        print("[SKIP] live LLM check skipped; pass --ask to enable it")


if __name__ == "__main__":
    main()
