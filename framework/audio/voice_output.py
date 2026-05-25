"""Public voice output session contract.

This module intentionally avoids importing provider-specific TTS implementations.
It defines the app-facing voice output boundary used by host applications such
as Daily Rhythm Companion while keeping real provider work behind future lazy
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

    The initial v5 contract is mock-safe and returns a safe unavailable result
    until a real provider adapter is explicitly configured in a later commit.
    """

    request_state: str
    audio_ready: bool = False
    audio_format: str | None = None
    audio_url: str | None = None
    audio_artifact_ref: str | None = None
    message: str = ""
    public_metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class VoiceOutputSessionInfo:
    """Public, app-safe metadata for a voice output session."""

    session_type: str = "voice_output"
    boundary_version: str = "v5.contract"
    supports_voice_output: bool = True
    real_tts_enabled: bool = False
    provider_configured: bool = False
    provider_details_exposed: bool = False
    supports_audio_url: bool = False
    supports_audio_artifact_ref: bool = False
    default_voice_profile_id: str = "default"
    project_root: str | None = None
    status: str = "contract_ready"
    status_reason: str = "Real TTS provider adapters are not configured by this contract-only implementation."


class VoiceOutputSession:
    """Public voice output session boundary.

    This contract-only implementation is deliberately lightweight:
    importing and constructing it must not import ElevenLabs, OpenAI TTS,
    ffplay/runtime audio, VTS, or any provider-specific implementation.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        default_voice_profile_id: str = "default",
    ) -> None:
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._default_voice_profile_id = default_voice_profile_id

    def info(self) -> VoiceOutputSessionInfo:
        """Return app-safe metadata without provider-specific details."""

        return VoiceOutputSessionInfo(
            default_voice_profile_id=self._default_voice_profile_id,
            project_root=str(self._project_root) if self._project_root is not None else None,
        )

    def create_output(self, request: VoiceOutputRequest | str) -> VoiceOutputResult:
        """Create a voice output artifact when a provider is available.

        Commit 2 only establishes the public contract, so this method returns a
        safe unavailable result instead of importing or invoking any real TTS
        provider. A later v5 commit can replace this body with a lazy adapter
        call while preserving the public request/result shape.
        """

        normalized = _normalize_request(
            request,
            default_voice_profile_id=self._default_voice_profile_id,
        )

        if not normalized.text.strip():
            return VoiceOutputResult(
                request_state="rejected",
                audio_ready=False,
                message="Voice output text is empty.",
                public_metadata={
                    "boundary": "voice_output",
                    "reason": "empty_text",
                },
            )

        return VoiceOutputResult(
            request_state="unavailable",
            audio_ready=False,
            audio_format=normalized.requested_audio_format,
            message=(
                "Voice output provider is not configured in this contract-only "
                "session. Real TTS will be handled by a lazy provider adapter."
            ),
            public_metadata={
                "boundary": "voice_output",
                "voice_profile_id": normalized.voice_profile_id,
                "provider_details_exposed": "false",
            },
        )

    def close(self) -> None:
        """Close the public session boundary.

        The contract-only implementation has no provider resources to release.
        """

        return None


# Alias kept small and readable for app code that thinks in terms of synthesis.
VoiceSynthesisRequest = VoiceOutputRequest
VoiceSynthesisResult = VoiceOutputResult


def create_voice_output_session(
    *,
    project_root: str | Path | None = None,
    default_voice_profile_id: str = "default",
) -> VoiceOutputSession:
    """Create a provider-neutral voice output session.

    This factory is safe to call without TTS API keys. It must remain free of
    provider imports so host apps can probe framework capability in mock-safe
    environments.
    """

    return VoiceOutputSession(
        project_root=project_root,
        default_voice_profile_id=default_voice_profile_id,
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


__all__ = [
    "VoiceOutputRequest",
    "VoiceOutputResult",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceSynthesisRequest",
    "VoiceSynthesisResult",
    "create_voice_output_session",
]
