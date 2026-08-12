"""Provider-neutral v5 standalone-session compatibility contract.

FW-RT6-11a Control A defines immutable compatibility and deprecation-policy
vocabulary only. Runtime adoption remains Control B work: importing this
explicit package does not construct a public session, invoke a provider,
register a callback, emit an event, issue a warning, or alter a factory.

Compatibility is deliberately distinct from deprecation. Existing v4/v5
session methods remain silent compatibility members. A member may use the
deprecation policy only after it has an explicit replacement, warning policy,
earliest removal major, and migration-evidence requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class StandaloneSessionKind(str, Enum):
    """Public session boundaries covered by FW-RT6-11a."""

    TEXT_CHAT = "text_chat"
    VOICE_INPUT = "voice_input"
    VOICE_OUTPUT = "voice_output"
    MOTION = "motion"
    REALTIME = "realtime"


class SessionCompatibilityMode(str, Enum):
    """Execution/compatibility selection visible at one session boundary."""

    V5_STANDALONE = "v5_standalone"
    V5_SKELETON = "v5_skeleton"
    V6_UNIFIED = "v6_unified"


class CompatibilityMemberStatus(str, Enum):
    """Whether use of a member is stable, compatible, or deprecated."""

    STABLE = "stable"
    COMPATIBILITY = "compatibility"
    DEPRECATED = "deprecated"


class CompatibilityWarningMode(str, Enum):
    """Only the two warning dispositions permitted by this contract."""

    SILENT = "silent"
    DEPRECATION_WARNING = "deprecation_warning"


_CONTRACT_VERSION_BY_KIND = MappingProxyType(
    {
        StandaloneSessionKind.TEXT_CHAT: "4.0",
        StandaloneSessionKind.VOICE_INPUT: "5.2.0",
        StandaloneSessionKind.VOICE_OUTPUT: "v5.lazy_provider_adapter",
        StandaloneSessionKind.MOTION: "5.5.0",
        StandaloneSessionKind.REALTIME: "5.2.0",
    }
)
_EXECUTION_OWNER_BY_KIND = MappingProxyType(
    {
        StandaloneSessionKind.TEXT_CHAT: "TextChatSession",
        StandaloneSessionKind.VOICE_INPUT: "VoiceInputSession",
        StandaloneSessionKind.VOICE_OUTPUT: "VoiceOutputSession",
        StandaloneSessionKind.MOTION: "MotionSession",
        StandaloneSessionKind.REALTIME: "RealtimeSession",
    }
)
_COMPATIBILITY_MEMBERS = MappingProxyType(
    {
        StandaloneSessionKind.TEXT_CHAT: (
            "ask",
            "ask_result",
            "ask_stream",
            "interrupt",
            "reset",
            "on_event",
            "on_state_change",
            "dispose",
        ),
        StandaloneSessionKind.VOICE_INPUT: (
            "listen_result",
            "text_fallback_result",
            "transcribe_audio_result",
            "listen_audio_result",
            "abort_input",
            "on_event",
            "dispose",
        ),
        StandaloneSessionKind.VOICE_OUTPUT: (
            "speak",
            "create_output",
            "dispose",
        ),
        StandaloneSessionKind.MOTION: (
            "preflight",
            "apply_motion",
            "on_event",
            "dispose",
        ),
        StandaloneSessionKind.REALTIME: (
            "run_turn",
            "on_legacy_event",
            "get_tts_queue_state",
            "interrupt",
            "cancel_current_turn",
            "flush_output",
            "set_barge_in_policy",
            "decide_barge_in",
            "dispose",
        ),
    }
)


def _session_kind(value: StandaloneSessionKind | str) -> StandaloneSessionKind:
    return (
        value
        if isinstance(value, StandaloneSessionKind)
        else StandaloneSessionKind(str(value))
    )


def _non_empty_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class SessionCompatibilityProfile:
    """Immutable facts for one existing public-session compatibility boundary."""

    session_kind: StandaloneSessionKind | str
    mode: SessionCompatibilityMode | str
    contract_version: str
    execution_owner: str
    legacy_methods_preserved: bool = True
    legacy_return_shapes_preserved: bool = True
    legacy_event_shapes_preserved: bool = True
    factory_signature_preserved: bool = True
    warning_mode: CompatibilityWarningMode | str = CompatibilityWarningMode.SILENT
    runtime_execution_performed: bool = False

    def __post_init__(self) -> None:
        kind = _session_kind(self.session_kind)
        mode = (
            self.mode
            if isinstance(self.mode, SessionCompatibilityMode)
            else SessionCompatibilityMode(str(self.mode))
        )
        warning_mode = (
            self.warning_mode
            if isinstance(self.warning_mode, CompatibilityWarningMode)
            else CompatibilityWarningMode(str(self.warning_mode))
        )
        contract_version = _non_empty_text(
            self.contract_version,
            field_name="contract_version",
        )
        execution_owner = _non_empty_text(
            self.execution_owner,
            field_name="execution_owner",
        )
        for field_name in (
            "legacy_methods_preserved",
            "legacy_return_shapes_preserved",
            "legacy_event_shapes_preserved",
            "factory_signature_preserved",
            "runtime_execution_performed",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        if kind is StandaloneSessionKind.REALTIME:
            if mode not in {
                SessionCompatibilityMode.V5_SKELETON,
                SessionCompatibilityMode.V6_UNIFIED,
            }:
                raise ValueError(
                    "RealtimeSession mode must be v5_skeleton or v6_unified"
                )
        elif mode is not SessionCompatibilityMode.V5_STANDALONE:
            raise ValueError(
                "non-realtime standalone sessions must use v5_standalone"
            )
        if contract_version != _CONTRACT_VERSION_BY_KIND[kind]:
            raise ValueError("contract_version must match the frozen session contract")
        if execution_owner != _EXECUTION_OWNER_BY_KIND[kind]:
            raise ValueError("execution_owner must reuse the existing public session")
        if not all(
            (
                self.legacy_methods_preserved,
                self.legacy_return_shapes_preserved,
                self.legacy_event_shapes_preserved,
                self.factory_signature_preserved,
            )
        ):
            raise ValueError("Control A compatibility profiles cannot describe breakage")
        if warning_mode is not CompatibilityWarningMode.SILENT:
            raise ValueError("compatibility profiles must remain warning-free")
        if self.runtime_execution_performed:
            raise ValueError("Control A profiles cannot perform runtime execution")

        object.__setattr__(self, "session_kind", kind)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "contract_version", contract_version)
        object.__setattr__(self, "execution_owner", execution_owner)
        object.__setattr__(self, "warning_mode", warning_mode)

    def as_dict(self) -> dict[str, str | bool]:
        """Return the exact JSON-friendly provider-neutral profile surface."""

        return {
            "session_kind": self.session_kind.value,
            "mode": self.mode.value,
            "contract_version": self.contract_version,
            "execution_owner": self.execution_owner,
            "legacy_methods_preserved": self.legacy_methods_preserved,
            "legacy_return_shapes_preserved": self.legacy_return_shapes_preserved,
            "legacy_event_shapes_preserved": self.legacy_event_shapes_preserved,
            "factory_signature_preserved": self.factory_signature_preserved,
            "warning_mode": self.warning_mode.value,
            "runtime_execution_performed": self.runtime_execution_performed,
        }


@dataclass(frozen=True, slots=True)
class DeprecatedMemberPolicy:
    """Explicit policy required before one public member may be deprecated."""

    session_kind: StandaloneSessionKind | str
    member_name: str
    replacement: str
    warning_mode: CompatibilityWarningMode | str = (
        CompatibilityWarningMode.DEPRECATION_WARNING
    )
    warning_category: str = "DeprecationWarning"
    stacklevel: int = 2
    warn_on_import: bool = False
    warn_on_construction: bool = False
    earliest_removal_major_version: int = 7
    migration_evidence_required: bool = True

    def __post_init__(self) -> None:
        kind = _session_kind(self.session_kind)
        member_name = _non_empty_text(self.member_name, field_name="member_name")
        replacement = _non_empty_text(self.replacement, field_name="replacement")
        warning_mode = (
            self.warning_mode
            if isinstance(self.warning_mode, CompatibilityWarningMode)
            else CompatibilityWarningMode(str(self.warning_mode))
        )
        warning_category = _non_empty_text(
            self.warning_category,
            field_name="warning_category",
        )
        if replacement == member_name:
            raise ValueError("replacement must differ from member_name")
        if member_name in _COMPATIBILITY_MEMBERS[kind]:
            raise ValueError(
                "an accepted compatibility member cannot be deprecated in Control A"
            )
        if warning_mode is not CompatibilityWarningMode.DEPRECATION_WARNING:
            raise ValueError("deprecated members must use DeprecationWarning")
        if warning_category != "DeprecationWarning":
            raise ValueError("warning_category must be DeprecationWarning")
        if isinstance(self.stacklevel, bool) or not isinstance(self.stacklevel, int):
            raise TypeError("stacklevel must be an integer")
        if self.stacklevel != 2:
            raise ValueError("stacklevel must identify the application call site")
        for field_name in (
            "warn_on_import",
            "warn_on_construction",
            "migration_evidence_required",
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(f"{field_name} must be a boolean")
        if self.warn_on_import or self.warn_on_construction:
            raise ValueError("deprecation warnings may be emitted only on member use")
        if (
            isinstance(self.earliest_removal_major_version, bool)
            or not isinstance(self.earliest_removal_major_version, int)
        ):
            raise TypeError("earliest_removal_major_version must be an integer")
        if self.earliest_removal_major_version < 7:
            raise ValueError("a v5 compatibility member cannot be removed before v7")
        if not self.migration_evidence_required:
            raise ValueError("deprecated removal requires migration evidence")

        object.__setattr__(self, "session_kind", kind)
        object.__setattr__(self, "member_name", member_name)
        object.__setattr__(self, "replacement", replacement)
        object.__setattr__(self, "warning_mode", warning_mode)
        object.__setattr__(self, "warning_category", warning_category)

    def as_dict(self) -> dict[str, str | int | bool]:
        """Return policy facts without a session, callback, or warning object."""

        return {
            "session_kind": self.session_kind.value,
            "member_name": self.member_name,
            "replacement": self.replacement,
            "warning_mode": self.warning_mode.value,
            "warning_category": self.warning_category,
            "stacklevel": self.stacklevel,
            "warn_on_import": self.warn_on_import,
            "warn_on_construction": self.warn_on_construction,
            "earliest_removal_major_version": self.earliest_removal_major_version,
            "migration_evidence_required": self.migration_evidence_required,
        }


def build_session_compatibility_profile(
    session_kind: StandaloneSessionKind | str,
    *,
    unified_runtime_requested: bool = False,
) -> SessionCompatibilityProfile:
    """Build the sole canonical profile for one existing public session."""

    kind = _session_kind(session_kind)
    if type(unified_runtime_requested) is not bool:
        raise TypeError("unified_runtime_requested must be a boolean")
    if kind is not StandaloneSessionKind.REALTIME and unified_runtime_requested:
        raise ValueError("only RealtimeSession can select v6_unified mode")
    if kind is StandaloneSessionKind.REALTIME:
        mode = (
            SessionCompatibilityMode.V6_UNIFIED
            if unified_runtime_requested
            else SessionCompatibilityMode.V5_SKELETON
        )
    else:
        mode = SessionCompatibilityMode.V5_STANDALONE
    return SessionCompatibilityProfile(
        session_kind=kind,
        mode=mode,
        contract_version=_CONTRACT_VERSION_BY_KIND[kind],
        execution_owner=_EXECUTION_OWNER_BY_KIND[kind],
    )


def build_deprecated_member_policy(
    session_kind: StandaloneSessionKind | str,
    member_name: str,
    *,
    replacement: str,
    earliest_removal_major_version: int = 7,
) -> DeprecatedMemberPolicy:
    """Build an explicit future deprecation policy without emitting a warning."""

    return DeprecatedMemberPolicy(
        session_kind=session_kind,
        member_name=member_name,
        replacement=replacement,
        earliest_removal_major_version=earliest_removal_major_version,
    )


def compatibility_members(
    session_kind: StandaloneSessionKind | str,
) -> tuple[str, ...]:
    """Return the frozen warning-free member inventory for one session."""

    return _COMPATIBILITY_MEMBERS[_session_kind(session_kind)]


def warning_mode_for_member(
    status: CompatibilityMemberStatus | str,
) -> CompatibilityWarningMode:
    """Map stable/compatibility use to silence and true deprecation to warning."""

    resolved = (
        status
        if isinstance(status, CompatibilityMemberStatus)
        else CompatibilityMemberStatus(str(status))
    )
    if resolved is CompatibilityMemberStatus.DEPRECATED:
        return CompatibilityWarningMode.DEPRECATION_WARNING
    return CompatibilityWarningMode.SILENT


__all__ = [
    "StandaloneSessionKind",
    "SessionCompatibilityMode",
    "CompatibilityMemberStatus",
    "CompatibilityWarningMode",
    "SessionCompatibilityProfile",
    "DeprecatedMemberPolicy",
    "build_session_compatibility_profile",
    "build_deprecated_member_policy",
    "compatibility_members",
    "warning_mode_for_member",
]
