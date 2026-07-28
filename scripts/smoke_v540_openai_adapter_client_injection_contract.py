"""Regression check for accepted v5.4.0 REQ-2 OpenAI adapter contract."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PROVIDER_MODULE_FRAGMENTS = (
    "speech_recognition",
    "pyaudio",
    "sounddevice",
    "whisper",
    "faster_whisper",
    "openai",
    "google.cloud",
    "boto3",
    "azure",
)


def _read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _validate_docs() -> None:
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/v540_openai_adapter_client_injection_contract.md"),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
            _read("docs/v540_real_stt_provider_execution_small_commit_checklist.md"),
        )
    )
    for marker in (
        "REQ-2: ACCEPTED",
        "OpenAIVoiceInputProviderAdapter",
        "OpenAIVoiceInputClientFactory",
        "client.audio.transcriptions.create(...)",
        "FILE_PATH",
        "WAV",
        "ready_not_executed",
    ):
        _require(marker in combined, f"REQ-2 docs missing marker: {marker}")
    _require(
        "REQ-2: IMPLEMENTED / NOT_ACCEPTED" not in combined,
        "REQ-2 stale pre-acceptance marker remains",
    )
    _ok("REQ-2 accepted documentation remains present")


def _validate_source_boundary() -> None:
    source = _read("framework/openai_voice_input_provider_adapter.py")
    tree = ast.parse(source)

    imported_roots: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    _require("os" not in imported_roots, "REQ-2 must not inspect environment")
    _require("pathlib" not in imported_roots, "REQ-2 must not inspect files")
    _require(
        not imported_roots.intersection(
            {"openai", "google", "boto3", "azure", "whisper"}
        ),
        "REQ-2 must not import provider SDKs",
    )
    _require(
        not calls.intersection(
            {
                "getenv",
                "open",
                "read_text",
                "read_bytes",
                "create_client",
            }
        ),
        "REQ-2 must not resolve credentials, clients, or audio",
    )
    _ok("REQ-2 source remains lazy, provider-safe, and audio-free")


def _validate_runtime_contract() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    hits = sorted(
        name
        for name in loaded
        if any(
            fragment in name.lower()
            for fragment in FORBIDDEN_PROVIDER_MODULE_FRAGMENTS
        )
    )
    _require(
        not hits,
        f"framework root import loaded provider modules: {hits}",
    )

    class FakeTranscriptions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: object) -> object:
            self.calls += 1
            raise AssertionError("REQ-2 regression must not execute create")

    class FakeAudio:
        def __init__(self) -> None:
            self.transcriptions = FakeTranscriptions()

    class FakeClient:
        def __init__(self) -> None:
            self.audio = FakeAudio()

    client = FakeClient()
    config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )
    adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="explicit-test-model",
        client=client,
    )
    wav = framework.VoiceInputAudioFormat.wav(duration_ms=1000)
    source = framework.VoiceInputAudioSource.from_file_path(
        "not-opened.wav",
        audio_format=wav,
        max_duration_ms=5000,
    )

    ready = adapter.preflight_contract(audio_source=source)
    _require(ready.is_ready, "REQ-2 preflight contract changed")
    result = adapter.transcribe(audio_source=source)
    _require(
        result.outcome is framework.VoiceInputOutcome.UNAVAILABLE,
        "REQ-2 transcribe must remain execution-free",
    )
    _require(client.audio.transcriptions.calls == 0, "REQ-2 executed client")
    _ok("REQ-2 accepted adapter contract remains execution-free")


def main() -> None:
    _validate_docs()
    _validate_source_boundary()
    _validate_runtime_contract()

    print("v540_openai_adapter_client_injection_status: accepted")
    print("v540_openai_client_factory_invoked: False")
    print("v540_provider_sdk_imported: False")
    print("v540_provider_client_created: False")
    print("v540_provider_execution_executed: False")
    print("v540_audio_read: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req3_authorization: authorized-by-req2-acceptance")
    _ok("v5.4.0 REQ-2 acceptance remains valid")


if __name__ == "__main__":
    main()
