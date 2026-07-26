"""v5.2.0 voice-input capability preflight smoke."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


class ContractFailure(AssertionError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v520_voice_input_capability_preflight.md"
    _require(path.exists(), "missing docs/v520_voice_input_capability_preflight.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Voice Input Capability Preflight",
        "VoiceInputProviderStatus",
        "VoiceInputProviderConfig",
        "VoiceInputCapabilities",
        "resolve_voice_input_provider_config",
        "get_voice_input_capabilities",
        "disabled",
        "missing_credentials",
        "provider_execution_not_allowed",
        "unsupported_provider",
        "real_stt_not_implemented",
        "Import safety",
        "VoiceInputSessionInfo",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"voice-input capability preflight doc missing phrase: {phrase}")
    _ok("v5.2.0 voice-input capability preflight doc is documented")


def _assert_import_safe(root: Path):
    sys.path.insert(0, str(root))
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    after = set(sys.modules)
    loaded = after - before

    forbidden_fragments = [
        "pyaudio",
        "sounddevice",
        "speech_recognition",
        "whisper",
        "faster_whisper",
        "elevenlabs",
    ]
    hits = sorted(name for name in loaded if any(fragment in name for fragment in forbidden_fragments))
    _require(not hits, "import framework eagerly loaded voice/STT provider modules: " + ", ".join(hits[:16]))
    _ok("voice-input capability preflight import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "VoiceInputProviderStatus",
        "VoiceInputProviderConfig",
        "VoiceInputCapabilities",
        "resolve_voice_input_provider_config",
        "get_voice_input_capabilities",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")
    _ok("framework exports public voice-input capability preflight symbols")


def _assert_default_disabled(framework) -> None:
    capabilities = framework.get_voice_input_capabilities(credential_env={})
    _require(capabilities.supports_voice_input_session, "voice-input session should be supported")
    _require(capabilities.supports_text_fallback, "text fallback should be supported")
    _require(not capabilities.supports_real_stt, "real STT should not be supported yet")
    _require(capabilities.provider_status == framework.VoiceInputProviderStatus.DISABLED, "default preflight should be disabled")
    _require(capabilities.public_metadata["reason"] == "real_stt_disabled", "default disabled reason mismatch")
    _ok("default voice-input capability preflight is disabled and mock-safe")


def _assert_missing_credentials(framework) -> None:
    capabilities = framework.get_voice_input_capabilities(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    _require(capabilities.provider_status == framework.VoiceInputProviderStatus.MISSING_CREDENTIALS, "google without credentials should report missing credentials")
    _require(capabilities.retryable, "missing credentials should be retryable")
    _require(capabilities.public_metadata["reason"] == "missing_credentials", "missing credentials reason mismatch")
    _ok("voice-input capability preflight reports missing credentials safely")


def _assert_guard_block(framework) -> None:
    capabilities = framework.get_voice_input_capabilities(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=False,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    _require(capabilities.provider_status == framework.VoiceInputProviderStatus.PROVIDER_EXECUTION_NOT_ALLOWED, "guarded provider should report execution not allowed")
    _require("should-not-leak" not in repr(capabilities), "capabilities should not leak credential values")
    _ok("voice-input capability preflight respects provider execution guard")


def _assert_not_implemented(framework) -> None:
    capabilities = framework.get_voice_input_capabilities(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
        public_metadata={"token": "secret"},
    )
    _require(capabilities.provider_status == framework.VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED, "configured real STT should remain not implemented")
    _require(not capabilities.supports_real_stt, "real STT support should remain false before implementation")
    _require(capabilities.public_metadata["reason"] == "real_stt_not_implemented", "not implemented reason mismatch")
    _require("should-not-leak" not in repr(capabilities), "capabilities should not leak credential values")
    _ok("voice-input capability preflight does not overclaim real STT readiness")


def _assert_config_secret_safe(framework) -> None:
    config = framework.resolve_voice_input_provider_config(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"GOOGLE_API_KEY": "should-not-leak"},
        public_metadata={"api_key": "also-secret"},
    )
    _require(config.provider == "google", "provider config should normalize provider")
    _require(config.credentials_available, "provider config should detect credential presence")
    _require(config.credential_source == "GOOGLE_API_KEY", "provider config should expose source key only")
    _require(config.public_metadata["api_key"] == "<redacted>", "provider config metadata should redact secret-like keys")
    _require("should-not-leak" not in repr(config), "provider config should not leak credential values")
    _ok("voice-input provider config preflight is credential-value safe")


def _assert_unsupported_provider(framework) -> None:
    capabilities = framework.get_voice_input_capabilities(
        provider="unknown-stt",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    _require(capabilities.provider_status == framework.VoiceInputProviderStatus.UNSUPPORTED_PROVIDER, "unsupported provider should be reported")
    _require(capabilities.public_metadata["reason"] == "unsupported_provider", "unsupported provider reason mismatch")
    _ok("voice-input capability preflight reports unsupported provider safely")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_default_disabled(framework)
    _assert_missing_credentials(framework)
    _assert_guard_block(framework)
    _assert_not_implemented(framework)
    _assert_config_secret_safe(framework)
    _assert_unsupported_provider(framework)
    _ok("v5.2.0 voice-input capability preflight is mock-safe")


if __name__ == "__main__":
    main()
