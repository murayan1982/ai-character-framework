"""Public voice output session contract.

This module intentionally avoids importing provider-specific TTS implementations.
It defines the app-facing voice output boundary used by host applications such
as Daily Rhythm Companion while keeping real provider work behind lazy internal
adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class VoiceOutputRequest:
    """Provider-neutral voice output request.

    Host apps should pass framework-level voice profile IDs and generic audio
    preferences. Provider voice IDs, API keys, model IDs, and provider-specific
    options remain framework responsibilities.
    """

    text: str
    voice_profile_id: str = "default"
    requested_audio_format: str | None = None
    utterance_purpose: str | None = None
    language_code: str | None = None


@dataclass(frozen=True)
class VoiceOutputResult:
    """Provider-neutral voice output result.

    The public result never exposes provider voice IDs, API keys, model IDs, or
    provider-specific request settings. Real provider execution, when explicitly
    enabled, returns a Web-app-friendly handoff through either ``audio_url`` or
    ``audio_artifact_ref`` instead of local playback side effects.

    Contract summary:

    - ``audio_ready=False`` means host apps must not try to play audio.
    - ``audio_ready=True`` is valid only for generated output with one handoff.
    - ``audio_url`` is for app-consumable URLs when FW hosts or signs audio.
    - ``audio_artifact_ref`` is an opaque FW-owned artifact reference.
    """

    request_state: str
    audio_ready: bool = False
    audio_format: str | None = None
    audio_url: str | None = None
    audio_artifact_ref: str | None = None
    message: str = ""
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def has_audio_handoff(self) -> bool:
        """Return whether the result includes one app-consumable audio handoff."""

        return self.audio_handoff_kind in {"audio_url", "audio_artifact_ref"}

    @property
    def audio_handoff_kind(self) -> str:
        """Classify the public audio handoff without exposing provider details.

        Possible values are ``none``, ``audio_url``, ``audio_artifact_ref``, and
        ``multiple``. Host apps should treat ``multiple`` as invalid for current
        v5.0.0 Web handoff usage.
        """

        has_url = bool(self.audio_url)
        has_artifact_ref = bool(self.audio_artifact_ref)

        if has_url and has_artifact_ref:
            return "multiple"
        if has_url:
            return "audio_url"
        if has_artifact_ref:
            return "audio_artifact_ref"
        return "none"

    @property
    def is_generated(self) -> bool:
        """Return whether the result represents generated, playable audio."""

        return self.request_state == "generated" and self.audio_ready


@dataclass(frozen=True)
class VoiceOutputSessionInfo:
    """Public, app-safe metadata for a voice output session."""

    session_type: str = "voice_output"
    boundary_version: str = "v5.lazy_provider_adapter"
    supports_voice_output: bool = True
    real_tts_enabled: bool = False
    provider_configured: bool = False
    provider_details_exposed: bool = False
    supports_audio_url: bool = False
    supports_audio_artifact_ref: bool = False
    default_voice_profile_id: str = "default"
    project_root: str | None = None
    status: str = "contract_ready"
    status_reason: str = "Real TTS is disabled or no FW-owned provider is configured."


class VoiceOutputSession:
    """Public voice output session boundary.

    Importing and constructing this session does not import ElevenLabs, OpenAI
    TTS, ffplay/runtime audio, VTS, or legacy local playback implementations.
    Provider resolution happens lazily when app code explicitly calls
    create_output().
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        default_voice_profile_id: str = "default",
        real_tts_enabled: bool | None = None,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._default_voice_profile_id = default_voice_profile_id
        self._real_tts_enabled = real_tts_enabled
        self._artifact_dir = artifact_dir

    def info(self) -> VoiceOutputSessionInfo:
        """Return app-safe metadata without provider-specific details."""

        from framework.audio._provider_adapter import resolve_provider_status

        provider_status = resolve_provider_status(real_tts_enabled=self._real_tts_enabled)
        return VoiceOutputSessionInfo(
            real_tts_enabled=provider_status.real_tts_enabled,
            provider_configured=provider_status.provider_configured,
            supports_audio_url=provider_status.supports_audio_url,
            supports_audio_artifact_ref=provider_status.supports_audio_artifact_ref,
            default_voice_profile_id=self._default_voice_profile_id,
            project_root=str(self._project_root) if self._project_root is not None else None,
            status=provider_status.status,
            status_reason=provider_status.status_reason,
        )

    def create_output(self, request: VoiceOutputRequest | str) -> VoiceOutputResult:
        """Create a voice output artifact when a provider is available.

        The default behavior remains mock-safe unavailable. When real TTS is
        explicitly enabled and configured in FW-owned settings, this method
        delegates to a lazy internal provider adapter without exposing provider
        details through the public request/result contract.
        """

        normalized = _normalize_request(
            request,
            default_voice_profile_id=self._default_voice_profile_id,
        )

        if not normalized.text.strip():
            return VoiceOutputResult(
                request_state="rejected",
                audio_ready=False,
                audio_format=_normalize_audio_format(normalized.requested_audio_format),
                message="Voice output text is empty.",
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "empty_text",
                },
            )

        from framework.audio._provider_adapter import create_voice_output_adapter

        adapter = create_voice_output_adapter(
            real_tts_enabled=self._real_tts_enabled,
            project_root=self._project_root,
            artifact_dir=self._artifact_dir,
        )
        return adapter.synthesize(normalized)

    def close(self) -> None:
        """Close the public session boundary.

        The lazy adapter implementation currently creates per-request provider
        clients and does not keep public session resources alive.
        """

        return None


# Alias kept small and readable for app code that thinks in terms of synthesis.
VoiceSynthesisRequest = VoiceOutputRequest
VoiceSynthesisResult = VoiceOutputResult


def create_voice_output_session(
    *,
    project_root: str | Path | None = None,
    default_voice_profile_id: str = "default",
    real_tts_enabled: bool | None = None,
    artifact_dir: str | Path | None = None,
) -> VoiceOutputSession:
    """Create a provider-neutral voice output session.

    This factory is safe to call without TTS API keys. Provider SDK imports and
    settings validation are delayed until explicit create_output() execution
    with real TTS enabled.
    """

    return VoiceOutputSession(
        project_root=project_root,
        default_voice_profile_id=default_voice_profile_id,
        real_tts_enabled=real_tts_enabled,
        artifact_dir=artifact_dir,
    )


def _normalize_request(
    request: VoiceOutputRequest | str,
    *,
    default_voice_profile_id: str,
) -> VoiceOutputRequest:
    if isinstance(request, VoiceOutputRequest):
        return request

    return VoiceOutputRequest(
        text=str(request),
        voice_profile_id=default_voice_profile_id,
    )


def _normalize_audio_format(value: str | None) -> str:
    normalized = (value or "mp3").strip().lower().lstrip(".")
    return normalized or "mp3"


__all__ = [
    "VoiceOutputRequest",
    "VoiceOutputResult",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceSynthesisRequest",
    "VoiceSynthesisResult",
    "create_voice_output_session",
]
