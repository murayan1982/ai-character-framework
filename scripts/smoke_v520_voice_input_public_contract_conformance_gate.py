"""v5.2.0 public voice-input contract conformance gate."""

from __future__ import annotations

import importlib
import inspect
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
    path = root / "docs" / "v520_voice_input_public_contract_conformance_gate.md"
    _require(path.exists(), "missing docs/v520_voice_input_public_contract_conformance_gate.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Voice Input Public Contract Conformance Gate",
        "VoiceInputOutcome",
        "VoiceInputErrorCode",
        "VoiceInputRequest",
        "VoiceInputResult",
        "VoiceInputProviderStatus",
        "VoiceInputProviderConfig",
        "VoiceInputCapabilities",
        "resolve_voice_input_provider_config",
        "get_voice_input_capabilities",
        "create_voice_input_session",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
        "Public import rule",
        "Factory signature rule",
        "Typed result rule",
        "Capability preflight rule",
        "Session rule",
        "Host-app example rule",
        "Current limitation",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"voice-input conformance gate doc missing phrase: {phrase}")
    _ok("v5.2.0 voice-input public contract conformance gate doc is documented")


def _import_framework_safely(root: Path):
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
    _ok("framework public import stays voice/STT provider safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "VoiceInputOutcome",
        "VoiceInputErrorCode",
        "VoiceInputRequest",
        "VoiceInputResult",
        "VoiceInputProviderStatus",
        "VoiceInputProviderConfig",
        "VoiceInputCapabilities",
        "resolve_voice_input_provider_config",
        "get_voice_input_capabilities",
        "create_voice_input_session",
        "VoiceInputSession",
        "VoiceInputSessionInfo",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")

    _ok("framework exports all public voice-input conformance symbols")


def _assert_factory_signature(framework) -> None:
    sig = inspect.signature(framework.create_voice_input_session)
    _require(sig.parameters, "create_voice_input_session should expose explicit parameters")
    for param in sig.parameters.values():
        _require(
            param.kind is inspect.Parameter.KEYWORD_ONLY,
            f"create_voice_input_session parameter should be keyword-only: {param.name}",
        )

    expected = {
        "project_root",
        "provider",
        "language",
        "real_stt_enabled",
        "allow_provider_execution",
        "credential_env",
        "public_metadata",
    }
    _require(expected.issubset(set(sig.parameters)), "create_voice_input_session missing expected public parameters")
    _ok("create_voice_input_session signature is explicit and keyword-only")


def _assert_public_types(framework) -> None:
    request = framework.VoiceInputRequest(
        language="ja-JP",
        timeout_ms=1000,
        max_duration_ms=2000,
        metadata={"purpose": "conformance", "token": "should-not-leak"},
    )
    _require(request.language == "ja-JP", "VoiceInputRequest should preserve language")
    _require(request.metadata["token"] == "<redacted>", "VoiceInputRequest should redact secret-like metadata")
    _require("should-not-leak" not in repr(request), "VoiceInputRequest repr should not leak secret-like metadata")

    completed = framework.VoiceInputResult.completed("hello", confidence=1.0)
    _require(completed.outcome == framework.VoiceInputOutcome.COMPLETED, "completed result outcome mismatch")
    _require(completed.is_completed, "completed result should be completed")
    _require(completed.is_terminal, "completed result should be terminal")

    no_input = framework.VoiceInputResult.no_input()
    _require(no_input.outcome == framework.VoiceInputOutcome.NO_INPUT, "no_input result outcome mismatch")
    _require(no_input.public_error_code == framework.VoiceInputErrorCode.NO_INPUT, "no_input error code mismatch")
    _require(no_input.retryable, "no_input should be retryable")

    interrupted = framework.VoiceInputResult.interrupted()
    _require(interrupted.outcome == framework.VoiceInputOutcome.INTERRUPTED, "interrupted result outcome mismatch")
    _require(interrupted.retryable, "interrupted should be retryable")

    unavailable = framework.VoiceInputResult.unavailable(public_metadata={"api_key": "should-not-leak"})
    _require(unavailable.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "unavailable result outcome mismatch")
    _require(unavailable.public_error_code == framework.VoiceInputErrorCode.UNAVAILABLE, "unavailable error code mismatch")
    _require(unavailable.public_metadata["api_key"] == "<redacted>", "unavailable result metadata should redact secret-like keys")

    failed = framework.VoiceInputResult.failed(public_error_code=framework.VoiceInputErrorCode.PROVIDER_ERROR)
    _require(failed.outcome == framework.VoiceInputOutcome.FAILED, "failed result outcome mismatch")

    closed = framework.VoiceInputResult.closed()
    _require(closed.outcome == framework.VoiceInputOutcome.CLOSED, "closed result outcome mismatch")
    _require(closed.public_error_code == framework.VoiceInputErrorCode.SESSION_CLOSED, "closed error code mismatch")

    _ok("public voice-input request/result types conform")


def _assert_capability_preflight(framework) -> None:
    disabled = framework.get_voice_input_capabilities(credential_env={})
    _require(disabled.provider_status == framework.VoiceInputProviderStatus.DISABLED, "default capability should be disabled")
    _require(disabled.supports_voice_input_session, "voice-input session should be supported")
    _require(disabled.supports_text_fallback, "text fallback should be supported")
    _require(not disabled.supports_real_stt, "real STT should not be supported yet")

    missing = framework.get_voice_input_capabilities(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    _require(missing.provider_status == framework.VoiceInputProviderStatus.MISSING_CREDENTIALS, "missing credential status mismatch")
    _require(missing.retryable, "missing credentials should be retryable")

    blocked = framework.get_voice_input_capabilities(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=False,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    _require(blocked.provider_status == framework.VoiceInputProviderStatus.PROVIDER_EXECUTION_NOT_ALLOWED, "provider guard status mismatch")

    unsupported = framework.get_voice_input_capabilities(
        provider="unknown-stt",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    _require(unsupported.provider_status == framework.VoiceInputProviderStatus.UNSUPPORTED_PROVIDER, "unsupported provider status mismatch")

    not_implemented = framework.get_voice_input_capabilities(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    _require(
        not_implemented.provider_status == framework.VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED,
        "configured real STT should remain not implemented",
    )
    _require(not not_implemented.supports_real_stt, "capability preflight must not overclaim real STT support")
    _require("should-not-leak" not in repr(not_implemented), "capability preflight should not leak credential values")

    config = framework.resolve_voice_input_provider_config(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "should-not-leak"},
    )
    _require(config.credentials_available, "provider config should detect credential presence")
    _require(config.credential_source == "OPENAI_API_KEY", "provider config should expose credential source key only")
    _require("should-not-leak" not in repr(config), "provider config should not leak credential values")

    _ok("public voice-input capability preflight conforms")


def _assert_session_contract(framework) -> None:
    events = []
    session = framework.create_voice_input_session(language="ja-JP", public_metadata={"secret": "should-not-leak"})
    session.on_event(events.append)

    _require(isinstance(session.info, framework.VoiceInputSessionInfo), "session.info should be VoiceInputSessionInfo")
    _require(isinstance(session.capabilities, framework.VoiceInputCapabilities), "session.capabilities should be VoiceInputCapabilities")
    _require(session.info.provider_status == framework.VoiceInputProviderStatus.DISABLED, "default session provider status mismatch")
    _require(session.info.public_metadata["secret"] == "<redacted>", "session info should redact secret-like metadata")

    result = session.listen_result()
    _require(result.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "default listen result should be unavailable")
    _require(result.public_metadata["provider_status"] == "disabled", "default listen result provider status mismatch")
    _require(any(event["type"] == "voice_input.started" for event in events), "session should emit started event")
    _require(any(event["type"] == "voice_input.unavailable" for event in events), "session should emit unavailable event")

    fallback = session.text_fallback_result("今日は眠いです。")
    _require(fallback.outcome == framework.VoiceInputOutcome.COMPLETED, "text fallback should complete")
    _require(fallback.text == "今日は眠いです。", "text fallback should preserve text")

    session.close()
    session.dispose()
    _require(session.is_closed, "session should be closed")
    closed = session.listen_result()
    _require(closed.outcome == framework.VoiceInputOutcome.CLOSED, "closed session should return closed result")
    _require(closed.public_error_code == framework.VoiceInputErrorCode.SESSION_CLOSED, "closed session error code mismatch")

    with framework.create_voice_input_session() as managed:
        _require(not managed.is_closed, "managed session should be open in context")
    _require(managed.is_closed, "managed session should close on context exit")

    missing_session = framework.create_voice_input_session(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    missing_result = missing_session.listen_result()
    _require(missing_session.info.provider_status == framework.VoiceInputProviderStatus.MISSING_CREDENTIALS, "missing session provider status mismatch")
    _require(missing_result.public_error_code == framework.VoiceInputErrorCode.MISSING_CREDENTIALS, "missing session result error code mismatch")

    unsupported_session = framework.create_voice_input_session(
        provider="unknown-stt",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )
    unsupported_result = unsupported_session.listen_result()
    _require(unsupported_result.public_error_code == framework.VoiceInputErrorCode.INVALID_REQUEST, "unsupported session should map to invalid_request")

    _ok("public VoiceInputSession contract conforms")


def _assert_host_app_examples(root: Path) -> None:
    examples = [
        root / "examples" / "app_voice_input_capability_preflight.py",
        root / "examples" / "app_voice_input_session_text_fallback.py",
        root / "examples" / "app_voice_input_missing_credentials.py",
    ]
    forbidden_phrases = [
        "from stt",
        "import stt",
        "from plugins",
        "import speech_recognition",
        "import whisper",
        "import sounddevice",
        "import pyaudio",
        "sys.path",
        "chdir(",
        "OPENAI_API_KEY =",
        "GOOGLE_API_KEY =",
    ]

    for path in examples:
        _require(path.exists(), f"missing host-app example: {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("import framework" in text, f"{path.name} should use public framework import")
        for phrase in forbidden_phrases:
            _require(phrase not in text, f"{path.name} contains forbidden phrase: {phrase}")

    _ok("voice-input host-app examples conform to public-only rule")


def _assert_readme(root: Path) -> None:
    path = root / "README.md"
    _require(path.exists(), "missing README.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_links = [
        "v520_voice_input_public_types.md",
        "v520_voice_input_session_skeleton.md",
        "v520_voice_input_capability_preflight.md",
        "v520_voice_input_session_preflight_wiring.md",
        "v520_voice_input_host_app_examples.md",
        "v520_voice_input_public_contract_conformance_gate.md",
    ]
    for link in required_links:
        _require(link in text, f"README missing v5.2.0 voice-input link: {link}")
    _ok("README links public voice-input contract docs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _import_framework_safely(root)
    _assert_public_exports(framework)
    _assert_factory_signature(framework)
    _assert_public_types(framework)
    _assert_capability_preflight(framework)
    _assert_session_contract(framework)
    _assert_host_app_examples(root)
    _assert_readme(root)
    _ok("v5.2.0 public voice-input contract conformance gate passed")


if __name__ == "__main__":
    main()
