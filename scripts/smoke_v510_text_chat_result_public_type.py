"""Mock-safe TextChatResult public type smoke for FW v5.1.0."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path


REQUIRED_FIELDS = (
    "outcome",
    "text",
    "public_error_code",
    "safe_message",
    "retryable",
    "public_metadata",
)

FORBIDDEN_PUBLIC_FRAGMENTS = (
    "api_key",
    "API_KEY",
    "secret",
    "provider raw",
    "traceback",
    "ElevenLabs",
    "OpenAIError",
    "C:\\",
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
    doc_path = root / "docs" / "v510_text_chat_result_public_type.md"
    _require(doc_path.exists(), "missing docs/v510_text_chat_result_public_type.md")
    text = _read_text(doc_path)
    normalized_text = " ".join(text.split())
    for phrase in (
        "TextChatResult",
        "outcome",
        "public_error_code",
        "retryable",
        "public_metadata",
        "provider-neutral",
        "does not change the existing text chat runtime return behavior yet",
    ):
        _require(
            phrase in normalized_text,
            f"TextChatResult public type doc missing phrase: {phrase}",
        )
    _ok("TextChatResult public type doc is documented")


def _assert_result_error_doc_updated(root: Path) -> None:
    doc_path = root / "docs" / "v510_result_error_contract.md"
    _require(doc_path.exists(), "missing docs/v510_result_error_contract.md")
    text = _read_text(doc_path)
    _require(
        "TextChatResult public type is now available" in text,
        "result/error contract doc should mention that TextChatResult is now public",
    )
    _require(
        "Text Chat typed result absence is recorded" not in text,
        "result/error contract doc still describes TextChatResult as absent",
    )
    _ok("result/error contract doc is updated for public TextChatResult")


def _assert_public_type(framework: object) -> None:
    exports = set(getattr(framework, "__all__", ()))
    _require("TextChatResult" in exports, "TextChatResult is not exported via framework.__all__")
    result_type = getattr(framework, "TextChatResult", None)
    _require(result_type is not None, "framework.TextChatResult is missing")
    _require(dataclasses.is_dataclass(result_type), "TextChatResult should be a dataclass")

    annotations = getattr(result_type, "__annotations__", {})
    missing = [field for field in REQUIRED_FIELDS if field not in annotations]
    _require(not missing, f"TextChatResult missing annotations: {missing}")
    _ok("TextChatResult public shape is exported")

    completed = result_type.completed("take an early rest today")
    _require(completed.outcome == "completed", "completed result should use outcome=completed")
    _require(completed.text, "completed result should contain text")
    _require(completed.public_error_code is None, "completed result should not expose error code")
    _require(completed.retryable is False, "completed result should not be retryable")
    _require(completed.is_completed is True, "completed result should report is_completed")
    _require(completed.has_text is True, "completed result should report has_text")

    failed = result_type.failed(
        public_error_code="provider_unavailable",
        safe_message="Text chat provider is not available.",
        retryable=True,
    )
    _require(failed.outcome == "failed", "failed result should use outcome=failed")
    _require(failed.text is None, "failed result should not contain text")
    _require(failed.public_error_code == "provider_unavailable", "failed result should expose public error code")
    _require(failed.retryable is True, "failed result retryable flag should be preserved")
    _require(failed.is_failed is True, "failed result should report is_failed")

    interrupted = result_type.interrupted(safe_message="Text chat request was interrupted.")
    _require(interrupted.outcome == "interrupted", "interrupted result should use outcome=interrupted")
    _require(interrupted.public_error_code == "request_cancelled", "interrupted result should use request_cancelled")
    _require(interrupted.is_interrupted is True, "interrupted result should report is_interrupted")
    _ok("TextChatResult constructors and helpers are mock-safe")

    public_repr = " ".join(repr(value) for value in (completed, failed, interrupted))
    leaked = [fragment for fragment in FORBIDDEN_PUBLIC_FRAGMENTS if fragment in public_repr]
    _require(not leaked, f"TextChatResult repr may expose private/provider details: {leaked}")
    _ok("TextChatResult public representation hides private/provider details")


def main() -> None:
    root = _ensure_repo_importable()
    import framework  # noqa: PLC0415

    _assert_doc(root)
    _assert_result_error_doc_updated(root)
    _assert_public_type(framework)
    _info("TextChatResult runtime-returning text chat method is covered by smoke_v510_text_chat_result_runtime_method.py")
    _ok("v5.1.0 TextChatResult public type is mock-safe")


if __name__ == "__main__":
    main()
