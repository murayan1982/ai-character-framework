"""v5.2.0 motion host-app examples smoke."""

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
    path = root / "docs" / "v520_motion_host_app_examples.md"
    _require(path.exists(), "missing docs/v520_motion_host_app_examples.md")
    text = path.read_text(encoding="utf-8", errors="replace")
    required_phrases = [
        "v5.2.0 Motion Host-App Examples",
        "app_motion_session_expression_flow.py",
        "app_motion_adapter_preflight.py",
        "app_motion_closed_session_behavior.py",
        "app_motion_real_adapter_guard.py",
        "MotionResult",
        "MotionCapability",
        "mock_motion=True",
        "mock_available",
        "supports_real_adapter=False",
        "provider_execution_not_allowed",
        "import framework",
    ]
    for phrase in required_phrases:
        _require(phrase in text, f"motion host-app examples doc missing phrase: {phrase}")
    _ok("v5.2.0 motion host-app examples doc is documented")


def _assert_examples_exist_and_public_only(root: Path) -> None:
    examples = [
        root / "examples" / "app_motion_session_expression_flow.py",
        root / "examples" / "app_motion_adapter_preflight.py",
        root / "examples" / "app_motion_closed_session_behavior.py",
        root / "examples" / "app_motion_real_adapter_guard.py",
    ]
    forbidden_phrases = [
        "from live2d",
        "import live2d",
        "from vts",
        "import vts",
        "from plugins",
        "import websocket",
        "import websockets",
        "sys.path",
        "chdir(",
        "TOKEN =",
        "VTS_TOKEN =",
        "MODEL_PATH =",
    ]

    for path in examples:
        _require(path.exists(), f"missing example: {path.relative_to(root)}")
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("import framework" in text, f"{path.name} should use public framework import")
        for phrase in forbidden_phrases:
            _require(phrase not in text, f"{path.name} contains forbidden phrase: {phrase}")

    _ok("motion examples use public imports only")


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
        "vtube",
        "vts",
        "live2d",
    ]
    hits = sorted(name for name in loaded if any(fragment in name.lower() for fragment in forbidden_fragments))
    _require(not hits, "examples/import framework eagerly loaded motion provider modules: " + ", ".join(hits[:16]))
    _ok("motion examples keep framework import provider safe")


def _assert_run_expression_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_motion_session_expression_flow.py")
    _require("adapter_status: mock_available" in output, "expression example should use mock adapter")
    _require("expression_outcome: completed" in output, "expression example should complete")
    _require("expression_mock_motion: True" in output, "expression example should mark mock motion")
    _require("speaking_outcome: completed" in output, "speaking example should complete")
    _require("state_after: idle" in output, "motion session should return to idle")
    _require("motion.session.created" in output, "expression example should emit session created")
    _require("motion.requested" in output, "expression example should emit requested")
    _require("motion.started" in output, "expression example should emit started")
    _require("motion.completed" in output, "expression example should emit completed")
    _ok("motion expression/speaking-state example runs")


def _assert_run_preflight_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_motion_adapter_preflight.py")
    _require("adapter: mock" in output, "preflight example should use mock adapter")
    _require("adapter_status: mock_available" in output, "preflight example should report mock_available")
    _require("supports_expression: True" in output, "preflight example should support expression")
    _require("supports_speaking_state: True" in output, "preflight example should support speaking state")
    _require("supports_real_adapter: False" in output, "preflight example should not overclaim real adapter")
    _require("motion.adapter.preflight.completed" in output, "preflight example should emit preflight event")
    _ok("motion adapter preflight example runs")


def _assert_run_closed_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_motion_closed_session_behavior.py")
    _require("is_closed: True" in output, "closed example should close session")
    _require("state: closed" in output, "closed example state mismatch")
    _require("closed_outcome: closed" in output, "closed example should return closed outcome")
    _require("closed_error: session_closed" in output, "closed example should return session_closed error")
    _require("motion.session.closed" in output, "closed example should emit session closed")
    _ok("motion closed-session example runs")


def _assert_run_guard_example(root: Path) -> None:
    output = _run_example(root / "examples" / "app_motion_real_adapter_guard.py")
    _require("adapter: vts" in output, "guard example should preserve adapter")
    _require("real_adapter_enabled: True" in output, "guard example should enable real adapter flag")
    _require("real_adapter_supported: False" in output, "guard example should not overclaim real adapter")
    _require("guard_outcome: unavailable" in output, "guard example should return unavailable")
    _require("guard_status: provider_execution_not_allowed" in output, "guard example status mismatch")
    _require("guard_error: provider_execution_not_allowed" in output, "guard example error mismatch")
    _require("motion.unsupported" in output, "guard example should emit unsupported")
    _ok("motion real-adapter guard example runs")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_examples_exist_and_public_only(root)
    _assert_import_safe(root)
    _assert_run_expression_example(root)
    _assert_run_preflight_example(root)
    _assert_run_closed_example(root)
    _assert_run_guard_example(root)
    _ok("v5.2.0 motion host-app examples are mock-safe")


if __name__ == "__main__":
    main()
