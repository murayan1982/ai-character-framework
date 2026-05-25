"""Smoke checks for the public voice output artifact result contract.

This script is offline-safe. It verifies the app-facing result shape used by
Web hosts such as Daily Rhythm Companion without calling real TTS providers.

Run:

    python scripts/smoke_voice_output_artifact_result_contract.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import fields, is_dataclass
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

EXPECTED_RESULT_FIELDS = {
    "request_state",
    "audio_ready",
    "audio_format",
    "audio_url",
    "audio_artifact_ref",
    "message",
    "public_metadata",
}


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
    if "provider_details_exposed" in metadata:
        _assert(
            metadata.get("provider_details_exposed") == "false",
            f"{context} should explicitly keep provider details hidden",
        )


def _build_request(*, text: str = "今日は少し早めに休むとよさそうです。", fmt: str = "mp3"):
    from framework import VoiceOutputRequest

    return VoiceOutputRequest(
        text=text,
        voice_profile_id="gentle_mina_default",
        requested_audio_format=fmt,
        utterance_purpose="daily_advice",
        language_code="ja",
    )


def _assert_not_playable(result, context: str) -> None:
    _assert(result.request_state != "generated", f"{context} must not be generated")
    _assert(not result.audio_ready, f"{context} must not be audio-ready")
    _assert(result.audio_url is None, f"{context} must not expose audio_url")
    _assert(result.audio_artifact_ref is None, f"{context} must not expose audio_artifact_ref")
    _assert(result.audio_handoff_kind == "none", f"{context} handoff kind should be none")
    _assert(not result.has_audio_handoff, f"{context} should not have audio handoff")
    _assert(not result.is_generated, f"{context} should not be generated")
    _assert_metadata_hides_provider_details(result.public_metadata, context)


def _assert_generated_handoff(result, context: str, expected_kind: str) -> None:
    _assert(result.request_state == "generated", f"{context} should be generated")
    _assert(result.audio_ready, f"{context} should be audio-ready")
    _assert(result.audio_format == "mp3", f"{context} should expose normalized mp3 format")
    _assert(result.audio_handoff_kind == expected_kind, f"{context} should expose {expected_kind}")
    _assert(result.has_audio_handoff, f"{context} should have exactly one audio handoff")
    _assert(result.is_generated, f"{context} should be recognized as generated")
    _assert_metadata_hides_provider_details(result.public_metadata, context)


def check_result_public_shape() -> None:
    from framework import VoiceOutputResult

    _assert(is_dataclass(VoiceOutputResult), "VoiceOutputResult should be a dataclass")
    field_names = {field.name for field in fields(VoiceOutputResult)}
    _assert(
        EXPECTED_RESULT_FIELDS <= field_names,
        f"VoiceOutputResult is missing expected fields: {EXPECTED_RESULT_FIELDS - field_names}",
    )
    leaked = sorted(field_names & FORBIDDEN_PUBLIC_FIELD_NAMES)
    _assert(not leaked, f"VoiceOutputResult exposes provider-specific fields: {leaked}")

    for attr in ("audio_handoff_kind", "has_audio_handoff", "is_generated"):
        _assert(hasattr(VoiceOutputResult, attr), f"VoiceOutputResult should expose {attr}")

    _assert_no_forbidden_imports("voice output result public shape")
    print("[OK] voice output artifact result public shape is provider-neutral")


def check_default_unavailable_has_no_audio_handoff() -> None:
    from framework import create_voice_output_session

    with temporary_env(_clear_opt_in_env()):
        session = create_voice_output_session(
            project_root=PROJECT_ROOT,
            default_voice_profile_id="gentle_mina_default",
        )
        info = session.info()
        _assert(not info.real_tts_enabled, "default session must not enable real TTS")
        _assert(not info.supports_audio_url, "default session must not advertise audio URL support")
        _assert(
            not info.supports_audio_artifact_ref,
            "default session must not advertise artifact handoff support",
        )

        result = session.create_output(_build_request(fmt=".MP3"))
        _assert(result.request_state == "unavailable", "default output should be unavailable")
        _assert(result.audio_format == "mp3", "audio format should be normalized")
        _assert_not_playable(result, "default unavailable output")
        _assert_no_forbidden_imports("default unavailable artifact contract")

    print("[OK] voice output unavailable result has no audio handoff")


def check_rejected_result_has_no_audio_handoff() -> None:
    from framework import create_voice_output_session

    with temporary_env(_clear_opt_in_env()):
        session = create_voice_output_session(project_root=PROJECT_ROOT)
        result = session.create_output(_build_request(text="   ", fmt=".wav"))
        _assert(result.request_state == "rejected", "empty text should be rejected")
        _assert(result.audio_format == "wav", "rejected result should preserve normalized format")
        _assert_not_playable(result, "rejected output")
        _assert(result.public_metadata.get("reason") == "empty_text", "rejected output should explain reason")
        _assert_no_forbidden_imports("rejected artifact contract")

    print("[OK] voice output rejected result has no audio handoff")


def check_configured_provider_guarded_result_has_no_audio_handoff() -> None:
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
        _assert(info.real_tts_enabled, "real TTS intent should be visible")
        _assert(info.provider_configured, "supported provider should be FW-configured")
        _assert(info.supports_audio_artifact_ref, "configured provider should advertise artifact ref support")
        _assert(not info.supports_audio_url, "current configured provider should not advertise URL support")

        result = session.create_output(_build_request())
        _assert(result.request_state == "skipped", "configured provider should be skipped while execution guard is closed")
        _assert_not_playable(result, "configured provider guarded output")
        _assert_no_forbidden_imports("configured provider guarded artifact contract")

    print("[OK] voice output guarded provider result has no audio handoff")


def check_generated_public_handoff_contract() -> None:
    from framework import VoiceOutputResult

    artifact_result = VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_artifact_ref="artifact://voice-output/demo.mp3",
        message="Generated for contract smoke only.",
        public_metadata={
            "boundary": "voice_output",
            "provider_details_exposed": "false",
            "artifact_kind": "file",
        },
    )
    _assert_generated_handoff(
        artifact_result,
        "synthetic generated artifact result",
        "audio_artifact_ref",
    )

    url_result = VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_url="https://example.invalid/fw/audio/demo.mp3",
        message="Generated URL handoff for contract smoke only.",
        public_metadata={
            "boundary": "voice_output",
            "provider_details_exposed": "false",
            "artifact_kind": "url",
        },
    )
    _assert_generated_handoff(url_result, "synthetic generated URL result", "audio_url")

    invalid_multiple = VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_url="https://example.invalid/fw/audio/demo.mp3",
        audio_artifact_ref="artifact://voice-output/demo.mp3",
        public_metadata={"provider_details_exposed": "false"},
    )
    _assert(
        invalid_multiple.audio_handoff_kind == "multiple",
        "results with both handoffs should be classified as multiple",
    )
    _assert(
        not invalid_multiple.has_audio_handoff,
        "current v5 contract treats multiple handoffs as invalid",
    )

    _assert_no_forbidden_imports("synthetic generated handoff contract")
    print("[OK] voice output generated result handoff contract is explicit")


def check_contract_documented() -> None:
    doc_path = PROJECT_ROOT / "docs" / "voice_output_artifact_result_contract.md"
    text = doc_path.read_text(encoding="utf-8")

    required_phrases = [
        "audio_url",
        "audio_artifact_ref",
        "audio_handoff_kind",
        "has_audio_handoff",
        "DRC real_tts_web_audio_output: NOT_ACCEPTED",
        "python scripts/smoke_voice_output_artifact_result_contract.py",
    ]

    for phrase in required_phrases:
        _assert(phrase in text, f"Artifact result contract doc is missing: {phrase}")

    print("[OK] voice output artifact result contract is documented")


def main() -> None:
    check_result_public_shape()
    check_default_unavailable_has_no_audio_handoff()
    check_rejected_result_has_no_audio_handoff()
    check_configured_provider_guarded_result_has_no_audio_handoff()
    check_generated_public_handoff_contract()
    check_contract_documented()
    print("[OK] voice output artifact result contract is mock-safe")


if __name__ == "__main__":
    main()
