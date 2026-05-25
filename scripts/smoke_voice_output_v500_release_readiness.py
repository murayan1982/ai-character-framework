"""Smoke checks for v5.0.0 voice output release readiness.

This script is intentionally mock-safe. It validates the release-readiness
contract for the public voice output boundary without provider credentials,
provider SDK imports, provider network calls, or generated audio artifacts.
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

REQUIRED_DOCS = [
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
    "docs/voice_output_real_tts_opt_in_checklist.md",
    "docs/voice_output_artifact_result_contract.md",
    "docs/voice_output_real_provider_execution_guard.md",
    "docs/voice_output_v500_release_readiness_checklist.md",
    "docs/host_app_voice_output_integration_handoff.md",
    "docs/voice_output_v500_package_readiness.md",
]

REQUIRED_SCRIPTS = [
    "scripts/smoke_public_facade.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_voice_output_real_tts_opt_in_boundary.py",
    "scripts/smoke_voice_output_artifact_result_contract.py",
    "scripts/smoke_voice_output_real_provider_execution_guard.py",
    "scripts/smoke_voice_output_v500_release_readiness.py",
    "scripts/smoke_voice_output_host_app_handoff.py",
    "scripts/smoke_voice_output_v500_package_readiness.py",
    "scripts/check_release_package.py",
]

ARTIFACT_DIR = PROJECT_ROOT / "temp" / "voice_output_release_readiness_smoke"


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


def _build_request():
    from framework import VoiceOutputRequest

    return VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )


def check_release_readiness_files_exist() -> None:
    missing = [item for item in [*REQUIRED_DOCS, *REQUIRED_SCRIPTS] if not (PROJECT_ROOT / item).is_file()]
    _assert(not missing, f"Missing v5.0.0 release readiness files: {missing}")
    print("[OK] voice output v5.0.0 release readiness files exist")


def check_release_readiness_documented() -> None:
    doc_path = PROJECT_ROOT / "docs" / "voice_output_v500_release_readiness_checklist.md"
    text = doc_path.read_text(encoding="utf-8")

    required_phrases = [
        "Public Voice Output / TTS Boundary Foundation",
        "mock-safe release readiness",
        "Real-run readiness boundary",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
        "request_state: skipped",
        "provider_execution_guard_disabled",
        "python scripts/smoke_voice_output_host_app_handoff.py",
        "python scripts/smoke_voice_output_v500_release_readiness.py",
        "python scripts/smoke_voice_output_v500_package_readiness.py",
        "python scripts/check_release_package.py",
        "DRC real_tts_web_audio_output: NOT_ACCEPTED",
        "DRC v2.0.0: NOT_RELEASED",
        "unavailable` and `skipped` are readiness states, not playable audio evidence",
        "voice_output_v500_package_readiness.md",
        "package-readiness smoke",
    ]

    for phrase in required_phrases:
        _assert(phrase in text, f"v5.0.0 release readiness checklist is missing: {phrase}")

    print("[OK] voice output v5.0.0 release readiness checklist is documented")


def check_release_package_includes_readiness_items() -> None:
    check_path = PROJECT_ROOT / "scripts" / "check_release_package.py"
    text = check_path.read_text(encoding="utf-8")

    required_entries = [
        "docs/voice_output_v500_release_readiness_checklist.md",
        "scripts/smoke_voice_output_v500_release_readiness.py",
        "scripts/smoke_voice_output_host_app_handoff.py",
        "scripts/smoke_voice_output_v500_package_readiness.py",
    ]
    for entry in required_entries:
        _assert(entry in text, f"release package check is missing required entry: {entry}")

    print("[OK] release package check includes voice output v5.0.0 readiness items")


def check_public_api_mock_safe_release_surface() -> None:
    _clear_artifact_dir()
    with temporary_env({**_clear_opt_in_env()}):
        import framework
        from framework import create_voice_output_session

        for public_name in (
            "create_voice_output_session",
            "VoiceOutputSession",
            "VoiceOutputSessionInfo",
            "VoiceOutputRequest",
            "VoiceOutputResult",
        ):
            _assert(hasattr(framework, public_name), f"framework is missing public API: {public_name}")
            _assert(public_name in framework.__all__, f"framework.__all__ is missing: {public_name}")

        session = create_voice_output_session(
            project_root=PROJECT_ROOT,
            default_voice_profile_id="gentle_mina_default",
        )
        info = session.info()
        _assert(info.supports_voice_output, "voice output session should advertise voice output support")
        _assert(not info.real_tts_enabled, "real TTS should be disabled by default")
        _assert(not info.provider_configured, "provider should not be configured by default")
        _assert(not info.provider_details_exposed, "session info must hide provider details")
        _assert(info.status == "contract_ready", "default release surface should be contract-ready")

        result = session.create_output(_build_request())
        _assert(result.request_state == "unavailable", "default output should be unavailable")
        _assert(not result.audio_ready, "default output should not create playable audio")
        _assert(result.audio_handoff_kind == "none", "default output should not expose handoff")
        _assert(not result.has_audio_handoff, "default output should not expose handoff helper")
        _assert(not result.is_generated, "default output should not be generated")
        _assert_metadata_hides_provider_details(result.public_metadata, "default release surface")
        _assert_no_forbidden_imports("default release surface")
        _assert_artifact_dir_empty("default release surface")

    print("[OK] voice output public API release surface is mock-safe")


def check_guarded_provider_release_surface_is_not_evidence() -> None:
    from framework import create_voice_output_session

    _clear_artifact_dir()
    with temporary_env(
        {
            **_clear_opt_in_env(),
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS": "1",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER": "elevenlabs",
            "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR": str(ARTIFACT_DIR),
            "ELEVENLABS_API_KEY": "dummy-key-never-used",
            "VOICE_MASTER": '[{"id":"dummy-voice-never-used","name":"Dummy"}]',
        }
    ):
        session = create_voice_output_session(project_root=PROJECT_ROOT)
        info = session.info()
        _assert(info.real_tts_enabled, "real TTS intent should be visible")
        _assert(info.provider_configured, "supported provider should be configured")
        _assert(info.status == "execution_guarded", "configured provider should remain guarded by default")
        _assert(not info.provider_details_exposed, "session info should hide provider details")

        result = session.create_output(_build_request())
        _assert(result.request_state == "skipped", "guarded provider should return skipped")
        _assert(not result.audio_ready, "guarded provider output should not create playable audio")
        _assert(result.audio_handoff_kind == "none", "guarded provider output should not expose handoff")
        _assert(not result.has_audio_handoff, "guarded provider output should not expose handoff helper")
        _assert(not result.is_generated, "guarded provider output should not count as generated evidence")
        _assert(
            result.public_metadata.get("reason") == "provider_execution_guard_disabled",
            "guarded provider should explain the execution guard boundary",
        )
        _assert_metadata_hides_provider_details(result.public_metadata, "guarded release surface")
        _assert_no_forbidden_imports("guarded release surface")
        _assert_artifact_dir_empty("guarded release surface")

    print("[OK] guarded provider release surface is not real audio evidence")


def main() -> None:
    check_release_readiness_files_exist()
    check_release_readiness_documented()
    check_release_package_includes_readiness_items()
    check_public_api_mock_safe_release_surface()
    check_guarded_provider_release_surface_is_not_evidence()
    print("[OK] voice output v5.0.0 release readiness is mock-safe")


if __name__ == "__main__":
    main()
