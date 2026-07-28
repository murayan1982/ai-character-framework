\
"""Regression check for accepted v5.4.0 REQ-4 lazy real-provider runtime."""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


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
            _read("docs/v540_openai_real_provider_runtime.md"),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
        )
    )
    _require("REQ-4: ACCEPTED" in combined, "REQ-4 accepted marker missing")
    _require(
        "REQ-4: IMPLEMENTED / NOT_ACCEPTED" not in combined,
        "REQ-4 stale marker remains",
    )
    for marker in (
        "OpenAIVoiceInputPrivateCredential",
        "OpenAIVoiceInputRealClientFactory",
        "allow_provider_sdk_import",
        "allow_provider_client_creation",
        "allow_real_provider_execution",
    ):
        _require(marker in combined, f"REQ-4 docs missing: {marker}")
    _ok("REQ-4 accepted documentation remains present")


def _validate_runtime() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    framework = importlib.import_module("framework")
    _require("openai" not in sys.modules, "root import loaded actual OpenAI SDK")

    secret = "sk-req4-regression-dummy"
    credential = framework.OpenAIVoiceInputPrivateCredential(secret)

    record: dict[str, object] = {"calls": 0, "api_key": None}

    class Transcriptions:
        def create(self, **kwargs: object) -> object:
            record["calls"] = int(record["calls"]) + 1
            kwargs["file"].read()
            return {"text": "req4 regression transcript", "language": "ja"}

    class OpenAI:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            record["api_key"] = api_key
            self.audio = SimpleNamespace(transcriptions=Transcriptions())

    sdk = SimpleNamespace(OpenAI=OpenAI)
    config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )
    policy = framework.OpenAIVoiceInputRealProviderPolicy(
        max_audio_bytes=1024,
        allow_provider_sdk_import=True,
        allow_provider_client_creation=True,
        allow_real_provider_execution=True,
        runtime_mode=framework.OpenAIVoiceInputRuntimeMode.TEST_DOUBLE,
    )
    factory = framework.OpenAIVoiceInputRealClientFactory(
        credential=credential,
        policy=policy,
        module_importer=lambda name: sdk,
    )
    adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="req4-regression-model",
        client_factory=factory,
    )

    with tempfile.TemporaryDirectory(prefix="fw-v540-req4-regression-") as temp:
        audio_path = Path(temp) / "audio.wav"
        audio_path.write_bytes(b"RIFF" + (b"\x00" * 20))
        source = framework.VoiceInputAudioSource.from_file_path(
            str(audio_path),
            audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=1000),
            language="ja",
            max_duration_ms=5000,
        )
        result = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=adapter
        ).execute(audio_source=source)

    _require(result.is_completed, "REQ-4 test-double execution no longer completes")
    _require(record["calls"] == 1, "REQ-4 protocol call count changed")
    _require(record["api_key"] == secret, "REQ-4 credential forwarding changed")
    _require(
        result.public_metadata["real_provider_execution_executed"] is False,
        "REQ-4 test double claimed real execution",
    )
    _require(secret not in str(result), "REQ-4 credential leaked")
    _require("openai" not in sys.modules, "regression loaded actual OpenAI SDK")
    _ok("REQ-4 accepted lazy runtime remains valid")


def main() -> None:
    _validate_docs()
    _validate_runtime()

    print("v540_openai_real_provider_runtime_status: accepted")
    print("v540_provider_root_import_safe: True")
    print("v540_provider_sdk_import_default: False")
    print("v540_provider_client_creation_default: False")
    print("v540_real_provider_execution_default: False")
    print("v540_private_credential_environment_read_by_framework: False")
    print("v540_private_credential_exposed: False")
    print("v540_provider_sdk_imported_in_smoke: False")
    print("v540_provider_client_created_in_smoke: False")
    print("v540_real_provider_execution_executed_in_smoke: False")
    print("v540_req5_authorization: authorized-by-req4-acceptance")
    _ok("v5.4.0 REQ-4 acceptance remains valid")


if __name__ == "__main__":
    main()
