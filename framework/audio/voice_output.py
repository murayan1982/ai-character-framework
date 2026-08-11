"""Public voice output session contract.

This module intentionally avoids importing provider-specific TTS implementations.
It defines the app-facing voice output boundary used by host applications such
as Daily Rhythm Companion while keeping real provider work behind lazy internal
adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

from ..version import VOICE_OUTPUT_BOUNDARY_VERSION

if TYPE_CHECKING:
    from ..session_close import SessionCloseResult


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
class VoiceArtifactRef:
    """Opaque public reference to a FW-owned voice artifact.

    Host apps may store or resolve this reference through FW-approved artifact
    handling, but must not treat it as a local filesystem path or provider
    object. The identifier is deliberately opaque and provider-neutral.
    """

    artifact_id: str
    artifact_kind: str = "audio"
    audio_format: str | None = None
    content_type: str | None = None
    expires_at: str | None = None
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        artifact_id = self.artifact_id
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            raise ValueError("VoiceArtifactRef.artifact_id must be a non-empty opaque string")
        if _looks_like_private_path(artifact_id):
            raise ValueError("VoiceArtifactRef.artifact_id must not expose a local/private path")
        if self.artifact_kind != "audio":
            raise ValueError("VoiceArtifactRef.artifact_kind must be 'audio'")

    @classmethod
    def from_id(
        cls,
        artifact_id: str,
        *,
        audio_format: str | None = None,
        content_type: str | None = None,
        expires_at: str | None = None,
        public_metadata: Mapping[str, str] | None = None,
    ) -> "VoiceArtifactRef":
        """Create an opaque voice artifact reference from a FW-owned ID."""

        return cls(
            artifact_id=artifact_id,
            audio_format=audio_format,
            content_type=content_type,
            expires_at=expires_at,
            public_metadata=dict(public_metadata or {}),
        )

    def to_public_dict(self) -> dict[str, object]:
        """Return a provider-neutral, secret-free public representation."""

        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "audio_format": self.audio_format,
            "content_type": self.content_type,
            "expires_at": self.expires_at,
            "public_metadata": dict(self.public_metadata),
        }

    def __str__(self) -> str:
        """Return the opaque artifact identifier, never a filesystem path."""

        return self.artifact_id


def _looks_like_private_path(value: str) -> bool:
    normalized = value.strip()
    if "\\" in normalized or "/" in normalized:
        return True
    if len(normalized) >= 2 and normalized[1] == ":":
        return True
    lowered = normalized.lower()
    private_tokens = ("api_key", "secret", "token", "elevenlabs", "openai")
    return any(token in lowered for token in private_tokens)


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
    audio_artifact_ref: VoiceArtifactRef | None = None
    message: str = ""
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.audio_artifact_ref is not None and not isinstance(
            self.audio_artifact_ref, VoiceArtifactRef
        ):
            raise TypeError(
                "VoiceOutputResult.audio_artifact_ref must be a VoiceArtifactRef or None"
            )

        has_url = bool(self.audio_url)
        has_artifact_ref = self.audio_artifact_ref is not None
        handoff_count = int(has_url) + int(has_artifact_ref)

        if self.request_state == "generated":
            if not self.audio_ready:
                raise ValueError("generated voice output must be audio-ready")
            if handoff_count != 1:
                raise ValueError(
                    "generated voice output must expose exactly one audio handoff"
                )
        else:
            if self.audio_ready:
                raise ValueError("non-generated voice output must not be audio-ready")
            if handoff_count:
                raise ValueError(
                    "non-generated voice output must not expose an audio handoff"
                )

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
    boundary_version: str = VOICE_OUTPUT_BOUNDARY_VERSION
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
    ``create_output()``.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        default_voice_profile_id: str = "default",
        real_tts_enabled: bool | None = None,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._project_root = (
            Path(project_root).resolve() if project_root is not None else None
        )
        self._default_voice_profile_id = default_voice_profile_id
        self._real_tts_enabled = real_tts_enabled
        self._artifact_dir = artifact_dir
        self._fw_public_closed = False
        self._last_close_result: SessionCloseResult | None = None

    def info(self) -> VoiceOutputSessionInfo:
        """Return app-safe metadata without provider-specific details."""

        from framework.audio._provider_adapter import resolve_provider_status

        provider_status = resolve_provider_status(
            real_tts_enabled=self._real_tts_enabled
        )
        return VoiceOutputSessionInfo(
            real_tts_enabled=provider_status.real_tts_enabled,
            provider_configured=provider_status.provider_configured,
            supports_audio_url=provider_status.supports_audio_url,
            supports_audio_artifact_ref=provider_status.supports_audio_artifact_ref,
            default_voice_profile_id=self._default_voice_profile_id,
            project_root=(
                str(self._project_root)
                if self._project_root is not None
                else None
            ),
            status=provider_status.status,
            status_reason=provider_status.status_reason,
        )

    @property
    def is_closed(self) -> bool:
        """Whether this public voice output session has been closed."""

        return self._fw_public_closed

    @property
    def last_close_result(self) -> SessionCloseResult | None:
        """Return the latest immutable close observation."""

        return self._last_close_result

    def close(self) -> None:
        """Close the public voice output session idempotently."""

        from ..session_close import (
            SessionCloseResult,
            _runtime_close_result,
            build_session_close_plan,
        )

        if self._fw_public_closed:
            self._last_close_result = SessionCloseResult.already_closed(
                public_metadata={"boundary": "voice_output"}
            )
            return
        self._fw_public_closed = True
        plan = build_session_close_plan(
            public_metadata={"boundary": "voice_output"}
        )
        self._last_close_result = _runtime_close_result(
            plan,
            public_metadata={"boundary": "voice_output"},
        )

    def dispose(self) -> None:
        """Compatibility alias for ``close()``."""

        self.close()

    def __enter__(self) -> "VoiceOutputSession":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False

    def speak(self, request: VoiceOutputRequest) -> VoiceOutputResult:
        """Create voice output using the stable host-app method name.

        ``speak`` is the preferred v5.1+ public method for host apps.
        ``create_output`` remains available as a v5.0 compatibility method.
        """

        return self.create_output(request)

    def create_output(self, request: VoiceOutputRequest | str) -> VoiceOutputResult:
        """Create a voice output artifact when a provider is available.

        The default behavior remains mock-safe unavailable. When real TTS is
        explicitly enabled and configured in FW-owned settings, this method
        delegates to a lazy internal provider adapter without exposing provider
        details through the public request/result contract.
        """

        if self.is_closed:
            return _voice_output_closed_result(request)

        normalized = _normalize_request(
            request,
            default_voice_profile_id=self._default_voice_profile_id,
        )

        if not normalized.text.strip():
            return VoiceOutputResult(
                request_state="rejected",
                audio_ready=False,
                audio_format=_normalize_audio_format(
                    normalized.requested_audio_format
                ),
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

def _voice_output_request_audio_format(request: object) -> str | None:
    value = getattr(request, "requested_audio_format", None)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _voice_output_closed_result(request: object) -> VoiceOutputResult:
    """Return a provider-neutral result for a closed voice output session."""

    kwargs = {
        "request_state": "failed",
        "audio_ready": False,
        "audio_format": _voice_output_request_audio_format(request),
        "audio_url": None,
        "audio_artifact_ref": None,
        "message": "Voice output session is closed.",
        "public_metadata": {
            "boundary": "voice_output",
            "public_error_code": "session_closed",
        },
    }
    try:
        return VoiceOutputResult(**kwargs)
    except TypeError as first_error:
        fallback_kwargs = dict(kwargs)
        fallback_kwargs["public_message"] = fallback_kwargs.pop("message")
        try:
            return VoiceOutputResult(**fallback_kwargs)
        except TypeError:
            raise first_error

