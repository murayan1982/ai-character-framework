"""Smoke-check the v5.1.0 public factory signature contract.

This is a mock-safe P0 checkpoint. It records the current public factory
signature baseline and checks for docs/API drift before larger SDK work begins.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_importable() -> Path:
    root = _repo_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root


def _force_mock_safe_environment() -> None:
    # These checks must not trigger real provider execution.
    os.environ.pop("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", None)
    os.environ.setdefault("FRAMEWORK_VOICE_OUTPUT_REAL_TTS", "0")


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _warn(message: str) -> None:
    print(f"[WARN] {message}")


def _fail(message: str) -> None:
    raise AssertionError(message)


def _param_names(signature: inspect.Signature) -> list[str]:
    return list(signature.parameters.keys())


def _assert_no_unwanted_alias_params(factory_name: str, signature: inspect.Signature) -> None:
    unwanted = {
        "preset_name",
        "preset_id",
        "character",
        "character_id",
        "framework_project_root",
        "tts_provider",
        "provider_voice_id",
        "api_key",
        "voice_id",
        "model_id",
    }
    found = sorted(unwanted.intersection(signature.parameters))
    if found:
        _fail(f"{factory_name} exposes unwanted public alias/provider params: {found}")
    _ok(f"{factory_name} exposes no unwanted alias/provider-specific params")


def _assert_signature_params(
    factory_name: str,
    signature: inspect.Signature,
    expected_names: list[str],
) -> None:
    actual_names = _param_names(signature)
    if actual_names != expected_names:
        _fail(
            f"{factory_name} parameter drift: expected {expected_names}, got {actual_names}"
        )
    _ok(f"{factory_name} parameter names match v5.1.0 baseline")


def _assert_keyword_only(factory_name: str, signature: inspect.Signature) -> None:
    non_keyword_only = [
        name
        for name, param in signature.parameters.items()
        if param.kind is not inspect.Parameter.KEYWORD_ONLY
    ]
    if non_keyword_only:
        _fail(f"{factory_name} must be keyword-only, but these are not: {non_keyword_only}")
    _ok(f"{factory_name} is keyword-only")


def _assert_doc_mentions(root: Path) -> None:
    doc_path = root / "docs" / "v510_public_factory_signature_contract.md"
    if not doc_path.exists():
        _fail("missing docs/v510_public_factory_signature_contract.md")
    text = doc_path.read_text(encoding="utf-8")
    required = [
        "create_text_chat_session",
        "create_voice_output_session",
        "preset",
        "character_name",
        "default_voice_profile_id",
        "real_tts_enabled",
        "artifact_dir",
        "session.speak(request)",
        "create_voice_input_session",
        "create_realtime_session",
        "create_motion_session",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        _fail(f"factory signature contract doc missing expected text: {missing}")
    _ok("public factory signature contract doc is documented")


def _assert_all_exports(framework: object) -> None:
    exported = set(getattr(framework, "__all__", ()))
    required = {
        "create_text_chat_session",
        "create_voice_output_session",
        "VoiceOutputRequest",
        "VoiceOutputResult",
    }
    missing = sorted(required - exported)
    if missing:
        _fail(f"framework.__all__ missing public factory/result exports: {missing}")
    _ok("framework.__all__ exports current public factory baseline")


def _assert_no_public_legacy_factory_aliases(framework: object) -> None:
    exported = set(getattr(framework, "__all__", ()))
    legacy_aliases = {
        "create_tts_session",
        "create_output_session",
        "create_text_session",
    }
    exposed = sorted(legacy_aliases.intersection(exported))
    if exposed:
        _fail(f"legacy factory aliases should not be exported publicly: {exposed}")
    _ok("no legacy factory aliases are exported from framework.__all__")


def main() -> None:
    root = _ensure_repo_importable()
    _force_mock_safe_environment()

    import framework  # noqa: PLC0415

    _assert_all_exports(framework)
    _assert_no_public_legacy_factory_aliases(framework)

    text_factory = getattr(framework, "create_text_chat_session", None)
    if text_factory is None:
        _fail("create_text_chat_session is not available")
    text_sig = inspect.signature(text_factory)
    _info(f"signature create_text_chat_session{text_sig}")
    _assert_signature_params(
        "create_text_chat_session",
        text_sig,
        ["preset", "character_name", "provider", "model"],
    )
    _assert_no_unwanted_alias_params("create_text_chat_session", text_sig)

    text_non_keyword_only = [
        name
        for name, param in text_sig.parameters.items()
        if param.kind is not inspect.Parameter.KEYWORD_ONLY
    ]
    if text_non_keyword_only:
        _warn(
            "create_text_chat_session is not keyword-only yet; record as v5.1.0 transition baseline"
        )
    else:
        _ok("create_text_chat_session is keyword-only")

    voice_factory = getattr(framework, "create_voice_output_session", None)
    if voice_factory is None:
        _fail("create_voice_output_session is not available")
    voice_sig = inspect.signature(voice_factory)
    _info(f"signature create_voice_output_session{voice_sig}")
    _assert_signature_params(
        "create_voice_output_session",
        voice_sig,
        ["project_root", "default_voice_profile_id", "real_tts_enabled", "artifact_dir"],
    )
    _assert_keyword_only("create_voice_output_session", voice_sig)
    _assert_no_unwanted_alias_params("create_voice_output_session", voice_sig)

    _assert_doc_mentions(root)
    _ok("v5.1.0 public factory signature contract is mock-safe")


if __name__ == "__main__":
    main()
