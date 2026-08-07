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
import threading
from typing import Mapping, Protocol, runtime_checkable
from uuid import uuid4

from .audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from .identity import GenerationId, SessionId, TurnId
from .public_safety import public_mapping, sanitize_public_value
from .realtime_capabilities import RealtimeVoiceOutputCapability
from .realtime_stage import RealtimeStageContext
from .voice_artifacts import VoiceArtifactStore


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


class ProviderNeutralVoiceSynthesisStage:
    """Reference synchronous synthesis stage with public-safe active state.

    Control B adopts the accepted provider-adapter protocol and makes the
    currently executing synthesis work observable without exposing request text,
    provider details, artifacts, or provider handles. The reference stage is
    intentionally synchronous and does not implement generation cancellation,
    pending work, artifact invalidation, or host playback control.
    """

    __slots__ = ("_adapter", "_artifact_store", "_capability", "_lock", "_closed", "_active_generation")

    def __init__(
        self,
        adapter: VoiceSynthesisProviderAdapter,
        *,
        artifact_store: VoiceArtifactStore | None = None,
    ) -> None:
        if not isinstance(adapter, VoiceSynthesisProviderAdapter):
            raise TypeError(
                "adapter must implement the VoiceSynthesisProviderAdapter protocol"
            )
        capability = adapter.capability()
        if not isinstance(capability, RealtimeVoiceOutputCapability):
            raise TypeError("adapter capability must be RealtimeVoiceOutputCapability")
        if capability.generation_cancel_supported:
            raise ValueError(
                "Control B stage does not adopt generation cancellation support"
            )
        if capability.provider_hard_cancel_supported:
            raise ValueError(
                "Control B stage does not adopt provider hard-cancel support"
            )
        if artifact_store is not None and not isinstance(
            artifact_store, VoiceArtifactStore
        ):
            raise TypeError("artifact_store must implement VoiceArtifactStore")
        self._adapter = adapter
        self._artifact_store = artifact_store
        self._capability = capability
        self._lock = threading.RLock()
        self._closed = False
        self._active_generation: VoiceSynthesisActiveGeneration | None = None

    @property
    def active_generation(self) -> VoiceSynthesisActiveGeneration | None:
        """Return the current public-safe active synthesis snapshot, if any."""

        with self._lock:
            return self._active_generation

    def preflight(self) -> RealtimeVoiceOutputCapability:
        """Return the adopted provider capability without provider execution."""

        return self._validated_capability()

    def capability(self) -> RealtimeVoiceOutputCapability:
        """Return the truthful current synthesis capability snapshot."""

        return self._validated_capability()

    def start(
        self,
        *,
        context: RealtimeStageContext,
        request: VoiceOutputRequest,
    ) -> VoiceSynthesisResultEnvelope:
        """Run one synchronous synthesis while exposing opaque active identity."""

        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if not isinstance(request, VoiceOutputRequest):
            raise TypeError("request must be a VoiceOutputRequest")
        work_id = SynthesisWorkId.new()
        active = self._claim_generation(context=context, work_id=work_id)
        return self._run_claimed(active=active, request=request)

    def _claim_generation(
        self,
        *,
        context: RealtimeStageContext,
        work_id: SynthesisWorkId | str,
    ) -> VoiceSynthesisActiveGeneration:
        """Claim one Framework-owned work identity without executing a provider."""

        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        normalized_work_id = (
            work_id
            if isinstance(work_id, SynthesisWorkId)
            else SynthesisWorkId.parse(work_id)
        )
        active = VoiceSynthesisActiveGeneration(
            context=context,
            work_id=normalized_work_id,
        )
        with self._lock:
            if self._closed:
                raise RuntimeError("Voice synthesis stage is closed.")
            if self._active_generation is not None:
                raise RuntimeError("Voice synthesis generation is already active.")
            self._active_generation = active
        return active

    def _run_claimed(
        self,
        *,
        active: VoiceSynthesisActiveGeneration,
        request: VoiceOutputRequest,
    ) -> VoiceSynthesisResultEnvelope:
        """Execute exactly one already-claimed synthesis work item."""

        if not isinstance(active, VoiceSynthesisActiveGeneration):
            raise TypeError("active must be VoiceSynthesisActiveGeneration")
        if not isinstance(request, VoiceOutputRequest):
            self._release_generation(active.work_id)
            raise TypeError("request must be a VoiceOutputRequest")
        with self._lock:
            if self._active_generation != active:
                raise RuntimeError("Voice synthesis work is not the active generation.")

        try:
            result = self._adapter.synthesize(request)
            if not isinstance(result, VoiceOutputResult):
                raise TypeError("adapter synthesize result must be VoiceOutputResult")
            self._bind_result_artifact(context=active.context, result=result)
            return VoiceSynthesisResultEnvelope(
                context=active.context,
                work_id=active.work_id,
                result=result,
            )
        finally:
            self._release_generation(active.work_id)

    def _release_generation(self, work_id: SynthesisWorkId | str) -> None:
        """Release one matching active generation without claiming cancellation."""

        normalized_work_id = (
            work_id
            if isinstance(work_id, SynthesisWorkId)
            else SynthesisWorkId.parse(work_id)
        )
        with self._lock:
            current = self._active_generation
            if current is not None and current.work_id == normalized_work_id:
                self._active_generation = None

    def cancel(
        self,
        *,
        context: RealtimeStageContext,
        work_id: SynthesisWorkId | str | None = None,
    ) -> VoiceSynthesisCancelResult:
        """Report Control B cancellation truth without cancelling synthesis.

        Active-generation cancellation execution and provider hard cancellation
        remain FW-RT6-6d work, so an active matching work item is classified as
        ``UNSUPPORTED`` rather than falsely returning ``REQUESTED``.
        """

        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        requested_work_id = work_id
        if requested_work_id is not None and not isinstance(
            requested_work_id, SynthesisWorkId
        ):
            requested_work_id = SynthesisWorkId.parse(requested_work_id)

        with self._lock:
            if self._closed:
                return VoiceSynthesisCancelResult(
                    outcome=VoiceSynthesisCancelOutcome.ALREADY_CLOSED,
                    context=context,
                    work_id=requested_work_id,
                    safe_message="Voice synthesis stage is already closed.",
                )
            active = self._active_generation
            if active is None:
                return VoiceSynthesisCancelResult(
                    outcome=VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION,
                    context=context,
                    work_id=requested_work_id,
                    safe_message="No voice synthesis generation is active.",
                )
            if active.context != context or (
                requested_work_id is not None and requested_work_id != active.work_id
            ):
                return VoiceSynthesisCancelResult(
                    outcome=VoiceSynthesisCancelOutcome.WORK_MISMATCH,
                    context=context,
                    work_id=requested_work_id,
                    safe_message="Requested voice synthesis work is not active.",
                )

            return VoiceSynthesisCancelResult(
                outcome=VoiceSynthesisCancelOutcome.UNSUPPORTED,
                context=context,
                work_id=active.work_id,
                safe_message="Active voice synthesis cancellation is not supported.",
            )

    def close(self) -> None:
        """Close the stage idempotently without claiming active cancellation."""

        with self._lock:
            self._closed = True

    def _bind_result_artifact(
        self,
        *,
        context: RealtimeStageContext,
        result: VoiceOutputResult,
    ) -> None:
        artifact_ref = result.audio_artifact_ref
        if artifact_ref is None:
            return
        store = self._artifact_store
        if store is None:
            raise RuntimeError(
                "Voice artifact store is required to bind an artifact result."
            )
        record = store.bind_generation(artifact_ref, context.generation_id)
        if record.ref != artifact_ref:
            raise RuntimeError("Voice artifact store returned a mismatched reference.")

    def _validated_capability(self) -> RealtimeVoiceOutputCapability:
        return self._capability


__all__ = [
    "SynthesisWorkId",
    "VoiceSynthesisResultEnvelope",
    "VoiceSynthesisActiveGeneration",
    "VoiceSynthesisCancelOutcome",
    "VoiceSynthesisCancelResult",
    "VoiceSynthesisProviderAdapter",
    "VoiceSynthesisStage",
]
