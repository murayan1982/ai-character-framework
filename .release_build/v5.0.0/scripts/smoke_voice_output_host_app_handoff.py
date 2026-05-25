"""Smoke checks for host app voice output integration handoff.

This script is intentionally mock-safe. It validates that the app-facing
handoff for public voice output integrations remains provider-neutral and safe
for general host applications such as Daily Rhythm Companion.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import fields
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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

FORBIDDEN_IMPORTS = [
    "tts.voice_engine",
    "elevenlabs",
    "elevenlabs.client",
    "live2d.vts_client",
    "stt.stt_engine",
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

ALLOWED_REQUEST_FIELDS = {
    "text",
    "voice_profile_id",
    "requested_audio_format",
    "utterance_purpose",
    "language_code",
}

ALLOWED_PROVIDER_METADATA_KEYS = {
    "provider_details_exposed",
    "provider_status",
}

ARTIFACT_DIR = PROJECT_ROOT / "temp" / "voice_output_host_app_handoff_smoke"


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
    _assert(not files, f"{context} should not create audio artifacts: {files}")


def _assert_no_forbidden_imports(context: str) -> None:
    imported = [module_name for module_name in FORBIDDEN_IMPORTS if module_name in sys.modules]
    _assert(not imported, f"{context} should not import provider/runtime internals: {imported}")


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


def _build_request():
    from framework import VoiceOutputRequest

    return VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )


def check_handoff_doc_is_documented() -> None:
    doc_path = PROJECT_ROOT / "docs" / "host_app_voice_output_integration_handoff.md"
    text = doc_path.read_text(encoding="utf-8")

    required_phrases = [
        "Host App Voice Output Integration Handoff",
        "Daily Rhythm Companion (DRC) is the first concrete integration target",
        "Host apps should not import `tts.voice_engine`",
        "What host apps may pass",
        "What FW owns and hides",
        "VoiceOutputResult handling",
        "request_state: skipped",
        "provider_execution_guard_disabled",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1",
        "DRC `real_tts_web_audio_output` remains `NOT_ACCEPTED`",
        "python scripts/smoke_voice_output_host_app_handoff.py",
    ]

    for phrase in required_phrases:
        _assert(phrase in text, f"host app handoff doc is missing: {phrase}")

    print("[OK] voice output host app handoff doc is documented")


def check_release_package_includes_handoff_items() -> None:
    check_path = PROJECT_ROOT / "scripts" / "check_release_package.py"
    text = check_path.read_text(encoding="utf-8")

    required_entries = [
        "docs/host_app_voice_output_integration_handoff.md",
        "scripts/smoke_voice_output_host_app_handoff.py",
    ]
    for entry in required_entries:
        _assert(entry in text, f"release package check is missing required entry: {entry}")

    print("[OK] release package check includes host app handoff items")


def check_public_docs_reference_handoff() -> None:
    required_references = {
        "docs/app_integration_contract.md": "host_app_voice_output_integration_handoff.md",
        "docs/public_facade.md": "host_app_voice_output_integration_handoff.md",
        "docs/RELEASE_NOTES.md": "host_app_voice_output_integration_handoff.md",
        "docs/roadmap_feature_v5.0.0.md": "Commit 10 - Host app voice output integration handoff plan",
    }

    for relative_path, phrase in required_references.items():
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        _assert(phrase in text, f"{relative_path} should reference host app handoff: {phrase}")

    print("[OK] public docs reference host app voice output handoff")


def check_request_shape_is_provider_neutral() -> None:
    from framework import VoiceOutputRequest

    request_fields = {field.name for field in fields(VoiceOutputRequest)}
    _assert(
        request_fields == ALLOWED_REQUEST_FIELDS,
        f"VoiceOutputRequest fields should stay host-app-safe: {sorted(request_fields)}",
    )

    forbidden_request_fields = sorted(request_fields.intersection(FORBIDDEN_PUBLIC_FIELD_NAMES))
    _assert(not forbidden_request_fields, f"VoiceOutputRequest leaked provider fields: {forbidden_request_fields}")

    print("[OK] voice output host app request shape is provider-neutral")


def check_mock_safe_unavailable_handoff() -> None:
    _clear_artifact_dir()
    with temporary_env({**_clear_opt_in_env(), "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR": str(ARTIFACT_DIR)}):
        from framework import create_voice_output_session

        session = create_voice_output_session(
            default_voice_profile_id="gentle_mina_default",
            artifact_dir=ARTIFACT_DIR,
        )
        result = session.create_output(_build_request())

        _assert(result.request_state == "unavailable", "default host app handoff should be unavailable")
        _assert(result.audio_ready is False, "default unavailable result should not be audio ready")
        _assert(result.audio_handoff_kind == "none", "default unavailable result should have no handoff")
        _assert(result.has_audio_handoff is False, "default unavailable result should not expose handoff")
        _assert(result.is_generated is False, "default unavailable result should not be generated")
        _assert_metadata_hides_provider_details(result.public_metadata, "default host app handoff")
        _assert_no_forbidden_imports("default host app handoff")
        _assert_artifact_dir_empty("default host app handoff")

    print("[OK] voice output host app unavailable handoff is mock-safe")


def check_guarded_provider_handoff_not_evidence() -> None:
    _clear_artifact_dir()
    with temporary_env(
        {
            **_clear_opt_in_env(),
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
            "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR": str(ARTIFACT_DIR),
        }
    ):
        from framework import create_voice_output_session

        session = create_voice_output_session(
            default_voice_profile_id="gentle_mina_default",
            artifact_dir=ARTIFACT_DIR,
        )
        result = session.create_output(_build_request())

        _assert(result.request_state == "skipped", "guarded provider should return skipped")
        _assert(result.audio_ready is False, "guarded provider skipped result should not be audio ready")
        _assert(result.audio_handoff_kind == "none", "guarded provider should not expose handoff")
        _assert(result.has_audio_handoff is False, "guarded provider should not expose handoff")
        _assert(result.is_generated is False, "guarded provider should not be generated")
        _assert(result.public_metadata.get("reason") == "provider_execution_guard_disabled", "guard reason mismatch")
        _assert_metadata_hides_provider_details(result.public_metadata, "guarded provider host app handoff")
        _assert_no_forbidden_imports("guarded provider host app handoff")
        _assert_artifact_dir_empty("guarded provider host app handoff")

    print("[OK] voice output guarded provider handoff is not real audio evidence")


def main() -> int:
    checks = [
        check_handoff_doc_is_documented,
        check_release_package_includes_handoff_items,
        check_public_docs_reference_handoff,
        check_request_shape_is_provider_neutral,
        check_mock_safe_unavailable_handoff,
        check_guarded_provider_handoff_not_evidence,
    ]

    for check in checks:
        check()

    print("[OK] voice output host app handoff is mock-safe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
