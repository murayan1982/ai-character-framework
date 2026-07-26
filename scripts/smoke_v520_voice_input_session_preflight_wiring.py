"""v5.2.0 voice-input session preflight wiring smoke."""

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
    path = root / "docs" / "v520_voice_input_session_preflight_wiring.md"
    _require(path.exists(), "missing docs/v520_voice_input_session_preflight_wiring.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Voice Input Session Preflight Wiring",
        "session.capabilities",
        "session.info.provider_status",
        "missing_credentials",
        "provider_execution_not_allowed",
        "unsupported_provider",
        "real_stt_not_implemented",
        "Result mapping",
        "voice_input.started",
        "voice_input.unavailable",
        "Import safety",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"voice-input session preflight wiring doc missing phrase: {phrase}")
    _ok("v5.2.0 voice-input session preflight wiring doc is documented")


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
    _ok("voice-input session preflight wiring import stays provider/internal safe")
    return framework


def _assert_default_session_capabilities(framework) -> None:
    events = []
    session = framework.create_voice_input_session(language="ja-JP", public_metadata={"token": "secret"})
    session.on_event(events.append)

    _require(session.info.provider_status == framework.VoiceInputProviderStatus.DISABLED, "default session status should be disabled")
    _require(session.capabilities.provider_status == framework.VoiceInputProviderStatus.DISABLED, "default capabilities status should be disabled")
    _require(session.info.public_metadata["token"] == "<redacted>", "session info should redact secret-like metadata")

    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "default result should be unavailable")
    _require(result.public_error_code == framework.VoiceInputErrorCode.UNAVAILABLE, "default error code should be unavailable")
    _require(result.public_metadata["provider_status"] == "disabled", "default result should include disabled provider_status")
    _require(result.public_metadata["reason"] == "real_stt_disabled", "default result reason mismatch")
    _require(any(event["type"] == "voice_input.started" for event in events), "listen_result should emit started event")
    _require(any(event["type"] == "voice_input.unavailable" for event in events), "listen_result should emit unavailable event")
    _ok("default VoiceInputSession uses capability preflight")


def _assert_missing_credentials_session(framework) -> None:
    session = framework.create_voice_input_session(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    _require(session.info.provider_status == framework.VoiceInputProviderStatus.MISSING_CREDENTIALS, "session info should report missing credentials")
    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "missing credential result should be unavailable")
    _require(result.public_error_code == framework.VoiceInputErrorCode.MISSING_CREDENTIALS, "missing credential error code mismatch")
    _require(result.retryable, "missing credentials should be retryable")
    _require(result.public_metadata["provider_status"] == "missing_credentials", "missing credential provider status metadata mismatch")
    _ok("VoiceInputSession reports missing credentials through typed result")


def _assert_guard_blocked_session(framework) -> None:
    session = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=False,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    _require(session.info.provider_status == framework.VoiceInputProviderStatus.PROVIDER_EXECUTION_NOT_ALLOWED, "session info should report provider execution guard")
    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "guard-blocked result should be unavailable")
    _require(result.public_metadata["provider_status"] == "provider_execution_not_allowed", "guard-blocked provider status mismatch")
    _require("should-not-leak" not in repr(session.info), "session info should not leak credential values")
    _require("should-not-leak" not in repr(result), "result should not leak credential values")
    _ok("VoiceInputSession respects provider execution guard")


def _assert_not_implemented_session(framework) -> None:
    session = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    _require(session.info.provider_status == framework.VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED, "session info should report real STT not implemented")
    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "not-implemented result should be unavailable")
    _require(result.public_metadata["provider_status"] == "real_stt_not_implemented", "not-implemented provider status mismatch")
    _require(not result.public_metadata["supports_real_stt"], "supports_real_stt should remain false")
    _ok("VoiceInputSession does not overclaim real STT readiness")


def _assert_unsupported_provider_session(framework) -> None:
    session = framework.create_voice_input_session(
        provider="unknown-stt",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    _require(session.info.provider_status == framework.VoiceInputProviderStatus.UNSUPPORTED_PROVIDER, "session info should report unsupported provider")
    result = session.listen_result()
    _require(result.public_error_code == framework.VoiceInputErrorCode.INVALID_REQUEST, "unsupported provider should map to invalid_request")
    _require(result.public_metadata["provider_status"] == "unsupported_provider", "unsupported provider status metadata mismatch")
    _ok("VoiceInputSession reports unsupported provider safely")


def _assert_closed_still_closed(framework) -> None:
    session = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    session.close()
    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.CLOSED, "closed session should still return closed")
    _require(result.public_error_code == framework.VoiceInputErrorCode.SESSION_CLOSED, "closed session error code mismatch")
    _ok("VoiceInputSession close result takes precedence over preflight status")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_default_session_capabilities(framework)
    _assert_missing_credentials_session(framework)
    _assert_guard_blocked_session(framework)
    _assert_not_implemented_session(framework)
    _assert_unsupported_provider_session(framework)
    _assert_closed_still_closed(framework)
    _ok("v5.2.0 voice-input session preflight wiring is mock-safe")


if __name__ == "__main__":
    main()
