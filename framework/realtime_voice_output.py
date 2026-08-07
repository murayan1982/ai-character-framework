"""Provider-neutral voice-synthesis generation contracts for v6.

FW-RT6-6a Control A defines synthesis work identity plus result, active-state,
cancellation, provider-adapter, and stage protocol vocabulary. Importing this
module must not import provider SDKs, execute providers, access the network or
private configuration, use a microphone, perform playback, or connect to VTube
Studio.

The package is explicitly stable as ``framework.realtime_voice_output`` but is
not imported or re-exported by the ``framework`` root in Control A. Existing
``VoiceOutputSession``, ``VoiceOutputRequest`` / ``VoiceOutputResult``,
``VoiceSynthesisRequest`` / ``VoiceSynthesisResult``, and
``framework.realtime_stage.VoiceOutputStage`` remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Mapping, Protocol, runtime_checkable
from uuid import uuid4

from .audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from .identity import GenerationId, SessionId, TurnId
from .public_safety import public_mapping, sanitize_public_value
from .realtime_capabilities import RealtimeVoiceOutputCapability
from .realtime_stage import RealtimeStageContext


_SYNTHESIS_WORK_ID_PATTERN = re.compile(r"^fw_synthesis_[0-9a-f]{32}$")


class SynthesisWorkId(str):
    """Opaque Framework-owned identity for one synthesis work item.

    A lifecycle ``GenerationId`` may contain multiple independent synthesis work
    items. This ID therefore supplements, and never replaces, session/turn/
    generation correlation.
    """

    _prefix = "fw_synthesis_"

    def __new__(cls, value: str) -> "SynthesisWorkId":
        if not isinstance(value, str):
            raise TypeError("SynthesisWorkId value must be a string")
        if value != value.strip() or not _SYNTHESIS_WORK_ID_PATTERN.fullmatch(value):
            raise ValueError("Invalid synthesis work identifier.")
        return str.__new__(cls, value)

    @classmethod
    def new(cls) -> "SynthesisWorkId":
        """Create a new provider-neutral Framework synthesis-work identity."""

        return cls(f"{cls._prefix}{uuid4().hex}")

    @classmethod
    def parse(cls, value: str) -> "SynthesisWorkId":
        """Validate and normalize one serialized synthesis-work identity."""

        if isinstance(value, cls):
            return value
        return cls(value)

    def to_json_value(self) -> str:
        """Return the JSON scalar representation."""

        return str(self)


@dataclass(frozen=True, slots=True)
class VoiceSynthesisResultEnvelope:
    """Correlation envelope for one completed provider-neutral synthesis work.

    The wrapped ``VoiceOutputResult`` is excluded from ``repr`` so artifact URLs,
    opaque artifact references, and other output handoff details are not exposed
    by simply printing the envelope.
    """

    context: RealtimeStageContext
    work_id: SynthesisWorkId | str
    result: VoiceOutputResult = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        work_id = (
            self.work_id
            if isinstance(self.work_id, SynthesisWorkId)
            else SynthesisWorkId.parse(self.work_id)
        )
        if not isinstance(self.result, VoiceOutputResult):
            raise TypeError("result must be a VoiceOutputResult")
        object.__setattr__(self, "work_id", work_id)

    @property
    def session_id(self) -> SessionId | str:
        return self.context.session_id

    @property
    def turn_id(self) -> TurnId | str:
        return self.context.turn_id

    @property
    def generation_id(self) -> GenerationId:
        return self.context.generation_id


@dataclass(frozen=True, slots=True)
class VoiceSynthesisActiveGeneration:
    """Public-safe snapshot of the currently active synthesis work.

    Only correlation context and opaque work identity are exposed. Requests,
    text, provider/model/voice identifiers, provider clients, provider payloads,
    artifact paths/references, and raw results are intentionally absent.
    """

    context: RealtimeStageContext
    work_id: SynthesisWorkId | str

    def __post_init__(self) -> None:
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        object.__setattr__(
            self,
            "work_id",
            self.work_id
            if isinstance(self.work_id, SynthesisWorkId)
            else SynthesisWorkId.parse(self.work_id),
        )

    @property
    def session_id(self) -> SessionId | str:
        return self.context.session_id

    @property
    def turn_id(self) -> TurnId | str:
        return self.context.turn_id

    @property
    def generation_id(self) -> GenerationId:
        return self.context.generation_id


class VoiceSynthesisCancelOutcome(str, Enum):
    """Typed result classification for one active-generation cancel request."""

    REQUESTED = "requested"
    NO_ACTIVE_GENERATION = "no_active_generation"
    WORK_MISMATCH = "work_mismatch"
    ALREADY_TERMINAL = "already_terminal"
    UNSUPPORTED = "unsupported"
    ALREADY_CLOSED = "already_closed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class VoiceSynthesisCancelResult:
    """Public-safe cancellation result for one synthesis generation boundary."""

    outcome: VoiceSynthesisCancelOutcome | str
    context: RealtimeStageContext
    work_id: SynthesisWorkId | str | None = None
    cooperative_cancel_requested: bool = False
    provider_hard_cancel_applied: bool = False
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, VoiceSynthesisCancelOutcome)
            else VoiceSynthesisCancelOutcome(str(self.outcome))
        )
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        work_id = self.work_id
        if work_id is not None and not isinstance(work_id, SynthesisWorkId):
            work_id = SynthesisWorkId.parse(work_id)
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")
        safe_message = sanitize_public_value(self.safe_message)
        if not isinstance(safe_message, str):
            raise TypeError("safe_message must normalize to public-safe text")

        cooperative = bool(self.cooperative_cancel_requested)
        hard_cancel = bool(self.provider_hard_cancel_applied)
        retryable = bool(self.retryable)
        non_cancel_outcomes = {
            VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION,
            VoiceSynthesisCancelOutcome.WORK_MISMATCH,
            VoiceSynthesisCancelOutcome.ALREADY_TERMINAL,
            VoiceSynthesisCancelOutcome.UNSUPPORTED,
            VoiceSynthesisCancelOutcome.ALREADY_CLOSED,
        }
        if outcome in non_cancel_outcomes and (cooperative or hard_cancel):
            raise ValueError(
                "non-cancel outcome must not claim cooperative or provider hard cancel"
            )
        if hard_cancel and not cooperative:
            raise ValueError(
                "provider_hard_cancel_applied requires cooperative_cancel_requested"
            )

        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "work_id", work_id)
        object.__setattr__(self, "cooperative_cancel_requested", cooperative)
        object.__setattr__(self, "provider_hard_cancel_applied", hard_cancel)
        object.__setattr__(self, "safe_message", safe_message)
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    @property
    def session_id(self) -> SessionId | str:
        return self.context.session_id

    @property
    def turn_id(self) -> TurnId | str:
        return self.context.turn_id

    @property
    def generation_id(self) -> GenerationId:
        return self.context.generation_id


@runtime_checkable
class VoiceSynthesisProviderAdapter(Protocol):
    """Provider-neutral adapter boundary used by a synthesis stage.

    Provider adapters receive only the existing public request. Session, turn,
    lifecycle-generation, and synthesis-work identities remain Framework-owned
    orchestration data and are never passed into the provider adapter protocol.
    """

    def capability(self) -> RealtimeVoiceOutputCapability:
        ...

    def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
        ...


@runtime_checkable
class VoiceSynthesisStage(Protocol):
    """Provider-neutral synthesis-generation stage contract.

    This is additive to the existing ``realtime_stage.VoiceOutputStage`` and
    deliberately excludes pending queue and host playback responsibilities.
    """

    @property
    def active_generation(self) -> VoiceSynthesisActiveGeneration | None:
        ...

    def preflight(self) -> RealtimeVoiceOutputCapability:
        ...

    def capability(self) -> RealtimeVoiceOutputCapability:
        ...

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: VoiceOutputRequest,
    ) -> VoiceSynthesisResultEnvelope:
        ...

    def cancel(
        self,
        *,
        context: RealtimeStageContext,
        work_id: SynthesisWorkId | str | None = None,
    ) -> VoiceSynthesisCancelResult:
        ...

    def close(self) -> None:
        ...


__all__ = [
    "SynthesisWorkId",
    "VoiceSynthesisResultEnvelope",
    "VoiceSynthesisActiveGeneration",
    "VoiceSynthesisCancelOutcome",
    "VoiceSynthesisCancelResult",
    "VoiceSynthesisProviderAdapter",
    "VoiceSynthesisStage",
]
