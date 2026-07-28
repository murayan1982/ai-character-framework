"""Bounded FILE_PATH reader and marked-fake OpenAI execution boundary.

REQ-3 may read a bounded host-provided audio file and invoke the structural
`client.audio.transcriptions.create(...)` method only on a directly injected
client that inherits `OpenAIVoiceInputFakeClientMarker`.

It does not import the OpenAI SDK, resolve or invoke client factories, inspect
credential values, access microphones, or execute a real provider client.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from .openai_voice_input_provider_adapter import (
    OpenAIVoiceInputProviderAdapter,
)
from .voice_input import (
    VoiceInputErrorCode,
    VoiceInputOutcome,
    VoiceInputRequest,
    VoiceInputResult,
)
from .voice_input_audio import VoiceInputAudioSource


class OpenAIVoiceInputFakeClientMarker:
    """Nominal marker required for REQ-3 fake-client execution."""

    __slots__ = ()
    ai_character_framework_fake_stt_client = True


class OpenAIVoiceInputFakeExecutionStatus(str, Enum):
    """Typed outcomes for the REQ-3 bounded fake execution boundary."""

    FAKE_EXECUTION_NOT_ALLOWED = "fake_execution_not_allowed"
    ADAPTER_NOT_READY = "adapter_not_ready"
    DIRECT_CLIENT_REQUIRED = "direct_client_required"
    CLIENT_NOT_MARKED_FAKE = "client_not_marked_fake"
    AUDIO_PATH_NOT_FOUND = "audio_path_not_found"
    AUDIO_SOURCE_NOT_REGULAR_FILE = "audio_source_not_regular_file"
    AUDIO_TOO_LARGE = "audio_too_large"
    AUDIO_READ_FAILED = "audio_read_failed"
    FAKE_PROVIDER_ERROR = "fake_provider_error"
    NO_TRANSCRIPT = "no_transcript"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class OpenAIVoiceInputFakeExecutionPolicy:
    """Explicit host policy for bounded fake-client execution."""

    max_audio_bytes: int
    allow_fake_client_execution: bool = False

    def __post_init__(self) -> None:
        if self.max_audio_bytes <= 0:
            raise ValueError("max_audio_bytes must be positive")


@dataclass(frozen=True)
class OpenAIVoiceInputFakeExecutor:
    """Execute a bounded audio handoff against a marked fake client only."""

    adapter: OpenAIVoiceInputProviderAdapter
    policy: OpenAIVoiceInputFakeExecutionPolicy

    @staticmethod
    def _response_value(response: Any, key: str) -> Any:
        if isinstance(response, Mapping):
            return response.get(key)
        return getattr(response, key, None)

    def _metadata(
        self,
        *,
        status: OpenAIVoiceInputFakeExecutionStatus,
        audio_bytes_read: int = 0,
        fake_protocol_call_executed: bool = False,
    ) -> dict[str, Any]:
        return {
            "provider": "openai",
            "fake_execution_status": status.value,
            "fake_client_marker_required": True,
            "fake_client_execution_allowed": (
                self.policy.allow_fake_client_execution
            ),
            "max_audio_bytes": self.policy.max_audio_bytes,
            "audio_bytes_read": audio_bytes_read,
            "fake_provider_protocol_call_executed": (
                fake_protocol_call_executed
            ),
            "client_factory_invoked": False,
            "provider_sdk_imported": False,
            "provider_client_created": False,
            "credential_values_read": False,
            "real_provider_execution_executed": False,
            "audio_path_exposed": False,
            "raw_audio_exposed": False,
            "provider_payload_exposed": False,
            "microphone_accessed": False,
        }

    def _unavailable(
        self,
        status: OpenAIVoiceInputFakeExecutionStatus,
        safe_message: str,
        *,
        audio_bytes_read: int = 0,
    ) -> VoiceInputResult:
        return VoiceInputResult.unavailable(
            safe_message=safe_message,
            retryable=False,
            public_metadata=self._metadata(
                status=status,
                audio_bytes_read=audio_bytes_read,
            ),
        )

    def execute(
        self,
        *,
        audio_source: VoiceInputAudioSource,
        request: VoiceInputRequest | None = None,
    ) -> VoiceInputResult:
        """Read at most max_audio_bytes and invoke only a marked fake client."""

        if not self.policy.allow_fake_client_execution:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus
                .FAKE_EXECUTION_NOT_ALLOWED,
                "Fake STT execution requires explicit host-controlled opt-in.",
            )

        contract = self.adapter.preflight_contract(
            audio_source=audio_source,
        )
        if not contract.is_ready:
            result = self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.ADAPTER_NOT_READY,
                contract.safe_message,
            )
            metadata = dict(result.public_metadata)
            metadata["adapter_guard"] = contract.status.value
            return VoiceInputResult.unavailable(
                safe_message=result.safe_message,
                retryable=False,
                public_metadata=metadata,
            )

        if self.adapter.client is None:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.DIRECT_CLIENT_REQUIRED,
                (
                    "REQ-3 requires a directly injected fake client; "
                    "client factories remain disabled."
                ),
            )

        if not isinstance(
            self.adapter.client,
            OpenAIVoiceInputFakeClientMarker,
        ):
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.CLIENT_NOT_MARKED_FAKE,
                (
                    "REQ-3 refuses clients that do not inherit "
                    "OpenAIVoiceInputFakeClientMarker."
                ),
            )

        path = Path(audio_source.ref.value)
        try:
            file_status = path.lstat()
        except FileNotFoundError:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.AUDIO_PATH_NOT_FOUND,
                "The host-provided audio file was not found.",
            )
        except OSError:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.AUDIO_READ_FAILED,
                "The host-provided audio file could not be inspected.",
            )

        if not stat.S_ISREG(file_status.st_mode):
            return self._unavailable(
                (
                    OpenAIVoiceInputFakeExecutionStatus
                    .AUDIO_SOURCE_NOT_REGULAR_FILE
                ),
                "The host-provided audio source must be a regular file.",
            )

        if file_status.st_size > self.policy.max_audio_bytes:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.AUDIO_TOO_LARGE,
                "The host-provided audio file exceeds the configured byte bound.",
            )

        try:
            with path.open("rb") as handle:
                audio_bytes = handle.read(
                    self.policy.max_audio_bytes + 1
                )
        except OSError:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.AUDIO_READ_FAILED,
                "The host-provided audio file could not be read.",
            )

        if len(audio_bytes) > self.policy.max_audio_bytes:
            return self._unavailable(
                OpenAIVoiceInputFakeExecutionStatus.AUDIO_TOO_LARGE,
                "The host-provided audio file exceeded the byte bound while reading.",
                audio_bytes_read=self.policy.max_audio_bytes,
            )

        payload = BytesIO(audio_bytes)
        payload.name = "audio.wav"

        language = (
            getattr(request, "language", None)
            or audio_source.language
        )
        call_kwargs: dict[str, Any] = {
            "model": self.adapter.model,
            "file": payload,
        }
        if language:
            call_kwargs["language"] = language

        try:
            response = (
                self.adapter.client
                .audio
                .transcriptions
                .create(**call_kwargs)
            )
        except Exception:
            return VoiceInputResult.failed(
                public_error_code=VoiceInputErrorCode.PROVIDER_ERROR,
                safe_message="The injected fake STT client failed.",
                retryable=False,
                public_metadata=self._metadata(
                    status=(
                        OpenAIVoiceInputFakeExecutionStatus
                        .FAKE_PROVIDER_ERROR
                    ),
                    audio_bytes_read=len(audio_bytes),
                    fake_protocol_call_executed=True,
                ),
            )
        finally:
            payload.close()

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
                safe_message="The injected fake STT client returned no transcript.",
                retryable=False,
                public_metadata=self._metadata(
                    status=(
                        OpenAIVoiceInputFakeExecutionStatus.NO_TRANSCRIPT
                    ),
                    audio_bytes_read=len(audio_bytes),
                    fake_protocol_call_executed=True,
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
                status=OpenAIVoiceInputFakeExecutionStatus.COMPLETED,
                audio_bytes_read=len(audio_bytes),
                fake_protocol_call_executed=True,
            ),
        )
