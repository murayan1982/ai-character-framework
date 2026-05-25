"""Smoke checks for the real provider execution guard.

This script is intentionally mock-safe. It verifies that a configured provider
cannot import provider SDKs, create artifacts, or make network calls unless FW
operator policy explicitly allows real provider execution.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Mapping


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
    "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
    "ELEVENLABS_API_KEY",
    "VOICE_MASTER",
    "SELECT_VOICE_INDEX",
    "SELECT_TTS_MODEL_INDEX",
}

ARTIFACT_DIR = PROJECT_ROOT / "temp" / "voice_output_guard_smoke"


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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _clear_opt_in_env() -> dict[str, str | None]:
    return {key: None for key in OPT_IN_ENV_KEYS}


def _clear_artifact_dir() -> None:
    if ARTIFACT_DIR.exists():
        shutil.rmtree(ARTIFACT_DIR)


def _assert_artifact_dir_empty(context: str) -> None:
    if not ARTIFACT_DIR.exists():
        return

    files = [path for path in ARTIFACT_DIR.rglob("*") if path.is_file()]
    _assert(not files, f"{context} should not create artifacts: {files}")


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


def _build_request(*, fmt: str = "mp3"):
    from framework import VoiceOutputRequest

    return VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format=fmt,
        utterance_purpose="daily_advice",
        language_code="ja",
    )


def check_configured_provider_is_guarded_by_default() -> None:
    from framework import create_voice_output_session

    _clear_artifact_dir()
    with temporary_env(
        {
            **_clear_opt_in_env(),
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
            "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR": str(ARTIFACT_DIR),
            # These dummy settings look like a configured run, but the execution
            # guard must still prevent provider imports and artifact writes.
            "ELEVENLABS_API_KEY": "dummy-key-never-used",
            "VOICE_MASTER": '[{"id":"dummy-voice-never-used","name":"Dummy"}]',
        }
    ):
        session = create_voice_output_session(project_root=PROJECT_ROOT)
        info = session.info()
        _assert(info.real_tts_enabled, "real TTS intent should be visible")
        _assert(info.provider_configured, "supported provider should be configured")
        _assert(info.status == "execution_guarded", "provider should be execution guarded")
        _assert(not info.provider_details_exposed, "session info should hide provider details")

        result = session.create_output(_build_request())
        _assert(result.request_state == "skipped", "guarded provider execution should be skipped")
        _assert(not result.audio_ready, "guarded provider execution must not create playable audio")
        _assert(result.audio_handoff_kind == "none", "guarded result must not expose handoff")
        _assert(
            result.public_metadata.get("reason") == "provider_execution_guard_disabled",
            "guarded result should explain that provider execution is disabled",
        )
        _assert_metadata_hides_provider_details(result.public_metadata, "guarded provider result")
        _assert_no_forbidden_imports("configured provider guarded by default")
        _assert_artifact_dir_empty("configured provider guarded by default")

    print("[OK] configured voice output provider is guarded by default")


def check_false_execution_guard_values_remain_guarded() -> None:
    from framework import create_voice_output_session

    for false_value in ("0", "false", "off", "disabled"):
        _clear_artifact_dir()
        with temporary_env(
            {
                **_clear_opt_in_env(),
                "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
                "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
                "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION": false_value,
                "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR": str(ARTIFACT_DIR),
                "ELEVENLABS_API_KEY": "dummy-key-never-used",
                "VOICE_MASTER": '[{"id":"dummy-voice-never-used","name":"Dummy"}]',
            }
        ):
            session = create_voice_output_session(project_root=PROJECT_ROOT)
            result = session.create_output(_build_request())
            _assert(result.request_state == "skipped", f"{false_value!r} should keep execution guarded")
            _assert(not result.audio_ready, f"{false_value!r} should not create audio")
            _assert_no_forbidden_imports(f"execution guard false value {false_value}")
            _assert_artifact_dir_empty(f"execution guard false value {false_value}")

    print("[OK] false execution guard values remain mock-safe")


def check_allowed_execution_with_missing_settings_stops_before_sdk_import() -> None:
    from framework import create_voice_output_session

    _clear_artifact_dir()
    with temporary_env(
        {
            **_clear_opt_in_env(),
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
            "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION": "1",
            "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR": str(ARTIFACT_DIR),
            "ELEVENLABS_API_KEY": "",
            "VOICE_MASTER": "[]",
        }
    ):
        session = create_voice_output_session(project_root=PROJECT_ROOT)
        info = session.info()
        _assert(info.real_tts_enabled, "real TTS intent should be visible")
        _assert(info.provider_configured, "provider should still be FW-configured")
        _assert(info.status == "provider_configured", "execution guard should be open")

        result = session.create_output(_build_request())
        _assert(result.request_state == "unavailable", "missing settings should stop before provider SDK import")
        _assert(not result.audio_ready, "missing settings should not create audio")
        _assert(result.audio_handoff_kind == "none", "missing settings should not expose handoff")
        _assert(
            result.public_metadata.get("reason") == "provider_settings_unavailable",
            "missing settings result should explain that provider settings are unavailable",
        )
        _assert_metadata_hides_provider_details(result.public_metadata, "allowed execution missing settings")
        _assert_no_forbidden_imports("allowed execution missing settings")
        _assert_artifact_dir_empty("allowed execution missing settings")

    print("[OK] allowed execution with missing settings stops before provider SDK import")


def check_guard_documented() -> None:
    doc_path = PROJECT_ROOT / "docs" / "voice_output_real_provider_execution_guard.md"
    text = doc_path.read_text(encoding="utf-8")

    required_phrases = [
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
        "request_state: skipped",
        "provider_execution_guard_disabled",
        "python scripts/smoke_voice_output_real_provider_execution_guard.py",
        "DRC real_tts_web_audio_output: NOT_ACCEPTED",
    ]

    for phrase in required_phrases:
        _assert(phrase in text, f"Real provider execution guard doc is missing: {phrase}")

    print("[OK] voice output real provider execution guard is documented")


def main() -> None:
    check_configured_provider_is_guarded_by_default()
    check_false_execution_guard_values_remain_guarded()
    check_allowed_execution_with_missing_settings_stops_before_sdk_import()
    check_guard_documented()
    print("[OK] voice output real provider execution guard is mock-safe")


if __name__ == "__main__":
    main()
