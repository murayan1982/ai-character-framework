"""v5.2.0 realtime host-app examples smoke."""

from __future__ import annotations

import contextlib
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
    path = root / "docs" / "v520_realtime_host_app_examples.md"
    _require(path.exists(), "missing docs/v520_realtime_host_app_examples.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Realtime Host-App Examples",
        "app_realtime_session_event_flow.py",
        "app_realtime_event_payload_mapping.py",
        "app_realtime_closed_session_behavior.py",
        "import framework",
        "create_realtime_session",
        "RealtimeEvent",
        "RealtimeEventType",
        "RealtimeState",
        "RealtimeTurnResult",
        "realtime.turn.started",
        "realtime.session.closed",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"realtime host-app examples doc missing phrase: {phrase}")
    _ok("v5.2.0 realtime host-app examples doc is documented")


def _assert_examples_exist_and_public_only(root: Path) -> None:
    examples = [
        root / "examples" / "app_realtime_session_event_flow.py",
        root / "examples" / "app_realtime_event_payload_mapping.py",
        root / "examples" / "app_realtime_closed_session_behavior.py",
    ]
    forbidden_phrases = [
        "from stt",
        "import stt",
        "from llm",
        "import llm",
        "from plugins",
        "import speech_recognition",
        "import whisper",
        "import sounddevice",
        "import pyaudio",
        "import websocket",
        "import websockets",
        "sys.path",
        "chdir(",
        "OPENAI_API_KEY =",
        "GOOGLE_API_KEY =",
    ]

    for path in examples:
        _require(path.exists(), f"missing example: {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("import framework" in text, f"{path.name} should use public framework import")
        for phrase in forbidden_phrases:
            _require(phrase not in text, f"{path.name} contains forbidden phrase: {phrase}")

    _ok("realtime examples use public imports only")


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
        "websocket",
        "websockets",
    ]
    hits = sorted(name for name in loaded if any(fragment in name for fragment in forbidden_fragments))
    _require(not hits, "examples/import framework eagerly loaded realtime/provider modules: " + ", ".join(hits[:16]))
    _ok("realtime examples keep framework import provider safe")


def _assert_run_event_flow_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_realtime_session_event_flow.py")
    _require("result_outcome: completed" in output, "event flow example should complete mock turn")
    _require("result_input_text: 今日は少し眠いです。" in output, "event flow example should preserve input text")
    _require("result_mock_runtime: True" in output, "event flow example should mark mock runtime")
    _require("session_closed_inside: False" in output, "event flow example should be open inside context")
    _require("session_closed_after: True" in output, "event flow example should close after context")
    for event_name in [
        "realtime.turn.started",
        "realtime.voice_input.started",
        "realtime.voice_input.completed",
        "realtime.text_chat.started",
        "realtime.text_chat.completed",
        "realtime.voice_output.started",
        "realtime.voice_output.completed",
        "realtime.turn.completed",
        "realtime.session.closed",
    ]:
        _require(event_name in output, f"event flow example missing event: {event_name}")
    _ok("realtime session event-flow example runs")


def _assert_run_payload_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_realtime_event_payload_mapping.py")
    _require("event_type: realtime.turn.started" in output, "payload example should print event type")
    _require("state: listening" in output, "payload example should print state")
    _require("previous_state: idle" in output, "payload example should print previous state")
    _require("turn_id: example-turn" in output, "payload example should print turn id")
    _require("metadata_api_key: <redacted>" in output, "payload example should redact secret-like metadata")
    _require("should-not-leak" not in output, "payload example should not leak secret-like metadata")
    _ok("realtime event payload mapping example runs")


def _assert_run_closed_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_realtime_closed_session_behavior.py")
    _require("session_closed: True" in output, "closed example should close session")
    _require("session_state: closed" in output, "closed example should show closed state")
    _require("result_outcome: closed" in output, "closed example should return closed result")
    _require("error_code: session_closed" in output, "closed example should return typed error")
    _require("retryable: False" in output, "closed example should not be retryable")
    _ok("realtime closed-session example runs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_examples_exist_and_public_only(root)
    _assert_import_safe(root)
    _assert_run_event_flow_example(root)
    _assert_run_payload_example(root)
    _assert_run_closed_example(root)
    _ok("v5.2.0 realtime host-app examples are mock-safe")


if __name__ == "__main__":
    main()
