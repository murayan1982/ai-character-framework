"""Mock-safe provider config ownership smoke for FW v5.1.0."""

from __future__ import annotations

import os
import sys
from pathlib import Path


FORBIDDEN_MODULE_FRAGMENTS = (
    "elevenlabs",
    "openai",
    "tts.voice_engine",
    "voice_input",
    "vts",
)

SECRET_MARKERS = (
    "test-google-secret",
    "test-openai-secret",
    "test-eleven-secret",
    "sk-test",
    "C:" + chr(92),
    "/home/",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_importable() -> Path:
    root = _repo_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _assert_doc(root: Path) -> None:
    doc_path = root / "docs" / "v510_provider_config_ownership.md"
    _require(doc_path.exists(), "missing docs/v510_provider_config_ownership.md")
    text = _read_text(doc_path)
    for phrase in (
        "Provider Config Ownership Contract",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "must not expose",
        "must not import provider SDKs",
        "does not run real providers",
    ):
        _require(phrase in text, f"provider config ownership doc missing phrase: {phrase}")
    _ok("provider config ownership doc is documented")


def _assert_no_forbidden_imports() -> None:
    loaded = sorted(sys.modules)
    forbidden = [name for name in loaded if any(fragment in name.lower() for fragment in FORBIDDEN_MODULE_FRAGMENTS)]
    _require(not forbidden, f"provider config import loaded forbidden provider/internal modules: {forbidden}")
    _ok("provider config import stays provider/internal safe")


def _with_clean_env(keys: tuple[str, ...]):
    class EnvGuard:
        def __enter__(self):
            self.original = {key: os.environ.get(key) for key in keys}
            for key in keys:
                os.environ.pop(key, None)
            return self

        def __exit__(self, exc_type, exc, tb):
            for key, value in self.original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            return False

    return EnvGuard()


def _assert_no_secret_leak(value: object) -> None:
    text = repr(value)
    leaked = [marker for marker in SECRET_MARKERS if marker in text]
    _require(not leaked, f"provider config snapshot leaked secret/private markers: {leaked}")


def _assert_gemini_alias(module: object) -> None:
    keys = (
        "FRAMEWORK_TEXT_PROVIDER",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    )
    with _with_clean_env(keys):
        os.environ["FRAMEWORK_TEXT_PROVIDER"] = "gemini"
        os.environ["GOOGLE_API_KEY"] = "test-google-secret"
        snapshot = module.get_provider_environment_snapshot()
        status = snapshot.text_chat
        _require(status.configured is True, "gemini should be configured by GOOGLE_API_KEY alias")
        _require(status.reason_code == "provider_environment_configured", "gemini alias should use configured reason")
        _require(os.environ.get("GEMINI_API_KEY") is None, "provider config must not mutate GEMINI_API_KEY alias")
        _assert_no_secret_leak(snapshot.to_public_dict())
    _ok("Gemini/Google API key alias is resolved inside FW without env mutation")


def _assert_missing_credential(module: object) -> None:
    keys = ("FRAMEWORK_TEXT_PROVIDER", "OPENAI_API_KEY")
    with _with_clean_env(keys):
        os.environ["FRAMEWORK_TEXT_PROVIDER"] = "openai"
        snapshot = module.get_provider_environment_snapshot()
        status = snapshot.text_chat
        _require(status.configured is False, "openai without key should not be configured")
        _require(status.reason_code == "credential_missing", "openai missing key should report credential_missing")
        _assert_no_secret_leak(snapshot.to_public_dict())
    _ok("missing provider credentials produce provider-neutral status")


def _assert_voice_output_config(module: object) -> None:
    keys = (
        "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
        "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
        "OPENAI_API_KEY",
    )
    with _with_clean_env(keys):
        os.environ["FRAMEWORK_VOICE_OUTPUT_REAL_TTS"] = "1"
        os.environ["FRAMEWORK_VOICE_OUTPUT_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "test-openai-secret"
        snapshot = module.get_provider_environment_snapshot()
        status = snapshot.voice_output
        _require(status.configured is True, "voice output should be configured by FW-owned provider alias")
        _require(status.reason_code == "provider_environment_configured", "voice output should report configured reason")
        _assert_no_secret_leak(snapshot.to_public_dict())
    _ok("voice output provider config is resolved without exposing secrets")


def _assert_real_tts_disabled(module: object) -> None:
    keys = (
        "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
        "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
        "ELEVENLABS_API_KEY",
    )
    with _with_clean_env(keys):
        os.environ["FRAMEWORK_VOICE_OUTPUT_PROVIDER"] = "elevenlabs"
        os.environ["ELEVENLABS_API_KEY"] = "test-eleven-secret"
        snapshot = module.get_provider_environment_snapshot()
        status = snapshot.voice_output
        _require(status.configured is False, "disabled real TTS should not be configured as usable")
        _require(status.reason_code == "real_tts_disabled", "disabled voice output should report real_tts_disabled")
        _assert_no_secret_leak(snapshot.to_public_dict())
    _ok("real TTS disabled state remains provider-neutral and secret-free")


def main() -> None:
    root = _ensure_repo_importable()
    _assert_doc(root)

    import framework.provider_config as provider_config  # noqa: PLC0415

    _assert_no_forbidden_imports()
    _assert_gemini_alias(provider_config)
    _assert_missing_credential(provider_config)
    _assert_voice_output_config(provider_config)
    _assert_real_tts_disabled(provider_config)
    _assert_no_forbidden_imports()
    _ok("v5.1.0 provider config ownership is mock-safe")


if __name__ == "__main__":
    main()
