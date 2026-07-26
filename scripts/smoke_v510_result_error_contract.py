"""Mock-safe v5.1.0 result/error contract smoke.

This is a P0/FW-F3 checkpoint. It documents and verifies the shared public
outcome/error vocabulary before text chat runtime behavior is changed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


SHARED_OUTCOMES = {
    "completed",
    "interrupted",
    "unavailable",
    "blocked",
    "skipped",
    "rejected",
    "failed",
    "expired",
    "cancelled",
}

PUBLIC_ERROR_CODES = {
    "configuration_missing",
    "provider_unavailable",
    "authentication_required",
    "rate_limited",
    "request_cancelled",
    "timeout",
    "unsupported_capability",
    "session_closed",
    "invalid_request",
    "artifact_missing",
    "artifact_expired",
    "provider_request_failed",
    "empty_response",
    "unknown_error",
}

NON_PLAYABLE_OUTCOMES = {
    "unavailable",
    "skipped",
    "rejected",
    "failed",
    "expired",
    "cancelled",
    "blocked",
}

FORBIDDEN_PUBLIC_FRAGMENTS = (
    "api_key",
    "API_KEY",
    "secret",
    "provider raw",
    "traceback",
    "ElevenLabs",
    "OpenAIError",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_importable() -> Path:
    root = _repo_root()
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    return root


def _force_mock_safe_environment() -> None:
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _assert_contract_doc(root: Path) -> None:
    doc_path = root / "docs" / "v510_result_error_contract.md"
    _require(doc_path.exists(), "missing docs/v510_result_error_contract.md")
    text = _read_text(doc_path)

    missing_outcomes = sorted(outcome for outcome in SHARED_OUTCOMES if outcome not in text)
    _require(not missing_outcomes, f"result/error contract doc missing outcomes: {missing_outcomes}")

    missing_codes = sorted(code for code in PUBLIC_ERROR_CODES if code not in text)
    _require(not missing_codes, f"result/error contract doc missing public error codes: {missing_codes}")

    required_phrases = [
        "TextChatResult",
        "VoiceOutputResult",
        "provider-neutral",
        "safe_message",
        "retryable",
        "must not expose",
        "raw local provider paths are not exposed",
    ]
    missing_phrases = [phrase for phrase in required_phrases if phrase not in text]
    _require(not missing_phrases, f"result/error contract doc missing phrases: {missing_phrases}")
    _ok("v5.1.0 result/error contract doc is documented")


def _assert_voice_output_result_shape(framework: object) -> None:
    request_type = getattr(framework, "VoiceOutputRequest", None)
    _require(request_type is not None, "VoiceOutputRequest is missing from public framework surface")

    session = framework.create_voice_output_session()
    speak = getattr(session, "speak", None) or getattr(session, "create_output", None)
    _require(callable(speak), "VoiceOutputSession exposes neither speak nor create_output")

    request = request_type(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="v510_result_error_contract",
        language_code="ja",
    )
    result = speak(request)

    required_attrs = (
        "request_state",
        "audio_ready",
        "audio_url",
        "audio_artifact_ref",
        "audio_handoff_kind",
        "has_audio_handoff",
        "is_generated",
        "public_metadata",
    )
    missing_attrs = [attr for attr in required_attrs if not hasattr(result, attr)]
    _require(not missing_attrs, f"VoiceOutputResult missing public attrs: {missing_attrs}")

    _info(f"voice output request_state={result.request_state}")
    _require(
        result.request_state in SHARED_OUTCOMES or result.request_state == "generated",
        f"VoiceOutputResult request_state is outside public vocabulary: {result.request_state}",
    )

    if result.request_state in NON_PLAYABLE_OUTCOMES:
        _require(result.audio_ready is False, "non-playable VoiceOutputResult must not be audio_ready")
        _require(result.audio_url is None, "non-playable VoiceOutputResult must not expose audio_url")
        _require(
            result.audio_artifact_ref is None,
            "non-playable VoiceOutputResult must not expose audio_artifact_ref",
        )
        _require(result.has_audio_handoff is False, "non-playable result must not have audio handoff")
        _require(result.audio_handoff_kind == "none", "non-playable handoff kind must be none")
        _require(result.is_generated is False, "non-playable result must not be generated")
        _ok("VoiceOutputResult non-playable outcome is public-safe")

    public_text = " ".join(
        str(getattr(result, attr, ""))
        for attr in ("message", "public_message", "safe_message", "public_metadata")
    )
    leaked = [fragment for fragment in FORBIDDEN_PUBLIC_FRAGMENTS if fragment in public_text]
    _require(not leaked, f"VoiceOutputResult public surface may expose private/provider details: {leaked}")
    _ok("VoiceOutputResult public surface hides provider/private details")


def _assert_text_chat_result_status(framework: object) -> None:
    exported = set(getattr(framework, "__all__", ()))
    text_result = getattr(framework, "TextChatResult", None)
    if text_result is None or "TextChatResult" not in exported:
        _warn("TextChatResult is not public yet; record as FW-F3 follow-up")
        return

    for attr in ("outcome", "text", "public_error_code", "safe_message", "retryable"):
        _require(hasattr(text_result, attr) or attr in getattr(text_result, "__annotations__", {}), f"TextChatResult missing field: {attr}")
    _ok("TextChatResult public shape is available")


def main() -> None:
    root = _ensure_repo_importable()
    _force_mock_safe_environment()

    import framework  # noqa: PLC0415

    _assert_contract_doc(root)
    _assert_voice_output_result_shape(framework)
    _assert_text_chat_result_status(framework)
    _ok("v5.1.0 result/error contract checkpoint is mock-safe")


if __name__ == "__main__":
    main()
