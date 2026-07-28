"""Validate v5.4.0 REQ-2 OpenAI adapter/client-injection contract."""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHANGED_PATHS = {
    "README.md",
    "docs/v540_openai_adapter_client_injection_contract.md",
    "docs/v540_provider_execution_configuration_status.md",
    "docs/v540_real_stt_provider_execution_requirements.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "framework/__init__.py",
    "framework/openai_voice_input_provider_adapter.py",
    "scripts/smoke_v540_openai_adapter_client_injection_contract.py",
    "scripts/smoke_v540_provider_execution_configuration_status.py",
}
LOCAL_ONLY_PATHS = {".vscode/settings.json"}
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


def _git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def _changed_paths() -> set[str]:
    return (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    ) - LOCAL_ONLY_PATHS


def _validate_changed_surface() -> None:
    actual = _changed_paths()
    _require(
        actual == EXPECTED_CHANGED_PATHS,
        "REQ-2 changed surface mismatch:\n"
        f"expected={sorted(EXPECTED_CHANGED_PATHS)}\n"
        f"actual={sorted(actual)}",
    )
    _ok("REQ-2 worktree contains the exact nine-file implementation surface")


def _validate_docs() -> None:
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/v540_openai_adapter_client_injection_contract.md"),
            _read("docs/v540_provider_execution_configuration_status.md"),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
            _read("docs/v540_real_stt_provider_execution_small_commit_checklist.md"),
        )
    )
    for marker in (
        "REQ-1: ACCEPTED",
        "REQ-2: ACCEPTED",
        "REQ-3: READY pending next small commit",
        "OpenAIVoiceInputProviderAdapter",
        "OpenAIVoiceInputClientFactory",
        "client.audio.transcriptions.create(...)",
        "FILE_PATH",
        "WAV",
        "ready_not_executed",
    ):
        _require(marker in combined, f"REQ-2 docs missing marker: {marker}")

    for forbidden in (
        "REQ-2: IMPLEMENTED / NOT_ACCEPTED",
        "REQ-3: BLOCKED pending REQ-2 acceptance",
        "real OpenAI transcription succeeded",
        "private provider acceptance completed",
    ):
        _require(
            forbidden not in combined,
            f"REQ-2 docs contain stale or premature marker: {forbidden}",
        )
    _ok("REQ-2 docs record acceptance and authorize REQ-3 for the next small commit")


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
    _ok("REQ-2 source is lazy, provider-safe, and audio-free")


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
        f"framework import loaded provider/runtime modules: {hits}",
    )

    exports = (
        "OpenAIVoiceInputClient",
        "OpenAIVoiceInputClientFactory",
        "OpenAIVoiceInputPreflight",
        "OpenAIVoiceInputPreflightStatus",
        "OpenAIVoiceInputProviderAdapter",
    )
    for name in exports:
        _require(hasattr(framework, name), f"framework missing export: {name}")
        _require(name in framework.__all__, f"framework.__all__ missing: {name}")

    class FakeTranscriptions:
        def __init__(self) -> None:
            self.create_calls = 0

        def create(self, **kwargs: object) -> object:
            self.create_calls += 1
            raise AssertionError("REQ-2 must not call transcription create")

    class FakeAudio:
        def __init__(self) -> None:
            self.transcriptions = FakeTranscriptions()

    class FakeClient:
        def __init__(self) -> None:
            self.audio = FakeAudio()

    fake_client = FakeClient()
    _require(
        isinstance(fake_client, framework.OpenAIVoiceInputClient),
        "fake client should satisfy the injected client protocol",
    )

    config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )

    adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="explicit-test-model",
        client=fake_client,
        public_metadata={"api_key": "must-not-leak"},
    )
    _require(
        isinstance(adapter, framework.VoiceInputProviderAdapter),
        "OpenAI adapter should satisfy the existing provider protocol",
    )

    no_source = adapter.preflight_contract()
    _require(
        no_source.status
        is framework.OpenAIVoiceInputPreflightStatus.SOURCE_REQUIRED,
        "configured adapter should require source preflight",
    )
    _require(
        no_source.public_metadata["api_key"] == "<redacted>",
        "REQ-2 metadata must redact secret-like keys",
    )

    wav = framework.VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=4200,
    )
    source = framework.VoiceInputAudioSource.from_file_path(
        r"C:\private\operator\voice.wav",
        audio_format=wav,
        language="ja-JP",
        max_duration_ms=15000,
    )
    ready = adapter.preflight_contract(audio_source=source)
    _require(
        ready.status
        is framework.OpenAIVoiceInputPreflightStatus.READY_NOT_EXECUTED,
        "bounded FILE_PATH WAV metadata should be contract-ready",
    )
    _require(ready.configured is True, "ready contract must be configured")
    _require(ready.source_supported is True, "ready source must be supported")
    _require(ready.is_ready is True, "ready contract property mismatch")
    _require(
        ready.public_metadata["client_factory_invoked"] is False,
        "REQ-2 must not invoke a client factory",
    )
    _require(
        ready.public_metadata["audio_read"] is False,
        "REQ-2 must not read audio",
    )
    _require(
        "private" not in str(ready.public_metadata).lower(),
        "REQ-2 metadata must not expose the source path",
    )

    result = adapter.transcribe(
        audio_source=source,
        request=framework.VoiceInputRequest(language="ja-JP"),
    )
    _require(
        result.outcome is framework.VoiceInputOutcome.UNAVAILABLE,
        "REQ-2 transcribe must remain unavailable",
    )
    _require(
        result.public_metadata["guard"] == "ready_not_executed",
        "REQ-2 result guard mismatch",
    )
    _require(
        result.public_metadata["provider_execution_executed"] is False,
        "REQ-2 must not execute the provider",
    )
    _require(
        fake_client.audio.transcriptions.create_calls == 0,
        "REQ-2 must not call client.audio.transcriptions.create",
    )
    _require(
        "voice.wav" not in str(result.public_metadata),
        "REQ-2 result metadata must not expose the source path",
    )

    factory_calls = {"count": 0}

    def fake_factory() -> FakeClient:
        factory_calls["count"] += 1
        return FakeClient()

    factory_adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="explicit-test-model",
        client_factory=fake_factory,
    )
    factory_ready = factory_adapter.preflight_contract(audio_source=source)
    _require(factory_ready.is_ready, "factory-injected adapter should be ready")
    _require(factory_calls["count"] == 0, "REQ-2 must not invoke factory")
    factory_adapter.transcribe(audio_source=source)
    _require(factory_calls["count"] == 0, "REQ-2 transcribe must not invoke factory")

    conflict = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="explicit-test-model",
        client=fake_client,
        client_factory=fake_factory,
    ).preflight_contract(audio_source=source)
    _require(
        conflict.status
        is framework.OpenAIVoiceInputPreflightStatus.CLIENT_CONFIGURATION_CONFLICT,
        "client/factory conflict status mismatch",
    )

    opaque = framework.VoiceInputAudioSource.from_opaque_id(
        "opaque_capture",
        audio_format=wav,
        max_duration_ms=15000,
    )
    unsupported = adapter.preflight_contract(audio_source=opaque)
    _require(
        unsupported.status
        is framework.OpenAIVoiceInputPreflightStatus.UNSUPPORTED_SOURCE,
        "opaque source should remain unsupported",
    )

    mp3_format = framework.VoiceInputAudioFormat(
        encoding=framework.VoiceInputAudioEncoding.MP3,
        duration_ms=1000,
    )
    mp3_source = framework.VoiceInputAudioSource.from_file_path(
        "voice.mp3",
        audio_format=mp3_format,
        max_duration_ms=15000,
    )
    unsupported_format = adapter.preflight_contract(audio_source=mp3_source)
    _require(
        unsupported_format.status
        is framework.OpenAIVoiceInputPreflightStatus.UNSUPPORTED_AUDIO_FORMAT,
        "non-WAV source should remain unsupported",
    )

    unbounded = framework.VoiceInputAudioSource.from_file_path(
        "voice.wav",
        audio_format=wav,
    )
    unbounded_status = adapter.preflight_contract(audio_source=unbounded)
    _require(
        unbounded_status.status
        is framework.OpenAIVoiceInputPreflightStatus.SOURCE_NOT_BOUNDED,
        "source without max_duration_ms should be rejected",
    )

    too_long = framework.VoiceInputAudioSource.from_file_path(
        "voice.wav",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=20000),
        max_duration_ms=15000,
    )
    too_long_status = adapter.preflight_contract(audio_source=too_long)
    _require(
        too_long_status.status
        is (
            framework.OpenAIVoiceInputPreflightStatus
            .SOURCE_DURATION_EXCEEDS_BOUND
        ),
        "declared duration over bound should be rejected",
    )

    blocked_config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=False,
        credentials_available=True,
    )
    blocked = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=blocked_config,
        model="explicit-test-model",
        client=fake_client,
    ).preflight_contract(audio_source=source)
    _require(
        blocked.status
        is (
            framework.OpenAIVoiceInputPreflightStatus
            .PROVIDER_EXECUTION_NOT_ALLOWED
        ),
        "explicit opt-in guard mismatch",
    )

    _ok("REQ-2 typed OpenAI adapter/client/source contract is execution-free")


def main() -> None:
    _validate_changed_surface()
    _validate_docs()
    _validate_source_boundary()
    _validate_runtime_contract()

    print("v540_openai_adapter_client_injection_status: accepted")
    print("v540_openai_adapter_public_export_present: True")
    print("v540_openai_client_protocol_present: True")
    print("v540_openai_client_factory_injection_present: True")
    print("v540_openai_client_factory_invoked: False")
    print("v540_openai_model_explicit: True")
    print("v540_openai_source_scope_file_path_only: True")
    print("v540_openai_audio_format_scope_wav_only: True")
    print("v540_openai_source_bound_required: True")
    print("v540_credential_values_read: False")
    print("v540_provider_sdk_imported: False")
    print("v540_provider_client_created: False")
    print("v540_provider_execution_executed: False")
    print("v540_audio_read: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req3_authorization: ready-for-req3")
    _ok("v5.4.0 REQ-2 OpenAI adapter/client-injection acceptance passed")


if __name__ == "__main__":
    main()
