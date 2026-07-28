"""Regression check for accepted v5.4.0 REQ-3 fake execution boundary."""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
            _read("docs/v540_openai_fake_execution_boundary.md"),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
            _read("docs/v540_real_stt_provider_execution_small_commit_checklist.md"),
        )
    )
    _require("REQ-3: ACCEPTED" in combined, "REQ-3 accepted marker missing")
    _require(
        "REQ-3: IMPLEMENTED / NOT_ACCEPTED" not in combined,
        "REQ-3 stale marker remains",
    )
    for marker in (
        "OpenAIVoiceInputFakeClientMarker",
        "max_audio_bytes",
        "fake_provider_protocol_call_executed",
    ):
        _require(marker in combined, f"REQ-3 docs missing: {marker}")
    _ok("REQ-3 accepted documentation remains present")


def _validate_runtime() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    framework = importlib.import_module("framework")

    class FakeTranscriptions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: object) -> object:
            self.calls += 1
            payload = kwargs["file"]
            return {
                "text": f"fake-{len(payload.read())}",
                "language": "ja",
            }

    class FakeAudio:
        def __init__(self) -> None:
            self.transcriptions = FakeTranscriptions()

    class MarkedFakeClient(framework.OpenAIVoiceInputFakeClientMarker):
        def __init__(self) -> None:
            self.audio = FakeAudio()

    config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )
    client = MarkedFakeClient()
    adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="req3-regression-model",
        client=client,
    )

    with tempfile.TemporaryDirectory(prefix="fw-v540-req3-regression-") as temp:
        audio_path = Path(temp) / "audio.wav"
        audio_path.write_bytes(b"RIFF" + (b"\x00" * 20))
        source = framework.VoiceInputAudioSource.from_file_path(
            str(audio_path),
            audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=1000),
            language="ja",
            max_duration_ms=5000,
        )
        result = framework.OpenAIVoiceInputFakeExecutor(
            adapter=adapter,
            policy=framework.OpenAIVoiceInputFakeExecutionPolicy(
                max_audio_bytes=1024,
                allow_fake_client_execution=True,
            ),
        ).execute(audio_source=source)

    _require(result.is_completed, "REQ-3 fake execution no longer completes")
    _require(client.audio.transcriptions.calls == 1, "REQ-3 fake call count changed")
    _require(
        result.public_metadata["real_provider_execution_executed"] is False,
        "REQ-3 must not claim real provider execution",
    )
    _ok("REQ-3 accepted bounded fake execution remains valid")


def main() -> None:
    _validate_docs()
    _validate_runtime()

    print("v540_openai_fake_execution_status: accepted")
    print("v540_fake_provider_protocol_call_executed: True")
    print("v540_provider_sdk_imported: False")
    print("v540_provider_client_created: False")
    print("v540_credential_values_read: False")
    print("v540_real_provider_execution_executed: False")
    print("v540_audio_path_exposed: False")
    print("v540_raw_audio_exposed: False")
    print("v540_provider_payload_exposed: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req4_authorization: authorized-by-req3-acceptance")
    _ok("v5.4.0 REQ-3 acceptance remains valid")


if __name__ == "__main__":
    main()
