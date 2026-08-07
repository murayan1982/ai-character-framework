"""Internal FW-RT6-6d voice-output cancellation/invalidation reference control.

This module composes already accepted provider-neutral voice-output primitives.
It is intentionally not a stable public package and is not imported by the
``framework`` root. It does not perform host playback or provider hard cancel.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import threading
from typing import Mapping

from .audio.voice_output import VoiceOutputRequest, VoiceOutputResult
from .identity import GenerationId
from .public_safety import public_mapping
from .realtime_capabilities import RealtimeVoiceOutputCapability
from .realtime_generation_gate import (
    GenerationAdmissionDecision,
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
)
from .realtime_stage import RealtimeStageContext
from .realtime_voice_output import (
    ProviderNeutralVoiceSynthesisStage,
    SynthesisWorkId,
    VoiceSynthesisActiveGeneration,
    VoiceSynthesisCancelOutcome,
    VoiceSynthesisCancelResult,
    VoiceSynthesisProviderAdapter,
    VoiceSynthesisResultEnvelope,
)
from .realtime_voice_output_queue import (
    BoundedVoiceSynthesisPendingQueue,
    VoiceSynthesisPendingClearResult,
)
from .voice_artifacts import VoiceArtifactStore


def _positive_timeout(value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("cancel_timeout_seconds must be a finite positive number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        raise ValueError("cancel_timeout_seconds must be a finite positive number")
    return normalized


@dataclass(frozen=True, slots=True)
class VoiceSynthesisControlFlushResult:
    """Internal public-safe aggregate of pending clear and active cancel effects."""

    pending_clear_result: VoiceSynthesisPendingClearResult
    active_cancel_result: VoiceSynthesisCancelResult | None = None
    completed_artifacts_invalidated: int = 0
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(
            self.pending_clear_result,
            VoiceSynthesisPendingClearResult,
        ):
            raise TypeError(
                "pending_clear_result must be VoiceSynthesisPendingClearResult"
            )
        if self.active_cancel_result is not None and not isinstance(
            self.active_cancel_result,
            VoiceSynthesisCancelResult,
        ):
            raise TypeError(
                "active_cancel_result must be VoiceSynthesisCancelResult or None"
            )
        if (
            isinstance(self.completed_artifacts_invalidated, bool)
            or not isinstance(self.completed_artifacts_invalidated, int)
        ):
            raise TypeError("completed_artifacts_invalidated must be an integer")
        if self.completed_artifacts_invalidated < 0:
            raise ValueError("completed_artifacts_invalidated must be non-negative")
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def future_delivery_suppressed(self) -> bool:
        result = self.active_cancel_result
        return bool(result is not None and result.future_delivery_suppressed)

    @property
    def idempotent_noop(self) -> bool:
        result = self.active_cancel_result
        return (
            self.pending_clear_result.cleared_count == 0
            and result is None
            and self.completed_artifacts_invalidated == 0
        )


class CancelableProviderNeutralVoiceSynthesisStage(
    ProviderNeutralVoiceSynthesisStage
):
    """Reference cooperative-cancel stage with bounded wait and stale suppression.

    Provider transports remain synchronous and correlation-free. Cancellation is
    therefore Framework-cooperative: it installs a one-way future-delivery
    barrier, optionally waits a bounded time for the provider call to quiesce,
    and reports provider hard cancel as unsupported. A late provider result is
    never returned with an audio handoff after cancellation.

    When a ``RealtimeGenerationGate`` is supplied, the returned synthesis
    completion is admitted through that existing gate. A retired/unknown/turn-
    mismatched generation is converted into a non-audio stale result and any
    generation-bound FW artifact is invalidated before return.
    """

    __slots__ = (
        "_cancel_timeout_seconds",
        "_generation_gate",
        "_active_done",
        "_cancel_requested_work",
        "_last_cancel_work_id",
        "_last_cancel_result",
        "_last_artifact_invalidated",
        "_last_stale_delivery_suppressed",
        "_last_generation_admission",
    )

    def __init__(
        self,
        adapter: VoiceSynthesisProviderAdapter,
        *,
        artifact_store: VoiceArtifactStore | None = None,
        generation_gate: RealtimeGenerationGate | None = None,
        cancel_timeout_seconds: float | int = 0.25,
    ) -> None:
        if generation_gate is not None and not isinstance(
            generation_gate,
            RealtimeGenerationGate,
        ):
            raise TypeError(
                "generation_gate must be RealtimeGenerationGate or None"
            )
        super().__init__(adapter, artifact_store=artifact_store)
        self._cancel_timeout_seconds = _positive_timeout(cancel_timeout_seconds)
        self._generation_gate = generation_gate
        self._active_done: threading.Event | None = None
        self._cancel_requested_work: SynthesisWorkId | None = None
        self._last_cancel_work_id: SynthesisWorkId | None = None
        self._last_cancel_result: VoiceSynthesisCancelResult | None = None
        self._last_artifact_invalidated = False
        self._last_stale_delivery_suppressed = False
        self._last_generation_admission: (
            GenerationAdmissionDecision[VoiceSynthesisResultEnvelope] | None
        ) = None

    @property
    def cancel_timeout_seconds(self) -> float:
        return self._cancel_timeout_seconds

    @property
    def active_cancel_requested(self) -> bool:
        with self._lock:
            active = self._active_generation
            return (
                active is not None
                and self._cancel_requested_work == active.work_id
            )

    @property
    def last_stale_delivery_suppressed(self) -> bool:
        with self._lock:
            return self._last_stale_delivery_suppressed

    @property
    def last_generation_admission(
        self,
    ) -> GenerationAdmissionDecision[VoiceSynthesisResultEnvelope] | None:
        with self._lock:
            return self._last_generation_admission

    def _validated_capability(self) -> RealtimeVoiceOutputCapability:
        base = self._capability
        metadata = {
            **dict(base.public_metadata),
            "framework_cooperative_cancel": True,
            "provider_hard_cancel_verified": False,
            "generation_gate_stale_guard": self._generation_gate is not None,
            "completed_artifact_invalidation": self._supports_invalidation(),
            "host_playback_owned": True,
        }
        return replace(
            base,
            generation_cancel_supported=True,
            provider_hard_cancel_supported=False,
            active_audio_invalidation_supported=self._supports_invalidation(),
            public_metadata=metadata,
        )

    def _supports_invalidation(self) -> bool:
        store = self._artifact_store
        return bool(
            store is not None
            and callable(getattr(store, "invalidate_generation", None))
        )

    def _invalidate_generation(self, generation_id: GenerationId | str) -> int:
        store = self._artifact_store
        if store is None:
            return 0
        invalidate = getattr(store, "invalidate_generation", None)
        if not callable(invalidate):
            return 0
        records = invalidate(generation_id)
        if not isinstance(records, tuple):
            raise TypeError(
                "artifact store invalidate_generation must return a tuple"
            )
        return len(records)

    def invalidate_completed(self, context: RealtimeStageContext) -> int:
        """Invalidate valid FW artifacts already bound to one generation."""

        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        return self._invalidate_generation(context.generation_id)

    def _claim_generation(
        self,
        *,
        context: RealtimeStageContext,
        work_id: SynthesisWorkId | str,
    ) -> VoiceSynthesisActiveGeneration:
        with self._lock:
            active = super()._claim_generation(
                context=context,
                work_id=work_id,
            )
            self._active_done = threading.Event()
            self._cancel_requested_work = None
            self._last_cancel_work_id = None
            self._last_cancel_result = None
            self._last_artifact_invalidated = False
            self._last_stale_delivery_suppressed = False
            self._last_generation_admission = None
            return active

    @staticmethod
    def _suppressed_result(
        result: VoiceOutputResult,
        *,
        reason: str,
    ) -> VoiceOutputResult:
        if reason not in {"cancelled", "stale"}:
            raise ValueError("suppression reason must be cancelled or stale")
        return VoiceOutputResult(
            request_state=reason,
            audio_ready=False,
            audio_format=result.audio_format,
            audio_url=None,
            audio_artifact_ref=None,
            message=(
                "Voice synthesis delivery was suppressed after cancellation."
                if reason == "cancelled"
                else "Stale voice synthesis delivery was suppressed."
            ),
            public_metadata={
                "boundary": "voice_synthesis",
                "reason": reason,
                "provider_result_suppressed": True,
            },
        )

    def _run_claimed(
        self,
        *,
        active: VoiceSynthesisActiveGeneration,
        request: VoiceOutputRequest,
    ) -> VoiceSynthesisResultEnvelope:
        if not isinstance(active, VoiceSynthesisActiveGeneration):
            raise TypeError("active must be VoiceSynthesisActiveGeneration")
        if not isinstance(request, VoiceOutputRequest):
            with self._lock:
                done = self._active_done
                self._release_generation(active.work_id)
                if done is not None:
                    done.set()
            raise TypeError("request must be a VoiceOutputRequest")

        with self._lock:
            if self._active_generation != active:
                raise RuntimeError(
                    "Voice synthesis work is not the active generation."
                )
            done = self._active_done
            if done is None:
                raise RuntimeError("Voice synthesis active completion signal is missing.")

        artifact_invalidated = False
        stale_suppressed = False
        try:
            result = self._adapter.synthesize(request)
            if not isinstance(result, VoiceOutputResult):
                raise TypeError(
                    "adapter synthesize result must be VoiceOutputResult"
                )

            with self._lock:
                if self._active_generation != active:
                    raise RuntimeError(
                        "Voice synthesis work is not the active generation."
                    )

                # Bind first so a just-produced FW artifact can be invalidated
                # before any suppressed completion leaves this boundary.
                self._bind_result_artifact(
                    context=active.context,
                    result=result,
                )
                envelope = VoiceSynthesisResultEnvelope(
                    context=active.context,
                    work_id=active.work_id,
                    result=result,
                )

                cancel_requested = (
                    self._cancel_requested_work == active.work_id
                )
                if not cancel_requested and self._generation_gate is not None:
                    admission = self._generation_gate.admit_completion(
                        RealtimeStageCompletionEnvelope(
                            turn_id=active.turn_id,
                            generation_id=active.generation_id,
                            stage="voice_output",
                            value=envelope,
                        )
                    )
                    self._last_generation_admission = admission
                    stale_suppressed = not admission.accepted

                if cancel_requested or stale_suppressed:
                    artifact_invalidated = (
                        self._invalidate_generation(
                            active.context.generation_id
                        )
                        > 0
                    )
                    result = self._suppressed_result(
                        result,
                        reason=(
                            "cancelled"
                            if cancel_requested
                            else "stale"
                        ),
                    )
                    envelope = VoiceSynthesisResultEnvelope(
                        context=active.context,
                        work_id=active.work_id,
                        result=result,
                    )

                self._last_artifact_invalidated = artifact_invalidated
                self._last_stale_delivery_suppressed = (
                    cancel_requested or stale_suppressed
                )
                return envelope
        finally:
            with self._lock:
                self._release_generation(active.work_id)
                done.set()

    def cancel(
        self,
        *,
        context: RealtimeStageContext,
        work_id: SynthesisWorkId | str | None = None,
    ) -> VoiceSynthesisCancelResult:
        """Request cooperative cancellation and wait only for the bounded timeout."""

        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        requested_work_id = work_id
        if requested_work_id is not None and not isinstance(
            requested_work_id,
            SynthesisWorkId,
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
                if (
                    self._last_cancel_result is not None
                    and self._last_cancel_result.context == context
                    and (
                        requested_work_id is None
                        or requested_work_id == self._last_cancel_work_id
                    )
                ):
                    return self._last_cancel_result
                return VoiceSynthesisCancelResult(
                    outcome=VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION,
                    context=context,
                    work_id=requested_work_id,
                    safe_message="No voice synthesis generation is active.",
                )

            if active.context != context or (
                requested_work_id is not None
                and requested_work_id != active.work_id
            ):
                return VoiceSynthesisCancelResult(
                    outcome=VoiceSynthesisCancelOutcome.WORK_MISMATCH,
                    context=context,
                    work_id=requested_work_id,
                    safe_message="Requested voice synthesis work is not active.",
                )

            if (
                self._last_cancel_result is not None
                and self._last_cancel_work_id == active.work_id
            ):
                return self._last_cancel_result

            self._cancel_requested_work = active.work_id
            done = self._active_done
            if done is None:
                raise RuntimeError(
                    "Voice synthesis active completion signal is missing."
                )

            # Invalidate any artifact that completed earlier in the same
            # lifecycle generation before waiting on this active provider call.
            invalidated_before_wait = (
                self._invalidate_generation(context.generation_id) > 0
            )

        completed = done.wait(timeout=self._cancel_timeout_seconds)

        with self._lock:
            if (
                self._last_cancel_result is not None
                and self._last_cancel_work_id == active.work_id
            ):
                return self._last_cancel_result

            artifact_invalidated = (
                invalidated_before_wait
                or (
                    completed
                    and self._last_artifact_invalidated
                )
            )
            outcome = (
                VoiceSynthesisCancelOutcome.COMPLETED
                if completed
                else VoiceSynthesisCancelOutcome.TIMED_OUT
            )
            result = VoiceSynthesisCancelResult(
                outcome=outcome,
                context=context,
                work_id=active.work_id,
                cooperative_cancel_requested=True,
                cooperative_cancel_completed=completed,
                provider_hard_cancel_applied=False,
                provider_hard_cancel_unsupported=True,
                artifact_invalidated=artifact_invalidated,
                future_delivery_suppressed=True,
                safe_message=(
                    "Voice synthesis cooperative cancellation completed."
                    if completed
                    else "Voice synthesis cooperative cancellation timed out."
                ),
                retryable=False,
                public_metadata={
                    "boundary": "voice_synthesis_cancel",
                    "provider_hard_cancel_supported": False,
                    "cancel_timeout_seconds": self._cancel_timeout_seconds,
                },
            )
            self._last_cancel_work_id = active.work_id
            self._last_cancel_result = result
            return result


class VoiceSynthesisOutputController:
    """Reference composition that keeps pending clear and active cancel distinct."""

    __slots__ = ("_queue", "_stage")

    def __init__(
        self,
        *,
        queue: BoundedVoiceSynthesisPendingQueue,
        stage: CancelableProviderNeutralVoiceSynthesisStage,
    ) -> None:
        if not isinstance(queue, BoundedVoiceSynthesisPendingQueue):
            raise TypeError(
                "queue must be BoundedVoiceSynthesisPendingQueue"
            )
        if not isinstance(stage, CancelableProviderNeutralVoiceSynthesisStage):
            raise TypeError(
                "stage must be CancelableProviderNeutralVoiceSynthesisStage"
            )
        self._queue = queue
        self._stage = stage

    def flush(
        self,
        *,
        context: RealtimeStageContext | None = None,
    ) -> VoiceSynthesisControlFlushResult:
        if context is not None and not isinstance(
            context,
            RealtimeStageContext,
        ):
            raise TypeError(
                "context must be a RealtimeStageContext or None"
            )

        pending = self._queue.clear_pending(context=context)
        active = self._stage.active_generation
        cancel_result: VoiceSynthesisCancelResult | None = None

        if active is not None and (
            context is None or active.context == context
        ):
            cancel_result = self._stage.cancel(
                context=active.context,
                work_id=active.work_id,
            )

        target_context = context
        if target_context is None and active is not None:
            target_context = active.context

        invalidated = (
            self._stage.invalidate_completed(target_context)
            if target_context is not None
            else 0
        )

        return VoiceSynthesisControlFlushResult(
            pending_clear_result=pending,
            active_cancel_result=cancel_result,
            completed_artifacts_invalidated=invalidated,
            public_metadata={
                "boundary": "voice_synthesis_output_control",
                "pending_clear_distinct_from_active_cancel": True,
                "host_playback_changed": False,
            },
        )
