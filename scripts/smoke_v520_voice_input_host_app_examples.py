"""v5.2.0 voice-input host-app examples smoke."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import runpy
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


def _run_example(path: Path) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        runpy.run_path(str(path), run_name="__main__")
    return buffer.getvalue()


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v520_voice_input_host_app_examples.md"
    _require(path.exists(), "missing docs/v520_voice_input_host_app_examples.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Voice Input Host-App Examples",
        "app_voice_input_capability_preflight.py",
        "app_voice_input_session_text_fallback.py",
        "app_voice_input_missing_credentials.py",
        "import framework",
        "get_voice_input_capabilities",
        "create_voice_input_session",
        "text_fallback_result",
        "missing_credentials",
        "real_stt_not_implemented",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"voice-input host-app examples doc missing phrase: {phrase}")
    _ok("v5.2.0 voice-input host-app examples doc is documented")


def _assert_examples_exist_and_public_only(root: Path) -> None:
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
        "OPENAI_API_KEY =",
        "GOOGLE_API_KEY =",
    ]

    for path in examples:
        _require(path.exists(), f"missing example: {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("import framework" in text, f"{path.name} should use public framework import")
        for phrase in forbidden_phrases:
            _require(phrase not in text, f"{path.name} contains forbidden phrase: {phrase}")

    _ok("voice-input examples use public imports only")


def _assert_import_safe(root: Path) -> None:
    sys.path.insert(0, str(root))
    before = set(sys.modules)
    __import__("framework")
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
    _require(not hits, "examples/import framework eagerly loaded voice/STT provider modules: " + ", ".join(hits[:16]))
    _ok("voice-input examples keep framework import provider safe")


def _assert_run_capability_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_voice_input_capability_preflight.py")
    _require("voice_input_session: True" in output, "capability example should print voice input session support")
    _require("text_fallback: True" in output, "capability example should print text fallback support")
    _require("real_stt: False" in output, "capability example should not overclaim real STT")
    _require("provider_status: disabled" in output, "capability example should report disabled by default")
    _ok("voice-input capability example runs")


def _assert_run_session_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_voice_input_session_text_fallback.py")
    _require("listen_outcome: unavailable" in output, "session example should show unavailable listen result")
    _require("listen_error: unavailable" in output, "session example should show unavailable error")
    _require("listen_status: disabled" in output, "session example should show disabled provider status")
    _require("fallback_outcome: completed" in output, "session example should complete text fallback")
    _require("fallback_text: 今日は少し眠いです。" in output, "session example should preserve fallback text")
    _require("closed: True" in output, "session example should close context manager")
    _require("voice_input.started" in output, "session example should emit started event")
    _require("voice_input.unavailable" in output, "session example should emit unavailable event")
    _ok("voice-input session text fallback example runs")


def _assert_run_missing_credentials_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_voice_input_missing_credentials.py")
    _require("provider_status: missing_credentials" in output, "missing credentials example should show provider status")
    _require("outcome: unavailable" in output, "missing credentials example should show unavailable outcome")
    _require("error_code: missing_credentials" in output, "missing credentials example should show typed error")
    _require("retryable: True" in output, "missing credentials example should be retryable")
    _ok("voice-input missing-credentials example runs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_examples_exist_and_public_only(root)
    _assert_import_safe(root)
    _assert_run_capability_example(root)
    _assert_run_session_example(root)
    _assert_run_missing_credentials_example(root)
    _ok("v5.2.0 voice-input host-app examples are mock-safe")


if __name__ == "__main__":
    main()
