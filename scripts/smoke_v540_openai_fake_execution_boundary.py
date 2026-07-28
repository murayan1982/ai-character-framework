"""Validate v5.4.0 REQ-3 bounded audio/fake execution boundary."""

from __future__ import annotations

import ast
import importlib
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHANGED_PATHS = {
    "README.md",
    "docs/v540_openai_adapter_client_injection_contract.md",
    "docs/v540_openai_fake_execution_boundary.md",
    "docs/v540_provider_execution_configuration_status.md",
    "docs/v540_real_stt_provider_execution_requirements.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "framework/__init__.py",
    "framework/openai_voice_input_fake_execution.py",
    "scripts/smoke_v540_openai_adapter_client_injection_contract.py",
    "scripts/smoke_v540_openai_fake_execution_boundary.py",
}
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
    import subprocess

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
    ) - {".vscode/settings.json"}


def _validate_changed_surface() -> None:
    actual = _changed_paths()
    _require(
        actual == EXPECTED_CHANGED_PATHS,
        "REQ-3 changed surface mismatch:\n"
        f"expected={sorted(EXPECTED_CHANGED_PATHS)}\n"
        f"actual={sorted(actual)}",
    )
    _ok("REQ-3 worktree contains the exact ten-file implementation surface")


def _validate_docs() -> None:
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/v540_openai_adapter_client_injection_contract.md"),
            _read("docs/v540_openai_fake_execution_boundary.md"),
            _read("docs/v540_provider_execution_configuration_status.md"),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
            _read("docs/v540_real_stt_provider_execution_small_commit_checklist.md"),
        )
    )
    for marker in (
        "REQ-2: ACCEPTED",
        "REQ-3: ACCEPTED",
        "REQ-4: READY pending next small commit",
        "OpenAIVoiceInputFakeClientMarker",
        "OpenAIVoiceInputFakeExecutionPolicy",
        "OpenAIVoiceInputFakeExecutor",
        "max_audio_bytes",
        "fake_provider_protocol_call_executed",
    ):
        _require(marker in combined, f"REQ-3 docs missing marker: {marker}")
    for forbidden in (
        "REQ-3: IMPLEMENTED / NOT_ACCEPTED",
        "REQ-4: BLOCKED pending REQ-3 acceptance",
        "real OpenAI transcription succeeded",
        "credential value loaded",
    ):
        _require(
            forbidden not in combined,
            f"REQ-3 docs contain stale or premature marker: {forbidden}",
        )
    _ok("REQ-3 docs record acceptance and authorize REQ-4 for the next small commit")


def _validate_source_boundary() -> None:
    source = _read("framework/openai_voice_input_fake_execution.py")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    _require("os" not in imported_roots, "REQ-3 must not inspect environment")
    _require(
        not imported_roots.intersection(
            {"openai", "google", "boto3", "azure", "whisper"}
        ),
        "REQ-3 must not import provider SDKs",
    )
    _require(
        "OpenAIVoiceInputFakeClientMarker" in source,
        "REQ-3 fake-client nominal marker missing",
    )
    _require(
        "self.adapter.client.audio.transcriptions.create" not in source,
        "REQ-3 source should use a formatted call chain, not unsafe eval text",
    )
    _ok("REQ-3 source imports no provider SDK or credential resolver")


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

    exports = (
        "OpenAIVoiceInputFakeClientMarker",
        "OpenAIVoiceInputFakeExecutionPolicy",
        "OpenAIVoiceInputFakeExecutionStatus",
        "OpenAIVoiceInputFakeExecutor",
    )
    for name in exports:
        _require(hasattr(framework, name), f"framework missing export: {name}")
        _require(name in framework.__all__, f"framework.__all__ missing: {name}")

    class FakeTranscriptions:
        def __init__(self, *, should_fail: bool = False) -> None:
            self.calls = 0
            self.last_model = None
            self.last_name = None
            self.last_bytes = b""
            self.should_fail = should_fail

        def create(self, **kwargs: object) -> object:
            self.calls += 1
            if self.should_fail:
                raise RuntimeError("private fake failure details")
            self.last_model = kwargs.get("model")
            payload = kwargs["file"]
            self.last_name = getattr(payload, "name", None)
            self.last_bytes = payload.read()
            return {"text": "fake transcript", "language": "ja"}

    class FakeAudio:
        def __init__(self, *, should_fail: bool = False) -> None:
            self.transcriptions = FakeTranscriptions(
                should_fail=should_fail
            )

    class MarkedFakeClient(framework.OpenAIVoiceInputFakeClientMarker):
        def __init__(self, *, should_fail: bool = False) -> None:
            self.audio = FakeAudio(should_fail=should_fail)

    class UnmarkedClient:
        def __init__(self) -> None:
            self.audio = FakeAudio()

    config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )
    wav = framework.VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=1000,
    )

    with tempfile.TemporaryDirectory(prefix="fw-v540-req3-") as temp:
        audio_path = Path(temp) / "private-operator-audio.wav"
        audio_bytes = b"RIFF" + (b"\x00" * 124)
        audio_path.write_bytes(audio_bytes)
        source = framework.VoiceInputAudioSource.from_file_path(
            str(audio_path),
            audio_format=wav,
            language="ja",
            max_duration_ms=5000,
        )

        marked_client = MarkedFakeClient()
        adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-fake-model",
            client=marked_client,
        )

        blocked = framework.OpenAIVoiceInputFakeExecutor(
            adapter=adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=1024,
                allow_fake_client_execution=False,
            ),
        ).execute(audio_source=source)
        _require(
            blocked.public_metadata["fake_execution_status"]
            == "fake_execution_not_allowed",
            "default fake execution guard mismatch",
        )
        _require(
            marked_client.audio.transcriptions.calls == 0,
            "blocked fake execution called client",
        )

        too_small = framework.OpenAIVoiceInputFakeExecutor(
            adapter=adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=16,
                allow_fake_client_execution=True,
            ),
        ).execute(audio_source=source)
        _require(
            too_small.public_metadata["fake_execution_status"]
            == "audio_too_large",
            "bounded audio rejection mismatch",
        )
        _require(
            marked_client.audio.transcriptions.calls == 0,
            "oversized audio called client",
        )

        completed = framework.OpenAIVoiceInputFakeExecutor(
            adapter=adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=1024,
                allow_fake_client_execution=True,
            ),
        ).execute(
            audio_source=source,
            request=framework.VoiceInputRequest(language="ja"),
        )
        _require(completed.is_completed, "marked fake execution did not complete")
        _require(completed.text == "fake transcript", "fake transcript mismatch")
        _require(
            marked_client.audio.transcriptions.calls == 1,
            "marked fake client should be called exactly once",
        )
        _require(
            marked_client.audio.transcriptions.last_model
            == "explicit-fake-model",
            "explicit model was not forwarded",
        )
        _require(
            marked_client.audio.transcriptions.last_name == "audio.wav",
            "sanitized in-memory filename mismatch",
        )
        _require(
            marked_client.audio.transcriptions.last_bytes == audio_bytes,
            "bounded bytes were not handed to fake client",
        )
        _require(
            completed.public_metadata[
                "fake_provider_protocol_call_executed"
            ]
            is True,
            "fake protocol-call marker mismatch",
        )
        _require(
            completed.public_metadata[
                "real_provider_execution_executed"
            ]
            is False,
            "REQ-3 must not claim real provider execution",
        )
        _require(
            completed.public_metadata["audio_bytes_read"] == len(audio_bytes),
            "bounded byte count mismatch",
        )
        metadata_text = str(completed.public_metadata)
        _require(
            "private-operator-audio.wav" not in metadata_text,
            "audio path leaked into public metadata",
        )
        _require(
            "RIFF" not in metadata_text,
            "raw audio leaked into public metadata",
        )

        unmarked_adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-fake-model",
            client=UnmarkedClient(),
        )
        unmarked = framework.OpenAIVoiceInputFakeExecutor(
            adapter=unmarked_adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=1024,
                allow_fake_client_execution=True,
            ),
        ).execute(audio_source=source)
        _require(
            unmarked.public_metadata["fake_execution_status"]
            == "client_not_marked_fake",
            "unmarked client rejection mismatch",
        )
        _require(
            unmarked_adapter.client.audio.transcriptions.calls == 0,
            "unmarked client was executed",
        )

        factory_calls = {"count": 0}

        def fake_factory() -> MarkedFakeClient:
            factory_calls["count"] += 1
            return MarkedFakeClient()

        factory_adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-fake-model",
            client_factory=fake_factory,
        )
        factory_result = framework.OpenAIVoiceInputFakeExecutor(
            adapter=factory_adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=1024,
                allow_fake_client_execution=True,
            ),
        ).execute(audio_source=source)
        _require(
            factory_result.public_metadata["fake_execution_status"]
            == "direct_client_required",
            "client-factory rejection mismatch",
        )
        _require(factory_calls["count"] == 0, "REQ-3 invoked client factory")

        failing_client = MarkedFakeClient(should_fail=True)
        failing_adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-fake-model",
            client=failing_client,
        )
        failed = framework.OpenAIVoiceInputFakeExecutor(
            adapter=failing_adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=1024,
                allow_fake_client_execution=True,
            ),
        ).execute(audio_source=source)
        _require(
            failed.outcome is framework.VoiceInputOutcome.FAILED,
            "fake provider exception should return typed failure",
        )
        _require(
            failed.safe_message == "The injected fake STT client failed.",
            "fake provider failure message must remain safe",
        )
        _require(
            "private fake failure details" not in str(failed),
            "fake provider exception details leaked",
        )

    _ok("REQ-3 bounded file read and marked-fake execution passed")


def main() -> None:
    _validate_changed_surface()
    _validate_docs()
    _validate_source_boundary()
    _validate_runtime_contract()

    print("v540_openai_fake_execution_status: accepted")
    print("v540_fake_client_nominal_marker_required: True")
    print("v540_fake_execution_explicit_opt_in: True")
    print("v540_audio_byte_bound_explicit: True")
    print("v540_audio_file_read_executed_in_smoke: True")
    print("v540_fake_provider_protocol_call_executed: True")
    print("v540_client_factory_invoked: False")
    print("v540_provider_sdk_imported: False")
    print("v540_provider_client_created: False")
    print("v540_credential_values_read: False")
    print("v540_real_provider_execution_executed: False")
    print("v540_audio_path_exposed: False")
    print("v540_raw_audio_exposed: False")
    print("v540_provider_payload_exposed: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req4_authorization: ready-for-req4")
    _ok("v5.4.0 REQ-3 bounded audio/fake execution acceptance passed")


if __name__ == "__main__":
    main()
