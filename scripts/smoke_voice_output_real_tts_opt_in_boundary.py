"""Smoke checks for the real TTS opt-in boundary.

This script is intentionally mock-safe. It verifies the public FW voice output
boundary around real TTS opt-in without making provider network calls, importing
legacy TTS playback internals, or requiring provider credentials.
"""

from __future__ import annotations

import inspect
import os
import sys
from dataclasses import fields
from pathlib import Path
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


FORBIDDEN_IMPORTS = [
    "core.runtime",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "elevenlabs",
    "elevenlabs.client",
    "live2d.vts_client",
]

FORBIDDEN_PUBLIC_FIELD_NAMES = {
    "api_key",
    "api_token",
    "endpoint",
    "model_id",
    "provider",
    "provider_name",
    "provider_options",
    "provider_request",
    "provider_response",
    "provider_voice_id",
    "secret",
    "token",
    "voice_id",
}

ALLOWED_PROVIDER_METADATA_KEYS = {
    "provider_details_exposed",
    "provider_status",
}

OPT_IN_ENV_KEYS = {
    "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
    "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
    "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR",
    "ELEVENLABS_API_KEY",
    "VOICE_MASTER",
    "SELECT_VOICE_INDEX",
    "SELECT_TTS_MODEL_INDEX",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class temporary_env:
    def __init__(self, updates: Mapping[str, str | None]) -> None:
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


def _clear_opt_in_env() -> dict[str, str | None]:
    return {key: None for key in OPT_IN_ENV_KEYS}


def _assert_no_forbidden_imports(context: str) -> None:
    imported = [module_name for module_name in FORBIDDEN_IMPORTS if module_name in sys.modules]
    _assert(not imported, f"{context} should not import runtime/provider internals: {imported}")


def _assert_metadata_hides_provider_details(metadata: Mapping[str, object], context: str) -> None:
    leaked_keys = sorted(
        key
        for key in metadata.keys()
        if key in FORBIDDEN_PUBLIC_FIELD_NAMES
        or (key.startswith("provider_") and key not in ALLOWED_PROVIDER_METADATA_KEYS)
    )
    _assert(not leaked_keys, f"{context} leaked provider detail metadata keys: {leaked_keys}")
    _assert(
        metadata.get("provider_details_exposed") == "false",
        f"{context} should explicitly keep provider details hidden",
    )


def _assert_public_dataclass_fields_hide_provider_details() -> None:
    from framework import VoiceOutputRequest, VoiceOutputResult, VoiceOutputSessionInfo

    for model in (VoiceOutputRequest, VoiceOutputResult, VoiceOutputSessionInfo):
        field_names = {field.name for field in fields(model)}
        leaked = sorted(field_names & FORBIDDEN_PUBLIC_FIELD_NAMES)
        _assert(not leaked, f"{model.__name__} exposes provider-specific fields: {leaked}")


def _assert_example_signature_hides_provider_details() -> None:
    from examples import app_voice_output_integration as example

    public_callables = [
        example.DailyAdviceVoiceOutput,
        example.DailyRhythmCompanionVoiceOutputBridge,
        example.build_drc_voice_output_bridge,
        example.run_voice_output_integration_demo,
    ]

    for callable_obj in public_callables:
        signature = inspect.signature(callable_obj)
        leaked = sorted(set(signature.parameters) & FORBIDDEN_PUBLIC_FIELD_NAMES)
        _assert(
            not leaked,
            f"{callable_obj.__name__} exposes provider-specific parameters: {leaked}",
        )


def _build_request():
    from framework import VoiceOutputRequest

    return VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )


def check_default_boundary_is_not_real_tts() -> None:
    from framework import create_voice_output_session

    with temporary_env(_clear_opt_in_env()):
        session = create_voice_output_session(
            project_root=PROJECT_ROOT,
            default_voice_profile_id="gentle_mina_default",
        )
        info = session.info()
        _assert(not info.real_tts_enabled, "default session must not enable real TTS")
        _assert(not info.provider_configured, "default session must not configure provider")
        _assert(not info.provider_details_exposed, "default info must hide provider details")

        result = session.create_output(_build_request())
        _assert(result.request_state == "unavailable", "default output should be unavailable")
        _assert(not result.audio_ready, "default output should not create audio")
        _assert(result.audio_artifact_ref is None, "default output should not expose artifact ref")
        _assert_metadata_hides_provider_details(result.public_metadata, "default output")
        _assert_no_forbidden_imports("default voice output boundary")

    print("[OK] voice output real TTS opt-in defaults are safe")


def check_explicit_opt_in_without_provider_is_unavailable() -> None:
    from framework import create_voice_output_session

    with temporary_env(
        {
            **_clear_opt_in_env(),
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
        }
    ):
        session = create_voice_output_session(project_root=PROJECT_ROOT)
        info = session.info()
        _assert(info.real_tts_enabled, "opt-in env should mark real TTS intent")
        _assert(not info.provider_configured, "missing provider should not be configured")
        _assert(not info.provider_details_exposed, "provider details must stay hidden")

        result = session.create_output(_build_request())
        _assert(result.request_state == "unavailable", "missing provider should be unavailable")
        _assert(not result.audio_ready, "missing provider should not create audio")
        _assert_metadata_hides_provider_details(result.public_metadata, "missing provider output")
        _assert_no_forbidden_imports("explicit opt-in without provider")

    print("[OK] voice output real TTS opt-in without provider is unavailable")


def check_unsupported_provider_is_unavailable() -> None:
    from framework import create_voice_output_session

    with temporary_env(
        {
            **_clear_opt_in_env(),
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "unsupported-provider",
        }
    ):
        session = create_voice_output_session(project_root=PROJECT_ROOT)
        info = session.info()
        _assert(info.real_tts_enabled, "unsupported provider check should keep real TTS intent")
        _assert(not info.provider_configured, "unsupported provider should not be configured")

        result = session.create_output(_build_request())
        _assert(result.request_state == "unavailable", "unsupported provider should be unavailable")
        _assert(not result.audio_ready, "unsupported provider should not create audio")
        _assert_metadata_hides_provider_details(result.public_metadata, "unsupported provider output")
        _assert_no_forbidden_imports("unsupported provider")

    print("[OK] voice output unsupported provider remains safe")


def check_supported_provider_missing_settings_does_not_execute_provider_sdk() -> None:
    from framework import create_voice_output_session

    with temporary_env(
        {
            **_clear_opt_in_env(),
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
        _assert(info.real_tts_enabled, "configured provider check should keep real TTS intent")
        _assert(info.provider_configured, "supported provider should be considered FW-configured")
        _assert(info.supports_audio_artifact_ref, "configured provider should support artifact refs")
        _assert(not info.provider_details_exposed, "info must hide provider details")
        _assert_no_forbidden_imports("configured provider info")

        result = session.create_output(_build_request())
        _assert(
            result.request_state == "unavailable",
            "missing FW provider settings should return unavailable",
        )
        _assert(not result.audio_ready, "missing FW provider settings should not create audio")
        _assert(result.audio_artifact_ref is None, "unavailable output should not expose artifact ref")
        _assert_metadata_hides_provider_details(result.public_metadata, "missing settings output")
        _assert_no_forbidden_imports("configured provider missing settings")

    print("[OK] voice output configured provider with missing settings is mock-safe")


def check_public_contract_hides_provider_details() -> None:
    _assert_public_dataclass_fields_hide_provider_details()
    _assert_example_signature_hides_provider_details()
    _assert_no_forbidden_imports("public contract provider detail check")
    print("[OK] voice output public contract hides provider details")


def check_checklist_documented() -> None:
    checklist_path = PROJECT_ROOT / "docs" / "voice_output_real_tts_opt_in_checklist.md"
    text = checklist_path.read_text(encoding="utf-8")

    required_phrases: Iterable[str] = [
        "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
        "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
        "provider-neutral voice output intent",
        "DRC real_tts_web_audio_output: NOT_ACCEPTED",
        "python scripts/smoke_voice_output_real_tts_opt_in_boundary.py",
        "Host apps must not import `tts.voice_engine`",
    ]

    for phrase in required_phrases:
        _assert(phrase in text, f"Checklist is missing required phrase: {phrase}")

    print("[OK] voice output real TTS opt-in checklist is documented")


def main() -> None:
    check_default_boundary_is_not_real_tts()
    check_explicit_opt_in_without_provider_is_unavailable()
    check_unsupported_provider_is_unavailable()
    check_supported_provider_missing_settings_does_not_execute_provider_sdk()
    check_public_contract_hides_provider_details()
    check_checklist_documented()
    print("[OK] voice output real TTS opt-in boundary is mock-safe")


if __name__ == "__main__":
    main()
