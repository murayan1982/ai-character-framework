"""FW-RT6-0b Control B voice-output session hygiene smoke.

This smoke is offline-safe. It does not enable provider execution, access a
microphone, play audio, or connect to a network/VTube Studio endpoint.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

VOICE_OUTPUT_SOURCE = PROJECT_ROOT / "framework" / "audio" / "voice_output.py"
PUBLIC_FACADE_DOC = PROJECT_ROOT / "docs" / "public_facade.md"
APP_INTEGRATION_DOC = PROJECT_ROOT / "docs" / "app_integration_contract.md"

EXPECTED_SINGLE_METHODS = {
    "__init__",
    "info",
    "is_closed",
    "close",
    "dispose",
    "__enter__",
    "__exit__",
    "speak",
    "create_output",
}
FORBIDDEN_IMPORTS = (
    "elevenlabs",
    "openai",
    "tts.voice_engine",
    "live2d.vts_client",
    "pyvts",
    "websockets",
)
ENV_GUARDS = (
    "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
    "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
    "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _temporary_env:
    def __init__(self) -> None:
        self._originals: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for name in ENV_GUARDS:
            self._originals[name] = os.environ.get(name)
            os.environ.pop(name, None)

    def __exit__(self, exc_type, exc, tb) -> None:
        for name, value in self._originals.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _method_nodes(class_node: ast.ClassDef) -> Iterator[ast.FunctionDef]:
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def check_source_structure() -> None:
    source = VOICE_OUTPUT_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    class_nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "VoiceOutputSession"
    ]
    _assert(len(class_nodes) == 1, "VoiceOutputSession must have one class definition")

    methods = list(_method_nodes(class_nodes[0]))
    counts: dict[str, int] = {}
    for method in methods:
        counts[method.name] = counts.get(method.name, 0) + 1

    for name in EXPECTED_SINGLE_METHODS:
        _assert(
            counts.get(name) == 1,
            f"VoiceOutputSession.{name} must be defined exactly once: {counts}",
        )

    duplicates = sorted(name for name, count in counts.items() if count > 1)
    _assert(not duplicates, f"duplicate VoiceOutputSession methods remain: {duplicates}")
    _assert(
        "_v510_original_create_output" not in source,
        "legacy create_output override storage must be removed",
    )
    _assert(
        "_v510_original_speak" not in source,
        "legacy speak override storage must be removed",
    )
    _assert(
        "v5.1.0 public session lifecycle override block" not in source,
        "legacy lifecycle override block must be removed",
    )

    print("[OK] VoiceOutputSession methods are defined through one lifecycle path")


def check_runtime_contract() -> None:
    before_modules = set(sys.modules)

    with _temporary_env():
        from framework import (
            VoiceOutputRequest,
            VoiceOutputSessionInfo,
            create_voice_output_session,
        )

        request = VoiceOutputRequest(
            text="今日は少し早めに休みましょう。",
            voice_profile_id="gentle_mina_default",
            requested_audio_format="mp3",
            utterance_purpose="control_b_smoke",
            language_code="ja",
        )
        session = create_voice_output_session(
            project_root=PROJECT_ROOT,
            default_voice_profile_id="gentle_mina_default",
        )

        _assert(callable(session.info), "session.info must remain a method")
        info = session.info()
        _assert(
            isinstance(info, VoiceOutputSessionInfo),
            "session.info() must return VoiceOutputSessionInfo",
        )
        _assert(not session.is_closed, "new session must be open")

        default_create = session.create_output(request)
        default_speak = session.speak(request)
        _assert(
            default_create.request_state == "unavailable",
            "default create_output must remain mock-safe unavailable",
        )
        _assert(
            default_speak.request_state == "unavailable",
            "default speak must remain mock-safe unavailable",
        )

        session.close()
        session.close()
        session.dispose()
        _assert(session.is_closed, "close/dispose must be idempotent")

        closed_create = session.create_output(request)
        closed_speak = session.speak(request)
        for label, result in (
            ("create_output", closed_create),
            ("speak", closed_speak),
        ):
            _assert(
                result.request_state == "failed",
                f"{label} after close must return failed",
            )
            _assert(
                result.public_metadata.get("public_error_code") == "session_closed",
                f"{label} after close must expose session_closed",
            )
            _assert(not result.audio_ready, f"{label} after close must not be playable")
            _assert(result.audio_url is None, f"{label} after close must not expose URL")
            _assert(
                result.audio_artifact_ref is None,
                f"{label} after close must not expose an artifact",
            )

        with create_voice_output_session(project_root=PROJECT_ROOT) as managed:
            _assert(not managed.is_closed, "context session must start open")
        _assert(managed.is_closed, "context manager exit must close the session")

    newly_imported = set(sys.modules) - before_modules
    forbidden = sorted(
        module_name
        for module_name in newly_imported
        if module_name in FORBIDDEN_IMPORTS
        or module_name.startswith("elevenlabs.")
        or module_name.startswith("openai.")
        or module_name.startswith("pyvts.")
        or module_name.startswith("websockets.")
    )
    _assert(not forbidden, f"provider/runtime modules were imported: {forbidden}")

    print("[OK] VoiceOutputSession public lifecycle and closed result are compatible")
    print("[OK] voice-output lifecycle smoke stayed provider/network/playback safe")


def check_docs() -> None:
    marker = "FW-RT6-0b-B-VOICE-OUTPUT-SESSION-HYGIENE"
    for path in (PUBLIC_FACADE_DOC, APP_INTEGRATION_DOC):
        text = path.read_text(encoding="utf-8")
        _assert(marker in text, f"Control B marker missing from {path.name}")

    print("[OK] public facade and app integration docs record Control B")


def main() -> None:
    check_source_structure()
    check_runtime_contract()
    check_docs()

    print("v600_voice_output_session_hygiene_status: implemented-awaiting-review")
    print("v600_voice_output_session_method_duplicates: False")
    print("v600_voice_output_info_remains_method: True")
    print("v600_voice_output_close_idempotent: True")
    print("v600_voice_output_closed_result_typed: True")
    print("v600_voice_output_provider_execution: False")
    print("v600_voice_output_network_execution: False")
    print("v600_voice_output_audio_playback: False")
    print("v600_next_control: FW-RT6-0b Control C")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-0b Control B voice-output session hygiene smoke passed")


if __name__ == "__main__":
    main()
