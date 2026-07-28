"""Lazy OpenAI real-provider runtime for voice-input transcription.

REQ-4 implements the first concrete real-provider execution boundary. The
OpenAI SDK is imported only after all explicit gates pass. The framework never
reads credential values from environment variables and never executes by
default.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Mapping

from .openai_voice_input_provider_adapter import OpenAIVoiceInputProviderAdapter
from .voice_input import (
    VoiceInputErrorCode,
    VoiceInputOutcome,
    VoiceInputRequest,
    VoiceInputResult,
)
from .voice_input_audio import VoiceInputAudioSource


class OpenAIVoiceInputRuntimeMode(str, Enum):
    """Whether the runtime importer targets the actual SDK or a test double."""

    REAL = "real"
    TEST_DOUBLE = "test_double"


class OpenAIVoiceInputRealProviderStatus(str, Enum):
    """Typed REQ-4 real-provider runtime outcomes."""

    REAL_EXECUTION_NOT_ALLOWED = "real_execution_not_allowed"
    SDK_IMPORT_NOT_ALLOWED = "sdk_import_not_allowed"
    CLIENT_CREATION_NOT_ALLOWED = "client_creation_not_allowed"
    PRIVATE_CREDENTIAL_REQUIRED = "private_credential_required"
    ADAPTER_NOT_READY = "adapter_not_ready"
    CONCRETE_FACTORY_REQUIRED = "concrete_factory_required"
    SDK_UNAVAILABLE = "sdk_unavailable"
    CLIENT_CREATION_FAILED = "client_creation_failed"
    AUDIO_PATH_NOT_FOUND = "audio_path_not_found"
    AUDIO_SOURCE_NOT_REGULAR_FILE = "audio_source_not_regular_file"
    AUDIO_EMPTY = "audio_empty"
    AUDIO_TOO_LARGE = "audio_too_large"
    AUDIO_READ_FAILED = "audio_read_failed"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_CONNECTION_ERROR = "provider_connection_error"
    PROVIDER_AUTHENTICATION_ERROR = "provider_authentication_error"
    PROVIDER_BAD_REQUEST = "provider_bad_request"
    PROVIDER_PERMISSION_DENIED = "provider_permission_denied"
    PROVIDER_NOT_FOUND = "provider_not_found"
    PROVIDER_CONFLICT = "provider_conflict"
    PROVIDER_UNPROCESSABLE_ENTITY = "provider_unprocessable_entity"
    PROVIDER_INTERNAL_ERROR = "provider_internal_error"
    PROVIDER_API_STATUS_ERROR = "provider_api_status_error"
    PROVIDER_ERROR = "provider_error"
    NO_TRANSCRIPT = "no_transcript"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True, init=False)
class OpenAIVoiceInputPrivateCredential:
    """Non-empty private API credential with redacted repr/str output."""

    _api_key: str = field(repr=False, compare=False)

    def __init__(self, api_key: str) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("OpenAI private credential must be non-empty")
        object.__setattr__(self, "_api_key", api_key.strip())

    def __repr__(self) -> str:
        return "OpenAIVoiceInputPrivateCredential(<redacted>)"

    __str__ = __repr__

    def _value_for_provider_client(self) -> str:
        return self._api_key


@dataclass(frozen=True, slots=True)
class OpenAIVoiceInputRealProviderPolicy:
    """Explicit host policy for lazy SDK import, client creation, and execution."""

    max_audio_bytes: int
    timeout_seconds: float = 30.0
    max_retries: int = 0
    allow_provider_sdk_import: bool = False
    allow_provider_client_creation: bool = False
    allow_real_provider_execution: bool = False
    runtime_mode: OpenAIVoiceInputRuntimeMode | str = OpenAIVoiceInputRuntimeMode.REAL

    def __post_init__(self) -> None:
        if self.max_audio_bytes <= 0:
            raise ValueError("max_audio_bytes must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        mode = (
            self.runtime_mode
            if isinstance(self.runtime_mode, OpenAIVoiceInputRuntimeMode)
            else OpenAIVoiceInputRuntimeMode(str(self.runtime_mode))
        )
        object.__setattr__(self, "runtime_mode", mode)


class _OpenAIVoiceInputRuntimeFailure(RuntimeError):
    def __init__(
        self,
        status: OpenAIVoiceInputRealProviderStatus,
        safe_message: str,
    ) -> None:
        super().__init__(safe_message)
        self.status = status
        self.safe_message = safe_message


ModuleImporter = Callable[[str], Any]


@dataclass(frozen=True)
class OpenAIVoiceInputRealClientFactory:
    """Lazy concrete OpenAI client factory with private credential injection."""

    credential: OpenAIVoiceInputPrivateCredential = field(repr=False, compare=False)
    policy: OpenAIVoiceInputRealProviderPolicy
    module_importer: ModuleImporter = field(
        default=import_module,
        repr=False,
        compare=False,
    )

    def __call__(self) -> Any:
        if not self.policy.allow_provider_sdk_import:
            raise _OpenAIVoiceInputRuntimeFailure(
                OpenAIVoiceInputRealProviderStatus.SDK_IMPORT_NOT_ALLOWED,
                "OpenAI SDK import requires explicit host-controlled opt-in.",
            )
        if not self.policy.allow_provider_client_creation:
            raise _OpenAIVoiceInputRuntimeFailure(
                OpenAIVoiceInputRealProviderStatus.CLIENT_CREATION_NOT_ALLOWED,
                "OpenAI client creation requires explicit host-controlled opt-in.",
            )

        try:
            sdk_module = self.module_importer("openai")
        except (ImportError, ModuleNotFoundError):
            raise _OpenAIVoiceInputRuntimeFailure(
                OpenAIVoiceInputRealProviderStatus.SDK_UNAVAILABLE,
                "The optional OpenAI SDK is unavailable.",
            ) from None
        except Exception:
            raise _OpenAIVoiceInputRuntimeFailure(
                OpenAIVoiceInputRealProviderStatus.SDK_UNAVAILABLE,
                "The optional OpenAI SDK could not be loaded.",
            ) from None

        client_type = getattr(sdk_module, "OpenAI", None)
        if client_type is None or not callable(client_type):
            raise _OpenAIVoiceInputRuntimeFailure(
                OpenAIVoiceInputRealProviderStatus.SDK_UNAVAILABLE,
                "The loaded OpenAI SDK does not expose the expected client.",
            )

        try:
            return client_type(
                api_key=self.credential._value_for_provider_client(),
                timeout=self.policy.timeout_seconds,
                max_retries=self.policy.max_retries,
            )
        except Exception:
            raise _OpenAIVoiceInputRuntimeFailure(
                OpenAIVoiceInputRealProviderStatus.CLIENT_CREATION_FAILED,
                "The OpenAI client could not be created.",
            ) from None


@dataclass(frozen=True)
class OpenAIVoiceInputRealProviderExecutor:
    """Bounded real-provider execution through the concrete lazy factory."""

    adapter: OpenAIVoiceInputProviderAdapter

    @staticmethod
    def _response_value(response: Any, key: str) -> Any:
        if isinstance(response, Mapping):
            return response.get(key)
        return getattr(response, key, None)

    @staticmethod
    def _exception_name(exc: Exception) -> str:
        return type(exc).__name__

    def _factory(self) -> OpenAIVoiceInputRealClientFactory | None:
        factory = self.adapter.client_factory
        return (
            factory
            if isinstance(factory, OpenAIVoiceInputRealClientFactory)
            else None
        )

    def _metadata(
        self,
        *,
        status: OpenAIVoiceInputRealProviderStatus,
        policy: OpenAIVoiceInputRealProviderPolicy | None,
        audio_bytes_read: int = 0,
        sdk_imported: bool = False,
        client_created: bool = False,
        provider_protocol_call_executed: bool = False,
        provider_error_type: str | None = None,
        provider_http_status: int | None = None,
    ) -> dict[str, Any]:
        runtime_mode = (
            policy.runtime_mode.value
            if policy is not None
            else OpenAIVoiceInputRuntimeMode.REAL.value
        )
        return {
            "provider": "openai",
            "real_provider_status": status.value,
            "runtime_mode": runtime_mode,
            "provider_runtime_loaded": sdk_imported,
            "provider_sdk_imported": (
                sdk_imported
                and runtime_mode == OpenAIVoiceInputRuntimeMode.REAL.value
            ),
            "test_double_runtime_loaded": (
                sdk_imported
                and runtime_mode == OpenAIVoiceInputRuntimeMode.TEST_DOUBLE.value
            ),
            "provider_client_created": (
                client_created
                and runtime_mode == OpenAIVoiceInputRuntimeMode.REAL.value
            ),
            "test_double_client_created": (
                client_created
                and runtime_mode == OpenAIVoiceInputRuntimeMode.TEST_DOUBLE.value
            ),
            "provider_protocol_call_executed": provider_protocol_call_executed,
            "provider_error_type": provider_error_type,
            "provider_http_status": provider_http_status,
            "real_provider_execution_executed": (
                provider_protocol_call_executed
                and runtime_mode == OpenAIVoiceInputRuntimeMode.REAL.value
            ),
            "test_double_execution_executed": (
                provider_protocol_call_executed
                and runtime_mode == OpenAIVoiceInputRuntimeMode.TEST_DOUBLE.value
            ),
            "credential_value_used_for_client": client_created,
            "private_auth_value_exposed": False,
            "client_factory_invoked": client_created,
            "max_audio_bytes": (
                policy.max_audio_bytes if policy is not None else None
            ),
            "audio_bytes_read": audio_bytes_read,
            "audio_path_exposed": False,
            "raw_audio_exposed": False,
            "provider_payload_exposed": False,
            "microphone_accessed": False,
        }

    def _unavailable(
        self,
        status: OpenAIVoiceInputRealProviderStatus,
        safe_message: str,
        *,
        policy: OpenAIVoiceInputRealProviderPolicy | None,
        audio_bytes_read: int = 0,
        sdk_imported: bool = False,
        client_created: bool = False,
    ) -> VoiceInputResult:
        return VoiceInputResult.unavailable(
            safe_message=safe_message,
            retryable=False,
            public_metadata=self._metadata(
                status=status,
                policy=policy,
                audio_bytes_read=audio_bytes_read,
                sdk_imported=sdk_imported,
                client_created=client_created,
            ),
        )

    def _provider_failure(
        self,
        exc: Exception,
        *,
        policy: OpenAIVoiceInputRealProviderPolicy,
        audio_bytes_read: int,
    ) -> VoiceInputResult:
        name = self._exception_name(exc)
        status_code_value = getattr(exc, "status_code", None)
        provider_http_status = (
            status_code_value
            if isinstance(status_code_value, int)
            else None
        )

        if name == "APITimeoutError":
            status = OpenAIVoiceInputRealProviderStatus.PROVIDER_TIMEOUT
            provider_error_type = "timeout"
            safe_message = "OpenAI transcription timed out."
            retryable = True
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "RateLimitError":
            status = OpenAIVoiceInputRealProviderStatus.PROVIDER_RATE_LIMITED
            provider_error_type = "rate_limited"
            provider_http_status = 429
            safe_message = "OpenAI transcription is temporarily rate limited."
            retryable = True
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "APIConnectionError":
            status = (
                OpenAIVoiceInputRealProviderStatus
                .PROVIDER_CONNECTION_ERROR
            )
            provider_error_type = "connection_error"
            safe_message = "OpenAI transcription could not connect."
            retryable = True
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "BadRequestError":
            status = (
                OpenAIVoiceInputRealProviderStatus.PROVIDER_BAD_REQUEST
            )
            provider_error_type = "bad_request"
            provider_http_status = 400
            safe_message = "OpenAI transcription request was rejected."
            retryable = False
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "AuthenticationError":
            status = (
                OpenAIVoiceInputRealProviderStatus
                .PROVIDER_AUTHENTICATION_ERROR
            )
            provider_error_type = "authentication_error"
            provider_http_status = 401
            safe_message = "OpenAI transcription credentials were rejected."
            retryable = False
            error_code = VoiceInputErrorCode.MISSING_CREDENTIALS
        elif name == "PermissionDeniedError":
            status = (
                OpenAIVoiceInputRealProviderStatus
                .PROVIDER_PERMISSION_DENIED
            )
            provider_error_type = "permission_denied"
            provider_http_status = 403
            safe_message = "OpenAI transcription permission was denied."
            retryable = False
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "NotFoundError":
            status = (
                OpenAIVoiceInputRealProviderStatus.PROVIDER_NOT_FOUND
            )
            provider_error_type = "not_found"
            provider_http_status = 404
            safe_message = (
                "OpenAI transcription model or endpoint was not found."
            )
            retryable = False
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "ConflictError":
            status = (
                OpenAIVoiceInputRealProviderStatus.PROVIDER_CONFLICT
            )
            provider_error_type = "conflict"
            provider_http_status = 409
            safe_message = "OpenAI transcription encountered a conflict."
            retryable = True
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "UnprocessableEntityError":
            status = (
                OpenAIVoiceInputRealProviderStatus
                .PROVIDER_UNPROCESSABLE_ENTITY
            )
            provider_error_type = "unprocessable_entity"
            provider_http_status = 422
            safe_message = "OpenAI transcription input was not processable."
            retryable = False
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "InternalServerError":
            status = (
                OpenAIVoiceInputRealProviderStatus
                .PROVIDER_INTERNAL_ERROR
            )
            provider_error_type = "internal_server_error"
            if provider_http_status is None:
                provider_http_status = 500
            safe_message = (
                "OpenAI transcription encountered a provider server error."
            )
            retryable = True
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        elif name == "APIStatusError":
            status = (
                OpenAIVoiceInputRealProviderStatus
                .PROVIDER_API_STATUS_ERROR
            )
            provider_error_type = "api_status_error"
            safe_message = (
                "OpenAI transcription returned an unsuccessful status."
            )
            retryable = bool(
                provider_http_status is not None
                and (
                    provider_http_status in (408, 409, 429)
                    or provider_http_status >= 500
                )
            )
            error_code = VoiceInputErrorCode.PROVIDER_ERROR
        else:
            status = OpenAIVoiceInputRealProviderStatus.PROVIDER_ERROR
            provider_error_type = "provider_error"
            safe_message = "OpenAI transcription failed."
            retryable = False
            error_code = VoiceInputErrorCode.PROVIDER_ERROR

        return VoiceInputResult.failed(
            public_error_code=error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=self._metadata(
                status=status,
                policy=policy,
                audio_bytes_read=audio_bytes_read,
                sdk_imported=True,
                client_created=True,
                provider_protocol_call_executed=True,
                provider_error_type=provider_error_type,
                provider_http_status=provider_http_status,
            ),
        )

    def execute(
        self,
        *,
        audio_source: VoiceInputAudioSource,
        request: VoiceInputRequest | None = None,
    ) -> VoiceInputResult:
        factory = self._factory()
        if factory is None:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.CONCRETE_FACTORY_REQUIRED,
                (
                    "REQ-4 requires OpenAIVoiceInputRealClientFactory; "
                    "direct or arbitrary factories are not executed."
                ),
                policy=None,
            )

        policy = factory.policy
        if not policy.allow_real_provider_execution:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.REAL_EXECUTION_NOT_ALLOWED,
                "Real OpenAI STT execution requires explicit host-controlled opt-in.",
                policy=policy,
            )
        if not policy.allow_provider_sdk_import:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.SDK_IMPORT_NOT_ALLOWED,
                "OpenAI SDK import requires explicit host-controlled opt-in.",
                policy=policy,
            )
        if not policy.allow_provider_client_creation:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.CLIENT_CREATION_NOT_ALLOWED,
                "OpenAI client creation requires explicit host-controlled opt-in.",
                policy=policy,
            )

        contract = self.adapter.preflight_contract(audio_source=audio_source)
        if not contract.is_ready:
            result = self._unavailable(
                OpenAIVoiceInputRealProviderStatus.ADAPTER_NOT_READY,
                contract.safe_message,
                policy=policy,
            )
            metadata = dict(result.public_metadata)
            metadata["adapter_guard"] = contract.status.value
            return VoiceInputResult.unavailable(
                safe_message=result.safe_message,
                retryable=False,
                public_metadata=metadata,
            )

        path = Path(audio_source.ref.value)
        try:
            path_status = path.lstat()
        except FileNotFoundError:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_PATH_NOT_FOUND,
                "The host-provided audio file was not found.",
                policy=policy,
            )
        except OSError:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_READ_FAILED,
                "The host-provided audio file could not be inspected.",
                policy=policy,
            )

        if not stat.S_ISREG(path_status.st_mode):
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_SOURCE_NOT_REGULAR_FILE,
                "The host-provided audio source must be a regular file.",
                policy=policy,
            )
        if path_status.st_size == 0:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_EMPTY,
                "The host-provided audio file is empty.",
                policy=policy,
            )
        if path_status.st_size > policy.max_audio_bytes:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_TOO_LARGE,
                "The host-provided audio file exceeds the configured byte bound.",
                policy=policy,
            )

        try:
            with path.open("rb") as handle:
                opened_status = os.fstat(handle.fileno())
                if not stat.S_ISREG(opened_status.st_mode):
                    return self._unavailable(
                        (
                            OpenAIVoiceInputRealProviderStatus
                            .AUDIO_SOURCE_NOT_REGULAR_FILE
                        ),
                        "The opened audio source is not a regular file.",
                        policy=policy,
                    )
                audio_bytes = handle.read(policy.max_audio_bytes + 1)
        except OSError:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_READ_FAILED,
                "The host-provided audio file could not be read.",
                policy=policy,
            )

        if not audio_bytes:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_EMPTY,
                "The host-provided audio file is empty.",
                policy=policy,
            )
        if len(audio_bytes) > policy.max_audio_bytes:
            return self._unavailable(
                OpenAIVoiceInputRealProviderStatus.AUDIO_TOO_LARGE,
                "The host-provided audio file exceeded the byte bound while reading.",
                policy=policy,
                audio_bytes_read=policy.max_audio_bytes,
            )

        try:
            client = factory()
        except _OpenAIVoiceInputRuntimeFailure as exc:
            return self._unavailable(
                exc.status,
                exc.safe_message,
                policy=policy,
                audio_bytes_read=len(audio_bytes),
                sdk_imported=(
                    exc.status
                    is OpenAIVoiceInputRealProviderStatus.CLIENT_CREATION_FAILED
                ),
                client_created=False,
            )

        payload = BytesIO(audio_bytes)
        payload.name = "audio.wav"
        language = getattr(request, "language", None) or audio_source.language
        call_kwargs: dict[str, Any] = {
            "model": self.adapter.model,
            "file": payload,
        }
        if language:
            call_kwargs["language"] = language

        try:
            response = client.audio.transcriptions.create(**call_kwargs)
        except Exception as exc:
            return self._provider_failure(
                exc,
                policy=policy,
                audio_bytes_read=len(audio_bytes),
            )
        finally:
            payload.close()

        if isinstance(response, str):
            transcript = response.strip()
            response_language = None
        else:
            text_value = self._response_value(response, "text")
            transcript = (
                str(text_value).strip()
                if text_value is not None
                else ""
            )
            response_language = self._response_value(response, "language")

        if not transcript:
            return VoiceInputResult(
                outcome=VoiceInputOutcome.NO_INPUT,
                public_error_code=VoiceInputErrorCode.NO_INPUT,
                safe_message="OpenAI transcription returned no transcript.",
                retryable=False,
                public_metadata=self._metadata(
                    status=OpenAIVoiceInputRealProviderStatus.NO_TRANSCRIPT,
                    policy=policy,
                    audio_bytes_read=len(audio_bytes),
                    sdk_imported=True,
                    client_created=True,
                    provider_protocol_call_executed=True,
                ),
            )

        return VoiceInputResult.completed(
            transcript,
            language=(
                str(response_language)
                if response_language is not None
                else language
            ),
            duration_ms=audio_source.ref.audio_format.duration_ms,
            public_metadata=self._metadata(
                status=OpenAIVoiceInputRealProviderStatus.COMPLETED,
                policy=policy,
                audio_bytes_read=len(audio_bytes),
                sdk_imported=True,
                client_created=True,
                provider_protocol_call_executed=True,
            ),
        )
