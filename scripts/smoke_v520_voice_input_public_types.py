"""v5.2.0 public voice-input type smoke."""

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
    path = root / "docs" / "v520_voice_input_public_types.md"
    _require(path.exists(), "missing docs/v520_voice_input_public_types.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Public Voice Input Types",
        "VoiceInputOutcome",
        "VoiceInputErrorCode",
        "VoiceInputRequest",
        "VoiceInputResult",
        "completed",
        "no_input",
        "interrupted",
        "unavailable",
        "closed",
        "Import safety",
        "create_voice_input_session",
        "VoiceInputSession",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"voice-input public type doc missing phrase: {phrase}")
    _ok("v5.2.0 public voice-input type doc is documented")


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
    _ok("public voice-input type import stays provider/internal safe")
    return framework


def _assert_public_exports(framework) -> None:
    required = [
        "VoiceInputOutcome",
        "VoiceInputErrorCode",
        "VoiceInputRequest",
        "VoiceInputResult",
    ]
    public = set(getattr(framework, "__all__", ()))
    for name in required:
        _require(hasattr(framework, name), f"framework missing public symbol: {name}")
        _require(name in public, f"framework.__all__ missing public symbol: {name}")
    _ok("framework exports public voice-input types")


def _assert_request_contract(framework) -> None:
    request = framework.VoiceInputRequest(
        language="ja-JP",
        timeout_ms=1000,
        max_duration_ms=3000,
        metadata={"purpose": "smoke", "api_key": "should-not-leak"},
    )
    _require(request.language == "ja-JP", "VoiceInputRequest language should be stored")
    _require(request.timeout_ms == 1000, "VoiceInputRequest timeout_ms should be stored")
    _require(request.max_duration_ms == 3000, "VoiceInputRequest max_duration_ms should be stored")
    _require(request.metadata["api_key"] == "<redacted>", "VoiceInputRequest should redact secret-like metadata")
    _require("should-not-leak" not in repr(request), "VoiceInputRequest repr should not leak secret-like metadata")

    fallback = framework.VoiceInputRequest.from_text_fallback(language="en-US")
    _require(fallback.metadata["input_mode"] == "text_fallback", "text fallback request should be marked")
    _ok("VoiceInputRequest contract is provider-neutral and secret-safe")


def _assert_result_contract(framework) -> None:
    completed = framework.VoiceInputResult.completed(
        "hello",
        language="en-US",
        confidence=0.75,
        duration_ms=1234,
        public_metadata={"source": "mock", "token": "should-not-leak"},
    )
    _require(completed.outcome == framework.VoiceInputOutcome.COMPLETED, "completed outcome mismatch")
    _require(completed.text == "hello", "completed text mismatch")
    _require(completed.is_completed, "completed result should be completed")
    _require(completed.is_terminal, "completed result should be terminal")
    _require(completed.public_metadata["token"] == "<redacted>", "result should redact secret-like metadata")
    _require("should-not-leak" not in repr(completed), "VoiceInputResult repr should not leak secret-like metadata")

    no_input = framework.VoiceInputResult.no_input()
    _require(no_input.outcome == framework.VoiceInputOutcome.NO_INPUT, "no_input outcome mismatch")
    _require(no_input.public_error_code == framework.VoiceInputErrorCode.NO_INPUT, "no_input error code mismatch")
    _require(no_input.retryable, "no_input should be retryable")

    unavailable = framework.VoiceInputResult.unavailable()
    _require(unavailable.outcome == framework.VoiceInputOutcome.UNAVAILABLE, "unavailable outcome mismatch")
    _require(unavailable.public_error_code == framework.VoiceInputErrorCode.UNAVAILABLE, "unavailable error code mismatch")

    closed = framework.VoiceInputResult.closed()
    _require(closed.outcome == framework.VoiceInputOutcome.CLOSED, "closed outcome mismatch")
    _require(closed.public_error_code == framework.VoiceInputErrorCode.SESSION_CLOSED, "closed error code mismatch")

    _ok("VoiceInputResult contract is provider-neutral and secret-safe")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    framework = _assert_import_safe(root)
    _assert_public_exports(framework)
    _assert_request_contract(framework)
    _assert_result_contract(framework)
    _ok("v5.2.0 public voice-input types are mock-safe")


if __name__ == "__main__":
    main()
