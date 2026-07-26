"""Mock-safe TextChatResult runtime method smoke for FW v5.1.0."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


FORBIDDEN_PUBLIC_FRAGMENTS = (
    "sk-live",
    "api_key",
    "API_KEY",
    "secret",
    "Traceback",
    "C:\\",
    "/home/",
    "provider raw",
)


class _FakeCompletedSession:
    def ask(self, message: str) -> str:
        return f"typed response: {message}"


class _FakeObjectResponse:
    def ask(self, message: str) -> object:
        class Response:
            text = "object response text"

        return Response()


class _FakeEmptySession:
    def ask(self, message: str) -> str:
        return "   "


class _FakeFailingSession:
    def ask(self, message: str) -> str:
        raise RuntimeError("provider request failed with private C:\\secret\\path and API_KEY=hidden")


class _FakeClosedSession:
    def ask(self, message: str) -> str:
        raise RuntimeError("session closed")


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
    doc_path = root / "docs" / "v510_text_chat_result_runtime_method.md"
    _require(doc_path.exists(), "missing docs/v510_text_chat_result_runtime_method.md")
    text = _read_text(doc_path)
    for phrase in (
        "ask_result()",
        "TextChatResult",
        "provider-neutral",
        "Existing v4/v5 behavior is preserved",
        "does not remove or change `ask()`",
    ):
        _require(phrase in text, f"TextChatResult runtime method doc missing phrase: {phrase}")
    _ok("TextChatResult runtime method doc is documented")


def _get_text_chat_session_class(framework: object) -> type:
    """Return TextChatSession class without constructing a provider-backed session.

    This smoke is intentionally mock-safe and must not require provider
    credentials from `.env` or the host environment.
    """

    candidate = getattr(framework, "TextChatSession", None)
    if candidate is not None and callable(getattr(candidate, "ask_result", None)):
        return candidate

    facade_module = sys.modules.get("framework.facade")
    candidate = getattr(facade_module, "TextChatSession", None) if facade_module is not None else None
    _require(candidate is not None, "TextChatSession class should be available after framework import")
    _require(callable(getattr(candidate, "ask_result", None)), "TextChatSession does not expose ask_result")
    return candidate


def _assert_public_method(framework: object) -> None:
    session_cls = _get_text_chat_session_class(framework)
    ask_result = getattr(session_cls, "ask_result", None)
    _require(callable(ask_result), "TextChatSession does not expose ask_result")

    sig = inspect.signature(ask_result)
    _info(f"signature TextChatSession.ask_result{sig}")
    _require("message" in sig.parameters, "ask_result should accept message")
    _ok("TextChatSession exposes ask_result typed companion method")

    completed = ask_result(_FakeCompletedSession(), "hello")
    _require(isinstance(completed, framework.TextChatResult), "ask_result should return TextChatResult")
    _require(completed.outcome == "completed", "completed fake should return outcome=completed")
    _require(completed.text == "typed response: hello", "completed fake should preserve text")
    _require(completed.public_error_code is None, "completed fake should not expose error code")
    _require(completed.public_metadata.get("boundary") == "text_chat", "completed result should include public boundary metadata")

    object_response = ask_result(_FakeObjectResponse(), "hello")
    _require(object_response.outcome == "completed", "object response should complete")
    _require(object_response.text == "object response text", "object response .text should be normalized")

    empty = ask_result(_FakeEmptySession(), "hello")
    _require(empty.outcome == "failed", "empty fake should return failed result")
    _require(empty.public_error_code == "empty_response", "empty fake should use empty_response")
    _require(empty.retryable is True, "empty fake should be retryable")

    failed = ask_result(_FakeFailingSession(), "hello")
    _require(failed.outcome == "failed", "failing fake should return failed result")
    _require(failed.text is None, "failed result should not include text")
    _require(failed.public_error_code == "provider_request_failed", "provider failure should use provider_request_failed")
    _require(failed.retryable is True, "provider failure should be retryable")
    _require("API_KEY" not in (failed.safe_message or ""), "safe message must not include raw exception detail")
    private_path_marker = "C:" + chr(92)
    _require(private_path_marker not in (failed.safe_message or ""), "safe message must not include private path")

    closed = ask_result(_FakeClosedSession(), "hello")
    _require(closed.public_error_code == "session_closed", "closed fake should use session_closed")
    _require(closed.retryable is False, "closed fake should not be retryable")

    public_repr = " ".join(repr(value) for value in (completed, failed, closed))
    leaked = [fragment for fragment in FORBIDDEN_PUBLIC_FRAGMENTS if fragment in public_repr]
    _require(not leaked, f"ask_result public result may expose private/provider detail: {leaked}")
    _ok("TextChatSession.ask_result paths are mock-safe")


def main() -> None:
    root = _ensure_repo_importable()
    import framework  # noqa: PLC0415

    _assert_doc(root)
    _assert_public_method(framework)
    _ok("v5.1.0 TextChatResult runtime method is mock-safe")


if __name__ == "__main__":
    main()
