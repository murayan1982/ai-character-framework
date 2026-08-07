"""Provider-neutral public capability snapshot for FW host apps.

Importing this module remains provider-safe. The global snapshot reports the
truthful public SDK boundaries and the deterministic mock-safe runtimes that are
available without importing provider SDKs, creating clients, accessing the
network, microphone, playback, VTube Studio, or private configuration values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

from .identity import SessionId
from .realtime_capabilities import (
    CapabilitySnapshotScope,
    RealtimeCapabilitySnapshot,
    RealtimeMotionCapability,
    RealtimeVoiceInputCapability,
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from .version import CAPABILITIES_SCHEMA_VERSION


CapabilityState = Literal[
    "supported",
    "configured",
    "available",
    "blocked",
    "unavailable",
    "fallback",
]


@dataclass(frozen=True, slots=True)
class CapabilityStatus:
    """Provider-neutral status for one public framework capability."""

    name: str
    status: CapabilityState
    supported: bool
    configured: bool
    available: bool
    blocked: bool = False
    reason_code: str | None = None
    safe_message: str | None = None
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        """Whether the capability is currently usable by a host app."""

        return self.available and not self.blocked

    @property
    def is_unavailable(self) -> bool:
        """Whether the capability is not currently usable."""

        return not self.is_available

    def to_public_dict(self) -> dict[str, object]:
        """Return a provider-neutral dictionary representation."""

        return {
            "name": self.name,
            "status": self.status,
            "supported": self.supported,
            "configured": self.configured,
            "available": self.available,
            "blocked": self.blocked,
            "reason_code": self.reason_code,
            "safe_message": self.safe_message,
            "public_metadata": dict(self.public_metadata),
        }


@dataclass(frozen=True, slots=True)
class FrameworkCapabilities:
    """Versioned compatibility snapshot with one detailed v6 global snapshot.

    The five ``CapabilityStatus`` fields and ``schema_version`` retain the v5.1
    public contract. ``realtime_snapshot`` is additive and carries the detailed
    v6 global capability model produced from the same authoritative decisions.
    """

    schema_version: str
    text_chat: CapabilityStatus
    voice_output: CapabilityStatus
    voice_input: CapabilityStatus
    realtime: CapabilityStatus
    motion: CapabilityStatus
    public_metadata: Mapping[str, str] = field(default_factory=dict)
    realtime_snapshot: RealtimeCapabilitySnapshot | None = None

    def to_public_dict(self) -> dict[str, object]:
        """Return a provider-neutral dictionary representation."""

        return {
            "schema_version": self.schema_version,
            "text_chat": self.text_chat.to_public_dict(),
            "voice_output": self.voice_output.to_public_dict(),
            "voice_input": self.voice_input.to_public_dict(),
            "realtime": self.realtime.to_public_dict(),
            "motion": self.motion.to_public_dict(),
            "public_metadata": dict(self.public_metadata),
            "realtime_snapshot": (
                dict(self.realtime_snapshot.as_dict())
                if self.realtime_snapshot is not None
                else None
            ),
        }


def get_capabilities(
    *,
    project_root: str | Path | None = None,
    real_tts_enabled: bool | None = None,
) -> FrameworkCapabilities:
    """Return a mock-safe truthful global capability snapshot.

    This function preserves the v5.1 return type and keyword-only signature. It
    now reports the existing voice-input, realtime, and motion public boundaries
    truthfully instead of claiming that they are missing. The additive detailed
    snapshot distinguishes deterministic fake runtimes from unprobed real
    runtimes and never treats configuration or an open guard as provider success.
    """

    resolved_project_root = (
        Path(project_root).resolve() if project_root is not None else None
    )
    text_chat = _text_chat_capability()
    voice_output = _voice_output_capability(real_tts_enabled=real_tts_enabled)
    voice_input = _mock_fallback_capability(
        "voice_input",
        "mock_voice_input_available",
        (
            "The public voice-input boundary and mock-safe adapter are available; "
            "real STT availability is not claimed."
        ),
    )
    realtime = _mock_fallback_capability(
        "realtime",
        "mock_realtime_available",
        (
            "The public realtime session and deterministic mock runtime are "
            "available; real unified orchestration is not claimed."
        ),
    )
    motion = _mock_fallback_capability(
        "motion",
        "mock_motion_available",
        (
            "The public motion session and mock adapter are available; real "
            "motion transport availability is not claimed."
        ),
    )
    detailed = _global_realtime_snapshot(voice_output=voice_output)

    return FrameworkCapabilities(
        schema_version=CAPABILITIES_SCHEMA_VERSION,
        text_chat=text_chat,
        voice_output=voice_output,
        voice_input=voice_input,
        realtime=realtime,
        motion=motion,
        public_metadata={
            "boundary": "capabilities",
            "project_root_provided": (
                "true" if resolved_project_root is not None else "false"
            ),
            "detailed_realtime_snapshot": "true",
            "snapshot_scope": CapabilitySnapshotScope.GLOBAL.value,
            "provider_execution_performed": "false",
        },
        realtime_snapshot=detailed,
    )


def _text_chat_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="text_chat",
        status="available",
        supported=True,
        configured=True,
        available=True,
        blocked=False,
        reason_code="public_boundary_available",
        safe_message="Text chat public boundary is available.",
        public_metadata={"boundary": "text_chat"},
    )


def _mock_fallback_capability(
    name: str,
    reason_code: str,
    safe_message: str,
) -> CapabilityStatus:
    return CapabilityStatus(
        name=name,
        status="fallback",
        supported=True,
        configured=True,
        available=True,
        blocked=False,
        reason_code=reason_code,
        safe_message=safe_message,
        public_metadata={
            "boundary": name,
            "fake_runtime": "true",
            "real_runtime": "false",
            "provider_execution_performed": "false",
        },
    )


def _voice_output_capability(*, real_tts_enabled: bool | None) -> CapabilityStatus:
    enabled = (
        _env_flag("FRAMEWORK_VOICE_OUTPUT_REAL_TTS")
        if real_tts_enabled is None
        else bool(real_tts_enabled)
    )
    provider_configured = bool(os.environ.get("FRAMEWORK_VOICE_OUTPUT_PROVIDER"))
    execution_allowed = _env_flag(
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"
    )

    metadata = {
        "boundary": "voice_output",
        "real_tts_enabled": str(enabled).lower(),
        "provider_configured": str(provider_configured).lower(),
        "provider_execution_allowed": str(execution_allowed).lower(),
        "provider_details_exposed": "false",
        "provider_execution_performed": "false",
    }

    if not enabled:
        return CapabilityStatus(
            name="voice_output",
            status="unavailable",
            supported=True,
            configured=False,
            available=False,
            blocked=False,
            reason_code="real_tts_disabled",
            safe_message=(
                "Voice output public boundary is available, but real TTS is "
                "disabled."
            ),
            public_metadata=metadata,
        )

    if not provider_configured:
        return CapabilityStatus(
            name="voice_output",
            status="unavailable",
            supported=True,
            configured=False,
            available=False,
            blocked=False,
            reason_code="provider_not_configured",
            safe_message="Voice output provider is not configured.",
            public_metadata=metadata,
        )

    if not execution_allowed:
        return CapabilityStatus(
            name="voice_output",
            status="blocked",
            supported=True,
            configured=True,
            available=False,
            blocked=True,
            reason_code="provider_execution_guarded",
            safe_message="Voice output provider execution is guarded by default.",
            public_metadata=metadata,
        )

    return CapabilityStatus(
        name="voice_output",
        status="configured",
        supported=True,
        configured=True,
        available=False,
        blocked=False,
        reason_code="real_provider_not_probed",
        safe_message=(
            "Voice output provider is configured, but availability was not "
            "probed by the mock-safe capability snapshot."
        ),
        public_metadata=metadata,
    )


def _global_realtime_snapshot(
    *,
    voice_output: CapabilityStatus,
) -> RealtimeCapabilitySnapshot:
    mock_runtime = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=True,
        real_runtime=False,
        unavailable_reason=None,
        public_metadata={
            "snapshot_source": "global_public_boundary",
            "provider_execution_performed": False,
        },
    )
    voice_output_runtime = RuntimeCapabilityState(
        configured=voice_output.configured,
        runtime_available=voice_output.available,
        guarded=voice_output.blocked,
        fake_runtime=False,
        real_runtime=voice_output.available,
        unavailable_reason=(
            None if voice_output.available else voice_output.reason_code
        ),
        public_metadata={
            "snapshot_source": "global_voice_output_preflight",
            "provider_execution_performed": False,
        },
    )

    return RealtimeCapabilitySnapshot(
        session_id=None,
        snapshot_scope=CapabilitySnapshotScope.GLOBAL,
        snapshot_generation=1,
        text_generation=TextGenerationCapability(
            runtime=mock_runtime,
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=False,
            public_metadata={"boundary": "text_generation"},
        ),
        voice_input=RealtimeVoiceInputCapability(
            runtime=mock_runtime,
            audio_chunk_input_supported=False,
            partial_transcript_supported=False,
            final_transcript_supported=True,
            input_abort_supported=False,
            backpressure_supported=False,
            accepted_audio_formats=(
                "wav",
                "m4a",
                "mp3",
                "webm",
                "ogg",
                "flac",
                "pcm16",
            ),
            maximum_chunk_size=None,
            maximum_duration=None,
            public_metadata={
                "boundary": "voice_input",
                "whole_audio_source_supported": True,
                "text_fallback_supported": True,
            },
        ),
        voice_output=RealtimeVoiceOutputCapability(
            runtime=voice_output_runtime,
            streaming_audio_supported=False,
            generation_cancel_supported=False,
            provider_hard_cancel_supported=False,
            pending_flush_supported=False,
            active_audio_invalidation_supported=False,
            audio_formats=(),
            maximum_text_size=None,
            public_metadata={
                "boundary": "voice_output",
                "host_playback_owned": True,
            },
        ),
        motion=RealtimeMotionCapability(
            runtime=mock_runtime,
            request_cancel_supported=False,
            completion_event_supported=True,
            provider_neutral_intent_supported=True,
            public_metadata={"boundary": "motion"},
        ),
        supports_text_chat=True,
        supports_voice_input=True,
        supports_voice_output=True,
        supports_motion=True,
        real_runtime_enabled=False,
        hard_cancel_supported=False,
        tts_queue_flush_supported=False,
        public_metadata={
            "boundary": "realtime_capabilities",
            "snapshot_source": "global_public_boundaries",
            "authoritative_builder": True,
            "provider_execution_performed": False,
            "session_wiring_adopted": False,
        },
    )



def _unavailable_runtime_state(*, reason: str, source: str) -> RuntimeCapabilityState:
    return RuntimeCapabilityState(
        configured=False,
        runtime_available=False,
        guarded=False,
        fake_runtime=False,
        real_runtime=False,
        unavailable_reason=reason,
        public_metadata={
            "snapshot_source": source,
            "provider_execution_performed": False,
        },
    )


def _unavailable_text_generation_capability(*, reason: str) -> TextGenerationCapability:
    return TextGenerationCapability(
        runtime=_unavailable_runtime_state(
            reason=reason,
            source="realtime_session_text_generation_preflight",
        ),
        streaming_supported=False,
        cooperative_cancel_supported=False,
        provider_hard_cancel_supported=False,
        public_metadata={"boundary": "text_generation"},
    )


def _unavailable_voice_input_capability(*, reason: str) -> RealtimeVoiceInputCapability:
    return RealtimeVoiceInputCapability(
        runtime=_unavailable_runtime_state(
            reason=reason,
            source="realtime_session_voice_input_preflight",
        ),
        audio_chunk_input_supported=False,
        partial_transcript_supported=False,
        final_transcript_supported=False,
        input_abort_supported=False,
        backpressure_supported=False,
        accepted_audio_formats=(),
        maximum_chunk_size=None,
        maximum_duration=None,
        public_metadata={"boundary": "voice_input"},
    )


def _unavailable_voice_output_capability(*, reason: str) -> RealtimeVoiceOutputCapability:
    return RealtimeVoiceOutputCapability(
        runtime=_unavailable_runtime_state(
            reason=reason,
            source="realtime_session_voice_output_preflight",
        ),
        streaming_audio_supported=False,
        generation_cancel_supported=False,
        provider_hard_cancel_supported=False,
        pending_flush_supported=False,
        active_audio_invalidation_supported=False,
        audio_formats=(),
        maximum_text_size=None,
        public_metadata={"boundary": "voice_output"},
    )


def _unavailable_motion_capability(*, reason: str) -> RealtimeMotionCapability:
    return RealtimeMotionCapability(
        runtime=_unavailable_runtime_state(
            reason=reason,
            source="realtime_session_motion_preflight",
        ),
        request_cancel_supported=False,
        completion_event_supported=False,
        provider_neutral_intent_supported=False,
        public_metadata={"boundary": "motion"},
    )


def _session_realtime_snapshot(
    *,
    session_id: SessionId | str,
    snapshot_generation: int = 1,
    project_root: str | Path | None = None,
    real_runtime_requested: bool = False,
    stage_capabilities: Mapping[str, object] | None = None,
    failed_stage_kinds: tuple[str, ...] = (),
) -> RealtimeCapabilitySnapshot:
    """Build one immutable truthful session-scoped capability snapshot.

    The default-off mock path preserves the accepted deterministic session
    capability surface. When real runtime composition is explicitly requested,
    only provider-neutral stage preflight results supplied by RealtimeSession are
    projected into the snapshot. This builder never calls a stage or provider.
    """

    resolved_project_root = (
        Path(project_root).resolve() if project_root is not None else None
    )
    normalized_stage_capabilities = dict(stage_capabilities or {})
    normalized_failed_stage_kinds = tuple(failed_stage_kinds)

    expected_capability_types: Mapping[str, type[object]] = {
        "voice_input": RealtimeVoiceInputCapability,
        "text_generation": TextGenerationCapability,
        "voice_output": RealtimeVoiceOutputCapability,
        "motion": RealtimeMotionCapability,
    }
    for stage_kind, capability in normalized_stage_capabilities.items():
        expected = expected_capability_types.get(stage_kind)
        if expected is None:
            raise ValueError("stage_capabilities contains an unknown realtime stage kind")
        if not isinstance(capability, expected):
            raise TypeError(
                f"stage_capabilities[{stage_kind!r}] must be {expected.__name__}"
            )
    for stage_kind in normalized_failed_stage_kinds:
        if stage_kind not in expected_capability_types:
            raise ValueError("failed_stage_kinds contains an unknown realtime stage kind")

    if not real_runtime_requested:
        mock_runtime = RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            guarded=False,
            fake_runtime=True,
            real_runtime=False,
            unavailable_reason=None,
            public_metadata={
                "snapshot_source": "realtime_session_mock_runtime",
                "provider_execution_performed": False,
            },
        )
        motion_runtime = RuntimeCapabilityState(
            configured=False,
            runtime_available=False,
            guarded=False,
            fake_runtime=False,
            real_runtime=False,
            unavailable_reason="not_wired_to_realtime_session",
            public_metadata={
                "snapshot_source": "realtime_session_motion_boundary",
                "provider_execution_performed": False,
            },
        )

        return RealtimeCapabilitySnapshot(
            session_id=session_id,
            snapshot_scope=CapabilitySnapshotScope.SESSION,
            snapshot_generation=snapshot_generation,
            text_generation=TextGenerationCapability(
                runtime=mock_runtime,
                streaming_supported=False,
                cooperative_cancel_supported=False,
                provider_hard_cancel_supported=False,
                public_metadata={
                    "boundary": "text_generation",
                    "session_stage": "mock_response_completed",
                },
            ),
            voice_input=RealtimeVoiceInputCapability(
                runtime=mock_runtime,
                audio_chunk_input_supported=False,
                partial_transcript_supported=False,
                final_transcript_supported=True,
                input_abort_supported=False,
                backpressure_supported=False,
                accepted_audio_formats=(),
                maximum_chunk_size=None,
                maximum_duration=None,
                public_metadata={
                    "boundary": "voice_input",
                    "session_stage": "mock_transcript_final",
                    "host_text_input_supported": True,
                },
            ),
            voice_output=RealtimeVoiceOutputCapability(
                runtime=mock_runtime,
                streaming_audio_supported=False,
                generation_cancel_supported=False,
                provider_hard_cancel_supported=False,
                pending_flush_supported=False,
                active_audio_invalidation_supported=False,
                audio_formats=(),
                maximum_text_size=None,
                public_metadata={
                    "boundary": "voice_output",
                    "session_stage": "mock_synthesis_completed",
                    "audio_artifact_delivery": False,
                    "host_playback_owned": True,
                },
            ),
            motion=RealtimeMotionCapability(
                runtime=motion_runtime,
                request_cancel_supported=False,
                completion_event_supported=False,
                provider_neutral_intent_supported=False,
                public_metadata={
                    "boundary": "motion",
                    "session_wiring": "not_adopted",
                },
            ),
            supports_text_chat=True,
            supports_voice_input=True,
            supports_voice_output=True,
            supports_motion=False,
            real_runtime_enabled=False,
            hard_cancel_supported=False,
            tts_queue_flush_supported=False,
            public_metadata={
                "boundary": "realtime_capabilities",
                "snapshot_source": "realtime_session",
                "authoritative_builder": True,
                "session_wiring_adopted": True,
                "real_runtime_requested": False,
                "real_runtime_available": False,
                "project_root_provided": resolved_project_root is not None,
                "provider_execution_performed": False,
                "preflight_ready_stage_kinds": tuple(normalized_stage_capabilities),
                "preflight_failed_stage_kinds": normalized_failed_stage_kinds,
            },
        )

    def unavailable_reason(stage_kind: str) -> str:
        return (
            "stage_preflight_failed"
            if stage_kind in normalized_failed_stage_kinds
            else "stage_not_configured"
        )

    text_generation = normalized_stage_capabilities.get("text_generation")
    if text_generation is None:
        text_generation = _unavailable_text_generation_capability(
            reason=unavailable_reason("text_generation")
        )
    voice_input = normalized_stage_capabilities.get("voice_input")
    if voice_input is None:
        voice_input = _unavailable_voice_input_capability(
            reason=unavailable_reason("voice_input")
        )
    voice_output = normalized_stage_capabilities.get("voice_output")
    if voice_output is None:
        voice_output = _unavailable_voice_output_capability(
            reason=unavailable_reason("voice_output")
        )
    motion = normalized_stage_capabilities.get("motion")
    if motion is None:
        motion = _unavailable_motion_capability(reason=unavailable_reason("motion"))

    assert isinstance(text_generation, TextGenerationCapability)
    assert isinstance(voice_input, RealtimeVoiceInputCapability)
    assert isinstance(voice_output, RealtimeVoiceOutputCapability)
    assert isinstance(motion, RealtimeMotionCapability)

    return RealtimeCapabilitySnapshot(
        session_id=session_id,
        snapshot_scope=CapabilitySnapshotScope.SESSION,
        snapshot_generation=snapshot_generation,
        text_generation=text_generation,
        voice_input=voice_input,
        voice_output=voice_output,
        motion=motion,
        supports_text_chat=text_generation.runtime.usable,
        supports_voice_input=voice_input.runtime.usable,
        supports_voice_output=voice_output.runtime.usable,
        supports_motion=motion.runtime.usable,
        real_runtime_enabled=False,
        hard_cancel_supported=(
            text_generation.provider_hard_cancel_supported
            or voice_output.provider_hard_cancel_supported
        ),
        tts_queue_flush_supported=voice_output.pending_flush_supported,
        public_metadata={
            "boundary": "realtime_capabilities",
            "snapshot_source": "realtime_session_stage_preflight",
            "authoritative_builder": True,
            "session_wiring_adopted": True,
            "real_runtime_requested": True,
            "real_runtime_available": False,
            "project_root_provided": resolved_project_root is not None,
            "provider_execution_performed": False,
            "preflight_ready_stage_kinds": tuple(normalized_stage_capabilities),
            "preflight_failed_stage_kinds": normalized_failed_stage_kinds,
        },
    )


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
