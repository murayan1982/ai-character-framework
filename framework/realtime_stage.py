"""Stable provider-neutral realtime stage protocol package.

FW-RT6-3a Control A defines the common public protocol vocabulary used by
future ``RealtimeSession`` stage injection. Importing this module must not load
provider SDKs, execute providers, access a microphone, perform playback, connect
to VTube Studio, inspect private configuration, or depend on a checkout/CWD.

The package is intentionally not imported by ``framework`` root in Control A.
Host applications that need protocol typing may import it explicitly as the
stable public package ``framework.realtime_stage``. Root-public adoption and
``RealtimeSession`` injection remain separately authorized controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Mapping, Protocol, TypeVar, runtime_checkable

from .audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from .identity import (
    GenerationId,
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)
from .motion import MotionRequest, MotionResult
from .public_safety import public_mapping
from .realtime import RealtimeTurn
from .realtime_capabilities import (
    RealtimeMotionCapability,
    RealtimeVoiceInputCapability,
    RealtimeVoiceOutputCapability,
    TextGenerationCapability,
)
from .text_chat_result import TextChatResult
from .voice_input import VoiceInputRequest, VoiceInputResult


StageResultT_co = TypeVar("StageResultT_co", covariant=True)


class RealtimeStageKind(str, Enum):
    """Provider-neutral identity of one unified realtime stage."""

    VOICE_INPUT = "voice_input"
    TEXT_GENERATION = "text_generation"
    VOICE_OUTPUT = "voice_output"
    MOTION = "motion"


_STAGE_RESULT_TYPES: Mapping[RealtimeStageKind, type[object]] = {
    RealtimeStageKind.VOICE_INPUT: VoiceInputResult,
    RealtimeStageKind.TEXT_GENERATION: TextChatResult,
    RealtimeStageKind.VOICE_OUTPUT: VoiceOutputResult,
    RealtimeStageKind.MOTION: MotionResult,
}


@dataclass(frozen=True, slots=True)
class RealtimeStageContext:
    """Public-safe correlation context for one stage operation.

    ``session_id`` and ``turn_id`` preserve legacy host strings while validating
    the Framework-reserved identity namespace. ``generation_id`` is always a
    Framework-owned opaque generation identity because stale-result admission is
    generation based.
    """

    session_id: SessionId | str
    turn_id: TurnId | str
    generation_id: GenerationId | str
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        session_id = normalize_session_id(self.session_id)
        turn_id = normalize_turn_id(self.turn_id)
        if session_id is None:
            raise ValueError("session_id must identify one realtime session")
        if turn_id is None:
            raise ValueError("turn_id must identify one realtime turn")
        generation_id = (
            self.generation_id
            if isinstance(self.generation_id, GenerationId)
            else GenerationId.parse(self.generation_id)
        )

        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "turn_id", turn_id)
        object.__setattr__(self, "generation_id", generation_id)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


@dataclass(frozen=True, slots=True)
class RealtimeStageResultEnvelope(Generic[StageResultT_co]):
    """Generation-bearing public envelope for one provider-neutral stage result.

    The stage value is hidden from ``repr`` to avoid accidental transcript,
    response-text, or artifact logging. The wrapped value remains one of the
    existing Framework public result models selected by the stage protocol.
    """

    stage_kind: RealtimeStageKind | str
    context: RealtimeStageContext
    result: StageResultT_co = field(repr=False)
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        stage_kind = (
            self.stage_kind
            if isinstance(self.stage_kind, RealtimeStageKind)
            else RealtimeStageKind(str(self.stage_kind))
        )
        if not isinstance(self.context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if self.result is None:
            raise ValueError("result must contain one public stage result")
        expected_result_type = _STAGE_RESULT_TYPES[stage_kind]
        if not isinstance(self.result, expected_result_type):
            raise TypeError(
                f"{stage_kind.value} results must use "
                f"{expected_result_type.__name__}"
            )

        object.__setattr__(self, "stage_kind", stage_kind)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
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


@runtime_checkable
class VoiceInputStage(Protocol):
    """Provider-neutral voice-input stage contract.

    ``cancel`` returns only whether cooperative cancellation was accepted. It
    does not claim provider hard-cancel completion or detailed subsystem reach;
    those remain separate later contracts.
    """

    @property
    def stage_kind(self) -> RealtimeStageKind:
        ...

    def preflight(self) -> RealtimeVoiceInputCapability:
        ...

    def capability(self) -> RealtimeVoiceInputCapability:
        ...

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: VoiceInputRequest,
    ) -> RealtimeStageResultEnvelope[VoiceInputResult]:
        ...

    def cancel(self, *, context: RealtimeStageContext) -> bool:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class TextGenerationStage(Protocol):
    """Provider-neutral text-generation stage contract."""

    @property
    def stage_kind(self) -> RealtimeStageKind:
        ...

    def preflight(self) -> TextGenerationCapability:
        ...

    def capability(self) -> TextGenerationCapability:
        ...

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: RealtimeTurn,
    ) -> RealtimeStageResultEnvelope[TextChatResult]:
        ...

    def cancel(self, *, context: RealtimeStageContext) -> bool:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class VoiceOutputStage(Protocol):
    """Provider-neutral voice-output stage contract."""

    @property
    def stage_kind(self) -> RealtimeStageKind:
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
    ) -> RealtimeStageResultEnvelope[VoiceOutputResult]:
        ...

    def cancel(self, *, context: RealtimeStageContext) -> bool:
        ...

    def close(self) -> None:
        ...


@runtime_checkable
class MotionStage(Protocol):
    """Provider-neutral motion stage contract."""

    @property
    def stage_kind(self) -> RealtimeStageKind:
        ...

    def preflight(self) -> RealtimeMotionCapability:
        ...

    def capability(self) -> RealtimeMotionCapability:
        ...

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: MotionRequest,
    ) -> RealtimeStageResultEnvelope[MotionResult]:
        ...

    def cancel(self, *, context: RealtimeStageContext) -> bool:
        ...

    def close(self) -> None:
        ...


__all__ = [
    "RealtimeStageKind",
    "RealtimeStageContext",
    "RealtimeStageResultEnvelope",
    "VoiceInputStage",
    "TextGenerationStage",
    "VoiceOutputStage",
    "MotionStage",
]
