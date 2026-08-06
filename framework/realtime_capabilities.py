"""Detailed provider-neutral realtime capability snapshot models.

FW-RT6-1d Control A defines the public v6 capability vocabulary only. Importing
this module must not inspect process environment, read credentials or private
configuration, import provider SDKs, create runtime clients, access the network,
microphone, playback, or VTube Studio, or probe provider availability.
"""

from __future__ import annotations
from .public_safety import public_mapping as _recursive_public_mapping

from dataclasses import dataclass, field
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Mapping

from .identity import SessionId, normalize_session_id
from .version import REALTIME_CAPABILITIES_SCHEMA_VERSION


class CapabilitySnapshotScope(str, Enum):
    """Public scope of one capability snapshot."""

    GLOBAL = "global"
    SESSION = "session"


def _public_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Delegate to the common recursive public-safety utility."""
    return _recursive_public_mapping(value)


def _normalize_optional_reason(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("unavailable_reason must be a string or None")
    normalized = value.strip()
    return normalized or None


def _normalize_string_tuple(
    values: tuple[str, ...] | list[str] | None,
    *,
    field_name: str,
) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} values must be strings")
        item = value.strip().lower()
        if not item:
            raise ValueError(f"{field_name} values must not be empty")
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return tuple(normalized)


def _positive_optional_int(value: int | None, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer or None")
    if value < 1:
        raise ValueError(f"{field_name} must be at least 1")
    return value


def _positive_optional_float(
    value: float | int | None,
    *,
    field_name: str,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number or None")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError(f"{field_name} must be a positive finite number")
    return normalized


@dataclass(frozen=True, slots=True)
class RuntimeCapabilityState:
    """Common truthful runtime state shared by every detailed stage capability.

    ``configured`` records whether the host supplied a complete public
    configuration assertion. ``runtime_available`` records whether the selected
    runtime is available according to the snapshot source. ``guarded`` remains
    independent so a configured and installed runtime can still be unavailable
    for execution. ``fake_runtime`` and ``real_runtime`` identify the selected
    runtime class and are mutually exclusive.
    """

    configured: bool = False
    runtime_available: bool = False
    guarded: bool = False
    fake_runtime: bool = False
    real_runtime: bool = False
    unavailable_reason: str | None = "not_configured"
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        configured = bool(self.configured)
        runtime_available = bool(self.runtime_available)
        guarded = bool(self.guarded)
        fake_runtime = bool(self.fake_runtime)
        real_runtime = bool(self.real_runtime)
        if fake_runtime and real_runtime:
            raise ValueError("fake_runtime and real_runtime are mutually exclusive")
        if (fake_runtime or real_runtime) and not runtime_available:
            raise ValueError("selected fake/real runtime requires runtime_available=True")
        object.__setattr__(self, "configured", configured)
        object.__setattr__(self, "runtime_available", runtime_available)
        object.__setattr__(self, "guarded", guarded)
        object.__setattr__(self, "fake_runtime", fake_runtime)
        object.__setattr__(self, "real_runtime", real_runtime)
        object.__setattr__(
            self,
            "unavailable_reason",
            _normalize_optional_reason(self.unavailable_reason),
        )
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    @property
    def usable(self) -> bool:
        """Whether this snapshot reports the selected runtime as usable now."""

        return self.configured and self.runtime_available and not self.guarded

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "configured": self.configured,
                "runtime_available": self.runtime_available,
                "guarded": self.guarded,
                "fake_runtime": self.fake_runtime,
                "real_runtime": self.real_runtime,
                "unavailable_reason": self.unavailable_reason,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class TextGenerationCapability:
    """Detailed text-generation capability for one snapshot scope."""

    runtime: RuntimeCapabilityState = field(default_factory=RuntimeCapabilityState)
    streaming_supported: bool = False
    cooperative_cancel_supported: bool = False
    provider_hard_cancel_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, RuntimeCapabilityState):
            raise TypeError("runtime must be RuntimeCapabilityState")
        object.__setattr__(self, "streaming_supported", bool(self.streaming_supported))
        object.__setattr__(
            self,
            "cooperative_cancel_supported",
            bool(self.cooperative_cancel_supported),
        )
        object.__setattr__(
            self,
            "provider_hard_cancel_supported",
            bool(self.provider_hard_cancel_supported),
        )
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "runtime": dict(self.runtime.as_dict()),
                "streaming_supported": self.streaming_supported,
                "cooperative_cancel_supported": self.cooperative_cancel_supported,
                "provider_hard_cancel_supported": self.provider_hard_cancel_supported,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class RealtimeVoiceInputCapability:
    """Detailed voice-input capability for one realtime snapshot."""

    runtime: RuntimeCapabilityState = field(default_factory=RuntimeCapabilityState)
    audio_chunk_input_supported: bool = False
    partial_transcript_supported: bool = False
    final_transcript_supported: bool = False
    input_abort_supported: bool = False
    backpressure_supported: bool = False
    accepted_audio_formats: tuple[str, ...] = ()
    maximum_chunk_size: int | None = None
    maximum_duration: float | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, RuntimeCapabilityState):
            raise TypeError("runtime must be RuntimeCapabilityState")
        for name in (
            "audio_chunk_input_supported",
            "partial_transcript_supported",
            "final_transcript_supported",
            "input_abort_supported",
            "backpressure_supported",
        ):
            object.__setattr__(self, name, bool(getattr(self, name)))
        object.__setattr__(
            self,
            "accepted_audio_formats",
            _normalize_string_tuple(
                self.accepted_audio_formats,
                field_name="accepted_audio_formats",
            ),
        )
        object.__setattr__(
            self,
            "maximum_chunk_size",
            _positive_optional_int(
                self.maximum_chunk_size,
                field_name="maximum_chunk_size",
            ),
        )
        object.__setattr__(
            self,
            "maximum_duration",
            _positive_optional_float(
                self.maximum_duration,
                field_name="maximum_duration",
            ),
        )
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "runtime": dict(self.runtime.as_dict()),
                "audio_chunk_input_supported": self.audio_chunk_input_supported,
                "partial_transcript_supported": self.partial_transcript_supported,
                "final_transcript_supported": self.final_transcript_supported,
                "input_abort_supported": self.input_abort_supported,
                "backpressure_supported": self.backpressure_supported,
                "accepted_audio_formats": self.accepted_audio_formats,
                "maximum_chunk_size": self.maximum_chunk_size,
                "maximum_duration": self.maximum_duration,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class RealtimeVoiceOutputCapability:
    """Detailed voice-output capability for one realtime snapshot."""

    runtime: RuntimeCapabilityState = field(default_factory=RuntimeCapabilityState)
    streaming_audio_supported: bool = False
    generation_cancel_supported: bool = False
    provider_hard_cancel_supported: bool = False
    pending_flush_supported: bool = False
    active_audio_invalidation_supported: bool = False
    audio_formats: tuple[str, ...] = ()
    maximum_text_size: int | None = None
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, RuntimeCapabilityState):
            raise TypeError("runtime must be RuntimeCapabilityState")
        for name in (
            "streaming_audio_supported",
            "generation_cancel_supported",
            "provider_hard_cancel_supported",
            "pending_flush_supported",
            "active_audio_invalidation_supported",
        ):
            object.__setattr__(self, name, bool(getattr(self, name)))
        object.__setattr__(
            self,
            "audio_formats",
            _normalize_string_tuple(self.audio_formats, field_name="audio_formats"),
        )
        object.__setattr__(
            self,
            "maximum_text_size",
            _positive_optional_int(
                self.maximum_text_size,
                field_name="maximum_text_size",
            ),
        )
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "runtime": dict(self.runtime.as_dict()),
                "streaming_audio_supported": self.streaming_audio_supported,
                "generation_cancel_supported": self.generation_cancel_supported,
                "provider_hard_cancel_supported": self.provider_hard_cancel_supported,
                "pending_flush_supported": self.pending_flush_supported,
                "active_audio_invalidation_supported": (
                    self.active_audio_invalidation_supported
                ),
                "audio_formats": self.audio_formats,
                "maximum_text_size": self.maximum_text_size,
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class RealtimeMotionCapability:
    """Detailed motion capability for one realtime snapshot."""

    runtime: RuntimeCapabilityState = field(default_factory=RuntimeCapabilityState)
    request_cancel_supported: bool = False
    completion_event_supported: bool = False
    provider_neutral_intent_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.runtime, RuntimeCapabilityState):
            raise TypeError("runtime must be RuntimeCapabilityState")
        object.__setattr__(
            self,
            "request_cancel_supported",
            bool(self.request_cancel_supported),
        )
        object.__setattr__(
            self,
            "completion_event_supported",
            bool(self.completion_event_supported),
        )
        object.__setattr__(
            self,
            "provider_neutral_intent_supported",
            bool(self.provider_neutral_intent_supported),
        )
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "runtime": dict(self.runtime.as_dict()),
                "request_cancel_supported": self.request_cancel_supported,
                "completion_event_supported": self.completion_event_supported,
                "provider_neutral_intent_supported": (
                    self.provider_neutral_intent_supported
                ),
                "public_metadata": dict(self.public_metadata),
            }
        )


@dataclass(frozen=True, slots=True)
class RealtimeCapabilitySnapshot:
    """Versioned detailed capability snapshot for a global or session scope.

    The compatibility booleans preserve the established v5 summary vocabulary.
    They are intentionally independent of the detailed stage models until a
    later control adopts one authoritative snapshot builder.
    """

    session_id: SessionId | str | None
    schema_version: str = REALTIME_CAPABILITIES_SCHEMA_VERSION
    snapshot_scope: CapabilitySnapshotScope | str = CapabilitySnapshotScope.SESSION
    snapshot_generation: int = 1
    text_generation: TextGenerationCapability = field(
        default_factory=TextGenerationCapability
    )
    voice_input: RealtimeVoiceInputCapability = field(
        default_factory=RealtimeVoiceInputCapability
    )
    voice_output: RealtimeVoiceOutputCapability = field(
        default_factory=RealtimeVoiceOutputCapability
    )
    motion: RealtimeMotionCapability = field(default_factory=RealtimeMotionCapability)
    supports_text_chat: bool = False
    supports_voice_input: bool = False
    supports_voice_output: bool = False
    supports_motion: bool = False
    real_runtime_enabled: bool = False
    hard_cancel_supported: bool = False
    tts_queue_flush_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        scope = (
            self.snapshot_scope
            if isinstance(self.snapshot_scope, CapabilitySnapshotScope)
            else CapabilitySnapshotScope(str(self.snapshot_scope))
        )
        session_id = normalize_session_id(self.session_id)
        if scope is CapabilitySnapshotScope.SESSION and session_id is None:
            raise ValueError("session-scoped capability snapshot requires session_id")
        if isinstance(self.snapshot_generation, bool) or not isinstance(
            self.snapshot_generation, int
        ):
            raise TypeError("snapshot_generation must be an integer")
        if self.snapshot_generation < 1:
            raise ValueError("snapshot_generation must be at least 1")
        if not isinstance(self.schema_version, str) or not self.schema_version.strip():
            raise ValueError("schema_version must be a non-empty string")
        for name, expected in (
            ("text_generation", TextGenerationCapability),
            ("voice_input", RealtimeVoiceInputCapability),
            ("voice_output", RealtimeVoiceOutputCapability),
            ("motion", RealtimeMotionCapability),
        ):
            if not isinstance(getattr(self, name), expected):
                raise TypeError(f"{name} must be {expected.__name__}")
        object.__setattr__(self, "snapshot_scope", scope)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "schema_version", self.schema_version.strip())
        for name in (
            "supports_text_chat",
            "supports_voice_input",
            "supports_voice_output",
            "supports_motion",
            "real_runtime_enabled",
            "hard_cancel_supported",
            "tts_queue_flush_supported",
        ):
            object.__setattr__(self, name, bool(getattr(self, name)))
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "schema_version": self.schema_version,
                "snapshot_scope": self.snapshot_scope.value,
                "snapshot_generation": self.snapshot_generation,
                "session_id": str(self.session_id) if self.session_id is not None else None,
                "text_generation": dict(self.text_generation.as_dict()),
                "voice_input": dict(self.voice_input.as_dict()),
                "voice_output": dict(self.voice_output.as_dict()),
                "motion": dict(self.motion.as_dict()),
                "supports_text_chat": self.supports_text_chat,
                "supports_voice_input": self.supports_voice_input,
                "supports_voice_output": self.supports_voice_output,
                "supports_motion": self.supports_motion,
                "real_runtime_enabled": self.real_runtime_enabled,
                "hard_cancel_supported": self.hard_cancel_supported,
                "tts_queue_flush_supported": self.tts_queue_flush_supported,
                "public_metadata": dict(self.public_metadata),
            }
        )


__all__ = [
    "CapabilitySnapshotScope",
    "RuntimeCapabilityState",
    "TextGenerationCapability",
    "RealtimeVoiceInputCapability",
    "RealtimeVoiceOutputCapability",
    "RealtimeMotionCapability",
    "RealtimeCapabilitySnapshot",
]
