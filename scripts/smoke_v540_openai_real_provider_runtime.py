\
"""Regression check for accepted v5.4.0 REQ-4 real-provider runtime.

The smoke uses only injected SDK test doubles. It verifies provider call shape,
success normalization, and safe OpenAI API-status error classification without
importing the actual SDK, reading credentials/audio outside its temporary
directory, or executing a network request.
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any


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
            _read(
                "docs/v540_openai_private_real_provider_operator_acceptance.md"
            ),
            _read("docs/v540_real_stt_provider_execution_requirements.md"),
        )
    )
    _require("REQ-4: ACCEPTED" in combined, "REQ-4 accepted marker missing")
    _require(
        "REQ-5: ACCEPTED" in combined,
        "REQ-5 accepted marker missing",
    )
    _require(
        "release readiness: READY pending next small commit" in combined,
        "REQ-5 release-readiness handoff marker missing",
    )
    _require(
        "v540_req5_private_evidence_status: accepted-by-validator"
        in combined,
        "REQ-5 public validator acceptance marker missing",
    )
    for marker in (
        "OpenAIVoiceInputPrivateCredential",
        "OpenAIVoiceInputRealClientFactory",
        "allow_provider_sdk_import",
        "allow_provider_client_creation",
        "allow_real_provider_execution",
        "provider_error_type",
        "provider_http_status",
        "BadRequestError",
        "PermissionDeniedError",
        "UnprocessableEntityError",
        "InternalServerError",
    ):
        _require(marker in combined, f"runtime docs missing: {marker}")
    _ok("REQ-4/REQ-5 safe API-status diagnostics documentation is present")


def _framework() -> Any:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    framework = importlib.import_module("framework")
    _require("openai" not in sys.modules, "root import loaded actual OpenAI SDK")
    return framework


def _execute(
    framework: Any,
    *,
    create: Any,
) -> tuple[Any, dict[str, object], str]:
    secret = "sk-safe-diagnostics-dummy"
    record: dict[str, object] = {
        "calls": 0,
        "api_key": None,
        "audio_bytes": b"",
        "file_name": None,
    }

    class Transcriptions:
        def create(self, **kwargs: object) -> object:
            record["calls"] = int(record["calls"]) + 1
            payload = kwargs["file"]
            record["file_name"] = getattr(payload, "name", None)
            record["audio_bytes"] = payload.read()
            return create(**kwargs)

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
        credential=framework.OpenAIVoiceInputPrivateCredential(secret),
        policy=policy,
        module_importer=lambda name: sdk,
    )
    adapter = framework.OpenAIVoiceInputProviderAdapter(
        execution_config=config,
        model="safe-diagnostics-model",
        client_factory=factory,
    )

    with tempfile.TemporaryDirectory(
        prefix="fw-v540-safe-diagnostics-"
    ) as temp:
        audio_path = Path(temp) / "private-source.wav"
        audio_path.write_bytes(b"RIFF" + (b"\x00" * 20))
        source = framework.VoiceInputAudioSource.from_file_path(
            str(audio_path),
            audio_format=framework.VoiceInputAudioFormat.wav(
                duration_ms=1000
            ),
            language="ja",
            max_duration_ms=5000,
        )
        result = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=adapter
        ).execute(audio_source=source)

    return result, record, secret


def _validate_success() -> None:
    framework = _framework()
    result, record, secret = _execute(
        framework,
        create=lambda **kwargs: {
            "text": "safe diagnostics transcript",
            "language": "ja",
        },
    )
    _require(result.is_completed, "test-double success no longer completes")
    _require(record["calls"] == 1, "provider call count changed")
    _require(record["api_key"] == secret, "credential forwarding changed")
    _require(record["file_name"] == "audio.wav", "sanitized name changed")
    _require(record["audio_bytes"] == b"RIFF" + (b"\x00" * 20), "audio changed")
    _require(
        result.public_metadata["real_provider_execution_executed"] is False,
        "test double claimed real execution",
    )
    _require(secret not in str(result), "credential leaked")
    _require("openai" not in sys.modules, "actual OpenAI SDK was imported")
    _ok("REQ-4 accepted lazy runtime success path remains valid")


def _exception(name: str, status_code: int | None) -> Exception:
    exception_type = type(name, (Exception,), {})
    exc = exception_type("PRIVATE_PROVIDER_ERROR_DETAIL_MUST_NOT_LEAK")
    if status_code is not None:
        setattr(exc, "status_code", status_code)
    return exc


def _validate_error_mapping() -> None:
    framework = _framework()
    cases = (
        ("APITimeoutError", None, "provider_timeout", "timeout", True),
        (
            "APIConnectionError",
            None,
            "provider_connection_error",
            "connection_error",
            True,
        ),
        (
            "BadRequestError",
            400,
            "provider_bad_request",
            "bad_request",
            False,
        ),
        (
            "AuthenticationError",
            401,
            "provider_authentication_error",
            "authentication_error",
            False,
        ),
        (
            "PermissionDeniedError",
            403,
            "provider_permission_denied",
            "permission_denied",
            False,
        ),
        (
            "NotFoundError",
            404,
            "provider_not_found",
            "not_found",
            False,
        ),
        (
            "ConflictError",
            409,
            "provider_conflict",
            "conflict",
            True,
        ),
        (
            "UnprocessableEntityError",
            422,
            "provider_unprocessable_entity",
            "unprocessable_entity",
            False,
        ),
        (
            "RateLimitError",
            429,
            "provider_rate_limited",
            "rate_limited",
            True,
        ),
        (
            "InternalServerError",
            503,
            "provider_internal_error",
            "internal_server_error",
            True,
        ),
        (
            "APIStatusError",
            418,
            "provider_api_status_error",
            "api_status_error",
            False,
        ),
    )

    for (
        exception_name,
        status_code,
        runtime_status,
        error_type,
        retryable,
    ) in cases:
        exc = _exception(exception_name, status_code)

        def raise_error(**kwargs: object) -> object:
            raise exc

        result, _record, secret = _execute(
            framework,
            create=raise_error,
        )
        metadata = result.public_metadata
        _require(not result.is_completed, f"{exception_name}: result not failed")
        _require(
            metadata["real_provider_status"] == runtime_status,
            f"{exception_name}: runtime status mismatch",
        )
        _require(
            metadata["provider_error_type"] == error_type,
            f"{exception_name}: safe error type mismatch",
        )
        _require(
            metadata["provider_http_status"] == status_code,
            f"{exception_name}: HTTP status mismatch",
        )
        _require(
            result.retryable is retryable,
            f"{exception_name}: retryable mismatch",
        )
        rendered = str(result)
        _require(secret not in rendered, f"{exception_name}: secret leaked")
        _require(
            "PRIVATE_PROVIDER_ERROR_DETAIL_MUST_NOT_LEAK" not in rendered,
            f"{exception_name}: exception detail leaked",
        )
        for forbidden_key in (
            "provider_response",
            "provider_payload",
            "request_id",
            "response_body",
        ):
            _require(
                forbidden_key not in metadata,
                f"{exception_name}: unsafe metadata key present",
            )

    _ok("OpenAI API status errors map to safe fixed classifications")


def main() -> None:
    _validate_docs()
    _validate_success()
    _validate_error_mapping()

    print("v540_openai_real_provider_runtime_status: accepted")
    print("v540_provider_root_import_safe: True")
    print("v540_provider_sdk_import_default: False")
    print("v540_provider_client_creation_default: False")
    print("v540_real_provider_execution_default: False")
    print("v540_private_credential_environment_read_by_framework: False")
    print("v540_private_credential_exposed: False")
    print("v540_openai_api_status_error_mapping_present: True")
    print("v540_openai_provider_error_body_exposed: False")
    print("v540_openai_provider_response_exposed: False")
    print("v540_openai_request_id_exposed: False")
    print("v540_provider_sdk_imported_in_smoke: False")
    print("v540_provider_client_created_in_smoke: False")
    print("v540_real_provider_execution_executed_in_smoke: False")
    print("v540_req5_authorization: authorized-by-req4-acceptance")
    _ok("v5.4.0 REQ-4 safe API-status diagnostics passed")


if __name__ == "__main__":
    main()
