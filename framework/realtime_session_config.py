"""Provider-neutral realtime-session construction models.

FW-RT6-4a Control A defines immutable public configuration and construction
result vocabulary only. Importing this module must not import provider SDKs,
execute providers, inspect environment or credentials, access a microphone,
perform playback, connect to VTube Studio, or construct a realtime session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Mapping

from .identity import SessionId
from .public_safety import REDACTED_PATH, public_mapping, sanitize_public_value

if TYPE_CHECKING:
    from .realtime_stage import (
        MotionStage,
        TextGenerationStage,
        VoiceInputStage,
        VoiceOutputStage,
    )


_CANONICAL_STAGE_KINDS = frozenset(
    {
        "voice_input",
        "text_generation",
        "voice_output",
        "motion",
    }
)


def _require_bool(value: object, *, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a boolean")
    return value


def _normalize_stage_kinds(
    values: tuple[str, ...] | list[str] | None,
    *,
    field_name: str,
) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list of stage-kind strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError(f"{field_name} values must be strings")
        item = value.strip().lower()
        if not item:
            raise ValueError(f"{field_name} values must not be empty")
        if item not in _CANONICAL_STAGE_KINDS:
            raise ValueError(f"{field_name} contains an unknown realtime stage kind")
        if item in seen:
            raise ValueError(f"{field_name} must not contain duplicate stage kinds")
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


def _normalize_safe_message(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("safe_message must be a string")
    normalized = value.strip()
    sanitized = sanitize_public_value(normalized)
    if not isinstance(sanitized, str):
        raise AssertionError("safe_message sanitization must produce a string")
    if sanitized == REDACTED_PATH:
        return "Realtime session construction is unavailable."
    return sanitized


@dataclass(frozen=True, slots=True)
class RealtimeSessionConfig:
    """Explicit provider-neutral composition input for one realtime session.

    Stage objects are intentionally hidden from ``repr``. Control A stores no
    provider name, credential, endpoint, private path, provider client, raw
    payload, or provider-specific handle. Validation and adoption by
    ``RealtimeSession`` remain a separately authorized control.
    """

    real_runtime_enabled: bool = False
    voice_input_stage: VoiceInputStage | None = field(default=None, repr=False)
    text_generation_stage: TextGenerationStage | None = field(default=None, repr=False)
    voice_output_stage: VoiceOutputStage | None = field(default=None, repr=False)
    motion_stage: MotionStage | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "real_runtime_enabled",
            _require_bool(
                self.real_runtime_enabled,
                field_name="real_runtime_enabled",
            ),
        )


class RealtimeSessionConstructionStatus(str, Enum):
    """Public provider-neutral outcome of realtime-session construction."""

    MOCK_READY = "mock_ready"
    REAL_CONFIGURATION_READY = "real_configuration_ready"
    CONFIGURATION_INCOMPLETE = "configuration_incomplete"
    PREFLIGHT_FAILED = "preflight_failed"


@dataclass(frozen=True, slots=True)
class RealtimeSessionConstructionResult:
    """Immutable public-safe construction result for one realtime session.

    The result describes composition truth without exposing stage instances,
    provider objects, raw exceptions, credentials, private paths, or payloads.
    ``runtime_executable`` describes the selected runtime path, not merely that
    configuration fields were supplied.
    """

    status: RealtimeSessionConstructionStatus | str
    session_id: SessionId | str
    configuration_complete: bool
    runtime_executable: bool
    real_runtime_requested: bool
    real_runtime_enabled: bool
    missing_stage_kinds: tuple[str, ...] = ()
    failed_stage_kinds: tuple[str, ...] = ()
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.status
            if isinstance(self.status, RealtimeSessionConstructionStatus)
            else RealtimeSessionConstructionStatus(str(self.status))
        )
        session_id = (
            self.session_id
            if isinstance(self.session_id, SessionId)
            else SessionId.parse(self.session_id)
        )
        configuration_complete = _require_bool(
            self.configuration_complete,
            field_name="configuration_complete",
        )
        runtime_executable = _require_bool(
            self.runtime_executable,
            field_name="runtime_executable",
        )
        real_runtime_requested = _require_bool(
            self.real_runtime_requested,
            field_name="real_runtime_requested",
        )
        real_runtime_enabled = _require_bool(
            self.real_runtime_enabled,
            field_name="real_runtime_enabled",
        )
        retryable = _require_bool(self.retryable, field_name="retryable")
        missing_stage_kinds = _normalize_stage_kinds(
            self.missing_stage_kinds,
            field_name="missing_stage_kinds",
        )
        failed_stage_kinds = _normalize_stage_kinds(
            self.failed_stage_kinds,
            field_name="failed_stage_kinds",
        )

        if real_runtime_enabled and not (
            real_runtime_requested
            and configuration_complete
            and runtime_executable
        ):
            raise ValueError(
                "real_runtime_enabled requires requested, complete, executable configuration"
            )
        if missing_stage_kinds and configuration_complete:
            raise ValueError(
                "missing_stage_kinds requires configuration_complete=False"
            )

        if status is RealtimeSessionConstructionStatus.MOCK_READY:
            if real_runtime_requested or real_runtime_enabled:
                raise ValueError("mock_ready cannot report real runtime requested or enabled")
            if not configuration_complete or not runtime_executable:
                raise ValueError("mock_ready requires complete executable mock configuration")
            if missing_stage_kinds or failed_stage_kinds:
                raise ValueError("mock_ready cannot report missing or failed stages")
        elif status is RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY:
            if not real_runtime_requested or not configuration_complete:
                raise ValueError(
                    "real_configuration_ready requires requested complete configuration"
                )
            if missing_stage_kinds or failed_stage_kinds:
                raise ValueError(
                    "real_configuration_ready cannot report missing or failed stages"
                )
        elif status is RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE:
            if not real_runtime_requested:
                raise ValueError(
                    "configuration_incomplete requires real_runtime_requested=True"
                )
            if configuration_complete or runtime_executable or real_runtime_enabled:
                raise ValueError(
                    "configuration_incomplete cannot be complete, executable, or enabled"
                )
            if not missing_stage_kinds:
                raise ValueError(
                    "configuration_incomplete requires at least one missing stage kind"
                )
            if failed_stage_kinds:
                raise ValueError(
                    "configuration_incomplete cannot report failed stage preflight"
                )
        elif status is RealtimeSessionConstructionStatus.PREFLIGHT_FAILED:
            if runtime_executable or real_runtime_enabled:
                raise ValueError(
                    "preflight_failed cannot report an executable or enabled runtime"
                )
            if not failed_stage_kinds:
                raise ValueError(
                    "preflight_failed requires at least one failed stage kind"
                )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "configuration_complete", configuration_complete)
        object.__setattr__(self, "runtime_executable", runtime_executable)
        object.__setattr__(self, "real_runtime_requested", real_runtime_requested)
        object.__setattr__(self, "real_runtime_enabled", real_runtime_enabled)
        object.__setattr__(self, "missing_stage_kinds", missing_stage_kinds)
        object.__setattr__(self, "failed_stage_kinds", failed_stage_kinds)
        object.__setattr__(self, "safe_message", _normalize_safe_message(self.safe_message))
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))


__all__ = [
    "RealtimeSessionConfig",
    "RealtimeSessionConstructionStatus",
    "RealtimeSessionConstructionResult",
]
