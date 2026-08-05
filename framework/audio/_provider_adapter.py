"""Lazy internal provider adapters for public voice output sessions.

This module is intentionally private. It may know about provider selection and
runtime settings, but it must not import provider SDKs or legacy local playback
engines at module import time. Public app integrations should continue to use
``framework.create_voice_output_session`` and provider-neutral request/result
models from ``framework.audio.voice_output``.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

if TYPE_CHECKING:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult


_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
_DISABLED_PROVIDER_VALUES = {"", "none", "mock", "unavailable", "disabled"}
_SUPPORTED_PROVIDER_VALUES = {"elevenlabs"}

_REAL_TTS_ENV = "FRAMEWORK_VOICE_OUTPUT_REAL_TTS"
_PROVIDER_ENV = "FRAMEWORK_VOICE_OUTPUT_PROVIDER"
_ARTIFACT_DIR_ENV = "FRAMEWORK_VOICE_OUTPUT_ARTIFACT_DIR"
_PROVIDER_EXECUTION_ENV = "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"


@dataclass(frozen=True)
class VoiceOutputProviderStatus:
    """Internal provider state summarized for public-safe session info."""

    real_tts_enabled: bool
    provider_configured: bool
    provider_execution_allowed: bool
    supports_audio_artifact_ref: bool
    supports_audio_url: bool
    status: str
    status_reason: str


class VoiceOutputProviderAdapter(Protocol):
    """Internal adapter protocol used by the public voice output boundary."""

    def synthesize(self, request: "VoiceOutputRequest") -> "VoiceOutputResult":
        """Return a provider-neutral public result for one request."""


def resolve_provider_status(
    *,
    real_tts_enabled: bool | None = None,
) -> VoiceOutputProviderStatus:
    """Resolve public-safe provider state without importing provider SDKs."""

    enabled = _resolve_real_tts_enabled(real_tts_enabled)
    provider_key = _resolve_provider_key()
    provider_execution_allowed = _resolve_provider_execution_allowed()

    if not enabled:
        return VoiceOutputProviderStatus(
            real_tts_enabled=False,
            provider_configured=False,
            provider_execution_allowed=False,
            supports_audio_artifact_ref=False,
            supports_audio_url=False,
            status="contract_ready",
            status_reason=(
                "Real TTS is disabled. Set FRAMEWORK_VOICE_OUTPUT_REAL_TTS=1 "
                "and configure a FW-owned provider to enable synthesis."
            ),
        )

    if provider_key in _DISABLED_PROVIDER_VALUES:
        return VoiceOutputProviderStatus(
            real_tts_enabled=True,
            provider_configured=False,
            provider_execution_allowed=provider_execution_allowed,
            supports_audio_artifact_ref=False,
            supports_audio_url=False,
            status="unavailable",
            status_reason=(
                "Real TTS was requested, but no FW-owned voice output provider "
                "is configured."
            ),
        )

    if provider_key not in _SUPPORTED_PROVIDER_VALUES:
        return VoiceOutputProviderStatus(
            real_tts_enabled=True,
            provider_configured=False,
            provider_execution_allowed=provider_execution_allowed,
            supports_audio_artifact_ref=False,
            supports_audio_url=False,
            status="unavailable",
            status_reason=(
                "The configured FW-owned voice output provider is not supported "
                "by this v5 boundary yet."
            ),
        )

    if not provider_execution_allowed:
        return VoiceOutputProviderStatus(
            real_tts_enabled=True,
            provider_configured=True,
            provider_execution_allowed=False,
            supports_audio_artifact_ref=True,
            supports_audio_url=False,
            status="execution_guarded",
            status_reason=(
                "A FW-owned voice output provider is configured, but real "
                "provider execution is disabled by the FW execution guard."
            ),
        )

    return VoiceOutputProviderStatus(
        real_tts_enabled=True,
        provider_configured=True,
        provider_execution_allowed=True,
        supports_audio_artifact_ref=True,
        supports_audio_url=False,
        status="provider_configured",
        status_reason=(
            "A FW-owned voice output provider is configured and real provider "
            "execution was explicitly allowed. Provider details remain hidden "
            "from the public app contract."
        ),
    )


def create_voice_output_adapter(
    *,
    real_tts_enabled: bool | None,
    project_root: Path | None,
    artifact_dir: str | Path | None = None,
) -> VoiceOutputProviderAdapter:
    """Create an internal adapter without importing provider SDKs eagerly."""

    status = resolve_provider_status(real_tts_enabled=real_tts_enabled)
    provider_key = _resolve_provider_key()

    if not status.real_tts_enabled or not status.provider_configured:
        return UnavailableVoiceOutputAdapter(status=status)

    if provider_key == "elevenlabs":
        return ElevenLabsVoiceOutputAdapter(
            project_root=project_root,
            artifact_dir=artifact_dir,
        )

    return UnavailableVoiceOutputAdapter(status=status)


class UnavailableVoiceOutputAdapter:
    """Safe adapter used when real TTS is disabled or unavailable."""

    def __init__(self, *, status: VoiceOutputProviderStatus) -> None:
        self._status = status

    def synthesize(self, request: "VoiceOutputRequest") -> "VoiceOutputResult":
        from framework.audio.voice_output import VoiceOutputResult

        return VoiceOutputResult(
            request_state="unavailable",
            audio_ready=False,
            audio_format=_normalize_audio_format(request.requested_audio_format),
            message=self._status.status_reason,
            public_metadata={
                "boundary": "voice_output",
                "voice_profile_id": request.voice_profile_id,
                "provider_details_exposed": "false",
                "provider_status": self._status.status,
            },
        )


class ElevenLabsVoiceOutputAdapter:
    """Internal ElevenLabs adapter loaded only during explicit real synthesis."""

    def __init__(
        self,
        *,
        project_root: Path | None,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._project_root = project_root
        self._artifact_dir = Path(artifact_dir).expanduser() if artifact_dir is not None else None

    def synthesize(self, request: "VoiceOutputRequest") -> "VoiceOutputResult":
        from framework.audio.voice_output import VoiceOutputResult

        audio_format = _normalize_audio_format(request.requested_audio_format)
        if audio_format != "mp3":
            return VoiceOutputResult(
                request_state="rejected",
                audio_ready=False,
                audio_format=audio_format,
                message="The current voice output adapter supports mp3 artifacts only.",
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "unsupported_audio_format",
                    "voice_profile_id": request.voice_profile_id,
                    "provider_details_exposed": "false",
                },
            )

        if not _resolve_provider_execution_allowed():
            return VoiceOutputResult(
                request_state="skipped",
                audio_ready=False,
                audio_format=audio_format,
                message=(
                    "Real provider execution is disabled by the FW execution guard. "
                    "Set FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1 only for "
                    "an explicit configured real TTS run."
                ),
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "provider_execution_guard_disabled",
                    "voice_profile_id": request.voice_profile_id,
                    "provider_details_exposed": "false",
                    "provider_status": "execution_guarded",
                },
            )

        try:
            # Settings validation remains inside the explicit real synthesis path.
            # This keeps import framework/session creation safe without API keys.
            from config.calibration import (  # noqa: PLC0415
                SIMILARITY_BOOST,
                VOICE_STABILITY,
                VOICE_STYLE,
            )
            from config.settings import (  # noqa: PLC0415
                ELEVENLABS_API_KEY,
                TTS_MODEL_ID,
                VOICE_ID,
                require_tts_settings,
            )

            require_tts_settings()
        except Exception as exc:
            return VoiceOutputResult(
                request_state="unavailable",
                audio_ready=False,
                audio_format=audio_format,
                message="Voice output provider settings are not configured for real TTS.",
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "provider_settings_unavailable",
                    "error_type": type(exc).__name__,
                    "voice_profile_id": request.voice_profile_id,
                    "provider_details_exposed": "false",
                },
            )

        try:
            # The provider SDK import is deliberately lazy and below settings
            # validation, so mock-safe checks do not load ElevenLabs at all.
            from elevenlabs.client import ElevenLabs  # noqa: PLC0415
        except Exception as exc:
            return VoiceOutputResult(
                request_state="unavailable",
                audio_ready=False,
                audio_format=audio_format,
                message="Voice output provider SDK is not available in this environment.",
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "provider_sdk_unavailable",
                    "error_type": type(exc).__name__,
                    "voice_profile_id": request.voice_profile_id,
                    "provider_details_exposed": "false",
                },
            )

        try:
            artifact_path = self._build_artifact_path(audio_format)
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            audio = client.text_to_speech.convert(
                voice_id=VOICE_ID,
                text=request.text,
                model_id=TTS_MODEL_ID,
                voice_settings={
                    "stability": VOICE_STABILITY,
                    "similarity_boost": SIMILARITY_BOOST,
                    "style": VOICE_STYLE,
                    "use_speaker_boost": True,
                },
            )

            with artifact_path.open("wb") as file:
                for chunk in audio:
                    if chunk:
                        file.write(chunk)
        except Exception as exc:
            return VoiceOutputResult(
                request_state="failed",
                audio_ready=False,
                audio_format=audio_format,
                message="Voice output generation failed inside the FW provider boundary.",
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "provider_generation_failed",
                    "error_type": type(exc).__name__,
                    "voice_profile_id": request.voice_profile_id,
                    "provider_details_exposed": "false",
                },
            )

        return VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_format=audio_format,
            audio_artifact_ref=str(artifact_path),
            message="Voice output audio artifact was generated by the FW provider boundary.",
            public_metadata={
                "boundary": "voice_output",
                "voice_profile_id": request.voice_profile_id,
                "provider_details_exposed": "false",
                "artifact_kind": "file",
            },
        )

    def _build_artifact_path(self, audio_format: str) -> Path:
        artifact_dir = self._resolve_artifact_dir()
        artifact_dir.mkdir(parents=True, exist_ok=True)
        filename = f"voice_output_{int(time.time() * 1000)}_{uuid4().hex[:8]}.{audio_format}"
        return artifact_dir / filename

    def _resolve_artifact_dir(self) -> Path:
        if self._artifact_dir is not None:
            return self._artifact_dir

        env_dir = os.getenv(_ARTIFACT_DIR_ENV, "").strip()
        if env_dir:
            return Path(env_dir).expanduser()

        if self._project_root is not None:
            return self._project_root / "temp" / "voice_output"

        return Path(tempfile.gettempdir()) / "ai-character-framework" / "voice_output"


def _resolve_real_tts_enabled(value: bool | None) -> bool:
    if value is not None:
        return bool(value)

    return os.getenv(_REAL_TTS_ENV, "").strip().lower() in _TRUE_VALUES


def _resolve_provider_key() -> str:
    return os.getenv(_PROVIDER_ENV, "").strip().lower()


def _resolve_provider_execution_allowed() -> bool:
    return os.getenv(_PROVIDER_EXECUTION_ENV, "").strip().lower() in _TRUE_VALUES


def _normalize_audio_format(value: str | None) -> str:
    normalized = (value or "mp3").strip().lower().lstrip(".")
    return normalized or "mp3"
