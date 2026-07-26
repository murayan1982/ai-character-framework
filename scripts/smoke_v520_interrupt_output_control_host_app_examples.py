"""v5.2.0 interrupt / output-control host-app examples smoke."""

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
    path = root / "docs" / "v520_interrupt_output_control_host_app_examples.md"
    _require(path.exists(), "missing docs/v520_interrupt_output_control_host_app_examples.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Interrupt / Output-Control Host-App Examples",
        "app_realtime_interrupt_handling.py",
        "app_realtime_output_flush_handling.py",
        "app_realtime_barge_in_policy.py",
        "InterruptRequest.user_barge_in",
        "InterruptResult",
        "get_tts_queue_state",
        "flush_output",
        "BargeInPolicy.hard_cancel",
        "provider_cancel_supported=False",
        "queue_flush_supported=False",
        "flush_outcome=nothing_to_flush",
        "import framework",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"interrupt/output-control examples doc missing phrase: {phrase}")
    _ok("v5.2.0 interrupt/output-control host-app examples doc is documented")


def _assert_examples_exist_and_public_only(root: Path) -> None:
    examples = [
        root / "examples" / "app_realtime_interrupt_handling.py",
        root / "examples" / "app_realtime_output_flush_handling.py",
        root / "examples" / "app_realtime_barge_in_policy.py",
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

    _ok("interrupt/output-control examples use public imports only")


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
    _require(not hits, "examples/import framework eagerly loaded interrupt/output provider modules: " + ", ".join(hits[:16]))
    _ok("interrupt/output-control examples keep framework import provider safe")


def _assert_run_interrupt_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_realtime_interrupt_handling.py")
    _require("interrupt_outcome: not_implemented" in output, "interrupt example should report not_implemented")
    _require("interrupt_scope: all" in output, "interrupt example should use all scope")
    _require("interrupt_reason: user_barge_in" in output, "interrupt example should use user_barge_in reason")
    _require("provider_cancel_supported: False" in output, "interrupt example should not overclaim provider cancel")
    _require("queue_flush_supported: False" in output, "interrupt example should not overclaim queue flush")
    _require("realtime.interrupt.requested" in output, "interrupt example should emit interrupt requested")
    _require("realtime.interrupt.unsupported" in output, "interrupt example should emit interrupt unsupported")
    _ok("realtime interrupt handling example runs")


def _assert_run_flush_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_realtime_output_flush_handling.py")
    _require("queued_count: 0" in output, "flush example should show empty queue")
    _require("queue_supports_flush: False" in output, "flush example should not overclaim queue flush")
    _require("queue_supports_provider_cancel: False" in output, "flush example should not overclaim provider cancel")
    _require("flush_outcome: nothing_to_flush" in output, "flush example should report nothing_to_flush")
    _require("flush_flushed: False" in output, "flush example should not report flushed")
    _require("realtime.output.flush.requested" in output, "flush example should emit flush requested")
    _require("realtime.output.flush.completed" in output, "flush example should emit flush completed")
    _ok("realtime output flush handling example runs")


def _assert_run_barge_in_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_realtime_barge_in_policy.py")
    _require("rejected_accepted: False" in output, "barge-in example should reject disabled policy")
    _require("policy_mode: hard_cancel" in output, "barge-in example should set hard_cancel policy")
    _require("accepted_accepted: True" in output, "barge-in example should accept hard_cancel policy decision")
    _require("should_stop_output: True" in output, "barge-in example should stop output")
    _require("should_flush_queue: True" in output, "barge-in example should flush queue by policy")
    _require("should_cancel_current_turn: True" in output, "barge-in example should cancel current turn by policy")
    _require("realtime.barge_in.detected" in output, "barge-in example should emit detected event")
    _require("realtime.barge_in.rejected" in output, "barge-in example should emit rejected event")
    _require("realtime.barge_in.accepted" in output, "barge-in example should emit accepted event")
    _ok("realtime barge-in policy example runs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_examples_exist_and_public_only(root)
    _assert_import_safe(root)
    _assert_run_interrupt_example(root)
    _assert_run_flush_example(root)
    _assert_run_barge_in_example(root)
    _ok("v5.2.0 interrupt/output-control host-app examples are mock-safe")


if __name__ == "__main__":
    main()
