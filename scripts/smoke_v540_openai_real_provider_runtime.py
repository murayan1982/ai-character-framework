"""Validate v5.4.0 REQ-4 lazy OpenAI real-provider runtime boundary."""

from __future__ import annotations

import ast
import importlib
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHANGED_PATHS = {
    "README.md",
    "docs/v540_openai_adapter_client_injection_contract.md",
    "docs/v540_openai_fake_execution_boundary.md",
    "docs/v540_openai_real_provider_runtime.md",
    "docs/v540_provider_execution_configuration_status.md",
    "docs/v540_real_stt_provider_execution_requirements.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "framework/__init__.py",
    "framework/openai_voice_input_real_provider.py",
    "scripts/smoke_v540_openai_fake_execution_boundary.py",
    "scripts/smoke_v540_openai_real_provider_runtime.py",
}
FORBIDDEN_ROOT_IMPORT_FRAGMENTS = (
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
        "REQ-4 changed surface mismatch:\n"
        f"expected={sorted(EXPECTED_CHANGED_PATHS)}\n"
        f"actual={sorted(actual)}",
    )
    _ok("REQ-4 worktree contains the exact eleven-file implementation surface")


def _validate_docs() -> None:
    combined = "\n".join(
        (
            _read("README.md"),
            _read("docs/v540_openai_adapter_client_injection_contract.md"),
            _read("docs/v540_openai_fake_execution_boundary.md"),
            _read("docs/v540_openai_real_provider_runtime.md"),
            _read("docs/v540_provider_execution_configuration_status.md"),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
            _read("docs/v540_real_stt_provider_execution_small_commit_checklist.md"),
        )
    )
    for marker in (
        "REQ-3: ACCEPTED",
        "REQ-4: ACCEPTED",
        "REQ-5: READY pending next small commit",
        "OpenAIVoiceInputPrivateCredential",
        "OpenAIVoiceInputRealProviderPolicy",
        "OpenAIVoiceInputRealClientFactory",
        "OpenAIVoiceInputRealProviderExecutor",
        "allow_provider_sdk_import",
        "allow_provider_client_creation",
        "allow_real_provider_execution",
        "client.audio.transcriptions.create(...)",
        "provider_timeout",
        "provider_rate_limited",
    ):
        _require(marker in combined, f"REQ-4 docs missing marker: {marker}")

    for forbidden in (
        "REQ-4: IMPLEMENTED / NOT_ACCEPTED",
        "REQ-5: BLOCKED pending REQ-4 acceptance",
        "real OpenAI transcription succeeded",
        "private credential committed",
    ):
        _require(
            forbidden not in combined,
            f"REQ-4 docs contain stale or premature marker: {forbidden}",
        )
    _ok("REQ-4 docs record acceptance and authorize REQ-5 for the next small commit")


def _validate_source_boundary() -> None:
    source = _read("framework/openai_voice_input_real_provider.py")
    tree = ast.parse(source)

    imported_modules: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    _require(
        "openai" not in imported_modules,
        "REQ-4 must not eagerly import the OpenAI SDK",
    )
    _require("getenv" not in calls, "REQ-4 must not read credential environment")
    _require(
        'self.module_importer("openai")' in source,
        "REQ-4 lazy OpenAI import boundary missing",
    )
    _require(
        "api_key=self.credential._value_for_provider_client()" in source,
        "REQ-4 explicit private credential injection missing",
    )
    _ok("REQ-4 source is lazy and does not resolve credential environment")


def _make_sdk(
    *,
    response: object | None = None,
    error_type: type[Exception] | None = None,
) -> tuple[object, dict[str, object]]:
    record: dict[str, object] = {
        "constructor_calls": 0,
        "create_calls": 0,
        "api_key": None,
        "timeout": None,
        "max_retries": None,
        "model": None,
        "language": None,
        "file_name": None,
        "file_bytes": b"",
    }

    class FakeTranscriptions:
        def create(self, **kwargs: object) -> object:
            record["create_calls"] = int(record["create_calls"]) + 1
            record["model"] = kwargs.get("model")
            record["language"] = kwargs.get("language")
            payload = kwargs["file"]
            record["file_name"] = getattr(payload, "name", None)
            record["file_bytes"] = payload.read()
            if error_type is not None:
                raise error_type("private provider details")
            return (
                response
                if response is not None
                else {"text": "runtime transcript", "language": "ja"}
            )

    class FakeAudio:
        def __init__(self) -> None:
            self.transcriptions = FakeTranscriptions()

    class FakeOpenAI:
        def __init__(
            self,
            *,
            api_key: str,
            timeout: float,
            max_retries: int,
        ) -> None:
            record["constructor_calls"] = int(record["constructor_calls"]) + 1
            record["api_key"] = api_key
            record["timeout"] = timeout
            record["max_retries"] = max_retries
            self.audio = FakeAudio()

    return SimpleNamespace(OpenAI=FakeOpenAI), record


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
            for fragment in FORBIDDEN_ROOT_IMPORT_FRAGMENTS
        )
    )
    _require(
        not hits,
        f"framework root import loaded provider/runtime modules: {hits}",
    )
    _require("openai" not in sys.modules, "root import loaded actual OpenAI SDK")

    exports = (
        "OpenAIVoiceInputPrivateCredential",
        "OpenAIVoiceInputRealClientFactory",
        "OpenAIVoiceInputRealProviderExecutor",
        "OpenAIVoiceInputRealProviderPolicy",
        "OpenAIVoiceInputRealProviderStatus",
        "OpenAIVoiceInputRuntimeMode",
    )
    for name in exports:
        _require(hasattr(framework, name), f"framework missing export: {name}")
        _require(name in framework.__all__, f"framework.__all__ missing: {name}")
    _require("openai" not in sys.modules, "lazy export imported actual OpenAI SDK")

    secret_value = "sk-req4-dummy-secret-never-log"
    credential = framework.OpenAIVoiceInputPrivateCredential(secret_value)
    _require(secret_value not in repr(credential), "credential repr leaked")
    _require(secret_value not in str(credential), "credential str leaked")

    config = framework.resolve_voice_input_provider_execution_config(
        provider="openai",
        allow_provider_execution=True,
        credentials_available=True,
    )

    import_calls = {"count": 0}

    def must_not_import(name: str) -> object:
        import_calls["count"] += 1
        raise AssertionError(f"default gates imported {name}")

    blocked_policy = framework.OpenAIVoiceInputRealProviderPolicy(
        max_audio_bytes=1024,
    )
    blocked_factory = framework.OpenAIVoiceInputRealClientFactory(
        credential=credential,
        policy=blocked_policy,
        module_importer=must_not_import,
    )
    blocked_adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="explicit-runtime-model",
        client_factory=blocked_factory,
    )
    blocked_source = framework.VoiceInputAudioSource.from_file_path(
        "must-not-be-read.wav",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=1000),
        language="ja",
        max_duration_ms=5000,
    )
    blocked = framework.OpenAIVoiceInputRealProviderExecutor(
        adapter=blocked_adapter,
    ).execute(audio_source=blocked_source)
    _require(
        blocked.public_metadata["real_provider_status"]
        == "real_execution_not_allowed",
        "default real execution gate mismatch",
    )
    _require(import_calls["count"] == 0, "default gates invoked SDK importer")

    sdk_blocked_policy = framework.OpenAIVoiceInputRealProviderPolicy(
        max_audio_bytes=1024,
        allow_real_provider_execution=True,
    )
    sdk_blocked_factory = framework.OpenAIVoiceInputRealClientFactory(
        credential=credential,
        policy=sdk_blocked_policy,
        module_importer=must_not_import,
    )
    sdk_blocked_adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="explicit-runtime-model",
        client_factory=sdk_blocked_factory,
    )
    sdk_blocked = framework.OpenAIVoiceInputRealProviderExecutor(
        adapter=sdk_blocked_adapter,
    ).execute(audio_source=blocked_source)
    _require(
        sdk_blocked.public_metadata["real_provider_status"]
        == "sdk_import_not_allowed",
        "SDK import gate mismatch",
    )
    _require(import_calls["count"] == 0, "SDK-blocked path invoked importer")

    with tempfile.TemporaryDirectory(prefix="fw-v540-req4-") as temp:
        audio_path = Path(temp) / "private-operator-audio.wav"
        audio_bytes = b"RIFF" + (b"\x00" * 120)
        audio_path.write_bytes(audio_bytes)
        source = framework.VoiceInputAudioSource.from_file_path(
            str(audio_path),
            audio_format=framework.VoiceInputAudioFormat.wav(
                sample_rate_hz=16000,
                channel_count=1,
                duration_ms=1000,
            ),
            language="ja",
            max_duration_ms=5000,
        )

        sdk, record = _make_sdk()
        importer_calls: list[str] = []

        def fake_importer(name: str) -> object:
            importer_calls.append(name)
            return sdk

        test_policy = framework.OpenAIVoiceInputRealProviderPolicy(
            max_audio_bytes=1024,
            timeout_seconds=12.5,
            max_retries=0,
            allow_provider_sdk_import=True,
            allow_provider_client_creation=True,
            allow_real_provider_execution=True,
            runtime_mode=framework.OpenAIVoiceInputRuntimeMode.TEST_DOUBLE,
        )
        factory = framework.OpenAIVoiceInputRealClientFactory(
            credential=credential,
            policy=test_policy,
            module_importer=fake_importer,
        )
        adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-runtime-model",
            client_factory=factory,
        )
        executor = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=adapter,
        )
        result = executor.execute(
            audio_source=source,
            request=framework.VoiceInputRequest(language="ja"),
        )

        _require(result.is_completed, "test-double runtime did not complete")
        _require(result.text == "runtime transcript", "transcript normalization changed")
        _require(importer_calls == ["openai"], "lazy importer call mismatch")
        _require(record["constructor_calls"] == 1, "client constructor count mismatch")
        _require(record["create_calls"] == 1, "transcription call count mismatch")
        _require(record["api_key"] == secret_value, "private credential not injected")
        _require(record["timeout"] == 12.5, "timeout was not forwarded")
        _require(record["max_retries"] == 0, "max_retries was not forwarded")
        _require(record["model"] == "explicit-runtime-model", "model mismatch")
        _require(record["language"] == "ja", "language mismatch")
        _require(record["file_name"] == "audio.wav", "sanitized filename mismatch")
        _require(record["file_bytes"] == audio_bytes, "audio handoff mismatch")

        metadata = dict(result.public_metadata)
        _require(metadata["provider_runtime_loaded"] is True, "runtime load marker mismatch")
        _require(metadata["provider_sdk_imported"] is False, "test double claimed SDK import")
        _require(metadata["test_double_runtime_loaded"] is True, "test runtime marker mismatch")
        _require(metadata["provider_client_created"] is False, "test client claimed real client")
        _require(metadata["test_double_client_created"] is True, "test client marker mismatch")
        _require(metadata["real_provider_execution_executed"] is False, "test double claimed real execution")
        _require(metadata["test_double_execution_executed"] is True, "test execution marker mismatch")
        _require(metadata["private_auth_value_exposed"] is False, "credential exposure marker mismatch")
        public_text = str(result)
        _require(secret_value not in public_text, "credential leaked into result")
        _require(str(audio_path) not in public_text, "private path leaked into result")
        _require("RIFF" not in public_text, "raw audio leaked into result")

        class APITimeoutError(Exception):
            pass

        timeout_sdk, _ = _make_sdk(error_type=APITimeoutError)
        timeout_factory = framework.OpenAIVoiceInputRealClientFactory(
            credential=credential,
            policy=test_policy,
            module_importer=lambda _name: timeout_sdk,
        )
        timeout_adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-runtime-model",
            client_factory=timeout_factory,
        )
        timeout_result = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=timeout_adapter,
        ).execute(audio_source=source)
        _require(
            timeout_result.public_metadata["real_provider_status"]
            == "provider_timeout",
            "timeout mapping mismatch",
        )
        _require(timeout_result.retryable is True, "timeout should be retryable")
        _require(
            "private provider details" not in str(timeout_result),
            "timeout exception details leaked",
        )

        class RateLimitError(Exception):
            pass

        rate_sdk, _ = _make_sdk(error_type=RateLimitError)
        rate_factory = framework.OpenAIVoiceInputRealClientFactory(
            credential=credential,
            policy=test_policy,
            module_importer=lambda _name: rate_sdk,
        )
        rate_adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=config,
            model="explicit-runtime-model",
            client_factory=rate_factory,
        )
        rate_result = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=rate_adapter,
        ).execute(audio_source=source)
        _require(
            rate_result.public_metadata["real_provider_status"]
            == "provider_rate_limited",
            "rate-limit mapping mismatch",
        )
        _require(rate_result.retryable is True, "rate limit should be retryable")

        empty_path = Path(temp) / "empty.wav"
        empty_path.write_bytes(b"")
        empty_source = framework.VoiceInputAudioSource.from_file_path(
            str(empty_path),
            audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=0),
            max_duration_ms=5000,
        )
        empty_result = executor.execute(audio_source=empty_source)
        _require(
            empty_result.public_metadata["real_provider_status"] == "audio_empty",
            "empty audio rejection mismatch",
        )

    _require("openai" not in sys.modules, "smoke imported actual OpenAI SDK")
    _ok("REQ-4 lazy runtime, private credential, call shape, and error mapping passed")


def main() -> None:
    _validate_changed_surface()
    _validate_docs()
    _validate_source_boundary()
    _validate_runtime_contract()

    print("v540_openai_real_provider_runtime_status: accepted")
    print("v540_provider_root_import_safe: True")
    print("v540_provider_sdk_import_default: False")
    print("v540_provider_client_creation_default: False")
    print("v540_real_provider_execution_default: False")
    print("v540_private_credential_explicit: True")
    print("v540_private_credential_environment_read: False")
    print("v540_private_credential_exposed: False")
    print("v540_test_double_runtime_loaded: True")
    print("v540_test_double_protocol_call_executed: True")
    print("v540_provider_sdk_imported_in_smoke: False")
    print("v540_provider_client_created_in_smoke: False")
    print("v540_real_provider_execution_executed_in_smoke: False")
    print("v540_timeout_mapping_present: True")
    print("v540_rate_limit_mapping_present: True")
    print("v540_audio_path_exposed: False")
    print("v540_raw_audio_exposed: False")
    print("v540_provider_payload_exposed: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req5_authorization: ready-for-req5")
    _ok("v5.4.0 REQ-4 lazy real-provider runtime acceptance passed")


if __name__ == "__main__":
    main()
